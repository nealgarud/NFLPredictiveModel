"""
PFFDataFetcher - Fetches PFF grades from database for player impact calculations

Handles position-specific grade lookups and provides a unified interface
for the PlayerWeightAssigner to get player quality ratings.
"""

import logging
from typing import Optional
from DatabaseUtils import DatabaseUtils

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class PFFDataFetcher:
    """Fetches PFF grades from database for active roster players"""
    
    def __init__(self, db_utils: DatabaseUtils):
        """
        Initialize PFF data fetcher
        
        Args:
            db_utils: Database utilities instance for querying PFF tables
        """
        self.db_utils = db_utils
        self.grade_cache = {}  # Cache grades to avoid repeated queries
        logger.info("PFFDataFetcher initialized")
    
    def get_player_grade(self, player_id: str, player_name: str, team: str, 
                        position: str, season: int) -> float:
        """
        Get PFF grade for a player, with caching.
        
        Args:
            player_id: Sportradar player ID
            player_name: Player's full name
            team: Team abbreviation
            position: Player position
            season: Season year
        
        Returns:
            PFF grade (0-100), defaults to 70.0 if not found
        """
        cache_key = f"{player_name}_{team}_{season}"
        
        # Check cache first
        if cache_key in self.grade_cache:
            return self.grade_cache[cache_key]
        
        # Fetch from database
        grade = self.db_utils.fetch_pff_grade(player_name, team, position, season)
        
        if grade is None:
            logger.debug(f"PFF grade not found for {player_name} ({position}, {team}), using default 70.0")
            grade = 70.0  # Default to average tier
        
        # Cache the result
        self.grade_cache[cache_key] = grade
        
        return grade
    
    def clear_cache(self):
        """Clear the grade cache (useful between games or seasons)"""
        self.grade_cache = {}
        logger.debug("PFF grade cache cleared")
