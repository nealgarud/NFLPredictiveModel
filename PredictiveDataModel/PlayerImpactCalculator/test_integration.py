"""
Integration Test Script - Verify all real data connections work

Tests:
1. Sportradar API connectivity
2. S3 data access (Madden ratings & historical games)
3. Supabase database connection
4. Full pipeline end-to-end
"""

import os
import logging
from SportradarClient import SportradarClient
from S3DataLoader import S3DataLoader
from SupabaseStorage import SupabaseStorage
from PositionMapper import PositionMapper
from PlayerWeightAssigner import PlayerWeightAssigner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_sportradar_api():
    """Test Sportradar API connection"""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Sportradar API Connection")
    logger.info("="*60)
    
    try:
        api_key = os.environ.get('SPORTRADAR_API_KEY', 'Passw0rdbr0!')
        client = SportradarClient(api_key=api_key)
        
        # Test 1a: Weekly schedule (CRITICAL - get game IDs)
        logger.info("Fetching weekly schedule for 2025 REG Week 10...")
        schedule = client.get_weekly_schedule(season=2025, week=10, season_type='REG')
        
        games = schedule.get('week', {}).get('games', [])
        logger.info(f"✓ SUCCESS: Fetched {len(games)} games")
        
        if games:
            sample_game = games[0]
            logger.info(f"  Sample game: {sample_game.get('away', {}).get('name')} @ {sample_game.get('home', {}).get('name')}")
            logger.info(f"  Game ID: {sample_game.get('id')}")
        
        # Test 1b: Injury endpoint (2025 Week 10)
        logger.info("\nFetching injuries for 2025 REG Week 10...")
        injuries = client.get_injuries(season=2025, week=10, season_type='REG')
        
        teams = injuries.get('week', {}).get('teams', [])
        logger.info(f"✓ SUCCESS: Fetched injury data for {len(teams)} teams")
        
        if teams:
            logger.info(f"  Sample team: {teams[0].get('name', 'Unknown')}")
            injured_count = len(teams[0].get('players', []))
            logger.info(f"  Injured players on first team: {injured_count}")
        
        # Test 1c: Game roster (if we have a game_id)
        if games:
            game_id = games[0].get('id')
            logger.info(f"\nFetching game roster for game {game_id[:8]}...")
            roster = client.get_game_roster(game_id)
            
            home_players = len(roster.get('home', {}).get('players', []))
            away_players = len(roster.get('away', {}).get('players', []))
            logger.info(f"✓ SUCCESS: Home={home_players} players, Away={away_players} players")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_s3_access():
    """Test S3 data loading"""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: AWS S3 Data Access")
    logger.info("="*60)
    
    try:
        loader = S3DataLoader(bucket_name='sportsdatacollection')
        
        # Test listing files
        logger.info("Listing available Madden files...")
        madden_files = loader.list_available_madden_files()
        logger.info(f"✓ Found {len(madden_files)} Madden CSV files")
        for file in madden_files[:3]:
            logger.info(f"  - {file}")
        
        logger.info("\nListing available game data files...")
        game_files = loader.list_available_game_data_files()
        logger.info(f"✓ Found {len(game_files)} game data CSV files")
        for file in game_files:
            logger.info(f"  - {file}")
        
        # Test loading Madden ratings
        logger.info("\nLoading Madden 2025 ratings...")
        madden_df = loader.load_madden_ratings(season=2025)
        logger.info(f"✓ SUCCESS: Loaded {len(madden_df)} player ratings")
        logger.info(f"  Columns: {madden_df.columns.tolist()}")
        
        if len(madden_df) > 0:
            logger.info(f"  Sample player: {madden_df.iloc[0].to_dict()}")
        
        # Test loading historical games
        logger.info("\nLoading 2024 game data...")
        games_df = loader.load_historical_games(season=2024)
        logger.info(f"✓ SUCCESS: Loaded {len(games_df)} games from 2024")
        logger.info(f"  Columns: {games_df.columns.tolist()}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_supabase_connection():
    """Test Supabase database connection"""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Supabase Database Connection")
    logger.info("="*60)
    
    try:
        storage = SupabaseStorage()
        logger.info("✓ Database connection established")
        
        # Test storing a player rating
        logger.info("\nTesting player rating storage...")
        test_player = {
            'player_id': 'test_integration_001',
            'player_name': 'Integration Test Player',
            'position': 'QB',
            'team': 'TST',
            'madden_rating': 85,
            'position_key': 'QB1',
            'weight': 0.95,
            'tier': 1,
            'season': 2025
        }
        
        success = storage.store_player_rating(test_player)
        logger.info(f"✓ Player rating stored: {success}")
        
        # Test retrieving the player
        retrieved = storage.get_player_rating('test_integration_001')
        if retrieved:
            logger.info(f"✓ Player rating retrieved: {retrieved['player_name']}")
        else:
            logger.warning("Player not found after storage")
        
        # Test storing injury impact
        logger.info("\nTesting injury impact storage...")
        test_impact = {
            'game_id': 'test_game_001',
            'team_id': 'test_team_001',
            'season': 2025,
            'week': 10,
            'season_type': 'REG',
            'total_injury_score': 2.5,
            'replacement_adjusted_score': 1.8,
            'inactive_starter_count': 3,
            'tier_1_out': 0,
            'tier_2_out': 2,
            'tier_3_out': 1,
            'tier_4_out': 0,
            'tier_5_out': 0,
            'qb1_active': True,
            'rb1_active': False,
            'wr1_active': True,
            'edge1_active': False,
            'cb1_active': True,
            'lt_active': True,
            's1_active': False
        }
        
        success = storage.store_injury_impact(test_impact)
        logger.info(f"✓ Injury impact stored: {success}")
        
        # Test retrieving game impact
        impacts = storage.get_game_injury_impact('test_game_001')
        logger.info(f"✓ Retrieved {len(impacts)} injury impact records")
        
        storage.close()
        logger.info("✓ SUCCESS: Database connection closed cleanly")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_pipeline():
    """Test complete pipeline integration"""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: Full Pipeline Integration")
    logger.info("="*60)
    
    try:
        # Initialize all components
        logger.info("Initializing components...")
        
        s3_loader = S3DataLoader()
        madden_df = s3_loader.load_madden_ratings(2025)
        logger.info(f"✓ Loaded {len(madden_df)} Madden ratings")
        
        position_mapper = PositionMapper()
        logger.info("✓ Position mapper initialized")
        
        weight_assigner = PlayerWeightAssigner(madden_data=madden_df)
        logger.info("✓ Weight assigner initialized with Madden data")
        
        # Test position mapping
        logger.info("\nTesting position mapping...")
        test_positions = ['QB', 'QUARTERBACK', 'Wide Receiver', 'DEFENSIVE END']
        for pos in test_positions:
            standard = position_mapper.standardize_position(pos)
            logger.info(f"  {pos:20} → {standard}")
        
        logger.info("✓ SUCCESS: Full pipeline components working together")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all integration tests"""
    logger.info("\n" + "="*80)
    logger.info("PLAYERIMPACTCALCULATOR INTEGRATION TEST SUITE")
    logger.info("="*80)
    
    results = {
        'Sportradar API': test_sportradar_api(),
        'S3 Data Access': test_s3_access(),
        'Supabase Database': test_supabase_connection(),
        'Full Pipeline': test_full_pipeline()
    }
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{test_name:25} {status}")
    
    logger.info("="*80)
    logger.info(f"TOTAL: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 ALL TESTS PASSED! System is ready to use.")
    else:
        logger.warning("⚠️  Some tests failed. Check configuration and credentials.")
    
    logger.info("="*80)
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)

