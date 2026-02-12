"""
HistoricalGamesBatchProcessor - Process ALL historical games for ML training

This Lambda:
1. Fetches all games from 2022-2025 (from S3 or Sportradar)
2. For each game, gets active roster from Sportradar
3. Calculates player impact based on who actually played
4. Stores in Supabase with game outcome and spread
5. Creates training dataset for ML model

Usage:
- Run once to build historical dataset
- Schedule weekly to update with new games
"""

import json
import logging
import os
import sys
import pandas as pd

sys.path.append(os.path.dirname(__file__))

from S3DataLoader import S3DataLoader
from SportradarClient import SportradarClient
from PositionMapper import PositionMapper
from PlayerWeightAssigner import PlayerWeightAssigner
from InjuryImpactCalculator import InjuryImpactCalculator
from game_processor import GameProcessor
from SupabaseStorage import SupabaseStorage

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Batch process historical games
    
    Event options:
    {
        "mode": "full",  // or "incremental"
        "seasons": [2022, 2023, 2024],  // optional, defaults to all
        "weeks": [1, 2, 3, ...],  // optional, defaults to all weeks
        "max_games": 100  // optional, for testing
    }
    """
    
    try:
        # Parse event
        mode = event.get('mode', 'full')
        seasons = event.get('seasons', [2022, 2023, 2024])
        weeks = event.get('weeks')  # None = all weeks
        max_games = event.get('max_games')  # Limit for testing
        
        logger.info(f"Starting {mode} batch processing for seasons: {seasons}")
        
        # Initialize components
        api_key = os.environ.get('SPORTRADAR_API_KEY')
        if not api_key:
            raise ValueError("SPORTRADAR_API_KEY environment variable must be set")
        sportradar = SportradarClient(api_key=api_key)
        s3_loader = S3DataLoader(bucket_name='player-data-nfl-predictive-model')
        storage = SupabaseStorage()
        
        total_processed = 0
        total_errors = 0
        results_by_season = {}
        
        # Process each season
        for season in seasons:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing Season {season}")
            logger.info(f"{'='*60}")
            
            # Load Madden ratings for this season
            logger.info(f"Loading player ratings from {season}.csv...")
            madden_df = s3_loader.load_madden_ratings(season=season)
            logger.info(f"✓ Loaded {len(madden_df)} player ratings")
            
            # Initialize season-specific components
            position_mapper = PositionMapper()
            weight_assigner = PlayerWeightAssigner(madden_data=madden_df)
            injury_calculator = InjuryImpactCalculator()
            game_processor = GameProcessor(
                sportradar_client=sportradar,
                position_mapper=position_mapper,
                weight_assigner=weight_assigner,
                injury_calculator=injury_calculator
            )
            
            # Get all games for this season
            games = get_season_games(sportradar, season, weeks)
            logger.info(f"Found {len(games)} games for season {season}")
            
            # Limit for testing
            if max_games:
                games = games[:max_games]
                logger.info(f"Limited to {max_games} games for testing")
            
            season_processed = 0
            season_errors = 0
            
            # Process each game
            for i, game in enumerate(games, 1):
                try:
                    logger.info(f"\n[{i}/{len(games)}] Processing game {game['id'][:8]}...")
                    
                    # Process game
                    result = game_processor.process_game(
                        game_id=game['id'],
                        home_team_id=game['home_team_id'],
                        away_team_id=game['away_team_id'],
                        season=season,
                        week=game['week'],
                        season_type=game['season_type']
                    )
                    
                    # Store home team impact
                    store_game_impact(storage, result, game, 'home')
                    
                    # Store away team impact
                    store_game_impact(storage, result, game, 'away')
                    
                    season_processed += 1
                    total_processed += 1
                    
                    logger.info(f"✓ Stored game {game['id'][:8]} - "
                               f"Home: {result['home_impact']['inactive_starter_count']} out, "
                               f"Away: {result['away_impact']['inactive_starter_count']} out")
                    
                except Exception as e:
                    season_errors += 1
                    total_errors += 1
                    logger.error(f"✗ Error processing game {game.get('id', 'unknown')[:8]}: {e}")
                    continue
            
            results_by_season[season] = {
                'processed': season_processed,
                'errors': season_errors
            }
            
            logger.info(f"\n✓ Season {season} complete: {season_processed} games processed, {season_errors} errors")
        
        # Final summary
        logger.info(f"\n{'='*60}")
        logger.info("BATCH PROCESSING COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Total games processed: {total_processed}")
        logger.info(f"Total errors: {total_errors}")
        logger.info(f"By season: {json.dumps(results_by_season, indent=2)}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'total_processed': total_processed,
                'total_errors': total_errors,
                'by_season': results_by_season
            })
        }
        
    except Exception as e:
        logger.error(f"Batch processing failed: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }


def get_season_games(sportradar, season, weeks=None):
    """Get all games for a season from Sportradar"""
    games = []
    
    # Get regular season schedule
    logger.info(f"Fetching {season} schedule...")
    schedule = sportradar.get_season_schedule(season, season_type='REG')
    
    # Parse weeks
    for week_data in schedule.get('weeks', []):
        week_num = week_data.get('sequence')
        
        # Filter by weeks if specified
        if weeks and week_num not in weeks:
            continue
        
        # Get games from this week
        for game in week_data.get('games', []):
            games.append({
                'id': game.get('id'),
                'week': week_num,
                'season_type': 'REG',
                'home_team_id': game.get('home', {}).get('id'),
                'away_team_id': game.get('away', {}).get('id'),
                'home_points': game.get('home_points'),
                'away_points': game.get('away_points'),
                'status': game.get('status'),
                'scheduled': game.get('scheduled')
            })
    
    logger.info(f"Found {len(games)} regular season games")
    return games


def store_game_impact(storage, result, game, team_side):
    """Store impact data with game outcome for ML training"""
    
    team_id = result[f'{team_side}_team_id']
    impact = result[f'{team_side}_impact']
    
    # Determine if this team covered the spread
    # (This would come from your game data - you'll need to add spread info)
    
    impact_data = {
        'game_id': game['id'],
        'team_id': team_id,
        'season': result.get('season', game.get('season')),
        'week': game['week'],
        'season_type': game['season_type'],
        'total_injury_score': impact['total_injury_score'],
        'replacement_adjusted_score': impact['replacement_adjusted_score'],
        'inactive_starter_count': impact['inactive_starter_count'],
        'tier_1_out': impact['tier_1_out'],
        'tier_2_out': impact['tier_2_out'],
        'tier_3_out': impact['tier_3_out'],
        'tier_4_out': impact['tier_4_out'],
        'tier_5_out': impact['tier_5_out'],
        'qb1_active': impact['qb1_active'],
        'rb1_active': impact['rb1_active'],
        'wr1_active': impact['wr1_active'],
        'edge1_active': impact['edge1_active'],
        'cb1_active': impact['cb1_active'],
        'lt_active': impact['lt_active'],
        's1_active': impact['s1_active']
    }
    
    storage.store_injury_impact(impact_data)


# For local testing
if __name__ == "__main__":
    # Test with limited games
    test_event = {
        "mode": "full",
        "seasons": [2024],
        "max_games": 5  # Test with 5 games
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))

