"""
Database connection and utilities for the AI agents system.

This module provides database connection management and common database operations
that are used by both stock update and prediction agents.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from contextlib import asynccontextmanager
import asyncpg
from agents.config.settings import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and operations for AI agents."""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self) -> None:
        """Initialize the database connection pool."""
        try:
            self.pool = await asyncpg.create_pool(
                settings.database.url,
                min_size=1,
                max_size=20,
                command_timeout=60
            )
            logger.info("Database connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database connection pool: {e}")
            raise
    
    async def close(self) -> None:
        """Close the database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get a database connection from the pool."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as connection:
            yield connection
    
    async def fetch_products_batch(self, offset: int, batch_size: int) -> List[Dict[str, Any]]:
        """
        Fetch a batch of products from the database.
        
        Args:
            offset: Starting offset for the batch
            batch_size: Number of products to fetch
            
        Returns:
            List of product dictionaries with index, name, and current_stock
        """
        query = """
            SELECT "index", "name", stock as current_stock
            FROM public.amazon_dataset
            ORDER BY "index"
            LIMIT $1 OFFSET $2
        """
        
        async with self.get_connection() as conn:
            rows = await conn.fetch(query, batch_size, offset)
            return [dict(row) for row in rows]
    
    async def fetch_sales_data_for_products(
        self, 
        product_ids: List[int], 
        prediction_date: str
    ) -> Dict[int, List[int]]:
        """
        Fetch recent sales data for a given list of product IDs.
        
        Args:
            product_ids: List of product IDs to fetch sales for
            prediction_date: The prediction date to calculate the 3-day window from
            
        Returns:
            Dictionary mapping product_id to list of quantity_sold values
        """
        query = """
            SELECT "index", "quantity_sold"
            FROM public.daily_sales
            WHERE "index" = ANY($1) 
              AND "date" >= (CAST($2 AS DATE) - interval '3 days')
              AND "date" < CAST($2 AS DATE)
        """
        
        async with self.get_connection() as conn:
            rows = await conn.fetch(query, product_ids, prediction_date)
            
            # Pre-populate with empty lists for products with no sales
            sales_by_product = {pid: [] for pid in product_ids}
            
            for row in rows:
                product_id = row['index']
                quantity_sold = row['quantity_sold']
                sales_by_product[product_id].append(quantity_sold)
            
            return sales_by_product
    
    async def update_stock_batch(self, sales_data: List[Dict[str, Any]]) -> int:
        """
        Update stock levels based on sales data using a batch transaction.
        
        Args:
            sales_data: List of dictionaries with 'index' and 'quantity_sold' keys
            
        Returns:
            Number of rows affected
        """
        async with self.get_connection() as conn:
            async with conn.transaction():
                # Create temporary table
                await conn.execute("""
                    CREATE TEMP TABLE sales_update (
                        product_index INT NOT NULL,
                        quantity_sold INT NOT NULL
                    ) ON COMMIT DROP;
                """)
                
                # Insert sales data into temp table
                values = [(sale['index'], sale['quantity_sold']) for sale in sales_data]
                await conn.executemany(
                    "INSERT INTO sales_update (product_index, quantity_sold) VALUES ($1, $2)",
                    values
                )
                
                # Update stock levels
                result = await conn.execute("""
                    UPDATE public.amazon_dataset AS ad
                    SET stock = ad.stock - su.quantity_sold
                    FROM sales_update AS su
                    WHERE ad.index = su.product_index;
                """)
                
                # Extract number of affected rows
                rows_affected = int(result.split()[-1])
                logger.info(f"Successfully updated stock for {rows_affected} products")
                
                return rows_affected
    
    async def health_check(self) -> bool:
        """
        Check if the database connection is healthy.
        
        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            async with self.get_connection() as conn:
                await conn.fetchval("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Global database manager instance
db_manager = DatabaseManager()