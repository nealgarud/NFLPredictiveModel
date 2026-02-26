"""
DatabaseUtils.py
Handles PostgreSQL connections, table creation, and upserts for team_season_features.
"""

import os
import logging
import pg8000
from typing import Optional, List, Dict, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS team_season_features (
    team_id TEXT NOT NULL,
    season INT NOT NULL,
    games_played INT DEFAULT 0,
    home_wins INT DEFAULT 0,
    home_games INT DEFAULT 0,
    home_win_rate DECIMAL,
    away_wins INT DEFAULT 0,
    away_games INT DEFAULT 0,
    away_win_rate DECIMAL,
    home_advantage DECIMAL,
    div_wins INT DEFAULT 0,
    div_games INT DEFAULT 0,
    div_win_rate DECIMAL,
    non_div_wins INT DEFAULT 0,
    non_div_games INT DEFAULT 0,
    non_div_win_rate DECIMAL,
    div_advantage DECIMAL,
    prime_time_wins INT DEFAULT 0,
    prime_time_games INT DEFAULT 0,
    prime_time_win_rate DECIMAL,
    vs_strong_wins INT DEFAULT 0,
    vs_strong_games INT DEFAULT 0,
    vs_strong_win_rate DECIMAL,
    vs_mid_wins INT DEFAULT 0,
    vs_mid_games INT DEFAULT 0,
    vs_mid_win_rate DECIMAL,
    vs_weak_wins INT DEFAULT 0,
    vs_weak_games INT DEFAULT 0,
    vs_weak_win_rate DECIMAL,
    close_game_ats_covers INT DEFAULT 0,
    close_game_ats_total INT DEFAULT 0,
    close_game_ats_rate DECIMAL,
    after_loss_ats_covers INT DEFAULT 0,
    after_loss_ats_total INT DEFAULT 0,
    after_loss_ats_rate DECIMAL,
    after_bye_ats_covers INT DEFAULT 0,
    after_bye_ats_total INT DEFAULT 0,
    after_bye_ats_rate DECIMAL,
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (team_id, season)
);
"""

UPSERT_SQL = """
INSERT INTO team_season_features (
    team_id, season, games_played,
    home_wins, home_games, home_win_rate,
    away_wins, away_games, away_win_rate, home_advantage,
    div_wins, div_games, div_win_rate,
    non_div_wins, non_div_games, non_div_win_rate, div_advantage,
    prime_time_wins, prime_time_games, prime_time_win_rate,
    vs_strong_wins, vs_strong_games, vs_strong_win_rate,
    vs_mid_wins, vs_mid_games, vs_mid_win_rate,
    vs_weak_wins, vs_weak_games, vs_weak_win_rate,
    close_game_ats_covers, close_game_ats_total, close_game_ats_rate,
    after_loss_ats_covers, after_loss_ats_total, after_loss_ats_rate,
    after_bye_ats_covers, after_bye_ats_total, after_bye_ats_rate,
    updated_at
) VALUES (
    :team_id, :season, :games_played,
    :home_wins, :home_games, :home_win_rate,
    :away_wins, :away_games, :away_win_rate, :home_advantage,
    :div_wins, :div_games, :div_win_rate,
    :non_div_wins, :non_div_games, :non_div_win_rate, :div_advantage,
    :prime_time_wins, :prime_time_games, :prime_time_win_rate,
    :vs_strong_wins, :vs_strong_games, :vs_strong_win_rate,
    :vs_mid_wins, :vs_mid_games, :vs_mid_win_rate,
    :vs_weak_wins, :vs_weak_games, :vs_weak_win_rate,
    :close_game_ats_covers, :close_game_ats_total, :close_game_ats_rate,
    :after_loss_ats_covers, :after_loss_ats_total, :after_loss_ats_rate,
    :after_bye_ats_covers, :after_bye_ats_total, :after_bye_ats_rate,
    NOW()
)
ON CONFLICT (team_id, season) DO UPDATE SET
    games_played = EXCLUDED.games_played,
    home_wins = EXCLUDED.home_wins,
    home_games = EXCLUDED.home_games,
    home_win_rate = EXCLUDED.home_win_rate,
    away_wins = EXCLUDED.away_wins,
    away_games = EXCLUDED.away_games,
    away_win_rate = EXCLUDED.away_win_rate,
    home_advantage = EXCLUDED.home_advantage,
    div_wins = EXCLUDED.div_wins,
    div_games = EXCLUDED.div_games,
    div_win_rate = EXCLUDED.div_win_rate,
    non_div_wins = EXCLUDED.non_div_wins,
    non_div_games = EXCLUDED.non_div_games,
    non_div_win_rate = EXCLUDED.non_div_win_rate,
    div_advantage = EXCLUDED.div_advantage,
    prime_time_wins = EXCLUDED.prime_time_wins,
    prime_time_games = EXCLUDED.prime_time_games,
    prime_time_win_rate = EXCLUDED.prime_time_win_rate,
    vs_strong_wins = EXCLUDED.vs_strong_wins,
    vs_strong_games = EXCLUDED.vs_strong_games,
    vs_strong_win_rate = EXCLUDED.vs_strong_win_rate,
    vs_mid_wins = EXCLUDED.vs_mid_wins,
    vs_mid_games = EXCLUDED.vs_mid_games,
    vs_mid_win_rate = EXCLUDED.vs_mid_win_rate,
    vs_weak_wins = EXCLUDED.vs_weak_wins,
    vs_weak_games = EXCLUDED.vs_weak_games,
    vs_weak_win_rate = EXCLUDED.vs_weak_win_rate,
    close_game_ats_covers = EXCLUDED.close_game_ats_covers,
    close_game_ats_total = EXCLUDED.close_game_ats_total,
    close_game_ats_rate = EXCLUDED.close_game_ats_rate,
    after_loss_ats_covers = EXCLUDED.after_loss_ats_covers,
    after_loss_ats_total = EXCLUDED.after_loss_ats_total,
    after_loss_ats_rate = EXCLUDED.after_loss_ats_rate,
    after_bye_ats_covers = EXCLUDED.after_bye_ats_covers,
    after_bye_ats_total = EXCLUDED.after_bye_ats_total,
    after_bye_ats_rate = EXCLUDED.after_bye_ats_rate,
    updated_at = NOW();
"""


class DatabaseUtils:
    """PostgreSQL connection and storage for team_season_features."""

    def __init__(self):
        self.host = (os.environ.get('SUPABASE_DB_HOST') or os.environ.get('DB_HOST', '')).strip()
        self.port = int(os.environ.get('SUPABASE_DB_PORT') or os.environ.get('DB_PORT', 5432))
        self.database = (os.environ.get('SUPABASE_DB_NAME') or os.environ.get('DB_NAME', '')).strip()
        self.user = (os.environ.get('SUPABASE_DB_USER') or os.environ.get('DB_USER', '')).strip()
        self.password = (os.environ.get('SUPABASE_DB_PASSWORD') or os.environ.get('DB_PASSWORD', '')).strip()

        if not all([self.host, self.database, self.user, self.password]):
            raise ValueError(
                "Missing DB env vars. Need SUPABASE_DB_HOST/NAME/USER/PASSWORD or DB_HOST/NAME/USER/PASSWORD"
            )

        self.connection: Optional[pg8000.Connection] = None
        logger.info("DatabaseUtils initialized")

    def connect(self) -> pg8000.Connection:
        if self.connection is None:
            self.connection = pg8000.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                ssl_context=True
            )
            self.connection.autocommit = True
            # Clear any stale transaction state
            try:
                self.connection.run("ROLLBACK")
            except Exception:
                pass
            logger.info(f"Connected to {self.database} (autocommit=True)")
        return self.connection

    def ensure_table(self):
        """Create team_season_features table if it doesn't exist."""
        conn = self.connect()
        try:
            conn.run(CREATE_TABLE_SQL)
            conn.run("COMMIT")
        except Exception as e:
            logger.warning(f"ensure_table hit error (may already exist): {e}")
            try:
                conn.run("ROLLBACK")
            except Exception:
                pass
        logger.info("team_season_features table ready")

    def fetch_games(self, seasons: List[int]):
        """Fetch all completed regular-season games for the given seasons."""
        conn = self.connect()
        query = """
        SELECT
            game_id, season, week, gameday,
            home_team, away_team, home_score, away_score,
            spread_line, div_game
        FROM games
        WHERE season = ANY(:seasons)
            AND game_type = 'REG'
            AND home_score IS NOT NULL
            AND away_score IS NOT NULL
        ORDER BY season, week, gameday
        """
        try:
            rows = conn.run(query, seasons=seasons)
            conn.run("COMMIT")
            logger.info(f"Fetched {len(rows)} games for seasons {seasons}")
            return rows
        except Exception as e:
            logger.error(f"fetch_games failed: {e}")
            try:
                conn.run("ROLLBACK")
            except Exception:
                self.connection = None
                self.connect()
            raise

    def upsert_team_season(self, features: Dict[str, Any]):
        """Upsert a single team-season row with per-statement commit."""
        conn = self.connect()
        try:
            conn.run(UPSERT_SQL, **features)
            conn.run("COMMIT")
        except Exception as e:
            logger.error(f"Upsert failed for {features.get('team_id')} S{features.get('season')}: {e}")
            try:
                conn.run("ROLLBACK")
            except Exception:
                self.connection = None
                self.connect()
            raise

    def commit(self):
        pass  # autocommit handles this

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("Connection closed")
