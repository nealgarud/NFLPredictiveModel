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
) -> np.ndarray:
    """
    Assemble every feature in the exact column order from feature_names.json.
    Mirrors the logic in generate_training_data.py / engineer_features().
    """
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

        # Build feature vector
        vector = _build_feature_vector(
            home_tr, away_tr, home_tf, away_tf,
            impact, spread_line, div_game, _feature_names,
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
