"""
S3FileReader.py
Reads CSV files from S3 and parses them into Python dictionaries
"""

import boto3
import csv
import io
import logging
from typing import List, Dict, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class S3FileReader:
    """
    Reads CSV files from Amazon S3 and parses them
    Handles S3 connection, file retrieval, and CSV parsing
    """
    
    def __init__(self, bucket_name: str):
        """
        Initialize S3 client
        
        Args:
            bucket_name: Name of the S3 bucket (e.g., 'neal-nitya-qb-bucket')
        """
        self.bucket_name = bucket_name
        self.s3_client = boto3.client('s3')
        logger.info(f"S3FileReader initialized for bucket: {bucket_name}")
    
    def list_files_in_folder(self, prefix: str) -> List[str]:
        """
        List all files in an S3 folder
        
        Args:
            prefix: S3 folder path (e.g., 'QBs/')
        
        Returns:
            List of S3 object keys
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' not in response:
                logger.warning(f"No files found in s3://{self.bucket_name}/{prefix}")
                return []
            
            # Filter out folders (keys ending with '/')
            files = [
                obj['Key'] for obj in response['Contents']
                if not obj['Key'].endswith('/')
            ]
            
            logger.info(f"Found {len(files)} files in {prefix}")
            return files
        
        except Exception as e:
            logger.error(f"Failed to list files in S3: {e}")
            raise
    
    def read_csv_from_s3(self, s3_key: str) -> List[Dict[str, Any]]:
        """
        Read a CSV file from S3 and parse it into a list of dictionaries
        
        Args:
            s3_key: Full S3 object key (e.g., 'QBs/passing_summary.csv')
        
        Returns:
            List of dictionaries, one per CSV row
        """
        logger.info(f"Reading CSV from s3://{self.bucket_name}/{s3_key}")
        
        try:
            # Get object from S3
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            # Read and decode content
            content = response['Body'].read().decode('utf-8')
            
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(content))
            rows = list(csv_reader)
            
            logger.info(f"✓ Parsed {len(rows)} rows from CSV")
            logger.info(f"  CSV columns: {list(rows[0].keys()) if rows else 'N/A'}")
            
            return rows
        
        except Exception as e:
            logger.error(f"Failed to read CSV from S3: {e}")
            raise
    
    def read_all_csvs_in_folder(self, prefix: str) -> List[Dict[str, Any]]:
        """
        Read all CSV files in an S3 folder and combine them
        
        Args:
            prefix: S3 folder path
        
        Returns:
            Combined list of all rows from all CSVs
        """
        all_rows = []
        
        # Get list of CSV files
        files = self.list_files_in_folder(prefix)
        csv_files = [f for f in files if f.endswith('.csv')]
        
        logger.info(f"Found {len(csv_files)} CSV files to process")
        
        # Read each CSV
        for csv_file in csv_files:
            rows = self.read_csv_from_s3(csv_file)
            all_rows.extend(rows)
        
        logger.info(f"✓ Total rows loaded: {len(all_rows)}")
        return all_rows

