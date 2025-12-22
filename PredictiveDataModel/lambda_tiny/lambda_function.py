import json
import logging
from TextFileParser import TextFileParser
from GameRepository import GameRepository
from TeamRankingsRepository import TeamRankingsRepository
from AggregateCalculator import AggregateCalculator
from BettingAnalyzer import BettingAnalyzer
from RankingsCalculator import RankingsCalculator
from S3Handler import S3Handler
from DatabaseConnection import DatabaseConnection

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Main Lambda function - orchestrates the entire pipeline
    """
    logger.info("=" * 60)
    logger.info("NFL Data Processing Lambda")
    logger.info("=" * 60)
    
    try:
        # Extract S3 info from event
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = event['Records'][0]['s3']['object']['key']
        
        logger.info(f"\n1. Reading file from S3: s3://{bucket}/{key}")
        
        # Initialize handlers
        s3_handler = S3Handler()
        parser = TextFileParser(delimiter=',')  # Adjust delimiter as needed
        game_repo = GameRepository()
        rankings_repo = TeamRankingsRepository()
        
        # Step 1: Read text file from S3
        text_content = s3_handler.read_text_file(bucket, key)
        logger.info(f"✓ Read {len(text_content)} characters")
        
        # Step 2: Parse text file
        logger.info("\n2. Parsing text file...")
        games_df = parser.parse(text_content)
        logger.info(f"✓ Parsed {len(games_df)} games")
        
        # Step 3: Insert games into database
        logger.info("\n3. Inserting games into database...")
        games_inserted = game_repo.insert_games(games_df)
        logger.info(f"✓ Inserted/updated {games_inserted} games")
        
        # Step 4: Calculate rankings for each season
        logger.info("\n4. Calculating team rankings...")
        seasons = games_df['season'].unique()
        
        for season in sorted(seasons):
            logger.info(f"\n  Processing season {season}...")
            
            # Get all games for this season
            season_games = game_repo.get_games_by_season(season)
            
            # Calculate aggregate stats
            aggregate_calc = AggregateCalculator()
            team_stats = aggregate_calc.calculate_team_stats(season_games, season)
            logger.info(f"    ✓ Calculated aggregate stats for {len(team_stats)} teams")
            
            # Calculate betting metrics
            betting_analyzer = BettingAnalyzer()
            betting_stats = betting_analyzer.calculate_betting_metrics(season_games, season)
            logger.info(f"    ✓ Calculated betting metrics")
            
            # Merge stats
            team_stats = team_stats.merge(betting_stats, on=['team_id', 'season'], how='left')
            
            # Calculate rankings
            rankings_calc = RankingsCalculator()
            team_stats = rankings_calc.calculate_rankings(team_stats)
            logger.info(f"    ✓ Calculated rankings")
            
            # Upsert to database
            rankings_upserted = rankings_repo.upsert_rankings(team_stats)
            logger.info(f"    ✓ Upserted {rankings_upserted} team rankings")
        
        # Close database connection
        db = DatabaseConnection()
        db.close()
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ Processing Complete!")
        logger.info(f"  - Games processed: {games_inserted}")
        logger.info(f"  - Seasons updated: {len(seasons)}")
        logger.info("=" * 60)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Success',
                'games_processed': games_inserted,
                'seasons_updated': len(seasons)
            })
        }
        
    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Error',
                'error': str(e)
            })
        }