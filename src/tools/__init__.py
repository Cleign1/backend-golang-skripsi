from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, List, Dict, Any, Optional
import os
import csv
import json
import httpx
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class StockUpdateInput(BaseModel):
    sales_data: List[Dict[str, Any]] = Field(description="List of sales data with index and quantity_sold")


class StockUpdateTool(BaseTool):
    """Tool for updating stock based on sales data."""
    name: str = "stock_update"
    description: str = "Updates stock levels in the database based on sales data"
    args_schema: Type[BaseModel] = StockUpdateInput
    database_manager: Any = Field(description="Database manager instance")
    
    class Config:
        arbitrary_types_allowed = True
    
    def _run(self, sales_data: List[Dict[str, Any]]) -> str:
        """Update stock levels."""
        try:
            rows_affected = self.database_manager.update_stock(sales_data)
            return f"Successfully updated {rows_affected} rows. Stock levels have been updated."
        except Exception as e:
            logger.error(f"Error updating stock: {e}")
            return f"Error updating stock: {str(e)}"


class ProductBatchInput(BaseModel):
    offset: int = Field(description="Offset for pagination")
    batch_size: int = Field(description="Number of products to fetch")


class ProductBatchTool(BaseTool):
    """Tool for fetching product batches."""
    name: str = "fetch_product_batch"
    description: str = "Fetches a batch of products from the database"
    args_schema: Type[BaseModel] = ProductBatchInput
    database_manager: Any = Field(description="Database manager instance")
    
    class Config:
        arbitrary_types_allowed = True
    
    def _run(self, offset: int, batch_size: int) -> str:
        """Fetch product batch."""
        try:
            products = self.database_manager.fetch_product_batch(offset, batch_size)
            return json.dumps(products)
        except Exception as e:
            logger.error(f"Error fetching products: {e}")
            return f"Error fetching products: {str(e)}"


class SalesDataInput(BaseModel):
    product_ids: List[int] = Field(description="List of product IDs")
    prediction_date: str = Field(description="Prediction date in YYYY-MM-DD format")


class SalesDataTool(BaseTool):
    """Tool for fetching sales data."""
    name: str = "fetch_sales_data"
    description: str = "Fetches recent sales data for given product IDs"
    args_schema: Type[BaseModel] = SalesDataInput
    database_manager: Any = Field(description="Database manager instance")
    
    class Config:
        arbitrary_types_allowed = True
    
    def _run(self, product_ids: List[int], prediction_date: str) -> str:
        """Fetch sales data."""
        try:
            sales_data = self.database_manager.fetch_sales_data_for_products(product_ids, prediction_date)
            return json.dumps(sales_data)
        except Exception as e:
            logger.error(f"Error fetching sales data: {e}")
            return f"Error fetching sales data: {str(e)}"


class CSVGeneratorInput(BaseModel):
    results: List[Dict[str, Any]] = Field(description="Prediction results to save to CSV")
    task_id: str = Field(description="Task ID for file naming")


class CSVGeneratorTool(BaseTool):
    """Tool for generating CSV files."""
    name: str = "generate_csv"
    description: str = "Generates CSV file from prediction results"
    args_schema: Type[BaseModel] = CSVGeneratorInput
    
    def _run(self, results: List[Dict[str, Any]], task_id: str) -> str:
        """Generate CSV file."""
        try:
            # Create results directory
            results_dir = "./prediction_results"
            os.makedirs(results_dir, exist_ok=True)
            
            # Create filename
            filename = f"prediction_result_{task_id}.csv"
            filepath = os.path.join(results_dir, filename)
            
            # Write CSV file
            with open(filepath, 'w', newline='', encoding='utf-8') as file:
                if results:
                    fieldnames = [
                        "Product ID", "Product Name", "Current Stock",
                        "Average Daily Sales (Last 3 Days)", 
                        "Predicted Demand (Next 3 Days)", "Is Stock Sufficient"
                    ]
                    writer = csv.DictWriter(file, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for result in results:
                        writer.writerow({
                            "Product ID": result['product_id'],
                            "Product Name": result['product_name'],
                            "Current Stock": result['current_stock'],
                            "Average Daily Sales (Last 3 Days)": f"{result['avg_daily_sales_3_days']:.2f}",
                            "Predicted Demand (Next 3 Days)": result['predicted_demand_3_day'],
                            "Is Stock Sufficient": result['is_sufficient']
                        })
            
            return filepath
        except Exception as e:
            logger.error(f"Error generating CSV: {e}")
            return f"Error generating CSV: {str(e)}"


class GoogleDriveUploadInput(BaseModel):
    file_path: str = Field(description="Path to file to upload")
    filename: str = Field(description="Name for the uploaded file")


class GoogleDriveUploadTool(BaseTool):
    """Tool for uploading files to Google Drive."""
    name: str = "upload_to_drive"
    description: str = "Uploads file to Google Drive"
    args_schema: Type[BaseModel] = GoogleDriveUploadInput
    credentials_path: str = Field(description="Path to Google Drive credentials")
    folder_id: Optional[str] = Field(default=None, description="Google Drive folder ID")
    service: Any = Field(default=None, description="Google Drive service instance")
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self, credentials_path: str, folder_id: str = None, **kwargs):
        super().__init__(
            credentials_path=credentials_path, 
            folder_id=folder_id, 
            **kwargs
        )
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Drive service."""
        try:
            if os.path.exists(self.credentials_path):
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=['https://www.googleapis.com/auth/drive']
                )
                self.service = build('drive', 'v3', credentials=credentials)
                logger.info("Google Drive service initialized successfully")
            else:
                logger.warning("Google Drive credentials file not found")
        except Exception as e:
            logger.error(f"Error initializing Google Drive service: {e}")
    
    def _run(self, file_path: str, filename: str) -> str:
        """Upload file to Google Drive."""
        try:
            if not self.service:
                return "Google Drive service not available"
            
            # File metadata
            file_metadata = {
                'name': filename,
                'parents': [self.folder_id] if self.folder_id else []
            }
            
            # Upload file
            media = MediaFileUpload(file_path, resumable=True)
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            # Make file publicly readable
            permission = {
                'type': 'anyone',
                'role': 'reader'
            }
            self.service.permissions().create(
                fileId=file['id'],
                body=permission
            ).execute()
            
            drive_url = f"https://drive.google.com/file/d/{file['id']}/view"
            return drive_url
            
        except Exception as e:
            logger.error(f"Error uploading to Google Drive: {e}")
            return f"Error uploading to Google Drive: {str(e)}"


class CallbackNotificationInput(BaseModel):
    callback_url: str = Field(description="URL to send callback notification")
    payload: Dict[str, Any] = Field(description="Payload to send in callback")


class CallbackNotificationTool(BaseTool):
    """Tool for sending callback notifications."""
    name: str = "send_callback"
    description: str = "Sends callback notification to specified URL"
    args_schema: Type[BaseModel] = CallbackNotificationInput
    
    def _run(self, callback_url: str, payload: Dict[str, Any]) -> str:
        """Send callback notification."""
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    callback_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return f"Callback sent successfully. Response: {response.status_code}"
        except Exception as e:
            logger.error(f"Error sending callback: {e}")
            return f"Error sending callback: {str(e)}"