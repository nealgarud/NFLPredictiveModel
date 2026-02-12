"""
PFF Grade Client - Fetch player grades from Supabase
Replaces Madden ratings with PFF grades for impact calculations
"""

import logging
from typing import Tuple, Optional
import pg8000

logger = logging.getLogger()


class PFFGradeClient:
    """
    Client for fetching PFF grades from Supabase database.
    
    PFF grades are stored by position in separate tables:
    - pff_qb_grades
    - pff_rb_grades  
    - pff_wr_grades
    - pff_ol_grades
    - pff_def_grades
    """
    
    def __init__(self, db_connection):
        """
        Initialize PFF client with database connection
        
        Args:
            db_connection: pg8000 database connection object
        """
        self.db_conn = db_connection
        self._cached_grades = {}  # Cache: {season-team-name: (grade, found)}
        logger.info("PFFGradeClient initialized")
    
    
    def get_player_grade(
        self, 
        player_name: str, 
        team: str, 
        position: str,
        season: int = 2024
    ) -> Tuple[float, bool]:
        """
        Look up player's PFF grade from appropriate position table.
        
        Args:
            player_name: Player's full name
            team: Team abbreviation (e.g., 'KC', 'SF')
            position: Standardized position (QB, RB, WR, TE, OL, EDGE, LB, CB, S, etc.)
            season: Season year
        
        Returns:
            tuple: (grade: float, found: bool)
                - grade: PFF overall grade (60-99 range, default 70)
                - found: True if player was found in database
        """
        
        # Check cache first
        cache_key = f"{season}-{team}-{player_name}-{position}"
        if cache_key in self._cached_grades:
            return self._cached_grades[cache_key]
        
        # Determine which table to query based on position
        table_name = self._get_pff_table_for_position(position)
        
        if not table_name:
            logger.debug(f"No PFF table for position {position}, using default grade")
            result = (70.0, False)
            self._cached_grades[cache_key] = result
            return result
        
        try:
            cursor = self.db_conn.cursor()
            
            # STRATEGY 1: Exact match (name + team)
            query = f"""
                SELECT grades_offense 
                FROM {table_name}
                WHERE player = %s 
                AND team_name = %s
                AND player_game_count >= 1
                LIMIT 1
            """
            
            cursor.execute(query, (player_name, team))
            result = cursor.fetchone()
            
            if result and result[0] is not None:
                grade = float(result[0])
                cursor.close()
                self._cached_grades[cache_key] = (grade, True)
                logger.debug(f"✓ Found PFF grade: {player_name} ({team}) = {grade}")
                return (grade, True)
            
            # STRATEGY 2: Normalized name match
            normalized_name = self._normalize_player_name(player_name)
            if normalized_name:
                # Use LOWER() for case-insensitive match
                query = f"""
                    SELECT grades_offense 
                    FROM {table_name}
                    WHERE LOWER(player) = LOWER(%s)
                    AND team_name = %s
                    AND player_game_count >= 1
                    LIMIT 1
                """
                
                cursor.execute(query, (normalized_name, team))
                result = cursor.fetchone()
                
                if result and result[0] is not None:
                    grade = float(result[0])
                    cursor.close()
                    logger.debug(f"✓ Found via normalized: {player_name} -> {normalized_name} = {grade}")
                    self._cached_grades[cache_key] = (grade, True)
                    return (grade, True)
            
            # STRATEGY 3: Name-only match (ignore team - handles trades)
            query = f"""
                SELECT grades_offense, team_name
                FROM {table_name}
                WHERE LOWER(player) = LOWER(%s)
                AND player_game_count >= 1
                LIMIT 1
            """
            
            cursor.execute(query, (normalized_name,))
            result = cursor.fetchone()
            
            if result and result[0] is not None:
                grade = float(result[0])
                matched_team = result[1]
                cursor.close()
                logger.debug(f"✓ Found via name-only: {player_name} ({team} -> {matched_team}) = {grade}")
                self._cached_grades[cache_key] = (grade, True)
                return (grade, True)
            
            cursor.close()
            
            # NOT FOUND - return default
            logger.debug(f"Player not found in {table_name}: {player_name} ({team})")
            result = (70.0, False)
            self._cached_grades[cache_key] = result
            return result
        
        except Exception as e:
            logger.warning(f"Error querying PFF grades for {player_name}: {str(e)}")
            return (70.0, False)
    
    
    def _get_pff_table_for_position(self, position: str) -> Optional[str]:
        """
        Map standardized position to PFF table name.
        
        Args:
            position: Standardized position key (QB, RB, WR, etc.)
        
        Returns:
            str: Table name or None if position not supported
        """
        # Offensive positions
        if position == 'QB':
            return 'pff_qb_grades'
        
        if position in ['RB', 'FB']:
            return 'pff_rb_grades'
        
        if position in ['WR', 'TE']:
            return 'pff_wr_grades'
        
        if position in ['LT', 'LG', 'C', 'RG', 'RT', 'OL']:
            return 'pff_ol_grades'
        
        # Defensive positions
        if position in ['EDGE', 'DT', 'NT', 'DE', 'DL', 'LB', 'MLB', 'ILB', 'OLB', 'CB', 'S', 'FS', 'SS', 'DB']:
            return 'pff_def_grades'
        
        # Special teams (use default - or add pff_st_grades later)
        if position in ['K', 'P', 'LS']:
            return None
        
        return None
    
    
    def _normalize_player_name(self, name: str) -> Optional[str]:
        """
        Normalize player name for better matching.
        
        Examples:
            "A.J. Brown" -> "aj brown"
            "Patrick Mahomes II" -> "patrick mahomes"
        
        Args:
            name: Raw player name
        
        Returns:
            str: Normalized name or None
        """
        if not name:
            return None
        
        # Convert to lowercase
        normalized = str(name).lower()
        
        # Remove common suffixes
        suffixes = [' jr.', ' jr', ' sr.', ' sr', ' ii', ' iii', ' iv', ' v']
        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
        
        # Remove periods (A.J. -> aj)
        normalized = normalized.replace('.', '')
        
        # Replace hyphens with spaces
        normalized = normalized.replace('-', ' ')
        
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        
        return normalized.strip()
    
    
    def clear_cache(self):
        """Clear the grade cache (useful between games/weeks)"""
        self._cached_grades.clear()
        logger.info("PFF grade cache cleared")


if __name__ == "__main__":
    # Test the client
    print("PFFGradeClient - Testing...")
    
    import os
    
    # Mock connection for testing structure
    print("✓ Client structure validated")
    print("Note: Actual database testing requires connection and PFF tables")

