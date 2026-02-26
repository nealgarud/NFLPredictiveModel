"""
TeamFeatures Lambda
Computes all team-level features from the games table and stores them
in the team_season_features table in Supabase (one row per team per season).

Event Formats:
    1. Process specific seasons:
       {"seasons": [2023, 2024, 2025]}

    2. Process single season:
       {"seasons": [2024]}

    3. Default (all available seasons):
       {}
"""

import json
import logging
from FeatureCalculator import FeatureCalculator
from DatabaseUtils import DatabaseUtils

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DEFAULT_SEASONS = [2022, 2023, 2024]


def lambda_handler(event, context):
    logger.info("=" * 60)
    logger.info("TeamFeatures Lambda Started")
    logger.info("=" * 60)
    logger.info(f"Event: {json.dumps(event)}")

    seasons = event.get('seasons', DEFAULT_SEASONS)

    try:
        db = DatabaseUtils()
        db.ensure_table()

        raw_rows = db.fetch_games(seasons)
        if not raw_rows:
            logger.info("No games found for the requested seasons")
            return _response(200, {
                'success': True, 'rows_written': 0,
                'message': 'No games found'
            })

        calculator = FeatureCalculator()
        feature_rows = calculator.compute_all(raw_rows, seasons)

        logger.info(f"Upserting {len(feature_rows)} rows into team_season_features...")
        written = 0
        errors = 0
        for i, row in enumerate(feature_rows, 1):
            try:
                db.upsert_team_season(row)
                written += 1
                if written % 50 == 0:
                    logger.info(f"  Progress: {written}/{len(feature_rows)} rows written")
            except Exception as e:
                errors += 1
                logger.error(f"Failed to upsert {row['team_id']} S{row['season']}: {e}")
        
        logger.info(f"Upsert complete: {written} written, {errors} errors")

        db.commit()
        db.close()

        logger.info("=" * 60)
        logger.info(f"Done: {written}/{len(feature_rows)} rows written")
        logger.info("=" * 60)

        return _response(200, {
            'success': True,
            'seasons': seasons,
            'rows_computed': len(feature_rows),
            'rows_written': written
        })

    except Exception as e:
        logger.error(f"Lambda failed: {e}", exc_info=True)
        return _response(500, {'success': False, 'error': str(e)})


def _response(status: int, body: dict) -> dict:
    return {
        'statusCode': status,
        'body': json.dumps(body, default=str)
    }
