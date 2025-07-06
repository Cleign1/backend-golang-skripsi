from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, SystemMessage
from typing import List, Dict, Any
import logging
import json

from ..tools import StockUpdateTool
from ..models import SaleData, StockUpdateResponse

logger = logging.getLogger(__name__)


class StockUpdateAgent:
    """
    AI Agent responsible for updating stock levels based on sales data.
    Uses Google Gemini LLM to intelligently process and validate stock updates.
    """
    
    def __init__(self, database_manager, google_api_key: str):
        """Initialize the Stock Update Agent."""
        self.database_manager = database_manager
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=google_api_key,
            temperature=0.1  # Low temperature for consistent, factual responses
        )
        
        # Initialize tool with keyword argument
        self.stock_update_tool = StockUpdateTool(database_manager=database_manager)
        
    def process_stock_update(self, sales_data: List[SaleData]) -> StockUpdateResponse:
        """
        Process stock update request using the AI agent.
        """
        try:
            # Convert Pydantic models to dictionaries
            sales_dict = [sale.dict() for sale in sales_data]
            
            # Validate data with AI first
            validation_result = self.validate_sales_data(sales_dict)
            
            if not validation_result.get("valid", False):
                issues = validation_result.get("issues", [])
                return StockUpdateResponse(
                    status="Validation Error",
                    message=f"Data validation failed: {', '.join(issues)}"
                )
            
            # Process the stock update using the tool
            result = self.stock_update_tool._run(sales_dict)
            
            # Parse the result and create response
            if "successfully updated" in result.lower():
                return StockUpdateResponse(
                    status="Process completed successfully",
                    message="Stok telah berhasil diperbarui."
                )
            else:
                return StockUpdateResponse(
                    status="Error",
                    message=result
                )
                
        except Exception as e:
            logger.error(f"Error in stock update agent: {e}")
            return StockUpdateResponse(
                status="Error",
                message=f"Database operation failed: {str(e)}"
            )
    
    def validate_sales_data(self, sales_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Use the AI agent to validate sales data before processing.
        """
        try:
            system_prompt = """You are a data validation AI assistant. Your task is to validate sales data for stock updates.

Check for the following issues:
1. Missing required fields (index, quantity_sold)
2. Invalid data types (index and quantity_sold should be integers)
3. Negative quantities (quantity_sold should be positive)
4. Duplicate entries (same index appearing multiple times)
5. Any other data quality issues

Respond with a JSON object containing:
- "valid": true/false
- "issues": array of issue descriptions
- "summary": brief summary of validation results"""

            validation_message = f"""
Please validate the following sales data:

{json.dumps(sales_data, indent=2)}

Total records: {len(sales_data)}
"""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=validation_message)
            ]
            
            response = self.llm.invoke(messages)
            
            # Try to parse JSON response
            try:
                # Extract JSON from response if it's wrapped in markdown or other text
                response_text = response.content.strip()
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end].strip()
                elif "```" in response_text:
                    json_start = response_text.find("```") + 3
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end].strip()
                
                validation_result = json.loads(response_text)
                return validation_result
            except json.JSONDecodeError:
                # Fallback: analyze the text response
                response_lower = response.content.lower()
                valid = "valid" in response_lower and "invalid" not in response_lower
                
                return {
                    "valid": valid,
                    "issues": [] if valid else ["AI validation could not parse response"],
                    "summary": response.content[:200] + "..." if len(response.content) > 200 else response.content
                }
                
        except Exception as e:
            logger.error(f"Error in validation: {e}")
            return {
                "valid": False,
                "issues": [f"Validation error: {str(e)}"],
                "summary": "Validation failed due to technical error"
            }