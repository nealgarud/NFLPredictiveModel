"""
lambda_function.py
AWS Lambda handler for processing Running Back (OLINE) PFF data from S3 to database.
Orchestrates the ETL pipeline: Read from S3 -> Transform -> Load to PostgreSQL.
"""

import json
import logging
import os
from S3FileReader import S3FileReader
from PFFDataProcessor import PFFDataProcessor
from DatabaseUtils import DatabaseUtils


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _normalize_seasons_to_process(event):
    """
    Parse and normalize season configuration from the Lambda event.
    Supports both single season and multiple seasons with custom S3 prefixes.
    
    Args:
        event: Lambda event dictionary containing season information
    
    Returns:
        List of dictionaries with 'season' and 's3_prefix' keys
    
    Raises:
        ValueError: If event doesn't contain required season information
    """
    # If seasons are already formatted, return them
    if 'seasons' in event and isinstance(event['seasons'], list):
        return event['seasons']
    
    # Otherwise parse from event
    if 'season' not in event:
        raise ValueError("Event must contain 'season' or 'seasons'")
    
    season_param = event['season']
    s3_prefix = event.get('s3_prefix', 'OLINEs/')
    s3_prefix_template = event.get('s3_prefix_template')
    
    # Handle multiple seasons
    if isinstance(season_param, (list, tuple)):
        seasons = [int(s) for s in season_param]
        if s3_prefix_template:
            return [{'season': s, 's3_prefix': s3_prefix_template.format(season=s)} for s in seasons]
        return [{'season': s, 's3_prefix': s3_prefix} for s in seasons]
    
    # Single season
    return [{'season': int(season_param), 's3_prefix': s3_prefix}]


def lambda_handler(event, context):
    """
    AWS Lambda handler for OLINE PFF data ingestion.
    
    Expected event format:
    {
        "bucket": "s3-bucket-name",
        "season": 2024,  // or ["season": [2023, 2024]] for multiple
        "s3_prefix": "OLINE/2024/",  // optional
        "s3_prefix_template": "OLINE/{season}/"  // optional, for multiple seasons
    }
    
    Args:
        event: Lambda event dictionary
        context: Lambda context object
    
    Returns:
        Response dictionary with statusCode and body
    """
    logger.info("=" * 60)
    logger.info("OLINE PFF Lambda Handler Started")
    logger.info("=" * 60)
    logger.info(f"Event: {json.dumps(event)}")

    try:
        # Parse configuration
        bucket = event.get('bucket') or os.environ.get('PLAYER_DATA_BUCKET', 'neal-nitya-oline-bucket')
        seasons_to_process = _normalize_seasons_to_process(event)

        logger.info("Initializing ETL components")
        s3_reader = S3FileReader(bucket_name=bucket)
        db_utils = DatabaseUtils()
        processor = PFFDataProcessor(db_utils=db_utils)

        # Process each season
        results = []
        total_rows = 0

        for season_config in seasons_to_process:
            season = season_config['season']
            s3_prefix = season_config['s3_prefix']
            
            logger.info(f"\n{'=' * 60}")
            logger.info(f"Processing Season {season}")
            logger.info(f"S3 Path: s3://{bucket}/{s3_prefix}")
            logger.info(f"{'=' * 60}\n")

            # Step 1: Read CSV files from S3
            logger.info("Step 1: Reading CSV files from S3")
            csv_rows = s3_reader.read_all_csvs_in_folder(s3_prefix)

            if not csv_rows:
                logger.warning(f"No data found for season {season}, skipping")
                results.append({
                    'season': season,
                    'rows_processed': 0,
                    'status': 'skipped',
                    'message': "No CSV files found in S3 bucket"
                })
                continue

            # Step 2: Process and store in database
            logger.info("Step 2: Processing and storing rows in database")
            rows_inserted = processor.process_and_store(csv_rows, season)

            total_rows += rows_inserted

            results.append({
                'season': season,
                'rows_processed': rows_inserted,
                'status': "success"
            })
            logger.info(f"✓ Season {season} complete: {rows_inserted} rows processed\n")
        
        # Close database connection
        db_utils.close()
        
        # Build success response
        logger.info(f"\n{'=' * 60}")
        logger.info(f"ETL COMPLETE")
        logger.info(f"Total rows processed: {total_rows}")
        logger.info(f"Seasons processed: {len(results)}")
        logger.info(f"{'=' * 60}\n")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'message': f'Successfully processed {total_rows} OLINE records across {len(results)} seasons',
                'total_rows': total_rows,
                'seasons_processed': len(results),
                'details': results
            })
        }
        
    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}", exc_info=True)
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': str(e),
                'message': 'OLINE PFF data ingestion failed'
            })
        }
