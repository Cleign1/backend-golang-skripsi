"""
Data models for the AI agents system.

This module defines Pydantic models for data validation and serialization
used across the stock management agents.
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator


class SaleData(BaseModel):
    """Model for individual sale data used in stock updates."""
    
    index: int = Field(..., description="Product index/ID")
    quantity_sold: int = Field(..., description="Quantity sold", gt=0)
    
    @validator('index')
    def validate_index(cls, v):
        if v <= 0:
            raise ValueError('Product index must be positive')
        return v


class Product(BaseModel):
    """Model for product information."""
    
    index: int = Field(..., description="Product index/ID")
    name: str = Field(..., description="Product name")
    current_stock: int = Field(..., description="Current stock level", ge=0)


class PredictionRequest(BaseModel):
    """Model for stock prediction requests."""
    
    prediction_date: str = Field(..., description="Date for prediction (YYYY-MM-DD format)")
    task_id: str = Field(..., description="Unique task identifier")
    
    @validator('prediction_date')
    def validate_prediction_date(cls, v):
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError('prediction_date must be in YYYY-MM-DD format')
        return v


class PredictionResult(BaseModel):
    """Model for individual product prediction results."""
    
    product_id: int = Field(..., description="Product ID")
    product_name: str = Field(..., description="Product name")
    current_stock: int = Field(..., description="Current stock level", ge=0)
    avg_daily_sales_3_days: float = Field(..., description="Average daily sales over last 3 days", ge=0)
    predicted_demand_3_day: int = Field(..., description="Predicted demand for next 3 days", ge=0)
    is_sufficient: bool = Field(..., description="Whether current stock is sufficient for predicted demand")


class StockUpdateRequest(BaseModel):
    """Model for stock update requests."""
    
    sales: List[SaleData] = Field(..., description="List of sales data")
    
    @validator('sales')
    def validate_sales_not_empty(cls, v):
        if not v:
            raise ValueError('Sales data cannot be empty')
        return v


class StockUpdateResponse(BaseModel):
    """Model for stock update responses."""
    
    status: str = Field(..., description="Operation status")
    message: str = Field(..., description="Response message")
    rows_affected: Optional[int] = Field(None, description="Number of rows affected")


class PredictionResponse(BaseModel):
    """Model for prediction task responses."""
    
    status: str = Field(..., description="Task status")
    task_id: str = Field(..., description="Task identifier")
    message: Optional[str] = Field(None, description="Additional message")


class AgentStatus(BaseModel):
    """Model for agent status information."""
    
    agent_name: str = Field(..., description="Name of the agent")
    status: str = Field(..., description="Current status")
    last_activity: Optional[datetime] = Field(None, description="Last activity timestamp")
    tasks_processed: int = Field(0, description="Number of tasks processed", ge=0)
    errors_count: int = Field(0, description="Number of errors encountered", ge=0)


class TaskResult(BaseModel):
    """Model for task execution results."""
    
    task_id: str = Field(..., description="Task identifier")
    agent_name: str = Field(..., description="Agent that executed the task")
    status: str = Field(..., description="Task execution status")
    result: Optional[dict] = Field(None, description="Task result data")
    error: Optional[str] = Field(None, description="Error message if task failed")
    started_at: datetime = Field(..., description="Task start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Task completion timestamp")
    duration_seconds: Optional[float] = Field(None, description="Task duration in seconds")