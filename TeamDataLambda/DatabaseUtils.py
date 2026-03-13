"""
DatabaseUtils.py
Handles PostgreSQL database connections and basic query operations
"""

import os
import logging
import pg8000
from typing import Optional, List, Tuple, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class DatabaseUtils:
    """
    PostgreSQL database connection and query utilities
    Handles connection pooling, query execution, and error handling
    """
    
    def __init__(self):
        """Initialize database connection from environment variables"""
        # Support both naming conventions: DB_* and SUPABASE_DB_*
        self.host = os.environ.get('SUPABASE_DB_HOST') or os.environ.get('DB_HOST')
        self.port = int(os.environ.get('SUPABASE_DB_PORT') or os.environ.get('DB_PORT', 5432))
        self.database = os.environ.get('SUPABASE_DB_NAME') or os.environ.get('DB_NAME')
        self.user = os.environ.get('SUPABASE_DB_USER') or os.environ.get('DB_USER')
        self.password = os.environ.get('SUPABASE_DB_PASSWORD') or os.environ.get('DB_PASSWORD')
        
        # Validate environment variables
        if not all([self.host, self.database, self.user, self.password]):
            raise ValueError("Missing required database environment variables. Need either DB_HOST/DB_NAME/DB_USER/DB_PASSWORD or SUPABASE_DB_HOST/SUPABASE_DB_NAME/SUPABASE_DB_USER/SUPABASE_DB_PASSWORD")
        
        self.connection: Optional[pg8000.Connection] = None
        logger.info("DatabaseUtils initialized")
    
    def connect(self) -> pg8000.Connection:
        """
        Establish database connection
        
        Returns:
            pg8000.Connection: Active database connection
        """
        if self.connection is None:
            try:
                self.connection = pg8000.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                    ssl_context=True  # Required for Supabase
                )
                logger.info(f"✓ Connected to database: {self.database}")
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                raise
        
        return self.connection
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> pg8000.Cursor:
        """
        Execute a SQL query (SELECT, INSERT, UPDATE, DELETE)
        
        Args:
            query: SQL query string
            params: Optional tuple of parameters for parameterized queries
        
        Returns:
            pg8000.Cursor: Cursor with query results
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            return cursor
        
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            logger.error(f"Query: {query}")
            raise
    
    def execute_batch(self, query: str, data_batch: List[Tuple]) -> int:
        """
        Execute a batch of INSERT/UPDATE queries efficiently
        
        Args:
            query: Parameterized SQL query
            data_batch: List of tuples, each representing one row of data
        
        Returns:
            int: Number of rows affected
        """
        conn = self.connect()
        cursor = conn.cursor()
        rows_affected = 0
        
        try:
            for row_data in data_batch:
                cursor.execute(query, row_data)
                rows_affected += 1
            
            conn.commit()
            logger.info(f"✓ Batch executed: {rows_affected} rows affected")
            return rows_affected
        
        except Exception as e:
            conn.rollback()
            logger.error(f"Batch execution failed: {e}")
            raise
        finally:
            cursor.close()
    
    def commit(self):
        """Commit current transaction"""
        if self.connection:
            self.connection.commit()
            logger.info("Transaction committed")
    
    def rollback(self):
        """Rollback current transaction"""
        if self.connection:
            self.connection.rollback()
            logger.warning("Transaction rolled back")
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("Database connection closed")
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - auto-close connection"""
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()

