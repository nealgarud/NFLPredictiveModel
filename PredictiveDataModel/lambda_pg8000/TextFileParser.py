import pandas as pd
from io import StringIO
from typing import List, Dict

class TextFileParser:
    """Parse .txt file with pipe-delimited or comma-delimited data"""
    
    def __init__(self, delimiter=','):
        self.delimiter = delimiter
        
    def parse(self, text_content: str) -> pd.DataFrame:
        """
        Parse text content into DataFrame
        
        Args:
            text_content: Raw text from .txt file
            
        Returns:
            DataFrame with parsed game data
        """
        # Define column names based on your structure
        columns = [
            'game_id', 'season', 'game_type', 'week', 'gameday', 'weekday', 'gametime',
            'away_team', 'away_score', 'home_team', 'home_score', 'location',
            'col12', 'col13', 'col14', 'old_game_id', 'col16', 'col17',
            'alt_game_id', 'col19', 'espn_game_id', 'venue_id',
            'away_rest', 'home_rest',
            'away_moneyline', 'home_moneyline', 'spread_line',
            'spread_odds_away', 'spread_odds_home',
            'total_line', 'total_odds_over', 'total_odds_under',
            'div_game', 'roof', 'surface', 'temp', 'wind',
            'away_qb_id', 'home_qb_id', 'away_qb_name', 'home_qb_name',
            'away_coach', 'home_coach', 'col43', 'col44', 'stadium_name'
        ]
        
        # Parse with pandas
        df = pd.read_csv(
            StringIO(text_content), 
            names=columns, 
            header=None,
            delimiter=self.delimiter
        )
        
        # Keep only what we need
        keep_cols = [
            'game_id', 'season', 'game_type', 'week', 'gameday', 'weekday', 'gametime',
            'away_team', 'away_score', 'home_team', 'home_score', 'location',
            'away_moneyline', 'home_moneyline', 'spread_line', 'total_line', 'div_game'
        ]
        
        df = df[keep_cols]
        
        # Data type conversions
        df = self._convert_types(df)
        
        # Validate and filter
        df = self._validate(df)
        
        return df
    
    def _convert_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert columns to proper data types"""
        df['season'] = df['season'].astype(int)
        df['week'] = df['week'].astype(int)
        df['away_score'] = pd.to_numeric(df['away_score'], errors='coerce')
        df['home_score'] = pd.to_numeric(df['home_score'], errors='coerce')
        df['away_moneyline'] = pd.to_numeric(df['away_moneyline'], errors='coerce')
        df['home_moneyline'] = pd.to_numeric(df['home_moneyline'], errors='coerce')
        df['spread_line'] = pd.to_numeric(df['spread_line'], errors='coerce')
        df['total_line'] = pd.to_numeric(df['total_line'], errors='coerce')
        df['div_game'] = df['div_game'].astype(int).astype(bool)
        
        return df
    
    def _validate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate data and filter out invalid rows"""
        # Only completed games
        df = df[df['away_score'].notna() & df['home_score'].notna()]
        
        # Only seasons we care about
        df = df[df['season'].isin([2022, 2023, 2024, 2025])]
        
        # Only regular season for now
        df = df[df['game_type'] == 'REG']
        
        return df