from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import TypedDict, List, Dict, Any, Optional
import logging
import json
import asyncio
from datetime import datetime

from ..tools import (
    ProductBatchTool, SalesDataTool, CSVGeneratorTool, 
    GoogleDriveUploadTool, CallbackNotificationTool
)
from ..models import PredictionRequest, PredictionResult, PredictionTaskResult

logger = logging.getLogger(__name__)


class PredictionState(TypedDict):
    """State for the prediction workflow."""
    task_id: str
    prediction_date: str
    offset: int
    batch_size: int
    all_products: List[Dict[str, Any]]
    insufficient_stock_products: List[Dict[str, Any]]
    current_batch: List[Dict[str, Any]]
    sales_data: Dict[int, List[int]]
    csv_file_path: Optional[str]
    drive_url: Optional[str]
    callback_url: str
    error_message: Optional[str]
    completed: bool


class StockPredictionAgent:
    """
    AI Agent responsible for predicting stock needs using LangGraph workflow.
    Uses Google Gemini LLM to analyze sales patterns and predict future demand.
    """
    
    def __init__(self, database_manager, google_api_key: str, batch_size: int = 500, 
             callback_url: str = "", credentials_path: str = "", drive_folder_id: str = ""):
        """Initialize the Stock Prediction Agent."""
        self.database_manager = database_manager
        self.batch_size = batch_size
        self.callback_url = callback_url
        
        # Initialize LLM
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=google_api_key,
            temperature=0.1
        )
        
        # Initialize tools with keyword arguments
        self.product_batch_tool = ProductBatchTool(database_manager=database_manager)
        self.sales_data_tool = SalesDataTool(database_manager=database_manager)
        self.csv_generator_tool = CSVGeneratorTool()
        
        if credentials_path and drive_folder_id:
            self.drive_upload_tool = GoogleDriveUploadTool(
                credentials_path=credentials_path,
                folder_id=drive_folder_id
            )
        else:
            self.drive_upload_tool = None
        
        if callback_url:
            self.callback_tool = CallbackNotificationTool()
        else:
            self.callback_tool = None
        
        # Create the workflow graph
        self.workflow = self._create_workflow()
    
    def _create_workflow(self) -> StateGraph:
        """Create the LangGraph workflow for stock prediction."""
        
        def fetch_product_batch(state: PredictionState) -> PredictionState:
            """Fetch a batch of products from the database."""
            try:
                logger.info(f"[Task {state['task_id']}] Fetching products at offset {state['offset']}")
                
                result = self.product_batch_tool._run(state["offset"], state["batch_size"])
                products = json.loads(result) if isinstance(result, str) and result.startswith('[') else []
                
                state["current_batch"] = products
                state["all_products"].extend(products)
                
                if not products:
                    state["completed"] = True
                    logger.info(f"[Task {state['task_id']}] All products fetched. Total: {len(state['all_products'])}")
                
                return state
                
            except Exception as e:
                logger.error(f"[Task {state['task_id']}] Error fetching products: {e}")
                state["error_message"] = f"Error fetching products: {str(e)}"
                return state
        
        def analyze_batch_with_ai(state: PredictionState) -> PredictionState:
            """Use AI to analyze the current batch of products."""
            try:
                if not state["current_batch"]:
                    return state
                
                logger.info(f"[Task {state['task_id']}] AI analyzing batch of {len(state['current_batch'])} products")
                
                # Extract product IDs for sales data fetch
                product_ids = [p["index"] for p in state["current_batch"]]
                
                # Fetch sales data
                sales_result = self.sales_data_tool._run(product_ids, state["prediction_date"])
                sales_data = json.loads(sales_result) if isinstance(sales_result, str) and sales_result.startswith('{') else {}
                
                # Use AI to analyze each product
                analysis_prompt = f"""
                You are analyzing product sales data to predict stock sufficiency. 
                
                Current batch of products: {json.dumps(state['current_batch'], indent=2)}
                Recent sales data (last 3 days): {json.dumps(sales_data, indent=2)}
                
                For each product, calculate:
                1. Average daily sales over the last 3 days
                2. Predicted demand for the next 3 days (average * 3)
                3. Whether current stock is sufficient (current_stock > predicted_demand)
                
                Return a JSON array of products that have INSUFFICIENT stock, with this format:
                [
                    {{
                        "product_id": int,
                        "product_name": str,
                        "current_stock": int,
                        "avg_daily_sales_3_days": float,
                        "predicted_demand_3_day": int,
                        "is_sufficient": false
                    }}
                ]
                
                Only include products where is_sufficient is false.
                """
                
                # Get AI analysis
                ai_response = self.llm.invoke(analysis_prompt)
                
                try:
                    # Parse AI response
                    insufficient_products = json.loads(ai_response.content)
                    if isinstance(insufficient_products, list):
                        state["insufficient_stock_products"].extend(insufficient_products)
                        logger.info(f"[Task {state['task_id']}] Found {len(insufficient_products)} products with insufficient stock in this batch")
                except json.JSONDecodeError:
                    # Fallback to manual calculation if AI response isn't valid JSON
                    logger.warning(f"[Task {state['task_id']}] AI response not valid JSON, falling back to manual calculation")
                    for product in state["current_batch"]:
                        product_id = product["index"]
                        product_sales = sales_data.get(str(product_id), [])
                        
                        total_sales = sum(product_sales)
                        avg_sales = total_sales / 3.0 if len(product_sales) > 0 else 0
                        predicted_demand = int(avg_sales * 3)
                        is_sufficient = product["stock"] > predicted_demand
                        
                        if not is_sufficient:
                            state["insufficient_stock_products"].append({
                                "product_id": product_id,
                                "product_name": product["name"],
                                "current_stock": product["stock"],
                                "avg_daily_sales_3_days": avg_sales,
                                "predicted_demand_3_day": predicted_demand,
                                "is_sufficient": False
                            })
                
                # Update offset for next batch
                state["offset"] += state["batch_size"]
                
                return state
                
            except Exception as e:
                logger.error(f"[Task {state['task_id']}] Error in AI analysis: {e}")
                state["error_message"] = f"Error in analysis: {str(e)}"
                return state
        
        def generate_report(state: PredictionState) -> PredictionState:
            """Generate CSV report of insufficient stock products."""
            try:
                logger.info(f"[Task {state['task_id']}] Generating CSV report with {len(state['insufficient_stock_products'])} products")
                
                csv_path = self.csv_generator_tool._run(
                    state["insufficient_stock_products"],
                    state["task_id"]
                )
                
                if csv_path and not csv_path.startswith("Error"):
                    state["csv_file_path"] = csv_path
                    logger.info(f"[Task {state['task_id']}] CSV report generated: {csv_path}")
                else:
                    state["error_message"] = csv_path or "Failed to generate CSV"
                
                return state
                
            except Exception as e:
                logger.error(f"[Task {state['task_id']}] Error generating report: {e}")
                state["error_message"] = f"Error generating report: {str(e)}"
                return state
        
        def upload_to_drive(state: PredictionState) -> PredictionState:
            """Upload the CSV report to Google Drive."""
            try:
                if not state.get("csv_file_path") or not self.drive_upload_tool:
                    logger.info(f"[Task {state['task_id']}] Skipping Google Drive upload")
                    return state
                
                logger.info(f"[Task {state['task_id']}] Uploading to Google Drive")
                
                filename = f"prediction_result_{state['task_id']}.csv"
                drive_url = self.drive_upload_tool._run(state["csv_file_path"], filename)
                
                if drive_url and not drive_url.startswith("Error"):
                    state["drive_url"] = drive_url
                    logger.info(f"[Task {state['task_id']}] Uploaded to Google Drive: {drive_url}")
                else:
                    logger.warning(f"[Task {state['task_id']}] Google Drive upload failed: {drive_url}")
                
                return state
                
            except Exception as e:
                logger.error(f"[Task {state['task_id']}] Error uploading to Drive: {e}")
                return state
        
        def send_callback_notification(state: PredictionState) -> PredictionState:
            """Send completion callback to the Flask app."""
            try:
                if not state.get("callback_url") or not self.callback_tool:
                    logger.info(f"[Task {state['task_id']}] No callback URL provided or callback tool not available")
                    return state
                
                logger.info(f"[Task {state['task_id']}] Sending callback notification")
                
                callback_payload = {
                    "task_id": state["task_id"],
                    "status": "Done" if not state.get("error_message") else "Error",
                    "products_flagged": len(state["insufficient_stock_products"]),
                    "file_location": state.get("csv_file_path", ""),
                    "drive_url": state.get("drive_url", ""),
                    "insufficient_stock_list": state["insufficient_stock_products"],
                    "last_message": "Prediksi Selesai, Silahkan cek Summary" if not state.get("error_message") else state["error_message"]
                }
                
                callback_result = self.callback_tool._run(state["callback_url"], callback_payload)
                logger.info(f"[Task {state['task_id']}] Callback result: {callback_result}")
                
                return state
                
            except Exception as e:
                logger.error(f"[Task {state['task_id']}] Error sending callback: {e}")
                return state
        
        def should_continue(state: PredictionState) -> str:
            """Determine if workflow should continue processing batches."""
            if state.get("error_message"):
                return "generate_report"
            elif state.get("completed"):
                return "generate_report"
            else:
                return "fetch_products"
        
        # Build the workflow graph
        workflow = StateGraph(PredictionState)
        
        # Add nodes
        workflow.add_node("fetch_products", fetch_product_batch)
        workflow.add_node("analyze_batch", analyze_batch_with_ai)
        workflow.add_node("generate_report", generate_report)
        workflow.add_node("upload_to_drive", upload_to_drive)
        workflow.add_node("send_callback", send_callback_notification)
        
        # Add edges
        workflow.set_entry_point("fetch_products")
        workflow.add_conditional_edges("fetch_products", should_continue)
        workflow.add_edge("analyze_batch", "fetch_products")
        workflow.add_edge("generate_report", "upload_to_drive")
        workflow.add_edge("upload_to_drive", "send_callback")
        workflow.add_edge("send_callback", END)
        
        return workflow.compile()
    
    async def process_prediction_request(self, request: PredictionRequest) -> str:
        """
        Process a stock prediction request asynchronously.
        """
        try:
            logger.info(f"[Task {request.task_id}] Starting stock prediction analysis")
            
            # Initialize state
            initial_state = PredictionState(
                task_id=request.task_id,
                prediction_date=request.prediction_date,
                offset=0,
                batch_size=self.batch_size,
                all_products=[],
                insufficient_stock_products=[],
                current_batch=[],
                sales_data={},
                csv_file_path=None,
                drive_url=None,
                callback_url=self.callback_url,
                error_message=None,
                completed=False
            )
            
            # Execute the workflow
            final_state = await self.workflow.ainvoke(initial_state)
            
            status = "completed" if not final_state.get("error_message") else "error"
            logger.info(f"[Task {request.task_id}] Prediction analysis {status}")
            
            return f"Prediction task {request.task_id} {status}"
            
        except Exception as e:
            logger.error(f"[Task {request.task_id}] Error in prediction workflow: {e}")
            return f"Error in prediction task {request.task_id}: {str(e)}"