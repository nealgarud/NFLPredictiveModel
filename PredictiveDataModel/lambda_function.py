"""
Predictive Data Model Lambda Handler
XGBoost ML-based NFL spread prediction (replaces manual weights)
"""

import json
import os
import sys
import logging
import joblib
import pandas as pd
from typing import Dict

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global cache for warm starts
_model = None
_feature_names = None


def load_model():
    """Load XGBoost model (cached on warm start)"""
    global _model, _feature_names
    
    if _model is not None:
        logger.info("Using cached model (warm start)")
        return _model, _feature_names
    
    logger.info("Loading XGBoost model (cold start)...")
    
    # Load from local file (included in Lambda package)
    model_path = 'models/latest_model.pkl'
    features_path = 'models/latest_features.json'
    
    try:
        _model = joblib.load(model_path)
        
        with open(features_path, 'r') as f:
            _feature_names = json.load(f)
        
        logger.info(f"✓ Model loaded: {len(_feature_names)} features")
        return _model, _feature_names
    
    except FileNotFoundError:
        logger.error(f"Model files not found. Expected {model_path} and {features_path}")
        logger.error("Did you copy models/ from ML-Training to predictivedatamodel/?")
        raise
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise


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
        "underdog_cover_probability": 0.35,
        "prediction": "favorite",
        "confidence": "medium"
    }
    """
    
    try:
        # Load model (cached on warm start)
        model, feature_names = load_model()
        
        # Parse event
        team_a = event['team_a'].upper()
        team_b = event['team_b'].upper()
        spread_line = float(event['spread_line'])
        spread_favorite = event.get('spread_favorite', 'team_a')
        
        logger.info(f"Predicting: {team_a} vs {team_b} (Spread: {spread_line}, Fav: {spread_favorite})")
        
        # Extract features
        features = extract_features_simple(team_a, team_b, spread_line, spread_favorite)
        
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
    
    except KeyError as e:
        logger.error(f"Missing required field: {e}")
        return {
            'statusCode': 400,
            'body': json.dumps({
                'success': False,
                'error': f'Missing required field: {e}'
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


def extract_features_simple(team_a, team_b, spread_line, spread_favorite):
    """
    Extract features for prediction (simplified version)
    
    TODO: For production, implement full feature extraction from Supabase
    This version uses default/estimated values
    """
    logger.info("Using simplified feature extraction (default values)")
    
    # Determine favorite/underdog
    is_fav_team_a = (spread_favorite == 'team_a')
    
    # Spread category
    if spread_line <= 3:
        spread_category = 0  # Very close
    elif spread_line <= 7:
        spread_category = 1  # Close
    elif spread_line <= 10:
        spread_category = 2  # Moderate
    else:
        spread_category = 3  # Large
    
    # Default features (in production, pull from Supabase)
    features = {
        'spread_line': spread_line,
        'fav_recent_form': 0.5,  # TODO: Calculate from recent games
        'und_recent_form': 0.5,
        'recent_form_diff': 0.0,
        'fav_ats': 0.5,  # TODO: Calculate ATS record
        'und_ats': 0.5,
        'ats_diff': 0.0,
        'fav_is_home': 1 if is_fav_team_a else 0,
        'fav_home_record': 0.5,  # TODO: Calculate from historical data
        'und_home_record': 0.5,
        'h2h_fav_wins': 0.5,  # TODO: Head-to-head record
        'is_divisional': 0,  # TODO: Check division
        'spread_category': spread_category,
        'surface_turf': 0,  # TODO: Stadium data
        'roof_dome': 0,
        'week_num': 10,  # TODO: Get actual week
        'is_late_season': 0,
        'home_impact': 0,  # TODO: Player impact from playerimpact Lambda
        'away_impact': 0,
        'net_advantage': 0
    }
    
    return features


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

