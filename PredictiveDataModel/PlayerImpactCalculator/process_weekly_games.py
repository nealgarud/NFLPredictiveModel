"""
Process All Games for a Week - Automated game processing using schedule API

This script:
1. Fetches the weekly schedule to get all game IDs
2. For each game, calculates injury impact
3. Stores results in Supabase
4. Generates weekly injury impact report

Usage:
    python process_weekly_games.py --season 2025 --week 10
"""

import os
import logging
import argparse
from datetime import datetime
from SportradarClient import SportradarClient
from S3DataLoader import S3DataLoader
from SupabaseStorage import SupabaseStorage
from PositionMapper import PositionMapper
from PlayerWeightAssigner import PlayerWeightAssigner
from InjuryImpactCalculator import InjuryImpactCalculator
from game_processor import GameProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def initialize_system():
    """Initialize all components"""
    logger.info("Initializing system components...")
    
    # API Client
    api_key = os.environ.get('SPORTRADAR_API_KEY', 'Passw0rdbr0!')
    client = SportradarClient(api_key=api_key)
    
    # S3 Data
    s3_loader = S3DataLoader(bucket_name='sportsdatacollection')
    madden_df = s3_loader.load_madden_ratings(season=2025)
    logger.info(f"Loaded {len(madden_df)} Madden ratings")
    
    # Pipeline components
    mapper = PositionMapper()
    assigner = PlayerWeightAssigner(madden_data=madden_df)
    calculator = InjuryImpactCalculator()
    processor = GameProcessor(client, mapper, assigner, calculator)
    
    # Storage
    storage = SupabaseStorage()
    
    logger.info("✓ System initialized")
    
    return {
        'client': client,
        'processor': processor,
        'storage': storage
    }


def get_week_games(client, season, week, season_type='REG'):
    """
    Fetch all games for a given week
    
    Returns:
        List of game dictionaries with game_id, home_team, away_team
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Fetching schedule for {season} {season_type} Week {week}")
    logger.info(f"{'='*60}")
    
    schedule = client.get_weekly_schedule(season, week, season_type)
    
    games = []
    week_data = schedule.get('week', {})
    game_list = week_data.get('games', [])
    
    logger.info(f"Found {len(game_list)} games for Week {week}")
    
    for game in game_list:
        game_info = {
            'game_id': game.get('id'),
            'home_team_id': game.get('home', {}).get('id'),
            'home_team_name': game.get('home', {}).get('name', 'Unknown'),
            'away_team_id': game.get('away', {}).get('id'),
            'away_team_name': game.get('away', {}).get('name', 'Unknown'),
            'scheduled': game.get('scheduled'),
            'status': game.get('status', 'scheduled')
        }
        games.append(game_info)
        
        logger.info(f"  {game_info['away_team_name']} @ {game_info['home_team_name']}")
    
    return games


def process_single_game(processor, storage, game_info, season, week, season_type):
    """Process a single game and store results"""
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing: {game_info['away_team_name']} @ {game_info['home_team_name']}")
    logger.info(f"{'='*60}")
    
    try:
        # Calculate injury impact
        result = processor.process_game(
            game_id=game_info['game_id'],
            home_team_id=game_info['home_team_id'],
            away_team_id=game_info['away_team_id'],
            season=season,
            week=week,
            season_type=season_type
        )
        
        # Store home team impact
        home_impact_data = {
            'game_id': game_info['game_id'],
            'team_id': game_info['home_team_id'],
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
        
        # Store away team impact
        away_impact_data = {
            'game_id': game_info['game_id'],
            'team_id': game_info['away_team_id'],
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
        
        # Log summary
        logger.info(f"✓ HOME ({game_info['home_team_name']}): "
                   f"{result['home_impact']['inactive_starter_count']} starters out, "
                   f"impact={result['home_impact']['replacement_adjusted_score']:.2f}")
        logger.info(f"✓ AWAY ({game_info['away_team_name']}): "
                   f"{result['away_impact']['inactive_starter_count']} starters out, "
                   f"impact={result['away_impact']['replacement_adjusted_score']:.2f}")
        logger.info(f"✓ Net Advantage: {result['net_injury_advantage']:.2f} "
                   f"({'HOME' if result['net_injury_advantage'] > 0 else 'AWAY'})")
        
        return result
        
    except Exception as e:
        logger.error(f"✗ Error processing game: {e}")
        import traceback
        traceback.print_exc()
        return None


def process_week(season, week, season_type='REG'):
    """
    Process all games for a given week
    
    Args:
        season: Year (e.g., 2025)
        week: Week number (1-18)
        season_type: 'REG' or 'POST'
    """
    start_time = datetime.now()
    
    logger.info("\n" + "="*80)
    logger.info(f"PROCESSING WEEK {week} OF {season} {season_type} SEASON")
    logger.info("="*80)
    
    # Initialize system
    components = initialize_system()
    
    # Get all games for the week
    games = get_week_games(components['client'], season, week, season_type)
    
    if not games:
        logger.warning("No games found for this week")
        return
    
    # Process each game
    results = []
    for i, game_info in enumerate(games, 1):
        logger.info(f"\n[Game {i}/{len(games)}]")
        result = process_single_game(
            processor=components['processor'],
            storage=components['storage'],
            game_info=game_info,
            season=season,
            week=week,
            season_type=season_type
        )
        if result:
            results.append(result)
    
    # Close connections
    components['storage'].close()
    
    # Summary report
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info("\n" + "="*80)
    logger.info("WEEKLY PROCESSING SUMMARY")
    logger.info("="*80)
    logger.info(f"Season: {season} {season_type} Week {week}")
    logger.info(f"Games Processed: {len(results)}/{len(games)}")
    logger.info(f"Time Elapsed: {elapsed:.1f} seconds")
    
    # Top injury impacts
    if results:
        logger.info("\nTop Injury Impacts (Replacement Adjusted):")
        all_impacts = []
        for result in results:
            all_impacts.append({
                'team': 'HOME',
                'game_id': result['game_id'],
                'impact': result['home_impact']['replacement_adjusted_score'],
                'starters_out': result['home_impact']['inactive_starter_count']
            })
            all_impacts.append({
                'team': 'AWAY',
                'game_id': result['game_id'],
                'impact': result['away_impact']['replacement_adjusted_score'],
                'starters_out': result['away_impact']['inactive_starter_count']
            })
        
        all_impacts.sort(key=lambda x: x['impact'], reverse=True)
        for i, impact in enumerate(all_impacts[:5], 1):
            logger.info(f"  {i}. Game {impact['game_id'][:8]}... ({impact['team']}): "
                       f"Impact={impact['impact']:.2f}, Starters Out={impact['starters_out']}")
    
    logger.info("="*80)
    logger.info("✓ WEEK PROCESSING COMPLETE")
    logger.info("="*80 + "\n")


def main():
    """Main entry point with CLI arguments"""
    parser = argparse.ArgumentParser(
        description='Process all NFL games for a given week with injury impact analysis'
    )
    parser.add_argument(
        '--season',
        type=int,
        default=2025,
        help='Season year (e.g., 2025)'
    )
    parser.add_argument(
        '--week',
        type=int,
        required=True,
        help='Week number (1-18 for regular season, 1-4 for playoffs)'
    )
    parser.add_argument(
        '--type',
        default='REG',
        choices=['REG', 'POST'],
        help='Season type: REG (regular season) or POST (playoffs)'
    )
    
    args = parser.parse_args()
    
    # Process the week
    process_week(
        season=args.season,
        week=args.week,
        season_type=args.type
    )


if __name__ == "__main__":
    # If run without arguments, process Week 10 of 2025 as example
    import sys
    if len(sys.argv) == 1:
        logger.info("No arguments provided. Processing Week 10 of 2025 as example.")
        logger.info("Usage: python process_weekly_games.py --season 2025 --week 10 --type REG\n")
        process_week(season=2025, week=10, season_type='REG')
    else:
        main()

