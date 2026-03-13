"""
TeamDataProcessor.py

Transforms one PFF team grades CSV row into three DB payloads
and upserts each into pff_team_offense / pff_team_defense / pff_team_special_teams.

CSV columns (all from PFF team export):
    team, season, record, pf, pa, overall, offense, passing,
    pass_block, receiving, run, run_block, defense, run_defense,
    tackling, pass_rush, coverage, special_teams
"""

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Upsert SQL — one per table
# ---------------------------------------------------------------------------

UPSERT_OFFENSE = """
INSERT INTO pff_team_offense
    (team, season, wins, losses, ties, points_for,
     overall_grade, offense_grade, passing_grade, pass_block_grade,
     receiving_grade, run_grade, run_block_grade)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON CONFLICT (team, season) DO UPDATE SET
    wins             = EXCLUDED.wins,
    losses           = EXCLUDED.losses,
    ties             = EXCLUDED.ties,
    points_for       = EXCLUDED.points_for,
    overall_grade    = EXCLUDED.overall_grade,
    offense_grade    = EXCLUDED.offense_grade,
    passing_grade    = EXCLUDED.passing_grade,
    pass_block_grade = EXCLUDED.pass_block_grade,
    receiving_grade  = EXCLUDED.receiving_grade,
    run_grade        = EXCLUDED.run_grade,
    run_block_grade  = EXCLUDED.run_block_grade
"""

UPSERT_DEFENSE = """
INSERT INTO pff_team_defense
    (team, season, points_against,
     defense_grade, run_defense_grade, tackling_grade,
     pass_rush_grade, coverage_grade)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
ON CONFLICT (team, season) DO UPDATE SET
    points_against    = EXCLUDED.points_against,
    defense_grade     = EXCLUDED.defense_grade,
    run_defense_grade = EXCLUDED.run_defense_grade,
    tackling_grade    = EXCLUDED.tackling_grade,
    pass_rush_grade   = EXCLUDED.pass_rush_grade,
    coverage_grade    = EXCLUDED.coverage_grade
"""

UPSERT_SPECIAL_TEAMS = """
INSERT INTO pff_team_special_teams
    (team, season, special_teams_grade)
VALUES (%s,%s,%s)
ON CONFLICT (team, season) DO UPDATE SET
    special_teams_grade = EXCLUDED.special_teams_grade
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _grade(value: Any) -> Decimal | None:
    """Cast a PFF grade string to Decimal. Returns None if blank/invalid."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        logger.warning(f"Could not parse grade value: {value!r}")
        return None


def _int(value: Any) -> int | None:
    """Cast to int. Returns None if blank/invalid."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(float(s))
    except (ValueError, TypeError):
        logger.warning(f"Could not parse int value: {value!r}")
        return None


def _parse_record(record_str: str) -> tuple[int, int, int]:
    """
    Parse PFF record string into (wins, losses, ties).
    Handles formats: "8 - 9", "15 - 2", "10 - 6 - 1"
    """
    if not record_str or not str(record_str).strip():
        return 0, 0, 0
    parts = [p.strip() for p in str(record_str).split('-')]
    wins   = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
    losses = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    ties   = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    return wins, losses, ties


def _normalize_team(team: str) -> str:
    """
    PFF uses some abbreviations that differ from games/team_rankings.
    Map them here so joins work downstream.
    """
    OVERRIDES = {
        "GNB": "GB",
        "KAN": "KC",
        "LVR": "LV",
        "NOR": "NO",
        "NWE": "NE",
        "SFO": "SF",
        "TAM": "TB",
        "OAK": "LV",   # historical Raiders
    }
    return OVERRIDES.get(team.strip().upper(), team.strip().upper())


# ---------------------------------------------------------------------------
# Main processor class
# ---------------------------------------------------------------------------

class TeamDataProcessor:
    """
    Reads PFF team grade rows and upserts into the three target tables.
    One instance is created per Lambda invocation and reused across seasons.
    """

    def __init__(self, db_utils, batch_size: int = 32):
        self.db = db_utils
        self.batch_size = batch_size

    # ------------------------------------------------------------------
    # Transform: one CSV dict → three DB tuples
    # ------------------------------------------------------------------

    def transform_row(self, row: dict, season: int) -> dict:
        """Return {'offense': tuple, 'defense': tuple, 'special_teams': tuple}."""
        team = _normalize_team(row.get("team", ""))
        if not team:
            return {}

        wins, losses, ties = _parse_record(row.get("record", ""))

        offense = (
            team, season,
            wins, losses, ties,
            _int(row.get("pf")),
            _grade(row.get("overall")),
            _grade(row.get("offense")),
            _grade(row.get("passing")),
            _grade(row.get("pass_block")),
            _grade(row.get("receiving")),
            _grade(row.get("run")),
            _grade(row.get("run_block")),
        )

        defense = (
            team, season,
            _int(row.get("pa")),
            _grade(row.get("defense")),
            _grade(row.get("run_defense")),
            _grade(row.get("tackling")),
            _grade(row.get("pass_rush")),
            _grade(row.get("coverage")),
        )

        special_teams = (
            team, season,
            _grade(row.get("special_teams")),
        )

        return {"offense": offense, "defense": defense, "special_teams": special_teams}

    def validate_row(self, transformed: dict) -> bool:
        if not transformed:
            return False
        # Require team (index 0) and season (index 1) on offense tuple
        o = transformed.get("offense", ())
        return bool(o and o[0] and o[1])

    # ------------------------------------------------------------------
    # Process + store
    # ------------------------------------------------------------------

    def process_and_store(self, csv_rows: list[dict], season: int) -> dict:
        """
        Transform all rows and upsert into the three tables.
        Returns a summary dict with row counts per table.
        """
        offense_batch, defense_batch, st_batch = [], [], []

        for raw in csv_rows:
            transformed = self.transform_row(raw, season)
            if not self.validate_row(transformed):
                logger.warning(f"Skipping invalid row: {raw}")
                continue
            offense_batch.append(transformed["offense"])
            defense_batch.append(transformed["defense"])
            st_batch.append(transformed["special_teams"])

        logger.info(f"Season {season}: {len(offense_batch)} valid rows to upsert")

        off_count = self._upsert_in_batches(UPSERT_OFFENSE, offense_batch)
        def_count = self._upsert_in_batches(UPSERT_DEFENSE, defense_batch)
        st_count  = self._upsert_in_batches(UPSERT_SPECIAL_TEAMS, st_batch)

        return {
            "season": season,
            "offense_rows": off_count,
            "defense_rows": def_count,
            "special_teams_rows": st_count,
        }

    def _upsert_in_batches(self, query: str, rows: list) -> int:
        total = 0
        for i in range(0, len(rows), self.batch_size):
            chunk = rows[i : i + self.batch_size]
            total += self.db.execute_batch(query, chunk)
        return total
