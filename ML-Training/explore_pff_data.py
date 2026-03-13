"""
PFF Data Exploration Script

Run this BEFORE building team_pff_profiles to understand:
  - What seasons/teams are in each PFF table
  - Null rates per column
  - Grade distributions
  - Whether team_name values match the team_id format used in games/team_rankings

Usage:
    python explore_pff_data.py
"""

import os
import pg8000
import pandas as pd
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))


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


def query(conn, sql, params=None):
    cur = conn.cursor()
    cur.execute(sql, params or [])
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    cur.close()
    return pd.DataFrame(rows, columns=cols)


def explore_table(conn, table: str, grade_cols: list[str]):
    print(f"\n{'='*60}")
    print(f"TABLE: {table}")
    print('='*60)

    # Row counts by season
    df = query(conn, f"SELECT season, COUNT(*) AS rows, COUNT(DISTINCT team_name) AS teams FROM {table} GROUP BY season ORDER BY season")
    print("\nRows + teams per season:")
    print(df.to_string(index=False))

    # Sample team_name values
    df_teams = query(conn, f"SELECT DISTINCT team_name FROM {table} ORDER BY team_name LIMIT 40")
    print(f"\nDistinct team_name values ({len(df_teams)} total):")
    print("  " + ", ".join(df_teams['team_name'].tolist()))

    # Null rates per grade column
    null_checks = ", ".join([f"ROUND(100.0 * SUM(CASE WHEN {c} IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS {c}_null_pct" for c in grade_cols])
    df_nulls = query(conn, f"SELECT {null_checks} FROM {table}")
    print(f"\nNull rates (%):")
    for col in df_nulls.columns:
        print(f"  {col}: {df_nulls[col].iloc[0]}%")

    # Grade distributions per column (for latest season)
    latest = query(conn, f"SELECT MAX(season) AS s FROM {table}").iloc[0]['s']
    for col in grade_cols:
        df_dist = query(conn, f"""
            SELECT ROUND(AVG({col})::numeric, 2) AS mean,
                   ROUND(MIN({col})::numeric, 2) AS min,
                   ROUND(MAX({col})::numeric, 2) AS max,
                   ROUND(STDDEV({col})::numeric, 2) AS stddev
            FROM {table} WHERE season = %s AND {col} IS NOT NULL
        """, [latest])
        row = df_dist.iloc[0]
        print(f"  {col} (season {latest}): mean={row['mean']}, min={row['min']}, max={row['max']}, std={row['stddev']}")


def check_team_name_alignment(conn):
    """Check whether pff table team_names align with team_id in games table."""
    print(f"\n{'='*60}")
    print("TEAM NAME ALIGNMENT CHECK")
    print('='*60)

    games_teams = query(conn, "SELECT DISTINCT home_team AS team FROM games UNION SELECT DISTINCT away_team FROM games ORDER BY team")
    print(f"\nTeam IDs in games table ({len(games_teams)}):")
    print("  " + ", ".join(games_teams['team'].tolist()))

    for table in ['pff_def_grades', 'pff_qb_grades', 'pff_wr_grades', 'pff_rb_grades', 'pff_ol_grades']:
        pff_teams = query(conn, f"SELECT DISTINCT team_name FROM {table} ORDER BY team_name")
        pff_set = set(pff_teams['team_name'].tolist())
        games_set = set(games_teams['team'].tolist())
        missing_in_pff = games_set - pff_set
        extra_in_pff = pff_set - games_set
        print(f"\n{table}:")
        print(f"  Distinct teams: {len(pff_set)}")
        if missing_in_pff:
            print(f"  Games teams NOT in PFF: {sorted(missing_in_pff)}")
        if extra_in_pff:
            print(f"  PFF names NOT in games: {sorted(extra_in_pff)}")
        if not missing_in_pff and not extra_in_pff:
            print("  PERFECT MATCH")


def preview_aggregation(conn):
    """Preview what the team-level PFF aggregation will look like."""
    print(f"\n{'='*60}")
    print("PREVIEW: TEAM-LEVEL DEFENSIVE AGGREGATION (sample)")
    print('='*60)

    df = query(conn, """
        SELECT
            team_name,
            season,
            COUNT(*) AS player_count,
            ROUND(AVG(grades_defense)::numeric, 2)      AS avg_defense,
            ROUND(AVG(grades_pass_rush)::numeric, 2)    AS avg_pass_rush,
            ROUND(AVG(grades_run_defense)::numeric, 2)  AS avg_run_defense,
            ROUND(AVG(grades_coverage)::numeric, 2)     AS avg_coverage
        FROM pff_def_grades
        WHERE season = (SELECT MAX(season) FROM pff_def_grades)
        GROUP BY team_name, season
        ORDER BY avg_defense DESC
        LIMIT 10
    """)
    print("\nTop 10 defenses by avg overall grade (latest season):")
    print(df.to_string(index=False))

    print(f"\n{'='*60}")
    print("PREVIEW: TEAM-LEVEL OFFENSIVE AGGREGATION (sample)")
    print('='*60)

    df_off = query(conn, """
        SELECT
            q.team_name,
            q.season,
            ROUND(AVG(q.grades_pass)::numeric, 2)       AS qb_pass_grade,
            ROUND(AVG(r.grades_offense)::numeric, 2)    AS rb_grade,
            ROUND(AVG(o.grades_pass_block)::numeric, 2) AS ol_pass_block,
            ROUND(AVG(o.grades_run_block)::numeric, 2)  AS ol_run_block
        FROM pff_qb_grades q
        LEFT JOIN pff_rb_grades r ON q.team_name = r.team_name AND q.season = r.season
        LEFT JOIN pff_ol_grades o ON q.team_name = o.team_name AND q.season = o.season
        WHERE q.season = (SELECT MAX(season) FROM pff_qb_grades)
        GROUP BY q.team_name, q.season
        ORDER BY qb_pass_grade DESC
        LIMIT 10
    """)
    print("\nTop 10 offenses by QB pass grade (latest season):")
    print(df_off.to_string(index=False))


def main():
    print("Connecting to Supabase...")
    conn = get_connection()
    print("Connected.")

    explore_table(conn, 'pff_def_grades', [
        'grades_defense', 'grades_pass_rush', 'grades_run_defense',
        'grades_coverage', 'grades_tackling'
    ])

    explore_table(conn, 'pff_qb_grades', [
        'grades_offense', 'grades_pass', 'grades_run'
    ])

    explore_table(conn, 'pff_wr_grades', [
        'grades_offense', 'grades_pass_route', 'grades_hands_drop'
    ])

    explore_table(conn, 'pff_rb_grades', [
        'grades_offense'
    ])

    explore_table(conn, 'pff_ol_grades', [
        'grades_offense', 'grades_pass_block', 'grades_run_block'
    ])

    check_team_name_alignment(conn)
    preview_aggregation(conn)

    conn.close()
    print("\nDone. Review output above before running build_pff_profiles.py")


if __name__ == "__main__":
    main()
