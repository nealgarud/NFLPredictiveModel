"""
S3FileReader.py
Reads CSV files from AWS S3 buckets and parses them into Python dictionaries.
Handles folder-level operations and batch file reading.
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
    Handles reading and parsing CSV files from AWS S3.
    Supports both individual file reading and batch folder operations.
    """
    
    def __init__(self, bucket_name: str):
        """
        Initialize S3 file reader with a specific bucket.
        
        Args:
            bucket_name: Name of the S3 bucket to read from
        """
        self.bucket_name = bucket_name
        self.s3_client = boto3.client('s3')
        logger.info(f"S3FileReader initialized for bucket: {bucket_name}")
    
    def list_files_in_folder(self, prefix: str) -> List[str]:
        """
        List all files in an S3 folder (prefix).
        
        Args:
            prefix: S3 prefix/folder path (e.g., 'OLINE/2024/')
        
        Returns:
            List of S3 keys (file paths) in the folder
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' not in response:
                logger.warning(f"No files found in s3://{self.bucket_name}/{prefix}")
                return []
            
            # Filter out directories (keys ending with '/')
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
        Read and parse a single CSV file from S3.
        
        Args:
            s3_key: Full S3 key/path to the CSV file
        
        Returns:
            List of dictionaries, each representing a row from the CSV
        """
        logger.info(f"Reading CSV from s3://{self.bucket_name}/{s3_key}")

        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            content = response['Body'].read().decode('utf-8')

            # Parse CSV content
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
        Read and combine all CSV files from an S3 folder.
        
        Args:
            prefix: S3 prefix/folder path to read from
        
        Returns:
            Combined list of all rows from all CSV files in the folder
        """
        all_rows = []
        
        # Get list of files in folder
        files = self.list_files_in_folder(prefix)
        csv_files = [f for f in files if f.endswith('.csv')]
        logger.info(f"Found {len(csv_files)} CSV files to process")

        # Read each CSV file and combine results
        for csv_file in csv_files:
            rows = self.read_csv_from_s3(csv_file)
            all_rows.extend(rows)
        
        logger.info(f"✓ Total rows loaded: {len(all_rows)}")
        return all_rows
