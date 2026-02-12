"""
XGBoost Prediction Lambda - Replaces SpreadPredictionCalculator
Uses trained ML model instead of manual weights

This Lambda:
1. Receives game matchup (team_a, team_b, spread_line)
2. Extracts features from Supabase
3. Runs XGBoost model prediction
4. Returns probability that favorite covers spread
"""

import json
import os
import sys
import logging
import joblib
import pandas as pd
import numpy as np
from typing import Dict, Any

# Add paths
sys.path.append(os.path.dirname(__file__))
from DatabaseConnection import DatabaseConnection

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global variables for warm start
_model = None
_feature_names = None
_db = None


def load_model():
    """Load XGBoost model (cached on warm start)"""
    global _model, _feature_names
    
    if _model is not None:
        logger.info("Using cached model (warm start)")
        return _model, _feature_names
    
    logger.info("Loading XGBoost model (cold start)...")
    
    # Load from S3 or local file
    model_path = os.environ.get('MODEL_PATH', 'models/latest_model.pkl')
    features_path = os.environ.get('FEATURES_PATH', 'models/latest_features.json')
    
    try:
        _model = joblib.load(model_path)
        
        with open(features_path, 'r') as f:
            _feature_names = json.load(f)
        
        logger.info(f"✓ Model loaded: {len(_feature_names)} features")
        return _model, _feature_names
    
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise


class FeatureExtractor:
    """Extract features for XGBoost model from Supabase"""
    
    def __init__(self, db: DatabaseConnection):
        self.db = db
    
    def extract_features(self, team_a: str, team_b: str, spread_line: float, spread_favorite: str) -> Dict[str, float]:
        """
        Extract all features needed for XGBoost prediction
        
        Args:
            team_a: Team A abbreviation
            team_b: Team B abbreviation
            spread_line: Spread line (positive number)
            spread_favorite: 'team_a' or 'team_b'
            
        Returns:
            Dictionary of features
        """
        logger.info(f"Extracting features: {team_a} vs {team_b} (Spread: {spread_line})")
        
        # Determine favorite/underdog
        fav_team = team_a if spread_favorite == 'team_a' else team_b
        und_team = team_b if spread_favorite == 'team_a' else team_a
        
        features = {}
        
        # Get historical games
        conn = self.db.get_connection()
        
        # Query recent games
        query = """
        SELECT 
            game_id,
            gameday,
            home_team,
            away_team,
            home_score,
            away_score,
            spread_favorite,
            spread_line
        FROM games g
        LEFT JOIN spreads s ON g.game_id = s.game_id
        WHERE g.game_type = 'REG'
            AND g.home_score IS NOT NULL
            AND g.away_score IS NOT NULL
        ORDER BY g.gameday DESC
        LIMIT 500
        """
        
        data = conn.run(query)
        
        if not data:
            logger.warning("No historical data - using defaults")
            return self._get_default_features(spread_line)
        
        columns = ['game_id', 'gameday', 'home_team', 'away_team', 
                   'home_score', 'away_score', 'spread_favorite', 'spread_line']
        df = pd.DataFrame(data, columns=columns)
        
        # Calculate features
        features['spread_line'] = spread_line
        features['fav_recent_form'] = self._get_recent_form(df, fav_team)
        features['und_recent_form'] = self._get_recent_form(df, und_team)
        features['recent_form_diff'] = features['fav_recent_form'] - features['und_recent_form']
        
        features['fav_ats'] = self._get_ats_record(df, fav_team)
        features['und_ats'] = self._get_ats_record(df, und_team)
        features['ats_diff'] = features['fav_ats'] - features['und_ats']
        
        # Home/away (assume team_a is home)
        is_fav_home = (spread_favorite == 'team_a')
        features['fav_is_home'] = 1 if is_fav_home else 0
        features['fav_home_record'] = self._get_home_away_record(df, fav_team, home=is_fav_home)
        features['und_home_record'] = self._get_home_away_record(df, und_team, home=not is_fav_home)
        
        features['h2h_fav_wins'] = self._get_h2h_record(df, fav_team, und_team)
        features['is_divisional'] = self._is_divisional_game(fav_team, und_team)
        
        # Spread category
        if spread_line <= 3:
            features['spread_category'] = 0
        elif spread_line <= 7:
            features['spread_category'] = 1
        elif spread_line <= 10:
            features['spread_category'] = 2
        else:
            features['spread_category'] = 3
        
        # Surface/roof (defaults for now)
        features['surface_turf'] = 0  # TODO: Get from stadium data
        features['roof_dome'] = 0
        
        # Week (estimate based on current date)
        features['week_num'] = 10  # TODO: Get actual week
        features['is_late_season'] = 0
        
        # Player impact (if available)
        features['home_impact'] = 0  # TODO: Get from player_impact table
        features['away_impact'] = 0
        features['net_advantage'] = 0
        
        logger.info(f"✓ Extracted {len(features)} features")
        
        return features
    
    def _get_recent_form(self, df, team, window=5):
        """Calculate win rate in last N games"""
        team_games = df[
            (df['home_team'] == team) | (df['away_team'] == team)
        ].head(window)
        
        if len(team_games) == 0:
            return 0.5
        
        wins = 0
        for _, game in team_games.iterrows():
            if game['home_team'] == team:
                wins += 1 if game['home_score'] > game['away_score'] else 0
            else:
                wins += 1 if game['away_score'] > game['home_score'] else 0
        
        return wins / len(team_games)
    
    def _get_ats_record(self, df, team):
        """Calculate ATS win rate"""
        # Filter games with spread data
        spread_games = df[df['spread_line'].notna()]
        team_games = spread_games[
            (spread_games['home_team'] == team) | (spread_games['away_team'] == team)
        ].head(20)
        
        if len(team_games) == 0:
            return 0.5
        
        covers = 0
        for _, game in team_games.iterrows():
            is_home = game['home_team'] == team
            is_favorite = (game['spread_favorite'] == 'home' and is_home) or (game['spread_favorite'] == 'away' and not is_home)
            
            margin = game['home_score'] - game['away_score']
            if not is_home:
                margin = -margin
            
            if is_favorite:
                covers += 1 if margin > game['spread_line'] else 0
            else:
                covers += 1 if margin + game['spread_line'] > 0 else 0
        
        return covers / len(team_games)
    
    def _get_home_away_record(self, df, team, home=True):
        """Get win rate as home or away team"""
        if home:
            team_games = df[df['home_team'] == team].head(10)
            if len(team_games) == 0:
                return 0.5
            wins = (team_games['home_score'] > team_games['away_score']).sum()
        else:
            team_games = df[df['away_team'] == team].head(10)
            if len(team_games) == 0:
                return 0.5
            wins = (team_games['away_score'] > team_games['home_score']).sum()
        
        return wins / len(team_games)
    
    def _get_h2h_record(self, df, team1, team2):
        """Get head-to-head win rate"""
        h2h_games = df[
            ((df['home_team'] == team1) & (df['away_team'] == team2)) |
            ((df['home_team'] == team2) & (df['away_team'] == team1))
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
        """Check if divisional game"""
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
    
    def _get_default_features(self, spread_line):
        """Return default features when no historical data"""
        return {
            'spread_line': spread_line,
            'fav_recent_form': 0.5,
            'und_recent_form': 0.5,
            'recent_form_diff': 0,
            'fav_ats': 0.5,
            'und_ats': 0.5,
            'ats_diff': 0,
            'fav_is_home': 1,
            'fav_home_record': 0.5,
            'und_home_record': 0.5,
            'h2h_fav_wins': 0.5,
            'is_divisional': 0,
            'spread_category': 1,
            'surface_turf': 0,
            'roof_dome': 0,
            'week_num': 10,
            'is_late_season': 0,
            'home_impact': 0,
            'away_impact': 0,
            'net_advantage': 0
        }


def lambda_handler(event, context):
    """
    AWS Lambda handler for XGBoost spread prediction
    
    Event format:
    {
        "team_a": "BAL",
        "team_b": "BUF",
        "spread_line": 2.5,
        "spread_favorite": "team_a"
    }
    
    Returns:
    {
        "favorite_cover_probability": 0.65,
        "prediction": "favorite",
        "confidence": "medium"
    }
    """
    global _db
    
    try:
        # Initialize database (cached on warm start)
        if _db is None:
            _db = DatabaseConnection()
        
        # Load model (cached on warm start)
        model, feature_names = load_model()
        
        # Parse event
        team_a = event['team_a'].upper()
        team_b = event['team_b'].upper()
        spread_line = float(event['spread_line'])
        spread_favorite = event.get('spread_favorite', 'team_a')
        
        logger.info(f"Predicting: {team_a} vs {team_b} (Spread: {spread_line}, Fav: {spread_favorite})")
        
        # Extract features
        extractor = FeatureExtractor(_db)
        features = extractor.extract_features(team_a, team_b, spread_line, spread_favorite)
        
        # Create feature vector (ensure correct order)
        feature_vector = [features.get(fname, 0) for fname in feature_names]
        X = pd.DataFrame([feature_vector], columns=feature_names)
        
        # Predict
        proba = model.predict_proba(X)[0, 1]  # Probability favorite covers
        prediction = "favorite" if proba > 0.5 else "underdog"
        
        # Confidence levels
        if proba > 0.65 or proba < 0.35:
            confidence = "high"
        elif proba > 0.55 or proba < 0.45:
            confidence = "medium"
        else:
            confidence = "low"
        
        logger.info(f"✓ Prediction: {prediction} ({proba:.3f}) - {confidence} confidence")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'favorite_cover_probability': round(proba, 4),
                'underdog_cover_probability': round(1 - proba, 4),
                'prediction': prediction,
                'confidence': confidence,
                'matchup': {
                    'team_a': team_a,
                    'team_b': team_b,
                    'spread_line': spread_line,
                    'favorite': team_a if spread_favorite == 'team_a' else team_b
                }
            })
        }
    
    except Exception as e:
        logger.error(f"Prediction failed: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }


# For local testing
if __name__ == "__main__":
    test_event = {
        "team_a": "BAL",
        "team_b": "BUF",
        "spread_line": 2.5,
        "spread_favorite": "team_a"
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(json.loads(result['body']), indent=2))

