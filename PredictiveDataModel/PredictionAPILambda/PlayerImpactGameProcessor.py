"""
PlayerImpactGameProcessor - Lambda for processing individual games

Full workflow:
1. Fetch game roster from Sportradar API (active/inactive players)
2. Load player ratings from S3 (Madden ratings)
3. Calculate impact based on who's actually playing
4. Store results in Supabase for ML training
"""

import json
import logging
import os
import sys

# Add PlayerImpactCalculator to path
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

# Global instances for Lambda container reuse
_game_processor = None
_storage = None
_current_season = None

def lambda_handler(event, context):
    """
    Process a single game with injury impact analysis
    
    Event structure:
    {
        "game_id": "ca9d8f84-8e7b-4ee7-a310-54c2e3ca4edc",
        "home_team_id": "home-uuid",
        "away_team_id": "away-uuid",
        "season": 2024,
        "week": 10,
        "season_type": "REG"
    }
    
    Returns:
    {
        "statusCode": 200,
        "body": {
            "success": true,
            "data": {
                "game_id": "...",
                "home_impact": {...},
                "away_impact": {...},
                "net_injury_advantage": 2.5,
                "stored_in_db": true
            }
        }
    }
    """
    global _game_processor, _storage, _current_season
    
    try:
        # Parse event
        game_id = event.get('game_id')
        home_team_id = event.get('home_team_id')
        away_team_id = event.get('away_team_id')
        season = event.get('season', 2024)
        week = event.get('week')
        season_type = event.get('season_type', 'REG')
        
        # Validate required parameters
        if not game_id:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'success': False,
                    'error': 'game_id is required'
                })
            }
        
        logger.info(f"Processing game {game_id} - Season {season}, Week {week}")
        
        # Initialize components (cold start or season change)
        if _game_processor is None or _current_season != season:
            logger.info(f"Initializing components for season {season}...")
            
            # Sportradar API client
            api_key = os.environ.get('SPORTRADAR_API_KEY')
            if not api_key:
                raise ValueError("SPORTRADAR_API_KEY environment variable must be set")
            sportradar_client = SportradarClient(api_key=api_key)
            
            # S3 Data Loader
            s3_loader = S3DataLoader(bucket_name='player-data-nfl-predictive-model')
            madden_df = s3_loader.load_madden_ratings(season=season)
            logger.info(f"✓ Loaded {len(madden_df)} player ratings from {season}.csv")
            
            # Position mapper
            position_mapper = PositionMapper()
            
            # Weight assigner with Madden ratings
            weight_assigner = PlayerWeightAssigner(madden_data=madden_df)
            
            # Injury calculator
            injury_calculator = InjuryImpactCalculator()
            
            # Game processor (orchestrator)
            _game_processor = GameProcessor(
                sportradar_client=sportradar_client,
                position_mapper=position_mapper,
                weight_assigner=weight_assigner,
                injury_calculator=injury_calculator
            )
            
            # Supabase storage
            _storage = SupabaseStorage()
            
            _current_season = season
            logger.info("✓ All components initialized")
        else:
            logger.info(f"Using cached components (season {season})")
        
        # If team IDs not provided, fetch from game roster
        if not home_team_id or not away_team_id:
            logger.info("Team IDs not provided - fetching from game roster...")
            game_roster = _game_processor.client.get_game_roster(game_id)
            home_team_id = game_roster.get('home', {}).get('id')
            away_team_id = game_roster.get('away', {}).get('id')
            logger.info(f"✓ Found teams: {home_team_id} (home) vs {away_team_id} (away)")
        
        # STEP 1: Process the game (fetches active/inactive roster from Sportradar)
        logger.info("Fetching game roster and calculating impact...")
        result = _game_processor.process_game(
            game_id=game_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            season=season,
            week=week,
            season_type=season_type
        )
        
        logger.info(f"✓ Impact calculated:")
        logger.info(f"  Home: {result['home_impact']['inactive_starter_count']} starters out, "
                   f"impact = {result['home_impact']['replacement_adjusted_score']:.2f}")
        logger.info(f"  Away: {result['away_impact']['inactive_starter_count']} starters out, "
                   f"impact = {result['away_impact']['replacement_adjusted_score']:.2f}")
        logger.info(f"  Net advantage: {result['net_injury_advantage']:.2f}")
        
        # STEP 2: Store in Supabase for ML training
        logger.info("Storing results in Supabase...")
        
        # Store home team impact
        home_impact_data = {
            'game_id': game_id,
            'team_id': home_team_id,
            'season': season,
            'week': week,
            'season_type': season_type,
            'total_injury_score': result['home_impact']['total_injury_score'],
            'replacement_adjusted_score': result['home_impact']['replacement_adjusted_score'],
            'inactive_starter_count': result['home_impact']['inactive_starter_count'],
            'tier_1_out': result['home_impact']['tier_1_out'],
            'tier_2_out': result['home_impact']['tier_2_out'],
            'tier_3_out': result['home_impact']['tier_3_out'],
            'tier_4_out': result['home_impact']['tier_4_out'],
            'tier_5_out': result['home_impact']['tier_5_out'],
            'qb1_active': result['home_impact']['qb1_active'],
            'rb1_active': result['home_impact']['rb1_active'],
            'wr1_active': result['home_impact']['wr1_active'],
            'edge1_active': result['home_impact']['edge1_active'],
            'cb1_active': result['home_impact']['cb1_active'],
            'lt_active': result['home_impact']['lt_active'],
            's1_active': result['home_impact']['s1_active']
        }
        _storage.store_injury_impact(home_impact_data)
        
        # Store away team impact
        away_impact_data = {
            'game_id': game_id,
            'team_id': away_team_id,
            'season': season,
            'week': week,
            'season_type': season_type,
            'total_injury_score': result['away_impact']['total_injury_score'],
            'replacement_adjusted_score': result['away_impact']['replacement_adjusted_score'],
            'inactive_starter_count': result['away_impact']['inactive_starter_count'],
            'tier_1_out': result['away_impact']['tier_1_out'],
            'tier_2_out': result['away_impact']['tier_2_out'],
            'tier_3_out': result['away_impact']['tier_3_out'],
            'tier_4_out': result['away_impact']['tier_4_out'],
            'tier_5_out': result['away_impact']['tier_5_out'],
            'qb1_active': result['away_impact']['qb1_active'],
            'rb1_active': result['away_impact']['rb1_active'],
            'wr1_active': result['away_impact']['wr1_active'],
            'edge1_active': result['away_impact']['edge1_active'],
            'cb1_active': result['away_impact']['cb1_active'],
            'lt_active': result['away_impact']['lt_active'],
            's1_active': result['away_impact']['s1_active']
        }
        _storage.store_injury_impact(away_impact_data)
        
        logger.info("✓ Results stored in Supabase")
        
        # Return complete result
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'data': {
                    'game_id': result['game_id'],
                    'home_team_id': result['home_team_id'],
                    'away_team_id': result['away_team_id'],
                    'home_impact': result['home_impact'],
                    'away_impact': result['away_impact'],
                    'net_injury_advantage': result['net_injury_advantage'],
                    'stored_in_db': True
                }
            })
        }
        
    except Exception as e:
        logger.error(f"Error processing game: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': str(e),
                'game_id': event.get('game_id')
            })
        }


# For testing locally
if __name__ == "__main__":
    test_event = {
        "game_id": "ca9d8f84-8e7b-4ee7-a310-54c2e3ca4edc",
        "season": 2024,
        "week": 10,
        "season_type": "REG"
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))

