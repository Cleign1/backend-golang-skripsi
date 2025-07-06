from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List
import os
import logging
import asyncio
from dotenv import load_dotenv

from src.database import DatabaseManager
from src.agents import StockUpdateAgent, StockPredictionAgent
from src.models import (
    SaleData, PredictionRequest, StockUpdateResponse, 
    PredictionResponse, PredictionTaskResult
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Stock Management AI Agents",
    description="LangChain/LangGraph AI agents for stock management using Google Gemini LLM",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for agents
database_manager = None
stock_update_agent = None
stock_prediction_agent = None


@app.on_event("startup")
async def startup_event():
    """Initialize database connection and agents on startup."""
    global database_manager, stock_update_agent, stock_prediction_agent
    
    try:
        # Environment variables
        database_url = os.getenv("DATABASE_URL")
        google_api_key = os.getenv("GOOGLE_API_KEY")
        batch_size = int(os.getenv("BATCH_SIZE", "500"))
        callback_url = os.getenv("CALLBACK_URL", "")
        credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "")
        drive_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
        
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        
        # Initialize database manager
        database_manager = DatabaseManager(database_url)
        
        # Test database connection
        if not database_manager.test_connection():
            raise Exception("Failed to connect to database")
        
        logger.info("Successfully connected to PostgreSQL database")
        
        # Initialize agents
        stock_update_agent = StockUpdateAgent(database_manager, google_api_key)
        stock_prediction_agent = StockPredictionAgent(
            database_manager=database_manager,
            google_api_key=google_api_key,
            batch_size=batch_size,
            callback_url=callback_url,
            credentials_path=credentials_path,
            drive_folder_id=drive_folder_id
        )
        
        logger.info("AI agents initialized successfully")
        logger.info("Available endpoints: POST /update-stock, POST /predict-stock")
        
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Stock Management AI Agents API",
        "version": "1.0.0",
        "description": "LangChain/LangGraph AI agents for intelligent stock management",
        "endpoints": {
            "POST /update-stock": "Updates stock based on sales data using AI agent",
            "POST /predict-stock": "Predicts stock needs using AI agent workflow",
            "GET /health": "Health check endpoint"
        },
        "ai_capabilities": [
            "Intelligent stock update validation using Google Gemini",
            "AI-powered sales pattern analysis",
            "Automated stock prediction with LangGraph workflow",
            "Smart error handling and reporting"
        ]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        db_healthy = database_manager and database_manager.test_connection()
        agents_healthy = stock_update_agent is not None and stock_prediction_agent is not None
        
        return {
            "status": "healthy" if db_healthy and agents_healthy else "unhealthy",
            "database": "connected" if db_healthy else "disconnected",
            "agents": "initialized" if agents_healthy else "not_initialized",
            "timestamp": "2024-01-01T00:00:00Z"
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "unhealthy", "error": str(e)}
        )


@app.post("/update-stock", response_model=StockUpdateResponse)
async def update_stock(sales_data: List[SaleData]):
    """
    Update stock levels based on sales data using AI agent.
    
    The AI agent will:
    - Validate the incoming sales data for correctness
    - Process stock updates efficiently and safely
    - Provide intelligent error handling and feedback
    """
    try:
        if not sales_data:
            return StockUpdateResponse(
                status="No update needed",
                message="No data provided for update."
            )
        
        logger.info(f"[Stock Update Agent] Processing {len(sales_data)} items")
        
        # Use AI agent to process the stock update
        response = stock_update_agent.process_stock_update(sales_data)
        
        logger.info(f"[Stock Update Agent] Completed: {response.status}")
        return response
        
    except Exception as e:
        logger.error(f"Error in update_stock endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/predict-stock", response_model=PredictionResponse)
async def predict_stock(request: PredictionRequest, background_tasks: BackgroundTasks):
    """
    Initiate stock prediction analysis using AI agent workflow.
    
    The AI agent workflow will:
    - Analyze historical sales patterns using Google Gemini
    - Predict future stock needs with intelligent batch processing
    - Generate comprehensive reports and notifications
    - Handle complex data processing with LangGraph state management
    """
    try:
        if not request.prediction_date or not request.task_id:
            raise HTTPException(
                status_code=400, 
                detail="Missing 'prediction_date' or 'task_id' in request body."
            )
        
        logger.info(f"[Stock Prediction Agent] Starting task {request.task_id} for date {request.prediction_date}")
        
        # Add the prediction task to background tasks
        background_tasks.add_task(
            run_prediction_task_async,
            stock_prediction_agent,
            request
        )
        
        return PredictionResponse(
            status="Prediction task accepted and is running in the background with AI workflow.",
            task_id=request.task_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in predict_stock endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


async def run_prediction_task_async(agent: StockPredictionAgent, request: PredictionRequest):
    """
    Run the prediction task asynchronously using the AI agent workflow.
    """
    try:
        result = await agent.process_prediction_request(request)
        logger.info(f"[Background Task] {result}")
    except Exception as e:
        logger.error(f"[Background Task] Error in prediction task {request.task_id}: {e}")


# Additional endpoints for agent management and monitoring

@app.get("/agents/status")
async def get_agents_status():
    """Get status of AI agents."""
    try:
        return {
            "stock_update_agent": {
                "initialized": stock_update_agent is not None,
                "model": "Google Gemini Pro",
                "capabilities": ["Sales data validation", "Stock update processing", "Error handling"]
            },
            "stock_prediction_agent": {
                "initialized": stock_prediction_agent is not None,
                "model": "Google Gemini Pro",
                "workflow": "LangGraph State Management",
                "capabilities": [
                    "Batch processing", "Sales pattern analysis", 
                    "Prediction generation", "Report creation",
                    "Google Drive integration", "Callback notifications"
                ]
            },
            "database": {
                "connected": database_manager and database_manager.test_connection()
            }
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Error getting agent status: {str(e)}"}
        )


@app.post("/validate-sales-data")
async def validate_sales_data(sales_data: List[SaleData]):
    """
    Validate sales data using the AI agent without performing updates.
    """
    try:
        if not stock_update_agent:
            raise HTTPException(status_code=500, detail="Stock update agent not initialized")
        
        # Convert to dict format for validation
        sales_dict = [sale.dict() for sale in sales_data]
        
        # Use AI agent to validate the data
        validation_result = stock_update_agent.validate_sales_data(sales_dict)
        
        return {
            "validation_result": validation_result,
            "data_count": len(sales_data)
        }
        
    except Exception as e:
        logger.error(f"Error in validate_sales_data endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)