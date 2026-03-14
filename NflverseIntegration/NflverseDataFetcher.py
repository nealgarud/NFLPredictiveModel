"""
NflverseDataFetcher
===================
Pulls per-game advanced metrics from nflverse (via nflreadpy), transforms them,
and upserts into Supabase tables:
  - nflverse_qb_stats
  - nflverse_rb_stats
  - nflverse_wr_stats

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
        timeout=30,
        ssl_context=True,
    )


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
    df = nfl.load_player_stats(seasons).to_pandas()
    qb_df = df[df["position"] == "QB"].copy()

    if weeks:
        qb_df = qb_df[qb_df["week"].isin(weeks)]

    conn = _get_conn()
    cur = conn.cursor()
    upserted = 0

    for _, g in qb_df.iterrows():
        atts     = _safe(g.get("attempts"), int)        or 0
        sacks    = _safe(g.get("sacks_suffered"), int)  or 0
        py       = _safe(g.get("passing_yards"), float) or 0.0
        pay      = _safe(g.get("passing_air_yards"), float) or 0.0
        epa      = _safe(g.get("passing_epa"), float)   or 0.0
        dropbacks = atts + sacks

        ypa  = round(py  / atts,     2) if atts > 0     else None
        adot = round(pay / atts,     2) if atts > 0     else None
        epd  = round(epa / dropbacks, 4) if dropbacks > 0 else None

        row = {
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
        }

        cols = list(row.keys())
        vals = [row[c] for c in cols]
        placeholders = ", ".join(["%s"] * len(cols))
        col_names    = ", ".join(cols)
        updates      = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols
                                 if c not in ("player_id", "season", "week"))

        sql = f"""
            INSERT INTO nflverse_qb_stats ({col_names})
            VALUES ({placeholders})
            ON CONFLICT (player_id, season, week) DO UPDATE SET {updates}
        """
        cur.execute(sql, vals)
        upserted += 1

    conn.commit()
    cur.close()
    conn.close()
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
    df = nfl.load_player_stats(seasons).to_pandas()
    rb_df = df[df["position"] == "RB"].copy()

    if weeks:
        rb_df = rb_df[rb_df["week"].isin(weeks)]

    conn = _get_conn()
    cur = conn.cursor()
    upserted = 0

    for _, g in rb_df.iterrows():
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

        row = {
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
        }

        cols = list(row.keys())
        vals = [row[c] for c in cols]
        placeholders = ", ".join(["%s"] * len(cols))
        col_names    = ", ".join(cols)
        updates      = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols
                                 if c not in ("player_id", "season", "week"))

        sql = f"""
            INSERT INTO nflverse_rb_stats ({col_names})
            VALUES ({placeholders})
            ON CONFLICT (player_id, season, week) DO UPDATE SET {updates}
        """
        cur.execute(sql, vals)
        upserted += 1

    conn.commit()
    cur.close()
    conn.close()
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
    df = nfl.load_player_stats(seasons).to_pandas()
    wr_df = df[df["position"].isin(["WR", "TE"])].copy()

    if weeks:
        wr_df = wr_df[wr_df["week"].isin(weeks)]

    conn = _get_conn()
    cur  = conn.cursor()
    upserted = 0

    for _, g in wr_df.iterrows():
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

        cols         = list(row.keys())
        vals         = [row[c] for c in cols]
        placeholders = ", ".join(["%s"] * len(cols))
        col_names    = ", ".join(cols)
        updates      = ", ".join(
            f"{c} = EXCLUDED.{c}" for c in cols
            if c not in ("player_id", "season", "week")
        )

        sql = f"""
            INSERT INTO nflverse_wr_stats ({col_names})
            VALUES ({placeholders})
            ON CONFLICT (player_id, season, week) DO UPDATE SET {updates}
        """
        cur.execute(sql, vals)
        upserted += 1

    conn.commit()
    cur.close()
    conn.close()
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
