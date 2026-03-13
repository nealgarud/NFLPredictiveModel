"""
DatabaseUtils.py — PlayerSeasonStatsAggregator

Reads player_game_stats and upserts rolling season averages
into player_season_stats.
"""
import logging
import os
from typing import Optional

import pg8000

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Minimum games played before a player's row is considered a reliable baseline.
# Rows with fewer games still get written — the BoxScoreCollector decides whether
# to use them based on this same threshold.
MIN_GAMES_FOR_BASELINE = 3


class DatabaseUtils:
    def __init__(self):
        self.host     = (os.environ.get('SUPABASE_DB_HOST') or os.environ.get('DB_HOST', '')).strip()
        self.port     = int(os.environ.get('SUPABASE_DB_PORT') or os.environ.get('DB_PORT', 5432))
        self.database = (os.environ.get('SUPABASE_DB_NAME') or os.environ.get('DB_NAME', '')).strip()
        self.user     = (os.environ.get('SUPABASE_DB_USER') or os.environ.get('DB_USER', '')).strip()
        self.password = (os.environ.get('SUPABASE_DB_PASSWORD') or os.environ.get('DB_PASSWORD', '')).strip()

        if not all([self.host, self.database, self.user, self.password]):
            raise ValueError("Missing required database environment variables")

        self.connection: Optional[pg8000.Connection] = None

    def connect(self) -> pg8000.Connection:
        if self.connection is not None:
            return self.connection
        self.connection = pg8000.connect(
            host=self.host, port=self.port,
            database=self.database, user=self.user,
            password=self.password, ssl_context=True,
        )
        self.connection.autocommit = True
        logger.info(f"Connected to {self.database}")
        return self.connection

    def aggregate_player_season_stats(self, season: int, through_week: Optional[int] = None) -> int:
        """
        Aggregates player_game_stats for the given season (optionally capped at
        through_week) and upserts results into player_season_stats.

        Derived ratio columns (comp_pct, ypa, ypc, catch_rate, ypr) are computed
        at the season level using SUM(numerator)/SUM(denominator) rather than
        AVG(per-game ratio), which is statistically correct.

        Returns the number of player rows upserted.
        """
        conn   = self.connect()
        cursor = conn.cursor()

        if through_week is None:
            cursor.execute(
                "SELECT COALESCE(MAX(week), 0) FROM player_game_stats WHERE season = %s",
                (season,)
            )
            through_week = cursor.fetchone()[0]
            if through_week == 0:
                logger.warning(f"No data found in player_game_stats for season {season}")
                cursor.close()
                return 0

        logger.info(f"Aggregating season {season} through week {through_week}")

        sql = """
            INSERT INTO player_season_stats (
                player_id, player_name, team, position,
                season, through_week, games_played,
                avg_pass_attempts, avg_pass_completions, avg_pass_yards,
                avg_pass_touchdowns, avg_pass_interceptions,
                avg_comp_pct, avg_ypa, avg_sacks_taken,
                avg_rush_attempts, avg_rush_yards, avg_rush_ypc,
                avg_rush_yac, avg_rush_broken_tackles, avg_rush_tlost, avg_scrambles,
                avg_targets, avg_receptions, avg_receiving_yards, avg_receiving_tds,
                avg_catch_rate, avg_ypr, avg_yac, avg_drops,
                avg_tackles, avg_ast_tackles, avg_missed_tackles, avg_def_sacks,
                avg_qb_hits, avg_hurries, avg_passes_defended, avg_interceptions,
                avg_def_targets, avg_def_comp_allowed, avg_tackles_for_loss,
                updated_at
            )
            SELECT
                player_id,
                MAX(player_name),
                MAX(team),
                MAX(position),
                season,
                %s AS through_week,
                COUNT(*) AS games_played,

                -- Passing per-game averages
                AVG(pass_attempts),
                AVG(pass_completions),
                AVG(pass_yards),
                AVG(pass_touchdowns),
                AVG(pass_interceptions),
                -- Season-level ratios (more accurate than averaging per-game ratios)
                CASE WHEN SUM(pass_attempts) > 0
                     THEN ROUND(SUM(pass_completions)::NUMERIC / SUM(pass_attempts), 4)
                END,
                CASE WHEN SUM(pass_attempts) > 0
                     THEN ROUND(SUM(pass_yards)::NUMERIC / SUM(pass_attempts), 2)
                END,
                AVG(sacks_taken),

                -- Rushing
                AVG(rush_attempts),
                AVG(rush_yards),
                CASE WHEN SUM(rush_attempts) > 0
                     THEN ROUND(SUM(rush_yards)::NUMERIC / SUM(rush_attempts), 2)
                END,
                AVG(rush_yards_after_contact),
                AVG(rush_broken_tackles),
                AVG(rush_tlost),
                AVG(scrambles),

                -- Receiving
                AVG(targets),
                AVG(receptions),
                AVG(receiving_yards),
                AVG(receiving_touchdowns),
                CASE WHEN SUM(targets) > 0
                     THEN ROUND(SUM(receptions)::NUMERIC / SUM(targets), 4)
                END,
                CASE WHEN SUM(receptions) > 0
                     THEN ROUND(SUM(receiving_yards)::NUMERIC / SUM(receptions), 2)
                END,
                AVG(yards_after_catch),
                AVG(drops),

                -- Defense
                AVG(tackles),
                AVG(ast_tackles),
                AVG(missed_tackles),
                AVG(def_sacks),
                AVG(qb_hits),
                AVG(hurries),
                AVG(passes_defended),
                AVG(interceptions),
                AVG(def_targets),
                AVG(def_completions_allowed),
                AVG(tackles_for_loss),

                CURRENT_TIMESTAMP

            FROM player_game_stats
            WHERE season = %s
              AND week   <= %s
            GROUP BY player_id, season

            ON CONFLICT (player_id, season) DO UPDATE SET
                player_name             = EXCLUDED.player_name,
                team                    = EXCLUDED.team,
                position                = EXCLUDED.position,
                through_week            = EXCLUDED.through_week,
                games_played            = EXCLUDED.games_played,
                avg_pass_attempts       = EXCLUDED.avg_pass_attempts,
                avg_pass_completions    = EXCLUDED.avg_pass_completions,
                avg_pass_yards          = EXCLUDED.avg_pass_yards,
                avg_pass_touchdowns     = EXCLUDED.avg_pass_touchdowns,
                avg_pass_interceptions  = EXCLUDED.avg_pass_interceptions,
                avg_comp_pct            = EXCLUDED.avg_comp_pct,
                avg_ypa                 = EXCLUDED.avg_ypa,
                avg_sacks_taken         = EXCLUDED.avg_sacks_taken,
                avg_rush_attempts       = EXCLUDED.avg_rush_attempts,
                avg_rush_yards          = EXCLUDED.avg_rush_yards,
                avg_rush_ypc            = EXCLUDED.avg_rush_ypc,
                avg_rush_yac            = EXCLUDED.avg_rush_yac,
                avg_rush_broken_tackles = EXCLUDED.avg_rush_broken_tackles,
                avg_rush_tlost          = EXCLUDED.avg_rush_tlost,
                avg_scrambles           = EXCLUDED.avg_scrambles,
                avg_targets             = EXCLUDED.avg_targets,
                avg_receptions          = EXCLUDED.avg_receptions,
                avg_receiving_yards     = EXCLUDED.avg_receiving_yards,
                avg_receiving_tds       = EXCLUDED.avg_receiving_tds,
                avg_catch_rate          = EXCLUDED.avg_catch_rate,
                avg_ypr                 = EXCLUDED.avg_ypr,
                avg_yac                 = EXCLUDED.avg_yac,
                avg_drops               = EXCLUDED.avg_drops,
                avg_tackles             = EXCLUDED.avg_tackles,
                avg_ast_tackles         = EXCLUDED.avg_ast_tackles,
                avg_missed_tackles      = EXCLUDED.avg_missed_tackles,
                avg_def_sacks           = EXCLUDED.avg_def_sacks,
                avg_qb_hits             = EXCLUDED.avg_qb_hits,
                avg_hurries             = EXCLUDED.avg_hurries,
                avg_passes_defended     = EXCLUDED.avg_passes_defended,
                avg_interceptions       = EXCLUDED.avg_interceptions,
                avg_def_targets         = EXCLUDED.avg_def_targets,
                avg_def_comp_allowed    = EXCLUDED.avg_def_comp_allowed,
                avg_tackles_for_loss    = EXCLUDED.avg_tackles_for_loss,
                updated_at              = CURRENT_TIMESTAMP
        """

        try:
            cursor.execute(sql, (through_week, season, through_week))
            count = cursor.rowcount
            logger.info(f"Upserted {count} player rows for season {season} through week {through_week}")
            return count
        finally:
            cursor.close()

    def close(self):
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None
