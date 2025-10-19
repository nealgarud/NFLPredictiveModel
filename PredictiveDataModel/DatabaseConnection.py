import psycopg2
import os
import logging
from typing import Optional

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class DatabaseConnection:
    """Singleton database connection manager"""
    
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
        """Create new database connection"""
        try:
            logger.info("Attempting to connect to database...")
            connection = psycopg2.connect(
                host=os.environ.get('DB_HOST'),
                database=os.environ.get('DB_NAME'),
                user=os.environ.get('DB_USER'),
                password=os.environ.get('DB_PASSWORD'),
                port=int(os.environ.get('DB_PORT', 5432)),
                connect_timeout=10
            )
            logger.info("✓ Database connection established")
            return connection
        except Exception as e:
            logger.error(f"✗ Database connection failed: {str(e)}")
            raise
    
    def get_connection(self):
        """Get database connection, reconnect if dead"""
        # Check if connection is still alive
        try:
            # Test the connection
            cursor = self._connection.cursor()
            cursor.execute('SELECT 1')
            cursor.close()
        except (psycopg2.InterfaceError, psycopg2.OperationalError, AttributeError):
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