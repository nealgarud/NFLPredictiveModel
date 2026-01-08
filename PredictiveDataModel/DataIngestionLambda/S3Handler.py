import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class S3Handler:
    """Handle S3 file operations"""
    
    def __init__(self):
        self.s3_client = boto3.client('s3')
        logger.info("S3Handler initialized")
    
    def read_text_file(self, bucket: str, key: str) -> str:
        """
        Read text file from S3
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            
        Returns:
            Text content as string
        """
        try:
            logger.info(f"Reading file from S3: s3://{bucket}/{key}")
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read().decode('utf-8')
            logger.info(f"Successfully read {len(content)} characters from S3")
            return content
        except Exception as e:
            logger.error(f"Error reading file from S3: {str(e)}")
            raise
    
    def write_text_file(self, bucket: str, key: str, content: str):
        """Write text file to S3"""
        try:
            logger.info(f"Writing file to S3: s3://{bucket}/{key}")
            self.s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=content.encode('utf-8')
            )
            logger.info(f"Successfully wrote file to S3")
        except Exception as e:
            logger.error(f"Error writing file to S3: {str(e)}")
            raise
    
    def file_exists(self, bucket: str, key: str) -> bool:
        """Check if file exists in S3"""
        try:
            self.s3_client.head_object(Bucket=bucket, Key=key)
            logger.info(f"File exists in S3: s3://{bucket}/{key}")
            return True
        except Exception as e:
            logger.info(f"File does not exist in S3: s3://{bucket}/{key}")
            return False