"""
fetch_wr_example.py
===================
Local test script — validates calc_wr_te_multiplier_enhanced for WR and TE.

Test players (BUF @ BAL, 2024 Week 4):
  Stefon Diggs  — WR, HOU  (released by BUF May 2024, signed HOU)
  Mark Andrews  — TE, BAL

Prints side-by-side original (box-score only) vs nflverse-enhanced multiplier.
"""
import sys
import os

import nflreadpy as nfl

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'BoxScoreCollector'))
from GameImpactCalculator import calc_wr_te_multiplier_enhanced

SEASON = 2024
WEEK   = 4

PLAYERS = [
    {"name": "Stefon Diggs",  "team": "HOU", "position": "WR"},
    {"name": "Mark Andrews",  "team": "BAL", "position": "TE"},
]


# ── nflverse column → our nv_game/nv_base keys ────────────────────────────────

def build_nv_game(g) -> dict:
    return {
        "receiving_epa":          g.get("receiving_epa"),
        "targets":                g.get("targets"),
        "receiving_yards":        g.get("receiving_yards"),
        "receiving_tds":          g.get("receiving_tds"),
        "receiving_first_downs":  g.get("receiving_first_downs"),
        "receptions":             g.get("receptions"),
        "wopr":                   g.get("wopr"),
        "target_share":           g.get("target_share"),
        "receiving_fumbles_lost": g.get("receiving_fumbles_lost"),
    }


def build_nv_base(base_rows) -> dict:
    total_tgts = float(base_rows["targets"].sum())
    total_recs = float(base_rows["receptions"].sum())
    return {
        "receiving_epa":          base_rows["receiving_epa"].sum(),
        "targets":                total_tgts,
        "receptions":             total_recs,
        "receiving_yards":        base_rows["receiving_yards"].sum(),
        "receiving_first_downs":  base_rows["receiving_first_downs"].sum(),
        "wopr":                   base_rows["wopr"].mean(),
        "target_share":           base_rows["target_share"].mean(),
        "receiving_fumbles_lost": base_rows["receiving_fumbles_lost"].sum()
                                  if "receiving_fumbles_lost" in base_rows.columns else 0,
    }


def build_p(g, position: str) -> dict:
    """Sportradar-shaped box-score dict (populated from nflverse as proxy)."""
    recs      = int(g.get("receptions")        or 0)
    tgts      = int(g.get("targets")           or 0)
    recv_yds  = float(g.get("receiving_yards") or 0)
    yac       = float(g.get("receiving_yards_after_catch") or 0)
    recv_tds  = int(g.get("receiving_tds")     or 0)
    return {
        "position":              position,
        "targets":               tgts,
        "receptions":            recs,
        "receiving_yards":       recv_yds,
        "yards_after_catch":     yac,
        "receiving_touchdowns":  recv_tds,
        "drops":                 0,   # not in nflverse — Sportradar only
    }


def build_b(base_rows) -> dict:
    """Sportradar-shaped season-baseline dict (populated from nflverse as proxy)."""
    n          = len(base_rows)
    total_tgts = float(base_rows["targets"].sum())
    total_recs = float(base_rows["receptions"].sum())
    total_yds  = float(base_rows["receiving_yards"].sum())
    total_yac  = float(base_rows["receiving_yards_after_catch"].sum())
    return {
        "avg_catch_rate":       total_recs / total_tgts        if total_tgts > 0 else 0.65,
        "avg_ypr":              total_yds  / total_recs        if total_recs > 0 else 11.0,
        "avg_receiving_yards":  total_yds  / n                 if n > 0          else 0.0,
        "avg_yac":              total_yac  / n                 if n > 0          else 0.0,
        "avg_drops":            0.0,   # not in nflverse — Sportradar only
        "avg_targets":          total_tgts / n                 if n > 0          else 0.0,
    }


# ── Per-player runner ─────────────────────────────────────────────────────────

def run_player(df, player_name: str, team: str, position: str):
    print("\n" + "=" * 55)
    print(f"  {player_name}  |  {position}  |  {team}  |  {SEASON} Week {WEEK}")
    print("=" * 55)

    player_df = df[
        (df["player_display_name"] == player_name) &
        (df["season"] == SEASON)
    ].copy()

    if player_df.empty:
        print(f"  [!] No data found for {player_name} in {SEASON}")
        return

    game_row = player_df[player_df["week"] == WEEK]
    if game_row.empty:
        print(f"  [!] No Week {WEEK} row for {player_name}")
        return

    base_rows = player_df[player_df["week"] < WEEK]
    if base_rows.empty:
        print(f"  [!] No baseline rows (weeks < {WEEK}) for {player_name}")
        return

    g = game_row.iloc[0]

    nv_game = build_nv_game(g)
    nv_base = build_nv_base(base_rows)
    p       = build_p(g, position)
    b       = build_b(base_rows)

    print(f"\n  nv_game  (Week {WEEK}):")
    for k, v in nv_game.items():
        print(f"    {k}: {round(v, 4) if isinstance(v, float) else v}")

    print(f"\n  nv_base  (weeks 1-{WEEK-1}, {len(base_rows)} games):")
    for k, v in nv_base.items():
        print(f"    {k}: {round(v, 4) if isinstance(v, float) else v}")

    print(f"\n  p  (box-score proxy):")
    for k, v in p.items():
        print(f"    {k}: {round(v, 3) if isinstance(v, float) else v}")

    print(f"\n  b  (baseline proxy):")
    for k, v in b.items():
        print(f"    {k}: {round(v, 3) if isinstance(v, float) else v}")

    original_mult  = calc_wr_te_multiplier_enhanced(p, b, nv_game=None,    nv_base=None)
    nflverse_mult  = calc_wr_te_multiplier_enhanced(p, b, nv_game=nv_game, nv_base=nv_base)

    print(f"\n  --- Multiplier Comparison ---")
    print(f"    original  (box-score only):  {round(original_mult,  4) if original_mult  is not None else 'N/A'}")
    print(f"    nflverse  (enhanced):        {round(nflverse_mult,  4) if nflverse_mult  is not None else 'N/A'}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Loading nflverse player stats...")
    df = nfl.load_player_stats([SEASON]).to_pandas()
    wr_te_df = df[df["position"].isin(["WR", "TE"])].copy()

    for player in PLAYERS:
        run_player(wr_te_df, player["name"], player["team"], player["position"])

    print("\n" + "=" * 55)


if __name__ == "__main__":
    main()
