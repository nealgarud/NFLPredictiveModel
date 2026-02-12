"""
Database utilities for PlayerImpact Lambda
Handles connections and queries to Supabase PostgreSQL
"""

import pg8000
import os
import logging

logger = logging.getLogger()


class DatabaseUtils:
    """
    Database utility class for Supabase/PostgreSQL operations.
    
    This class manages database connections and provides methods for
    executing queries and batch operations.
    
    Usage:
        db = DatabaseUtils()
        try:
            results = db.execute_query("SELECT * FROM table WHERE id = %s", (123,))
            rows = results.fetchall()
        finally:
            db.close()
    """
    
    def __init__(self):
        """
        Initialize database connection using environment variables.
        
        Required environment variables:
            - DB_HOST: Database host (e.g., aws-1-us-east-2.pooler.supabase.com)
            - DB_NAME: Database name (usually 'postgres')
            - DB_USER: Database user (e.g., postgres.xxx)
            - DB_PASSWORD: Database password
            - DB_PORT: Database port (optional, defaults to 5432)
        
        Raises:
            Exception: If connection fails or required env vars are missing
        """
        try:
            # Get connection parameters from environment
            host = os.environ.get('DB_HOST')
            port = int(os.environ.get('DB_PORT', 5432))
            database = os.environ.get('DB_NAME')
            user = os.environ.get('DB_USER')
            password = os.environ.get('DB_PASSWORD')
            
            # Validate required parameters
            if not all([host, database, user, password]):
                missing = []
                if not host: missing.append('DB_HOST')
                if not database: missing.append('DB_NAME')
                if not user: missing.append('DB_USER')
                if not password: missing.append('DB_PASSWORD')
                raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
            
            # Create connection
            self.connection = pg8000.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                timeout=30
            )
            
            logger.info(f"Database connection established to {host}")
            
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise Exception(f"Database connection failed: {str(e)}")
    
    
    def execute_query(self, query, params=None):
        """
        Execute a single SQL query.
        
        This method is used for SELECT, INSERT, UPDATE, or DELETE operations.
        For batch inserts, use execute_batch() instead.
        
        Args:
            query (str): SQL query with %s placeholders for parameters
            params (tuple, optional): Parameter values for placeholders
        
        Returns:
            cursor: Database cursor object
                - Use cursor.fetchall() to get SELECT results
                - Use cursor.fetchone() to get single row
                - Use cursor.rowcount to get affected rows
        
        Example:
            # SELECT query
            cursor = db.execute_query(
                "SELECT * FROM games WHERE season = %s AND week = %s",
                (2024, 1)
            )
            rows = cursor.fetchall()
            
            # INSERT query
            db.execute_query(
                "INSERT INTO table (col1, col2) VALUES (%s, %s)",
                ('value1', 'value2')
            )
        
        Raises:
            Exception: If query execution fails
        """
        try:
            cursor = self.connection.cursor()
            
            # Execute with or without parameters
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Commit transaction (for INSERT/UPDATE/DELETE)
            self.connection.commit()
            
            return cursor
            
        except Exception as e:
            # Rollback on error to keep database in consistent state
            logger.error(f"Query execution failed: {e}")
            self.connection.rollback()
            raise
    
    
    def execute_batch(self, query, batch_data):
        """
        Execute a query with multiple parameter sets (batch operation).
        
        This is more efficient than calling execute_query() in a loop
        because it sends all data to the database in one operation.
        
        Args:
            query (str): SQL query with %s placeholders
            batch_data (list[tuple]): List of parameter tuples
        
        Returns:
            int: Number of rows affected
        
        Example:
            # Batch insert multiple rows
            query = "INSERT INTO table (col1, col2) VALUES (%s, %s)"
            data = [
                ('value1', 'value2'),
                ('value3', 'value4'),
                ('value5', 'value6')
            ]
            rows_affected = db.execute_batch(query, data)
            # Inserts 3 rows in one operation
        
        Raises:
            Exception: If batch execution fails
        """
        try:
            cursor = self.connection.cursor()
            
            # executemany() runs the query once for each tuple in batch_data
            cursor.executemany(query, batch_data)
            
            # Commit transaction
            self.connection.commit()
            
            # Get number of rows affected
            rows_affected = cursor.rowcount
            logger.info(f"Batch execution completed: {rows_affected} rows affected")
            
            return rows_affected
            
        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            self.connection.rollback()
            raise
    
    
    def close(self):
        """
        Close database connection.
        
        Always call this when done to free up database resources.
        Use try/finally or context managers to ensure it's called.
        
        Example:
            db = DatabaseUtils()
            try:
                # Do database operations
                pass
            finally:
                db.close()  # Always runs, even if error occurs
        """
        try:
            if self.connection:
                self.connection.close()
                logger.info("Database connection closed")
        except Exception as e:
            logger.warning(f"Error closing database connection: {e}")
    
    
    def __enter__(self):
        """
        Context manager entry (enables 'with' statement).
        
        Example:
            with DatabaseUtils() as db:
                results = db.execute_query("SELECT * FROM table")
            # Connection automatically closed after 'with' block
        """
        return self
    
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit (automatically closes connection).
        """
        self.close()

