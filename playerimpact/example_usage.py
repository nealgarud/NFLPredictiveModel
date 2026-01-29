"""
Example Usage - Full injury impact calculation pipeline with REAL DATA

This demonstrates:
- Fetching real data from Sportradar API
- Loading Madden ratings from S3
- Loading historical game data from S3
- Storing results in Supabase
- Processing a complete game with injury impact analysis
"""

import os
import logging
from SportradarClient import SportradarClient
from PositionMapper import PositionMapper
from MaddenRatingMapper import MaddenRatingMapper
from PlayerWeightAssigner import PlayerWeightAssigner
from InjuryImpactCalculator import InjuryImpactCalculator
from game_processor import GameProcessor
from S3DataLoader import S3DataLoader
from SupabaseStorage import SupabaseStorage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def initialize_components():
    """Initialize all components with real data sources"""
    
    logger.info("="*60)
    logger.info("INITIALIZING PLAYER IMPACT CALCULATOR WITH REAL DATA")
    logger.info("="*60)
    
    # ========== STEP 1: Initialize Sportradar API Client ==========
    api_key = os.environ.get('SPORTRADAR_API_KEY')
    if not api_key:
        raise ValueError("SPORTRADAR_API_KEY environment variable must be set")
    logger.info("Initializing Sportradar API client...")
    sportradar_client = SportradarClient(api_key=api_key)
    logger.info("✓ Sportradar client ready")
    
    # ========== STEP 2: Initialize S3 Data Loader ==========
    logger.info("Initializing S3 data loader...")
    s3_loader = S3DataLoader(bucket_name='sportsdatacollection')
    logger.info("✓ S3 loader ready")
    
    # ========== STEP 3: Load Madden Ratings from S3 ==========
    logger.info("Loading Madden ratings from S3...")
    madden_df = s3_loader.load_madden_ratings(season=2025)
    logger.info(f"✓ Loaded {len(madden_df)} Madden player ratings")
    
    # ========== STEP 4: Initialize Position Mapper ==========
    logger.info("Initializing position mapper...")
    position_mapper = PositionMapper()
    logger.info("✓ Position mapper ready")
    
    # ========== STEP 5: Initialize Weight Assigner with Madden Data ==========
    logger.info("Initializing player weight assigner...")
    weight_assigner = PlayerWeightAssigner(madden_data=madden_df)
    logger.info("✓ Weight assigner ready with Madden ratings")
    
    # ========== STEP 6: Initialize Injury Impact Calculator ==========
    logger.info("Initializing injury impact calculator...")
    injury_calculator = InjuryImpactCalculator()
    logger.info("✓ Injury calculator ready")
    
    # ========== STEP 7: Initialize Supabase Storage ==========
    logger.info("Initializing Supabase storage...")
    storage = SupabaseStorage()
    logger.info("✓ Supabase storage connected")
    
    # ========== STEP 8: Initialize Game Processor (orchestrator) ==========
    logger.info("Initializing game processor...")
    game_processor = GameProcessor(
        sportradar_client=sportradar_client,
        position_mapper=position_mapper,
        weight_assigner=weight_assigner,
        injury_calculator=injury_calculator
    )
    logger.info("✓ Game processor ready")
    
    logger.info("\n" + "="*60)
    logger.info("ALL COMPONENTS INITIALIZED SUCCESSFULLY")
    logger.info("="*60 + "\n")
    
    return {
        'game_processor': game_processor,
        's3_loader': s3_loader,
        'storage': storage,
        'sportradar_client': sportradar_client,
        'weight_assigner': weight_assigner
    }


def process_game_with_storage(components, game_id, home_team_id, away_team_id, season, week, season_type='REG'):
    """
    Process a game and store results in Supabase
    
    Args:
        components: Dict of initialized components
        game_id: Sportradar game UUID
        home_team_id: Sportradar home team UUID
        away_team_id: Sportradar away team UUID
        season: Year (e.g., 2025)
        week: Week number
        season_type: 'REG' or 'POST'
    """
    game_processor = components['game_processor']
    storage = components['storage']
    weight_assigner = components['weight_assigner']
    
    logger.info(f"\n{'='*60}")
    logger.info(f"PROCESSING GAME: {away_team_id} @ {home_team_id}")
    logger.info(f"Season: {season}, Week: {week}, Type: {season_type}")
    logger.info(f"{'='*60}\n")
    
    # Process the game
    result = game_processor.process_game(
        game_id=game_id,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        season=season,
        week=week,
        season_type=season_type
    )
    
    # Store home team injury impact
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
    storage.store_injury_impact(home_impact_data)
    
    # Store away team injury impact
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
    storage.store_injury_impact(away_impact_data)
    
    # Display results
    display_results(result)
    
    return result


def display_results(result):
    """Display injury impact results in a readable format"""
    
    print("\n" + "="*60)
    print("INJURY IMPACT RESULTS")
    print("="*60)
    
    print(f"\nHome Team Impact:")
    print(f"  - Inactive Starters: {result['home_impact']['inactive_starter_count']}")
    print(f"  - Raw Impact Score: {result['home_impact']['total_injury_score']:.2f}")
    print(f"  - Replacement Adjusted: {result['home_impact']['replacement_adjusted_score']:.2f}")
    print(f"  - Tier Breakdown: T1={result['home_impact']['tier_1_out']}, "
          f"T2={result['home_impact']['tier_2_out']}, "
          f"T3={result['home_impact']['tier_3_out']}")
    
    print(f"\nAway Team Impact:")
    print(f"  - Inactive Starters: {result['away_impact']['inactive_starter_count']}")
    print(f"  - Raw Impact Score: {result['away_impact']['total_injury_score']:.2f}")
    print(f"  - Replacement Adjusted: {result['away_impact']['replacement_adjusted_score']:.2f}")
    print(f"  - Tier Breakdown: T1={result['away_impact']['tier_1_out']}, "
          f"T2={result['away_impact']['tier_2_out']}, "
          f"T3={result['away_impact']['tier_3_out']}")
    
    print(f"\nNet Injury Advantage: {result['net_injury_advantage']:.2f}")
    if result['net_injury_advantage'] > 0:
        print("  → HOME team has advantage (less injured)")
    elif result['net_injury_advantage'] < 0:
        print("  → AWAY team has advantage (less injured)")
    else:
        print("  → Both teams equally impacted")
    
    print("\n" + "="*60 + "\n")


def main():
    """Run complete injury impact analysis with real data"""
    
    try:
        # Initialize all components
        components = initialize_components()
        
        # Example: Process a specific game
        # Replace these with real game IDs and team IDs from Sportradar
        game_id = "example-game-uuid"  # Get from Sportradar API
        home_team_id = "home-team-uuid"  # Get from Sportradar API
        away_team_id = "away-team-uuid"  # Get from Sportradar API
        season = 2025
        week = 10
        season_type = 'REG'
        
        # Process the game and store results
        result = process_game_with_storage(
            components=components,
            game_id=game_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            season=season,
            week=week,
            season_type=season_type
        )
        
        # Close connections
        components['storage'].close()
        
        logger.info("✓ Processing complete!")
        return result
        
    except Exception as e:
        logger.error(f"✗ Error in main process: {e}")
        import traceback
        traceback.print_exc()
        raise


def demo_load_historical_data():
    """Demo: Load and display historical game data from S3"""
    
    logger.info("="*60)
    logger.info("DEMO: Loading Historical Game Data from S3")
    logger.info("="*60)
    
    s3_loader = S3DataLoader()
    
    # Load historical games from 2022, 2023, 2024
    historical_df = s3_loader.load_all_historical_games([2022, 2023, 2024])
    
    logger.info(f"\n✓ Loaded {len(historical_df)} historical games")
    logger.info(f"Columns: {historical_df.columns.tolist()}")
    logger.info(f"Date range: {historical_df['date'].min() if 'date' in historical_df.columns else 'N/A'} to "
                f"{historical_df['date'].max() if 'date' in historical_df.columns else 'N/A'}")
    
    return historical_df


if __name__ == "__main__":
    # Run the main processing pipeline
    result = main()
    
    # Optional: Also demo loading historical data
    # historical_data = demo_load_historical_data()

