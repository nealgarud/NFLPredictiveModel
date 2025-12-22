from typing import List, Dict, Optional
import pandas as pd
import logging
from datetime import datetime

from TextFileParser import TextFileParser
from GameRepository import GameRepository
from TeamRankingsRepository import TeamRankingsRepository
from AggregateCalculator import AggregateCalculator
from BettingAnalyzer import BettingAnalyzer
from RankingsCalculator import RankingsCalculator
from S3Handler import S3Handler
from DuplicateHandler import DuplicateHandler
from DatabaseConnection import DatabaseConnection

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class DataPipelineOrchestrator:
    """
    Central orchestrator for the entire NFL data pipeline.
    Manages the workflow: Extract → Read → Calculate → Store
    """
    
    def __init__(self):
        # Initialize all dependencies
        self.s3_handler = S3Handler()
        self.parser = TextFileParser(delimiter=',')
        self.game_repo = GameRepository()
        self.rankings_repo = TeamRankingsRepository()
        self.aggregate_calc = AggregateCalculator()
        self.betting_analyzer = BettingAnalyzer()
        self.rankings_calc = RankingsCalculator()
        self.db = DatabaseConnection()
        
        # Pipeline state
        self.extracted_games = None
        self.existing_data_summary = {}
        self.seasons_to_process = []
        self.processing_log = []
    
    def run_pipeline(self, bucket: str, key: str) -> Dict:
        """
        Execute the complete data pipeline
        
        Args:
            bucket: S3 bucket name
            key: S3 object key for the .txt file
            
        Returns:
            Dictionary with pipeline execution summary
        """
        pipeline_start = datetime.now()
        
        try:
            # PHASE 1: EXTRACT
            logger.info("\n" + "="*60)
            logger.info("PHASE 1: EXTRACT DATA FROM S3")
            logger.info("="*60)
            extracted_data = self._phase_extract(bucket, key)
            
            # PHASE 2: READ EXISTING DATA
            logger.info("\n" + "="*60)
            logger.info("PHASE 2: READ EXISTING RDS DATA")
            logger.info("="*60)
            existing_summary = self._phase_read_existing()
            
            # PHASE 3: IDENTIFY WHAT TO PROCESS
            logger.info("\n" + "="*60)
            logger.info("PHASE 3: IDENTIFY PROCESSING SCOPE")
            logger.info("="*60)
            processing_plan = self._phase_identify_scope(extracted_data, existing_summary)
            
            # PHASE 4: STORE NEW GAMES
            logger.info("\n" + "="*60)
            logger.info("PHASE 4: STORE GAMES IN DATABASE")
            logger.info("="*60)
            games_stored = self._phase_store_games(extracted_data)
            
            # PHASE 5: CALCULATE INSIGHTS
            logger.info("\n" + "="*60)
            logger.info("PHASE 5: CALCULATE TEAM INSIGHTS")
            logger.info("="*60)
            insights = self._phase_calculate_insights(processing_plan)
            
            # PHASE 6: STORE INSIGHTS
            logger.info("\n" + "="*60)
            logger.info("PHASE 6: STORE INSIGHTS IN RANKINGS TABLE")
            logger.info("="*60)
            rankings_stored = self._phase_store_insights(insights)
            
            # PHASE 7: SUMMARY
            pipeline_end = datetime.now()
            duration = (pipeline_end - pipeline_start).total_seconds()
            
            summary = self._generate_summary(
                extracted_data=extracted_data,
                games_stored=games_stored,
                insights=insights,
                rankings_stored=rankings_stored,
                duration=duration
            )
            
            logger.info("\n" + "="*60)
            logger.info("PIPELINE EXECUTION COMPLETE")
            logger.info("="*60)
            self._print_summary(summary)
            
            return summary
            
        except Exception as e:
            logger.error(f"\n✗ Pipeline failed: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
        
        finally:
            # Always close DB connection
            self.db.close()
    
    def _phase_extract(self, bucket: str, key: str) -> pd.DataFrame:
        """
        PHASE 1: Extract and parse the .txt file from S3
        """
        logger.info(f"→ Reading file: s3://{bucket}/{key}")
        
        # Read text file from S3
        text_content = self.s3_handler.read_text_file(bucket, key)
        logger.info(f"  ✓ Read {len(text_content):,} characters")
        
        # Parse text file
        logger.info(f"→ Parsing text file...")
        games_df = self.parser.parse(text_content)
        logger.info(f"  ✓ Parsed {len(games_df):,} games")
        
        # Show breakdown by season and week
        breakdown = games_df.groupby(['season', 'week']).size().reset_index(name='games')
        logger.info(f"\n  Games by Season/Week:")
        for _, row in breakdown.iterrows():
            logger.info(f"    Season {row['season']}, Week {row['week']}: {row['games']} games")
        
        self.extracted_games = games_df
        return games_df
    
    def _phase_read_existing(self) -> Dict:
        """
        PHASE 2: Read existing data from RDS to understand what's already stored
        """
        logger.info(f"→ Querying existing games in database...")
        
        summary = {}
        
        # Check what seasons we have data for
        seasons = [2022, 2023, 2024, 2025]
        
        for season in seasons:
            game_count = self.game_repo.get_game_count(season)
            
            if game_count > 0:
                # Get week breakdown
                season_games = self.game_repo.get_games_by_season(season)
                week_counts = season_games.groupby('week').size().to_dict()
                
                summary[season] = {
                    'total_games': game_count,
                    'weeks': week_counts,
                    'max_week': max(week_counts.keys()) if week_counts else 0
                }
                
                logger.info(f"  ✓ Season {season}: {game_count} games stored (through Week {summary[season]['max_week']})")
            else:
                summary[season] = {
                    'total_games': 0,
                    'weeks': {},
                    'max_week': 0
                }
                logger.info(f"  ○ Season {season}: No games stored yet")
        
        self.existing_data_summary = summary
        return summary
    
    def _phase_identify_scope(self, extracted_data: pd.DataFrame, 
                               existing_summary: Dict) -> Dict:
        """
        PHASE 3: Identify what needs to be processed
        Determine which weeks are new or updated
        """
        logger.info(f"→ Comparing extracted data with existing data...")
        
        processing_plan = {
            'new_games': [],
            'updated_weeks': {},
            'seasons_to_recalculate': set()
        }
        
        for season in extracted_data['season'].unique():
            season_data = extracted_data[extracted_data['season'] == season]
            existing = existing_summary.get(season, {'weeks': {}, 'max_week': 0})
            
            for week in season_data['week'].unique():
                week_games = len(season_data[season_data['week'] == week])
                existing_week_games = existing['weeks'].get(week, 0)
                
                if week_games > existing_week_games:
                    # New or updated week
                    new_games_count = week_games - existing_week_games
                    processing_plan['new_games'].append({
                        'season': season,
                        'week': week,
                        'new_game_count': new_games_count
                    })
                    
                    if season not in processing_plan['updated_weeks']:
                        processing_plan['updated_weeks'][season] = []
                    processing_plan['updated_weeks'][season].append(week)
                    
                    # Mark season for recalculation
                    processing_plan['seasons_to_recalculate'].add(season)
        
        # Print processing plan
        if processing_plan['new_games']:
            logger.info(f"\n  New/Updated Data Found:")
            for item in processing_plan['new_games']:
                logger.info(f"    Season {item['season']}, Week {item['week']}: {item['new_game_count']} new games")
            
            logger.info(f"\n  Seasons to Recalculate: {sorted(processing_plan['seasons_to_recalculate'])}")
        else:
            logger.info(f"  ○ No new data to process")
        
        self.seasons_to_process = list(processing_plan['seasons_to_recalculate'])
        return processing_plan
    
    def _phase_store_games(self, games_df: pd.DataFrame) -> int:
        """
        PHASE 4: Store games in the database (with duplicate prevention)
        """
        logger.info(f"→ Inserting/updating games in database...")
        
        games_inserted = self.game_repo.insert_games(games_df)
        
        logger.info(f"  ✓ Processed {games_inserted:,} game records")
        logger.info(f"    (New games inserted or existing games updated)")
        
        return games_inserted
    
    def _phase_calculate_insights(self, processing_plan: Dict) -> Dict:
        """
        PHASE 5: Calculate all insights for affected seasons
        """
        seasons = processing_plan['seasons_to_recalculate']
        
        if not seasons:
            logger.info(f"  ○ No calculations needed (no new data)")
            return {}
        
        all_insights = {}
        
        for season in sorted(seasons):
            logger.info(f"\n→ Processing Season {season}...")
            
            # Get all games for this season
            logger.info(f"  → Fetching games from database...")
            season_games = self.game_repo.get_games_by_season(season)
            logger.info(f"    ✓ Retrieved {len(season_games):,} games")
            
            # Calculate aggregate statistics
            logger.info(f"  → Calculating aggregate statistics...")
            team_stats = self.aggregate_calc.calculate_team_stats(season_games, season)
            logger.info(f"    ✓ Calculated stats for {len(team_stats)} teams")
            
            # Calculate betting metrics
            logger.info(f"  → Analyzing betting odds...")
            betting_stats = self.betting_analyzer.calculate_betting_metrics(season_games, season)
            logger.info(f"    ✓ Analyzed betting data for {len(betting_stats)} teams")
            
            # Merge statistics
            logger.info(f"  → Merging all statistics...")
            combined_stats = team_stats.merge(
                betting_stats, 
                on=['team_id', 'season'], 
                how='left'
            )
            
            # Calculate rankings
            logger.info(f"  → Calculating rankings...")
            final_stats = self.rankings_calc.calculate_rankings(combined_stats)
            logger.info(f"    ✓ Ranked all teams (Offense, Defense, Overall)")
            
            # Show top 5 teams
            top_5 = final_stats.nsmallest(5, 'overall_rank')[['team_id', 'overall_rank', 'win_rate', 'offensive_rank', 'defensive_rank']]
            logger.info(f"\n    Top 5 Teams for {season}:")
            for _, team in top_5.iterrows():
                logger.info(f"      {team['overall_rank']:2d}. {team['team_id']:3s} - Win Rate: {team['win_rate']:.3f}, " +
                      f"Off Rank: {team['offensive_rank']:2d}, Def Rank: {team['defensive_rank']:2d}")
            
            all_insights[season] = final_stats
        
        return all_insights
    
    def _phase_store_insights(self, insights: Dict) -> int:
        """
        PHASE 6: Store calculated insights in team_rankings table
        """
        if not insights:
            logger.info(f"  ○ No insights to store")
            return 0
        
        total_stored = 0
        
        for season, stats_df in insights.items():
            logger.info(f"→ Storing rankings for Season {season}...")
            
            count = self.rankings_repo.upsert_rankings(stats_df)
            total_stored += count
            
            logger.info(f"  ✓ Stored {count} team ranking records")
        
        logger.info(f"\n  ✓ Total rankings stored: {total_stored}")
        
        return total_stored
    
    def _generate_summary(self, extracted_data: pd.DataFrame, games_stored: int,
                          insights: Dict, rankings_stored: int, duration: float) -> Dict:
        """
        Generate execution summary
        """
        return {
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'duration_seconds': duration,
            'extraction': {
                'total_games_extracted': len(extracted_data),
                'seasons_extracted': sorted(extracted_data['season'].unique().tolist()),
                'weeks_extracted': extracted_data.groupby('season')['week'].max().to_dict()
            },
            'storage': {
                'games_processed': games_stored,
                'rankings_stored': rankings_stored
            },
            'calculations': {
                'seasons_calculated': list(insights.keys()),
                'teams_per_season': {season: len(df) for season, df in insights.items()}
            },
            'database_state': self.existing_data_summary
        }
    
    def _print_summary(self, summary: Dict):
        """
        Print formatted summary
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"EXECUTION SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Status: {summary['status'].upper()}")
        logger.info(f"Duration: {summary['duration_seconds']:.2f} seconds")
        logger.info(f"\nExtraction:")
        logger.info(f"  - Games extracted: {summary['extraction']['total_games_extracted']:,}")
        logger.info(f"  - Seasons: {summary['extraction']['seasons_extracted']}")
        logger.info(f"\nStorage:")
        logger.info(f"  - Games processed: {summary['storage']['games_processed']:,}")
        logger.info(f"  - Rankings stored: {summary['storage']['rankings_stored']:,}")
        logger.info(f"\nCalculations:")
        logger.info(f"  - Seasons calculated: {summary['calculations']['seasons_calculated']}")
        for season, count in summary['calculations']['teams_per_season'].items():
            logger.info(f"    • Season {season}: {count} teams")
        logger.info(f"{'='*60}\n")