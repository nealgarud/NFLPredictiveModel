import pandas as pd
import logging
from DatabaseConnection import DatabaseConnection
from DuplicateHandler import DuplicateHandler

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class GameRepository:
    """Repository for games table operations"""
    
    def __init__(self):
        self.db = DatabaseConnection()
        self.duplicate_handler = DuplicateHandler()
    
    def insert_games(self, games_df: pd.DataFrame) -> int:
        """
        Insert games into database with duplicate prevention
        
        Args:
            games_df: DataFrame with game data
            
        Returns:
            Number of games inserted/updated
        """
        conn = self.db.get_connection()
        
        columns = [
            'game_id', 'season', 'game_type', 'week', 'gameday', 'weekday', 'gametime',
            'away_team', 'away_score', 'home_team', 'home_score', 'location',
            'away_moneyline', 'home_moneyline', 'spread_line', 'total_line', 'div_game'
        ]
        
        conflict_columns = ['game_id']
        update_columns = ['away_score', 'home_score']
        
        query = self.duplicate_handler.generate_upsert_query(
            table='games',
            columns=columns,
            conflict_columns=conflict_columns,
            update_columns=update_columns
        )
        
        insert_count = 0
        
        for _, row in games_df.iterrows():
            try:
                values = [row[col] if pd.notna(row[col]) else None for col in columns]
                conn.run(query, *values)
                insert_count += 1
            except Exception as e:
                logger.error(f"Error inserting game {row['game_id']}: {e}")
                continue
        
        return insert_count
    
    def get_games_by_season(self, season: int) -> pd.DataFrame:
        """Get all games for a season"""
        conn = self.db.get_connection()
        query = """
            SELECT * FROM games 
            WHERE season = :season AND game_type = 'REG'
            ORDER BY week, gameday
        """
        rows = conn.run(query, season=season)
        if rows:
            columns = [col['name'] for col in conn.columns]
            return pd.DataFrame(rows, columns=columns)
        return pd.DataFrame()
    
    def get_game_count(self, season: int) -> int:
        """Get count of games for a season"""
        conn = self.db.get_connection()
        result = conn.run("SELECT COUNT(*) FROM games WHERE season = :season", season=season)
        return result[0][0] if result else 0