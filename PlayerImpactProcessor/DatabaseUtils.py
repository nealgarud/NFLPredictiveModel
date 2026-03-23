"""
DatabaseUtils.py — PlayerImpactProcessor
=========================================
Handles all DB operations for the PlayerImpactProcessor pipeline:
  - Fetch games to process (same as BoxScoreCollector)
  - PFF grade lookup (same as BoxScoreCollector)
  - Upsert player_game_stats with enriched multiplier_components + nflverse_enriched
  - Update game_id_mapping with position-group impacts + player_details JSONB
  - Player-season-stats baseline lookup (same as BoxScoreCollector)
"""
import json
import logging
import os
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pg8000

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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
        logger.info("Connected to %s", self.database)
        return self.connection

    def _reset_connection(self):
        try:
            if self.connection:
                self.connection.close()
        except Exception:
            pass
        self.connection = None

    # ── Game fetching ─────────────────────────────────────────────────────────

    def fetch_games_to_process(
        self,
        season: Optional[int] = None,
        week: Optional[int] = None,
        limit: Optional[int] = None,
        force: bool = False,
    ) -> List[Dict[str, Any]]:
        conn   = self.connect()
        cursor = conn.cursor()
        try:
            where  = ["sportradar_id IS NOT NULL", "sportradar_id != game_id", "week <= 18"]
            if not force:
                where.append("player_impact_collected_at IS NULL")
            params: List[Any] = []

            if season is not None:
                where.append("season = %s")
                params.append(season)
            if week is not None:
                where.append("week = %s")
                params.append(week)

            sql = (
                "SELECT game_id, sportradar_id, season, week, home_team, away_team "
                "FROM game_id_mapping "
                f"WHERE {' AND '.join(where)} "
                "ORDER BY season DESC, week DESC, game_id"
            )
            if limit:
                sql += f" LIMIT {limit}"

            cursor.execute(sql, tuple(params))
            rows  = cursor.fetchall()
            games = [
                {'game_id': r[0], 'sportradar_id': r[1], 'season': r[2],
                 'week': r[3], 'home_team': r[4], 'away_team': r[5]}
                for r in rows
            ]
            logger.info("Fetched %d games to process", len(games))
            return games
        finally:
            cursor.close()

    # ── PFF grade lookup ──────────────────────────────────────────────────────

    def fetch_pff_grades_bulk(self, player_names: List[str], season: int) -> Dict[str, float]:
        if not player_names:
            return {}

        conn     = self.connect()
        cursor   = conn.cursor()
        name_set = set(player_names)

        try:
            sql = """
                SELECT player, grades_offense FROM qb_pff_ratings    WHERE season = %s
                UNION ALL
                SELECT player, grades_offense FROM rb_pff_ratings    WHERE season = %s
                UNION ALL
                SELECT player, grades_offense FROM wr_pff_ratings    WHERE season = %s
                UNION ALL
                SELECT player, grades_offense FROM oline_pff_ratings WHERE season = %s
                UNION ALL
                SELECT player, grades_defense FROM defense_pff_ratings WHERE season = %s
            """
            cursor.execute(sql, (season, season, season, season, season))

            result: Dict[str, float] = {}
            for row in cursor.fetchall():
                name, grade = row[0], row[1]
                if name in name_set and name not in result and grade is not None:
                    result[name] = float(grade)

            logger.info(
                "PFF grade lookup: %d/%d players matched for season %d",
                len(result), len(name_set), season,
            )
            return result
        except Exception as e:
            logger.warning("PFF grade bulk lookup failed: %s", e)
            return {}
        finally:
            cursor.close()
            self._reset_connection()

    # ── player_game_stats (enriched) ──────────────────────────────────────────

    def upsert_player_stats_enriched(self, players: List[Dict[str, Any]]) -> int:
        """
        UPSERT player rows including new multiplier_components (JSONB) and
        nflverse_enriched (BOOLEAN) columns added by migrate_game_id_mapping.sql.
        Returns number of rows upserted.
        """
        if not players:
            return 0

        conn   = self.connect()
        cursor = conn.cursor()
        count  = 0

        sql = """
            INSERT INTO player_game_stats (
                game_id, sportradar_game_id, player_id, player_name,
                team, position, season, week,
                rush_attempts, rush_yards, rush_touchdowns, rush_first_downs,
                rush_yards_after_contact, rush_broken_tackles, rush_tlost, scrambles,
                pass_attempts, pass_completions, pass_yards, pass_touchdowns,
                pass_interceptions, pass_air_yards, pass_on_target, pass_poorly_thrown,
                sacks_taken, sack_yards, avg_pocket_time, times_blitzed, times_hurried,
                targets, receptions, receiving_yards, receiving_touchdowns,
                yards_after_catch, drops,
                tackles, ast_tackles, missed_tackles, def_sacks, def_sack_yards,
                qb_hits, hurries, knockdowns, passes_defended,
                interceptions, int_yards, int_touchdowns,
                def_targets, def_completions_allowed, tackles_for_loss,
                fg_attempts, fg_made, fg_longest, xp_attempts, xp_made,
                kick_return_yards, punt_return_yards,
                team_points_scored, team_points_allowed, game_result,
                actual_impact_score, pff_grade, performance_multiplier,
                multiplier_components, nflverse_enriched
            ) VALUES (
                %s,%s,%s,%s, %s,%s,%s,%s,
                %s,%s,%s,%s, %s,%s,%s,%s,
                %s,%s,%s,%s, %s,%s,%s,%s,
                %s,%s,%s,%s,%s,
                %s,%s,%s,%s, %s,%s,
                %s,%s,%s,%s,%s,
                %s,%s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,%s,%s,
                %s,%s,
                %s,%s,%s,
                %s,%s,%s,
                %s,%s
            )
            ON CONFLICT (game_id, player_id) DO UPDATE SET
                player_name              = EXCLUDED.player_name,
                position                 = EXCLUDED.position,
                rush_attempts            = EXCLUDED.rush_attempts,
                rush_yards               = EXCLUDED.rush_yards,
                rush_touchdowns          = EXCLUDED.rush_touchdowns,
                rush_first_downs         = EXCLUDED.rush_first_downs,
                rush_yards_after_contact = EXCLUDED.rush_yards_after_contact,
                rush_broken_tackles      = EXCLUDED.rush_broken_tackles,
                rush_tlost               = EXCLUDED.rush_tlost,
                scrambles                = EXCLUDED.scrambles,
                pass_attempts            = EXCLUDED.pass_attempts,
                pass_completions         = EXCLUDED.pass_completions,
                pass_yards               = EXCLUDED.pass_yards,
                pass_touchdowns          = EXCLUDED.pass_touchdowns,
                pass_interceptions       = EXCLUDED.pass_interceptions,
                pass_air_yards           = EXCLUDED.pass_air_yards,
                pass_on_target           = EXCLUDED.pass_on_target,
                sacks_taken              = EXCLUDED.sacks_taken,
                sack_yards               = EXCLUDED.sack_yards,
                avg_pocket_time          = EXCLUDED.avg_pocket_time,
                times_blitzed            = EXCLUDED.times_blitzed,
                times_hurried            = EXCLUDED.times_hurried,
                targets                  = EXCLUDED.targets,
                receptions               = EXCLUDED.receptions,
                receiving_yards          = EXCLUDED.receiving_yards,
                receiving_touchdowns     = EXCLUDED.receiving_touchdowns,
                yards_after_catch        = EXCLUDED.yards_after_catch,
                drops                    = EXCLUDED.drops,
                tackles                  = EXCLUDED.tackles,
                ast_tackles              = EXCLUDED.ast_tackles,
                missed_tackles           = EXCLUDED.missed_tackles,
                def_sacks                = EXCLUDED.def_sacks,
                def_sack_yards           = EXCLUDED.def_sack_yards,
                qb_hits                  = EXCLUDED.qb_hits,
                hurries                  = EXCLUDED.hurries,
                knockdowns               = EXCLUDED.knockdowns,
                passes_defended          = EXCLUDED.passes_defended,
                interceptions            = EXCLUDED.interceptions,
                int_yards                = EXCLUDED.int_yards,
                int_touchdowns           = EXCLUDED.int_touchdowns,
                def_targets              = EXCLUDED.def_targets,
                def_completions_allowed  = EXCLUDED.def_completions_allowed,
                tackles_for_loss         = EXCLUDED.tackles_for_loss,
                fg_attempts              = EXCLUDED.fg_attempts,
                fg_made                  = EXCLUDED.fg_made,
                fg_longest               = EXCLUDED.fg_longest,
                xp_attempts              = EXCLUDED.xp_attempts,
                xp_made                  = EXCLUDED.xp_made,
                kick_return_yards        = EXCLUDED.kick_return_yards,
                punt_return_yards        = EXCLUDED.punt_return_yards,
                team_points_scored       = EXCLUDED.team_points_scored,
                team_points_allowed      = EXCLUDED.team_points_allowed,
                game_result              = EXCLUDED.game_result,
                actual_impact_score      = EXCLUDED.actual_impact_score,
                pff_grade                = EXCLUDED.pff_grade,
                performance_multiplier   = EXCLUDED.performance_multiplier,
                multiplier_components    = EXCLUDED.multiplier_components,
                nflverse_enriched        = EXCLUDED.nflverse_enriched,
                updated_at               = CURRENT_TIMESTAMP
        """

        try:
            for p in players:
                mc_json = json.dumps(p.get('multiplier_components') or {})
                cursor.execute(sql, (
                    p['game_id'], p.get('sportradar_game_id'), p['player_id'], p.get('player_name'),
                    p['team'], p.get('position'), p['season'], p['week'],
                    p['rush_attempts'], p['rush_yards'], p['rush_touchdowns'], p['rush_first_downs'],
                    p['rush_yards_after_contact'], p['rush_broken_tackles'], p['rush_tlost'], p['scrambles'],
                    p['pass_attempts'], p['pass_completions'], p['pass_yards'], p['pass_touchdowns'],
                    p['pass_interceptions'], p['pass_air_yards'], p['pass_on_target'], p['pass_poorly_thrown'],
                    p['sacks_taken'], p['sack_yards'], p.get('avg_pocket_time'), p['times_blitzed'], p['times_hurried'],
                    p['targets'], p['receptions'], p['receiving_yards'], p['receiving_touchdowns'],
                    p['yards_after_catch'], p['drops'],
                    p['tackles'], p['ast_tackles'], p['missed_tackles'], p['def_sacks'], p['def_sack_yards'],
                    p['qb_hits'], p['hurries'], p['knockdowns'], p['passes_defended'],
                    p['interceptions'], p['int_yards'], p['int_touchdowns'],
                    p['def_targets'], p['def_completions_allowed'], p['tackles_for_loss'],
                    p['fg_attempts'], p['fg_made'], p['fg_longest'], p['xp_attempts'], p['xp_made'],
                    p['kick_return_yards'], p['punt_return_yards'],
                    p.get('team_points_scored'), p.get('team_points_allowed'), p.get('game_result'),
                    p.get('actual_impact_score'),
                    p.get('pff_grade'),
                    p.get('performance_multiplier'),
                    mc_json,
                    bool(p.get('nflverse_enriched', False)),
                ))
                count += 1

            logger.info("Upserted %d enriched player rows for %s", count, players[0]['game_id'])
            return count
        finally:
            cursor.close()

    # ── game_id_mapping — enriched impact write ───────────────────────────────

    def update_game_with_enriched_impact(
        self,
        game_id: str,
        home_actual: float,
        away_actual: float,
        home_surprise: float,
        away_surprise: float,
        home_groups: Dict[str, float],
        away_groups: Dict[str, float],
        home_details: List[Dict],
        away_details: List[Dict],
    ) -> bool:
        """
        Writes all impact columns to game_id_mapping including:
          - home/away actual + expected impact
          - home/away performance_surprise
          - position-group impacts (offense, defense, OL)
          - home/away player_details as enriched JSONB
          - player_impact_collected_at timestamp
        """
        conn   = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE game_id_mapping SET
                    home_actual_game_impact   = %s,
                    away_actual_game_impact   = %s,
                    home_performance_surprise = %s,
                    away_performance_surprise = %s,
                    performance_surprise_diff = %s,
                    home_offense_impact       = %s,
                    home_defense_impact       = %s,
                    home_ol_impact            = %s,
                    away_offense_impact       = %s,
                    away_defense_impact       = %s,
                    away_ol_impact            = %s,
                    home_player_details       = %s,
                    away_player_details       = %s,
                    impact_processor_version  = %s,
                    player_impact_collected_at = CURRENT_TIMESTAMP
                WHERE game_id = %s
                """,
                (
                    home_actual, away_actual,
                    home_surprise, away_surprise,
                    round(home_surprise - away_surprise, 4),
                    home_groups.get('offense_impact'),
                    home_groups.get('defense_impact'),
                    home_groups.get('ol_impact'),
                    away_groups.get('offense_impact'),
                    away_groups.get('defense_impact'),
                    away_groups.get('ol_impact'),
                    json.dumps(home_details, default=str),
                    json.dumps(away_details, default=str),
                    'PlayerImpactProcessor-v1',
                    game_id,
                ),
            )
            return cursor.rowcount > 0
        finally:
            cursor.close()

    def update_game_script(
        self,
        game_id: str,
        quarter_scores: Dict[str, Any],
        weather: Optional[Dict[str, Any]] = None,
    ) -> bool:
        conn   = self.connect()
        cursor = conn.cursor()
        w = weather or {}
        try:
            cursor.execute(
                """
                UPDATE game_id_mapping SET
                    home_q1_points      = %s, away_q1_points      = %s,
                    home_q2_points      = %s, away_q2_points      = %s,
                    home_q3_points      = %s, away_q3_points      = %s,
                    home_q4_points      = %s, away_q4_points      = %s,
                    home_led_at_half    = %s, halftime_margin     = %s,
                    weather_temp        = %s, weather_wind_speed  = %s,
                    weather_condition   = %s, is_dome             = %s
                WHERE game_id = %s
                """,
                (
                    quarter_scores.get('home_q1'), quarter_scores.get('away_q1'),
                    quarter_scores.get('home_q2'), quarter_scores.get('away_q2'),
                    quarter_scores.get('home_q3'), quarter_scores.get('away_q3'),
                    quarter_scores.get('home_q4'), quarter_scores.get('away_q4'),
                    quarter_scores.get('home_led_at_half'), quarter_scores.get('halftime_margin'),
                    w.get('weather_temp'), w.get('weather_wind_speed'),
                    w.get('weather_condition'), w.get('is_dome'),
                    game_id,
                ),
            )
            return cursor.rowcount > 0
        finally:
            cursor.close()

    # ── player_season_stats lookup ────────────────────────────────────────────

    def fetch_player_season_stats(self, player_ids: List[str], season: int) -> Dict[str, Dict]:
        if not player_ids:
            return {}

        MIN_GAMES_THRESHOLD = 3

        conn   = self.connect()
        cursor = conn.cursor()
        id_set = set(player_ids)

        columns = [
            'player_id', 'season', 'games_played',
            'avg_pass_attempts', 'avg_pass_completions', 'avg_pass_yards',
            'avg_pass_touchdowns', 'avg_pass_interceptions',
            'avg_comp_pct', 'avg_ypa', 'avg_sacks_taken',
            'avg_rush_attempts', 'avg_rush_yards', 'avg_rush_ypc',
            'avg_rush_yac', 'avg_rush_broken_tackles', 'avg_rush_tlost', 'avg_scrambles',
            'avg_targets', 'avg_receptions', 'avg_receiving_yards', 'avg_receiving_tds',
            'avg_catch_rate', 'avg_ypr', 'avg_yac', 'avg_drops',
            'avg_tackles', 'avg_ast_tackles', 'avg_missed_tackles', 'avg_def_sacks',
            'avg_qb_hits', 'avg_hurries', 'avg_passes_defended', 'avg_interceptions',
            'avg_def_targets', 'avg_def_comp_allowed', 'avg_tackles_for_loss',
        ]

        try:
            cursor.execute(
                f"SELECT {', '.join(columns)} FROM player_season_stats "
                "WHERE season IN (%s, %s)",
                (season, season - 1),
            )
            rows = cursor.fetchall()

            current_stats: Dict[str, Dict] = {}
            prior_stats:   Dict[str, Dict] = {}

            for row in rows:
                pid   = row[0]
                s     = int(row[1])
                games = int(row[2])

                if pid not in id_set:
                    continue

                d: Dict[str, Any] = {
                    'player_id':    pid,
                    'season':       s,
                    'games_played': games,
                }
                for col, val in zip(columns[3:], row[3:]):
                    d[col] = float(val) if val is not None else None

                if s == season:
                    current_stats[pid] = d
                else:
                    prior_stats[pid] = d

            result: Dict[str, Dict] = {}
            for pid in id_set:
                if pid in current_stats and current_stats[pid]['games_played'] >= MIN_GAMES_THRESHOLD:
                    result[pid] = current_stats[pid]
                elif pid in prior_stats:
                    result[pid] = prior_stats[pid]

            current_count = sum(1 for d in result.values() if d['season'] == season)
            prior_count   = sum(1 for d in result.values() if d['season'] == season - 1)
            logger.info(
                "Player baselines: %d/%d matched (%d current, %d prior, %d neutral)",
                len(result), len(id_set), current_count, prior_count,
                len(id_set) - len(result),
            )
            return result

        except Exception as e:
            logger.warning("fetch_player_season_stats failed: %s", e)
            return {}
        finally:
            cursor.close()

    # ── OL starters + team season averages ───────────────────────────────────

    # game_id_mapping uses JAC/LA; oline_pff_ratings uses JAX/LAR
    _GIM_TO_PFF = {'JAC': 'JAX', 'LA': 'LAR'}

    def get_ol_starters(
        self, team: str, season: int, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Return top-`limit` OL starters for `team` in `season` from oline_pff_ratings,
        ordered by snap_counts_offense DESC.  Filters to position IN ('T','G','C').
        Returns [] if no data found.
        """
        pff_team = self._GIM_TO_PFF.get(team, team)
        conn   = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT player, player_id, position, team_name, season,
                       grades_offense, grades_pass_block, grades_run_block,
                       snap_counts_offense, player_game_count,
                       sacks_allowed, hurries_allowed, pressures_allowed, penalties
                FROM oline_pff_ratings
                WHERE team_name = %s
                  AND season    = %s
                  AND position IN ('T', 'G', 'C')
                ORDER BY snap_counts_offense DESC
                LIMIT %s
                """,
                [pff_team, season, limit],
            )
            cols = [d[0] for d in cursor.description]
            rows = cursor.fetchall()
            result = [dict(zip(cols, r)) for r in rows]
            logger.info(
                "OL starters %s %d: %d found (queried as %s)",
                team, season, len(result), pff_team,
            )
            return result
        except Exception as e:
            logger.warning("get_ol_starters failed for %s %d: %s", team, season, e)
            return []
        finally:
            cursor.close()

    def get_team_season_averages(
        self, team: str, season: int, before_week: Optional[int] = None
    ) -> Dict[str, float]:
        """
        Compute team's season-to-date averages for the OL proxy baseline:
          - avg_sack_rate          (total sacks / (atts + sacks) across all QB games)
          - avg_ypc                (total rush_yards / total carries across all RB games)
          - avg_rush_epa_per_carry (total rushing_epa / total carries from RB games)

        Queries nflverse_qb_stats and nflverse_rb_stats.
        If before_week is set, only games with week < before_week are included
        (prevents data leakage for in-season processing).
        Falls back to league-average constants when no data found.
        """
        FALLBACK: Dict[str, float] = {
            'avg_sack_rate':          0.065,
            'avg_ypc':                4.3,
            'avg_rush_epa_per_carry': 0.0,
        }

        conn   = self.connect()
        cursor = conn.cursor()

        week_sql   = "AND week < %s" if (before_week and before_week > 1) else ""
        week_param = [before_week] if (before_week and before_week > 1) else []

        try:
            # QB sack rate
            cursor.execute(
                f"""
                SELECT COALESCE(SUM(attempts),         0),
                       COALESCE(SUM(sacks_suffered),   0)
                FROM nflverse_qb_stats
                WHERE team = %s AND season = %s {week_sql}
                """,
                [team, season] + week_param,
            )
            qb_row  = cursor.fetchone()
            total_atts   = float(qb_row[0])
            total_sacks  = float(qb_row[1])
            sack_rate    = (
                total_sacks / (total_atts + total_sacks)
                if (total_atts + total_sacks) > 0
                else FALLBACK['avg_sack_rate']
            )

            # RB rushing stats
            cursor.execute(
                f"""
                SELECT COALESCE(SUM(carries),       0),
                       COALESCE(SUM(rushing_yards), 0),
                       COALESCE(SUM(rushing_epa),   0)
                FROM nflverse_rb_stats
                WHERE team = %s AND season = %s {week_sql}
                """,
                [team, season] + week_param,
            )
            rb_row       = cursor.fetchone()
            total_carries    = float(rb_row[0])
            total_rush_yds   = float(rb_row[1])
            total_rush_epa   = float(rb_row[2])
            ypc              = (
                total_rush_yds / total_carries
                if total_carries > 0
                else FALLBACK['avg_ypc']
            )
            rush_epa_pc      = (
                total_rush_epa / total_carries
                if total_carries > 0
                else FALLBACK['avg_rush_epa_per_carry']
            )

            return {
                'avg_sack_rate':          round(sack_rate,   6),
                'avg_ypc':                round(ypc,         4),
                'avg_rush_epa_per_carry': round(rush_epa_pc, 6),
            }

        except Exception as e:
            logger.warning(
                "get_team_season_averages failed for %s %d: %s — using fallback",
                team, season, e,
            )
            return FALLBACK
        finally:
            cursor.close()

    # ── Backfill: read existing player rows from DB ───────────────────────────

    def fetch_players_from_game(self, game_id: str) -> List[Dict[str, Any]]:
        """
        Read all player rows for a game from player_game_stats.
        Returns list of dicts with the same field names expected by
        calc_team_impacts / position-multiplier functions.
        Used in backfill mode so no Sportradar API call is needed.
        """
        conn   = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    game_id, sportradar_game_id, player_id, player_name,
                    team, position, season, week,
                    COALESCE(rush_attempts,            0)    AS rush_attempts,
                    COALESCE(rush_yards,               0)    AS rush_yards,
                    COALESCE(rush_touchdowns,          0)    AS rush_touchdowns,
                    COALESCE(rush_first_downs,         0)    AS rush_first_downs,
                    COALESCE(rush_yards_after_contact, 0)    AS rush_yards_after_contact,
                    COALESCE(rush_broken_tackles,      0)    AS rush_broken_tackles,
                    COALESCE(rush_tlost,               0)    AS rush_tlost,
                    COALESCE(scrambles,                0)    AS scrambles,
                    COALESCE(pass_attempts,            0)    AS pass_attempts,
                    COALESCE(pass_completions,         0)    AS pass_completions,
                    COALESCE(pass_yards,               0)    AS pass_yards,
                    COALESCE(pass_touchdowns,          0)    AS pass_touchdowns,
                    COALESCE(pass_interceptions,       0)    AS pass_interceptions,
                    COALESCE(pass_air_yards,           0)    AS pass_air_yards,
                    COALESCE(pass_on_target,           0)    AS pass_on_target,
                    COALESCE(pass_poorly_thrown,       0)    AS pass_poorly_thrown,
                    COALESCE(sacks_taken,              0)    AS sacks_taken,
                    COALESCE(sack_yards,               0)    AS sack_yards,
                    avg_pocket_time,
                    COALESCE(times_blitzed,            0)    AS times_blitzed,
                    COALESCE(times_hurried,            0)    AS times_hurried,
                    COALESCE(targets,                  0)    AS targets,
                    COALESCE(receptions,               0)    AS receptions,
                    COALESCE(receiving_yards,          0)    AS receiving_yards,
                    COALESCE(receiving_touchdowns,     0)    AS receiving_touchdowns,
                    COALESCE(yards_after_catch,        0)    AS yards_after_catch,
                    COALESCE(drops,                    0)    AS drops,
                    COALESCE(tackles,                  0)    AS tackles,
                    COALESCE(ast_tackles,              0)    AS ast_tackles,
                    COALESCE(missed_tackles,           0)    AS missed_tackles,
                    COALESCE(def_sacks,                0)    AS def_sacks,
                    COALESCE(def_sack_yards,           0)    AS def_sack_yards,
                    COALESCE(qb_hits,                  0)    AS qb_hits,
                    COALESCE(hurries,                  0)    AS hurries,
                    COALESCE(knockdowns,               0)    AS knockdowns,
                    COALESCE(passes_defended,          0)    AS passes_defended,
                    COALESCE(interceptions,            0)    AS interceptions,
                    COALESCE(int_yards,                0)    AS int_yards,
                    COALESCE(int_touchdowns,           0)    AS int_touchdowns,
                    COALESCE(def_targets,              0)    AS def_targets,
                    COALESCE(def_completions_allowed,  0)    AS def_completions_allowed,
                    COALESCE(tackles_for_loss,         0)    AS tackles_for_loss,
                    COALESCE(fg_attempts,              0)    AS fg_attempts,
                    COALESCE(fg_made,                  0)    AS fg_made,
                    COALESCE(fg_longest,               0)    AS fg_longest,
                    COALESCE(xp_attempts,              0)    AS xp_attempts,
                    COALESCE(xp_made,                  0)    AS xp_made,
                    COALESCE(kick_return_yards,        0)    AS kick_return_yards,
                    COALESCE(punt_return_yards,        0)    AS punt_return_yards,
                    team_points_scored, team_points_allowed, game_result,
                    pff_grade
                FROM player_game_stats
                WHERE game_id = %s
                ORDER BY team, position, player_name
                """,
                [game_id],
            )
            cols = [d[0] for d in cursor.description]
            rows = cursor.fetchall()
            players = [dict(zip(cols, r)) for r in rows]
            logger.info("fetch_players_from_game %s: %d rows", game_id, len(players))
            return players
        except Exception as e:
            logger.warning("fetch_players_from_game failed for %s: %s", game_id, e)
            return []
        finally:
            cursor.close()

    def close(self):
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None
