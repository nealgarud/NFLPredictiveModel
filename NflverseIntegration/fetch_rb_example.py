"""
fetch_rb_example.py
====================
Local test script — validates the original vs nflverse-enhanced RB multiplier.
Mirrors the structure of fetch_lamar_example.py (QB session).

Uses nflreadpy to pull 2024 weekly player stats.
No DB connection required — all data comes from nflverse in-memory.

Usage:
    python fetch_rb_example.py
"""

import sys
import os
import nflreadpy as nfl
import pandas as pd

# Pull in the existing multiplier logic from BoxScoreCollector
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'BoxScoreCollector'))
from GameImpactCalculator import calc_rb_multiplier_enhanced

SEASON = 2024


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_rb_data(season: int) -> pd.DataFrame:
    """Load nflverse weekly player stats, filtered to RBs."""
    df = nfl.load_player_stats([season]).to_pandas()
    return df[df["position"] == "RB"].copy()


def _nv_game_dict(g: pd.Series) -> dict:
    """Build the nv_game dict from a single nflverse row (confirmed column names)."""
    return {
        "carries":                 g.get("carries"),
        "rushing_yards":           g.get("rushing_yards"),
        "rushing_epa":             g.get("rushing_epa"),
        "rushing_first_downs":     g.get("rushing_first_downs"),
        "rushing_fumbles_lost":    g.get("rushing_fumbles_lost"),
        "receiving_yards":         g.get("receiving_yards"),
        "receiving_tds":           g.get("receiving_tds"),
        "receiving_epa":           g.get("receiving_epa"),
        "receiving_fumbles_lost":  g.get("receiving_fumbles_lost"),
        "target_share":            g.get("target_share"),
        "wopr":                    g.get("wopr"),
    }


def _nv_base_dict(base_df: pd.DataFrame) -> dict:
    """Build the nv_base dict from rolling prior-week rows."""
    base_carries = float(base_df["carries"].sum())
    return {
        "carries":                 base_carries,
        "rushing_yards":           float(base_df["rushing_yards"].sum()),
        "rushing_epa":             float(base_df["rushing_epa"].sum()),
        "rushing_first_downs":     float(base_df["rushing_first_downs"].sum()),
        "avg_receiving_yards":     float(base_df["receiving_yards"].mean()),
        "receiving_epa":           float(base_df["receiving_epa"].sum()),
        "rushing_fumbles_lost":    float(base_df["rushing_fumbles_lost"].sum()),
        "receiving_fumbles_lost":  float(base_df["receiving_fumbles_lost"].sum()),
    }


def _p_dict(g: pd.Series) -> dict:
    """
    Build the Sportradar-style p dict from nflverse columns.
    In production p comes from BoxScoreParser; here we approximate from nflverse.
    YAC and broken tackles are NOT in nflverse — zeroed out (graceful degradation).
    """
    carries = int(g.get("carries") or 0)
    return {
        "rush_attempts":          carries,
        "rush_yards":             float(g.get("rushing_yards")  or 0),
        "rush_yards_after_contact": 0,    # Sportradar only — not in nflverse
        "rush_broken_tackles":    0,      # Sportradar only — not in nflverse
        "rush_tlost":             0,      # Sportradar only — not in nflverse
        "receptions":             int(g.get("receptions")        or 0),
        "receiving_yards":        int(g.get("receiving_yards")   or 0),
        "receiving_touchdowns":   int(g.get("receiving_tds")     or 0),
        "position":               "RB",
    }


def _b_dict(base_df: pd.DataFrame) -> dict:
    """Build the baseline b dict (mirrors player_season_stats rolling averages)."""
    base_carries = float(base_df["carries"].sum())
    base_rush    = float(base_df["rushing_yards"].sum())
    return {
        "avg_rush_ypc":            (base_rush / base_carries) if base_carries > 0 else 4.3,
        "avg_rush_yac":            0.0,   # Sportradar only — fallback to league avg
        "avg_rush_broken_tackles": 0.0,   # Sportradar only
        "avg_rush_attempts":       float(base_df["carries"].mean()),
        "avg_rush_yards":          float(base_df["rushing_yards"].mean()),
    }


def _print_section(label: str, d: dict) -> None:
    print(f"\n{label}:")
    for k, v in d.items():
        if isinstance(v, float):
            print(f"  {k}: {round(v, 4)}")
        else:
            print(f"  {k}: {v}")


def run_case(rb_df: pd.DataFrame, player_name: str, week: int, label: str) -> None:
    """Run one test case and print results."""
    print("\n" + "=" * 60)
    print(f"TEST: {label}  ({player_name}, 2024 Week {week})")
    print("=" * 60)

    player_df = rb_df[rb_df["player_display_name"] == player_name].copy()
    if player_df.empty:
        print(f"  !! No data found for {player_name}")
        return

    game_row = player_df[player_df["week"] == week]
    if game_row.empty:
        print(f"  !! No Week {week} row for {player_name}")
        return

    base_df = player_df[player_df["week"] < week]
    if base_df.empty:
        print(f"  !! No baseline rows (weeks < {week}) — cannot compute enhanced")
        return

    g      = game_row.iloc[0]
    p      = _p_dict(g)
    b      = _b_dict(base_df)
    nv_g   = _nv_game_dict(g)
    nv_b   = _nv_base_dict(base_df)

    _print_section(f"nv_game  (Week {week})", nv_g)
    _print_section(f"nv_base  (weeks 1-{week-1}, {len(base_df)} games)", nv_b)
    _print_section(f"p  (box-score approximation)", p)
    _print_section(f"b  (rolling baseline)", b)

    original = calc_rb_multiplier_enhanced(p, b, nv_game=None,  nv_base=None)
    enhanced = calc_rb_multiplier_enhanced(p, b, nv_game=nv_g,  nv_base=nv_b)

    print(f"\n--- Multiplier Comparison ---")
    print(f"  original  (box-score only):  {round(original, 4) if original is not None else 'N/A (< 3 carries)'}")
    print(f"  nflverse  (enhanced):        {round(enhanced, 4) if enhanced is not None else 'N/A (< 3 carries)'}")


def main() -> None:
    print("Loading nflverse 2024 RB data...")
    rb_df = _load_rb_data(SEASON)
    print(f"  {len(rb_df)} RB-week rows loaded.")

    # ── Test Case 1: Derrick Henry Week 4 (primary validation) ───────────────
    run_case(rb_df, "Derrick Henry", week=4,
             label="Power back, high volume — rushing EPA impact")

    # ── Test Case 2: Christian McCaffrey Week 8 (dual-threat) ────────────────
    # CMC was injured in 2024; try Week 4 instead
    run_case(rb_df, "Christian McCaffrey", week=4,
             label="Dual-threat — receiving component boost")

    # ── Test Case 3: Find an RB with fumbles ─────────────────────────────────
    fumble_rows = rb_df[
        (rb_df["rushing_fumbles_lost"] + rb_df["receiving_fumbles_lost"] >= 1)
        & (rb_df["carries"] >= 5)
        & (rb_df["week"] >= 2)   # need at least 1 prior week for a baseline
    ].copy()
    if not fumble_rows.empty:
        f_row = fumble_rows.iloc[0]
        f_name = f_row["player_display_name"]
        f_week = int(f_row["week"])
        run_case(rb_df, f_name, week=f_week,
                 label="Ball security penalty — RB with fumble")
    else:
        print("\n  (No RB with 1+ fumble lost and 5+ carries found in 2024 data)")

    # ── Test Case 4: Low-volume game — should return None ─────────────────────
    print("\n" + "=" * 60)
    print("TEST: Low-volume game (<3 carries) — should return None")
    print("=" * 60)
    low_vol_p = {
        "rush_attempts": 2, "rush_yards": 8.0,
        "rush_yards_after_contact": 0, "rush_broken_tackles": 0,
        "rush_tlost": 0, "receptions": 1, "receiving_yards": 5,
        "receiving_touchdowns": 0, "position": "RB",
    }
    result = calc_rb_multiplier_enhanced(low_vol_p)
    print(f"  result: {result}  (expected: None)")


if __name__ == "__main__":
    main()
