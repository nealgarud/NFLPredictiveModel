"""
fetch_ol_example.py
===================
Local test script — validates calc_ol_multiplier using team-level context
derived from nflverse QB + RB stats.

Game: BUF @ BAL, 2024 Week 4

The OL multiplier is team-level (same value applied to all 5 OL starters).
We derive team context from:
  - QB sacks_suffered / attempts  → pass protection signal
  - RB rushing_yards / carries / rushing_epa → run blocking signal

Two teams shown side-by-side:
  BAL offensive line  (protecting Lamar Jackson, blocking for Derrick Henry)
  BUF offensive line  (protecting Josh Allen)
"""
import sys
import os

import nflreadpy as nfl
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'BoxScoreCollector'))
from GameImpactCalculator import calc_ol_multiplier

SEASON = 2024
WEEK   = 4

TEAMS = [
    {"team": "BAL", "qb": "Lamar Jackson"},
    {"team": "BUF", "qb": "Josh Allen"},
]

OL_POSITIONS = ["LT", "LG", "C", "RG", "RT"]


def build_team_context(df, team: str, qb_name: str, week: int, label: str) -> tuple:
    """
    Build nv_game and nv_base dicts for a team's OL from QB + RB nflverse data.
    Returns (nv_game, nv_base, summary_str).
    """
    # ── QB rows ───────────────────────────────────────────────────────────────
    qb_all = df[
        (df["player_display_name"] == qb_name) &
        (df["season"] == SEASON)
    ].copy()

    qb_game_rows = qb_all[qb_all["week"] == week]
    qb_base_rows = qb_all[qb_all["week"] < week]

    if qb_game_rows.empty:
        return None, None, f"  [!] No Week {week} data for {qb_name}"

    qb_g = qb_game_rows.iloc[0]

    # ── RB rows for this team this week ───────────────────────────────────────
    rb_game_rows = df[
        (df["position"] == "RB") &
        (df["team"] == team) &
        (df["season"] == SEASON) &
        (df["week"] == week)
    ].copy()

    rb_base_rows = df[
        (df["position"] == "RB") &
        (df["team"] == team) &
        (df["season"] == SEASON) &
        (df["week"] < week)
    ].copy()

    # ── nv_game — team context for this specific game ─────────────────────────
    team_sacks    = float(qb_g.get("sacks_suffered") or 0)
    team_pass_att = float(qb_g.get("attempts")       or 0)
    team_rush_yds = float(rb_game_rows["rushing_yards"].sum()) if not rb_game_rows.empty else 0.0
    team_carries  = float(rb_game_rows["carries"].sum())       if not rb_game_rows.empty else 0.0
    team_rush_epa = float(rb_game_rows["rushing_epa"].sum())   if not rb_game_rows.empty else 0.0

    nv_game = {
        "team_sacks_suffered": team_sacks,
        "team_pass_attempts":  team_pass_att,
        "team_rushing_yards":  team_rush_yds,
        "team_carries":        team_carries,
        "team_rushing_epa":    team_rush_epa,
        # team_ol_penalties, team_hurries, team_knockdowns — Sportradar only
        # omitted here; component defaults to neutral (1.0)
    }

    # ── nv_base — rolling avg for prior weeks ─────────────────────────────────
    if qb_base_rows.empty:
        nv_base = None
    else:
        base_sacks    = float(qb_base_rows["sacks_suffered"].sum())
        base_pass_att = float(qb_base_rows["attempts"].sum())
        base_dropbacks = base_pass_att + base_sacks
        base_sack_rate = base_sacks / base_dropbacks if base_dropbacks > 0 else 0.065

        base_rb = rb_base_rows if not rb_base_rows.empty else None
        base_carries   = float(base_rb["carries"].sum())       if base_rb is not None else 0.0
        base_rush_yds  = float(base_rb["rushing_yards"].sum()) if base_rb is not None else 0.0
        base_rush_epa  = float(base_rb["rushing_epa"].sum())   if base_rb is not None else 0.0
        base_team_ypc  = (base_rush_yds / base_carries) if base_carries > 0 else 4.3

        nv_base = {
            "base_sack_rate":      base_sack_rate,
            "base_team_ypc":       base_team_ypc,
            "base_team_rush_epa":  base_rush_epa,
            "base_carries":        base_carries,
            # base_ol_penalties, base_pressure_rate — not available → fallback defaults
        }

    summary = (
        f"  sacks={int(team_sacks)}  dropbacks={int(team_pass_att + team_sacks)}"
        f"  rush_yds={int(team_rush_yds)}  carries={int(team_carries)}"
        f"  rush_epa={round(team_rush_epa, 2)}"
    )
    return nv_game, nv_base, summary


def run_team(df, team: str, qb_name: str):
    print("\n" + "=" * 55)
    print(f"  {team} Offensive Line  |  QB: {qb_name}  |  {SEASON} Week {WEEK}")
    print("=" * 55)

    nv_game, nv_base, summary = build_team_context(df, team, qb_name, WEEK, team)
    print(f"\n  Team context (Week {WEEK}): {summary}")

    if nv_game is None:
        print(f"  {summary}")
        return

    if nv_base is None:
        print(f"  [!] No baseline data (weeks < {WEEK})")
        return

    print(f"\n  nv_game:")
    for k, v in nv_game.items():
        print(f"    {k}: {round(v, 4) if isinstance(v, float) else v}")

    print(f"\n  nv_base:")
    for k, v in nv_base.items():
        print(f"    {k}: {round(v, 4) if isinstance(v, float) else v}")

    # Neutral player dict — OL individual stats not needed for the calculation
    p = {"position": "LT", "team": team}

    neutral_mult = calc_ol_multiplier(p, b=None, nv_game=None, nv_base=None)
    team_mult    = calc_ol_multiplier(p, b=None, nv_game=nv_game, nv_base=nv_base)

    print(f"\n  --- OL Multiplier ---")
    print(f"    neutral  (no nflverse data):  {round(neutral_mult, 4)}")
    print(f"    enhanced (team proxy):         {round(team_mult,   4)}")

    # Show per-position breakdown (same value, different weights applied upstream)
    print(f"\n  Applied uniformly to all 5 starters: LT, LG, C, RG, RT")


def main():
    print("Loading nflverse player stats...")
    df = nfl.load_player_stats([SEASON]).to_pandas()

    for entry in TEAMS:
        run_team(df, entry["team"], entry["qb"])

    print("\n" + "=" * 55)


if __name__ == "__main__":
    main()
