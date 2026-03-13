"""
PlayerSeasonStatsAggregator Lambda

Reads player_game_stats for a season and computes rolling per-player
season averages, storing them in player_season_stats.

BoxScoreCollector reads player_season_stats as player-specific baselines
for performance_surprise — comparing each player's game to THEIR own
season average rather than a hardcoded league average.

Run this AFTER BoxScoreCollector finishes a season (or set of weeks).
For retroactive computation, run week by week in ascending order.

Event formats:
    {"season": 2023}              -- aggregate all collected weeks for 2023
    {"season": 2023, "week": 10}  -- aggregate weeks 1-10 only
    {"seasons": [2023, 2024]}     -- aggregate multiple seasons sequentially
"""
import json
import logging
import os
import sys
import time
from typing import Any, Dict

sys.path.insert(0, '/var/task')

from DatabaseUtils import DatabaseUtils

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger().setLevel(logging.INFO)


def lambda_handler(event: Dict, context: Any) -> Dict:
    logger.info("=" * 60)
    logger.info("PlayerSeasonStatsAggregator started")
    logger.info(f"Event: {json.dumps(event)}")

    try:
        db = DatabaseUtils()

        # Support multi-season batch
        season  = event.get('season')
        seasons = event.get('seasons')
        week    = event.get('week')

        if not season and not seasons:
            raise ValueError("Must provide 'season' or 'seasons'")

        seasons_to_process = [season] if season else seasons
        total_players = 0

        for i, s in enumerate(seasons_to_process):
            logger.info(f"Aggregating season {s} (through_week={week or 'max'})")
            count = db.aggregate_player_season_stats(season=s, through_week=week)
            total_players += count
            logger.info(f"Season {s}: {count} player rows upserted")

            if i < len(seasons_to_process) - 1:
                time.sleep(0.5)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'seasons_processed': seasons_to_process,
                'through_week': week,
                'total_players_upserted': total_players,
            }),
        }

    except Exception as e:
        logger.error(f"Lambda failed: {e}", exc_info=True)
        return {'statusCode': 500, 'body': json.dumps({'success': False, 'error': str(e)})}
