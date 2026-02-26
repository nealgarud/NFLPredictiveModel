"""
DatabaseUtils.py
Handles PostgreSQL database connections and operations for PFF game processing.
"""

import os
import logging
import pg8000
from typing import Optional, List, Tuple, Any, Dict
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class DatabaseUtils:
    """
    PostgreSQL database connection and query utilities for PFF data.
    Handles fetching PFF grades and storing game impact calculations.
    """
    
    def __init__(self):
        """Initialize database connection from environment variables"""
        # Support both naming conventions: DB_* and SUPABASE_DB_*
        # Strip whitespace to prevent authentication errors
        self.host = (os.environ.get('SUPABASE_DB_HOST') or os.environ.get('DB_HOST', '')).strip()
        self.port = int(os.environ.get('SUPABASE_DB_PORT') or os.environ.get('DB_PORT', 5432))
        self.database = (os.environ.get('SUPABASE_DB_NAME') or os.environ.get('DB_NAME', '')).strip()
        self.user = (os.environ.get('SUPABASE_DB_USER') or os.environ.get('DB_USER', '')).strip()
        self.password = (os.environ.get('SUPABASE_DB_PASSWORD') or os.environ.get('DB_PASSWORD', '')).strip()
        
        # Validate environment variables
        if not all([self.host, self.database, self.user, self.password]):
            raise ValueError("Missing required database environment variables")
        
        self.connection: Optional[pg8000.Connection] = None
        logger.info("DatabaseUtils initialized")
    
    def connect(self) -> pg8000.Connection:
        """
        Establish database connection with automatic reconnection on transaction errors.
        Uses autocommit mode to prevent transaction blocks.
        """
        # Check if existing connection is healthy
        if self.connection is not None:
            try:
                # Test connection with simple query
                cursor = self.connection.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                return self.connection
            except Exception as e:
                # Connection failed or transaction aborted - reconnect
                logger.warning(f"Connection unhealthy, reconnecting: {e}")
                try:
                    self.connection.close()
                except:
                    pass
                self.connection = None
        
        # Create new connection
        try:
            self.connection = pg8000.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                ssl_context=True
            )
            # Enable autocommit to prevent transaction blocks on read queries
            self.connection.autocommit = True
            logger.info(f"✓ Connected to database: {self.database} (autocommit=True)")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
        
        return self.connection
    
    def fetch_pff_grade(self, player_name: str, team: str, position: str, season: int) -> Optional[float]:
        """
        Fetch PFF grade for a player from the appropriate PFF table.
        Uses fuzzy name matching to handle variations (apostrophes, hyphens, initials).
        
        Args:
            player_name: Player's full name (from Sportradar)
            team: Team abbreviation (from Sportradar)
            position: Player position (QB, RB, WR, TE, OL positions, DEF positions)
            season: Season year
        
        Returns:
            PFF grade (0-100) or None if not found
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            # Determine which table and grade column to query
            table_name, grade_column = self._get_table_and_grade_column(position)
            
            if table_name is None:
                logger.warning(f"No PFF table mapping for position: {position}")
                return None
            
            # Normalize team abbreviation (handle BLT→BAL, etc.)
            normalized_team = self._normalize_team_abbr(team)
            
            logger.info(f"Looking up: {player_name} | {position} → {table_name} | team={team}→{normalized_team} | season={season}")
            
            # Try 1: Exact match
            grade = self._try_exact_match(cursor, table_name, grade_column, player_name, normalized_team, season)
            if grade is not None:
                return grade
            
            # Try 2: Case-insensitive match
            grade = self._try_case_insensitive_match(cursor, table_name, grade_column, player_name, normalized_team, season)
            if grade is not None:
                logger.debug(f"✓ Case-insensitive match: '{player_name}'")
                return grade
            
            # Try 3: Fuzzy match (remove special chars from BOTH sides using Python)
            normalized_name = self._normalize_name(player_name)
            grade = self._try_fuzzy_match_python(cursor, table_name, grade_column, normalized_name, normalized_team, season)
            if grade is not None:
                logger.debug(f"✓ Fuzzy match: '{player_name}' → '{normalized_name}'")
                return grade
            
            # Try 4: Last name only (if unique)
            last_name = player_name.split()[-1] if ' ' in player_name else player_name
            grade = self._try_last_name_match(cursor, table_name, grade_column, last_name, normalized_team, season)
            if grade is not None:
                logger.debug(f"✓ Last name match: '{player_name}' → '{last_name}'")
                return grade
            
            logger.debug(f"✗ No PFF match: {player_name} ({position}, {team}, {season})")
            return None
            
        except Exception as e:
            logger.warning(f"Error fetching PFF grade for {player_name}: {e}")
            return None
        finally:
            cursor.close()
    
    def _normalize_team_abbr(self, team: str) -> str:
        """Normalize team abbreviations (BLT→BAL, etc.)"""
        mapping = {
            'BLT': 'BAL',
            'CLV': 'CLE',
            'ARZ': 'ARI',
            'HST': 'HOU'
        }
        return mapping.get(team, team)
    
    def _normalize_name(self, name: str) -> str:
        """
        Normalize player name: remove apostrophes, hyphens, periods, extra spaces.
        
        Examples:
            "De'Marcus Lawrence" → "demarcus lawrence"
            "T.J. Watt" → "tj watt"
            "Jalyn Armour-Davis" → "jalyn armourdavis"
        """
        import re
        normalized = re.sub(r"['\-\.]", '', name)
        normalized = ' '.join(normalized.split())
        return normalized.lower()
    
    def _try_exact_match(self, cursor, table_name, grade_column, player_name, team, season):
        """Try exact name match"""
        query = f"""
            SELECT {grade_column}
            FROM {table_name}
            WHERE player = %s 
              AND team_name = %s 
              AND season = %s
            LIMIT 1
        """
        logger.debug(f"Exact match query: table={table_name}, player={player_name}, team={team}, season={season}")
        cursor.execute(query, (player_name, team, season))
        result = cursor.fetchone()
        
        if result and result[0] is not None:
            logger.info(f"✓ FOUND: {player_name} ({team}) = {result[0]}")
            return float(result[0]) if isinstance(result[0], Decimal) else result[0]
        return None
    
    def _try_case_insensitive_match(self, cursor, table_name, grade_column, player_name, team, season):
        """Try case-insensitive exact match"""
        query = f"""
            SELECT {grade_column}
            FROM {table_name}
            WHERE LOWER(player) = LOWER(%s)
              AND team_name = %s 
              AND season = %s
            LIMIT 1
        """
        cursor.execute(query, (player_name, team, season))
        result = cursor.fetchone()
        
        if result and result[0] is not None:
            return float(result[0]) if isinstance(result[0], Decimal) else result[0]
        return None
    
    def _try_fuzzy_match_python(self, cursor, table_name, grade_column, normalized_name, team, season):
        """
        Fuzzy match by normalizing in Python (more reliable than SQL regex).
        Fetches all players for team/season, then matches in Python.
        """
        import re
        
        query = f"""
            SELECT player, {grade_column}
            FROM {table_name}
            WHERE team_name = %s 
              AND season = %s
        """
        cursor.execute(query, (team, season))
        results = cursor.fetchall()
        
        for row in results:
            db_player_name = row[0]
            grade = row[1]
            
            # Normalize database name
            db_normalized = re.sub(r"['\-\.]", '', db_player_name).lower()
            db_normalized = ' '.join(db_normalized.split())
            
            # Compare normalized names
            if db_normalized == normalized_name:
                logger.debug(f"Python fuzzy match: '{db_player_name}' (DB) = '{normalized_name}' (query)")
                return float(grade) if isinstance(grade, Decimal) else grade
        
        return None
    
    def _try_last_name_match(self, cursor, table_name, grade_column, last_name, team, season):
        """Try match by last name only (only if exactly 1 match to avoid ambiguity)"""
        query = f"""
            SELECT {grade_column}
            FROM {table_name}
            WHERE player LIKE %s
              AND team_name = %s 
              AND season = %s
        """
        cursor.execute(query, (f'%{last_name}%', team, season))
        results = cursor.fetchall()
        
        # Only return if exactly 1 match (avoid ambiguous matches)
        if len(results) == 1 and results[0][0] is not None:
            return float(results[0][0]) if isinstance(results[0][0], Decimal) else results[0][0]
        return None
    
    def _get_table_and_grade_column(self, position: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Map position to the appropriate PFF table and grade column.
        
        Returns:
            Tuple of (table_name, grade_column) or (None, None) if no mapping
        """
        position = position.upper()
        
        # QB positions
        if position in ['QB']:
            return ('qb_pff_ratings', 'grades_offense')
        
        # RB positions
        elif position in ['RB', 'HB', 'FB']:
            return ('rb_pff_ratings', 'grades_offense')
        
        # WR/TE positions
        elif position in ['WR']:
            return ('wr_pff_ratings', 'grades_offense')
        elif position in ['TE']:
            return ('wr_pff_ratings', 'grades_offense')  # TEs often in WR table
        
        # OL positions - special handling needed for averaging
        elif position in ['LT', 'RT', 'LG', 'RG', 'C', 'T', 'G', 'OL']:
            return ('oline_pff_ratings', '(grades_pass_block + grades_run_block) / 2.0')
        
        # Defensive positions
        elif position in ['DE', 'DT', 'NT', 'EDGE', 'LB', 'CB', 'S', 'FS', 'SS']:
            return ('defense_pff_ratings', 'grades_defense')
        
        else:
            return (None, None)
    
    def fetch_games_to_process(self, season: Optional[int] = None, 
                               week: Optional[int] = None,
                               limit: Optional[int] = None,
                               force: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch games from game_id_mapping that need impact processing.
        
        Args:
            season: Filter by season (optional)
            week: Filter by week (optional)
            limit: Limit number of games returned (optional)
        
        Returns:
            List of game dictionaries with sportradar_id and metadata
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            query = """
                SELECT game_id, sportradar_id, season, week, home_team, away_team
                FROM game_id_mapping
                WHERE sportradar_id IS NOT NULL
            """
            if not force:
                query += " AND home_total_impact IS NULL"
            params = []
            
            if season is not None:
                query += " AND season = %s"
                params.append(season)
            
            if week is not None:
                query += " AND week = %s"
                params.append(week)
            
            query += " ORDER BY season DESC, week DESC, game_id"
            
            if limit is not None:
                query += f" LIMIT {limit}"
            
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            
            games = []
            for row in rows:
                games.append({
                    'game_id': row[0],
                    'sportradar_id': row[1],
                    'season': row[2],
                    'week': row[3],
                    'home_team': row[4],
                    'away_team': row[5]
                })
            
            logger.info(f"Fetched {len(games)} games to process")
            return games
            
        except Exception as e:
            logger.error(f"Failed to fetch games: {e}")
            raise
        finally:
            cursor.close()
    
    def update_game_impact(self, game_id: str, home_impact: Dict[str, Any], 
                          away_impact: Dict[str, Any]) -> bool:
        """
        Update game_id_mapping with calculated impact scores for both teams.
        
        Args:
            game_id: Internal game ID (e.g., '2024_10_BUF_KC')
            home_impact: Home team impact data dictionary
            away_impact: Away team impact data dictionary
        
        Returns:
            True if successful, False otherwise
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            impact_diff = home_impact['total_impact_score'] - away_impact['total_impact_score']
            avg_impact_diff = home_impact['avg_player_impact'] - away_impact['avg_player_impact']
            
            # Convert player_details to JSON string
            import json
            home_players_json = json.dumps(home_impact.get('player_details', []))
            away_players_json = json.dumps(away_impact.get('player_details', []))
            
            logger.info(f"Updating game {game_id}: home={home_impact['total_impact_score']:.2f}, away={away_impact['total_impact_score']:.2f}")
            
            # First, verify the game exists
            check_query = "SELECT game_id FROM game_id_mapping WHERE game_id = %s"
            cursor.execute(check_query, (game_id,))
            exists = cursor.fetchone()
            
            if not exists:
                logger.error(f"Game {game_id} not found in game_id_mapping!")
                return False
            
            logger.info(f"Game {game_id} exists in database, proceeding with UPDATE")
            
            query = """
                UPDATE game_id_mapping
                SET 
                    home_total_impact = %s,
                    home_avg_impact = %s,
                    home_active_players = %s,
                    home_tier_1_count = %s,
                    home_tier_2_count = %s,
                    home_tier_3_count = %s,
                    home_tier_4_count = %s,
                    home_tier_5_count = %s,
                    home_qb1_active = %s,
                    home_rb1_active = %s,
                    home_wr1_active = %s,
                    home_edge1_active = %s,
                    home_cb1_active = %s,
                    home_lt_active = %s,
                    home_s1_active = %s,
                    home_player_details = %s,
                    away_total_impact = %s,
                    away_avg_impact = %s,
                    away_active_players = %s,
                    away_tier_1_count = %s,
                    away_tier_2_count = %s,
                    away_tier_3_count = %s,
                    away_tier_4_count = %s,
                    away_tier_5_count = %s,
                    away_qb1_active = %s,
                    away_rb1_active = %s,
                    away_wr1_active = %s,
                    away_edge1_active = %s,
                    away_cb1_active = %s,
                    away_lt_active = %s,
                    away_s1_active = %s,
                    away_player_details = %s,
                    impact_differential = %s,
                    avg_impact_differential = %s,
                    impact_calculated_at = CURRENT_TIMESTAMP
                WHERE game_id = %s
            """
            
            cursor.execute(query, (
                home_impact['total_impact_score'],
                home_impact['avg_player_impact'],
                home_impact['active_player_count'],
                home_impact['tier_1_count'],
                home_impact['tier_2_count'],
                home_impact['tier_3_count'],
                home_impact['tier_4_count'],
                home_impact['tier_5_count'],
                home_impact['qb1_active'],
                home_impact['rb1_active'],
                home_impact['wr1_active'],
                home_impact['edge1_active'],
                home_impact['cb1_active'],
                home_impact['lt_active'],
                home_impact['s1_active'],
                home_players_json,
                away_impact['total_impact_score'],
                away_impact['avg_player_impact'],
                away_impact['active_player_count'],
                away_impact['tier_1_count'],
                away_impact['tier_2_count'],
                away_impact['tier_3_count'],
                away_impact['tier_4_count'],
                away_impact['tier_5_count'],
                away_impact['qb1_active'],
                away_impact['rb1_active'],
                away_impact['wr1_active'],
                away_impact['edge1_active'],
                away_impact['cb1_active'],
                away_impact['lt_active'],
                away_impact['s1_active'],
                away_players_json,
                impact_diff,
                avg_impact_diff,
                game_id
            ))
            
            # With autocommit=True, no need to call commit()
            rows_updated = cursor.rowcount
            
            logger.info(f"UPDATE executed: {rows_updated} rows affected")
            
            if rows_updated > 0:
                logger.info(f"✓ Updated game_id_mapping for {game_id} (impact diff: {impact_diff:.2f})")
                return True
            else:
                logger.error(f"UPDATE returned 0 rows for game_id: {game_id}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to update game impact for {game_id}: {e}", exc_info=True)
            return False
        finally:
            cursor.close()
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("Database connection closed")
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if exc_type:
            if self.connection:
                self.connection.rollback()
        self.close()
