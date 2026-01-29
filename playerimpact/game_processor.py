"""
GameProcessor - Orchestrates injury impact calculation for a single game

Combines all components to process game-day roster data and return
injury impact metrics for both teams.
"""

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class GameProcessor:
    """Processes a single game to calculate injury impact for both teams"""
    
    def __init__(self, sportradar_client, position_mapper, weight_assigner, injury_calculator):
        """
        Args:
            sportradar_client: SportradarClient instance
            position_mapper: PositionMapper instance
            weight_assigner: PlayerWeightAssigner instance (configured with Madden data)
            injury_calculator: InjuryImpactCalculator instance
        """
        self.client = sportradar_client
        self.mapper = position_mapper
        self.weight_assigner = weight_assigner
        self.injury_calculator = injury_calculator
        
        logger.info("GameProcessor initialized")

    def process_game(self, game_id, home_team_id, away_team_id, season, week, season_type='REG'):
        """Process a single game and return injury impact for both teams"""
        
        logger.info(f"Processing game {game_id}: {away_team_id} @ {home_team_id}")
        
        # Step 1: Fetch weekly depth chart (contains ALL teams)
        depth_chart_data = self.client.get_depth_chart(season, week, season_type)
        
        # Step 2: Fetch game roster (ACTIVE/INACTIVE for THIS game)
        game_roster_data = self.client.get_game_roster(game_id)
        
        # Step 3: Extract home team's depth chart from weekly data
        home_depth = self._extract_team_depth_chart(depth_chart_data, home_team_id)
        
        # Step 4: Extract away team's depth chart from weekly data
        away_depth = self._extract_team_depth_chart(depth_chart_data, away_team_id)
        
        # Step 5: Extract home team's game roster
        home_roster = self._extract_team_roster(game_roster_data, home_team_id)
        
        # Step 6: Extract away team's game roster
        away_roster = self._extract_team_roster(game_roster_data, away_team_id)
        
        # Step 7: Process home team through pipeline
        home_impact = self._process_team(home_depth, home_roster)
        
        # Step 8: Process away team through pipeline
        away_impact = self._process_team(away_depth, away_roster)
        
        # Step 9: Calculate net advantage (positive = home advantage, negative = away advantage)
        net_advantage = home_impact['replacement_adjusted_score'] - away_impact['replacement_adjusted_score']
        
        # Step 10: Return results
        return {
            'game_id': game_id,
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            'home_impact': home_impact,
            'away_impact': away_impact,
            'net_injury_advantage': net_advantage
        }

    def _extract_team_depth_chart(self, depth_chart_data, team_id):
        """
        Extract a single team's depth chart from weekly depth chart response
        
        Args:
            depth_chart_data: Full depth chart response (dict with 'teams' list)
            team_id: Sportradar team UUID
            
        Returns:
            dict: Single team's depth chart data
        """
        teams = depth_chart_data.get('teams', [])
        
        for team in teams:
            if team['id'] == team_id:
                return team
        
        # If team not found, log warning and return None
        logger.warning(f"Team {team_id} not found in depth chart data")
        return None
    def _extract_team_roster(self, game_roster_data, team_id):
        """
        Extract a single team's roster from game roster response
        
        Args:
            game_roster_data: Full game roster response (dict with 'home' and 'away' keys)
            team_id: Sportradar team UUID
            
        Returns:
            list: List of player dictionaries with active/inactive status
        """
        home_team = game_roster_data.get('home')
        away_team = game_roster_data.get('away')
        
        if home_team and home_team['id'] == team_id:
            return home_team.get('players', [])
        
        if away_team and away_team['id'] == team_id:
            return away_team.get('players', [])
        
        # Team not found
        logger.warning(f"Team {team_id} not found in game roster")
        return []


    def _process_team(self, team_depth_chart, team_roster):
        """
        Run a single team through the full injury impact pipeline
        
        Args:
            team_depth_chart: Team's depth chart data (dict)
            team_roster: Team's game roster with active/inactive status (list)
            
        Returns:
            dict: Injury impact metrics for this team
        """
        
        # Step 1: Map positions (PositionMapper handles iteration internally)
        mapped_players = self.mapper.map_team_depth_chart(team_depth_chart)
        
        # Step 2: Assign weights (PlayerWeightAssigner handles iteration internally)
        weighted_players = self.weight_assigner.assign_weights(mapped_players)
        
        # Step 3: Calculate injury impact (InjuryImpactCalculator handles iteration internally)
        injury_impact = self.injury_calculator.calculate_impact(weighted_players, team_roster)
        
        return injury_impact