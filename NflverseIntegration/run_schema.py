"""
run_schema.py
=============
Runs NflverseIntegration/schema.sql against Supabase via pg8000.
Reads credentials from ML-Training/.env (DB_* prefix) OR from
SUPABASE_DB_* env vars if set.
"""
import os
import sys

import pg8000

# ── Credential resolution ─────────────────────────────────────────────────────
# Accept either naming convention
HOST     = os.environ.get("SUPABASE_DB_HOST")     or os.environ.get("DB_HOST")
PORT     = int(os.environ.get("SUPABASE_DB_PORT")  or os.environ.get("DB_PORT") or 5432)
DBNAME   = os.environ.get("SUPABASE_DB_NAME")     or os.environ.get("DB_NAME")
USER     = os.environ.get("SUPABASE_DB_USER")     or os.environ.get("DB_USER")
PASSWORD = os.environ.get("SUPABASE_DB_PASSWORD") or os.environ.get("DB_PASSWORD")

if not all([HOST, DBNAME, USER, PASSWORD]):
    print("ERROR: DB credentials not set. Expected DB_HOST/DB_NAME/DB_USER/DB_PASSWORD")
    sys.exit(1)

SQL_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

with open(SQL_PATH, "r") as f:
    sql = f.read()

print(f"Connecting to {HOST}:{PORT} / {DBNAME} as {USER}")

conn = pg8000.connect(
    host=HOST,
    database=DBNAME,
    user=USER,
    password=PASSWORD,
    port=PORT,
    ssl_context=True,
)
cur = conn.cursor()

# Execute each statement individually (split on blank lines between statements)
statements = [s.strip() for s in sql.split(";") if s.strip()]
ok = 0
for stmt in statements:
    try:
        cur.execute(stmt)
        ok += 1
        # Show first line of each statement for visibility
        print(f"  OK: {stmt.splitlines()[0][:80]}")
    except Exception as e:
        print(f"  ERROR on: {stmt.splitlines()[0][:80]}")
        print(f"         -> {e}")

conn.commit()
cur.close()
conn.close()
print(f"\nDone: {ok}/{len(statements)} statements executed successfully.")
