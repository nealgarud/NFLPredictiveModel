"""
QB PFF Lambda Handler
Orchestrates the ETL process: Extract from S3 -> Transform -> Load to Database
"""

import json
import logging
import os
from S3FileReader import S3FileReader
from PFFDataProcessor import PFFDataProcessor
from DatabaseUtils import DatabaseUtils

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _normalize_seasons_to_process(event):
    """
    Normalize event to list of {season, s3_prefix} configs.
    Supports: season (int), season (list), or seasons (list of configs).
    """
    if 'seasons' in event:
        return event['seasons']
    if 'season' not in event:
        raise ValueError("Event must contain 'season' or 'seasons'")
    season_param = event['season']
    s3_prefix = event.get('s3_prefix', 'QBs/')
    s3_prefix_template = event.get('s3_prefix_template')
    if isinstance(season_param, (list, tuple)):
        seasons = [int(s) for s in season_param]
        if s3_prefix_template:
            return [{'season': s, 's3_prefix': s3_prefix_template.format(season=s)} for s in seasons]
        return [{'season': s, 's3_prefix': s3_prefix} for s in seasons]
    return [{'season': int(season_param), 's3_prefix': s3_prefix}]


def lambda_handler(event, context):
    """
    AWS Lambda handler for QB PFF data ingestion
    
    Event format - single season:
    {
        "bucket": "neal-nitya-qb-bucket",
        "season": 2024,
        "s3_prefix": "QBs/"
    }
    
    Event format - multiple seasons (same prefix for all):
    {
        "bucket": "neal-nitya-qb-bucket",
        "season": [2022, 2023, 2024],
        "s3_prefix": "QBs/"
    }
    
    Event format - multiple seasons (per-season S3 path):
    {
        "bucket": "neal-nitya-qb-bucket",
        "season": [2022, 2023, 2024],
        "s3_prefix_template": "QBs/QBs-{season}/"
    }
    
    OR legacy format:
    {
        "bucket": "neal-nitya-qb-bucket",
        "seasons": [
            {"season": 2022, "s3_prefix": "QBs/QBs-2022/"},
            {"season": 2023, "s3_prefix": "QBs/QBs-2023/"},
            {"season": 2024, "s3_prefix": "QBs/QBs-2024/"}
        ]
    }
    
    Returns:
    {
        "statusCode": 200,
        "body": {
            "success": true,
            "message": "Processed X rows across Y seasons",
            "details": [...]
        }
    }
    """
    
    logger.info("QB PFF Lambda triggered")
    logger.info(f"Event: {json.dumps(event)}")
    
    try:
        # Extract parameters
        bucket = event.get('bucket') or os.environ.get('PLAYER_DATA_BUCKET', 'neal-nitya-qb-bucket')
        seasons_to_process = _normalize_seasons_to_process(event)
        
        # Initialize components
        logger.info("Initializing ETL components...")
        s3_reader = S3FileReader(bucket_name=bucket)
        db_utils = DatabaseUtils()
        processor = PFFDataProcessor(db_utils=db_utils, batch_size=50)
        
        # Process each season
        results = []
        total_rows = 0
        
        for season_config in seasons_to_process:
            season = season_config['season']
            s3_prefix = season_config['s3_prefix']
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing Season {season}")
            logger.info(f"S3 Path: s3://{bucket}/{s3_prefix}")
            logger.info(f"{'='*60}\n")
            
            # Step 1: Read CSV files from S3
            logger.info("STEP 1: Reading CSV files from S3...")
            csv_rows = s3_reader.read_all_csvs_in_folder(s3_prefix)
            
            if not csv_rows:
                logger.warning(f"No data found for season {season}, skipping")
                results.append({
                    'season': season,
                    'rows_processed': 0,
                    'status': 'skipped',
                    'message': 'No CSV files found'
                })
                continue
            
            # Step 2: Process and store in database
            logger.info("STEP 2: Processing and storing data...")
            rows_inserted = processor.process_and_store(csv_rows, season)
            
            total_rows += rows_inserted
            
            results.append({
                'season': season,
                'rows_processed': rows_inserted,
                'status': 'success'
            })
            
            logger.info(f"✓ Season {season} complete: {rows_inserted} rows processed\n")
        
        # Close database connection
        db_utils.close()
        
        # Build success response
        logger.info(f"\n{'='*60}")
        logger.info(f"ETL COMPLETE")
        logger.info(f"Total rows processed: {total_rows}")
        logger.info(f"Seasons processed: {len(results)}")
        logger.info(f"{'='*60}\n")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'message': f'Successfully processed {total_rows} QB records across {len(results)} seasons',
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
                'message': 'QB PFF data ingestion failed'
            })
        }


# For local testing
if __name__ == '__main__':
    # Single season
    test_event = {"bucket": "neal-nitya-qb-bucket", "season": 2024, "s3_prefix": "QBs/"}
    # Or multiple seasons: test_event = {"season": [2022, 2023, 2024], "s3_prefix_template": "QBs/QBs-{season}/"}
    
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))

