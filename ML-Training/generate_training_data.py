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
    g.gameday,
    (g.home_score - g.away_score)                   AS actual_margin,
    (g.home_score - g.away_score - g.spread_line)   AS ats_result,
    g.div_game,

    -- Player impact legacy (PFFGameProcessor v1)
    gm.home_avg_impact,
    gm.away_avg_impact,
    gm.avg_impact_differential,

    -- Player Impact PFF (PlayerImpactProcessor)
    gm.home_total_impact,
    gm.away_total_impact,
    gm.impact_differential,
    gm.home_tier_1_count,
    gm.home_tier_2_count,
    gm.home_tier_3_count,
    gm.home_tier_4_count,
    gm.home_tier_5_count,
    gm.away_tier_1_count,
    gm.away_tier_2_count,
    gm.away_tier_3_count,
    gm.away_tier_4_count,
    gm.away_tier_5_count,
    gm.home_qb1_active,
    gm.home_rb1_active,
    gm.home_wr1_active,
    gm.home_edge1_active,
    gm.home_cb1_active,
    gm.away_qb1_active,
    gm.away_rb1_active,
    gm.away_wr1_active,
    gm.away_edge1_active,
    gm.away_cb1_active,

    -- Offense / Defense / OL breakdown
    gm.home_offense_impact,
    gm.home_defense_impact,
    gm.home_ol_impact,
    gm.away_offense_impact,
    gm.away_defense_impact,
    gm.away_ol_impact,

    -- PFF grades
    gm.home_pff_offense,
    gm.away_pff_offense,
    gm.home_pff_defense,
    gm.away_pff_defense,
    gm.home_pff_run,
    gm.away_pff_run,
    gm.home_pff_passing,
    gm.away_pff_passing,
    gm.home_pff_coverage,
    gm.away_pff_coverage,
    gm.home_pff_pass_rush,
    gm.away_pff_pass_rush,
    gm.home_pff_special_teams,
    gm.away_pff_special_teams,

    -- Team rankings (PFF-based)
    gm.home_run_offense_rank,
    gm.away_run_offense_rank,
    gm.home_pass_offense_rank,
    gm.away_pass_offense_rank,
    gm.home_run_defense_rank,
    gm.away_run_defense_rank,
    gm.home_pass_defense_rank,
    gm.away_pass_defense_rank,
    gm.home_pass_rush_rank,
    gm.away_pass_rush_rank,
    gm.home_special_teams_rank,
    gm.away_special_teams_rank,

    -- Matchup differentials (pre-computed)
    gm.matchup_run_off_vs_run_def,
    gm.matchup_pass_off_vs_coverage,
    gm.matchup_pass_rush_vs_pass_block,
    gm.matchup_overall_off_vs_def,
    gm.matchup_special_teams,
    gm.pff_overall_diff,

    -- Box score impact (safe — reflects what happened, used as feature)
    gm.home_actual_game_impact,
    gm.away_actual_game_impact,

    -- Raw surprise scores — fetched for rolling window computation only.
    -- These are post-game values and will be DROPPED before saving to CSV.
    gm.home_performance_surprise,
    gm.away_performance_surprise,

    -- Home team season rankings
    home_tr.win_rate            AS home_win_rate,
    home_tr.avg_points_scored   AS home_ppg,
    home_tr.avg_points_allowed  AS home_papg,
    home_tr.point_differential  AS home_pt_diff,
    home_tr.offensive_rank      AS home_off_rank,
    home_tr.defensive_rank      AS home_def_rank,
    home_tr.overall_rank        AS home_overall_rank,
    home_tr.ats_cover_rate      AS home_ats_rate,
    home_tr.avg_spread_line     AS home_avg_spread,

    -- Away team season rankings
    away_tr.win_rate            AS away_win_rate,
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
    AND g.away_score IS NOT NULL
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
# 4a. ROLLING SURPRISE FEATURES
#     For each game we want to know: "how has this team been performing
#     relative to expectations over their last N games?"
#     We CANNOT use the current game's surprise (that's post-game leakage).
#     So we build a per-team history from ALL games, then for each row
#     look strictly backward (gameday < current game's gameday).
# ---------------------------------------------------------------------------

def compute_rolling_surprise(df: pd.DataFrame) -> pd.DataFrame:
    # Convert gameday to datetime for reliable comparison
    df['gameday'] = pd.to_datetime(df['gameday'])

    # Build a flat per-team-game history from both sides of each game
    home_hist = df[['home_team', 'gameday', 'home_performance_surprise']].rename(
        columns={'home_team': 'team', 'home_performance_surprise': 'surprise'}
    )
    away_hist = df[['away_team', 'gameday', 'away_performance_surprise']].rename(
        columns={'away_team': 'team', 'away_performance_surprise': 'surprise'}
    )
    history = pd.concat([home_hist, away_hist], ignore_index=True).sort_values('gameday')

    def prior_rolling(team: str, game_date: pd.Timestamp, n: int) -> float:
        """Mean surprise over the n games this team played strictly before game_date."""
        prior = history.loc[
            (history['team'] == team) & (history['gameday'] < game_date),
            'surprise'
        ].dropna()
        if prior.empty:
            return 0.0
        return float(prior.iloc[-n:].mean())

    logger.info("Computing rolling surprise features (3g, 5g) for %d games...", len(df))
    df['home_rolling_3g_surprise'] = df.apply(
        lambda r: prior_rolling(r['home_team'], r['gameday'], 3), axis=1
    )
    df['home_rolling_5g_surprise'] = df.apply(
        lambda r: prior_rolling(r['home_team'], r['gameday'], 5), axis=1
    )
    df['away_rolling_3g_surprise'] = df.apply(
        lambda r: prior_rolling(r['away_team'], r['gameday'], 3), axis=1
    )
    df['away_rolling_5g_surprise'] = df.apply(
        lambda r: prior_rolling(r['away_team'], r['gameday'], 5), axis=1
    )
    df['rolling_3g_surprise_diff'] = df['home_rolling_3g_surprise'] - df['away_rolling_3g_surprise']
    df['rolling_5g_surprise_diff'] = df['home_rolling_5g_surprise'] - df['away_rolling_5g_surprise']

    return df


# ---------------------------------------------------------------------------
# 4b. FEATURE ENGINEERING
#     The raw columns are good, but XGBoost does better with DIFFERENTIALS.
#     Instead of feeding "home team scores 25 ppg" and "away team scores 20 ppg"
#     separately, we also tell it "home team scores 5 MORE ppg than away."
#     That gap is what actually predicts outcomes.
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

    # -- PlayerImpactProcessor differentials --
    df['offense_impact_diff']  = df['home_offense_impact']  - df['away_offense_impact']
    df['defense_impact_diff']  = df['home_defense_impact']  - df['away_defense_impact']
    df['ol_impact_diff']       = df['home_ol_impact']       - df['away_ol_impact']
    df['actual_impact_diff']   = df['home_actual_game_impact'] - df['away_actual_game_impact']

    # PFF grade differentials
    df['pff_offense_diff']      = df['home_pff_offense']      - df['away_pff_offense']
    df['pff_defense_diff']      = df['home_pff_defense']      - df['away_pff_defense']
    df['pff_pass_rush_diff']    = df['home_pff_pass_rush']    - df['away_pff_pass_rush']
    df['pff_coverage_diff']     = df['home_pff_coverage']     - df['away_pff_coverage']
    df['pff_run_diff']          = df['home_pff_run']          - df['away_pff_run']
    df['pff_passing_diff']      = df['home_pff_passing']      - df['away_pff_passing']
    df['pff_st_diff']           = df['home_pff_special_teams'] - df['away_pff_special_teams']

    # PFF rank differentials (lower = better → away - home)
    df['run_off_rank_diff']     = df['away_run_offense_rank']  - df['home_run_offense_rank']
    df['pass_off_rank_diff']    = df['away_pass_offense_rank'] - df['home_pass_offense_rank']
    df['run_def_rank_diff']     = df['away_run_defense_rank']  - df['home_run_defense_rank']
    df['pass_def_rank_diff']    = df['away_pass_defense_rank'] - df['home_pass_defense_rank']
    df['pass_rush_rank_diff']   = df['away_pass_rush_rank']    - df['home_pass_rush_rank']
    df['st_rank_diff']          = df['away_special_teams_rank'] - df['home_special_teams_rank']

    # Tier counts differential (home elite players minus away elite players)
    df['tier1_diff'] = df['home_tier_1_count'] - df['away_tier_1_count']
    df['tier2_diff'] = df['home_tier_2_count'] - df['away_tier_2_count']

    # -- Convert booleans --
    df['div_game'] = df['div_game'].fillna(False).astype(int)
    for col in ['home_qb1_active', 'home_rb1_active', 'home_wr1_active',
                'home_edge1_active', 'home_cb1_active',
                'away_qb1_active', 'away_rb1_active', 'away_wr1_active',
                'away_edge1_active', 'away_cb1_active']:
        if col in df.columns:
            df[col] = df[col].fillna(True).astype(int)

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
    df = compute_rolling_surprise(df)    # uses home/away_performance_surprise + gameday
    df = engineer_features(df)

    # Drop post-game leakage columns — must not appear in the final CSV
    df.drop(columns=[
        'home_performance_surprise',
        'away_performance_surprise',
        'gameday',
    ], errors='ignore', inplace=True)

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
