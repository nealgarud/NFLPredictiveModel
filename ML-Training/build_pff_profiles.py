"""
Build Team PFF Profiles

Aggregates player-level PFF grades into one team-season row per team.
Creates (or replaces) the `team_pff_profiles` table in Supabase.

Run AFTER explore_pff_data.py has confirmed the data looks correct.
Run BEFORE generate_training_data.py.

What this produces (one row per team per season):
  Defensive grades:
    def_grade          — overall defensive grade (all defenders)
    pass_rush_grade    — pass rush (EDGE + DT weighted)
    run_def_grade      — run defense (DT + LB weighted)
    coverage_grade     — coverage (CB + S weighted)

  Offensive grades:
    qb_grade           — QB passing grade
    rb_grade           — RB offensive grade
    ol_pass_block      — OL pass blocking grade
    ol_run_block       — OL run blocking grade

  Derived:
    off_run_pass_ratio — ol_run_block / ol_pass_block  (>1 = run-heavy OL)

Leakage note: This table is indexed by (team_name, season).
generate_training_data.py joins on g.season - 1, so 2024 games
use 2023 PFF profiles — same pattern as all other features.
"""

import os
import pg8000
import pandas as pd
import logging
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_connection():
    host = (os.environ.get('SUPABASE_DB_HOST') or os.environ.get('DB_HOST', '')).strip()
    port = int((os.environ.get('SUPABASE_DB_PORT') or os.environ.get('DB_PORT', '6543')).strip())
    database = (os.environ.get('SUPABASE_DB_NAME') or os.environ.get('DB_NAME', '')).strip()
    user = (os.environ.get('SUPABASE_DB_USER') or os.environ.get('DB_USER', '')).strip()
    password = (os.environ.get('SUPABASE_DB_PASSWORD') or os.environ.get('DB_PASSWORD', '')).strip()
    conn = pg8000.connect(host=host, port=port, database=database,
                          user=user, password=password, ssl_context=True)
    conn.autocommit = True
    return conn


# ---------------------------------------------------------------------------
# DDL — create the target table if it doesn't exist
# ---------------------------------------------------------------------------

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS team_pff_profiles (
    team_name       VARCHAR(10)  NOT NULL,
    season          INT          NOT NULL,

    -- Defensive grades (team averages from pff_def_grades)
    def_grade           NUMERIC(5,2),
    pass_rush_grade     NUMERIC(5,2),
    run_def_grade       NUMERIC(5,2),
    coverage_grade      NUMERIC(5,2),

    -- Offensive grades
    qb_grade            NUMERIC(5,2),   -- from pff_qb_grades
    rb_grade            NUMERIC(5,2),   -- from pff_rb_grades
    ol_pass_block       NUMERIC(5,2),   -- from pff_ol_grades
    ol_run_block        NUMERIC(5,2),   -- from pff_ol_grades

    -- Derived
    off_run_pass_ratio  NUMERIC(6,4),   -- ol_run_block / ol_pass_block

    PRIMARY KEY (team_name, season)
);
"""

# ---------------------------------------------------------------------------
# Aggregation query — one row per (team_name, season) across all PFF tables
#
# Position weights for defensive aggregation:
#   pass_rush: EDGE=1.5, DT=1.0 (pass rushers matter most)
#   run_def:   DT=1.5,  LB=1.2, EDGE=0.8
#   coverage:  CB=1.5,  S=1.2,  LB=0.5
#
# Using COALESCE so a team with no RBs/QBs still gets a row (NULLs allowed).
# ---------------------------------------------------------------------------

AGGREGATION_QUERY = """
WITH def_agg AS (
    SELECT
        team_name,
        season,
        AVG(grades_defense) AS def_grade,
        -- Pass rush: weight EDGE higher than DT
        SUM(grades_pass_rush * CASE position WHEN 'EDGE' THEN 1.5 WHEN 'DT' THEN 1.0 ELSE 0.8 END)
            / NULLIF(SUM(CASE WHEN grades_pass_rush IS NOT NULL
                              THEN CASE position WHEN 'EDGE' THEN 1.5 WHEN 'DT' THEN 1.0 ELSE 0.8 END
                              ELSE 0 END), 0)            AS pass_rush_grade,
        -- Run defense: weight DT and LB higher
        SUM(grades_run_defense * CASE position WHEN 'DT' THEN 1.5 WHEN 'LB' THEN 1.2 WHEN 'EDGE' THEN 0.8 ELSE 0.7 END)
            / NULLIF(SUM(CASE WHEN grades_run_defense IS NOT NULL
                              THEN CASE position WHEN 'DT' THEN 1.5 WHEN 'LB' THEN 1.2 WHEN 'EDGE' THEN 0.8 ELSE 0.7 END
                              ELSE 0 END), 0)            AS run_def_grade,
        -- Coverage: weight CB and S higher
        SUM(grades_coverage * CASE position WHEN 'CB' THEN 1.5 WHEN 'S' THEN 1.2 WHEN 'LB' THEN 0.5 ELSE 0.6 END)
            / NULLIF(SUM(CASE WHEN grades_coverage IS NOT NULL
                              THEN CASE position WHEN 'CB' THEN 1.5 WHEN 'S' THEN 1.2 WHEN 'LB' THEN 0.5 ELSE 0.6 END
                              ELSE 0 END), 0)            AS coverage_grade
    FROM pff_def_grades
    GROUP BY team_name, season
),
qb_agg AS (
    SELECT team_name, season, AVG(grades_pass) AS qb_grade
    FROM pff_qb_grades
    GROUP BY team_name, season
),
rb_agg AS (
    SELECT team_name, season, AVG(grades_offense) AS rb_grade
    FROM pff_rb_grades
    GROUP BY team_name, season
),
ol_agg AS (
    SELECT
        team_name,
        season,
        AVG(grades_pass_block) AS ol_pass_block,
        AVG(grades_run_block)  AS ol_run_block
    FROM pff_ol_grades
    GROUP BY team_name, season
)
SELECT
    d.team_name,
    d.season,
    ROUND(d.def_grade::numeric,       2) AS def_grade,
    ROUND(d.pass_rush_grade::numeric, 2) AS pass_rush_grade,
    ROUND(d.run_def_grade::numeric,   2) AS run_def_grade,
    ROUND(d.coverage_grade::numeric,  2) AS coverage_grade,
    ROUND(q.qb_grade::numeric,        2) AS qb_grade,
    ROUND(r.rb_grade::numeric,        2) AS rb_grade,
    ROUND(o.ol_pass_block::numeric,   2) AS ol_pass_block,
    ROUND(o.ol_run_block::numeric,    2) AS ol_run_block,
    ROUND(
        CASE WHEN o.ol_pass_block > 0
             THEN o.ol_run_block / o.ol_pass_block
             ELSE NULL END::numeric, 4
    ) AS off_run_pass_ratio
FROM def_agg d
LEFT JOIN qb_agg q USING (team_name, season)
LEFT JOIN rb_agg r USING (team_name, season)
LEFT JOIN ol_agg o USING (team_name, season)
ORDER BY d.season, d.team_name
"""

UPSERT_SQL = """
INSERT INTO team_pff_profiles
    (team_name, season, def_grade, pass_rush_grade, run_def_grade, coverage_grade,
     qb_grade, rb_grade, ol_pass_block, ol_run_block, off_run_pass_ratio)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (team_name, season) DO UPDATE SET
    def_grade           = EXCLUDED.def_grade,
    pass_rush_grade     = EXCLUDED.pass_rush_grade,
    run_def_grade       = EXCLUDED.run_def_grade,
    coverage_grade      = EXCLUDED.coverage_grade,
    qb_grade            = EXCLUDED.qb_grade,
    rb_grade            = EXCLUDED.rb_grade,
    ol_pass_block       = EXCLUDED.ol_pass_block,
    ol_run_block        = EXCLUDED.ol_run_block,
    off_run_pass_ratio  = EXCLUDED.off_run_pass_ratio
"""


def create_table(conn):
    cur = conn.cursor()
    cur.execute(CREATE_TABLE_SQL)
    cur.close()
    logger.info("team_pff_profiles table ready")


def build_profiles(conn) -> pd.DataFrame:
    logger.info("Running PFF aggregation query...")
    cur = conn.cursor()
    cur.execute(AGGREGATION_QUERY)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    cur.close()
    df = pd.DataFrame(rows, columns=cols)
    logger.info(f"Aggregated {len(df)} team-season rows across {df['season'].nunique()} seasons")
    return df


def upsert_profiles(conn, df: pd.DataFrame):
    cur = conn.cursor()
    inserted = 0
    for _, row in df.iterrows():
        cur.execute(UPSERT_SQL, (
            row['team_name'], int(row['season']),
            row['def_grade'],       row['pass_rush_grade'],
            row['run_def_grade'],   row['coverage_grade'],
            row['qb_grade'],        row['rb_grade'],
            row['ol_pass_block'],   row['ol_run_block'],
            row['off_run_pass_ratio'],
        ))
        inserted += 1
    cur.close()
    logger.info(f"Upserted {inserted} rows into team_pff_profiles")


def validate(conn):
    """Spot-check: print a sample and confirm null rates."""
    cur = conn.cursor()
    cur.execute("""
        SELECT season, COUNT(*) AS teams,
               ROUND(100.0*SUM(CASE WHEN def_grade IS NULL THEN 1 ELSE 0 END)/COUNT(*),1) AS def_null_pct,
               ROUND(100.0*SUM(CASE WHEN qb_grade IS NULL THEN 1 ELSE 0 END)/COUNT(*),1) AS qb_null_pct
        FROM team_pff_profiles
        GROUP BY season ORDER BY season
    """)
    rows = cur.fetchall()
    cur.close()
    print("\nValidation — rows per season:")
    print(f"  {'Season':<8} {'Teams':<8} {'def_null%':<12} {'qb_null%'}")
    for r in rows:
        print(f"  {r[0]:<8} {r[1]:<8} {r[2]:<12} {r[3]}")


def main():
    logger.info("=" * 60)
    logger.info("BUILDING TEAM PFF PROFILES")
    logger.info("=" * 60)

    conn = get_connection()
    logger.info("Connected to Supabase")

    create_table(conn)
    df = build_profiles(conn)

    print("\nSample rows (top 5 defenses, latest season):")
    latest = df['season'].max()
    sample = df[df['season'] == latest].sort_values('def_grade', ascending=False).head(5)
    print(sample[['team_name', 'season', 'def_grade', 'pass_rush_grade', 'run_def_grade', 'coverage_grade']].to_string(index=False))

    print("\nSample rows (top 5 offenses by QB grade, latest season):")
    sample_off = df[df['season'] == latest].sort_values('qb_grade', ascending=False).head(5)
    print(sample_off[['team_name', 'season', 'qb_grade', 'rb_grade', 'ol_pass_block', 'ol_run_block', 'off_run_pass_ratio']].to_string(index=False))

    upsert_profiles(conn, df)
    validate(conn)

    conn.close()
    logger.info("Done. Run generate_training_data.py next.")


if __name__ == "__main__":
    main()
