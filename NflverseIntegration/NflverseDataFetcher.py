"""
NflverseDataFetcher
===================
Pulls per-game advanced metrics from nflverse (via nflreadpy), transforms them,
and upserts into Supabase tables:
  - nflverse_qb_stats
  - nflverse_rb_stats
  - nflverse_wr_stats
  - nflverse_def_stats

Connection uses pg8000 (same pattern as playerimpact Lambda).

Environment variables required:
  SUPABASE_DB_HOST, SUPABASE_DB_NAME, SUPABASE_DB_USER,
  SUPABASE_DB_PASSWORD, SUPABASE_DB_PORT
"""

import os
import logging
from typing import Optional

import pg8000
import nflreadpy as nfl

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ── DB connection ─────────────────────────────────────────────────────────────

def _get_conn():
    return pg8000.connect(
        host=os.environ["SUPABASE_DB_HOST"],
        database=os.environ["SUPABASE_DB_NAME"],
        user=os.environ["SUPABASE_DB_USER"],
        password=os.environ["SUPABASE_DB_PASSWORD"],
        port=int(os.environ.get("SUPABASE_DB_PORT", 5432)),
        timeout=120,
        ssl_context=True,
    )


_BATCH_SIZE = 100   # rows per commit+reconnect — keeps each socket session well under timeout


def _write_in_batches(rows: list, table: str, conflict_cols: tuple) -> int:
    """
    Upsert `rows` (list of dicts, all same keys) into `table`.
    Reconnects every _BATCH_SIZE rows so no single connection stays open too long.
    Returns total rows upserted.
    """
    if not rows:
        return 0

    cols        = list(rows[0].keys())
    placeholders = ", ".join(["%s"] * len(cols))
    col_names    = ", ".join(cols)
    updates      = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols
                             if c not in conflict_cols)
    conflict     = ", ".join(conflict_cols)
    sql = (
        f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) "
        f"ON CONFLICT ({conflict}) DO UPDATE SET {updates}"
    )

    upserted = 0
    conn = cur = None

    for i, row in enumerate(rows):
        if i % _BATCH_SIZE == 0:
            if conn is not None:
                conn.commit(); cur.close(); conn.close()
            conn = _get_conn()
            cur  = conn.cursor()
            cur.execute("SET statement_timeout = 0")  # override Supabase default

        cur.execute(sql, [row[c] for c in cols])
        upserted += 1

    if conn is not None:
        conn.commit(); cur.close(); conn.close()

    return upserted


def _safe(val, cast=None):
    """Return None if val is NaN/None, otherwise cast and return."""
    if val is None:
        return None
    try:
        import math
        if isinstance(val, float) and math.isnan(val):
            return None
    except Exception:
        pass
    return cast(val) if cast else val


# =============================================================================
# QB — fetch, transform, store, query
# =============================================================================

def fetch_and_store_qb_stats(seasons: list, weeks: list = None) -> int:
    """
    Pull QB stats from nflverse for the given seasons (and optional week filter),
    transform to our schema, and upsert into nflverse_qb_stats.
    Returns total rows upserted.
    """
    df = nfl.load_player_stats(seasons)
    qb_df = df.filter((df["position"] == "QB") & (df["week"] <= 18))

    if weeks:
        qb_df = qb_df.filter(qb_df["week"].is_in(weeks))

    rows_to_write = []
    for g in qb_df.iter_rows(named=True):
        atts     = _safe(g.get("attempts"), int)        or 0
        sacks    = _safe(g.get("sacks_suffered"), int)  or 0
        py       = _safe(g.get("passing_yards"), float) or 0.0
        pay      = _safe(g.get("passing_air_yards"), float) or 0.0
        epa      = _safe(g.get("passing_epa"), float)   or 0.0
        dropbacks = atts + sacks

        ypa  = round(py  / atts,     2) if atts > 0     else None
        adot = round(pay / atts,     2) if atts > 0     else None
        epd  = round(epa / dropbacks, 4) if dropbacks > 0 else None

        rows_to_write.append({
            "player_id":                 _safe(g.get("player_id")),
            "player_name":               _safe(g.get("player_display_name")),
            "team":                      _safe(g.get("recent_team")),
            "season":                    _safe(g.get("season"), int),
            "week":                      _safe(g.get("week"), int),
            "completions":               _safe(g.get("completions"), int),
            "attempts":                  atts,
            "passing_yards":             _safe(g.get("passing_yards"), int),
            "passing_tds":               _safe(g.get("passing_tds"), int),
            "passing_interceptions":     _safe(g.get("passing_interceptions"), int),
            "sacks_suffered":            sacks,
            "sack_yards_lost":           _safe(g.get("sack_yards_lost"), int),
            "passing_air_yards":         _safe(g.get("passing_air_yards"), int),
            "passing_yards_after_catch": _safe(g.get("passing_yards_after_catch"), int),
            "passing_first_downs":       _safe(g.get("passing_first_downs"), int),
            "passing_epa":               _safe(g.get("passing_epa"), float),
            "passing_cpoe":              _safe(g.get("passing_cpoe"), float),
            "pacr":                      _safe(g.get("pacr"), float),
            "carries":                   _safe(g.get("carries"), int),
            "rushing_yards":             _safe(g.get("rushing_yards"), int),
            "rushing_tds":               _safe(g.get("rushing_tds"), int),
            "rushing_epa":               _safe(g.get("rushing_epa"), float),
            "rushing_first_downs":       _safe(g.get("rushing_first_downs"), int),
            "cpoe":                      _safe(g.get("passing_cpoe"), float),
            "ypa":                       ypa,
            "adot":                      adot,
            "epa_per_dropback":          epd,
            "opponent":                  _safe(g.get("opponent_team")),
            "game_id":                   _safe(g.get("game_id")),
        })

    upserted = _write_in_batches(rows_to_write, "nflverse_qb_stats",
                                 conflict_cols=("player_id", "season", "week"))
    logger.info("nflverse_qb_stats: upserted %d rows", upserted)
    return upserted


def get_qb_game_stats(player_name: str, team: str, season: int, week: int) -> Optional[dict]:
    """Return a single QB's nflverse game row as a dict, or None."""
    conn = _get_conn()
    cur  = conn.cursor()
    cur.execute(
        """
        SELECT * FROM nflverse_qb_stats
        WHERE player_name = %s AND team = %s AND season = %s AND week = %s
        LIMIT 1
        """,
        [player_name, team, season, week],
    )
    row  = cur.fetchone()
    cols = [d[0] for d in cur.description]
    cur.close()
    conn.close()
    return dict(zip(cols, row)) if row else None


def get_qb_rolling_baseline(
    player_name: str, team: str, season: int, current_week: int, window: int = 5
) -> Optional[dict]:
    """Aggregate nflverse QB stats from the last `window` weeks before current_week."""
    conn = _get_conn()
    cur  = conn.cursor()
    cur.execute(
        """
        SELECT
            AVG(passing_cpoe)       AS cpoe,
            SUM(passing_epa)        AS passing_epa,
            SUM(passing_air_yards)  AS passing_air_yards,
            SUM(attempts)           AS attempts,
            AVG(rushing_yards)      AS rushing_yards,
            AVG(sacks_suffered)     AS sacks
        FROM nflverse_qb_stats
        WHERE player_name = %s AND season = %s AND week < %s
        ORDER BY week DESC
        LIMIT %s
        """,
        [player_name, season, current_week, window],
    )
    row  = cur.fetchone()
    cols = [d[0] for d in cur.description]
    cur.close()
    conn.close()
    return dict(zip(cols, row)) if row else None


# =============================================================================
# RB — fetch, transform, store, query
# =============================================================================

def fetch_and_store_rb_stats(seasons: list, weeks: list = None) -> int:
    """
    Pull RB stats from nflverse for the given seasons (and optional week filter),
    transform to our schema, and upsert into nflverse_rb_stats.
    Returns total rows upserted.
    """
    df = nfl.load_player_stats(seasons)
    rb_df = df.filter((df["position"] == "RB") & (df["week"] <= 18))

    if weeks:
        rb_df = rb_df.filter(rb_df["week"].is_in(weeks))

    rows_to_write = []
    for g in rb_df.iter_rows(named=True):
        carries   = _safe(g.get("carries"),              int)   or 0
        rush_yds  = _safe(g.get("rushing_yards"),        float) or 0.0
        rush_epa  = _safe(g.get("rushing_epa"),          float) or 0.0
        rush_fds  = _safe(g.get("rushing_first_downs"),  int)   or 0
        recv_epa  = _safe(g.get("receiving_epa"),        float) or 0.0
        recv_yds  = _safe(g.get("receiving_yards"),      int)   or 0
        rush_tds  = _safe(g.get("rushing_tds"),          int)   or 0
        recv_tds  = _safe(g.get("receiving_tds"),        int)   or 0

        ypc           = round(rush_yds / carries, 2)          if carries > 0 else None
        epa_per_carry = round(rush_epa / carries, 4)          if carries > 0 else None
        fd_rate       = round(rush_fds / carries, 4)          if carries > 0 else None
        total_epa     = round((rush_epa or 0) + (recv_epa or 0), 3)
        total_yards   = (int(rush_yds) if rush_yds else 0) + (recv_yds or 0)
        total_tds     = (rush_tds or 0) + (recv_tds or 0)

        rows_to_write.append({
            "player_id":                    _safe(g.get("player_id")),
            "player_name":                  _safe(g.get("player_display_name")),
            "team":                         _safe(g.get("recent_team")),
            "season":                       _safe(g.get("season"), int),
            "week":                         _safe(g.get("week"), int),
            "carries":                      carries,
            "rushing_yards":                _safe(g.get("rushing_yards"), int),
            "rushing_tds":                  rush_tds,
            "rushing_fumbles":              _safe(g.get("rushing_fumbles"), int),
            "rushing_fumbles_lost":         _safe(g.get("rushing_fumbles_lost"), int),
            "rushing_first_downs":          rush_fds,
            "rushing_epa":                  rush_epa,
            "receptions":                   _safe(g.get("receptions"), int),
            "targets":                      _safe(g.get("targets"), int),
            "receiving_yards":              recv_yds,
            "receiving_tds":                recv_tds,
            "receiving_air_yards":          _safe(g.get("receiving_air_yards"), int),
            "receiving_yards_after_catch":  _safe(g.get("receiving_yards_after_catch"), int),
            "receiving_first_downs":        _safe(g.get("receiving_first_downs"), int),
            "receiving_epa":                recv_epa,
            "receiving_fumbles_lost":       _safe(g.get("receiving_fumbles_lost"), int),
            "target_share":                 _safe(g.get("target_share"), float),
            "wopr":                         _safe(g.get("wopr"), float),
            "ypc":                          ypc,
            "epa_per_carry":                epa_per_carry,
            "fd_rate":                      fd_rate,
            "total_epa":                    total_epa,
            "total_yards":                  total_yards,
            "total_tds":                    total_tds,
            "opponent":                     _safe(g.get("opponent_team")),
            "game_id":                      _safe(g.get("game_id")),
        })

    upserted = _write_in_batches(rows_to_write, "nflverse_rb_stats",
                                 conflict_cols=("player_id", "season", "week"))
    logger.info("nflverse_rb_stats: upserted %d rows", upserted)
    return upserted


def get_rb_game_stats(player_name: str, team: str, season: int, week: int) -> Optional[dict]:
    """Return a single RB's nflverse game row as a dict, or None."""
    conn = _get_conn()
    cur  = conn.cursor()
    cur.execute(
        """
        SELECT * FROM nflverse_rb_stats
        WHERE player_name = %s AND team = %s AND season = %s AND week = %s
        LIMIT 1
        """,
        [player_name, team, season, week],
    )
    row  = cur.fetchone()
    cols = [d[0] for d in cur.description]
    cur.close()
    conn.close()
    return dict(zip(cols, row)) if row else None


def get_rb_rolling_baseline(
    player_name: str, team: str, season: int, current_week: int, window: int = 5
) -> Optional[dict]:
    """
    Aggregate nflverse RB stats from up to the last `window` weeks before current_week.
    Returns sums/avgs in the same shape as nv_base expected by calc_rb_multiplier_enhanced.
    """
    conn = _get_conn()
    cur  = conn.cursor()
    cur.execute(
        """
        SELECT
            SUM(carries)                AS carries,
            SUM(rushing_yards)          AS rushing_yards,
            SUM(rushing_epa)            AS rushing_epa,
            SUM(rushing_first_downs)    AS rushing_first_downs,
            AVG(receiving_yards)        AS avg_receiving_yards,
            SUM(receiving_epa)          AS receiving_epa,
            SUM(rushing_fumbles_lost)   AS rushing_fumbles_lost,
            SUM(receiving_fumbles_lost) AS receiving_fumbles_lost
        FROM (
            SELECT * FROM nflverse_rb_stats
            WHERE player_name = %s AND season = %s AND week < %s
            ORDER BY week DESC
            LIMIT %s
        ) recent
        """,
        [player_name, season, current_week, window],
    )
    row  = cur.fetchone()
    cols = [d[0] for d in cur.description]
    cur.close()
    conn.close()
    return dict(zip(cols, row)) if row else None


# =============================================================================
# WR/TE — fetch, transform, store, query
# =============================================================================

def fetch_and_store_wr_stats(seasons: list, weeks: list = None) -> int:
    """
    Pull WR and TE stats from nflverse for the given seasons (and optional week
    filter), transform to our schema, and upsert into nflverse_wr_stats.
    Returns total rows upserted.
    """
    df = nfl.load_player_stats(seasons)
    wr_df = df.filter(df["position"].is_in(["WR", "TE"]) & (df["week"] <= 18))

    if weeks:
        wr_df = wr_df.filter(wr_df["week"].is_in(weeks))

    rows_to_write = []

    for g in wr_df.iter_rows(named=True):
        tgts     = _safe(g.get("targets"),               int)   or 0
        recs     = _safe(g.get("receptions"),            int)   or 0
        recv_yds = _safe(g.get("receiving_yards"),       int)   or 0
        recv_epa = _safe(g.get("receiving_epa"),         float) or 0.0
        recv_fds = _safe(g.get("receiving_first_downs"), int)   or 0
        recv_tds = _safe(g.get("receiving_tds"),         int)   or 0

        catch_rate    = round(recs     / tgts,     4) if tgts > 0 else None
        ypr           = round(recv_yds / recs,     2) if recs  > 0 else None
        epa_per_tgt   = round(recv_epa / tgts,     4) if tgts > 0 else None
        fd_rate       = round(recv_fds / recs,     4) if recs  > 0 else None

        row = {
            "player_id":                  _safe(g.get("player_id")),
            "player_name":                _safe(g.get("player_display_name")),
            "position":                   _safe(g.get("position")),
            "team":                       _safe(g.get("recent_team")),
            "season":                     _safe(g.get("season"), int),
            "week":                       _safe(g.get("week"),   int),
            "receptions":                 recs,
            "targets":                    tgts,
            "receiving_yards":            recv_yds,
            "receiving_tds":              recv_tds,
            "receiving_air_yards":        _safe(g.get("receiving_air_yards"),         int),
            "receiving_yards_after_catch":_safe(g.get("receiving_yards_after_catch"), int),
            "receiving_first_downs":      recv_fds,
            "receiving_epa":              recv_epa,
            "receiving_fumbles":          _safe(g.get("receiving_fumbles"),      int),
            "receiving_fumbles_lost":     _safe(g.get("receiving_fumbles_lost"), int),
            "receiving_2pt_conversions":  _safe(g.get("receiving_2pt_conversions"), int),
            "target_share":               _safe(g.get("target_share"),    float),
            "air_yards_share":            _safe(g.get("air_yards_share"), float),
            "wopr":                       _safe(g.get("wopr"),            float),
            "racr":                       _safe(g.get("racr"),            float),
            "catch_rate":                 catch_rate,
            "ypr":                        ypr,
            "epa_per_target":             epa_per_tgt,
            "fd_rate":                    fd_rate,
            "opponent":                   _safe(g.get("opponent_team")),
            "game_id":                    _safe(g.get("game_id")),
        }

        rows_to_write.append(row)

    upserted = _write_in_batches(rows_to_write, "nflverse_wr_stats",
                                 conflict_cols=("player_id", "season", "week"))
    logger.info("nflverse_wr_stats: upserted %d rows", upserted)
    return upserted


def get_wr_game_stats(player_name: str, team: str, season: int, week: int) -> Optional[dict]:
    """Return a single WR/TE's nflverse game row as a dict, or None."""
    conn = _get_conn()
    cur  = conn.cursor()
    cur.execute(
        """
        SELECT * FROM nflverse_wr_stats
        WHERE player_name = %s AND team = %s AND season = %s AND week = %s
        LIMIT 1
        """,
        [player_name, team, season, week],
    )
    row  = cur.fetchone()
    cols = [d[0] for d in cur.description]
    cur.close()
    conn.close()
    return dict(zip(cols, row)) if row else None


def get_wr_rolling_baseline(
    player_name: str, team: str, season: int, current_week: int, window: int = 5
) -> Optional[dict]:
    """
    Aggregate nflverse WR/TE stats from up to the last `window` weeks before
    current_week. Returns sums/avgs in the shape expected by
    calc_wr_te_multiplier_enhanced.
    """
    conn = _get_conn()
    cur  = conn.cursor()
    cur.execute(
        """
        SELECT
            SUM(targets)                AS targets,
            SUM(receptions)             AS receptions,
            SUM(receiving_yards)        AS receiving_yards,
            SUM(receiving_epa)          AS receiving_epa,
            SUM(receiving_first_downs)  AS receiving_first_downs,
            AVG(wopr)                   AS wopr,
            AVG(target_share)           AS target_share,
            SUM(receiving_fumbles_lost) AS receiving_fumbles_lost
        FROM (
            SELECT * FROM nflverse_wr_stats
            WHERE player_name = %s AND season = %s AND week < %s
            ORDER BY week DESC
            LIMIT %s
        ) recent
        """,
        [player_name, season, current_week, window],
    )
    row  = cur.fetchone()
    cols = [d[0] for d in cur.description]
    cur.close()
    conn.close()
    return dict(zip(cols, row)) if row else None


# =============================================================================
# DEF � fetch, transform, store
# =============================================================================

_FRONT7_POSITIONS    = {"DE", "DT", "NT", "LB", "ILB", "OLB", "MLB", "EDGE", "DL"}
_SECONDARY_POSITIONS = {"CB", "S", "FS", "SS", "DB"}
_ALL_DEF_POSITIONS   = _FRONT7_POSITIONS | _SECONDARY_POSITIONS
_DEF_SEASONS_MAX     = 2024   # 2025 defensive data not yet included


def _build_def_row(g: dict) -> dict:
    """Transform one nflverse defensive player-game row into our DB schema dict."""
    return {
        "player_id":                    _safe(g.get("player_id")),
        "player_name":                  _safe(g.get("player_display_name")),
        "position":                     _safe(g.get("position")),
        "team":                         _safe(g.get("recent_team")),
        "season":                       _safe(g.get("season"),                      int),
        "week":                         _safe(g.get("week"),                        int),
        "def_tackles_solo":             _safe(g.get("def_tackles_solo"),            int),
        "def_tackles_with_assist":      _safe(g.get("def_tackles_with_assist"),     int),
        "def_tackle_assists":           _safe(g.get("def_tackle_assists"),          int),
        "def_tackles_for_loss":         _safe(g.get("def_tackles_for_loss"),        float),
        "def_tackles_for_loss_yards":   _safe(g.get("def_tackles_for_loss_yards"),  float),
        "def_sacks":                    _safe(g.get("def_sacks"),                   float),
        "def_sack_yards":               _safe(g.get("def_sack_yards"),              float),
        "def_qb_hits":                  _safe(g.get("def_qb_hits"),                 int),
        "def_interceptions":            _safe(g.get("def_interceptions"),           int),
        "def_interception_yards":       _safe(g.get("def_interception_yards"),      int),
        "def_pass_defended":            _safe(g.get("def_pass_defended"),           int),
        "def_fumbles_forced":           _safe(g.get("def_fumbles_forced"),          int),
        "def_fumbles":                  _safe(g.get("def_fumbles"),                 int),
        "def_tds":                      _safe(g.get("def_tds"),                     int),
        "def_safeties":                 _safe(g.get("def_safeties"),                int),
        "opponent":                     _safe(g.get("opponent_team")),
        "game_id":                      _safe(g.get("game_id")),
    }


def fetch_and_store_def_stats(seasons: list, weeks: list = None) -> int:
    """
    Pull defensive player stats from nflverse and upsert into two tables:
      - nflverse_front7_stats    (DE, DT, NT, LB, ILB, OLB, MLB, EDGE, DL)
      - nflverse_secondary_stats (CB, S, FS, SS, DB)
    Only includes regular season (week <= 18) and seasons up to 2024.
    Returns total rows upserted across both tables.
    """
    seasons = [s for s in seasons if s <= _DEF_SEASONS_MAX]
    if not seasons:
        logger.info("No eligible seasons for DEF backfill (max %d)", _DEF_SEASONS_MAX)
        return 0

    df = nfl.load_player_stats(seasons)
    def_df = df.filter(
        df["position"].is_in(list(_ALL_DEF_POSITIONS)) & (df["week"] <= 18)
    )
    if weeks:
        def_df = def_df.filter(def_df["week"].is_in(weeks))

    front7_rows    = []
    secondary_rows = []

    for g in def_df.iter_rows(named=True):
        pos = (g.get("position") or "").upper()
        row = _build_def_row(g)
        if pos in _FRONT7_POSITIONS:
            front7_rows.append(row)
        elif pos in _SECONDARY_POSITIONS:
            secondary_rows.append(row)

    conflict = ("player_id", "season", "week")
    f7  = _write_in_batches(front7_rows,    "nflverse_front7_stats",    conflict)
    sec = _write_in_batches(secondary_rows, "nflverse_secondary_stats", conflict)

    logger.info("nflverse_front7_stats: upserted %d rows",    f7)
    logger.info("nflverse_secondary_stats: upserted %d rows", sec)
    return f7 + sec


# ── Query helpers ──────────────────────────────────────────────────────────────

def get_front7_game_stats(player_name: str, team: str, season: int, week: int) -> Optional[dict]:
    """Return a single front-7 player's nflverse game row as a dict, or None."""
    conn = _get_conn()
    cur  = conn.cursor()
    cur.execute(
        "SELECT * FROM nflverse_front7_stats "
        "WHERE player_name = %s AND team = %s AND season = %s AND week = %s LIMIT 1",
        [player_name, team, season, week],
    )
    row  = cur.fetchone()
    cols = [d[0] for d in cur.description]
    cur.close(); conn.close()
    return dict(zip(cols, row)) if row else None


def get_secondary_game_stats(player_name: str, team: str, season: int, week: int) -> Optional[dict]:
    """Return a single secondary player's nflverse game row as a dict, or None."""
    conn = _get_conn()
    cur  = conn.cursor()
    cur.execute(
        "SELECT * FROM nflverse_secondary_stats "
        "WHERE player_name = %s AND team = %s AND season = %s AND week = %s LIMIT 1",
        [player_name, team, season, week],
    )
    row  = cur.fetchone()
    cols = [d[0] for d in cur.description]
    cur.close(); conn.close()
    return dict(zip(cols, row)) if row else None


def get_front7_rolling_baseline(
    player_name: str, team: str, season: int, current_week: int, window: int = 5
) -> Optional[dict]:
    """Aggregate front-7 nflverse stats from the last `window` weeks before current_week."""
    conn = _get_conn()
    cur  = conn.cursor()
    cur.execute(
        """
        SELECT
            SUM(def_tackles_solo)       AS tackles_solo,
            SUM(def_sacks)              AS sacks,
            SUM(def_tackles_for_loss)   AS tfl,
            SUM(def_qb_hits)            AS qb_hits,
            SUM(def_fumbles_forced)     AS fumbles_forced
        FROM (
            SELECT * FROM nflverse_front7_stats
            WHERE player_name = %s AND season = %s AND week < %s
            ORDER BY week DESC LIMIT %s
        ) recent
        """,
        [player_name, season, current_week, window],
    )
    row  = cur.fetchone()
    cols = [d[0] for d in cur.description]
    cur.close(); conn.close()
    return dict(zip(cols, row)) if row else None


def get_secondary_rolling_baseline(
    player_name: str, team: str, season: int, current_week: int, window: int = 5
) -> Optional[dict]:
    """Aggregate secondary nflverse stats from the last `window` weeks before current_week."""
    conn = _get_conn()
    cur  = conn.cursor()
    cur.execute(
        """
        SELECT
            SUM(def_interceptions)      AS interceptions,
            SUM(def_pass_defended)      AS pass_defended,
            SUM(def_tackles_solo)       AS tackles_solo,
            SUM(def_interception_yards) AS int_yards,
            SUM(def_fumbles_forced)     AS fumbles_forced
        FROM (
            SELECT * FROM nflverse_secondary_stats
            WHERE player_name = %s AND season = %s AND week < %s
            ORDER BY week DESC LIMIT %s
        ) recent
        """,
        [player_name, season, current_week, window],
    )
    row  = cur.fetchone()
    cols = [d[0] for d in cur.description]
    cur.close(); conn.close()
    return dict(zip(cols, row)) if row else None
