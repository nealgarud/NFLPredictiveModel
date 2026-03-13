"""
Generate Training Data for XGBoost NFL Spread Prediction

Joins Supabase tables into one flat CSV:
  - games                (game results, spread lines)
  - game_id_mapping      (player impact, PFF matchup features, game script, performance surprise)
  - team_rankings        (season-level team stats & rankings)
  - team_season_features (situational records: primetime, vs strong/weak, ATS)
  - team_pff_profiles    (PFF defensive/offensive grades — built by build_pff_profiles.py)

Output: training_data.csv  (one row per game, ~800+ rows for 2022-2024)

Run order:
  1. Run TeamPFFProcessor/alter_game_id_mapping.sql    (PFF matchup columns)
  2. Run BoxScoreCollector/alter_game_id_mapping.sql   (game script + surprise columns)
  3. python TeamPFFProcessor/team_pff_processor.py
  4. Deploy + invoke BoxScoreCollector Lambda
  5. python generate_training_data.py
  6. python train_model.py
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

    -- Team PFF grades per game (pre-computed by TeamPFFProcessor, prev season)
    gm.home_pff_offense,       gm.away_pff_offense,
    gm.home_pff_defense,       gm.away_pff_defense,
    gm.home_pff_run,           gm.away_pff_run,
    gm.home_pff_passing,       gm.away_pff_passing,
    gm.home_pff_run_defense,   gm.away_pff_run_defense,
    gm.home_pff_coverage,      gm.away_pff_coverage,
    gm.home_pff_pass_rush,     gm.away_pff_pass_rush,
    gm.home_pff_special_teams, gm.away_pff_special_teams,

    -- Season rankings 1-32 (1=best)
    gm.home_run_offense_rank,   gm.away_run_offense_rank,
    gm.home_pass_offense_rank,  gm.away_pass_offense_rank,
    gm.home_run_defense_rank,   gm.away_run_defense_rank,
    gm.home_pass_defense_rank,  gm.away_pass_defense_rank,
    gm.home_pass_rush_rank,     gm.away_pass_rush_rank,
    gm.home_special_teams_rank, gm.away_special_teams_rank,

    -- Pre-computed matchup differentials (positive = home advantage)
    gm.matchup_run_off_vs_run_def,
    gm.matchup_pass_off_vs_coverage,
    gm.matchup_pass_rush_vs_pass_block,
    gm.matchup_overall_off_vs_def,
    gm.matchup_special_teams,
    gm.pff_overall_diff,

    -- Rank advantages (positive = home advantage)
    gm.rank_adv_run_game,
    gm.rank_adv_pass_game,
    gm.rank_adv_rush_pressure,
    gm.rank_adv_special_teams,

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
    away_tf.after_bye_ats_rate      AS away_after_bye_ats,

    -- Home team PFF grades (Enhancement 1)
    home_pff.def_grade          AS home_def_grade,
    home_pff.pass_rush_grade    AS home_pass_rush_grade,
    home_pff.run_def_grade      AS home_run_def_grade,
    home_pff.coverage_grade     AS home_coverage_grade,
    home_pff.qb_grade           AS home_qb_grade,
    home_pff.rb_grade           AS home_rb_grade,
    home_pff.ol_pass_block      AS home_ol_pass_block,
    home_pff.ol_run_block       AS home_ol_run_block,
    home_pff.off_run_pass_ratio AS home_run_pass_ratio,

    -- Away team PFF grades (Enhancement 1)
    away_pff.def_grade          AS away_def_grade,
    away_pff.pass_rush_grade    AS away_pass_rush_grade,
    away_pff.run_def_grade      AS away_run_def_grade,
    away_pff.coverage_grade     AS away_coverage_grade,
    away_pff.qb_grade           AS away_qb_grade,
    away_pff.rb_grade           AS away_rb_grade,
    away_pff.ol_pass_block      AS away_ol_pass_block,
    away_pff.ol_run_block       AS away_ol_run_block,
    away_pff.off_run_pass_ratio AS away_run_pass_ratio,

    -- Game script: quarter scoring (BoxScoreCollector)
    gm.home_q1_points,  gm.away_q1_points,
    gm.home_q2_points,  gm.away_q2_points,
    gm.home_q3_points,  gm.away_q3_points,
    gm.home_q4_points,  gm.away_q4_points,
    gm.home_led_at_half,
    gm.halftime_margin,

    -- Actual game impact + performance surprise (BoxScoreCollector)
    gm.home_actual_game_impact,
    gm.away_actual_game_impact,
    gm.home_performance_surprise,
    gm.away_performance_surprise,
    gm.performance_surprise_diff

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
-- PFF profiles: LEFT JOIN so missing data doesn't drop games, fills with NULL -> 0
LEFT JOIN team_pff_profiles home_pff
    ON g.home_team = home_pff.team_name AND g.season - 1 = home_pff.season
LEFT JOIN team_pff_profiles away_pff
    ON g.away_team = away_pff.team_name AND g.season - 1 = away_pff.season
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

    # -- Enhancement 1: PFF grade differentials --
    # Straight defensive strength differentials
    df['def_grade_diff']        = df['home_def_grade'] - df['away_def_grade']
    df['pass_rush_diff']        = df['home_pass_rush_grade'] - df['away_pass_rush_grade']
    df['run_def_diff']          = df['home_run_def_grade'] - df['away_run_def_grade']
    df['coverage_diff']         = df['home_coverage_grade'] - df['away_coverage_grade']

    # Offensive strength differentials
    df['qb_grade_diff']         = df['home_qb_grade'] - df['away_qb_grade']
    df['rb_grade_diff']         = df['home_rb_grade'] - df['away_rb_grade']
    df['ol_pass_block_diff']    = df['home_ol_pass_block'] - df['away_ol_pass_block']
    df['ol_run_block_diff']     = df['home_ol_run_block'] - df['away_ol_run_block']

    # Matchup interaction features:
    #   away pass attack (away_qb_grade) vs home coverage (home_coverage_grade)
    #   away run attack  (away_rb_grade)  vs home run defense (home_run_def_grade)
    #   home pass attack (home_qb_grade)  vs away coverage (away_coverage_grade)
    #   home run attack  (home_rb_grade)  vs away run defense (away_run_def_grade)
    df['matchup_away_pass_vs_home_cov']  = df['away_qb_grade']  - df['home_coverage_grade']
    df['matchup_away_run_vs_home_rdef']  = df['away_rb_grade']  - df['home_run_def_grade']
    df['matchup_home_pass_vs_away_cov']  = df['home_qb_grade']  - df['away_coverage_grade']
    df['matchup_home_run_vs_away_rdef']  = df['home_rb_grade']  - df['away_run_def_grade']

    # -- Enhancement 2: Team PFF grade differentials (from game_id_mapping) --
    df['pff_offense_diff'] = df['home_pff_offense'] - df['away_pff_offense']
    df['pff_defense_diff'] = df['home_pff_defense'] - df['away_pff_defense']

    # -- Enhancement 3: Box score / game script features --
    # Rolling 3-game performance surprise (using PREVIOUS games only — no leakage)
    df = _add_rolling_surprise(df, window=3)
    df = _add_rolling_surprise(df, window=5)

    # Halftime margin diff (home perspective)
    df['halftime_margin'] = df['halftime_margin'].fillna(0)
    df['home_led_at_half'] = df['home_led_at_half'].fillna(False).astype(int)

    # Quarter scoring differentials
    for q in (1, 2, 3, 4):
        home_col = f'home_q{q}_points'
        away_col = f'away_q{q}_points'
        if home_col in df.columns:
            df[f'q{q}_margin'] = df[home_col].fillna(0) - df[away_col].fillna(0)

    # -- Convert booleans --
    df['div_game'] = df['div_game'].fillna(False).astype(int)

    # -- Fill any remaining NULLs with neutral values --
    df = df.fillna(0)

    logger.info(f"Engineered features. Total columns: {len(df.columns)}")
    return df


# ---------------------------------------------------------------------------
# 4b. ROLLING SURPRISE HELPER
#     Uses shift(1) so a game only sees surprise from PREVIOUS games.
#     Sorted by season+week before rolling so ordering is correct.
# ---------------------------------------------------------------------------

def _add_rolling_surprise(df: pd.DataFrame, window: int) -> pd.DataFrame:
    """
    For each game, compute the rolling mean of home/away performance_surprise
    over the previous `window` games for that team.

    home_rolling_{w}g_surprise = avg surprise of home team's last w games
    away_rolling_{w}g_surprise = avg surprise of away team's last w games
    """
    if 'home_performance_surprise' not in df.columns:
        return df

    df = df.sort_values(['season', 'week']).reset_index(drop=True)

    # Build a team-indexed series of surprise scores across all games
    rows = []
    for _, r in df.iterrows():
        rows.append({'game_id': r['game_id'], 'season': r['season'], 'week': r['week'],
                     'team': r['home_team'], 'surprise': r.get('home_performance_surprise', 0)})
        rows.append({'game_id': r['game_id'], 'season': r['season'], 'week': r['week'],
                     'team': r['away_team'], 'surprise': r.get('away_performance_surprise', 0)})

    team_df = pd.DataFrame(rows).sort_values(['team', 'season', 'week'])
    team_df[f'rolling_{window}g'] = (
        team_df.groupby('team')['surprise']
        .transform(lambda s: s.shift(1).rolling(window, min_periods=1).mean())
    )
    rolling_map = team_df.set_index(['game_id', 'team'])[f'rolling_{window}g'].to_dict()

    home_col = f'home_rolling_{window}g_surprise'
    away_col = f'away_rolling_{window}g_surprise'
    df[home_col] = df.apply(lambda r: rolling_map.get((r['game_id'], r['home_team']), 0), axis=1)
    df[away_col] = df.apply(lambda r: rolling_map.get((r['game_id'], r['away_team']), 0), axis=1)
    df[f'rolling_{window}g_surprise_diff'] = df[home_col] - df[away_col]

    logger.info(f"Added rolling {window}g surprise features")
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
