import nflreadpy as nfl
import pandas as pd


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

    # 4) Week 4 BUF game (nv_game)
    lam_w4 = lam_all[lam_all["week"] == WEEK]
    if lam_w4.empty:
        print(f"No Week {WEEK} row for {PLAYER_NAME}")
        return

    g = lam_w4.iloc[0]
    nv_game = {
        "cpoe": g.get("cpoe"),
        "passing_epa": g.get("passing_epa"),
        "passing_air_yards": g.get("passing_air_yards"),
        "attempts": g.get("attempts"),
       # "sacks": g.get("sacks"),
        "rushing_yards": g.get("rushing_yards"),
        "rushing_epa": g.get("rushing_epa"),
    }

    print("nv_game (2024 Week 4 BUF):")
    for k, v in nv_game.items():
        print(f"  {k}: {v}")

    # 5) Baseline: weeks < 4 (nv_base)
    lam_base = lam_all[lam_all["week"] < WEEK]
    if lam_base.empty:
        print(f"No baseline rows (weeks < {WEEK}), cannot build nv_base")
        return

    base_attempts = float(lam_base["attempts"].sum())
    #base_sacks = float(lam_base["sacks"].sum())

    nv_base = {
        "cpoe": lam_base["cpoe"].mean(),
        "passing_epa": lam_base["passing_epa"].sum(),
        "passing_air_yards": lam_base["passing_air_yards"].sum(),
        "attempts": base_attempts,
    #    "sacks": base_sacks,
        "rushing_yards": lam_base["rushing_yards"].mean(),
    }

    print("\nnv_base (rolling baseline, weeks 13):")
    for k, v in nv_base.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()