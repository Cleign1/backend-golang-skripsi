"""
Stock Update Agent using LangChain/LangGraph framework.

This agent transforms the existing /update-stock endpoint functionality into an intelligent AI agent
that can process sales data and update stock levels with validation, error handling, and decision making.
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from langchain.agents import AgentExecutor
from langchain.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field

from agents.database.models import SaleData, StockUpdateRequest, StockUpdateResponse
from agents.database.manager import db_manager
from agents.utils.logging import AgentLogger
from agents.config.settings import settings


class StockUpdateState(BaseModel):
    """State for the stock update agent workflow."""
    
    sales_data: List[SaleData] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)
    processed_count: int = 0
    failed_count: int = 0
    total_rows_affected: int = 0
    status: str = "pending"
    message: str = ""
    agent_reasoning: List[str] = Field(default_factory=list)


class ValidateSalesDataTool(BaseTool):
    """Tool for validating sales data before processing."""
    
    name: str = "validate_sales_data"
    description: str = "Validates sales data for consistency and business rules"
    
    def _run(self, sales_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate sales data."""
        errors = []
        validated_sales = []
        
        for i, sale in enumerate(sales_data):
            try:
                # Validate required fields
                if 'index' not in sale or 'quantity_sold' not in sale:
                    errors.append(f"Sale {i}: Missing required fields")
                    continue
                
                # Convert and validate data types
                try:
                    index = int(sale['index'])
                    quantity_sold = int(sale['quantity_sold'])
                except (ValueError, TypeError):
                    errors.append(f"Sale {i}: Invalid data types")
                    continue
                
                # Business rule validation
                if index <= 0:
                    errors.append(f"Sale {i}: Product index must be positive")
                    continue
                
                if quantity_sold <= 0:
                    errors.append(f"Sale {i}: Quantity sold must be positive")
                    continue
                
                if quantity_sold > 10000:  # Reasonable upper limit
                    errors.append(f"Sale {i}: Quantity sold seems unreasonably high ({quantity_sold})")
                    continue
                
                validated_sales.append(SaleData(index=index, quantity_sold=quantity_sold))
                
            except Exception as e:
                errors.append(f"Sale {i}: Validation error - {str(e)}")
        
        return {
            "valid_sales": validated_sales,
            "errors": errors,
            "validation_passed": len(errors) == 0
        }


class UpdateStockTool(BaseTool):
    """Tool for updating stock levels in the database."""
    
    name: str = "update_stock"
    description: str = "Updates stock levels in the database based on validated sales data"
    
    async def _arun(self, sales_data: List[SaleData]) -> Dict[str, Any]:
        """Update stock levels asynchronously."""
        try:
            # Convert to format expected by database manager
            sales_dict = [{"index": sale.index, "quantity_sold": sale.quantity_sold} for sale in sales_data]
            
            # Perform the batch update
            rows_affected = await db_manager.update_stock_batch(sales_dict)
            
            return {
                "success": True,
                "rows_affected": rows_affected,
                "message": f"Successfully updated stock for {rows_affected} products"
            }
            
        except Exception as e:
            return {
                "success": False,
                "rows_affected": 0,
                "message": f"Database update failed: {str(e)}"
            }


class StockUpdateAgent:
    """
    Intelligent Stock Update Agent using LangGraph.
    
    This agent processes sales data with intelligent validation, error handling,
    and decision-making capabilities.
    """
    
    def __init__(self):
        self.logger = AgentLogger("StockUpdateAgent")
        self.llm = None
        self.graph: Optional[CompiledStateGraph] = None
        self.validate_tool = ValidateSalesDataTool()
        self.update_tool = UpdateStockTool()
        
    async def initialize(self) -> None:
        """Initialize the agent with LLM and build the workflow graph."""
        # Initialize LLM if API key is available
        if settings.agents.openai_api_key:
            self.llm = ChatOpenAI(
                temperature=0,
                model="gpt-3.5-turbo",
                api_key=settings.agents.openai_api_key
            )
        
        # Build the workflow graph
        self.graph = self._build_graph()
        self.logger.info("Stock Update Agent initialized successfully")
    
    def _build_graph(self) -> CompiledStateGraph:
        """Build the LangGraph workflow for stock updates."""
        
        # Create the state graph
        workflow = StateGraph(StockUpdateState)
        
        # Add nodes
        workflow.add_node("validate", self._validate_node)
        workflow.add_node("analyze", self._analyze_node)
        workflow.add_node("update", self._update_node)
        workflow.add_node("finalize", self._finalize_node)
        
        # Add edges
        workflow.add_edge(START, "validate")
        workflow.add_conditional_edges(
            "validate",
            self._should_continue_after_validation,
            {"continue": "analyze", "stop": "finalize"}
        )
        workflow.add_edge("analyze", "update")
        workflow.add_edge("update", "finalize")
        workflow.add_edge("finalize", END)
        
        return workflow.compile()
    
    async def _validate_node(self, state: StockUpdateState) -> StockUpdateState:
        """Validation node - validates sales data."""
        self.logger.info(f"Validating {len(state.sales_data)} sales records")
        
        # Convert to dict format for validation tool
        sales_dict = [{"index": sale.index, "quantity_sold": sale.quantity_sold} for sale in state.sales_data]
        
        # Run validation
        validation_result = self.validate_tool._run(sales_dict)
        
        state.sales_data = validation_result["valid_sales"]
        state.validation_errors = validation_result["errors"]
        state.agent_reasoning.append(f"Validation completed: {len(state.sales_data)} valid records, {len(state.validation_errors)} errors")
        
        if validation_result["validation_passed"]:
            state.status = "validated"
        else:
            state.status = "validation_failed"
            state.message = f"Validation failed with {len(state.validation_errors)} errors"
        
        return state
    
    async def _analyze_node(self, state: StockUpdateState) -> StockUpdateState:
        """Analysis node - performs intelligent analysis if LLM is available."""
        self.logger.info("Analyzing sales data for patterns and anomalies")
        
        if self.llm:
            # Use LLM for intelligent analysis
            analysis_prompt = ChatPromptTemplate.from_template("""
            You are a stock management expert analyzing sales data for potential issues.
            
            Sales data summary:
            - Total records: {total_records}
            - Validation errors: {validation_errors}
            
            Sample sales data: {sample_data}
            
            Please analyze this data and provide:
            1. Any potential issues or anomalies
            2. Recommendations for processing
            3. Risk assessment (low/medium/high)
            
            Keep your response concise and actionable.
            """)
            
            try:
                # Prepare sample data (first 5 records)
                sample_data = state.sales_data[:5] if state.sales_data else []
                sample_str = "\n".join([f"Product {sale.index}: {sale.quantity_sold} units" for sale in sample_data])
                
                response = await self.llm.ainvoke(
                    analysis_prompt.format(
                        total_records=len(state.sales_data),
                        validation_errors=len(state.validation_errors),
                        sample_data=sample_str
                    )
                )
                
                state.agent_reasoning.append(f"LLM Analysis: {response.content}")
                
            except Exception as e:
                self.logger.warning(f"LLM analysis failed: {e}")
                state.agent_reasoning.append("LLM analysis unavailable, proceeding with standard processing")
        else:
            # Basic rule-based analysis
            total_quantity = sum(sale.quantity_sold for sale in state.sales_data)
            avg_quantity = total_quantity / len(state.sales_data) if state.sales_data else 0
            
            state.agent_reasoning.append(f"Basic analysis: {len(state.sales_data)} records, total quantity: {total_quantity}, avg: {avg_quantity:.2f}")
        
        state.status = "analyzed"
        return state
    
    async def _update_node(self, state: StockUpdateState) -> StockUpdateState:
        """Update node - performs the actual stock update."""
        self.logger.info(f"Updating stock for {len(state.sales_data)} products")
        
        try:
            # Perform the update
            update_result = await self.update_tool._arun(state.sales_data)
            
            if update_result["success"]:
                state.total_rows_affected = update_result["rows_affected"]
                state.processed_count = len(state.sales_data)
                state.status = "completed"
                state.message = update_result["message"]
                state.agent_reasoning.append(f"Successfully updated {state.total_rows_affected} records")
            else:
                state.status = "update_failed"
                state.message = update_result["message"]
                state.failed_count = len(state.sales_data)
                state.agent_reasoning.append(f"Update failed: {update_result['message']}")
                
        except Exception as e:
            state.status = "error"
            state.message = f"Unexpected error during update: {str(e)}"
            state.failed_count = len(state.sales_data)
            state.agent_reasoning.append(f"Error: {str(e)}")
            self.logger.error(f"Update error: {e}", exc_info=True)
        
        return state
    
    async def _finalize_node(self, state: StockUpdateState) -> StockUpdateState:
        """Finalization node - prepares final response."""
        self.logger.info(f"Finalizing stock update: status={state.status}")
        
        if state.status == "validation_failed":
            state.message = f"Validation failed: {'; '.join(state.validation_errors[:5])}"  # Show first 5 errors
        elif state.status == "completed":
            state.message = f"Stock update completed successfully. Updated {state.total_rows_affected} products."
        
        state.agent_reasoning.append("Processing completed")
        return state
    
    def _should_continue_after_validation(self, state: StockUpdateState) -> str:
        """Determine whether to continue processing after validation."""
        if state.status == "validation_failed":
            return "stop"
        return "continue"
    
    async def process_stock_update(self, request: StockUpdateRequest) -> StockUpdateResponse:
        """
        Process a stock update request through the agent workflow.
        
        Args:
            request: Stock update request containing sales data
            
        Returns:
            Stock update response with results
        """
        self.logger.info(f"Processing stock update request with {len(request.sales)} items")
        
        if not self.graph:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        
        # Create initial state
        initial_state = StockUpdateState(sales_data=request.sales)
        
        try:
            # Execute the workflow
            final_state = await self.graph.ainvoke(initial_state)
            
            # Create response
            response = StockUpdateResponse(
                status=final_state.status,
                message=final_state.message,
                rows_affected=final_state.total_rows_affected if final_state.status == "completed" else None
            )
            
            self.logger.info(f"Stock update completed: {response.status}")
            return response
            
        except Exception as e:
            self.logger.error(f"Stock update failed: {e}", exc_info=True)
            return StockUpdateResponse(
                status="error",
                message=f"Processing failed: {str(e)}"
            )


# Global agent instance
stock_update_agent = StockUpdateAgent()