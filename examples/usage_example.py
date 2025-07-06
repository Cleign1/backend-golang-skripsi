"""
Example usage of the AI Agents Stock Management System.

This script demonstrates how to interact with the AI agents
for stock updates and predictions.
"""

import asyncio
import json
import aiohttp
from datetime import datetime
from typing import List, Dict, Any


class StockManagementClient:
    """Client for interacting with the AI Agents Stock Management System."""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check the health of the AI agents system."""
        async with self.session.get(f"{self.base_url}/health") as response:
            return await response.json()
    
    async def update_stock(self, sales_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update stock levels using the Stock Update Agent."""
        payload = {"sales": sales_data}
        
        async with self.session.post(
            f"{self.base_url}/agents/update-stock",
            json=payload
        ) as response:
            return await response.json()
    
    async def predict_stock(self, prediction_date: str, task_id: str) -> Dict[str, Any]:
        """Start a stock prediction task using the Stock Prediction Agent."""
        payload = {
            "prediction_date": prediction_date,
            "task_id": task_id
        }
        
        async with self.session.post(
            f"{self.base_url}/agents/predict-stock",
            json=payload
        ) as response:
            return await response.json()
    
    async def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """Get the result of a specific task."""
        async with self.session.get(f"{self.base_url}/tasks/{task_id}") as response:
            return await response.json()
    
    async def get_agents_status(self) -> Dict[str, Any]:
        """Get the status of all agents."""
        async with self.session.get(f"{self.base_url}/agents/status") as response:
            return await response.json()


async def example_stock_update():
    """Example of using the Stock Update Agent."""
    print("=== Stock Update Agent Example ===")
    
    async with StockManagementClient() as client:
        # Check if the service is healthy
        health = await client.health_check()
        print(f"Service health: {health['orchestrator']['status']}")
        
        # Example sales data
        sales_data = [
            {"index": 1, "quantity_sold": 5},
            {"index": 2, "quantity_sold": 3},
            {"index": 3, "quantity_sold": 8},
            {"index": 4, "quantity_sold": 2}
        ]
        
        print(f"\nUpdating stock for {len(sales_data)} products...")
        
        # Update stock using the AI agent
        result = await client.update_stock(sales_data)
        
        print(f"Update result: {result['status']}")
        print(f"Message: {result['message']}")
        if result.get('rows_affected'):
            print(f"Rows affected: {result['rows_affected']}")


async def example_stock_prediction():
    """Example of using the Stock Prediction Agent."""
    print("\n=== Stock Prediction Agent Example ===")
    
    async with StockManagementClient() as client:
        # Generate a unique task ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        task_id = f"prediction_example_{timestamp}"
        prediction_date = "2024-01-15"
        
        print(f"Starting prediction task: {task_id}")
        print(f"Prediction date: {prediction_date}")
        
        # Start prediction task
        result = await client.predict_stock(prediction_date, task_id)
        
        print(f"Task status: {result['status']}")
        print(f"Message: {result['message']}")
        
        # Wait a moment and check task status
        print("\nWaiting for task to process...")
        await asyncio.sleep(5)
        
        try:
            task_result = await client.get_task_result(task_id)
            print(f"Task result status: {task_result['status']}")
            if task_result.get('result'):
                print(f"Task details: {json.dumps(task_result['result'], indent=2)}")
        except Exception as e:
            print(f"Task still processing or not found: {e}")


async def example_monitoring():
    """Example of monitoring agents and tasks."""
    print("\n=== Monitoring Example ===")
    
    async with StockManagementClient() as client:
        # Get agents status
        agents_status = await client.get_agents_status()
        
        print("Agents Status:")
        for agent_name, status in agents_status.items():
            print(f"  {agent_name}:")
            print(f"    Status: {status['status']}")
            print(f"    Tasks processed: {status['tasks_processed']}")
            print(f"    Errors: {status['errors_count']}")
            if status.get('last_activity'):
                print(f"    Last activity: {status['last_activity']}")


async def example_error_handling():
    """Example of error handling with invalid data."""
    print("\n=== Error Handling Example ===")
    
    async with StockManagementClient() as client:
        # Try to update stock with invalid data
        invalid_sales_data = [
            {"index": 0, "quantity_sold": 5},  # Invalid index
            {"index": 2, "quantity_sold": -3},  # Invalid quantity
            {"index": "invalid", "quantity_sold": 3}  # Invalid type
        ]
        
        print("Testing with invalid sales data...")
        
        try:
            result = await client.update_stock(invalid_sales_data)
            print(f"Result: {result['status']}")
            print(f"Message: {result['message']}")
            
            # The AI agent should handle this gracefully with validation
            if result['status'] == 'validation_failed':
                print("✓ AI agent correctly identified and handled invalid data")
            
        except Exception as e:
            print(f"Error: {e}")


async def comprehensive_example():
    """Run a comprehensive example demonstrating all features."""
    print("🤖 AI Agents Stock Management System - Comprehensive Example")
    print("=" * 60)
    
    try:
        # 1. Stock Update Example
        await example_stock_update()
        
        # 2. Stock Prediction Example
        await example_stock_prediction()
        
        # 3. Monitoring Example
        await example_monitoring()
        
        # 4. Error Handling Example
        await example_error_handling()
        
        print("\n✅ All examples completed successfully!")
        print("\nThe AI agents demonstrated:")
        print("  • Intelligent stock updating with validation")
        print("  • Asynchronous stock prediction with forecasting")
        print("  • Comprehensive monitoring and status tracking")
        print("  • Robust error handling and validation")
        
    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        print("\nMake sure the AI agents server is running:")
        print("  python main_agents.py")


if __name__ == "__main__":
    # Run the comprehensive example
    asyncio.run(comprehensive_example())