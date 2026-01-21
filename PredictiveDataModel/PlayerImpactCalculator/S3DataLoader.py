"""
S3DataLoader - Load historical game data and Madden ratings from S3

Handles:
- Loading historical game data CSVs (2022, 2023, 2024)
- Loading Madden rating CSVs
- Caching loaded data in memory
- Parsing CSV data into pandas DataFrames
"""

import boto3
import pandas as pd
import logging
from io import StringIO
from typing import Dict, Optional, List
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class S3DataLoader:
    """Load NFL data and Madden ratings from S3"""
    
    def __init__(self, bucket_name: str = 'player-data-nfl-predictive-model'):
        """
        Initialize S3 data loader
        
        Args:
            bucket_name: S3 bucket name (default: player-data-nfl-predictive-model)
        """
        self.bucket_name = bucket_name
        self.s3_client = boto3.client('s3')
        
        # Cache for loaded data
        self._madden_cache: Optional[pd.DataFrame] = None
        self._game_data_cache: Dict[int, pd.DataFrame] = {}
        
        logger.info(f"S3DataLoader initialized (bucket: {bucket_name})")
    
    def load_madden_ratings(self, season: int = 2025) -> pd.DataFrame:
        """
        Load Madden ratings CSV from S3
        
        Args:
            season: Year for Madden ratings (e.g., 2025)
            
        Returns:
            pd.DataFrame: Madden ratings with columns [player_id, player_name, overallrating, position, team]
        """
        # Check cache first
        if self._madden_cache is not None:
            logger.info("Using cached Madden ratings")
            return self._madden_cache
        
        try:
            # Try multiple possible file paths for player/Madden data
            possible_keys = [
                f'{season}.csv',  # Files are at bucket root: 2022.csv, 2023.csv, 2024.csv
                f'madden-ratings/madden_{season}.csv',
                f'madden-ratings/{season}.csv',
                f'raw-data/{season}.csv',
                f'madden_{season}.csv'
            ]
            
            for key in possible_keys:
                try:
                    logger.info(f"Attempting to load Madden ratings: s3://{self.bucket_name}/{key}")
                    csv_content = self._read_s3_file(key)
                    
                    # Parse CSV
                    df = pd.read_csv(StringIO(csv_content))
                    
                    # Validate required columns
                    required_columns = ['overallrating']
                    if not all(col in df.columns for col in required_columns):
                        logger.warning(f"Missing required columns in {key}: {df.columns.tolist()}")
                        continue
                    
                    # Standardize column names
                    df = self._standardize_madden_columns(df)
                    
                    logger.info(f"✓ Loaded Madden ratings: {len(df)} players from {key}")
                    self._madden_cache = df
                    return df
                    
                except Exception as e:
                    logger.debug(f"Failed to load {key}: {e}")
                    continue
            
            # If we get here, none of the paths worked
            raise FileNotFoundError(f"Could not find Madden ratings CSV in bucket {self.bucket_name}")
            
        except Exception as e:
            logger.error(f"Error loading Madden ratings: {e}")
            # Return empty DataFrame as fallback
            return pd.DataFrame(columns=['player_id', 'player_name', 'overallrating', 'position', 'team'])
    
    def load_historical_games(self, season: int) -> pd.DataFrame:
        """
        Load historical game data CSV from S3
        
        Args:
            season: Year (e.g., 2022, 2023, 2024)
            
        Returns:
            pd.DataFrame: Historical game data
        """
        # Check cache first
        if season in self._game_data_cache:
            logger.info(f"Using cached game data for {season}")
            return self._game_data_cache[season]
        
        try:
            key = f'raw-data/{season}.csv'
            logger.info(f"Loading game data: s3://{self.bucket_name}/{key}")
            
            csv_content = self._read_s3_file(key)
            df = pd.read_csv(StringIO(csv_content))
            
            logger.info(f"✓ Loaded {len(df)} games from {season}")
            self._game_data_cache[season] = df
            return df
            
        except Exception as e:
            logger.error(f"Error loading game data for {season}: {e}")
            raise
    
    def load_all_historical_games(self, seasons: List[int] = [2022, 2023, 2024]) -> pd.DataFrame:
        """
        Load and combine multiple seasons of historical game data
        
        Args:
            seasons: List of years to load (default: [2022, 2023, 2024])
            
        Returns:
            pd.DataFrame: Combined game data from all seasons
        """
        all_games = []
        
        for season in seasons:
            try:
                df = self.load_historical_games(season)
                df['season'] = season  # Add season column if not present
                all_games.append(df)
                logger.info(f"✓ Loaded {len(df)} games from {season}")
            except Exception as e:
                logger.warning(f"Skipping {season}: {e}")
                continue
        
        if not all_games:
            logger.warning("No historical game data loaded")
            return pd.DataFrame()
        
        # Combine all seasons
        combined_df = pd.concat(all_games, ignore_index=True)
        logger.info(f"✓ Combined {len(combined_df)} total games from {len(all_games)} seasons")
        
        return combined_df
    
    def list_available_madden_files(self) -> List[str]:
        """
        List all Madden CSV files available in S3
        
        Returns:
            List of S3 keys for Madden files
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix='madden'
            )
            
            files = [obj['Key'] for obj in response.get('Contents', []) if obj['Key'].endswith('.csv')]
            logger.info(f"Found {len(files)} Madden CSV files in S3")
            return files
            
        except Exception as e:
            logger.error(f"Error listing Madden files: {e}")
            return []
    
    def list_available_game_data_files(self) -> List[str]:
        """
        List all game data CSV files available in S3
        
        Returns:
            List of S3 keys for game data files
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix='raw-data/'
            )
            
            files = [obj['Key'] for obj in response.get('Contents', []) if obj['Key'].endswith('.csv')]
            logger.info(f"Found {len(files)} game data CSV files in S3")
            return files
            
        except Exception as e:
            logger.error(f"Error listing game data files: {e}")
            return []
    
    def _read_s3_file(self, key: str) -> str:
        """
        Read text file content from S3
        
        Args:
            key: S3 object key
            
        Returns:
            str: File content
        """
        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
        content = response['Body'].read().decode('utf-8')
        return content
    
    def _standardize_madden_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Standardize Madden DataFrame column names
        
        Args:
            df: Raw Madden DataFrame
            
        Returns:
            pd.DataFrame: Standardized DataFrame
        """
        # Map common variations to standard names
        column_mapping = {
            'Overall': 'overallrating',
            'overall': 'overallrating',
            'OVR': 'overallrating',
            'rating': 'overallrating',
            'name': 'player_name',
            'Name': 'player_name',
            'full_name': 'player_name',
            'Position': 'position',
            'pos': 'position',
            'Team': 'team',
            'team_abbr': 'team',
            'player_uuid': 'player_id',
            'uuid': 'player_id',
            'id': 'player_id'
        }
        
        # Rename columns if they match known variations
        df = df.rename(columns=column_mapping)
        
        # Add missing columns with defaults
        if 'player_id' not in df.columns and 'player_name' in df.columns:
            # Generate player_id from name if not present
            df['player_id'] = df['player_name'].str.lower().str.replace(' ', '_')
        
        if 'player_name' not in df.columns:
            df['player_name'] = 'Unknown'
        
        if 'position' not in df.columns:
            df['position'] = 'UNKNOWN'
        
        if 'team' not in df.columns:
            df['team'] = 'UNKNOWN'
        
        return df
    
    def clear_cache(self):
        """Clear all cached data"""
        self._madden_cache = None
        self._game_data_cache.clear()
        logger.info("Cache cleared")


# Test the loader
if __name__ == "__main__":
    print("S3DataLoader - Testing...")
    
    try:
        loader = S3DataLoader()
        print("✓ Loader initialized")
        
        # List available files
        print("\nListing Madden files:")
        madden_files = loader.list_available_madden_files()
        for file in madden_files[:5]:  # Show first 5
            print(f"  - {file}")
        
        print("\nListing game data files:")
        game_files = loader.list_available_game_data_files()
        for file in game_files:
            print(f"  - {file}")
        
        # Try loading Madden ratings
        print("\nLoading Madden ratings...")
        madden_df = loader.load_madden_ratings(2025)
        print(f"✓ Loaded {len(madden_df)} player ratings")
        print(f"Columns: {madden_df.columns.tolist()}")
        
        # Try loading historical games
        print("\nLoading 2024 game data...")
        games_df = loader.load_historical_games(2024)
        print(f"✓ Loaded {len(games_df)} games")
        print(f"Columns: {games_df.columns.tolist()}")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()

