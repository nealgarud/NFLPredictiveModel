"""
Configuration file for NFL Training Data Preparation
Centralized settings for easy modification
"""

import os
from typing import List

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

DB_CONFIG = {
    'host': os.environ.get('SUPABASE_DB_HOST'),
    'database': os.environ.get('SUPABASE_DB_NAME', 'postgres'),
    'user': os.environ.get('SUPABASE_DB_USER', 'postgres'),
    'password': os.environ.get('SUPABASE_DB_PASSWORD'),
    'port': int(os.environ.get('SUPABASE_DB_PORT', 5432))
}

# ============================================================================
# TRAINING DATA CONFIGURATION
# ============================================================================

# Seasons to include in training data
DEFAULT_SEASONS: List[int] = [2024, 2025]

# Output file path
DEFAULT_OUTPUT_FILE: str = 'training_data.csv'

# Minimum games required for historical calculations
MIN_GAMES_FOR_STATS: int = 3

# ============================================================================
# FEATURE ENGINEERING PARAMETERS
# ============================================================================

# Recent form: number of games to consider
RECENT_FORM_WINDOW: int = 5

# Bye week: minimum days between games to consider as bye
BYE_WEEK_THRESHOLD_DAYS: int = 14

# Close game: spread threshold
CLOSE_GAME_THRESHOLD: float = 3.0

# Spread categorization ranges
SPREAD_CATEGORIES = {
    'very_close': (0, 3),
    'close': (3, 7),
    'moderate': (7, 10),
    'large': (10, 100)
}

# ============================================================================
# DATA QUALITY PARAMETERS
# ============================================================================

# Columns that should never have missing values
REQUIRED_COLUMNS: List[str] = [
    'game_id', 'season', 'week', 'home_team', 'away_team',
    'spread_line', 'target_favorite_covered'
]

# Maximum percentage of missing values allowed per feature
MAX_MISSING_PERCENT: float = 0.10  # 10%

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_LEVEL: str = os.environ.get('LOG_LEVEL', 'INFO')
LOG_FORMAT: str = '%(asctime)s - %(levelname)s - %(message)s'

# ============================================================================
# PERFORMANCE SETTINGS
# ============================================================================

# Progress update frequency (every N games)
PROGRESS_UPDATE_FREQUENCY: int = 50

# Database query timeout (seconds)
DB_TIMEOUT: int = 30

# ============================================================================
# FEATURE FLAGS
# ============================================================================

# Enable/disable specific feature groups
ENABLE_FORM_FEATURES: bool = True
ENABLE_SITUATIONAL_FEATURES: bool = True
ENABLE_CONTEXTUAL_FEATURES: bool = True
ENABLE_PERFORMANCE_FEATURES: bool = True
ENABLE_CORE_FEATURES: bool = True

# Future features (when data becomes available)
ENABLE_PLAYER_FEATURES: bool = False  # QB ratings, injuries
ENABLE_WEATHER_FEATURES: bool = False  # Temperature, wind
ENABLE_ADVANCED_METRICS: bool = False  # DVOA, efficiency

# ============================================================================
# VALIDATION SETTINGS
# ============================================================================

# Ensure no data leakage: only use games before current game
ENFORCE_TEMPORAL_VALIDATION: bool = True

# Check for impossible values
VALIDATE_FEATURE_RANGES: bool = True

# Expected value ranges for validation
FEATURE_RANGES = {
    'fav_recent_form': (0.0, 1.0),
    'und_recent_form': (0.0, 1.0),
    'fav_div_ats': (0.0, 1.0),
    'und_div_ats': (0.0, 1.0),
    'fav_close_game_perf': (0.0, 1.0),
    'fav_after_loss_perf': (0.0, 1.0),
    'fav_sit_ats': (0.0, 1.0),
    'und_sit_ats': (0.0, 1.0),
    'fav_overall_ats': (0.0, 1.0),
    'und_overall_ats': (0.0, 1.0),
    'fav_home_away_wr': (0.0, 1.0),
    'und_home_away_wr': (0.0, 1.0),
    'spread_magnitude': (0, 3),
    'target_favorite_covered': (0, 1)
}

