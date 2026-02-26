"""
lambda_function.py
AWS Lambda handler for processing game player impact using PFF grades.

Workflow:
1. Query game_id_mapping table for games to process (filtered by season/week)
2. Extract sportradar_id for each game
3. Fetch rosters from Sportradar API
4. Calculate player impact using PFF grades
5. Update game_id_mapping with home/away impact scores

Event Formats:
    1. Process all unmapped games (default):
       {}
    
    2. Filter by season:
       {
           "season": 2024
       }
    
    3. Filter by season and week:
       {
           "season": 2024,
           "week": 10
       }
    
    4. Limit number of games:
       {
           "season": 2024,
           "limit": 50
       }
    
    5. Single game by internal ID (testing):
       {
           "game_id": "2024_10_BUF_KC",
           "sportradar_id": "abc-123-def",
           "season": 2024,
           "week": 10,
           "home_team": "KC",
           "away_team": "BUF"
       }
"""

import json
import logging
import os
import time
from typing import List, Dict, Any
from SportradarClient import SportradarClient
from DatabaseUtils import DatabaseUtils
from GameImpactProcessor import GameImpactProcessor

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Main Lambda handler for PFF Game Impact Processor.
    
    Workflow:
        1. Fetch games from game_id_mapping table (filtered by season/week if provided)
        2. For each game, use sportradar_id to fetch rosters and calculate impact
        3. Update game_id_mapping with home/away impact scores
    
    Args:
        event: Lambda event (see module docstring for formats)
        context: Lambda context
    
    Returns:
        Response with processing results
    """
    logger.info("=" * 60)
    logger.info("PFF Game Impact Processor Lambda Started")
    logger.info("=" * 60)
    logger.info(f"Event: {json.dumps(event)}")
    
    try:
        # Initialize components
        api_key = os.environ.get('SPORTRADAR_API_KEY')
        if not api_key:
            raise ValueError("SPORTRADAR_API_KEY not found in environment")
        
        sportradar = SportradarClient(api_key)
        db_utils = DatabaseUtils()
        processor = GameImpactProcessor(sportradar, db_utils)
        
        # Handle single game by internal game_id (testing mode)
        if 'game_id' in event and 'sportradar_id' in event:
            logger.info("Single game mode (testing)")
            result = processor.process_game(
                internal_game_id=event['game_id'],
                sportradar_id=event['sportradar_id'],
                season=event['season'],
                week=event['week'],
                home_team=event['home_team'],
                away_team=event['away_team']
            )
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'success': True,
                    'games_processed': 1,
                    'result': result
                }, default=str)
            }
        
        # Batch mode: Fetch games from game_id_mapping
        season = event.get('season')
        week = event.get('week')
        limit = event.get('limit')
        force = event.get('force', False)
        
        logger.info(f"Batch mode: Fetching games (season={season}, week={week}, limit={limit}, force={force})")
        games = db_utils.fetch_games_to_process(season=season, week=week, limit=limit, force=force)
        
        if not games:
            logger.info("No games found to process")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'success': True,
                    'games_processed': 0,
                    'message': 'No games found with specified filters'
                })
            }
        
        logger.info(f"Found {len(games)} games to process")
        
        # Process each game
        results = []
        success_count = 0
        
        for i, game in enumerate(games, 1):
            logger.info(f"[{i}/{len(games)}] Processing {game['game_id']}")
            
            try:
                result = processor.process_game(
                    internal_game_id=game['game_id'],
                    sportradar_id=game['sportradar_id'],
                    season=game['season'],
                    week=game['week'],
                    home_team=game['home_team'],
                    away_team=game['away_team']
                )
                
                if result['success']:
                    success_count += 1
                
                results.append({
                    'game_id': game['game_id'],
                    'success': result['success'],
                    'impact_differential': result.get('impact_differential'),
                    'home_impact': result.get('home_impact'),
                    'away_impact': result.get('away_impact')
                })
                
                # Rate limit protection (Sportradar API: 1 call/sec)
                if i < len(games):
                    time.sleep(1.1)
                
            except Exception as e:
                logger.error(f"Failed to process game {game['game_id']}: {e}", exc_info=True)
                results.append({
                    'game_id': game['game_id'],
                    'success': False,
                    'error': str(e)
                })
        
        logger.info("=" * 60)
        logger.info(f"Batch processing complete: {success_count}/{len(games)} games successful")
        logger.info("=" * 60)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'games_processed': success_count,
                'total_games': len(games),
                'filters': {
                    'season': season,
                    'week': week,
                    'limit': limit
                },
                'results': results
            }, default=str)
        }
    
    except Exception as e:
        logger.error(f"Lambda execution failed: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }
