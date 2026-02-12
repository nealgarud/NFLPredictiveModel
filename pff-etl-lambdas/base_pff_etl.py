"""
Base PFF ETL Lambda - Common utilities for loading PFF data from S3 to Supabase
S3 Structure: s3://your-bucket/pff-grades/[PositionGroup]/[PositionGroup]_[Year].csv
"""

import json
import logging
import os
import io
import csv
import boto3
import pg8000
from typing import Dict, List, Any, Optional
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global connections (for Lambda warm starts)
_s3_client = None
_db_conn = None


def get_s3_client():
    """Get or create S3 client (cached for warm starts)"""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client('s3')
        logger.info("✓ S3 client initialized")
    return _s3_client


def get_db_connection():
    """Get or create database connection (cached for warm starts)"""
    global _db_conn
    
    if _db_conn is None or _db_conn.in_transaction:
        # Get connection parameters from environment
        db_host = os.environ.get('DB_HOST')
        db_port = int(os.environ.get('DB_PORT', 5432))
        db_name = os.environ.get('DB_NAME')
        db_user = os.environ.get('DB_USER')
        db_password = os.environ.get('DB_PASSWORD')
        
        if not all([db_host, db_name, db_user, db_password]):
            raise ValueError("Missing required database environment variables")
        
        _db_conn = pg8000.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password,
            ssl_context=True
        )
        logger.info(f"✓ Database connection established to {db_host}")
    
    return _db_conn


def fetch_csv_from_s3(bucket: str, key: str) -> List[Dict[str, Any]]:
    """
    Fetch CSV file from S3 and parse into list of dictionaries
    
    Args:
        bucket: S3 bucket name
        key: S3 object key (e.g., 'pff-grades/WR/WR_2024.csv')
    
    Returns:
        List of dictionaries, one per CSV row
    """
    s3 = get_s3_client()
    
    logger.info(f"Fetching s3://{bucket}/{key}")
    
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read().decode('utf-8')
        
        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(content))
        rows = list(csv_reader)
        
        logger.info(f"✓ Loaded {len(rows)} rows from CSV")
        return rows
    
    except Exception as e:
        logger.error(f"Failed to fetch CSV from S3: {e}")
        raise


def clean_value(value: Any, data_type: str = 'str') -> Any:
    """
    Clean and convert CSV value to appropriate database type
    
    Args:
        value: Raw CSV value (string)
        data_type: Target type ('str', 'int', 'decimal', 'bool')
    
    Returns:
        Cleaned value or None
    """
    if value is None or value == '' or value == 'None':
        return None
    
    try:
        if data_type == 'int':
            return int(float(value))  # Handle "1.0" -> 1
        elif data_type == 'decimal':
            return Decimal(str(value))
        elif data_type == 'bool':
            return value.lower() in ['true', '1', 'yes']
        else:
            return str(value).strip()
    except (ValueError, TypeError):
        return None


def normalize_team_name(team: str) -> str:
    """
    Normalize team abbreviations to match Sportradar format
    
    Examples:
        'MIN' -> 'MIN'
        'LAC' -> 'LAC'
        'LA' -> 'LAR' (Rams)
    """
    if not team:
        return 'UNK'
    
    team = team.strip().upper()
    
    # Handle LA teams
    team_mapping = {
        'LA': 'LAR',  # Rams by default
        'LAR': 'LAR',
        'LAC': 'LAC',
        'LV': 'LV',
        'NO': 'NO',
        'SF': 'SF',
        'TB': 'TB',
        'NE': 'NE',
        'GB': 'GB',
        'KC': 'KC'
    }
    
    return team_mapping.get(team, team)


def upsert_to_database(
    table_name: str,
    data: List[Dict[str, Any]],
    unique_keys: List[str]
) -> int:
    """
    Upsert data into database table (INSERT ... ON CONFLICT UPDATE)
    
    Args:
        table_name: Target table name
        data: List of dictionaries to insert
        unique_keys: Columns that uniquely identify a row (for conflict resolution)
    
    Returns:
        Number of rows inserted/updated
    """
    if not data:
        logger.warning("No data to upsert")
        return 0
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get column names from first row
    columns = list(data[0].keys())
    
    # Build INSERT query
    placeholders = ', '.join(['%s'] * len(columns))
    columns_str = ', '.join(columns)
    
    # Build UPDATE clause for ON CONFLICT
    update_clauses = [f"{col} = EXCLUDED.{col}" for col in columns if col not in unique_keys and col != 'id']
    update_str = ', '.join(update_clauses)
    
    # Build conflict target (unique keys)
    conflict_target = ', '.join(unique_keys)
    
    query = f"""
        INSERT INTO {table_name} ({columns_str})
        VALUES ({placeholders})
        ON CONFLICT ({conflict_target})
        DO UPDATE SET {update_str}
    """
    
    # Execute batch insert
    rows_affected = 0
    try:
        for row in data:
            values = [row[col] for col in columns]
            cursor.execute(query, values)
            rows_affected += 1
        
        conn.commit()
        logger.info(f"✓ Upserted {rows_affected} rows into {table_name}")
        return rows_affected
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to upsert data: {e}")
        raise
    finally:
        cursor.close()


def lambda_response(success: bool, message: str, data: Optional[Dict] = None) -> Dict:
    """
    Standard Lambda response format
    """
    return {
        'statusCode': 200 if success else 500,
        'body': json.dumps({
            'success': success,
            'message': message,
            'data': data or {}
        })
    }

