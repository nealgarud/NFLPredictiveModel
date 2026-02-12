"""
Generate Training Data for XGBoost Model
Pulls all features from Supabase and creates training dataset

This script:
1. Fetches all completed games (2022-2025) from Supabase
2. Extracts features (recent form, divisional ATS, player impact, etc.)
3. Creates target variable (favorite_covered: 1 or 0)
4. Saves to training_data.csv
"""

import os
import sys
import pandas as pd
import numpy as np
import logging
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import database connection
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'PredictionAPILambda'))
from DatabaseConnection import DatabaseConnection

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TrainingDataGenerator:
    """Generate training dataset from Supabase for XGBoost"""
    
    def __init__(self):
        """Initialize database connection"""
        self.db = DatabaseConnection()
        logger.info("✓ Database connection initialized")
    
    def fetch_games_with_features(self, seasons=[2022, 2023, 2024, 2025]):
        """
        Fetch all games with spread data and calculate features
        
        Returns:
            pd.DataFrame: Training data with features and target
        """
        conn = self.db.get_connection()
        
        # Query to get all games with spread data
        query = """
        SELECT 
            g.game_id,
            g.season,
            g.week,
            g.gameday,
            g.home_team,
            g.away_team,
            g.home_score,
            g.away_score,
            s.spread_favorite,
            s.spread_line,
            s.home_moneyline,
            s.away_moneyline,
            s.over_under,
            g.roof,
            g.surface,
            g.game_type
        FROM games g
        LEFT JOIN spreads s ON g.game_id = s.game_id
        WHERE g.season = ANY(:seasons)
            AND g.game_type = 'REG'
            AND g.home_score IS NOT NULL
            AND g.away_score IS NOT NULL
            AND s.spread_line IS NOT NULL
        ORDER BY g.gameday, g.game_id
        """
        
        logger.info(f"Fetching games for seasons: {seasons}")
        data = conn.run(query, seasons=seasons)
        
        if not data:
            logger.error("No games found!")
            return pd.DataFrame()
        
        columns = [
            'game_id', 'season', 'week', 'gameday', 
            'home_team', 'away_team', 'home_score', 'away_score',
            'spread_favorite', 'spread_line', 'home_moneyline', 
            'away_moneyline', 'over_under', 'roof', 'surface', 'game_type'
        ]
        
        df = pd.DataFrame(data, columns=columns)
        logger.info(f"✓ Fetched {len(df)} games with spread data")
        
        return df
    
    def calculate_target(self, df):
        """
        Calculate target variable: favorite_covered (1 or 0)
        
        Args:
            df: DataFrame with game data
            
        Returns:
            DataFrame with target column added
        """
        logger.info("Calculating target variable (favorite_covered)...")
        
        df['favorite_team'] = df.apply(
            lambda row: row['home_team'] if row['spread_favorite'] == 'home' else row['away_team'],
            axis=1
        )
        
        df['underdog_team'] = df.apply(
            lambda row: row['away_team'] if row['spread_favorite'] == 'home' else row['home_team'],
            axis=1
        )
        
        df['favorite_score'] = df.apply(
            lambda row: row['home_score'] if row['spread_favorite'] == 'home' else row['away_score'],
            axis=1
        )
        
        df['underdog_score'] = df.apply(
            lambda row: row['away_score'] if row['spread_favorite'] == 'home' else row['home_score'],
            axis=1
        )
        
        # Favorite covers if they win by MORE than the spread
        df['favorite_margin'] = df['favorite_score'] - df['underdog_score']
        df['favorite_covered'] = (df['favorite_margin'] > df['spread_line']).astype(int)
        
        logger.info(f"✓ Target calculated: {df['favorite_covered'].sum()} favorites covered, {len(df) - df['favorite_covered'].sum()} underdogs covered")
        
        return df
    
    def calculate_rolling_features(self, df):
        """
        Calculate rolling/historical features for each game
        Uses only data BEFORE the current game (no data leakage)
        """
        logger.info("Calculating rolling features...")
        
        df = df.sort_values(['gameday', 'game_id']).reset_index(drop=True)
        
        features_list = []
        
        for idx, game in df.iterrows():
            if idx % 50 == 0:
                logger.info(f"  Processing game {idx}/{len(df)}")
            
            # Get historical games BEFORE this game
            historical = df[df['gameday'] < game['gameday']].copy()
            
            features = self._calculate_game_features(
                game,
                historical,
                game['favorite_team'],
                game['underdog_team']
            )
            
            features_list.append(features)
        
        features_df = pd.DataFrame(features_list)
        logger.info(f"✓ Calculated {len(features_df.columns)} features")
        
        return features_df
    
    def _calculate_game_features(self, game, historical, fav_team, und_team):
        """Calculate all features for a single game"""
        
        features = {
            'game_id': game['game_id'],
            'season': game['season'],
            'week': game['week'],
            'favorite_team': fav_team,
            'underdog_team': und_team,
            'spread_line': game['spread_line']
        }
        
        # Feature 1: Recent Form (Last 5 games win rate)
        fav_recent = self._get_recent_form(historical, fav_team, window=5)
        und_recent = self._get_recent_form(historical, und_team, window=5)
        features['fav_recent_form'] = fav_recent
        features['und_recent_form'] = und_recent
        features['recent_form_diff'] = fav_recent - und_recent
        
        # Feature 2: ATS Performance (Against the Spread)
        fav_ats = self._get_ats_record(historical, fav_team)
        und_ats = self._get_ats_record(historical, und_team)
        features['fav_ats'] = fav_ats
        features['und_ats'] = und_ats
        features['ats_diff'] = fav_ats - und_ats
        
        # Feature 3: Home/Away Performance
        is_fav_home = game['spread_favorite'] == 'home'
        features['fav_is_home'] = 1 if is_fav_home else 0
        features['fav_home_record'] = self._get_home_away_record(historical, fav_team, home=is_fav_home)
        features['und_home_record'] = self._get_home_away_record(historical, und_team, home=not is_fav_home)
        
        # Feature 4: Head-to-Head
        features['h2h_fav_wins'] = self._get_h2h_record(historical, fav_team, und_team)
        
        # Feature 5: Divisional Game
        features['is_divisional'] = self._is_divisional_game(fav_team, und_team)
        
        # Feature 6: Spread Magnitude Category
        spread = abs(game['spread_line'])
        if spread <= 3:
            features['spread_category'] = 0  # Very close
        elif spread <= 7:
            features['spread_category'] = 1  # Close
        elif spread <= 10:
            features['spread_category'] = 2  # Moderate
        else:
            features['spread_category'] = 3  # Large
        
        # Feature 7: Surface & Roof
        features['surface_turf'] = 1 if game.get('surface') == 'turf' else 0
        features['roof_dome'] = 1 if game.get('roof') == 'dome' else 0
        
        # Feature 8: Week number (early/mid/late season)
        features['week_num'] = game['week']
        features['is_late_season'] = 1 if game['week'] >= 14 else 0
        
        return features
    
    def _get_recent_form(self, historical, team, window=5):
        """Calculate win rate in last N games"""
        team_games = historical[
            (historical['home_team'] == team) | (historical['away_team'] == team)
        ].tail(window)
        
        if len(team_games) == 0:
            return 0.5  # Default
        
        wins = 0
        for _, game in team_games.iterrows():
            if game['home_team'] == team:
                wins += 1 if game['home_score'] > game['away_score'] else 0
            else:
                wins += 1 if game['away_score'] > game['home_score'] else 0
        
        return wins / len(team_games)
    
    def _get_ats_record(self, historical, team):
        """Calculate ATS (Against the Spread) win rate"""
        team_games = historical[
            ((historical['favorite_team'] == team) | (historical['underdog_team'] == team)) &
            (historical['spread_line'].notna())
        ]
        
        if len(team_games) == 0:
            return 0.5
        
        covers = team_games['favorite_covered'].sum() if team in team_games['favorite_team'].values else len(team_games) - team_games['favorite_covered'].sum()
        return covers / len(team_games)
    
    def _get_home_away_record(self, historical, team, home=True):
        """Get win rate as home or away team"""
        if home:
            team_games = historical[historical['home_team'] == team]
            if len(team_games) == 0:
                return 0.5
            wins = (team_games['home_score'] > team_games['away_score']).sum()
        else:
            team_games = historical[historical['away_team'] == team]
            if len(team_games) == 0:
                return 0.5
            wins = (team_games['away_score'] > team_games['home_score']).sum()
        
        return wins / len(team_games)
    
    def _get_h2h_record(self, historical, team1, team2):
        """Get head-to-head win rate for team1"""
        h2h_games = historical[
            ((historical['home_team'] == team1) & (historical['away_team'] == team2)) |
            ((historical['home_team'] == team2) & (historical['away_team'] == team1))
        ]
        
        if len(h2h_games) == 0:
            return 0.5
        
        wins = 0
        for _, game in h2h_games.iterrows():
            if game['home_team'] == team1:
                wins += 1 if game['home_score'] > game['away_score'] else 0
            else:
                wins += 1 if game['away_score'] > game['home_score'] else 0
        
        return wins / len(h2h_games)
    
    def _is_divisional_game(self, team1, team2):
        """Check if two teams are in the same division"""
        divisions = {
            'AFC_EAST': ['BUF', 'MIA', 'NE', 'NYJ'],
            'AFC_NORTH': ['BAL', 'CIN', 'CLE', 'PIT'],
            'AFC_SOUTH': ['HOU', 'IND', 'JAX', 'TEN'],
            'AFC_WEST': ['DEN', 'KC', 'LV', 'LAC'],
            'NFC_EAST': ['DAL', 'NYG', 'PHI', 'WAS'],
            'NFC_NORTH': ['CHI', 'DET', 'GB', 'MIN'],
            'NFC_SOUTH': ['ATL', 'CAR', 'NO', 'TB'],
            'NFC_WEST': ['ARI', 'LAR', 'SF', 'SEA']
        }
        
        for teams in divisions.values():
            if team1 in teams and team2 in teams:
                return 1
        return 0
    
    def add_player_impact_features(self, features_df):
        """
        Add player impact features from Supabase (if available)
        This requires running HistoricalGamesBatchProcessor first
        """
        logger.info("Checking for player impact data...")
        
        try:
            conn = self.db.get_connection()
            
            # Check if player_impact table exists
            query = """
            SELECT game_id, home_impact, away_impact, net_advantage
            FROM player_impact
            """
            
            player_data = conn.run(query)
            
            if player_data:
                player_df = pd.DataFrame(player_data, columns=['game_id', 'home_impact', 'away_impact', 'net_advantage'])
                features_df = features_df.merge(player_df, on='game_id', how='left')
                
                # Fill missing with 0 (neutral impact)
                features_df['home_impact'] = features_df['home_impact'].fillna(0)
                features_df['away_impact'] = features_df['away_impact'].fillna(0)
                features_df['net_advantage'] = features_df['net_advantage'].fillna(0)
                
                logger.info(f"✓ Added player impact features for {len(player_df)} games")
            else:
                logger.warning("No player impact data found - run HistoricalGamesBatchProcessor first")
                features_df['home_impact'] = 0
                features_df['away_impact'] = 0
                features_df['net_advantage'] = 0
        
        except Exception as e:
            logger.warning(f"Could not load player impact data: {e}")
            features_df['home_impact'] = 0
            features_df['away_impact'] = 0
            features_df['net_advantage'] = 0
        
        return features_df
    
    def generate_training_data(self, output_file='training_data.csv'):
        """Main method to generate complete training dataset"""
        
        logger.info("="*60)
        logger.info("GENERATING TRAINING DATA FOR XGBOOST")
        logger.info("="*60)
        
        # Step 1: Fetch games
        games_df = self.fetch_games_with_features()
        
        if games_df.empty:
            logger.error("No games found - cannot generate training data")
            return None
        
        # Step 2: Calculate target
        games_df = self.calculate_target(games_df)
        
        # Step 3: Calculate features
        features_df = self.calculate_rolling_features(games_df)
        
        # Step 4: Add player impact (if available)
        features_df = self.add_player_impact_features(features_df)
        
        # Step 5: Merge with target
        final_df = features_df.merge(
            games_df[['game_id', 'favorite_covered']], 
            on='game_id', 
            how='left'
        )
        
        # Step 6: Save
        final_df.to_csv(output_file, index=False)
        logger.info(f"✓ Training data saved to {output_file}")
        logger.info(f"  Shape: {final_df.shape}")
        logger.info(f"  Target distribution: {final_df['favorite_covered'].value_counts().to_dict()}")
        
        # Show summary
        logger.info("\nFeature Summary:")
        logger.info(f"  Total features: {len(final_df.columns) - 1}")  # Exclude target
        logger.info(f"  Total samples: {len(final_df)}")
        logger.info(f"  Missing values: {final_df.isnull().sum().sum()}")
        
        return final_df


if __name__ == "__main__":
    generator = TrainingDataGenerator()
    df = generator.generate_training_data(output_file='training_data.csv')
    
    if df is not None:
        print("\n" + "="*60)
        print("✓ TRAINING DATA READY FOR XGBOOST!")
        print("="*60)
        print(f"\nNext step: Run train_xgboost_model.py")

