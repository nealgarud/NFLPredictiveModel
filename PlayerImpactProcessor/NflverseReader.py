"""
NflverseReader.py — PlayerImpactProcessor
==========================================
Reads nflverse per-game stats and rolling baselines from Supabase.
Returns dicts keyed by normalised player display name so the orchestrator
can match them against Sportradar player records.

Tables read (written by NflverseIntegration/NflverseDataFetcher.py):
    nflverse_qb_stats  — cpoe, passing_epa, passing_air_yards, sacks_suffered
    nflverse_rb_stats  — rushing_epa, rushing_first_downs, receiving_yards …
    nflverse_wr_stats  — receiving_epa, wopr, target_share …

Name normalisation
------------------
Both nflverse and Sportradar use display names like "Patrick Mahomes".
_norm() lowercases, strips punctuation, and drops common suffixes (Jr/Sr/II…)
to maximise exact-match rate without needing fuzzy matching.
"""
import logging
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ── Name normalisation ────────────────────────────────────────────────────────

_SUFFIX_RE = re.compile(r'\b(jr|sr|ii|iii|iv|v)\b\.?$')


def _norm(name: str) -> str:
    """Lowercase, strip punctuation, collapse spaces, drop name suffixes."""
    n = (name or '').lower().strip()
    n = re.sub(r"['.,-]", '', n)
    n = _SUFFIX_RE.sub('', n).strip()
    n = re.sub(r'\s+', ' ', n)
    return n


# ── Reader class ──────────────────────────────────────────────────────────────

class NflverseReader:
    """
    Reads nflverse stats from the three nflverse_*_stats tables.
    Accepts a DatabaseUtils instance for connection parameters.
    Each method opens and closes its own connection to avoid state issues.
    """

    def __init__(self, db: Any):
        """
        db: DatabaseUtils instance — used for host/port/database/user/password only.
        """
        self._host     = db.host
        self._port     = db.port
        self._database = db.database
        self._user     = db.user
        self._password = db.password

    # ── Internal connection helper ────────────────────────────────────────────

    def _connect(self):
        import pg8000
        conn = pg8000.connect(
            host=self._host,
            port=self._port,
            database=self._database,
            user=self._user,
            password=self._password,
            ssl_context=True,
            timeout=120,
        )
        conn.autocommit = True
        return conn

    # ── Per-game stats (current week) ─────────────────────────────────────────

    def fetch_game_nflverse(self, season: int, week: int) -> Dict[str, Dict]:
        """
        Returns {norm_name: nv_game_dict} for all QB/RB/WR/TE players
        in the given season + week.

        Keys in nv_game_dict match exactly what the enhanced multiplier
        functions in GameImpactCalculator expect.
        """
        conn = self._connect()
        cur  = conn.cursor()
        result: Dict[str, Dict] = {}

        try:
            # ── QB ─────────────────────────────────────────────────────────────
            cur.execute(
                """
                SELECT player_name,
                    attempts, passing_air_yards, passing_epa, sacks_suffered,
                    cpoe, carries, rushing_yards, rushing_epa
                FROM nflverse_qb_stats
                WHERE season = %s AND week = %s AND attempts IS NOT NULL
                """,
                (season, week),
            )
            for row in cur.fetchall():
                name = _norm(row[0] or '')
                if not name:
                    continue
                result[name] = {
                    'attempts':          row[1],
                    'passing_air_yards': row[2],
                    'passing_epa':       float(row[3]) if row[3] is not None else 0.0,
                    'sacks':             row[4],
                    'cpoe':              float(row[5]) if row[5] is not None else 0.0,
                    'carries':           row[6],
                    'rushing_yards':     row[7],
                    'rushing_epa':       float(row[8]) if row[8] is not None else 0.0,
                    '_position_type':    'qb',
                }

            # ── RB ─────────────────────────────────────────────────────────────
            cur.execute(
                """
                SELECT player_name,
                    carries, rushing_epa, receiving_yards, receiving_tds,
                    rushing_first_downs, rushing_fumbles_lost, receiving_fumbles_lost
                FROM nflverse_rb_stats
                WHERE season = %s AND week = %s AND carries IS NOT NULL
                """,
                (season, week),
            )
            for row in cur.fetchall():
                name = _norm(row[0] or '')
                if not name:
                    continue
                result[name] = {
                    'carries':                row[1],
                    'rushing_epa':            float(row[2]) if row[2] is not None else 0.0,
                    'receiving_yards':        row[3],
                    'receiving_tds':          row[4],
                    'rushing_first_downs':    row[5],
                    'rushing_fumbles_lost':   row[6],
                    'receiving_fumbles_lost': row[7],
                    '_position_type':         'rb',
                }

            # ── WR / TE ────────────────────────────────────────────────────────
            cur.execute(
                """
                SELECT player_name,
                    targets, receiving_epa, receiving_yards, receiving_tds,
                    receiving_first_downs, wopr, target_share,
                    receiving_fumbles_lost, receptions
                FROM nflverse_wr_stats
                WHERE season = %s AND week = %s AND targets IS NOT NULL
                """,
                (season, week),
            )
            for row in cur.fetchall():
                name = _norm(row[0] or '')
                if not name:
                    continue
                result[name] = {
                    'targets':                row[1],
                    'receiving_epa':          float(row[2]) if row[2] is not None else 0.0,
                    'receiving_yards':        row[3],
                    'receiving_tds':          row[4],
                    'receiving_first_downs':  row[5],
                    'wopr':                   float(row[6]) if row[6] is not None else 0.0,
                    'target_share':           float(row[7]) if row[7] is not None else 0.0,
                    'receiving_fumbles_lost': row[8],
                    'receptions':             row[9],
                    '_position_type':         'wr',
                }

        finally:
            cur.close()
            conn.close()

        logger.info(
            "NflverseReader game: %d players season=%d week=%d",
            len(result), season, week,
        )
        return result

    # ── Rolling baselines (prior weeks in same season) ─────────────────────────

    def fetch_nflverse_baselines(self, season: int, week: int) -> Dict[str, Dict]:
        """
        Returns {norm_name: nv_base_dict} using SUM/AVG over all weeks < current
        in the same season.

        If week == 1 (no prior data), returns an empty dict — multiplier
        functions then fall back to league-average constants.

        Keys in nv_base_dict match exactly what the enhanced multiplier
        functions expect for their *nv_base* argument.
        """
        if week <= 1:
            logger.info("NflverseReader baselines: week=1, no prior data")
            return {}

        conn = self._connect()
        cur  = conn.cursor()
        result: Dict[str, Dict] = {}

        try:
            # ── QB baselines ───────────────────────────────────────────────────
            cur.execute(
                """
                SELECT player_name,
                    AVG(cpoe::float)            AS avg_cpoe,
                    SUM(passing_air_yards)      AS total_air_yards,
                    SUM(attempts)               AS total_attempts,
                    SUM(passing_epa::float)     AS total_passing_epa,
                    SUM(sacks_suffered)         AS total_sacks
                FROM nflverse_qb_stats
                WHERE season = %s AND week < %s AND attempts IS NOT NULL
                GROUP BY player_name
                """,
                (season, week),
            )
            for row in cur.fetchall():
                name = _norm(row[0] or '')
                if not name:
                    continue
                result[name] = {
                    'cpoe':              float(row[1]) if row[1] is not None else 0.0,
                    'passing_air_yards': int(row[2] or 0),
                    'attempts':          int(row[3] or 0),
                    'passing_epa':       float(row[4]) if row[4] is not None else 0.0,
                    'sacks':             int(row[5] or 0),
                    '_position_type':    'qb',
                }

            # ── RB baselines ───────────────────────────────────────────────────
            cur.execute(
                """
                SELECT player_name,
                    SUM(carries)                AS total_carries,
                    SUM(rushing_epa::float)     AS total_rushing_epa,
                    SUM(rushing_first_downs)    AS total_rushing_fds,
                    AVG(receiving_yards::float) AS avg_recv_yards,
                    SUM(rushing_fumbles_lost)   AS total_rush_fumb,
                    SUM(receiving_fumbles_lost) AS total_recv_fumb
                FROM nflverse_rb_stats
                WHERE season = %s AND week < %s AND carries IS NOT NULL
                GROUP BY player_name
                """,
                (season, week),
            )
            for row in cur.fetchall():
                name = _norm(row[0] or '')
                if not name:
                    continue
                result[name] = {
                    'carries':               int(row[1] or 0),
                    'rushing_epa':           float(row[2]) if row[2] is not None else 0.0,
                    'rushing_first_downs':   int(row[3] or 0),
                    'avg_receiving_yards':   float(row[4]) if row[4] is not None else 15.0,
                    'rushing_fumbles_lost':  int(row[5] or 0),
                    'receiving_fumbles_lost': int(row[6] or 0),
                    '_position_type':        'rb',
                }

            # ── WR/TE baselines ────────────────────────────────────────────────
            cur.execute(
                """
                SELECT player_name,
                    SUM(receiving_epa::float)   AS total_recv_epa,
                    SUM(targets)                AS total_targets,
                    SUM(receiving_yards)        AS total_recv_yards,
                    SUM(receiving_first_downs)  AS total_recv_fds,
                    AVG(wopr::float)            AS avg_wopr,
                    AVG(target_share::float)    AS avg_target_share,
                    SUM(receptions)             AS total_receptions,
                    SUM(receiving_fumbles_lost) AS total_fumb_lost
                FROM nflverse_wr_stats
                WHERE season = %s AND week < %s AND targets IS NOT NULL
                GROUP BY player_name
                """,
                (season, week),
            )
            for row in cur.fetchall():
                name = _norm(row[0] or '')
                if not name:
                    continue
                result[name] = {
                    'receiving_epa':          float(row[1]) if row[1] is not None else 0.0,
                    'targets':                int(row[2] or 0),
                    'receiving_yards':        int(row[3] or 0),
                    'receiving_first_downs':  int(row[4] or 0),
                    'wopr':                   float(row[5]) if row[5] is not None else 0.0,
                    'target_share':           float(row[6]) if row[6] is not None else 0.0,
                    'receptions':             int(row[7] or 0),
                    'receiving_fumbles_lost': int(row[8] or 0),
                    '_position_type':         'wr',
                }

        finally:
            cur.close()
            conn.close()

        logger.info(
            "NflverseReader baselines: %d players season=%d week<%d",
            len(result), season, week,
        )
        return result
