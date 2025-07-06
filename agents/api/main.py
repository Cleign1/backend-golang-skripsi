"""
FastAPI application for AI Agents Stock Management System.

This module provides RESTful API endpoints for interacting with the
Stock Update and Stock Prediction agents through the orchestrator.
"""

from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import asyncio
from contextlib import asynccontextmanager

from agents.database.models import (
    StockUpdateRequest, StockUpdateResponse,
    PredictionRequest, PredictionResponse,
    AgentStatus, TaskResult
)
from agents.orchestrator.coordinator import orchestrator, AgentType
from agents.config.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    success = await orchestrator.initialize()
    if not success:
        raise RuntimeError("Failed to initialize orchestrator")
    
    yield
    
    # Shutdown
    await orchestrator.shutdown()


# Create FastAPI application
app = FastAPI(
    title="AI Agents Stock Management System",
    description="Intelligent stock management system using LangChain/LangGraph agents",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def check_orchestrator_ready():
    """Dependency to check if orchestrator is ready."""
    if orchestrator.status.value != "ready":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready. Please try again later."
        )
    return orchestrator


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "AI Agents Stock Management System",
        "version": "1.0.0",
        "framework": "LangChain/LangGraph",
        "endpoints": {
            "update_stock": "/agents/update-stock",
            "predict_stock": "/agents/predict-stock",
            "health": "/health",
            "status": "/status",
            "agents": "/agents/status",
            "tasks": "/tasks"
        }
    }


@app.post("/agents/update-stock", response_model=StockUpdateResponse)
async def update_stock(
    request: StockUpdateRequest,
    orchestrator_instance = Depends(check_orchestrator_ready)
) -> StockUpdateResponse:
    """
    Update stock levels based on sales data through the Stock Update Agent.
    
    This endpoint processes sales data and updates stock levels with intelligent
    validation, error handling, and decision making.
    """
    try:
        return await orchestrator_instance.process_stock_update(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stock update processing failed: {str(e)}"
        )


@app.post("/agents/predict-stock", response_model=PredictionResponse)
async def predict_stock(
    request: PredictionRequest,
    orchestrator_instance = Depends(check_orchestrator_ready)
) -> PredictionResponse:
    """
    Initiate stock prediction analysis through the Stock Prediction Agent.
    
    This endpoint starts an asynchronous prediction task that analyzes historical
    sales data and predicts future stock requirements with intelligent forecasting.
    """
    try:
        return await orchestrator_instance.process_stock_prediction(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stock prediction processing failed: {str(e)}"
        )


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Comprehensive health check endpoint.
    
    Returns the health status of the orchestrator, agents, database,
    and external services.
    """
    try:
        return await orchestrator.health_check()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )


@app.get("/status")
async def service_status() -> Dict[str, Any]:
    """
    Get service status information.
    
    Returns basic status information about the service and orchestrator.
    """
    return {
        "status": orchestrator.status.value,
        "initialized_at": orchestrator.initialized_at.isoformat() if orchestrator.initialized_at else None,
        "agents_count": len(orchestrator.agents_status),
        "tasks_processed": len(orchestrator.task_history)
    }


@app.get("/agents/status")
async def agents_status() -> Dict[str, AgentStatus]:
    """
    Get status of all managed agents.
    
    Returns detailed status information for each agent including
    task counts, error counts, and last activity.
    """
    return orchestrator.agents_status


@app.get("/agents/{agent_type}/status")
async def agent_status(agent_type: str) -> AgentStatus:
    """
    Get status of a specific agent.
    
    Args:
        agent_type: Type of agent (stock_update or stock_prediction)
    """
    try:
        agent_enum = AgentType(agent_type)
        status = orchestrator.get_agent_status(agent_enum)
        if not status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_type} not found"
            )
        return status
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid agent type: {agent_type}. Valid types: stock_update, stock_prediction"
        )


@app.get("/tasks")
async def task_history(limit: int = 100) -> Dict[str, TaskResult]:
    """
    Get recent task history.
    
    Args:
        limit: Maximum number of tasks to return (default: 100)
    """
    return orchestrator.get_task_history(limit)


@app.get("/tasks/{task_id}")
async def task_result(task_id: str) -> TaskResult:
    """
    Get result of a specific task.
    
    Args:
        task_id: Task identifier
    """
    result = orchestrator.get_task_result(task_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )
    return result


@app.get("/config")
async def configuration_info() -> Dict[str, Any]:
    """
    Get configuration information (non-sensitive).
    
    Returns configuration information without exposing sensitive data.
    """
    return {
        "database": {
            "url_configured": bool(settings.database.url)
        },
        "google_drive": {
            "folder_id_configured": bool(settings.google_drive.folder_id),
            "credentials_configured": bool(settings.google_drive.credentials_path)
        },
        "server": {
            "port": settings.server.port,
            "batch_size": settings.server.batch_size,
            "callback_url_configured": bool(settings.server.callback_url)
        },
        "agents": {
            "openai_api_key_configured": bool(settings.agents.openai_api_key),
            "langchain_tracing_enabled": settings.agents.langchain_tracing_v2,
            "max_retries": settings.agents.max_retries,
            "timeout": settings.agents.timeout
        }
    }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "agents.api.main:app",
        host="0.0.0.0",
        port=settings.server.port,
        reload=False,
        log_level="info"
    )