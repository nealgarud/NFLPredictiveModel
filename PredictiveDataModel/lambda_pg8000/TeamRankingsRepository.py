import pandas as pd
import logging
from DatabaseConnection import DatabaseConnection
from DuplicateHandler import DuplicateHandler

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class TeamRankingsRepository:
    """Repository for team_rankings table operations"""
    
    def __init__(self):
        self.db = DatabaseConnection()
        self.duplicate_handler = DuplicateHandler()
    
    def upsert_rankings(self, rankings_df: pd.DataFrame) -> int:
        """
        Insert or update team rankings
        
        Args:
            rankings_df: DataFrame with team rankings
            
        Returns:
            Number of records inserted/updated
        """
        conn = self.db.get_connection()
        
        columns = [
            'team_id', 'season', 'games_played', 'wins', 'losses', 'ties', 'win_rate',
            'total_points_scored', 'total_points_allowed',
            'avg_points_scored', 'avg_points_allowed',
            'point_differential', 'avg_point_differential',
            'offensive_rank', 'defensive_rank', 'overall_rank',
            'home_games', 'home_wins', 'home_losses', 'home_win_rate',
            'home_avg_points_scored', 'home_avg_points_allowed',
            'away_games', 'away_wins', 'away_losses', 'away_win_rate',
            'away_avg_points_scored', 'away_avg_points_allowed',
            'div_games', 'div_wins', 'div_losses', 'div_win_rate',
            'avg_spread_line', 'avg_total_line', 'times_favored', 'times_underdog',
            'ats_wins', 'ats_losses', 'ats_pushes', 'ats_cover_rate', 'avg_spread_margin'
        ]
        
        conflict_columns = ['team_id', 'season']
        update_columns = [col for col in columns if col not in conflict_columns]
        
        query = self.duplicate_handler.generate_upsert_query(
            table='team_rankings',
            columns=columns,
            conflict_columns=conflict_columns,
            update_columns=update_columns
        )
        
        upsert_count = 0
        
        for _, row in rankings_df.iterrows():
            try:
                values = [row[col] if pd.notna(row[col]) else None for col in columns]
                conn.run(query, *values)
                upsert_count += 1
            except Exception as e:
                logger.error(f"Error upserting rankings for {row['team_id']} {row['season']}: {e}")
                continue
        
        return upsert_count
    
    def get_rankings_by_season(self, season: int) -> pd.DataFrame:
        """Get all team rankings for a season"""
        conn = self.db.get_connection()
        query = """
            SELECT * FROM team_rankings 
            WHERE season = :season
            ORDER BY overall_rank
        """
        rows = conn.run(query, season=season)
        if rows:
            columns = [col['name'] for col in conn.columns]
            return pd.DataFrame(rows, columns=columns)
        return pd.DataFrame()
    
    def get_team_history(self, team_id: str) -> pd.DataFrame:
        """Get ranking history for a specific team"""
        conn = self.db.get_connection()
        query = """
            SELECT * FROM team_rankings 
            WHERE team_id = :team_id
            ORDER BY season
        """
        rows = conn.run(query, team_id=team_id)
        if rows:
            columns = [col['name'] for col in conn.columns]
            return pd.DataFrame(rows, columns=columns)
        return pd.DataFrame()