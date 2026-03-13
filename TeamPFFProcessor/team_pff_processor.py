"""
TeamPFFProcessor

Computes team-level PFF matchup features for every game in game_id_mapping
and UPDATEs those rows with 38 new columns.

Data sources:
  - pff_team_offense     (team, season, overall_grade, offense_grade, passing_grade,
                          pass_block_grade, run_grade, ...)
  - pff_team_defense     (team, season, defense_grade, run_defense_grade,
                          coverage_grade, pass_rush_grade, ...)
  - pff_team_special_teams (team, season, special_teams_grade)
  - games                (game_id, home_team, away_team, season, game_type)
  - game_id_mapping      (game_id — rows to UPDATE)

Leakage rule:
  A game in season N uses PFF grades from season N-1.
  2022 games → no 2021 data → all PFF columns remain NULL → fillna(0) at training.

Run order:
  1. Run alter_game_id_mapping.sql in Supabase SQL Editor
  2. python team_pff_processor.py
  3. python ML-Training/generate_training_data.py
  4. python ML-Training/train_model.py

Usage:
  python team_pff_processor.py              # processes all games
  python team_pff_processor.py --season 2024  # single season only
"""

import os
import sys
import logging
import argparse
from decimal import Decimal

import pg8000
import pandas as pd

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'ML-Training', '.env'))
except ImportError:
    pass  # Lambda gets credentials from environment variables directly

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
# Lambda runtime sets up root logger before user code runs, so basicConfig is a no-op.
# Force level directly so logger.info() shows in CloudWatch.
logging.getLogger().setLevel(logging.INFO)
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# DB connection (mirrors generate_training_data.py pattern)
# ---------------------------------------------------------------------------

def get_connection():
    host     = (os.environ.get('SUPABASE_DB_HOST') or os.environ.get('DB_HOST', '')).strip()
    port     = int((os.environ.get('SUPABASE_DB_PORT') or os.environ.get('DB_PORT', '6543')).strip())
    database = (os.environ.get('SUPABASE_DB_NAME') or os.environ.get('DB_NAME', '')).strip()
    user     = (os.environ.get('SUPABASE_DB_USER') or os.environ.get('DB_USER', '')).strip()
    password = (os.environ.get('SUPABASE_DB_PASSWORD') or os.environ.get('DB_PASSWORD', '')).strip()
    conn = pg8000.connect(host=host, port=port, database=database,
                          user=user, password=password, ssl_context=True)
    conn.autocommit = False
    return conn


# ---------------------------------------------------------------------------
# Step 1: Load all PFF team grades from the 3 pff_team_* tables
# ---------------------------------------------------------------------------

GRADES_QUERY = """
SELECT
    o.team,
    o.season,
    o.overall_grade,
    o.offense_grade,
    o.passing_grade,
    o.pass_block_grade,
    o.run_grade,
    d.defense_grade,
    d.run_defense_grade,
    d.coverage_grade,
    d.pass_rush_grade,
    st.special_teams_grade
FROM pff_team_offense o
JOIN pff_team_defense d
    USING (team, season)
JOIN pff_team_special_teams st
    USING (team, season)
ORDER BY season, team
"""


def load_pff_grades(conn) -> pd.DataFrame:
    cur = conn.cursor()
    cur.execute(GRADES_QUERY)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    cur.close()
    df = pd.DataFrame(rows, columns=cols)
    # Cast all grade columns to float for arithmetic
    grade_cols = [c for c in df.columns if c not in ('team', 'season')]
    for c in grade_cols:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    logger.info(f"Loaded PFF grades: {len(df)} rows, seasons {sorted(df['season'].unique())}")
    return df


# ---------------------------------------------------------------------------
# Step 2: Compute per-season 1-32 rankings for each grade category
#   Rank 1 = best (highest grade), method='min' so ties share the better rank
# ---------------------------------------------------------------------------

RANK_SPECS = {
    # column to rank              → rank column name
    'run_grade':          'run_offense_rank',
    'passing_grade':      'pass_offense_rank',
    'run_defense_grade':  'run_defense_rank',
    'coverage_grade':     'pass_defense_rank',   # coverage = primary pass defense metric
    'pass_rush_grade':    'pass_rush_rank',
    'special_teams_grade':'special_teams_rank',
}


def compute_rankings(grades_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add rank columns to grades_df in-place.
    Rank 1 = highest grade = best team in that category.
    ascending=False means highest grade → rank 1.
    """
    ranked = grades_df.copy()
    for grade_col, rank_col in RANK_SPECS.items():
        ranked[rank_col] = (
            ranked.groupby('season')[grade_col]
            .rank(ascending=False, method='min')
            .astype('Int64')   # nullable int handles NaN seasons cleanly
        )
    logger.info(f"Computed rankings for {len(RANK_SPECS)} categories across {ranked['season'].nunique()} seasons")
    return ranked


# ---------------------------------------------------------------------------
# Step 3: Load all REG-season games that have a game_id_mapping row
# ---------------------------------------------------------------------------

GAMES_QUERY = """
SELECT
    g.game_id,
    g.home_team,
    g.away_team,
    g.season
FROM game_id_mapping gm
JOIN games g ON gm.game_id = g.game_id
WHERE g.game_type = 'REG'
ORDER BY g.season, g.week
"""


def load_games(conn, season_filter: int | None = None) -> pd.DataFrame:
    cur = conn.cursor()
    if season_filter:
        cur.execute(GAMES_QUERY.replace("ORDER BY", f"AND g.season = {season_filter}\nORDER BY"))
    else:
        cur.execute(GAMES_QUERY)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    cur.close()
    df = pd.DataFrame(rows, columns=cols)
    logger.info(f"Loaded {len(df)} games to process")
    return df


# ---------------------------------------------------------------------------
# Step 4: For each game, look up previous-season grades + ranks and
#         compute all 38 matchup values
# ---------------------------------------------------------------------------

def _g(team_row: pd.Series | None, col: str) -> float:
    """Safe grade lookup — returns 0.0 if row is None or column is NaN."""
    if team_row is None:
        return 0.0
    val = team_row.get(col, 0.0)
    return float(val) if pd.notna(val) else 0.0


def _r(team_row: pd.Series | None, col: str) -> int | None:
    """Safe rank lookup — returns None if no data (will be NULL in DB)."""
    if team_row is None:
        return None
    val = team_row.get(col)
    return int(val) if pd.notna(val) else None


def compute_game_features(
    home_row: pd.Series | None,
    away_row: pd.Series | None,
) -> dict:
    """
    Given pre-filtered rows for home and away teams (previous season),
    compute all 38 matchup values.
    Returns a dict keyed by game_id_mapping column name.
    """
    # ---------- raw grades ----------
    h_off  = _g(home_row, 'offense_grade')
    h_def  = _g(home_row, 'defense_grade')
    h_run  = _g(home_row, 'run_grade')
    h_pass = _g(home_row, 'passing_grade')
    h_rdef = _g(home_row, 'run_defense_grade')
    h_cov  = _g(home_row, 'coverage_grade')
    h_pr   = _g(home_row, 'pass_rush_grade')
    h_pb   = _g(home_row, 'pass_block_grade')
    h_st   = _g(home_row, 'special_teams_grade')
    h_ovr  = _g(home_row, 'overall_grade')

    a_off  = _g(away_row, 'offense_grade')
    a_def  = _g(away_row, 'defense_grade')
    a_run  = _g(away_row, 'run_grade')
    a_pass = _g(away_row, 'passing_grade')
    a_rdef = _g(away_row, 'run_defense_grade')
    a_cov  = _g(away_row, 'coverage_grade')
    a_pr   = _g(away_row, 'pass_rush_grade')
    a_pb   = _g(away_row, 'pass_block_grade')
    a_st   = _g(away_row, 'special_teams_grade')
    a_ovr  = _g(away_row, 'overall_grade')

    # ---------- ranks ----------
    h_ror  = _r(home_row, 'run_offense_rank')
    h_por  = _r(home_row, 'pass_offense_rank')
    h_rdr  = _r(home_row, 'run_defense_rank')
    h_pdr  = _r(home_row, 'pass_defense_rank')
    h_prr  = _r(home_row, 'pass_rush_rank')
    h_str  = _r(home_row, 'special_teams_rank')

    a_ror  = _r(away_row, 'run_offense_rank')
    a_por  = _r(away_row, 'pass_offense_rank')
    a_rdr  = _r(away_row, 'run_defense_rank')
    a_pdr  = _r(away_row, 'pass_defense_rank')
    a_prr  = _r(away_row, 'pass_rush_rank')
    a_str  = _r(away_row, 'special_teams_rank')

    # ---------- matchup differentials (positive = home advantage) ----------
    # run game net: (home run attack vs away run def) - (away run attack vs home run def)
    run_matchup  = (h_run - a_rdef) - (a_run - h_rdef)
    # pass game net: (home pass attack vs away coverage) - (away pass attack vs home coverage)
    pass_matchup = (h_pass - a_cov) - (a_pass - h_cov)
    # trench net: (home pass rush vs away pass block) - (away pass rush vs home pass block)
    trench       = (h_pr - a_pb) - (a_pr - h_pb)
    # overall net: (home offense vs away defense) - (away offense vs home defense)
    overall      = (h_off - a_def) - (a_off - h_def)
    # special teams: straightforward home - away
    st_diff      = h_st - a_st
    # overall grade differential
    ovr_diff     = h_ovr - a_ovr

    # ---------- rank advantages (positive = home better, lower rank = better) ----------
    # e.g. away_run_defense_rank=25 vs home_run_offense_rank=5 → 25-5=+20 (big home run advantage)
    def _rank_adv(away_rank, home_rank):
        if away_rank is None or home_rank is None:
            return None
        return away_rank - home_rank

    return {
        # raw grades (16)
        'home_pff_offense':       round(h_off,  2) or None,
        'away_pff_offense':       round(a_off,  2) or None,
        'home_pff_defense':       round(h_def,  2) or None,
        'away_pff_defense':       round(a_def,  2) or None,
        'home_pff_run':           round(h_run,  2) or None,
        'away_pff_run':           round(a_run,  2) or None,
        'home_pff_passing':       round(h_pass, 2) or None,
        'away_pff_passing':       round(a_pass, 2) or None,
        'home_pff_run_defense':   round(h_rdef, 2) or None,
        'away_pff_run_defense':   round(a_rdef, 2) or None,
        'home_pff_coverage':      round(h_cov,  2) or None,
        'away_pff_coverage':      round(a_cov,  2) or None,
        'home_pff_pass_rush':     round(h_pr,   2) or None,
        'away_pff_pass_rush':     round(a_pr,   2) or None,
        'home_pff_special_teams': round(h_st,   2) or None,
        'away_pff_special_teams': round(a_st,   2) or None,
        # rankings (12)
        'home_run_offense_rank':   h_ror,
        'away_run_offense_rank':   a_ror,
        'home_pass_offense_rank':  h_por,
        'away_pass_offense_rank':  a_por,
        'home_run_defense_rank':   h_rdr,
        'away_run_defense_rank':   a_rdr,
        'home_pass_defense_rank':  h_pdr,
        'away_pass_defense_rank':  a_pdr,
        'home_pass_rush_rank':     h_prr,
        'away_pass_rush_rank':     a_prr,
        'home_special_teams_rank': h_str,
        'away_special_teams_rank': a_str,
        # matchup differentials (6)
        'matchup_run_off_vs_run_def':      round(run_matchup,  3),
        'matchup_pass_off_vs_coverage':    round(pass_matchup, 3),
        'matchup_pass_rush_vs_pass_block': round(trench,       3),
        'matchup_overall_off_vs_def':      round(overall,      3),
        'matchup_special_teams':           round(st_diff,      3),
        'pff_overall_diff':                round(ovr_diff,     3),
        # rank advantages (4)
        'rank_adv_run_game':       _rank_adv(a_rdr, h_ror),
        'rank_adv_pass_game':      _rank_adv(a_pdr, h_por),
        'rank_adv_rush_pressure':  _rank_adv(a_por, h_prr),   # home pass rush vs away pass offense
        'rank_adv_special_teams':  _rank_adv(a_str, h_str),
    }


# ---------------------------------------------------------------------------
# The UPDATE query — set all 38 columns for a given game_id
# ---------------------------------------------------------------------------

UPDATE_COLS = [
    'home_pff_offense', 'away_pff_offense',
    'home_pff_defense', 'away_pff_defense',
    'home_pff_run', 'away_pff_run',
    'home_pff_passing', 'away_pff_passing',
    'home_pff_run_defense', 'away_pff_run_defense',
    'home_pff_coverage', 'away_pff_coverage',
    'home_pff_pass_rush', 'away_pff_pass_rush',
    'home_pff_special_teams', 'away_pff_special_teams',
    'home_run_offense_rank', 'away_run_offense_rank',
    'home_pass_offense_rank', 'away_pass_offense_rank',
    'home_run_defense_rank', 'away_run_defense_rank',
    'home_pass_defense_rank', 'away_pass_defense_rank',
    'home_pass_rush_rank', 'away_pass_rush_rank',
    'home_special_teams_rank', 'away_special_teams_rank',
    'matchup_run_off_vs_run_def',
    'matchup_pass_off_vs_coverage',
    'matchup_pass_rush_vs_pass_block',
    'matchup_overall_off_vs_def',
    'matchup_special_teams',
    'pff_overall_diff',
    'rank_adv_run_game',
    'rank_adv_pass_game',
    'rank_adv_rush_pressure',
    'rank_adv_special_teams',
]

SET_CLAUSE = ", ".join(f"{c} = %s" for c in UPDATE_COLS)
UPDATE_SQL = f"UPDATE game_id_mapping SET {SET_CLAUSE} WHERE game_id = %s"


# ---------------------------------------------------------------------------
# Team abbreviation bridge
# Maps games-table abbreviations (Sportradar) → PFF abbreviations stored in pff_team_* tables
# ---------------------------------------------------------------------------
GAMES_TO_PFF = {
    'JAC': 'JAX',   # Jaguars — Sportradar uses JAC, PFF uses JAX
    'LA':  'LAR',   # Rams — some sources use LA, PFF uses LAR
}

def _to_pff(team: str) -> str:
    return GAMES_TO_PFF.get(team.upper(), team.upper())


# ---------------------------------------------------------------------------
# Main processing loop
# ---------------------------------------------------------------------------

def process(conn, season_filter: int | None = None, batch_size: int = 50):
    grades_df = load_pff_grades(conn)
    ranked_df = compute_rankings(grades_df)

    # Index into a dict keyed by (team, season) for O(1) lookup
    pff_lookup: dict[tuple, pd.Series] = {
        (row['team'], int(row['season'])): row
        for _, row in ranked_df.iterrows()
    }

    games_df = load_games(conn, season_filter)

    # Log all team names in PFF lookup so we can spot mismatches
    pff_teams_by_season = {}
    for (team, ssn) in pff_lookup.keys():
        pff_teams_by_season.setdefault(ssn, set()).add(team)
    for ssn in sorted(pff_teams_by_season):
        logger.info(f"PFF teams available season {ssn}: {sorted(pff_teams_by_season[ssn])}")

    # Log all distinct team names in games table
    game_teams = set(games_df['home_team'].str.upper().tolist() + games_df['away_team'].str.upper().tolist())
    logger.info(f"Games table team abbreviations: {sorted(game_teams)}")

    # Log which teams won't resolve after mapping
    missing_teams = set()
    for t in game_teams:
        mapped = _to_pff(t)
        sample_season = (games_df[games_df['season'] == (games_df['season'].max())]).iloc[0]['season'] if len(games_df) else 2024
        if (mapped, int(sample_season)) not in pff_lookup:
            missing_teams.add(f"{t}→{mapped}")
    if missing_teams:
        logger.warning(f"Teams with no PFF mapping: {sorted(missing_teams)}")

    updated = skipped = no_data = 0
    missing_team_log: dict[str, int] = {}
    batch_params = []

    for _, game in games_df.iterrows():
        game_id   = game['game_id']
        home_team = _to_pff(game['home_team'])
        away_team = _to_pff(game['away_team'])
        season    = int(game['season'])
        home_row = pff_lookup.get((home_team, season))
        away_row = pff_lookup.get((away_team, season))

        if home_row is None:
            missing_team_log[home_team] = missing_team_log.get(home_team, 0) + 1
        if away_row is None:
            missing_team_log[away_team] = missing_team_log.get(away_team, 0) + 1

        if home_row is None and away_row is None:
            no_data += 1
            continue

        features = compute_game_features(home_row, away_row)
        row_vals = tuple(features[c] for c in UPDATE_COLS) + (game_id,)
        batch_params.append(row_vals)

        if len(batch_params) >= batch_size:
            _flush(conn, batch_params)
            updated += len(batch_params)
            batch_params = []

    if batch_params:
        _flush(conn, batch_params)
        updated += len(batch_params)

    conn.commit()
    if missing_team_log:
        logger.warning(f"Teams with missing PFF data (games affected): {dict(sorted(missing_team_log.items()))}")
    logger.info(
        f"Done. Updated={updated}, both_teams_missing={no_data}, skipped={skipped}"
    )
    return updated


def _flush(conn, batch_params: list):
    cur = conn.cursor()
    for params in batch_params:
        cur.execute(UPDATE_SQL, params)
    cur.close()


# ---------------------------------------------------------------------------
# Validation printout
# ---------------------------------------------------------------------------

def validate(conn, season: int = 2024):
    query = """
        SELECT
            COUNT(*) AS total_games,
            COUNT(home_pff_offense) AS games_with_pff,
            ROUND(AVG(matchup_overall_off_vs_def)::numeric, 2) AS avg_matchup_overall,
            ROUND(AVG(pff_overall_diff)::numeric, 2)           AS avg_overall_diff
        FROM game_id_mapping gm
        JOIN games g ON gm.game_id = g.game_id
        WHERE g.season = %s AND g.game_type = 'REG'
    """
    cur = conn.cursor()
    cur.execute(query, (season,))
    row = cur.fetchone()
    cur.close()
    if row:
        print(f"\nValidation (season {season}):")
        print(f"  Total REG games:       {row[0]}")
        print(f"  Games with PFF data:   {row[1]}")
        print(f"  Avg matchup_overall:   {row[2]}")
        print(f"  Avg pff_overall_diff:  {row[3]}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Compute team PFF matchup features for game_id_mapping")
    parser.add_argument('--season', type=int, default=None,
                        help="Process only this season (default: all seasons)")
    parser.add_argument('--batch-size', type=int, default=50)
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("TEAM PFF PROCESSOR")
    logger.info("=" * 60)
    if args.season:
        logger.info(f"Season filter: {args.season}")

    conn = get_connection()
    try:
        updated = process(conn, season_filter=args.season, batch_size=args.batch_size)
        validate(conn, season=args.season or 2024)
        print(f"\nDone! {updated} games updated in game_id_mapping.")
        print("Next: python ML-Training/generate_training_data.py")
    finally:
        conn.close()


def lambda_handler(event, context):
    """
    AWS Lambda entry point.

    Event formats:
      {}                          — process all seasons
      {"season": 2024}            — single season only
      {"seasons": [2023, 2024]}   — multiple specific seasons
    """
    import json

    logger.info(f"Event: {json.dumps(event)}")

    seasons = None
    if "season" in event:
        seasons = [int(event["season"])]
    elif "seasons" in event:
        seasons = [int(s) for s in event["seasons"]]

    conn = get_connection()
    results = []
    try:
        if seasons:
            for s in seasons:
                updated = process(conn, season_filter=s)
                results.append({"season": s, "updated": updated})
        else:
            updated = process(conn)
            results.append({"season": "all", "updated": updated})
    finally:
        conn.close()

    return {
        "statusCode": 200,
        "body": json.dumps({"success": True, "results": results}),
    }


if __name__ == "__main__":
    main()
