"""
Test S3 Access from Lambda
Use this to debug S3 data loading issues
"""

import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """Test S3 access and list available files"""
    
    try:
        s3_client = boto3.client('s3')
        bucket = 'sportsdatacollection'
        
        results = {
            'bucket': bucket,
            'madden_files': [],
            'raw_data_files': [],
            'errors': []
        }
        
        # List Madden files
        logger.info(f"Checking Madden files in s3://{bucket}/madden-ratings/")
        try:
            response = s3_client.list_objects_v2(Bucket=bucket, Prefix='madden-ratings/')
            if 'Contents' in response:
                results['madden_files'] = [obj['Key'] for obj in response['Contents']]
                logger.info(f"Found {len(results['madden_files'])} Madden files")
            else:
                logger.warning("No Madden files found")
        except Exception as e:
            error_msg = f"Error listing Madden files: {str(e)}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
        
        # List raw data files
        logger.info(f"Checking game data in s3://{bucket}/raw-data/")
        try:
            response = s3_client.list_objects_v2(Bucket=bucket, Prefix='raw-data/')
            if 'Contents' in response:
                results['raw_data_files'] = [obj['Key'] for obj in response['Contents']]
                logger.info(f"Found {len(results['raw_data_files'])} game data files")
            else:
                logger.warning("No game data files found")
        except Exception as e:
            error_msg = f"Error listing game data files: {str(e)}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
        
        # Try reading a sample file
        if results['madden_files']:
            sample_file = results['madden_files'][0]
            logger.info(f"Attempting to read sample file: {sample_file}")
            try:
                response = s3_client.get_object(Bucket=bucket, Key=sample_file)
                content = response['Body'].read().decode('utf-8')
                first_lines = '\n'.join(content.split('\n')[:3])
                results['sample_file'] = sample_file
                results['sample_content'] = first_lines
                logger.info(f"Successfully read {len(content)} bytes from {sample_file}")
            except Exception as e:
                error_msg = f"Error reading sample file: {str(e)}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
        
        return {
            'statusCode': 200,
            'body': json.dumps(results, indent=2)
        }
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

