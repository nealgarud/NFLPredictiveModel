"""
NFL Spread Prediction - Training Data Preparation Script
Generates feature matrix from historical game data for XGBoost model training

Author: Neal
Date: 2026-01-21
"""

import sys
import os
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'PredictiveDataModel', 'DataIngestionLambda'))
from DatabaseConnection import DatabaseConnection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TrainingDataPreparator:
    """Prepare training data for NFL spread prediction model"""
    
    def __init__(self):
        """Initialize with database connection"""
        self.db = DatabaseConnection()
        self.conn = self.db.get_connection()
        logger.info("✅ Database connection established")
        
    def prepare_training_data(
        self, 
        seasons: List[int] = [2024, 2025],
        output_file: str = 'training_data.csv'
    ) -> pd.DataFrame:
        """
        Main method to prepare complete training dataset
        
        Args:
            seasons: List of seasons to include (default: [2024, 2025])
            output_file: Path to save CSV output
            
        Returns:
            DataFrame with all features and target variable
        """
        logger.info(f"🏈 Starting training data preparation for seasons: {seasons}")
        
        # Step 1: Query all completed games
        games = self._query_completed_games(seasons)
        logger.info(f"✅ Retrieved {len(games)} completed games")
        
        if len(games) == 0:
            logger.warning("⚠️ No games found. Check database connection and query filters.")
            return pd.DataFrame()
        
        # Step 2: Calculate features for each game
        training_data = []
        total_games = len(games)
        
        for idx, game in enumerate(games, 1):
            if idx % 50 == 0 or idx == total_games:
                logger.info(f"Processing game {idx}/{total_games}...")
            
            try:
                features = self._calculate_game_features(game, seasons)
                target = self._calculate_target(game)
                
                # Combine features and target
                row = {
                    'game_id': game['game_id'],
                    'season': game['season'],
                    'week': game['week'],
                    'gameday': game['gameday'],
                    'home_team': game['home_team'],
                    'away_team': game['away_team'],
                    'spread_line': game['spread_line'],
                    **features,
                    'target_favorite_covered': target
                }
                
                training_data.append(row)
                
            except Exception as e:
                logger.warning(f"⚠️ Error processing game {game['game_id']}: {str(e)}")
                continue
        
        # Step 3: Create DataFrame
        df = pd.DataFrame(training_data)
        logger.info(f"✅ Created DataFrame with {len(df)} rows and {len(df.columns)} columns")
        
        # Step 4: Handle missing values
        initial_count = len(df)
        df = self._handle_missing_values(df)
        final_count = len(df)
        
        if initial_count > final_count:
            logger.info(f"🧹 Filtered out {initial_count - final_count} rows with missing features")
        
        # Step 5: Save to CSV
        df.to_csv(output_file, index=False)
        logger.info(f"💾 Training data saved to: {output_file}")
        
        # Step 6: Print summary statistics
        self._print_summary(df)
        
        return df
    
    def _query_completed_games(self, seasons: List[int]) -> List[Dict]:
        """
        Query all completed regular season games with required data
        
        Args:
            seasons: List of seasons to query
            
        Returns:
            List of game dictionaries
        """
        query = """
        SELECT 
            game_id,
            season,
            week,
            gameday,
            home_team,
            away_team,
            home_score,
            away_score,
            spread_line,
            div_game
        FROM games
        WHERE season = ANY(:seasons)
            AND game_type = 'REG'
            AND home_score IS NOT NULL
            AND away_score IS NOT NULL
            AND spread_line IS NOT NULL
        ORDER BY gameday ASC, game_id ASC
        """
        
        result = self.conn.run(query, seasons=seasons)
        
        # Convert to list of dictionaries
        columns = ['game_id', 'season', 'week', 'gameday', 'home_team', 'away_team',
                   'home_score', 'away_score', 'spread_line', 'div_game']
        
        games = []
        for row in result:
            game_dict = dict(zip(columns, row))
            games.append(game_dict)
        
        return games
    
    def _calculate_game_features(self, game: Dict, seasons: List[int]) -> Dict:
        """
        Calculate all features for a single game
        
        CRITICAL: Only use data from BEFORE this game (prevent data leakage)
        
        Args:
            game: Game dictionary with game_id, teams, scores, etc.
            seasons: Seasons to consider for historical data
            
        Returns:
            Dictionary with all feature values
        """
        # Determine favored and underdog teams
        spread = game['spread_line']
        
        if spread > 0:
            # Home team is favored
            favored_team = game['home_team']
            underdog_team = game['away_team']
            favored_home = True
        else:
            # Away team is favored
            favored_team = game['away_team']
            underdog_team = game['home_team']
            favored_home = False
        
        spread_abs = abs(spread)
        
        features = {
            'favored_team': favored_team,
            'underdog_team': underdog_team,
            'favored_home': favored_home,
            'spread_magnitude': self._categorize_spread(spread_abs),
        }
        
        # TEAM FORM FEATURES
        form = self._calc_recent_form(
            favored_team, underdog_team, game['gameday'], seasons
        )
        features['fav_recent_form'] = form['favored_rate']
        features['und_recent_form'] = form['underdog_rate']
        
        # SITUATIONAL FEATURES
        features['is_divisional'] = bool(game.get('div_game', False))
        
        div_perf = self._calc_divisional_ats(
            favored_team, underdog_team, game['gameday'], seasons
        )
        features['fav_div_ats'] = div_perf['favored_rate']
        features['und_div_ats'] = div_perf['underdog_rate']
        
        # CONTEXTUAL FEATURES
        bye_week = self._calc_bye_week_status(
            favored_team, underdog_team, game['gameday'], seasons
        )
        features['fav_bye_week'] = bye_week['favored_coming_off_bye']
        features['und_bye_week'] = bye_week['underdog_coming_off_bye']
        
        features['is_prime_time'] = self._is_prime_time_game(game['gameday'])
        
        # PERFORMANCE FEATURES
        close_game_perf = self._calc_close_game_performance(
            favored_team, game['gameday'], seasons
        )
        features['fav_close_game_perf'] = close_game_perf
        
        after_loss_perf = self._calc_after_loss_performance(
            favored_team, game['gameday'], seasons
        )
        features['fav_after_loss_perf'] = after_loss_perf
        
        # CORE FEATURES (from SpreadPredictionCalculator logic)
        spread_range = self._get_spread_range(spread_abs)
        
        situational_ats = self._calc_situational_ats(
            favored_team, underdog_team, favored_home, 
            spread_range, game['gameday'], seasons
        )
        features['fav_sit_ats'] = situational_ats['favored_rate']
        features['und_sit_ats'] = situational_ats['underdog_rate']
        
        overall_ats = self._calc_overall_ats_historical(
            favored_team, underdog_team, game['gameday'], seasons
        )
        features['fav_overall_ats'] = overall_ats['favored_rate']
        features['und_overall_ats'] = overall_ats['underdog_rate']
        
        home_away = self._calc_home_away_performance(
            favored_team, underdog_team, favored_home, game['gameday'], seasons
        )
        features['fav_home_away_wr'] = home_away['favored_rate']
        features['und_home_away_wr'] = home_away['underdog_rate']
        
        # TODO: PLAYER DATA FEATURES (to be added when data is deployed)
        # features['fav_qb_rating'] = self._get_qb_rating(favored_team, game['gameday'])
        # features['und_qb_rating'] = self._get_qb_rating(underdog_team, game['gameday'])
        # features['fav_key_injuries'] = self._count_key_injuries(favored_team, game['gameday'])
        # features['und_key_injuries'] = self._count_key_injuries(underdog_team, game['gameday'])
        
        return features
    
    def _calculate_target(self, game: Dict) -> int:
        """
        Calculate target variable: Did the favorite cover the spread?
        
        Args:
            game: Game dictionary
            
        Returns:
            1 if favorite covered, 0 if not
        """
        spread = game['spread_line']
        home_score = game['home_score']
        away_score = game['away_score']
        
        if spread > 0:
            # Home team is favored
            margin = home_score - away_score
            covered = 1 if margin > spread else 0
        else:
            # Away team is favored
            margin = away_score - home_score
            covered = 1 if margin > abs(spread) else 0
        
        return covered
    
    # ============================================================================
    # FEATURE CALCULATION HELPERS
    # ============================================================================
    
    def _categorize_spread(self, spread: float) -> int:
        """Categorize spread magnitude: 0=0-3, 1=3-7, 2=7-10, 3=10+"""
        if spread < 3:
            return 0
        elif spread < 7:
            return 1
        elif spread < 10:
            return 2
        else:
            return 3
    
    def _get_spread_range(self, spread: float) -> str:
        """Get spread range string for situational ATS calculation"""
        if spread <= 2:
            return "0-2"
        elif spread <= 4:
            return "2-4"
        elif spread <= 7:
            return "4-7"
        elif spread <= 10:
            return "7-10"
        else:
            return "10+"
    
    def _is_prime_time_game(self, gameday) -> bool:
        """Check if game is prime time (TNF/SNF/MNF)"""
        gameday_dt = pd.to_datetime(gameday)
        day_of_week = gameday_dt.day_name()
        hour = gameday_dt.hour
        
        # Thursday Night Football
        if day_of_week == 'Thursday':
            return True
        # Sunday Night Football (8pm ET = 20:00 UTC adjustment)
        if day_of_week == 'Sunday' and hour >= 20:
            return True
        # Monday Night Football
        if day_of_week == 'Monday':
            return True
        
        return False
    
    def _calc_recent_form(
        self, 
        favored: str, 
        underdog: str, 
        current_gameday,
        seasons: List[int]
    ) -> Dict:
        """
        Calculate last 5 games win rate (rolling window)
        Only uses games BEFORE current_gameday to prevent data leakage
        """
        query = """
        SELECT 
            gameday,
            home_team,
            away_team,
            home_score,
            away_score
        FROM games
        WHERE season = ANY(:seasons)
            AND (home_team IN (:fav, :und) OR away_team IN (:fav, :und))
            AND game_type = 'REG'
            AND home_score IS NOT NULL
            AND gameday < :current_gameday
        ORDER BY gameday ASC
        """
        
        data = self.conn.run(
            query, 
            seasons=seasons, 
            fav=favored, 
            und=underdog,
            current_gameday=current_gameday
        )
        
        if not data:
            return {'favored_rate': 0.5, 'underdog_rate': 0.5}
        
        columns = ['gameday', 'home_team', 'away_team', 'home_score', 'away_score']
        games_df = pd.DataFrame(data, columns=columns)
        
        # Create home perspective
        home_games = games_df.copy()
        home_games['team'] = games_df['home_team']
        home_games['won'] = games_df['home_score'] > games_df['away_score']
        
        # Create away perspective
        away_games = games_df.copy()
        away_games['team'] = games_df['away_team']
        away_games['won'] = games_df['away_score'] > games_df['home_score']
        
        # Combine and sort
        all_games = pd.concat([home_games, away_games], ignore_index=True)
        all_games = all_games.sort_values(by=['team', 'gameday'])
        
        # Calculate rolling 5-game win rate (using last 5 games, not including current)
        all_games['wins_last_5'] = (
            all_games
            .groupby('team')['won']
            .transform(lambda x: x.rolling(5, min_periods=1).sum().shift(1))
        )
        all_games['games_last_5'] = (
            all_games
            .groupby('team')['won']
            .transform(lambda x: x.rolling(5, min_periods=1).count().shift(1))
        )
        all_games['form_rate'] = all_games['wins_last_5'] / all_games['games_last_5']
        
        # Get most recent form for each team
        latest_form = all_games.groupby('team').tail(1)
        
        fav_form = latest_form[latest_form['team'] == favored]
        und_form = latest_form[latest_form['team'] == underdog]
        
        fav_rate = float(fav_form['form_rate'].iloc[0]) if not fav_form.empty and not pd.isna(fav_form['form_rate'].iloc[0]) else 0.5
        und_rate = float(und_form['form_rate'].iloc[0]) if not und_form.empty and not pd.isna(und_form['form_rate'].iloc[0]) else 0.5
        
        return {
            'favored_rate': fav_rate,
            'underdog_rate': und_rate
        }
    
    def _calc_divisional_ats(
        self,
        favored: str,
        underdog: str,
        current_gameday,
        seasons: List[int]
    ) -> Dict:
        """Calculate ATS performance in division games"""
        # Favored team divisional ATS
        fav_query = """
        SELECT 
            div_game,
            CASE 
                WHEN (home_team = :team AND spread_line > 0 AND (home_score - away_score) > spread_line)
                     OR (away_team = :team AND spread_line < 0 AND (away_score - home_score) > ABS(spread_line))
                THEN 1
                WHEN (home_team = :team AND spread_line > 0 AND (home_score - away_score) <= spread_line)
                     OR (away_team = :team AND spread_line < 0 AND (away_score - home_score) <= ABS(spread_line))
                THEN 0
                ELSE NULL
            END as ats_covered
        FROM games
        WHERE (home_team = :team OR away_team = :team)
            AND season = ANY(:seasons)
            AND game_type = 'REG'
            AND home_score IS NOT NULL
            AND spread_line IS NOT NULL
            AND gameday < :current_gameday
        """
        
        fav_data = self.conn.run(
            fav_query, 
            team=favored, 
            seasons=seasons,
            current_gameday=current_gameday
        )
        
        und_data = self.conn.run(
            fav_query, 
            team=underdog, 
            seasons=seasons,
            current_gameday=current_gameday
        )
        
        # Process favored team
        if fav_data:
            fav_df = pd.DataFrame(fav_data, columns=['div_game', 'ats_covered'])
            fav_df = fav_df[fav_df['ats_covered'].notna()]
            div_games = fav_df[fav_df['div_game'] == True]
            fav_div_rate = div_games['ats_covered'].mean() if len(div_games) > 0 else 0.5
        else:
            fav_div_rate = 0.5
        
        # Process underdog team
        if und_data:
            und_df = pd.DataFrame(und_data, columns=['div_game', 'ats_covered'])
            und_df = und_df[und_df['ats_covered'].notna()]
            div_games = und_df[und_df['div_game'] == True]
            und_div_rate = div_games['ats_covered'].mean() if len(div_games) > 0 else 0.5
        else:
            und_div_rate = 0.5
        
        return {
            'favored_rate': float(fav_div_rate),
            'underdog_rate': float(und_div_rate)
        }
    
    def _calc_bye_week_status(
        self,
        favored: str,
        underdog: str,
        current_gameday,
        seasons: List[int]
    ) -> Dict:
        """Check if teams are coming off bye week (14+ days rest)"""
        query = """
        SELECT 
            gameday
        FROM games
        WHERE (home_team = :team OR away_team = :team)
            AND season = ANY(:seasons)
            AND game_type = 'REG'
            AND home_score IS NOT NULL
            AND gameday < :current_gameday
        ORDER BY gameday DESC
        LIMIT 1
        """
        
        # Check favored team
        fav_result = self.conn.run(
            query, 
            team=favored, 
            seasons=seasons,
            current_gameday=current_gameday
        )
        
        if fav_result and fav_result[0][0]:
            last_game = pd.to_datetime(fav_result[0][0])
            current = pd.to_datetime(current_gameday)
            days_rest = (current - last_game).days
            fav_bye = days_rest >= 14
        else:
            fav_bye = False
        
        # Check underdog team
        und_result = self.conn.run(
            query, 
            team=underdog, 
            seasons=seasons,
            current_gameday=current_gameday
        )
        
        if und_result and und_result[0][0]:
            last_game = pd.to_datetime(und_result[0][0])
            current = pd.to_datetime(current_gameday)
            days_rest = (current - last_game).days
            und_bye = days_rest >= 14
        else:
            und_bye = False
        
        return {
            'favored_coming_off_bye': fav_bye,
            'underdog_coming_off_bye': und_bye
        }
    
    def _calc_close_game_performance(
        self,
        team: str,
        current_gameday,
        seasons: List[int]
    ) -> float:
        """Calculate ATS performance in close games (spread < 3)"""
        query = """
        SELECT 
            spread_line,
            CASE 
                WHEN home_team = :team AND spread_line > 0 
                THEN CASE WHEN (home_score - away_score) > spread_line THEN 1 ELSE 0 END
                WHEN away_team = :team AND spread_line < 0
                THEN CASE WHEN (away_score - home_score) > ABS(spread_line) THEN 1 ELSE 0 END
                ELSE NULL
            END as ats_covered
        FROM games
        WHERE (home_team = :team OR away_team = :team)
            AND season = ANY(:seasons)
            AND game_type = 'REG'
            AND home_score IS NOT NULL
            AND spread_line IS NOT NULL
            AND ABS(spread_line) < 3
            AND gameday < :current_gameday
        """
        
        data = self.conn.run(
            query, 
            team=team, 
            seasons=seasons,
            current_gameday=current_gameday
        )
        
        if not data:
            return 0.5
        
        df = pd.DataFrame(data, columns=['spread_line', 'ats_covered'])
        df = df[df['ats_covered'].notna()]
        
        if len(df) == 0:
            return 0.5
        
        return float(df['ats_covered'].mean())
    
    def _calc_after_loss_performance(
        self,
        team: str,
        current_gameday,
        seasons: List[int]
    ) -> float:
        """Calculate ATS performance in games after a loss"""
        query = """
        SELECT 
            gameday,
            home_team,
            away_team,
            home_score,
            away_score,
            spread_line
        FROM games
        WHERE (home_team = :team OR away_team = :team)
            AND season = ANY(:seasons)
            AND game_type = 'REG'
            AND home_score IS NOT NULL
            AND spread_line IS NOT NULL
            AND gameday < :current_gameday
        ORDER BY gameday ASC
        """
        
        data = self.conn.run(
            query, 
            team=team, 
            seasons=seasons,
            current_gameday=current_gameday
        )
        
        if not data:
            return 0.5
        
        columns = ['gameday', 'home_team', 'away_team', 'home_score', 'away_score', 'spread_line']
        df = pd.DataFrame(data, columns=columns)
        
        # Determine if team won and covered spread
        df['was_home'] = df['home_team'] == team
        df['won'] = np.where(
            df['was_home'],
            df['home_score'] > df['away_score'],
            df['away_score'] > df['home_score']
        )
        
        df['margin'] = np.where(
            df['was_home'],
            df['home_score'] - df['away_score'],
            df['away_score'] - df['home_score']
        )
        
        df['team_spread'] = np.where(df['was_home'], df['spread_line'], -df['spread_line'])
        df['ats_covered'] = df['margin'] > df['team_spread']
        
        # Identify games after losses
        df['prev_won'] = df['won'].shift(1)
        df['is_after_loss'] = df['prev_won'] == False
        
        after_loss_games = df[df['is_after_loss'] == True]
        
        if len(after_loss_games) == 0:
            return 0.5
        
        return float(after_loss_games['ats_covered'].mean())
    
    def _calc_situational_ats(
        self,
        favored: str,
        underdog: str,
        favored_home: bool,
        spread_range: str,
        current_gameday,
        seasons: List[int]
    ) -> Dict:
        """Calculate situational ATS (spread range + location)"""
        # Parse spread range
        if spread_range == "10+":
            min_spread, max_spread = 10, 100
        else:
            parts = spread_range.split('-')
            min_spread = int(float(parts[0]))
            max_spread = int(float(parts[1]))
        
        # Favored team query
        favored_location = "home" if favored_home else "away"
        
        if favored_location == "home":
            favored_query = """
            SELECT 
                COUNT(*) as total_games,
                SUM(CASE 
                    WHEN spread_line > 0 AND (home_score - away_score) > spread_line THEN 1
                    ELSE 0 
                END) as ats_wins
            FROM games
            WHERE season = ANY(:seasons)
                AND home_team = :team
                AND spread_line BETWEEN :min_spread AND :max_spread
                AND game_type = 'REG'
                AND home_score IS NOT NULL
                AND gameday < :current_gameday
            """
        else:
            favored_query = """
            SELECT 
                COUNT(*) as total_games,
                SUM(CASE 
                    WHEN spread_line < 0 AND (away_score - home_score) > ABS(spread_line) THEN 1
                    ELSE 0 
                END) as ats_wins
            FROM games
            WHERE season = ANY(:seasons)
                AND away_team = :team
                AND spread_line BETWEEN (:min_spread * -1) AND (:max_spread * -1)
                AND game_type = 'REG'
                AND home_score IS NOT NULL
                AND gameday < :current_gameday
            """
        
        fav_result = self.conn.run(
            favored_query,
            seasons=seasons,
            team=favored,
            min_spread=min_spread,
            max_spread=max_spread,
            current_gameday=current_gameday
        )
        
        # Underdog team query
        underdog_location = "away" if favored_home else "home"
        
        if underdog_location == "home":
            underdog_query = """
            SELECT 
                COUNT(*) as total_games,
                SUM(CASE 
                    WHEN spread_line < 0 AND (home_score - away_score) > spread_line THEN 1
                    ELSE 0 
                END) as ats_wins
            FROM games
            WHERE season = ANY(:seasons)
                AND home_team = :team
                AND spread_line BETWEEN (:min_spread * -1) AND (:max_spread * -1)
                AND game_type = 'REG'
                AND home_score IS NOT NULL
                AND gameday < :current_gameday
            """
        else:
            underdog_query = """
            SELECT 
                COUNT(*) as total_games,
                SUM(CASE 
                    WHEN spread_line > 0 AND (away_score - home_score) > -spread_line THEN 1
                    ELSE 0 
                END) as ats_wins
            FROM games
            WHERE season = ANY(:seasons)
                AND away_team = :team
                AND spread_line BETWEEN :min_spread AND :max_spread
                AND game_type = 'REG'
                AND home_score IS NOT NULL
                AND gameday < :current_gameday
            """
        
        und_result = self.conn.run(
            underdog_query,
            seasons=seasons,
            team=underdog,
            min_spread=min_spread,
            max_spread=max_spread,
            current_gameday=current_gameday
        )
        
        # Calculate rates
        fav_total = fav_result[0][0] if fav_result else 0
        fav_wins = fav_result[0][1] if fav_result else 0
        fav_rate = fav_wins / fav_total if fav_total > 0 else 0.5
        
        und_total = und_result[0][0] if und_result else 0
        und_wins = und_result[0][1] if und_result else 0
        und_rate = und_wins / und_total if und_total > 0 else 0.5
        
        return {
            'favored_rate': float(fav_rate),
            'underdog_rate': float(und_rate)
        }
    
    def _calc_overall_ats_historical(
        self,
        favored: str,
        underdog: str,
        current_gameday,
        seasons: List[int]
    ) -> Dict:
        """
        Calculate overall ATS from game-by-game data (not team_rankings table)
        This ensures we don't use future data
        """
        query = """
        SELECT 
            CASE 
                WHEN (home_team = :team AND spread_line > 0 AND (home_score - away_score) > spread_line)
                     OR (away_team = :team AND spread_line < 0 AND (away_score - home_score) > ABS(spread_line))
                THEN 1
                WHEN (home_team = :team AND spread_line > 0 AND (home_score - away_score) <= spread_line)
                     OR (away_team = :team AND spread_line < 0 AND (away_score - home_score) <= ABS(spread_line))
                THEN 0
                ELSE NULL
            END as ats_covered
        FROM games
        WHERE (home_team = :team OR away_team = :team)
            AND season = ANY(:seasons)
            AND game_type = 'REG'
            AND home_score IS NOT NULL
            AND spread_line IS NOT NULL
            AND gameday < :current_gameday
        """
        
        fav_data = self.conn.run(
            query, 
            team=favored, 
            seasons=seasons,
            current_gameday=current_gameday
        )
        
        und_data = self.conn.run(
            query, 
            team=underdog, 
            seasons=seasons,
            current_gameday=current_gameday
        )
        
        # Process favored team
        if fav_data:
            fav_df = pd.DataFrame(fav_data, columns=['ats_covered'])
            fav_df = fav_df[fav_df['ats_covered'].notna()]
            fav_rate = fav_df['ats_covered'].mean() if len(fav_df) > 0 else 0.5
        else:
            fav_rate = 0.5
        
        # Process underdog team
        if und_data:
            und_df = pd.DataFrame(und_data, columns=['ats_covered'])
            und_df = und_df[und_df['ats_covered'].notna()]
            und_rate = und_df['ats_covered'].mean() if len(und_df) > 0 else 0.5
        else:
            und_rate = 0.5
        
        return {
            'favored_rate': float(fav_rate),
            'underdog_rate': float(und_rate)
        }
    
    def _calc_home_away_performance(
        self,
        favored: str,
        underdog: str,
        favored_home: bool,
        current_gameday,
        seasons: List[int]
    ) -> Dict:
        """Calculate home/away win rate performance"""
        # Favored team
        fav_location = "home" if favored_home else "away"
        
        if fav_location == "home":
            fav_query = """
            SELECT 
                COUNT(*) as games,
                SUM(CASE WHEN home_score > away_score THEN 1 ELSE 0 END) as wins
            FROM games
            WHERE home_team = :team
                AND season = ANY(:seasons)
                AND game_type = 'REG'
                AND home_score IS NOT NULL
                AND gameday < :current_gameday
            """
        else:
            fav_query = """
            SELECT 
                COUNT(*) as games,
                SUM(CASE WHEN away_score > home_score THEN 1 ELSE 0 END) as wins
            FROM games
            WHERE away_team = :team
                AND season = ANY(:seasons)
                AND game_type = 'REG'
                AND home_score IS NOT NULL
                AND gameday < :current_gameday
            """
        
        fav_result = self.conn.run(
            fav_query, 
            team=favored, 
            seasons=seasons,
            current_gameday=current_gameday
        )
        
        fav_games = fav_result[0][0] if fav_result else 0
        fav_wins = fav_result[0][1] if fav_result else 0
        fav_rate = fav_wins / fav_games if fav_games > 0 else 0.5
        
        # Underdog team
        und_location = "away" if favored_home else "home"
        
        if und_location == "home":
            und_query = """
            SELECT 
                COUNT(*) as games,
                SUM(CASE WHEN home_score > away_score THEN 1 ELSE 0 END) as wins
            FROM games
            WHERE home_team = :team
                AND season = ANY(:seasons)
                AND game_type = 'REG'
                AND home_score IS NOT NULL
                AND gameday < :current_gameday
            """
        else:
            und_query = """
            SELECT 
                COUNT(*) as games,
                SUM(CASE WHEN away_score > home_score THEN 1 ELSE 0 END) as wins
            FROM games
            WHERE away_team = :team
                AND season = ANY(:seasons)
                AND game_type = 'REG'
                AND home_score IS NOT NULL
                AND gameday < :current_gameday
            """
        
        und_result = self.conn.run(
            und_query, 
            team=underdog, 
            seasons=seasons,
            current_gameday=current_gameday
        )
        
        und_games = und_result[0][0] if und_result else 0
        und_wins = und_result[0][1] if und_result else 0
        und_rate = und_wins / und_games if und_games > 0 else 0.5
        
        return {
            'favored_rate': float(fav_rate),
            'underdog_rate': float(und_rate)
        }
    
    # ============================================================================
    # DATA QUALITY & SUMMARY
    # ============================================================================
    
    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Handle missing values in the dataset
        Strategy: Drop rows with any NaN in feature columns
        """
        initial_count = len(df)
        
        # Identify feature columns (exclude metadata columns)
        metadata_cols = ['game_id', 'season', 'week', 'gameday', 'home_team', 
                         'away_team', 'spread_line', 'favored_team', 'underdog_team']
        feature_cols = [col for col in df.columns if col not in metadata_cols]
        
        # Check for missing values
        missing_counts = df[feature_cols].isnull().sum()
        if missing_counts.sum() > 0:
            logger.info(f"📊 Missing value counts:")
            for col, count in missing_counts[missing_counts > 0].items():
                logger.info(f"  {col}: {count}")
        
        # Drop rows with any missing feature values
        df_clean = df.dropna(subset=feature_cols)
        
        dropped_count = initial_count - len(df_clean)
        if dropped_count > 0:
            logger.info(f"Dropped {dropped_count} rows with missing values ({dropped_count/initial_count*100:.1f}%)")
        
        return df_clean
    
    def _print_summary(self, df: pd.DataFrame):
        """Print summary statistics of the training data"""
        logger.info("\n" + "="*80)
        logger.info("📊 TRAINING DATA SUMMARY")
        logger.info("="*80)
        
        logger.info(f"\n📈 Dataset Size:")
        logger.info(f"  Total games: {len(df)}")
        logger.info(f"  Total features: {len(df.columns) - 8}")  # Exclude metadata cols
        
        logger.info(f"\n⚖️ Target Distribution:")
        target_counts = df['target_favorite_covered'].value_counts()
        logger.info(f"  Favorite covered (1): {target_counts.get(1, 0)} ({target_counts.get(1, 0)/len(df)*100:.1f}%)")
        logger.info(f"  Favorite didn't cover (0): {target_counts.get(0, 0)} ({target_counts.get(0, 0)/len(df)*100:.1f}%)")
        
        logger.info(f"\n📅 Season Distribution:")
        for season, count in df['season'].value_counts().sort_index().items():
            logger.info(f"  {season}: {count} games")
        
        logger.info(f"\n📊 Spread Distribution:")
        logger.info(f"  Mean: {df['spread_line'].abs().mean():.2f}")
        logger.info(f"  Median: {df['spread_line'].abs().median():.2f}")
        logger.info(f"  Min: {df['spread_line'].abs().min():.2f}")
        logger.info(f"  Max: {df['spread_line'].abs().max():.2f}")
        
        logger.info(f"\n✅ Data preparation complete!")
        logger.info("="*80 + "\n")


def main():
    """Main execution function"""
    try:
        # Initialize preparator
        preparator = TrainingDataPreparator()
        
        # Prepare training data for 2024 and 2025 seasons
        df = preparator.prepare_training_data(
            seasons=[2024, 2025],
            output_file='training_data.csv'
        )
        
        logger.info(f"✅ Success! Training data saved with {len(df)} samples")
        
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
