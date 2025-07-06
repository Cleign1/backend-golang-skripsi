import psycopg2
import psycopg2.extras
from typing import List, Dict, Any, Optional
import os
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, database_url: str):
        self.database_url = database_url
        
    @contextmanager
    def get_connection(self):
        """Get a database connection with proper cleanup."""
        conn = None
        try:
            conn = psycopg2.connect(self.database_url)
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def update_stock(self, sales_data: List[Dict[str, Any]]) -> int:
        """Update stock based on sales data."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                # Create temporary table
                cursor.execute("""
                    CREATE TEMP TABLE sales_update (
                        product_index INT NOT NULL,
                        quantity_sold INT NOT NULL
                    ) ON COMMIT DROP;
                """)
                
                # Insert sales data into temp table
                insert_query = "INSERT INTO sales_update (product_index, quantity_sold) VALUES %s"
                data_tuples = [(sale['index'], sale['quantity_sold']) for sale in sales_data]
                psycopg2.extras.execute_values(cursor, insert_query, data_tuples)
                
                # Update main table
                update_query = """
                    UPDATE public.amazon_dataset AS ad
                    SET stock = ad.stock - su.quantity_sold
                    FROM sales_update AS su
                    WHERE ad.index = su.product_index;
                """
                cursor.execute(update_query)
                rows_affected = cursor.rowcount
                
                conn.commit()
                return rows_affected
    
    def fetch_product_batch(self, offset: int, batch_size: int) -> List[Dict[str, Any]]:
        """Fetch a batch of products from the database."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                query = '''
                    SELECT "index", "name", "stock" 
                    FROM public.amazon_dataset 
                    ORDER BY "index" 
                    LIMIT %s OFFSET %s;
                '''
                cursor.execute(query, (batch_size, offset))
                return [dict(row) for row in cursor.fetchall()]
    
    def fetch_sales_data_for_products(self, product_ids: List[int], prediction_date: str) -> Dict[int, List[int]]:
        """Fetch recent sales data for given product IDs."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                query = """
                    SELECT "index", "quantity_sold"
                    FROM public.daily_sales
                    WHERE "index" = ANY(%s) 
                      AND "date" >= (CAST(%s AS DATE) - interval '3 days')
                      AND "date" < CAST(%s AS DATE);
                """
                cursor.execute(query, (product_ids, prediction_date, prediction_date))
                
                sales_by_product = {product_id: [] for product_id in product_ids}
                for product_id, quantity_sold in cursor.fetchall():
                    sales_by_product[product_id].append(quantity_sold)
                
                return sales_by_product
    
    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False