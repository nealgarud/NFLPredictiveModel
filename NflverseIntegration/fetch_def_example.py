"""
fetch_def_example.py
====================
Local test script — validates the split defensive multipliers using nflverse
defensive player stats.

Game: SF @ BAL  |  2023 Week 16  (Christmas Day, Dec 25 2023)

Players:
  Nick Bosa     — EDGE  — San Francisco 49ers  -> calc_front7_multiplier
  Kyle Hamilton — S     — Baltimore Ravens      -> calc_secondary_multiplier

Coverage stats (def_targets, def_completions_allowed) and hurries are NOT
in nflverse (PFF/NGS only).  Those fields default to 0 here.
"""
import sys
import os

import nflreadpy as nfl
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'BoxScoreCollector'))
from GameImpactCalculator import calc_front7_multiplier, calc_secondary_multiplier

SEASON = 2023
WEEK   = 16

FRONT7    = {'EDGE', 'DE', 'DT', 'NT', 'LB', 'ILB', 'OLB', 'MLB', 'DL'}
SECONDARY = {'CB', 'S', 'FS', 'SS', 'DB', 'SAF'}

PLAYERS = [
    {"name": "Nick Bosa",     "team": "SF",  "position": "EDGE"},
    {"name": "Kyle Hamilton", "team": "BAL", "position": "S"},
]


def _safe(val, default=0.0) -> float:
    try:
        if val is None:
            return default
        if isinstance(val, float) and pd.isna(val):
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


def build_player_rows(df: pd.DataFrame, name: str):
    """Return (game_row Series, base_rows DataFrame) for this player."""
    player_rows = df[
        (df["player_display_name"] == name) &
        (df["season"] == SEASON)
    ].copy()

    if player_rows.empty:
        return None, None

    game_rows = player_rows[player_rows["week"] == WEEK]
    base_rows = player_rows[player_rows["week"] < WEEK]

    g    = game_rows.iloc[0] if not game_rows.empty else None
    base = base_rows         if not base_rows.empty  else None
    return g, base


def row_to_p(g, position: str) -> dict:
    """Map a nflverse defensive row to the p-dict the multiplier functions expect."""
    ast = _safe(g.get("def_tackle_assists") or g.get("def_tackles_with_assist"))
    return {
        "position":                position,
        "tackles":                 _safe(g.get("def_tackles_solo") or g.get("def_tackles")),
        "ast_tackles":             ast,
        "def_sacks":               _safe(g.get("def_sacks")),
        "qb_hits":                 _safe(g.get("def_qb_hits")),       # 0 if absent
        "hurries":                 0.0,                               # not in nflverse
        "passes_defended":         _safe(g.get("def_pass_defended") or g.get("def_pass_defensed")),
        "interceptions":           _safe(g.get("def_interceptions")),
        "tackles_for_loss":        _safe(g.get("def_tackles_for_loss")),
        "def_fumbles_forced":      _safe(g.get("def_fumbles_forced")),
        # Coverage & missed-tackle data not in nflverse — default neutral
        "def_targets":             0.0,
        "def_completions_allowed": 0.0,
        "missed_tackles":          0.0,
    }


def rows_to_b(base: pd.DataFrame) -> dict:
    """Map rolling prior-week rows to the b-dict the multiplier functions expect."""
    def col_mean(col):
        return _safe(base[col].mean()) if col in base.columns else 0.0

    return {
        "avg_tackles":          col_mean("def_tackles_solo"),
        "avg_def_sacks":        col_mean("def_sacks"),
        "avg_qb_hits":          col_mean("def_qb_hits"),
        "avg_hurries":          0.0,
        "avg_passes_defended":  col_mean("def_pass_defended"),
        "avg_interceptions":    col_mean("def_interceptions"),
        "avg_fumbles_forced":   col_mean("def_fumbles_forced"),
        "avg_def_targets":      0.0,
        "avg_def_comp_allowed": 0.0,
    }


def run_player(df: pd.DataFrame, name: str, team: str, position: str):
    pos_upper = position.upper()
    if pos_upper in FRONT7:
        fn_name = "calc_front7_multiplier"
        calc_fn = calc_front7_multiplier
    else:
        fn_name = "calc_secondary_multiplier"
        calc_fn = calc_secondary_multiplier

    print("\n" + "=" * 62)
    print(f"  {name}  |  {position}  |  {team}  |  {SEASON} Week {WEEK}")
    print(f"  Function: {fn_name}")
    print("=" * 62)

    g, base = build_player_rows(df, name)

    if g is None:
        print(f"  [!] No data found for '{name}' in {SEASON}")
        sample = df[df["season"] == SEASON]["player_display_name"].dropna().unique()
        print(f"  Available names (first 10): {sorted(sample)[:10]}")
        return

    # ── Raw nflverse stats ────────────────────────────────────────────────────
    KEY_COLS = [
        "def_tackles_solo", "def_tackle_assists", "def_tackles_with_assist",
        "def_sacks", "def_qb_hits", "def_pass_defended",
        "def_interceptions", "def_tackles_for_loss", "def_fumbles_forced",
        "def_tds", "def_safeties",
    ]
    print(f"\n  nflverse game stats (Week {WEEK}):")
    for col in KEY_COLS:
        val = g.get(col)
        if val is not None and not (isinstance(val, float) and pd.isna(val)):
            print(f"    {col}: {_safe(val):.1f}")

    # ── Build p and b ─────────────────────────────────────────────────────────
    p = row_to_p(g, position)
    b = rows_to_b(base) if base is not None else None
    n_base = len(base) if base is not None else 0

    print(f"\n  p dict ({fn_name} input):")
    for k, v in p.items():
        if k != "position":
            print(f"    {k}: {v:.1f}")

    if b:
        print(f"\n  b dict  (rolling avg, {n_base} prior weeks):")
        for k, v in b.items():
            print(f"    {k}: {v:.3f}")
    else:
        print(f"\n  [!] No baseline data (no prior-week rows)")

    # ── Compute multiplier ────────────────────────────────────────────────────
    mult = calc_fn(p, b)

    print(f"\n  --- Result ---")
    if mult is None:
        print(f"    {name}: None  (total_activity < 1)")
    else:
        print(f"    {name}: {round(mult, 4)}")

    # ── Component breakdown ───────────────────────────────────────────────────
    if mult is None:
        return

    sacks   = p["def_sacks"]
    hits    = p["qb_hits"]
    hurries = p["hurries"]
    tackles = p["tackles"]
    ast     = p["ast_tackles"]
    tfl     = p["tackles_for_loss"]
    pds     = p["passes_defended"]
    ints    = p["interceptions"]
    ff      = p["def_fumbles_forced"]

    if pos_upper in FRONT7:
        # --- Front-7 breakdown ---
        avg_pressure = 0.0
        if b:
            avg_pressure = (_safe(b.get("avg_def_sacks"))*3.0 +
                            _safe(b.get("avg_qb_hits"))  *1.5 +
                            _safe(b.get("avg_hurries"))  *0.75)
        game_pressure = sacks*3.0 + hits*1.5 + hurries*0.75
        pressure_denom = max(avg_pressure, 2.0)
        pressure_m = max(0.5, min(1.8, 1.0 + (game_pressure - avg_pressure) / pressure_denom))

        avg_run = max(_safe((b or {}).get("avg_tackles") or 3.0), 0.5)
        run_stop = tackles + ast*0.5 + tfl*2.0
        run_m = max(0.5, min(1.8, 1.0 + (run_stop - avg_run)*0.08))

        tackle_quality_m = max(0.5, min(1.2, 1.0 - p["missed_tackles"]*0.15))

        avg_to = 0.0
        if b:
            avg_to = (_safe(b.get("avg_interceptions"))*1.5 + _safe(b.get("avg_fumbles_forced"))*1.0)
        to_score = ints*1.5 + ff*1.0
        turnover_m = max(0.7, min(1.8, 1.0 + (to_score - avg_to)*0.30))

        coverage_m = max(0.6, min(1.5, 1.0 + pds*0.04 + ints*0.05))

        print(f"\n  Component breakdown (front-7):")
        print(f"    pressure_m       (0.35): {pressure_m:.4f}")
        print(f"      game={game_pressure:.2f}  avg={avg_pressure:.2f}  denom={pressure_denom:.2f}")
        print(f"      [Note: qb_hits/hurries absent from nflverse — pressure likely understated]")
        print(f"    run_m            (0.25): {run_m:.4f}")
        print(f"      run_stop={run_stop:.1f}  avg={avg_run:.2f}")
        print(f"    tackle_quality_m (0.15): {tackle_quality_m:.4f}")
        print(f"    turnover_m       (0.15): {turnover_m:.4f}")
        print(f"      INTs={ints:.0f}  FF={ff:.0f}  to_score={to_score:.1f}  avg={avg_to:.2f}")
        print(f"    coverage_m       (0.10): {coverage_m:.4f}")
        print(f"      PDs={pds:.0f}  INTs={ints:.0f}")

    else:
        # --- Secondary breakdown ---
        coverage_m = max(0.4, min(2.0, 1.0 + pds*0.07 + ints*0.15))

        avg_play = 0.0
        if b:
            avg_play = (_safe(b.get("avg_passes_defended"))*0.5 +
                        _safe(b.get("avg_interceptions"))  *1.5 +
                        _safe(b.get("avg_fumbles_forced")) *1.0)
        play_score = pds*0.5 + ints*1.5 + ff*1.0
        play_baseline = max(avg_play, 0.5)
        play_m = max(0.5, min(2.5, 1.0 + (play_score - avg_play)/play_baseline*0.5))

        avg_tackles = _safe((b or {}).get("avg_tackles") or 4.0)
        tackle_score = tackles + ast*0.5 - p["missed_tackles"]*1.5
        tackle_m = max(0.5, min(1.5, 1.0 + (tackle_score - avg_tackles)*0.05))

        avg_to = 0.0
        if b:
            avg_to = (_safe(b.get("avg_interceptions"))*2.0 + _safe(b.get("avg_fumbles_forced"))*1.0)
        to_score = ints*2.0 + ff*1.0
        turnover_m = max(0.7, min(2.0, 1.0 + (to_score - avg_to)*0.25))

        avg_pressure = 0.0
        if b:
            avg_pressure = (_safe(b.get("avg_def_sacks"))*3.0 +
                            _safe(b.get("avg_qb_hits"))  *1.0 +
                            _safe(b.get("avg_hurries"))  *0.5)
        pressure = sacks*3.0 + hits*1.0 + hurries*0.5
        pressure_denom = max(avg_pressure, 1.0)
        pressure_m = max(0.8, min(1.3, 1.0 + (pressure - avg_pressure)/pressure_denom*0.4))

        print(f"\n  Component breakdown (secondary):")
        print(f"    coverage_m  (0.35): {coverage_m:.4f}")
        print(f"      PDs={pds:.0f}  INTs={ints:.0f}")
        print(f"      [Note: def_targets/completions_allowed not in nflverse — coverage partial]")
        print(f"    play_m      (0.25): {play_m:.4f}")
        print(f"      play_score={play_score:.2f}  avg_play={avg_play:.2f}  baseline={play_baseline:.2f}")
        print(f"    tackle_m    (0.20): {tackle_m:.4f}")
        print(f"      tackles={tackles:.0f}  ast={ast:.0f}  avg={avg_tackles:.2f}")
        print(f"    turnover_m  (0.15): {turnover_m:.4f}")
        print(f"      INTs={ints:.0f}  FF={ff:.0f}  to_score={to_score:.1f}  avg={avg_to:.2f}")
        print(f"    pressure_m  (0.05): {pressure_m:.4f}")


def main():
    print("Loading nflverse player stats (2023)...")
    try:
        df = nfl.load_player_stats([SEASON], stat_type="defense").to_pandas()
        print(f"  Loaded {len(df)} rows (defense).")
    except (TypeError, Exception) as e:
        print(f"  [!] stat_type='defense' failed ({e}), loading all stats...")
        df = nfl.load_player_stats([SEASON]).to_pandas()
        print(f"  Loaded {len(df)} rows (all positions).")

    def_cols = [c for c in df.columns if c.startswith("def_")]
    print(f"  Defensive columns: {def_cols}")

    for entry in PLAYERS:
        run_player(df, entry["name"], entry["team"], entry["position"])

    print("\n" + "=" * 62)


if __name__ == "__main__":
    main()
