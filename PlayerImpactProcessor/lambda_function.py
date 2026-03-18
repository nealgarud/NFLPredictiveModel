"""
PlayerImpactProcessor Lambda
=============================
Enhanced BoxScoreCollector with full nflverse enrichment.

For each game in game_id_mapping (filtered by season/week):
  1. Fetch Sportradar /games/{id}/statistics.json → player stats + scores
  2. Parse + enrich with PFF grades and player-season baselines
  3. Fetch nflverse game-week stats (QB/RB/WR/TE) from nflverse_*_stats tables
  4. Fetch nflverse rolling baselines (prior weeks, same season)
  5. Build nflverse_data lookup keyed by Sportradar player_id (via name match)
  6. calc_team_impacts (two-pass OL, position groups, multiplier_components)
  7. Upsert enriched player rows → player_game_stats
  8. Write position-group impacts + player_details JSONB → game_id_mapping

Event formats:
    {}                                  -- all uncollected games
    {"season": 2024}                    -- one season
    {"season": 2024, "week": 10}        -- one week
    {"season": 2024, "limit": 5}        -- limited batch
    {"force": true, "season": 2024}     -- re-collect already processed games
    {                                   -- single game test
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
import re
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, '/var/task')

from SportradarClient import SportradarClient
from BoxScoreParser import parse_game_statistics
from GameImpactCalculator import calc_team_impacts, calc_performance_surprise
from DatabaseUtils import DatabaseUtils
from NflverseReader import NflverseReader, _norm

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger().setLevel(logging.INFO)


def lambda_handler(event: Dict, context: Any) -> Dict:
    logger.info("=" * 60)
    logger.info("PlayerImpactProcessor Lambda started")
    logger.info("Event: %s", json.dumps(event))

    try:
        api_key = os.environ.get('SPORTRADAR_API_KEY')
        if not api_key:
            raise ValueError("SPORTRADAR_API_KEY not set")

        sportradar = SportradarClient(api_key)
        db         = DatabaseUtils()
        nflverse   = NflverseReader(db)

        # ── SQS trigger — unwrap Records[0].body ─────────────────────────────
        if 'Records' in event:
            record   = event['Records'][0]
            raw_body = record['body'].strip()
            logger.info("SQS raw body: %r", raw_body)
            decoder  = json.JSONDecoder()
            event, _ = decoder.raw_decode(raw_body)
            logger.info("SQS message parsed: %s", json.dumps(event))

        # ── Single-game test mode ─────────────────────────────────────────────
        if 'game_id' in event and 'sportradar_id' in event:
            game = {
                'game_id':       event['game_id'],
                'sportradar_id': event['sportradar_id'],
                'season':        event['season'],
                'week':          event['week'],
                'home_team':     event['home_team'],
                'away_team':     event['away_team'],
            }
            result = _process_game(game, sportradar, db, nflverse)
            return {
                'statusCode': 200,
                'body': json.dumps({'success': True, 'result': result}, default=str),
            }

        # ── Batch mode ────────────────────────────────────────────────────────
        season = event.get('season')
        week   = event.get('week')
        limit  = event.get('limit')
        force  = event.get('force', False)

        games = db.fetch_games_to_process(season=season, week=week, limit=limit, force=force)
        if not games:
            logger.info("No games to process")
            return {'statusCode': 200, 'body': json.dumps({'success': True, 'games_processed': 0})}

        logger.info("Processing %d games", len(games))
        results       = []
        success_count = 0

        for i, game in enumerate(games, 1):
            logger.info("[%d/%d] %s", i, len(games), game['game_id'])
            try:
                result = _process_game(game, sportradar, db, nflverse)
                if result['success']:
                    success_count += 1
                results.append({'game_id': game['game_id'], **result})
            except Exception as e:
                logger.error("Failed %s: %s", game['game_id'], e, exc_info=True)
                results.append({'game_id': game['game_id'], 'success': False, 'error': str(e)})

            # Sportradar trial: 1 req/sec
            if i < len(games):
                time.sleep(1.1)

        logger.info("Done: %d/%d successful", success_count, len(games))
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success':         True,
                'games_processed': success_count,
                'total_games':     len(games),
                'results':         results,
            }, default=str),
        }

    except Exception as e:
        logger.error("Lambda failed: %s", e, exc_info=True)
        return {'statusCode': 500, 'body': json.dumps({'success': False, 'error': str(e)})}


def _process_game(
    game: Dict,
    sportradar: SportradarClient,
    db: DatabaseUtils,
    nflverse: NflverseReader,
) -> Dict:
    """Full pipeline for one game: fetch → parse → enrich → store → impact → surprise."""
    gid    = game['game_id']
    sid    = game['sportradar_id']
    home   = game['home_team']
    away   = game['away_team']
    season = game['season']
    week   = game['week']

    # 1. Fetch + parse Sportradar stats
    stats_resp = sportradar.get_game_statistics(sid)
    players    = parse_game_statistics(stats_resp, gid, season, week)

    if not players:
        logger.warning("No players parsed from %s", gid)
        return {'success': False, 'reason': 'no_players'}

    # 2. Enrich with PFF grades
    player_names = [p['player_name'] for p in players if p.get('player_name')]
    pff_grades   = db.fetch_pff_grades_bulk(player_names, season)
    for p in players:
        p['pff_grade'] = pff_grades.get(p.get('player_name'))

    # 3. Fetch player-specific season baselines (player_season_stats)
    player_ids       = [p['player_id'] for p in players if p.get('player_id')]
    player_baselines = db.fetch_player_season_stats(player_ids, season)

    # 4. Fetch nflverse game + rolling baselines from DB
    try:
        nflverse_game      = nflverse.fetch_game_nflverse(season, week)
        nflverse_baselines = nflverse.fetch_nflverse_baselines(season, week)
    except Exception as e:
        logger.warning("NflverseReader failed for %s w%d: %s — falling back to box-score only", season, week, e)
        nflverse_game      = {}
        nflverse_baselines = {}

    # 5. Build nflverse_data: {player_id → {nv_game, nv_base}}
    #    Match Sportradar player_name to nflverse player_name via _norm()
    nflverse_data: Dict[str, Dict] = {}
    for p in players:
        norm_name = _norm(p.get('player_name') or '')
        nv_game   = nflverse_game.get(norm_name)
        nv_base   = nflverse_baselines.get(norm_name)
        if nv_game or nv_base:
            nflverse_data[p.get('player_id', '')] = {
                'nv_game': nv_game,
                'nv_base': nv_base,
            }

    logger.info(
        "%s: %d Sportradar players, %d nflverse matches",
        gid, len(players), len(nflverse_data),
    )

    # 6. Calculate enriched team impacts (two-pass OL + position groups)
    home_actual, home_expected, home_groups, home_details = calc_team_impacts(
        players, home, player_baselines, nflverse_data
    )
    away_actual, away_expected, away_groups, away_details = calc_team_impacts(
        players, away, player_baselines, nflverse_data
    )

    # 7. Upsert enriched player rows
    db.upsert_player_stats_enriched(players)

    # 8. Compute surprise and write enriched game record
    home_surprise = calc_performance_surprise(home_actual, home_expected)
    away_surprise = calc_performance_surprise(away_actual, away_expected)

    db.update_game_with_enriched_impact(
        gid,
        home_actual,   away_actual,
        home_surprise, away_surprise,
        home_groups,   away_groups,
        home_details,  away_details,
    )

    return {
        'success':           True,
        'players_collected': len(players),
        'nflverse_matches':  len(nflverse_data),
        'home_actual':       home_actual,
        'home_expected':     home_expected,
        'away_actual':       away_actual,
        'away_expected':     away_expected,
        'home_surprise':     home_surprise,
        'away_surprise':     away_surprise,
        'home_groups':       home_groups,
        'away_groups':       away_groups,
    }
