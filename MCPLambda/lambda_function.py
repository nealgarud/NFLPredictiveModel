"""
MCPLambda — MCP Tool Server
============================
Receives tool call requests from BedrockChatLambda, routes to the correct
internal function, queries Supabase, and returns structured data.

Event format:
    {
        "tool_name": "get_player_game_stats",
        "parameters": { ... }
    }

Available tools:
    get_player_game_stats     — per-game stats for a player vs an opponent
    get_team_season_metrics   — team ATS + performance metrics by season
    get_game_context          — game result, spread, scores, impact flags
    get_matchup_analysis      — PFF matchup differentials for a specific game
    get_position_grades       — PFF position grades for a team/season
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

import pg8000

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AVAILABLE_TOOLS = (
    "get_player_game_stats, get_team_season_metrics, get_game_context, "
    "get_matchup_analysis, get_position_grades"
)

# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

def _get_connection() -> pg8000.Connection:
    conn = pg8000.connect(
        host=os.environ.get("SUPABASE_DB_HOST", "").strip(),
        port=int(os.environ.get("SUPABASE_DB_PORT", 5432)),
        database=os.environ.get("SUPABASE_DB_NAME", "").strip(),
        user=os.environ.get("SUPABASE_DB_USER", "").strip(),
        password=os.environ.get("SUPABASE_DB_PASSWORD", "").strip(),
        ssl_context=True,
    )
    conn.autocommit = True
    return conn


def _rows_to_dicts(cursor) -> List[Dict[str, Any]]:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def _ok(tool_name: str, data: Any, row_count: int = 0) -> Dict:
    return {
        "success": True,
        "tool_name": tool_name,
        "data": data,
        "row_count": row_count,
        "error": None,
    }


def _err(tool_name: str, message: str) -> Dict:
    return {
        "success": False,
        "tool_name": tool_name,
        "data": None,
        "row_count": 0,
        "error": message,
    }


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------

def lambda_handler(event: Dict, context: Any) -> Dict:
    logger.info("MCPLambda event: %s", json.dumps(event, default=str))

    tool_name  = event.get("tool_name", "unknown")
    parameters = event.get("parameters", {})

    router = {
        "get_player_game_stats":   _get_player_game_stats,
        "get_team_season_metrics": _get_team_season_metrics,
        "get_game_context":        _get_game_context,
        "get_matchup_analysis":    _get_matchup_analysis,
        "get_position_grades":     _get_position_grades,
    }

    if tool_name not in router:
        return {
            "success":   False,
            "tool_name": "unknown",
            "error": (
                f"Tool not recognized. Available tools: {AVAILABLE_TOOLS}"
            ),
            "data": None,
        }

    try:
        return router[tool_name](parameters)
    except Exception as e:
        logger.error("Tool %s failed: %s", tool_name, e, exc_info=True)
        return _err(tool_name, str(e))


# ---------------------------------------------------------------------------
# Tool: get_player_game_stats
# ---------------------------------------------------------------------------

def _get_player_game_stats(params: Dict) -> Dict:
    """
    Per-game stats for a player vs an opponent, with win/loss averages.

    Parameters:
        player_name   (str)       — case-insensitive partial or full name
        opponent_team (str)       — 3-letter team abbreviation
        seasons       (list[int]) — e.g. [2022, 2023]
        stat_types    (list[str]) — any of: passing, rushing, receiving
        result_filter (str)       — "win", "loss", or "all"
    """
    TOOL = "get_player_game_stats"

    player_name   = params.get("player_name", "")
    opponent_team = params.get("opponent_team", "")
    seasons       = params.get("seasons", [])
    stat_types    = params.get("stat_types", ["passing", "rushing", "receiving"])
    result_filter = params.get("result_filter", "all").lower()

    if not player_name:
        return _err(TOOL, "player_name is required")
    if not seasons:
        return _err(TOOL, "seasons list is required")

    # Build stat column selection based on stat_types
    stat_cols: List[str] = ["pgs.game_id", "pgs.season", "pgs.week",
                             "pgs.team", "pgs.position",
                             "pgs.actual_impact_score", "pgs.pff_grade",
                             "pgs.performance_multiplier",
                             "g.home_team", "g.away_team",
                             "g.home_score", "g.away_score",
                             "g.spread_line"]

    if "passing" in stat_types:
        stat_cols += [
            "pgs.pass_attempts", "pgs.pass_completions", "pgs.pass_yards",
            "pgs.pass_touchdowns", "pgs.pass_interceptions",
            "pgs.pass_air_yards", "pgs.sacks_taken", "pgs.avg_pocket_time",
            "pgs.times_blitzed", "pgs.times_hurried",
        ]
    if "rushing" in stat_types:
        stat_cols += [
            "pgs.rush_attempts", "pgs.rush_yards", "pgs.rush_touchdowns",
            "pgs.rush_first_downs", "pgs.rush_yards_after_contact",
            "pgs.rush_broken_tackles", "pgs.scrambles",
        ]
    if "receiving" in stat_types:
        stat_cols += [
            "pgs.targets", "pgs.receptions", "pgs.receiving_yards",
            "pgs.receiving_touchdowns", "pgs.yards_after_catch", "pgs.drops",
        ]

    season_placeholders = ", ".join(["%s"] * len(seasons))
    where_clauses = [
        "LOWER(pgs.player_name) LIKE LOWER(%s)",
        f"pgs.season IN ({season_placeholders})",
        "(g.home_team = %s OR g.away_team = %s)",
        "pgs.team != %s",  # exclude games where the player's team IS the opponent
    ]
    bind: List[Any] = [f"%{player_name}%", *seasons, opponent_team, opponent_team, opponent_team]

    # Win/loss filter: derive result from scores relative to player's team
    result_expr = ""
    if result_filter == "win":
        result_expr = (
            " AND ((pgs.team = g.home_team AND g.home_score > g.away_score) OR "
            "      (pgs.team = g.away_team AND g.away_score > g.home_score))"
        )
    elif result_filter == "loss":
        result_expr = (
            " AND ((pgs.team = g.home_team AND g.home_score < g.away_score) OR "
            "      (pgs.team = g.away_team AND g.away_score < g.home_score))"
        )

    sql = (
        f"SELECT {', '.join(stat_cols)} "
        "FROM player_game_stats pgs "
        "JOIN games g ON pgs.game_id = g.game_id "
        f"WHERE {' AND '.join(where_clauses)}"
        f"{result_expr} "
        "ORDER BY pgs.season DESC, pgs.week DESC"
    )

    conn   = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, tuple(bind))
        rows = _rows_to_dicts(cursor)
    finally:
        cursor.close()
        conn.close()

    # Compute win/loss averages for numeric columns
    def _avg(subset, col):
        vals = [r[col] for r in subset if r.get(col) is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    numeric_cols = [
        c.split(".")[-1] for c in stat_cols
        if c.startswith("pgs.") and c not in
        ("pgs.game_id", "pgs.team", "pgs.position")
    ]

    def _is_win(r):
        return (
            (r["team"] == r["home_team"] and (r["home_score"] or 0) > (r["away_score"] or 0)) or
            (r["team"] == r["away_team"] and (r["away_score"] or 0) > (r["home_score"] or 0))
        )

    wins   = [r for r in rows if _is_win(r)]
    losses = [r for r in rows if not _is_win(r)]

    averages = {
        "overall": {c: _avg(rows,   c) for c in numeric_cols},
        "wins":    {c: _avg(wins,   c) for c in numeric_cols},
        "losses":  {c: _avg(losses, c) for c in numeric_cols},
        "game_count": {"overall": len(rows), "wins": len(wins), "losses": len(losses)},
    }

    return _ok(TOOL, {"games": rows, "averages": averages}, row_count=len(rows))


# ---------------------------------------------------------------------------
# Tool: get_team_season_metrics
# ---------------------------------------------------------------------------

def _get_team_season_metrics(params: Dict) -> Dict:
    """
    Team ATS + performance metrics from team_season_features.

    Parameters:
        team          (str)            — 3-letter abbreviation
        seasons       (list[int])
        metric_filter (str, optional)  — "primetime", "division", "bye",
                                         "close_game", "vs_strong", "vs_weak"
    """
    TOOL = "get_team_season_metrics"

    team          = params.get("team", "")
    seasons       = params.get("seasons", [])
    metric_filter = params.get("metric_filter", "").lower()

    if not team or not seasons:
        return _err(TOOL, "team and seasons are required")

    # Column groups by filter keyword
    FILTER_COLS: Dict[str, List[str]] = {
        "primetime": ["primetime_win_rate", "primetime_ats_rate",
                      "primetime_games", "primetime_wins"],
        "division":  ["div_win_rate", "div_ats_rate", "div_games",
                      "div_wins", "home_div_wr", "away_div_wr"],
        "bye":       ["after_bye_ats", "after_bye_wins", "after_bye_games"],
        "close_game":["close_ats", "close_win_rate", "close_games"],
        "vs_strong": ["vs_strong_ats", "vs_strong_wins", "vs_strong_games",
                      "home_vs_strong", "away_vs_strong"],
        "vs_weak":   ["vs_weak_ats", "vs_weak_wins", "vs_weak_games",
                      "home_vs_weak", "away_vs_weak"],
    }

    if metric_filter and metric_filter in FILTER_COLS:
        base_cols = ["team", "season"] + FILTER_COLS[metric_filter]
        select    = ", ".join(base_cols)
    else:
        select = "*"

    season_placeholders = ", ".join(["%s"] * len(seasons))
    sql = (
        f"SELECT {select} FROM team_season_features "
        f"WHERE team = %s AND season IN ({season_placeholders}) "
        "ORDER BY season DESC"
    )

    conn   = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (team, *seasons))
        rows = _rows_to_dicts(cursor)
    finally:
        cursor.close()
        conn.close()

    return _ok(TOOL, rows, row_count=len(rows))


# ---------------------------------------------------------------------------
# Tool: get_game_context
# ---------------------------------------------------------------------------

def _get_game_context(params: Dict) -> Dict:
    """
    Game result, spread, scores, div_game, impact flags from games + game_id_mapping.

    Parameters:
        home_team (str)
        away_team (str)
        season    (int)
        week      (int, optional)
    """
    TOOL = "get_game_context"

    home_team = params.get("home_team", "")
    away_team = params.get("away_team", "")
    season    = params.get("season")
    week      = params.get("week")

    if not home_team or not away_team or not season:
        return _err(TOOL, "home_team, away_team, and season are required")

    where  = ["g.home_team = %s", "g.away_team = %s", "g.season = %s"]
    bind: List[Any] = [home_team, away_team, season]
    if week:
        where.append("g.week = %s")
        bind.append(week)

    sql = """
        SELECT
            g.game_id, g.season, g.week, g.game_date,
            g.home_team, g.away_team,
            g.home_score, g.away_score,
            g.spread_line, g.div_game,
            (g.home_score - g.away_score)            AS actual_margin,
            (g.home_score - g.away_score - g.spread_line) AS ats_result,
            gm.home_tier_1_count, gm.home_tier_2_count,
            gm.home_tier_3_count, gm.home_tier_4_count, gm.home_tier_5_count,
            gm.away_tier_1_count, gm.away_tier_2_count,
            gm.away_tier_3_count, gm.away_tier_4_count, gm.away_tier_5_count,
            gm.home_qb1_active, gm.home_rb1_active, gm.home_wr1_active,
            gm.home_edge1_active, gm.home_cb1_active,
            gm.away_qb1_active, gm.away_rb1_active, gm.away_wr1_active,
            gm.away_edge1_active, gm.away_cb1_active,
            gm.home_actual_game_impact, gm.away_actual_game_impact,
            gm.home_performance_surprise, gm.away_performance_surprise,
            gm.performance_surprise_diff,
            gm.home_offense_impact, gm.home_defense_impact, gm.home_ol_impact,
            gm.away_offense_impact, gm.away_defense_impact, gm.away_ol_impact
        FROM games g
        LEFT JOIN game_id_mapping gm ON g.game_id = gm.game_id
        WHERE """ + " AND ".join(where) + """
        ORDER BY g.week DESC
    """

    conn   = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, tuple(bind))
        rows = _rows_to_dicts(cursor)
    finally:
        cursor.close()
        conn.close()

    return _ok(TOOL, rows, row_count=len(rows))


# ---------------------------------------------------------------------------
# Tool: get_matchup_analysis
# ---------------------------------------------------------------------------

def _get_matchup_analysis(params: Dict) -> Dict:
    """
    PFF matchup differentials, grades, and rank advantages for a specific game.

    Parameters:
        home_team (str)
        away_team (str)
        season    (int)
    """
    TOOL = "get_matchup_analysis"

    home_team = params.get("home_team", "")
    away_team = params.get("away_team", "")
    season    = params.get("season")

    if not home_team or not away_team or not season:
        return _err(TOOL, "home_team, away_team, and season are required")

    sql = """
        SELECT
            game_id, season, week, home_team, away_team,
            -- Matchup differentials
            matchup_run_off_vs_run_def,
            matchup_pass_off_vs_coverage,
            matchup_pass_rush_vs_pass_block,
            matchup_overall_off_vs_def,
            matchup_special_teams,
            pff_overall_diff,
            -- PFF grades — home
            home_pff_offense, home_pff_defense, home_pff_run,
            home_pff_passing, home_pff_coverage, home_pff_pass_rush,
            home_pff_special_teams,
            -- PFF grades — away
            away_pff_offense, away_pff_defense, away_pff_run,
            away_pff_passing, away_pff_coverage, away_pff_pass_rush,
            away_pff_special_teams,
            -- Team rankings
            home_run_offense_rank, home_pass_offense_rank,
            home_run_defense_rank, home_pass_defense_rank,
            home_pass_rush_rank,   home_special_teams_rank,
            away_run_offense_rank, away_pass_offense_rank,
            away_run_defense_rank, away_pass_defense_rank,
            away_pass_rush_rank,   away_special_teams_rank
        FROM game_id_mapping
        WHERE home_team = %s AND away_team = %s AND season = %s
        ORDER BY week DESC
    """

    conn   = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (home_team, away_team, season))
        rows = _rows_to_dicts(cursor)
    finally:
        cursor.close()
        conn.close()

    return _ok(TOOL, rows, row_count=len(rows))


# ---------------------------------------------------------------------------
# Tool: get_position_grades
# ---------------------------------------------------------------------------

_POSITION_TABLES: Dict[str, str] = {
    "QB":  "qb_pff_ratings",
    "RB":  "rb_pff_ratings",
    "WR":  "wr_pff_ratings",
    "OL":  "oline_pff_ratings",
    "DEF": "defense_pff_ratings",
}


def _get_position_grades(params: Dict) -> Dict:
    """
    PFF position grades for a team filtered by seasons.

    Parameters:
        team           (str)       — 3-letter abbreviation
        position_group (str)       — QB, RB, WR, OL, DEF
        seasons        (list[int])
    """
    TOOL = "get_position_grades"

    team           = params.get("team", "")
    position_group = params.get("position_group", "").upper()
    seasons        = params.get("seasons", [])

    if not team or not position_group or not seasons:
        return _err(TOOL, "team, position_group, and seasons are required")

    if position_group not in _POSITION_TABLES:
        return _err(
            TOOL,
            f"position_group must be one of: {', '.join(_POSITION_TABLES.keys())}",
        )

    table               = _POSITION_TABLES[position_group]
    season_placeholders = ", ".join(["%s"] * len(seasons))

    # team_name column is consistent across all PFF rating tables
    sql = (
        f"SELECT * FROM {table} "
        f"WHERE team_name = %s AND season IN ({season_placeholders}) "
        "ORDER BY season DESC, snap_counts_offense DESC NULLS LAST, "
        "snap_counts_defense DESC NULLS LAST"
    )

    conn   = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (team, *seasons))
        rows = _rows_to_dicts(cursor)
    finally:
        cursor.close()
        conn.close()

    return _ok(TOOL, rows, row_count=len(rows))
