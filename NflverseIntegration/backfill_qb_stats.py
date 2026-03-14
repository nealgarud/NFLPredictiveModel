"""
backfill_qb_stats.py
====================
One-shot backfill script — populates nflverse_qb_stats, nflverse_rb_stats,
and nflverse_wr_stats for the specified seasons (default: 2022-2025).

Requires DB env vars:
  SUPABASE_DB_HOST, SUPABASE_DB_NAME, SUPABASE_DB_USER,
  SUPABASE_DB_PASSWORD, SUPABASE_DB_PORT

Usage:
    python backfill_qb_stats.py
    python backfill_qb_stats.py --seasons 2023 2024
    python backfill_qb_stats.py --seasons 2024 --positions qb
    python backfill_qb_stats.py --seasons 2024 --positions rb
    python backfill_qb_stats.py --seasons 2024 --positions wr
"""

import argparse
import logging
import sys

from NflverseDataFetcher import (
    fetch_and_store_qb_stats,
    fetch_and_store_rb_stats,
    fetch_and_store_wr_stats,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_SEASONS = [2022, 2023, 2024, 2025]


def parse_args():
    p = argparse.ArgumentParser(description="Backfill nflverse QB + RB stats into Supabase")
    p.add_argument(
        "--seasons", nargs="+", type=int, default=DEFAULT_SEASONS,
        help="List of seasons to backfill (default: 2022 2023 2024 2025)",
    )
    p.add_argument(
        "--positions", nargs="+", choices=["qb", "rb", "wr", "all"], default=["all"],
        help="Which positions to backfill (default: all)",
    )
    return p.parse_args()


def main():
    args = parse_args()
    seasons    = args.seasons
    positions  = set(args.positions)
    do_all     = "all" in positions

    logger.info("Starting nflverse backfill  seasons=%s  positions=%s", seasons, positions)

    # ── QB ────────────────────────────────────────────────────────────────────
    if do_all or "qb" in positions:
        logger.info("--- Backfilling QB stats ---")
        for season in seasons:
            try:
                n = fetch_and_store_qb_stats([season])
                logger.info("  QB  season=%d  rows=%d", season, n)
            except Exception as exc:
                logger.error("  QB  season=%d  ERROR: %s", season, exc)

    # ── RB ────────────────────────────────────────────────────────────────────
    if do_all or "rb" in positions:
        logger.info("--- Backfilling RB stats ---")
        for season in seasons:
            try:
                n = fetch_and_store_rb_stats([season])
                logger.info("  RB  season=%d  rows=%d", season, n)
            except Exception as exc:
                logger.error("  RB  season=%d  ERROR: %s", season, exc)

    # ── WR/TE ──────────────────────────────────────────────────────────────────
    if do_all or "wr" in positions:
        logger.info("--- Backfilling WR/TE stats ---")
        for season in seasons:
            try:
                n = fetch_and_store_wr_stats([season])
                logger.info("  WR/TE  season=%d  rows=%d", season, n)
            except Exception as exc:
                logger.error("  WR/TE  season=%d  ERROR: %s", season, exc)

    logger.info("Backfill complete.")


if __name__ == "__main__":
    main()
