"""
BoxScoreCollector Lambda

For each game in game_id_mapping (filtered by season/week):
  1. Calls Sportradar /games/{id}/statistics.json  → player stats + final scores
  2. Parses + upserts rows into player_game_stats
  3. Calculates actual team impact scores
  4. Computes performance_surprise vs pre-game expected impact
  5. Updates game_id_mapping with all new values

Note: summary.json (quarter scores + weather) is intentionally excluded for now
to stay within Sportradar trial rate limits (1 call/game). Add back later.

Event formats:
    {}                              -- all uncollected games
    {"season": 2024}                -- one season
    {"season": 2024, "week": 10}    -- one week
    {"season": 2024, "limit": 5}    -- limited batch
    {"force": true, "season": 2024} -- re-collect already processed games
    {                               -- single game test
        "game_id": "2024_10_BUF_KC",
        "sportradar_id": "uuid-here",
        "season": 2024, "week": 10,
        "home_team": "KC", "away_team": "BUF"
    }

SQS trigger format (Records wrapper parsed automatically):
    {"Records": [{"body": "{\"season\": 2023, \"week\": 1}"}]}
"""
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, '/var/task')

from SportradarClient import SportradarClient
from BoxScoreParser import parse_game_statistics
from GameImpactCalculator import calc_team_impacts, calc_performance_surprise
from DatabaseUtils import DatabaseUtils

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger().setLevel(logging.INFO)


def lambda_handler(event: Dict, context: Any) -> Dict:
    logger.info("=" * 60)
    logger.info("BoxScoreCollector Lambda started")
    logger.info(f"Event: {json.dumps(event)}")

    try:
        api_key = os.environ.get('SPORTRADAR_API_KEY')
        if not api_key:
            raise ValueError("SPORTRADAR_API_KEY not set")

        sportradar = SportradarClient(api_key)
        db = DatabaseUtils()

        # ── SQS trigger — unwrap Records[0].body ──────────────────────────
        if 'Records' in event:
            record = event['Records'][0]
            raw_body = record['body'].strip()
            logger.info(f"SQS raw body: {repr(raw_body)}")
            decoder = json.JSONDecoder()
            event, _ = decoder.raw_decode(raw_body)
            logger.info(f"SQS message parsed: {json.dumps(event)}")

        # ── Single game test mode ──────────────────────────────────────────
        if 'game_id' in event and 'sportradar_id' in event:
            game = {
                'game_id':       event['game_id'],
                'sportradar_id': event['sportradar_id'],
                'season':        event['season'],
                'week':          event['week'],
                'home_team':     event['home_team'],
                'away_team':     event['away_team'],
            }
            result = _process_game(game, sportradar, db)
            return {'statusCode': 200, 'body': json.dumps({'success': True, 'result': result}, default=str)}

        # ── Batch mode ─────────────────────────────────────────────────────
        season = event.get('season')
        week   = event.get('week')
        limit  = event.get('limit')
        force  = event.get('force', False)

        games = db.fetch_games_to_process(season=season, week=week, limit=limit, force=force)
        if not games:
            logger.info("No games to process")
            return {'statusCode': 200, 'body': json.dumps({'success': True, 'games_processed': 0})}

        logger.info(f"Processing {len(games)} games")
        results = []
        success_count = 0

        for i, game in enumerate(games, 1):
            logger.info(f"[{i}/{len(games)}] {game['game_id']}")
            try:
                result = _process_game(game, sportradar, db)
                if result['success']:
                    success_count += 1
                results.append({'game_id': game['game_id'], **result})
            except Exception as e:
                logger.error(f"Failed {game['game_id']}: {e}", exc_info=True)
                results.append({'game_id': game['game_id'], 'success': False, 'error': str(e)})

            # Sportradar trial: 1 req/sec — 1 call per game (statistics only)
            if i < len(games):
                time.sleep(1.1)

        logger.info(f"Done: {success_count}/{len(games)} successful")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'games_processed': success_count,
                'total_games': len(games),
                'results': results,
            }, default=str),
        }

    except Exception as e:
        logger.error(f"Lambda failed: {e}", exc_info=True)
        return {'statusCode': 500, 'body': json.dumps({'success': False, 'error': str(e)})}


def _process_game(game: Dict, sportradar: SportradarClient, db: DatabaseUtils) -> Dict:
    """Full pipeline for one game: fetch → parse → store → impact → surprise."""
    gid  = game['game_id']
    sid  = game['sportradar_id']
    home = game['home_team']
    away = game['away_team']

    # 1. Fetch player stats (1 API call — statistics.json contains final scores too)
    stats_resp = sportradar.get_game_statistics(sid)
    players    = parse_game_statistics(stats_resp, gid, game['season'], game['week'])

    if not players:
        logger.warning(f"No players parsed from {gid}")
        return {'success': False, 'reason': 'no_players'}

    # 2. Enrich each player with their season PFF grade
    player_names = [p['player_name'] for p in players if p.get('player_name')]
    pff_grades   = db.fetch_pff_grades_bulk(player_names, game['season'])
    for p in players:
        p['pff_grade'] = pff_grades.get(p.get('player_name'))

    # 3. Fetch player-specific season baselines for performance_surprise
    #    (player_season_stats populated by PlayerSeasonStatsAggregator)
    player_ids       = [p['player_id'] for p in players if p.get('player_id')]
    player_baselines = db.fetch_player_season_stats(player_ids, game['season'])

    # 4. Calculate actual + expected impact using player-specific baselines
    home_actual, home_expected = calc_team_impacts(players, home, player_baselines)
    away_actual, away_expected = calc_team_impacts(players, away, player_baselines)

    # 5. Upsert player rows (pff_grade, performance_multiplier, actual_impact_score populated)
    db.upsert_player_stats(players)

    # 6. Compute surprise and write to game_id_mapping
    home_surprise = calc_performance_surprise(home_actual, home_expected)
    away_surprise = calc_performance_surprise(away_actual, away_expected)

    db.update_performance_surprise(gid, home_actual, away_actual, home_surprise, away_surprise)

    return {
        'success': True,
        'players_collected': len(players),
        'home_actual': home_actual,
        'home_expected': home_expected,
        'away_actual': away_actual,
        'away_expected': away_expected,
        'home_surprise': home_surprise,
        'away_surprise': away_surprise,
    }
