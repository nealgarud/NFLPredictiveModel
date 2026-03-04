"""
Generate Training Data for XGBoost NFL Spread Prediction

Joins 4 Supabase tables into one flat CSV:
  - games              (game results, spread lines)
  - game_id_mapping    (player impact scores per game)
  - team_rankings      (season-level team stats & rankings)
  - team_season_features (situational records: primetime, vs strong/weak, ATS)

Output: training_data.csv  (one row per game, ~700 rows for 2022-2024)
"""

import os
import pg8000
import pandas as pd
import numpy as np
import logging
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. DATABASE CONNECTION
#    pg8000 is a pure-Python PostgreSQL driver. We point it at Supabase.
#    Credentials come from a .env file so we never hardcode secrets.
# ---------------------------------------------------------------------------

def get_connection():
    host = (os.environ.get('SUPABASE_DB_HOST') or os.environ.get('DB_HOST', '')).strip()
    port = int((os.environ.get('SUPABASE_DB_PORT') or os.environ.get('DB_PORT', '6543')).strip())
    database = (os.environ.get('SUPABASE_DB_NAME') or os.environ.get('DB_NAME', '')).strip()
    user = (os.environ.get('SUPABASE_DB_USER') or os.environ.get('DB_USER', '')).strip()
    password = (os.environ.get('SUPABASE_DB_PASSWORD') or os.environ.get('DB_PASSWORD', '')).strip()

    conn = pg8000.connect(
        host=host, port=port, database=database,
        user=user, password=password, ssl_context=True
    )
    conn.autocommit = True
    return conn


# ---------------------------------------------------------------------------
# 2. MASTER JOIN QUERY
#    This is the big SQL that pulls everything together.
#    Think of it like stacking Lego sets side by side:
#      - Start with every game (the base plate)
#      - Snap on player impact data for that game
#      - Snap on season stats for the HOME team
#      - Snap on season stats for the AWAY team
#      - Snap on situational features for HOME team
#      - Snap on situational features for AWAY team
# ---------------------------------------------------------------------------

MASTER_QUERY = """
SELECT
    g.game_id, g.season, g.week,
    g.home_team, g.away_team,
    g.home_score, g.away_score,
    g.spread_line,
    (g.home_score - g.away_score)                   AS actual_margin,
    (g.home_score - g.away_score - g.spread_line)   AS ats_result,
    g.div_game,

    -- Player impact (per-game from PFFGameProcessor)
    gm.home_avg_impact,
    gm.away_avg_impact,
    gm.avg_impact_differential,

    -- Home team season rankings
    home_tr.win_rate        AS home_win_rate,
    home_tr.avg_points_scored   AS home_ppg,
    home_tr.avg_points_allowed  AS home_papg,
    home_tr.point_differential  AS home_pt_diff,
    home_tr.offensive_rank      AS home_off_rank,
    home_tr.defensive_rank      AS home_def_rank,
    home_tr.overall_rank        AS home_overall_rank,
    home_tr.ats_cover_rate      AS home_ats_rate,
    home_tr.avg_spread_line     AS home_avg_spread,

    -- Away team season rankings
    away_tr.win_rate        AS away_win_rate,
    away_tr.avg_points_scored   AS away_ppg,
    away_tr.avg_points_allowed  AS away_papg,
    away_tr.point_differential  AS away_pt_diff,
    away_tr.offensive_rank      AS away_off_rank,
    away_tr.defensive_rank      AS away_def_rank,
    away_tr.overall_rank        AS away_overall_rank,
    away_tr.ats_cover_rate      AS away_ats_rate,
    away_tr.avg_spread_line     AS away_avg_spread,

    -- Home team situational features
    home_tf.home_win_rate       AS home_at_home_wr,
    home_tf.away_win_rate       AS home_on_road_wr,
    home_tf.home_advantage      AS home_home_adv,
    home_tf.div_win_rate        AS home_div_wr,
    home_tf.div_advantage       AS home_div_adv,
    home_tf.prime_time_win_rate AS home_pt_wr,
    home_tf.vs_strong_win_rate  AS home_vs_strong,
    home_tf.vs_mid_win_rate     AS home_vs_mid,
    home_tf.vs_weak_win_rate    AS home_vs_weak,
    home_tf.close_game_ats_rate     AS home_close_ats,
    home_tf.after_loss_ats_rate     AS home_after_loss_ats,
    home_tf.after_bye_ats_rate      AS home_after_bye_ats,

    -- Away team situational features
    away_tf.home_win_rate       AS away_at_home_wr,
    away_tf.away_win_rate       AS away_on_road_wr,
    away_tf.home_advantage      AS away_home_adv,
    away_tf.div_win_rate        AS away_div_wr,
    away_tf.div_advantage       AS away_div_adv,
    away_tf.prime_time_win_rate AS away_pt_wr,
    away_tf.vs_strong_win_rate  AS away_vs_strong,
    away_tf.vs_mid_win_rate     AS away_vs_mid,
    away_tf.vs_weak_win_rate    AS away_vs_weak,
    away_tf.close_game_ats_rate     AS away_close_ats,
    away_tf.after_loss_ats_rate     AS away_after_loss_ats,
    away_tf.after_bye_ats_rate      AS away_after_bye_ats

FROM games g
JOIN game_id_mapping gm
    ON g.game_id = gm.game_id
-- Use PREVIOUS season's team data to prevent leakage.
-- A 2024 game joins to 2023 team stats (what's actually known at game time).
JOIN team_rankings home_tr
    ON g.home_team = home_tr.team_id AND g.season - 1 = home_tr.season
JOIN team_rankings away_tr
    ON g.away_team = away_tr.team_id AND g.season - 1 = away_tr.season
JOIN team_season_features home_tf
    ON g.home_team = home_tf.team_id AND g.season - 1 = home_tf.season
JOIN team_season_features away_tf
    ON g.away_team = away_tf.team_id AND g.season - 1 = away_tf.season
WHERE g.game_type = 'REG'
    AND g.home_score IS NOT NULL
    AND gm.home_avg_impact IS NOT NULL
ORDER BY g.season, g.week
"""


# ---------------------------------------------------------------------------
# 3. FETCH + BUILD DATAFRAME
#    Run the query, get rows back, turn them into a pandas DataFrame.
#    A DataFrame is basically an Excel spreadsheet in Python.
# ---------------------------------------------------------------------------

def fetch_raw_data():
    logger.info("Connecting to Supabase...")
    conn = get_connection()

    logger.info("Running master join query...")
    cursor = conn.cursor()
    cursor.execute(MASTER_QUERY)
    rows = cursor.fetchall()
    col_names = [desc[0] for desc in cursor.description]
    cursor.close()
    conn.close()

    df = pd.DataFrame(rows, columns=col_names)
    logger.info(f"Fetched {len(df)} games with all features joined")
    return df


# ---------------------------------------------------------------------------
# 4. FEATURE ENGINEERING
#    The raw columns are good, but XGBoost does better with DIFFERENTIALS.
#    Instead of feeding "home team scores 25 ppg" and "away team scores 20 ppg"
#    separately, we also tell it "home team scores 5 MORE ppg than away."
#    That gap is what actually predicts outcomes.
# ---------------------------------------------------------------------------

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    # -- Differentials (home minus away) --
    df['ppg_diff']      = df['home_ppg'] - df['away_ppg']
    df['papg_diff']     = df['home_papg'] - df['away_papg']
    df['pt_diff_diff']  = df['home_pt_diff'] - df['away_pt_diff']
    df['win_rate_diff']  = df['home_win_rate'] - df['away_win_rate']

    # Rank diffs (lower rank = better, so away - home = positive when home is better)
    df['off_rank_diff']     = df['away_off_rank'] - df['home_off_rank']
    df['def_rank_diff']     = df['away_def_rank'] - df['home_def_rank']
    df['overall_rank_diff'] = df['away_overall_rank'] - df['home_overall_rank']

    df['ats_rate_diff']     = df['home_ats_rate'] - df['away_ats_rate']
    df['vs_strong_diff']    = df['home_vs_strong'] - df['away_vs_strong']
    df['vs_weak_diff']      = df['home_vs_weak'] - df['away_vs_weak']
    df['pt_wr_diff']        = df['home_pt_wr'] - df['away_pt_wr']
    df['close_ats_diff']    = df['home_close_ats'] - df['away_close_ats']

    # -- Convert booleans --
    df['div_game'] = df['div_game'].fillna(False).astype(int)

    # -- Fill any remaining NULLs with neutral values --
    df = df.fillna(0)

    logger.info(f"Engineered features. Total columns: {len(df.columns)}")
    return df


# ---------------------------------------------------------------------------
# 5. SAVE TO CSV
#    The CSV is the handoff: generate_training_data creates it,
#    train_model.py reads it. Keeps the two scripts independent.
# ---------------------------------------------------------------------------

def main():
    logger.info("=" * 60)
    logger.info("GENERATING TRAINING DATA")
    logger.info("=" * 60)

    df = fetch_raw_data()
    df = engineer_features(df)

    output_path = os.path.join(os.path.dirname(__file__), 'training_data.csv')
    df.to_csv(output_path, index=False)

    logger.info(f"Saved to {output_path}")
    logger.info(f"  Rows:    {len(df)}")
    logger.info(f"  Columns: {len(df.columns)}")
    logger.info(f"  Seasons: {sorted(df['season'].unique())}")
    logger.info(f"  Nulls:   {df.isnull().sum().sum()}")

    print(f"\nDone! {len(df)} rows saved to training_data.csv")
    print("Next step: python train_model.py")


if __name__ == "__main__":
    main()
