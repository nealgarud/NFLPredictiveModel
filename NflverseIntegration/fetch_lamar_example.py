import sys
import os
import nflreadpy as nfl
import pandas as pd

# Pull in the existing multiplier logic from BoxScoreCollector
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'BoxScoreCollector'))
from GameImpactCalculator import calc_qb_multiplier_enhanced

SEASON = 2024
PLAYER_NAME = "Lamar Jackson"
WEEK = 4


def main() -> None:
    # 1) Load nflverse player stats for the season
    player_stats = nfl.load_player_stats([SEASON])
    df = player_stats.to_pandas()

    # 2) Filter to QB rows only
    qb_df = df[df["position"] == "QB"].copy()

    # 3) Filter to this QB for this season
    lam_all = qb_df[
        (qb_df["player_display_name"] == PLAYER_NAME)
        & (qb_df["season"] == SEASON)
    ].copy()

    if lam_all.empty:
        print(f"No rows for {PLAYER_NAME} in season {SEASON}")
        return

    # 4) Week 4 game row (nv_game)
    #    Column names confirmed from nflverse schema (Brady sample):
    #    passing_cpoe, passing_epa, passing_air_yards, attempts,
    #    carries, rushing_yards, rushing_epa, sacks_suffered
    lam_w4 = lam_all[lam_all["week"] == WEEK]
    if lam_w4.empty:
        print(f"No Week {WEEK} row for {PLAYER_NAME}")
        return

    g = lam_w4.iloc[0]

    nv_game = {
        "cpoe":              g.get("passing_cpoe"),       # confirmed column name
        "passing_epa":       g.get("passing_epa"),
        "passing_air_yards": g.get("passing_air_yards"),
        "attempts":          g.get("attempts"),
        "carries":           g.get("carries"),
        "rushing_yards":     g.get("rushing_yards"),
        "rushing_epa":       g.get("rushing_epa"),
        "sacks":             g.get("sacks_suffered"),
    }

    # 5) Baseline: all weeks < WEEK (nv_base — season-to-date averages)
    lam_base = lam_all[lam_all["week"] < WEEK]
    if lam_base.empty:
        print(f"No baseline rows (weeks < {WEEK}), cannot build nv_base")
        return

    base_attempts = float(lam_base["attempts"].sum())

    nv_base = {
        "cpoe":              lam_base["passing_cpoe"].mean(),
        "passing_epa":       lam_base["passing_epa"].sum(),
        "passing_air_yards": lam_base["passing_air_yards"].sum(),
        "attempts":          base_attempts,
        "rushing_yards":     lam_base["rushing_yards"].mean(),
        "sacks":             lam_base["sacks_suffered"].mean(),
    }

    print("=" * 50)
    print(f"nv_game  (2024 Week {WEEK}):")
    for k, v in nv_game.items():
        print(f"  {k}: {round(v, 4) if isinstance(v, float) else v}")

    print(f"\nnv_base  (weeks 1-{WEEK-1} rolling avg, {len(lam_base)} games):")
    for k, v in nv_base.items():
        print(f"  {k}: {round(v, 4) if isinstance(v, float) else v}")

    # 6) p — game box-score dict (what GameImpactCalculator expects)
    p = {
        "pass_attempts":      int(g.get("attempts")              or 0),
        "pass_completions":   int(g.get("completions")           or 0),
        "pass_yards":         float(g.get("passing_yards")        or 0),
        "pass_touchdowns":    int(g.get("passing_tds")           or 0),
        "pass_interceptions": int(g.get("passing_interceptions") or 0),
        "sacks_taken":        int(g.get("sacks_suffered")        or 0),
        "rush_yards":         float(g.get("rushing_yards")        or 0),
        "scrambles":          int(g.get("rushing_first_downs")   or 0),
        "position":           "QB",
    }

    # 7) b — season baseline dict (what GameImpactCalculator expects)
    n_base_games = len(lam_base)
    b = {
        "avg_comp_pct":           (lam_base["completions"].sum() / base_attempts
                                   if base_attempts > 0 else 0.65),
        "avg_ypa":                (lam_base["passing_yards"].sum() / base_attempts
                                   if base_attempts > 0 else 7.0),
        "avg_pass_touchdowns":    lam_base["passing_tds"].mean(),
        "avg_pass_interceptions": lam_base["passing_interceptions"].mean(),
        "avg_pass_attempts":      lam_base["attempts"].mean(),
        "avg_sacks_taken":        lam_base["sacks_suffered"].mean(),
        "avg_rush_yards":         lam_base["rushing_yards"].mean(),
    }

    print(f"\np  (Week {WEEK} box-score):")
    for k, v in p.items():
        print(f"  {k}: {round(v, 3) if isinstance(v, float) else v}")

    print(f"\nb  (weeks 1-{WEEK-1} baseline, {n_base_games} games):")
    for k, v in b.items():
        print(f"  {k}: {round(v, 3) if isinstance(v, float) else v}")

    # 8) Compute both multipliers
    original_mult  = calc_qb_multiplier_enhanced(p, b, nv_game=None,    nv_base=None)
    nflverse_mult  = calc_qb_multiplier_enhanced(p, b, nv_game=nv_game, nv_base=nv_base)

    print("\n" + "=" * 50)
    print("--- QB Multiplier Comparison ---")
    print(f"  original  (box-score only):  {round(original_mult,  4) if original_mult  is not None else 'N/A'}")
    print(f"  nflverse  (enhanced):        {round(nflverse_mult,  4) if nflverse_mult  is not None else 'N/A'}")
    print("=" * 50)

    return {"original": original_mult, "nflverse": nflverse_mult}


if __name__ == "__main__":
    main()
