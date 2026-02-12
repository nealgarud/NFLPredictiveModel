import pg8000
import os
import logging

logger = logging.getLogger()

class DatabaseUtils:
    """
    Simple database utility class for Supabase/PostgreSQL operations.
    
    Usage:
        db = DatabaseUtils()
        db.execute_query("SELECT * FROM table WHERE id = %s", (123,))
        db.close()
    """
    
    def __init__(self):
        """
        Initialize database connection using environment variables.
        
        Required env vars:
            - DB_HOST
            - DB_NAME
            - DB_USER
            - DB_PASSWORD
            - DB_PORT (optional, defaults to 5432)
        """
        try:
            self.connection = pg8000.connect(
                host=os.environ.get('DB_HOST'),
                port=int(os.environ.get('DB_PORT', 5432)),
                database=os.environ.get('DB_NAME'),
                user=os.environ.get('DB_USER'),
                password=os.environ.get('DB_PASSWORD')
            )
            logger.info("Database connection established")
            
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise Exception(f"Database connection failed: {str(e)}")
    
    
    def execute_query(self, query, params=None):
        """
        Execute a single SQL query.
        
        Args:
            query (str): SQL query with %s placeholders
            params (tuple): Parameter values for placeholders
        
        Returns:
            cursor: Database cursor (for fetching results if SELECT)
        
        Example:
            db.execute_query(
                "INSERT INTO table (col1, col2) VALUES (%s, %s)",
                ('value1', 'value2')
            )
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params or ())
            self.connection.commit()
            return cursor
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            self.connection.rollback()
            raise
    
    
    def execute_batch(self, query, batch_data):
        """
        Execute a query with multiple parameter sets (batch insert).
        
        Args:
            query (str): SQL query with %s placeholders
            batch_data (list[tuple]): List of parameter tuples
        
        Returns:
            int: Number of rows affected
        
        Example:
            db.execute_batch(
                "INSERT INTO table (col1, col2) VALUES (%s, %s)",
                [('val1', 'val2'), ('val3', 'val4')]
            )
        """
        try:
            cursor = self.connection.cursor()
            cursor.executemany(query, batch_data)
            self.connection.commit()
            
            rows_affected = cursor.rowcount
            logger.info(f"Batch execution completed: {rows_affected} rows affected")
            return rows_affected
            
        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            self.connection.rollback()
            raise
    
    
    def close(self):
        """Close database connection."""
        try:
            self.connection.close()
            logger.info("Database connection closed")
        except Exception as e:
            logger.warning(f"Error closing database connection: {e}")