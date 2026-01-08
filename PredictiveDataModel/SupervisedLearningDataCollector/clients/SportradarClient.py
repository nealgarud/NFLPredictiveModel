import requests
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class SportradarClient:
    """Client for interacting with Sportradar NFL API"""
    
    def __init__(self):
        self.api_key = os.environ.get('SPORTRADAR_API_KEY')
        self.base_url = os.environ.get(
            'SPORTRADAR_BASE_URL',
            'https://api.sportradar.com/nfl/official/trial/v7/en'
        )
        
        if not self.api_key:
            raise ValueError("SPORTRADAR_API_KEY environment variable not set")
        
        logger.info(f"SportradarClient initialized")
    
    def get_depth_chart(self, season, week, season_type='REG'):
        """Fetch depth chart data for all teams for a specific week"""
        endpoint = f"/seasons/{season}/{season_type}/{week}/depth_charts.json"
        logger.info(f"Fetching depth chart: {season} {season_type} Week {week}")
        return self._make_request(endpoint)
    
    def get_injuries(self, season, week, season_type='REG'):
        """Fetch injury report data for all teams for a specific week"""
        endpoint = f"/seasons/{season}/{season_type}/{week}/injuries.json"
        logger.info(f"Fetching injuries: {season} {season_type} Week {week}")
        return self._make_request(endpoint)
    
    def get_game_roster(self, game_id):
        """Fetch game roster showing who was active/inactive for a specific game"""
        endpoint = f"/games/{game_id}/roster.json"
        logger.info(f"Fetching game roster: {game_id}")
        return self._make_request(endpoint)
   
    
    def _make_request(self, endpoint):
        """Make GET request to Sportradar API"""
        url = f"{self.base_url}{endpoint}"
        params = {"api_key": self.api_key}
        
        try:
            logger.info(f"Calling API: {url}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            logger.info(f"✓ Success: {response.status_code}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Error: {e}")
            raise