from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class SaleData(BaseModel):
    index: int
    quantity_sold: int


class PredictionRequest(BaseModel):
    prediction_date: str
    task_id: str


class Product(BaseModel):
    index: int
    name: str
    current_stock: int


class PredictionResult(BaseModel):
    product_id: int
    product_name: str
    current_stock: int
    avg_daily_sales_3_days: float
    predicted_demand_3_day: int
    is_sufficient: bool


class StockUpdateResponse(BaseModel):
    status: str
    message: str


class PredictionResponse(BaseModel):
    status: str
    task_id: str


class PredictionTaskResult(BaseModel):
    task_id: str
    status: str
    products_flagged: int
    file_location: str
    drive_url: Optional[str] = None
    insufficient_stock_list: List[PredictionResult]
    last_message: str