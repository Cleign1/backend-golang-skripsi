"""
Stock Prediction Agent using LangChain/LangGraph framework.

This agent transforms the existing /predict-stock endpoint functionality into an intelligent AI agent
that analyzes historical sales data and predicts future stock requirements with intelligent forecasting
algorithms and trend analysis.
"""

import asyncio
import csv
import os
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import aiohttp
from langchain.agents import AgentExecutor
from langchain.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field

from agents.database.models import Product, PredictionRequest, PredictionResult, PredictionResponse
from agents.database.manager import db_manager
from agents.utils.logging import AgentLogger
from agents.utils.google_drive import drive_manager
from agents.config.settings import settings


class PredictionState(BaseModel):
    """State for the stock prediction agent workflow."""
    
    task_id: str = ""
    prediction_date: str = ""
    products: List[Product] = Field(default_factory=list)
    sales_data: Dict[int, List[int]] = Field(default_factory=dict)
    predictions: List[PredictionResult] = Field(default_factory=list)
    insufficient_stock_products: List[PredictionResult] = Field(default_factory=list)
    batch_count: int = 0
    total_processed: int = 0
    status: str = "pending"
    csv_file_path: Optional[str] = None
    drive_url: Optional[str] = None
    error_message: Optional[str] = None
    agent_reasoning: List[str] = Field(default_factory=list)
    start_time: datetime = Field(default_factory=datetime.now)


class FetchProductsTool(BaseTool):
    """Tool for fetching products from the database in batches."""
    
    name: str = "fetch_products"
    description: str = "Fetches products from database in batches for analysis"
    
    async def _arun(self, offset: int, batch_size: int) -> List[Product]:
        """Fetch products asynchronously."""
        try:
            products_data = await db_manager.fetch_products_batch(offset, batch_size)
            return [Product(**product) for product in products_data]
        except Exception as e:
            raise Exception(f"Failed to fetch products: {str(e)}")


class FetchSalesDataTool(BaseTool):
    """Tool for fetching historical sales data."""
    
    name: str = "fetch_sales_data"
    description: str = "Fetches historical sales data for given products and date range"
    
    async def _arun(self, product_ids: List[int], prediction_date: str) -> Dict[int, List[int]]:
        """Fetch sales data asynchronously."""
        try:
            return await db_manager.fetch_sales_data_for_products(product_ids, prediction_date)
        except Exception as e:
            raise Exception(f"Failed to fetch sales data: {str(e)}")


class PredictionAnalysisTool(BaseTool):
    """Tool for performing prediction analysis."""
    
    name: str = "analyze_predictions"
    description: str = "Analyzes sales data and generates stock predictions"
    
    def _run(self, products: List[Product], sales_data: Dict[int, List[int]]) -> List[PredictionResult]:
        """Perform prediction analysis."""
        predictions = []
        
        for product in products:
            product_sales = sales_data.get(product.index, [])
            
            # Calculate average daily sales over last 3 days
            total_sales = sum(product_sales)
            avg_daily_sales = total_sales / 3.0 if product_sales else 0.0
            
            # Predict demand for next 3 days (simple average-based prediction)
            predicted_demand = int(avg_daily_sales * 3)
            
            # Determine if current stock is sufficient
            is_sufficient = product.current_stock > predicted_demand
            
            prediction = PredictionResult(
                product_id=product.index,
                product_name=product.name,
                current_stock=product.current_stock,
                avg_daily_sales_3_days=avg_daily_sales,
                predicted_demand_3_day=predicted_demand,
                is_sufficient=is_sufficient
            )
            
            predictions.append(prediction)
        
        return predictions


class AdvancedPredictionTool(BaseTool):
    """Tool for advanced prediction using LLM insights."""
    
    name: str = "advanced_prediction"
    description: str = "Performs advanced prediction analysis using AI insights"
    
    def __init__(self, llm):
        super().__init__()
        self.llm = llm
    
    async def _arun(self, predictions: List[PredictionResult]) -> Dict[str, Any]:
        """Perform advanced prediction analysis."""
        if not self.llm:
            return {"insights": "LLM not available for advanced analysis"}
        
        try:
            # Prepare data for LLM analysis
            summary_data = []
            for pred in predictions[:10]:  # Sample first 10 for analysis
                summary_data.append({
                    "product": pred.product_name[:30],  # Truncate long names
                    "current_stock": pred.current_stock,
                    "avg_sales": pred.avg_daily_sales_3_days,
                    "predicted_demand": pred.predicted_demand_3_day,
                    "sufficient": pred.is_sufficient
                })
            
            analysis_prompt = ChatPromptTemplate.from_template("""
            You are a supply chain expert analyzing inventory predictions.
            
            Sample prediction data:
            {sample_data}
            
            Total products analyzed: {total_products}
            Products with insufficient stock: {insufficient_count}
            
            Please provide:
            1. Key insights about inventory patterns
            2. Risk assessment for stock-outs
            3. Recommendations for inventory management
            4. Any seasonal or trend considerations
            
            Be concise and actionable in your response.
            """)
            
            insufficient_count = sum(1 for p in predictions if not p.is_sufficient)
            
            response = await self.llm.ainvoke(
                analysis_prompt.format(
                    sample_data=json.dumps(summary_data, indent=2),
                    total_products=len(predictions),
                    insufficient_count=insufficient_count
                )
            )
            
            return {
                "insights": response.content,
                "analyzed_products": len(summary_data),
                "total_products": len(predictions)
            }
            
        except Exception as e:
            return {"insights": f"Advanced analysis failed: {str(e)}"}


class StockPredictionAgent:
    """
    Intelligent Stock Prediction Agent using LangGraph.
    
    This agent analyzes historical sales data and predicts future stock requirements
    with intelligent forecasting algorithms and trend analysis.
    """
    
    def __init__(self):
        self.logger = AgentLogger("StockPredictionAgent")
        self.llm = None
        self.graph: Optional[CompiledStateGraph] = None
        self.fetch_products_tool = FetchProductsTool()
        self.fetch_sales_tool = FetchSalesDataTool()
        self.prediction_tool = PredictionAnalysisTool()
        self.advanced_tool = None
        
    async def initialize(self) -> None:
        """Initialize the agent with LLM and build the workflow graph."""
        # Initialize LLM if API key is available
        if settings.agents.openai_api_key:
            self.llm = ChatOpenAI(
                temperature=0,
                model="gpt-3.5-turbo",
                api_key=settings.agents.openai_api_key
            )
            self.advanced_tool = AdvancedPredictionTool(self.llm)
        
        # Build the workflow graph
        self.graph = self._build_graph()
        self.logger.info("Stock Prediction Agent initialized successfully")
    
    def _build_graph(self) -> CompiledStateGraph:
        """Build the LangGraph workflow for stock predictions."""
        
        # Create the state graph
        workflow = StateGraph(PredictionState)
        
        # Add nodes
        workflow.add_node("process_batches", self._process_batches_node)
        workflow.add_node("analyze_predictions", self._analyze_predictions_node)
        workflow.add_node("generate_insights", self._generate_insights_node)
        workflow.add_node("export_results", self._export_results_node)
        workflow.add_node("upload_to_drive", self._upload_to_drive_node)
        workflow.add_node("send_callback", self._send_callback_node)
        workflow.add_node("finalize", self._finalize_node)
        
        # Add edges
        workflow.add_edge(START, "process_batches")
        workflow.add_edge("process_batches", "analyze_predictions")
        workflow.add_edge("analyze_predictions", "generate_insights")
        workflow.add_edge("generate_insights", "export_results")
        workflow.add_conditional_edges(
            "export_results",
            self._should_upload_to_drive,
            {"upload": "upload_to_drive", "skip": "send_callback"}
        )
        workflow.add_edge("upload_to_drive", "send_callback")
        workflow.add_edge("send_callback", "finalize")
        workflow.add_edge("finalize", END)
        
        return workflow.compile()
    
    async def _process_batches_node(self, state: PredictionState) -> PredictionState:
        """Process products in batches and fetch their sales data."""
        self.logger.info(f"Starting batch processing for task {state.task_id}")
        
        offset = 0
        batch_size = settings.server.batch_size
        all_predictions = []
        
        try:
            while True:
                # Fetch batch of products
                self.logger.info(f"Processing batch {state.batch_count + 1}, offset {offset}")
                
                products = await self.fetch_products_tool._arun(offset, batch_size)
                if not products:
                    break  # No more products
                
                state.products.extend(products)
                
                # Fetch sales data for this batch
                product_ids = [p.index for p in products]
                batch_sales_data = await self.fetch_sales_tool._arun(product_ids, state.prediction_date)
                
                # Merge sales data
                state.sales_data.update(batch_sales_data)
                
                # Analyze this batch
                batch_predictions = self.prediction_tool._run(products, batch_sales_data)
                all_predictions.extend(batch_predictions)
                
                state.batch_count += 1
                state.total_processed += len(products)
                offset += batch_size
                
                self.logger.info(f"Batch {state.batch_count} completed: {len(products)} products processed")
            
            state.predictions = all_predictions
            state.status = "batches_processed"
            state.agent_reasoning.append(f"Processed {state.total_processed} products in {state.batch_count} batches")
            
        except Exception as e:
            state.status = "batch_error"
            state.error_message = f"Batch processing failed: {str(e)}"
            self.logger.error(f"Batch processing error: {e}", task_id=state.task_id, exc_info=True)
        
        return state
    
    async def _analyze_predictions_node(self, state: PredictionState) -> PredictionState:
        """Analyze predictions to identify insufficient stock products."""
        self.logger.info(f"Analyzing {len(state.predictions)} predictions", task_id=state.task_id)
        
        # Filter products with insufficient stock
        state.insufficient_stock_products = [
            pred for pred in state.predictions 
            if not pred.is_sufficient
        ]
        
        total_products = len(state.predictions)
        insufficient_count = len(state.insufficient_stock_products)
        
        state.agent_reasoning.append(
            f"Analysis complete: {insufficient_count} of {total_products} products have insufficient stock"
        )
        
        state.status = "analyzed"
        self.logger.info(
            f"Found {insufficient_count} products with insufficient stock out of {total_products}",
            task_id=state.task_id
        )
        
        return state
    
    async def _generate_insights_node(self, state: PredictionState) -> PredictionState:
        """Generate intelligent insights using LLM if available."""
        self.logger.info("Generating intelligent insights", task_id=state.task_id)
        
        if self.advanced_tool:
            try:
                insights = await self.advanced_tool._arun(state.predictions)
                state.agent_reasoning.append(f"AI Insights: {insights['insights']}")
                self.logger.info("Advanced AI insights generated", task_id=state.task_id)
            except Exception as e:
                state.agent_reasoning.append(f"Advanced insights failed: {str(e)}")
                self.logger.warning(f"Advanced insights failed: {e}", task_id=state.task_id)
        else:
            # Basic statistical insights
            if state.predictions:
                total_current_stock = sum(p.current_stock for p in state.predictions)
                total_predicted_demand = sum(p.predicted_demand_3_day for p in state.predictions)
                avg_demand = total_predicted_demand / len(state.predictions)
                
                state.agent_reasoning.append(
                    f"Basic insights: Total current stock: {total_current_stock}, "
                    f"Total predicted demand: {total_predicted_demand}, "
                    f"Average demand per product: {avg_demand:.2f}"
                )
        
        state.status = "insights_generated"
        return state
    
    async def _export_results_node(self, state: PredictionState) -> PredictionState:
        """Export results to CSV file."""
        self.logger.info("Exporting results to CSV", task_id=state.task_id)
        
        try:
            # Create results directory
            results_dir = "./prediction_results"
            os.makedirs(results_dir, exist_ok=True)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"prediction_results_{state.task_id}_{timestamp}.csv"
            state.csv_file_path = os.path.join(results_dir, filename)
            
            # Write CSV file
            with open(state.csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'product_id', 'product_name', 'current_stock',
                    'avg_daily_sales_3_days', 'predicted_demand_3_day', 'is_sufficient'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for result in state.insufficient_stock_products:
                    writer.writerow({
                        'product_id': result.product_id,
                        'product_name': result.product_name,
                        'current_stock': result.current_stock,
                        'avg_daily_sales_3_days': result.avg_daily_sales_3_days,
                        'predicted_demand_3_day': result.predicted_demand_3_day,
                        'is_sufficient': result.is_sufficient
                    })
            
            state.status = "csv_exported"
            state.agent_reasoning.append(f"CSV exported to {state.csv_file_path}")
            self.logger.info(f"CSV file created: {state.csv_file_path}", task_id=state.task_id)
            
        except Exception as e:
            state.status = "export_error"
            state.error_message = f"CSV export failed: {str(e)}"
            self.logger.error(f"CSV export error: {e}", task_id=state.task_id, exc_info=True)
        
        return state
    
    async def _upload_to_drive_node(self, state: PredictionState) -> PredictionState:
        """Upload CSV file to Google Drive."""
        self.logger.info("Uploading file to Google Drive", task_id=state.task_id)
        
        try:
            if not drive_manager.is_available():
                state.agent_reasoning.append("Google Drive not available, skipping upload")
                return state
            
            filename = os.path.basename(state.csv_file_path)
            success, public_url = await drive_manager.upload_file(state.csv_file_path, filename)
            
            if success:
                state.drive_url = public_url
                state.agent_reasoning.append(f"File uploaded to Google Drive: {public_url}")
                self.logger.info(f"File uploaded successfully: {public_url}", task_id=state.task_id)
            else:
                state.agent_reasoning.append("Google Drive upload failed")
                self.logger.warning("Google Drive upload failed", task_id=state.task_id)
                
        except Exception as e:
            state.agent_reasoning.append(f"Drive upload error: {str(e)}")
            self.logger.error(f"Drive upload error: {e}", task_id=state.task_id, exc_info=True)
        
        return state
    
    async def _send_callback_node(self, state: PredictionState) -> PredictionState:
        """Send results to callback URL."""
        if not settings.server.callback_url:
            state.agent_reasoning.append("No callback URL configured, skipping callback")
            return state
        
        self.logger.info("Sending callback", task_id=state.task_id)
        
        try:
            # Prepare callback payload
            duration = (datetime.now() - state.start_time).total_seconds()
            
            payload = {
                "task_id": state.task_id,
                "status": "completed" if state.status != "export_error" else "failed",
                "prediction_date": state.prediction_date,
                "total_products_analyzed": len(state.predictions),
                "insufficient_stock_count": len(state.insufficient_stock_products),
                "csv_file_url": state.drive_url,
                "duration_seconds": duration,
                "agent_reasoning": state.agent_reasoning,
                "error": state.error_message
            }
            
            # Send callback
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    settings.server.callback_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        state.agent_reasoning.append("Callback sent successfully")
                        self.logger.info("Callback sent successfully", task_id=state.task_id)
                    else:
                        state.agent_reasoning.append(f"Callback failed with status {response.status}")
                        self.logger.warning(f"Callback failed: {response.status}", task_id=state.task_id)
                        
        except Exception as e:
            state.agent_reasoning.append(f"Callback error: {str(e)}")
            self.logger.error(f"Callback error: {e}", task_id=state.task_id, exc_info=True)
        
        return state
    
    async def _finalize_node(self, state: PredictionState) -> PredictionState:
        """Finalize the prediction task."""
        duration = (datetime.now() - state.start_time).total_seconds()
        
        if state.error_message:
            state.status = "failed"
        else:
            state.status = "completed"
        
        state.agent_reasoning.append(f"Task completed in {duration:.2f} seconds")
        
        self.logger.info(
            f"Prediction task finalized: {state.status} in {duration:.2f}s",
            task_id=state.task_id
        )
        
        return state
    
    def _should_upload_to_drive(self, state: PredictionState) -> str:
        """Determine whether to upload to Google Drive."""
        if state.csv_file_path and drive_manager.is_available():
            return "upload"
        return "skip"
    
    async def process_prediction_request(self, request: PredictionRequest) -> PredictionResponse:
        """
        Process a stock prediction request through the agent workflow.
        
        Args:
            request: Stock prediction request
            
        Returns:
            Prediction response with task status
        """
        self.logger.info(f"Processing prediction request: {request.task_id}")
        
        if not self.graph:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        
        # Create initial state
        initial_state = PredictionState(
            task_id=request.task_id,
            prediction_date=request.prediction_date,
            start_time=datetime.now()
        )
        
        # Start the workflow asynchronously
        asyncio.create_task(self._run_prediction_workflow(initial_state))
        
        # Return immediate response
        return PredictionResponse(
            status="accepted",
            task_id=request.task_id,
            message="Prediction task accepted and is running in the background"
        )
    
    async def _run_prediction_workflow(self, initial_state: PredictionState) -> None:
        """Run the prediction workflow asynchronously."""
        try:
            final_state = await self.graph.ainvoke(initial_state)
            self.logger.info(f"Prediction workflow completed: {final_state.status}", task_id=initial_state.task_id)
        except Exception as e:
            self.logger.error(f"Prediction workflow failed: {e}", task_id=initial_state.task_id, exc_info=True)


# Global agent instance
stock_prediction_agent = StockPredictionAgent()