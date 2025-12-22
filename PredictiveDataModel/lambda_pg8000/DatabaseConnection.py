import pg8000.native
import os
import logging
from typing import Optional

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class DatabaseConnection:
    """Singleton database connection manager for Supabase PostgreSQL using pg8000"""
    
    _instance: Optional['DatabaseConnection'] = None
    _connection = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._connection is None:
            self._connection = self._create_connection()
    
    def _create_connection(self):
        """Create new Supabase database connection using pg8000"""
        try:
            logger.info("Attempting to connect to Supabase database...")
            
            # Supabase connection parameters
            # For Lambda, connection pooling (port 6543) is recommended
            connection = pg8000.native.Connection(
                host=os.environ.get('SUPABASE_DB_HOST'),  # e.g., db.xxxxxx.supabase.co
                database=os.environ.get('SUPABASE_DB_NAME', 'postgres'),  # Usually 'postgres'
                user=os.environ.get('SUPABASE_DB_USER', 'postgres'),  # Usually 'postgres'
                password=os.environ.get('SUPABASE_DB_PASSWORD'),  # Your database password
                port=int(os.environ.get('SUPABASE_DB_PORT', 5432)),  # 5432 direct or 6543 pooler
                timeout=10,
                ssl_context=True  # Supabase requires SSL
            )
            
            logger.info("✓ Supabase database connection established")
            return connection
        except Exception as e:
            logger.error(f"✗ Supabase database connection failed: {str(e)}")
            raise
    
    def get_connection(self):
        """Get database connection, reconnect if dead"""
        # Check if connection is still alive
        try:
            # Test the connection
            self._connection.run('SELECT 1')
        except Exception:
            # Reconnect if connection is dead
            logger.warning("Database connection lost, reconnecting...")
            self._connection = self._create_connection()
        
        return self._connection
    
    def close(self):
        """Close database connection"""
        if self._connection:
            try:
                self._connection.close()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database connection: {str(e)}")