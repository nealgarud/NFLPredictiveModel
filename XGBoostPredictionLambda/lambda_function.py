"""
XGBoost Prediction Lambda

On cold start:
  - Downloads nfl_spread_model_latest.json + feature_names.json from S3 to /tmp/
  - Loads the XGBoost model into memory
  - Opens a Supabase DB connection

On each invocation:
  - Queries team_rankings + team_season_features for both teams (previous season)
  - Queries game_id_mapping for average player impact scores (current season)
  - Builds the 61-feature vector in the exact order feature_names.json expects
  - Runs model.predict() → predicted margin (home - away)
  - Compares predicted margin to spread_line → ATS pick + confidence
"""

import json
import os
import logging
import boto3
import pg8000
import xgboost as xgb
import numpy as np

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Global cache (warm start reuse)
# ---------------------------------------------------------------------------
_model: xgb.XGBRegressor | None = None
_feature_names: list[str] | None = None
_db_conn = None

S3_BUCKET = os.environ.get("S3_BUCKET", "nfl-predictive-model-artifacts")
MODEL_KEY = "models/nfl_spread_model_latest.json"
FEATURES_KEY = "models/feature_names.json"
MODEL_LOCAL = "/tmp/nfl_spread_model_latest.json"
FEATURES_LOCAL = "/tmp/feature_names.json"


# ---------------------------------------------------------------------------
# Cold-start initialisation
# ---------------------------------------------------------------------------

def _load_model_from_s3() -> tuple[xgb.XGBRegressor, list[str]]:
    logger.info("Cold start: downloading model artifacts from S3")
    s3 = boto3.client("s3")
    s3.download_file(S3_BUCKET, MODEL_KEY, MODEL_LOCAL)
    s3.download_file(S3_BUCKET, FEATURES_KEY, FEATURES_LOCAL)

    model = xgb.XGBRegressor()
    model.load_model(MODEL_LOCAL)

    with open(FEATURES_LOCAL) as f:
        feature_names = json.load(f)

    logger.info(f"Model loaded. Features: {len(feature_names)}")
    return model, feature_names


def _get_db_connection():
    global _db_conn
    if _db_conn is not None:
        try:
            cur = _db_conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            return _db_conn
        except Exception:
            _db_conn = None

    _db_conn = pg8000.connect(
        host=os.environ["SUPABASE_DB_HOST"],
        database=os.environ.get("SUPABASE_DB_NAME", "postgres"),
        user=os.environ.get("SUPABASE_DB_USER", "postgres"),
        password=os.environ["SUPABASE_DB_PASSWORD"],
        port=int(os.environ.get("SUPABASE_DB_PORT", 6543)),
        timeout=30,
        ssl_context=True,
    )
    _db_conn.autocommit = True
    logger.info("Connected to Supabase")
    return _db_conn


# ---------------------------------------------------------------------------
# Supabase queries
# ---------------------------------------------------------------------------

def _fetch_team_rankings(db, team_id: str, season: int) -> dict:
    """Pull previous-season team_rankings row for a team."""
    query = """
        SELECT win_rate, avg_points_scored, avg_points_allowed,
               point_differential, offensive_rank, defensive_rank,
               overall_rank, ats_cover_rate, avg_spread_line
        FROM team_rankings
        WHERE team_id = %s AND season = %s
        LIMIT 1
    """
    cur = db.cursor()
    cur.execute(query, (team_id, season - 1))
    row = cur.fetchone()
    cur.close()

    if row is None:
        logger.warning(f"No team_rankings for {team_id} season {season - 1}; using zeros")
        return {
            "win_rate": 0.5, "avg_points_scored": 22.0, "avg_points_allowed": 22.0,
            "point_differential": 0.0, "offensive_rank": 16, "defensive_rank": 16,
            "overall_rank": 16, "ats_cover_rate": 0.5, "avg_spread_line": 0.0,
        }

    cols = [
        "win_rate", "avg_points_scored", "avg_points_allowed",
        "point_differential", "offensive_rank", "defensive_rank",
        "overall_rank", "ats_cover_rate", "avg_spread_line",
    ]
    return dict(zip(cols, row))


def _fetch_team_season_features(db, team_id: str, season: int) -> dict:
    """Pull previous-season team_season_features row for a team."""
    query = """
        SELECT home_win_rate, away_win_rate, home_advantage,
               div_win_rate, div_advantage, prime_time_win_rate,
               vs_strong_win_rate, vs_mid_win_rate, vs_weak_win_rate,
               close_game_ats_rate, after_loss_ats_rate, after_bye_ats_rate
        FROM team_season_features
        WHERE team_id = %s AND season = %s
        LIMIT 1
    """
    cur = db.cursor()
    cur.execute(query, (team_id, season - 1))
    row = cur.fetchone()
    cur.close()

    if row is None:
        logger.warning(f"No team_season_features for {team_id} season {season - 1}; using zeros")
        return {k: 0.5 for k in [
            "home_win_rate", "away_win_rate", "home_advantage",
            "div_win_rate", "div_advantage", "prime_time_win_rate",
            "vs_strong_win_rate", "vs_mid_win_rate", "vs_weak_win_rate",
            "close_game_ats_rate", "after_loss_ats_rate", "after_bye_ats_rate",
        ]}

    cols = [
        "home_win_rate", "away_win_rate", "home_advantage",
        "div_win_rate", "div_advantage", "prime_time_win_rate",
        "vs_strong_win_rate", "vs_mid_win_rate", "vs_weak_win_rate",
        "close_game_ats_rate", "after_loss_ats_rate", "after_bye_ats_rate",
    ]
    return dict(zip(cols, row))


def _fetch_pff_profile(db, team_id: str, season: int) -> dict:
    """Pull previous-season team_pff_profiles row for a team."""
    query = """
        SELECT def_grade, pass_rush_grade, run_def_grade, coverage_grade,
               qb_grade, rb_grade, ol_pass_block, ol_run_block, off_run_pass_ratio
        FROM team_pff_profiles
        WHERE team_name = %s AND season = %s
        LIMIT 1
    """
    cur = db.cursor()
    cur.execute(query, (team_id, season - 1))
    row = cur.fetchone()
    cur.close()

    cols = [
        "def_grade", "pass_rush_grade", "run_def_grade", "coverage_grade",
        "qb_grade", "rb_grade", "ol_pass_block", "ol_run_block", "off_run_pass_ratio",
    ]
    if row is None:
        logger.warning(f"No team_pff_profiles for {team_id} season {season - 1}; using zeros")
        return {k: 0.0 for k in cols}

    return dict(zip(cols, [float(v) if v is not None else 0.0 for v in row]))


def _fetch_pff_team_matchup(db, home_team: str, away_team: str, season: int) -> dict:
    """
    Load all 32 teams' PFF grades for season-1, compute per-season 1-32 rankings,
    then return all 38 matchup features for the home vs away pairing.
    Falls back gracefully to zeros if no data exists for that season.
    """
    query = """
        SELECT
            o.team, o.overall_grade, o.offense_grade, o.passing_grade,
            o.pass_block_grade, o.run_grade,
            d.defense_grade, d.run_defense_grade, d.coverage_grade, d.pass_rush_grade,
            st.special_teams_grade
        FROM pff_team_offense o
        JOIN pff_team_defense d USING (team, season)
        JOIN pff_team_special_teams st USING (team, season)
        WHERE o.season = %s
    """
    cur = db.cursor()
    cur.execute(query, (season,))
    rows = cur.fetchall()
    cur.close()

    _zero = {
        'home_pff_offense': 0.0, 'away_pff_offense': 0.0,
        'home_pff_defense': 0.0, 'away_pff_defense': 0.0,
        'home_pff_run': 0.0, 'away_pff_run': 0.0,
        'home_pff_passing': 0.0, 'away_pff_passing': 0.0,
        'home_pff_run_defense': 0.0, 'away_pff_run_defense': 0.0,
        'home_pff_coverage': 0.0, 'away_pff_coverage': 0.0,
        'home_pff_pass_rush': 0.0, 'away_pff_pass_rush': 0.0,
        'home_pff_special_teams': 0.0, 'away_pff_special_teams': 0.0,
        'home_run_offense_rank': 16, 'away_run_offense_rank': 16,
        'home_pass_offense_rank': 16, 'away_pass_offense_rank': 16,
        'home_run_defense_rank': 16, 'away_run_defense_rank': 16,
        'home_pass_defense_rank': 16, 'away_pass_defense_rank': 16,
        'home_pass_rush_rank': 16, 'away_pass_rush_rank': 16,
        'home_special_teams_rank': 16, 'away_special_teams_rank': 16,
        'matchup_run_off_vs_run_def': 0.0, 'matchup_pass_off_vs_coverage': 0.0,
        'matchup_pass_rush_vs_pass_block': 0.0, 'matchup_overall_off_vs_def': 0.0,
        'matchup_special_teams': 0.0, 'pff_overall_diff': 0.0,
        'rank_adv_run_game': 0, 'rank_adv_pass_game': 0,
        'rank_adv_rush_pressure': 0, 'rank_adv_special_teams': 0,
        'pff_offense_diff': 0.0, 'pff_defense_diff': 0.0,
    }

    if not rows:
        logger.warning(f"No PFF team grades for season {prev}; using zeros")
        return _zero

    cols = [
        'team', 'overall_grade', 'offense_grade', 'passing_grade',
        'pass_block_grade', 'run_grade',
        'defense_grade', 'run_defense_grade', 'coverage_grade', 'pass_rush_grade',
        'special_teams_grade',
    ]
    # Build team lookup dict
    grades: dict[str, dict] = {}
    for row in rows:
        d = dict(zip(cols, row))
        grades[d['team'].upper()] = {k: float(v) if v is not None else 0.0
                                     for k, v in d.items() if k != 'team'}

    # Compute 1-32 ranks (rank 1 = highest grade = best)
    rank_specs = [
        ('run_grade',           'run_offense_rank'),
        ('passing_grade',       'pass_offense_rank'),
        ('run_defense_grade',   'run_defense_rank'),
        ('coverage_grade',      'pass_defense_rank'),
        ('pass_rush_grade',     'pass_rush_rank'),
        ('special_teams_grade', 'special_teams_rank'),
    ]
    for grade_col, rank_col in rank_specs:
        sorted_teams = sorted(grades.keys(),
                              key=lambda t: grades[t].get(grade_col, 0.0),
                              reverse=True)
        for rank, team in enumerate(sorted_teams, start=1):
            grades[team][rank_col] = rank

    # Normalize abbreviations to match PFF storage (e.g. JAC→JAX, LA→LAR)
    _GAMES_TO_PFF = {'JAC': 'JAX', 'LA': 'LAR'}
    home_pff_key = _GAMES_TO_PFF.get(home_team, home_team)
    away_pff_key = _GAMES_TO_PFF.get(away_team, away_team)
    hg = grades.get(home_pff_key, {})
    ag = grades.get(away_pff_key, {})

    def _g(d, k): return d.get(k, 0.0)
    def _r(d, k): return int(d.get(k, 16))

    h_off  = _g(hg, 'offense_grade');   a_off  = _g(ag, 'offense_grade')
    h_def  = _g(hg, 'defense_grade');   a_def  = _g(ag, 'defense_grade')
    h_run  = _g(hg, 'run_grade');       a_run  = _g(ag, 'run_grade')
    h_pass = _g(hg, 'passing_grade');   a_pass = _g(ag, 'passing_grade')
    h_rdef = _g(hg, 'run_defense_grade'); a_rdef = _g(ag, 'run_defense_grade')
    h_cov  = _g(hg, 'coverage_grade');  a_cov  = _g(ag, 'coverage_grade')
    h_pr   = _g(hg, 'pass_rush_grade'); a_pr   = _g(ag, 'pass_rush_grade')
    h_pb   = _g(hg, 'pass_block_grade'); a_pb  = _g(ag, 'pass_block_grade')
    h_st   = _g(hg, 'special_teams_grade'); a_st = _g(ag, 'special_teams_grade')
    h_ovr  = _g(hg, 'overall_grade');   a_ovr  = _g(ag, 'overall_grade')

    h_ror = _r(hg, 'run_offense_rank');  a_ror = _r(ag, 'run_offense_rank')
    h_por = _r(hg, 'pass_offense_rank'); a_por = _r(ag, 'pass_offense_rank')
    h_rdr = _r(hg, 'run_defense_rank');  a_rdr = _r(ag, 'run_defense_rank')
    h_pdr = _r(hg, 'pass_defense_rank'); a_pdr = _r(ag, 'pass_defense_rank')
    h_prr = _r(hg, 'pass_rush_rank');   a_prr = _r(ag, 'pass_rush_rank')
    h_str = _r(hg, 'special_teams_rank'); a_str = _r(ag, 'special_teams_rank')

    return {
        'home_pff_offense': h_off, 'away_pff_offense': a_off,
        'home_pff_defense': h_def, 'away_pff_defense': a_def,
        'home_pff_run': h_run,     'away_pff_run': a_run,
        'home_pff_passing': h_pass, 'away_pff_passing': a_pass,
        'home_pff_run_defense': h_rdef, 'away_pff_run_defense': a_rdef,
        'home_pff_coverage': h_cov, 'away_pff_coverage': a_cov,
        'home_pff_pass_rush': h_pr, 'away_pff_pass_rush': a_pr,
        'home_pff_special_teams': h_st, 'away_pff_special_teams': a_st,
        'home_run_offense_rank': h_ror,  'away_run_offense_rank': a_ror,
        'home_pass_offense_rank': h_por, 'away_pass_offense_rank': a_por,
        'home_run_defense_rank': h_rdr,  'away_run_defense_rank': a_rdr,
        'home_pass_defense_rank': h_pdr, 'away_pass_defense_rank': a_pdr,
        'home_pass_rush_rank': h_prr,    'away_pass_rush_rank': a_prr,
        'home_special_teams_rank': h_str, 'away_special_teams_rank': a_str,
        'matchup_run_off_vs_run_def':      (h_run - a_rdef) - (a_run - h_rdef),
        'matchup_pass_off_vs_coverage':    (h_pass - a_cov) - (a_pass - h_cov),
        'matchup_pass_rush_vs_pass_block': (h_pr - a_pb) - (a_pr - h_pb),
        'matchup_overall_off_vs_def':      (h_off - a_def) - (a_off - h_def),
        'matchup_special_teams':           h_st - a_st,
        'pff_overall_diff':                h_ovr - a_ovr,
        'rank_adv_run_game':       a_rdr - h_ror,
        'rank_adv_pass_game':      a_pdr - h_por,
        'rank_adv_rush_pressure':  a_por - h_prr,
        'rank_adv_special_teams':  a_str - h_str,
        'pff_offense_diff':        h_off - a_off,
        'pff_defense_diff':        h_def - a_def,
    }


def _fetch_player_impact(db, home_team: str, away_team: str, season: int) -> dict:
    """
    Average player impact scores per team for the season from game_id_mapping.
    Falls back to 0 if no data exists yet (e.g. upcoming season).
    """
    query = """
        SELECT
            AVG(CASE WHEN home_team = %s THEN home_avg_impact END) AS home_avg_impact,
            AVG(CASE WHEN away_team = %s THEN away_avg_impact END) AS away_avg_impact
        FROM game_id_mapping
        WHERE season = %s
          AND (home_team = %s OR away_team = %s)
    """
    cur = db.cursor()
    cur.execute(query, (home_team, away_team, season, home_team, away_team))
    row = cur.fetchone()
    cur.close()

    home_impact = float(row[0]) if row and row[0] is not None else 0.0
    away_impact = float(row[1]) if row and row[1] is not None else 0.0
    differential = home_impact - away_impact
    return {
        "home_avg_impact": home_impact,
        "away_avg_impact": away_impact,
        "avg_impact_differential": differential,
    }


# ---------------------------------------------------------------------------
# Feature vector builder
# ---------------------------------------------------------------------------

def _build_feature_vector(
    home_tr: dict,
    away_tr: dict,
    home_tf: dict,
    away_tf: dict,
    impact: dict,
    spread_line: float,
    div_game: int,
    feature_names: list[str],
    home_pff: dict | None = None,
    away_pff: dict | None = None,
    pff_matchup: dict | None = None,
) -> np.ndarray:
    """
    Assemble every feature in the exact column order from feature_names.json.
    Mirrors the logic in generate_training_data.py / engineer_features().
    home_pff / away_pff are optional; missing keys default to 0.
    """
    home_pff = home_pff or {}
    away_pff = away_pff or {}
    pff_matchup = pff_matchup or {}

    raw = {
        # Game-level
        "spread_line": spread_line,
        "div_game": div_game,

        # Player impact
        "home_avg_impact": impact["home_avg_impact"],
        "away_avg_impact": impact["away_avg_impact"],
        "avg_impact_differential": impact["avg_impact_differential"],

        # Home team rankings
        "home_win_rate": home_tr["win_rate"],
        "home_ppg": home_tr["avg_points_scored"],
        "home_papg": home_tr["avg_points_allowed"],
        "home_pt_diff": home_tr["point_differential"],
        "home_off_rank": home_tr["offensive_rank"],
        "home_def_rank": home_tr["defensive_rank"],
        "home_overall_rank": home_tr["overall_rank"],
        "home_ats_rate": home_tr["ats_cover_rate"],
        "home_avg_spread": home_tr["avg_spread_line"],

        # Away team rankings
        "away_win_rate": away_tr["win_rate"],
        "away_ppg": away_tr["avg_points_scored"],
        "away_papg": away_tr["avg_points_allowed"],
        "away_pt_diff": away_tr["point_differential"],
        "away_off_rank": away_tr["offensive_rank"],
        "away_def_rank": away_tr["defensive_rank"],
        "away_overall_rank": away_tr["overall_rank"],
        "away_ats_rate": away_tr["ats_cover_rate"],
        "away_avg_spread": away_tr["avg_spread_line"],

        # Home situational
        "home_at_home_wr": home_tf["home_win_rate"],
        "home_on_road_wr": home_tf["away_win_rate"],
        "home_home_adv": home_tf["home_advantage"],
        "home_div_wr": home_tf["div_win_rate"],
        "home_div_adv": home_tf["div_advantage"],
        "home_pt_wr": home_tf["prime_time_win_rate"],
        "home_vs_strong": home_tf["vs_strong_win_rate"],
        "home_vs_mid": home_tf["vs_mid_win_rate"],
        "home_vs_weak": home_tf["vs_weak_win_rate"],
        "home_close_ats": home_tf["close_game_ats_rate"],
        "home_after_loss_ats": home_tf["after_loss_ats_rate"],
        "home_after_bye_ats": home_tf["after_bye_ats_rate"],

        # Away situational
        "away_at_home_wr": away_tf["home_win_rate"],
        "away_on_road_wr": away_tf["away_win_rate"],
        "away_home_adv": away_tf["home_advantage"],
        "away_div_wr": away_tf["div_win_rate"],
        "away_div_adv": away_tf["div_advantage"],
        "away_pt_wr": away_tf["prime_time_win_rate"],
        "away_vs_strong": away_tf["vs_strong_win_rate"],
        "away_vs_mid": away_tf["vs_mid_win_rate"],
        "away_vs_weak": away_tf["vs_weak_win_rate"],
        "away_close_ats": away_tf["close_game_ats_rate"],
        "away_after_loss_ats": away_tf["after_loss_ats_rate"],
        "away_after_bye_ats": away_tf["after_bye_ats_rate"],

        # PFF grades — raw per team
        "home_def_grade":       home_pff.get("def_grade", 0.0),
        "home_pass_rush_grade": home_pff.get("pass_rush_grade", 0.0),
        "home_run_def_grade":   home_pff.get("run_def_grade", 0.0),
        "home_coverage_grade":  home_pff.get("coverage_grade", 0.0),
        "home_qb_grade":        home_pff.get("qb_grade", 0.0),
        "home_rb_grade":        home_pff.get("rb_grade", 0.0),
        "home_ol_pass_block":   home_pff.get("ol_pass_block", 0.0),
        "home_ol_run_block":    home_pff.get("ol_run_block", 0.0),
        "home_run_pass_ratio":  home_pff.get("off_run_pass_ratio", 0.0),

        "away_def_grade":       away_pff.get("def_grade", 0.0),
        "away_pass_rush_grade": away_pff.get("pass_rush_grade", 0.0),
        "away_run_def_grade":   away_pff.get("run_def_grade", 0.0),
        "away_coverage_grade":  away_pff.get("coverage_grade", 0.0),
        "away_qb_grade":        away_pff.get("qb_grade", 0.0),
        "away_rb_grade":        away_pff.get("rb_grade", 0.0),
        "away_ol_pass_block":   away_pff.get("ol_pass_block", 0.0),
        "away_ol_run_block":    away_pff.get("ol_run_block", 0.0),
        "away_run_pass_ratio":  away_pff.get("off_run_pass_ratio", 0.0),

        # Engineered differentials (mirrors generate_training_data.engineer_features)
        "ppg_diff": home_tr["avg_points_scored"] - away_tr["avg_points_scored"],
        "papg_diff": home_tr["avg_points_allowed"] - away_tr["avg_points_allowed"],
        "pt_diff_diff": home_tr["point_differential"] - away_tr["point_differential"],
        "win_rate_diff": home_tr["win_rate"] - away_tr["win_rate"],
        "off_rank_diff": away_tr["offensive_rank"] - home_tr["offensive_rank"],
        "def_rank_diff": away_tr["defensive_rank"] - home_tr["defensive_rank"],
        "overall_rank_diff": away_tr["overall_rank"] - home_tr["overall_rank"],
        "ats_rate_diff": home_tr["ats_cover_rate"] - away_tr["ats_cover_rate"],
        "vs_strong_diff": home_tf["vs_strong_win_rate"] - away_tf["vs_strong_win_rate"],
        "vs_weak_diff": home_tf["vs_weak_win_rate"] - away_tf["vs_weak_win_rate"],
        "pt_wr_diff": home_tf["prime_time_win_rate"] - away_tf["prime_time_win_rate"],
        "close_ats_diff": home_tf["close_game_ats_rate"] - away_tf["close_game_ats_rate"],

        # PFF differentials
        "def_grade_diff":     home_pff.get("def_grade", 0.0)       - away_pff.get("def_grade", 0.0),
        "pass_rush_diff":     home_pff.get("pass_rush_grade", 0.0) - away_pff.get("pass_rush_grade", 0.0),
        "run_def_diff":       home_pff.get("run_def_grade", 0.0)   - away_pff.get("run_def_grade", 0.0),
        "coverage_diff":      home_pff.get("coverage_grade", 0.0)  - away_pff.get("coverage_grade", 0.0),
        "qb_grade_diff":      home_pff.get("qb_grade", 0.0)        - away_pff.get("qb_grade", 0.0),
        "rb_grade_diff":      home_pff.get("rb_grade", 0.0)        - away_pff.get("rb_grade", 0.0),
        "ol_pass_block_diff": home_pff.get("ol_pass_block", 0.0)   - away_pff.get("ol_pass_block", 0.0),
        "ol_run_block_diff":  home_pff.get("ol_run_block", 0.0)    - away_pff.get("ol_run_block", 0.0),

        # Matchup interactions (player-aggregated, Enhancement 1)
        "matchup_away_pass_vs_home_cov": away_pff.get("qb_grade", 0.0)        - home_pff.get("coverage_grade", 0.0),
        "matchup_away_run_vs_home_rdef": away_pff.get("rb_grade", 0.0)        - home_pff.get("run_def_grade", 0.0),
        "matchup_home_pass_vs_away_cov": home_pff.get("qb_grade", 0.0)        - away_pff.get("coverage_grade", 0.0),
        "matchup_home_run_vs_away_rdef": home_pff.get("rb_grade", 0.0)        - away_pff.get("run_def_grade", 0.0),

        # Team-level PFF matchup features (Enhancement 2 — from pff_team_grades)
        **{k: pff_matchup.get(k, 0.0) for k in [
            'home_pff_offense', 'away_pff_offense',
            'home_pff_defense', 'away_pff_defense',
            'home_pff_run', 'away_pff_run',
            'home_pff_passing', 'away_pff_passing',
            'home_pff_run_defense', 'away_pff_run_defense',
            'home_pff_coverage', 'away_pff_coverage',
            'home_pff_pass_rush', 'away_pff_pass_rush',
            'home_pff_special_teams', 'away_pff_special_teams',
            'home_run_offense_rank', 'away_run_offense_rank',
            'home_pass_offense_rank', 'away_pass_offense_rank',
            'home_run_defense_rank', 'away_run_defense_rank',
            'home_pass_defense_rank', 'away_pass_defense_rank',
            'home_pass_rush_rank', 'away_pass_rush_rank',
            'home_special_teams_rank', 'away_special_teams_rank',
            'matchup_run_off_vs_run_def', 'matchup_pass_off_vs_coverage',
            'matchup_pass_rush_vs_pass_block', 'matchup_overall_off_vs_def',
            'matchup_special_teams', 'pff_overall_diff',
            'rank_adv_run_game', 'rank_adv_pass_game',
            'rank_adv_rush_pressure', 'rank_adv_special_teams',
            'pff_offense_diff', 'pff_defense_diff',
        ]},
    }

    # Build array in strict feature_names order, defaulting unknown keys to 0
    vector = np.array([raw.get(f, 0.0) for f in feature_names], dtype=np.float32)
    return vector


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    """
    Event format (direct invoke or API Gateway):
    {
        "home_team":  "BAL",
        "away_team":  "BUF",
        "spread_line": -2.5,   # negative = home team favored
        "div_game":   false,
        "season":     2025
    }

    Response:
    {
        "predicted_margin":  3.4,
        "spread_line":      -2.5,
        "model_pick":       "home",   # which side the model says covers
        "confidence_pts":    5.9,     # |predicted_margin - spread_line|
        "home_team":        "BAL",
        "away_team":        "BUF"
    }
    """
    global _model, _feature_names

    try:
        # Handle API Gateway wrapper
        if "body" in event:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        else:
            body = event

        home_team = body["home_team"].upper()
        away_team = body["away_team"].upper()
        spread_line = float(body["spread_line"])
        div_game = int(bool(body.get("div_game", False)))
        season = int(body.get("season", 2025))

        # Cold start: load model + connect DB
        if _model is None:
            _model, _feature_names = _load_model_from_s3()

        db = _get_db_connection()

        # Fetch features from Supabase
        home_tr = _fetch_team_rankings(db, home_team, season)
        away_tr = _fetch_team_rankings(db, away_team, season)
        home_tf = _fetch_team_season_features(db, home_team, season)
        away_tf = _fetch_team_season_features(db, away_team, season)
        impact = _fetch_player_impact(db, home_team, away_team, season)
        home_pff = _fetch_pff_profile(db, home_team, season)
        away_pff = _fetch_pff_profile(db, away_team, season)
        pff_matchup = _fetch_pff_team_matchup(db, home_team, away_team, season)

        # Build feature vector
        vector = _build_feature_vector(
            home_tr, away_tr, home_tf, away_tf,
            impact, spread_line, div_game, _feature_names,
            home_pff=home_pff, away_pff=away_pff,
            pff_matchup=pff_matchup,
        )

        # Predict
        predicted_margin = float(_model.predict(vector.reshape(1, -1))[0])
        confidence_pts = abs(predicted_margin - spread_line)

        # ATS pick: if predicted margin > spread_line, home covers
        if predicted_margin > spread_line:
            model_pick = "home"
            pick_team = home_team
        else:
            model_pick = "away"
            pick_team = away_team

        logger.info(
            f"{away_team} @ {home_team} | spread={spread_line} | "
            f"predicted_margin={predicted_margin:.2f} | pick={pick_team} | conf={confidence_pts:.2f}pts"
        )

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "success": True,
                "home_team": home_team,
                "away_team": away_team,
                "spread_line": spread_line,
                "predicted_margin": round(predicted_margin, 2),
                "model_pick": model_pick,
                "pick_team": pick_team,
                "confidence_pts": round(confidence_pts, 2),
                "season": season,
                "features_used": len(_feature_names),
            }),
        }

    except KeyError as e:
        logger.error(f"Missing required field: {e}")
        return {
            "statusCode": 400,
            "body": json.dumps({"success": False, "error": f"Missing field: {e}"}),
        }
    except Exception as e:
        logger.error(f"Prediction failed: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"success": False, "error": str(e)}),
        }
