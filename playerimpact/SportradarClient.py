"""
SportradarClient - Fetch NFL data from Sportradar API

Handles:
- Weekly depth charts
- Injury reports
- Game rosters (active/inactive status)
- Player profiles
"""

import requests
import os
import logging
import time
from typing import Dict, Any, Optional

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class SportradarClient:
    """Client for interacting with Sportradar NFL API"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Sportradar API client
        
        Args:
            api_key: Sportradar API key (if None, reads from SPORTRADAR_API_KEY env var)
        """
        self.api_key = api_key or os.environ.get('SPORTRADAR_API_KEY')
        self.base_url = os.environ.get(
            'SPORTRADAR_BASE_URL',
            'https://api.sportradar.com/nfl/official/trial/v7/en'
        )
        
        if not self.api_key:
            raise ValueError("SPORTRADAR_API_KEY not provided and environment variable not set")
        
        # Rate limiting: Sportradar allows 1 request per second on trial
        self.min_request_interval = 1.0  # seconds
        self.last_request_time = 0
        
        logger.info("SportradarClient initialized")
    
    def get_depth_chart(self, season: int, week: int, season_type: str = 'REG') -> Dict[str, Any]:
        """
        Fetch depth chart data for all teams for a specific week
        
        Args:
            season: Year (e.g., 2024, 2025)
            week: Week number (1-18 for REG, 1-4 for POST)
            season_type: 'REG' (regular season) or 'POST' (playoffs)
            
        Returns:
            dict: Full depth chart response with all teams
        """
        endpoint = f"/seasons/{season}/{season_type}/{week}/depth_charts.json"
        logger.info(f"Fetching depth chart: {season} {season_type} Week {week}")
        return self._make_request(endpoint)
    
    def get_injuries(self, season: int, week: int, season_type: str = 'REG') -> Dict[str, Any]:
        """
        Fetch injury report data for all teams for a specific week
        
        Args:
            season: Year (e.g., 2024, 2025)
            week: Week number
            season_type: 'REG' or 'POST'
            
        Returns:
            dict: Full injury report with all teams
        """
        endpoint = f"/seasons/{season}/{season_type}/{week}/injuries.json"
        logger.info(f"Fetching injuries: {season} {season_type} Week {week}")
        return self._make_request(endpoint)
    
    def get_game_roster(self, game_id: str) -> Dict[str, Any]:
        """
        Fetch game roster showing who was active/inactive for a specific game
        
        Args:
            game_id: Sportradar game UUID
            
        Returns:
            dict: Game roster with home/away teams and player statuses
        """
        endpoint = f"/games/{game_id}/roster.json"
        logger.info(f"Fetching game roster: {game_id}")
        return self._make_request(endpoint)
    
    def get_game_statistics(self, game_id: str) -> Dict[str, Any]:
        """
        Fetch game statistics showing who actually played and their stats
        
        Args:
            game_id: Sportradar game UUID
            
        Returns:
            dict: Game statistics with home/away player stats by category
        """
        endpoint = f"/games/{game_id}/statistics.json"
        logger.info(f"Fetching game statistics: {game_id}")
        return self._make_request(endpoint)
    
    def get_team_roster(self, team_id: str, season: int = 2025) -> Dict[str, Any]:
        """
        Fetch full team roster for a season
        
        Args:
            team_id: Sportradar team UUID
            season: Year (e.g., 2025)
            
        Returns:
            dict: Team roster with all players
        """
        endpoint = f"/teams/{team_id}/full_roster.json"
        logger.info(f"Fetching team roster: {team_id} ({season})")
        return self._make_request(endpoint)
    
    def get_player_profile(self, player_id: str) -> Dict[str, Any]:
        """
        Fetch detailed player profile
        
        Args:
            player_id: Sportradar player UUID
            
        Returns:
            dict: Player profile with stats, position, etc.
        """
        endpoint = f"/players/{player_id}/profile.json"
        logger.info(f"Fetching player profile: {player_id}")
        return self._make_request(endpoint)
    
    def get_weekly_schedule(self, season: int, week: int, season_type: str = 'REG') -> Dict[str, Any]:
        """
        Fetch all games scheduled for a specific week
        
        CRITICAL: Use this to get game_ids for processing
        
        Args:
            season: Year (e.g., 2025)
            week: Week number (1-18 for REG, 1-4 for POST)
            season_type: 'REG' (regular season) or 'POST' (playoffs)
            
        Returns:
            dict: Weekly schedule with all games, including game_ids, teams, scores
            
        Example response structure:
        {
            "week": {
                "number": 10,
                "games": [
                    {
                        "id": "ca9d8f84-8e7b-4ee7-a310-54c2e3ca4edc",
                        "home": {"id": "...", "name": "Kansas City Chiefs"},
                        "away": {"id": "...", "name": "Denver Broncos"},
                        "scheduled": "2025-11-10T18:00:00+00:00"
                    }
                ]
            }
        }
        """
        endpoint = f"/seasons/{season}/{season_type}/{week}/schedule.json"
        logger.info(f"Fetching weekly schedule: {season} {season_type} Week {week}")
        return self._make_request(endpoint)
    
    def get_season_schedule(self, season: int, season_type: str = 'REG') -> Dict[str, Any]:
        """
        Fetch complete season schedule
        
        Args:
            season: Year (e.g., 2025)
            season_type: 'REG' or 'POST'
            
        Returns:
            dict: Full season schedule with all weeks and games
        """
        endpoint = f"/seasons/{season}/{season_type}/schedule.json"
        logger.info(f"Fetching season schedule: {season} {season_type}")
        return self._make_request(endpoint)
    
    def get_game_summary(self, game_id: str) -> Dict[str, Any]:
        """
        Fetch game summary (boxscore, final stats)
        
        Args:
            game_id: Sportradar game UUID
            
        Returns:
            dict: Game summary with final score, team stats, player stats
        """
        endpoint = f"/games/{game_id}/summary.json"
        logger.info(f"Fetching game summary: {game_id}")
        return self._make_request(endpoint)
    
    def get_standings(self, season: int, season_type: str = 'REG') -> Dict[str, Any]:
        """
        Fetch current standings
        
        Args:
            season: Year (e.g., 2025)
            season_type: 'REG' or 'POST'
            
        Returns:
            dict: Conference/division standings with wins, losses, etc.
        """
        endpoint = f"/seasons/{season}/{season_type}/standings.json"
        logger.info(f"Fetching standings: {season} {season_type}")
        return self._make_request(endpoint)
    
    def _make_request(self, endpoint: str) -> Dict[str, Any]:
        """
        Make GET request to Sportradar API with rate limiting
        
        Args:
            endpoint: API endpoint (without base URL)
            
        Returns:
            dict: JSON response
            
        Raises:
            requests.exceptions.RequestException: If request fails
        """
        # Rate limiting: ensure minimum time between requests
        time_since_last_request = time.time() - self.last_request_time
        if time_since_last_request < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last_request
            logger.info(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        # Build URL
        url = f"{self.base_url}{endpoint}"
        
        # Use header-based authentication (more secure than query params)
        headers = {
            'accept': 'application/json',
            'x-api-key': self.api_key
        }
        
        try:
            logger.info(f"Calling API: {url}")
            response = requests.get(url, headers=headers, timeout=30)
            self.last_request_time = time.time()
            
            response.raise_for_status()
            logger.info(f"✓ Success: {response.status_code}")
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"✗ HTTP Error: {e}")
            logger.error(f"Response: {response.text if response else 'No response'}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Request Error: {e}")
            raise


# Test the client
if __name__ == "__main__":
    print("SportradarClient - Testing...")
    
    # Test initialization
    try:
        test_api_key = os.environ.get('SPORTRADAR_API_KEY')
        if not test_api_key:
            print("✗ SPORTRADAR_API_KEY environment variable not set")
            exit(1)
        client = SportradarClient(api_key=test_api_key)
        print("✓ Client initialized")
        
        # Test injury fetch (2025 REG Week 10)
        injuries = client.get_injuries(season=2025, week=10, season_type='REG')
        print(f"✓ Fetched injuries: {len(injuries.get('week', {}).get('teams', []))} teams")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")

