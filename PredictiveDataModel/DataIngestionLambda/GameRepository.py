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
        
        # Build query with named parameters for pg8000
        columns_str = ', '.join(columns)
        placeholders = ', '.join([f':{col}' for col in columns])
        
        query = f"""
            INSERT INTO games ({columns_str})
            VALUES ({placeholders})
            ON CONFLICT (game_id)
            DO UPDATE SET
                away_score = EXCLUDED.away_score,
                home_score = EXCLUDED.home_score,
                updated_at = CURRENT_TIMESTAMP
        """
        
        insert_count = 0
        
        for _, row in games_df.iterrows():
            try:
                # Create named parameters dict with proper type conversion
                params = {}
                for col in columns:
                    value = row[col] if pd.notna(row[col]) else None
                    
                    # Convert scores and moneylines to integers
                    if col in ['away_score', 'home_score', 'away_moneyline', 'home_moneyline'] and value is not None:
                        params[col] = int(float(value))
                    # Convert week and season to integers
                    elif col in ['week', 'season'] and value is not None:
                        params[col] = int(value)
                    # Convert spread and total to floats
                    elif col in ['spread_line', 'total_line'] and value is not None:
                        params[col] = float(value)
                    else:
                        params[col] = value
                
                conn.run(query, **params)
                insert_count += 1
            except Exception as e:
                logger.error(f"Error inserting game {row.get('game_id', 'unknown')}: {e}")
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