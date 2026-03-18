"""
NflverseBackfill Lambda
=======================
Fetches nflverse player stats and upserts into Supabase.

Event formats:
    {}                                    -- backfill current season, all positions
    {"season": 2024}                      -- specific season, all positions
    {"season": 2024, "week": 10}          -- single week
    {"seasons": [2022, 2023, 2024]}       -- multiple seasons
    {"positions": ["qb", "rb"]}           -- specific positions
    {"season": 2024, "positions": ["wr"]} -- season + position combo

Environment variables required:
    SUPABASE_DB_HOST, SUPABASE_DB_NAME, SUPABASE_DB_USER,
    SUPABASE_DB_PASSWORD, SUPABASE_DB_PORT
"""
import json
import logging
import os
from datetime import datetime

from NflverseDataFetcher import (
    fetch_and_store_qb_stats,
    fetch_and_store_rb_stats,
    fetch_and_store_wr_stats,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CURRENT_SEASON = 2025


def lambda_handler(event, context):
    logger.info("NflverseBackfill started | event=%s", json.dumps(event))

    # ── Parse event ────────────────────────────────────────────────────────────
    if isinstance(event.get("body"), str):
        event = json.loads(event["body"])

    seasons_arg   = event.get("seasons") or ([event["season"]] if "season" in event else [CURRENT_SEASON])
    weeks_arg     = [event["week"]] if "week" in event else None
    positions_arg = set(p.lower() for p in event.get("positions", ["qb", "rb", "wr"]))

    logger.info("Running backfill | seasons=%s weeks=%s positions=%s",
                seasons_arg, weeks_arg, positions_arg)

    results = {}

    # ── QB ─────────────────────────────────────────────────────────────────────
    if "qb" in positions_arg:
        try:
            n = fetch_and_store_qb_stats(seasons_arg, weeks=weeks_arg)
            results["qb"] = {"status": "ok", "rows": n}
            logger.info("QB backfill complete: %d rows", n)
        except Exception as e:
            logger.error("QB backfill failed: %s", e)
            results["qb"] = {"status": "error", "message": str(e)}

    # ── RB ─────────────────────────────────────────────────────────────────────
    if "rb" in positions_arg:
        try:
            n = fetch_and_store_rb_stats(seasons_arg, weeks=weeks_arg)
            results["rb"] = {"status": "ok", "rows": n}
            logger.info("RB backfill complete: %d rows", n)
        except Exception as e:
            logger.error("RB backfill failed: %s", e)
            results["rb"] = {"status": "error", "message": str(e)}

    # ── WR/TE ──────────────────────────────────────────────────────────────────
    if "wr" in positions_arg:
        try:
            n = fetch_and_store_wr_stats(seasons_arg, weeks=weeks_arg)
            results["wr"] = {"status": "ok", "rows": n}
            logger.info("WR/TE backfill complete: %d rows", n)
        except Exception as e:
            logger.error("WR/TE backfill failed: %s", e)
            results["wr"] = {"status": "error", "message": str(e)}

    any_error = any(v.get("status") == "error" for v in results.values())

    return {
        "statusCode": 207 if any_error else 200,
        "body": json.dumps({
            "timestamp": datetime.utcnow().isoformat(),
            "seasons":   seasons_arg,
            "weeks":     weeks_arg,
            "results":   results,
        }),
    }
