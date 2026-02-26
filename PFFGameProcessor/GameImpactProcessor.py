"""
GameImpactProcessor - Calculate team player impact for games using PFF grades

Process Flow:
1. Fetch game roster from Sportradar (who played)
2. Map player positions with depth chart
3. Fetch PFF grades from database
4. Assign weights based on position importance + PFF quality
5. Calculate team impact scores
6. Store results in database
"""

import logging
from typing import Dict, Any, List, Optional
from SportradarClient import SportradarClient
from PositionMapper import PositionMapper
from PlayerWeightAssigner import PlayerWeightAssigner
from PFFDataFetcher import PFFDataFetcher
from DatabaseUtils import DatabaseUtils

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class GameImpactProcessor:
    """Processes games to calculate player impact using PFF grades"""
    
    def __init__(self, sportradar_client: SportradarClient, db_utils: DatabaseUtils):
        """
        Initialize game impact processor
        
        Args:
            sportradar_client: Client for fetching game rosters
            db_utils: Database utilities for PFF grades and storage
        """
        self.sportradar = sportradar_client
        self.db_utils = db_utils
        self.position_mapper = PositionMapper()
        
        # Initialize PFF data fetcher
        self.pff_fetcher = PFFDataFetcher(db_utils)
        
        # Initialize weight assigner with PFF grade fetcher
        def fetch_pff_grade(player_id, position, season):
            # We'll need player_name and team from context
            # This will be called from within process_game where we have full player info
            return 70.0  # Placeholder - actual fetching happens in assign_weights_with_pff
        
        self.weight_assigner = PlayerWeightAssigner(pff_data_fetcher=fetch_pff_grade)
        
        logger.info("GameImpactProcessor initialized")
    
    def process_game(self, internal_game_id: str, sportradar_id: str, 
                    season: int, week: int, home_team: str, away_team: str) -> Dict[str, Any]:
        """
        Process a single game and calculate player impact for both teams.
        
        Args:
            internal_game_id: Internal game ID (e.g., '2024_10_BUF_KC')
            sportradar_id: Sportradar game UUID
            season: Season year
            week: Week number
            home_team: Home team abbreviation
            away_team: Away team abbreviation
        
        Returns:
            Dictionary with impact results for both teams
        """
        logger.info(f"Processing game: {internal_game_id} ({away_team} @ {home_team})")
        logger.info(f"  Sportradar ID: {sportradar_id}")
        
        try:
            # Step 1: Fetch game statistics (shows who actually played) from Sportradar
            stats_data = self.sportradar.get_game_statistics(sportradar_id)
            logger.info(f"Fetched statistics data structure: {list(stats_data.keys())}")
            
            # Step 2: Extract players who actually played from statistics
            home_stats = stats_data.get('statistics', {}).get('home', {})
            away_stats = stats_data.get('statistics', {}).get('away', {})
            
            home_players = self._extract_players_from_statistics(home_stats)
            away_players = self._extract_players_from_statistics(away_stats)
            
            logger.info(f"Home players who played: {len(home_players)}")
            logger.info(f"Away players who played: {len(away_players)}")
            
            home_impact = self._process_team_roster(
                team_roster=home_players,
                team_id=stats_data.get('summary', {}).get('home', {}).get('id', 'unknown'),
                team_abbr=home_team,
                season=season,
                week=week
            )
            
            away_impact = self._process_team_roster(
                team_roster=away_players,
                team_id=stats_data.get('summary', {}).get('away', {}).get('id', 'unknown'),
                team_abbr=away_team,
                season=season,
                week=week
            )
            
            # Step 3: Store results back in game_id_mapping table
            success = self.db_utils.update_game_impact(internal_game_id, home_impact, away_impact)
            
            if not success:
                logger.warning(f"Failed to update game_id_mapping for {internal_game_id}")
            
            return {
                'game_id': internal_game_id,
                'sportradar_id': sportradar_id,
                'home_impact': home_impact['total_impact_score'],
                'home_avg_impact': home_impact['avg_player_impact'],
                'away_impact': away_impact['total_impact_score'],
                'away_avg_impact': away_impact['avg_player_impact'],
                'impact_differential': home_impact['total_impact_score'] - away_impact['total_impact_score'],
                'avg_impact_differential': home_impact['avg_player_impact'] - away_impact['avg_player_impact'],
                'success': success
            }
            
        except Exception as e:
            logger.error(f"Failed to process game {internal_game_id}: {e}")
            raise
    
    def _process_team_roster(self, team_roster: List[Dict], team_id: str, 
                            team_abbr: str, season: int, week: int) -> Dict[str, Any]:
        """
        Process a team's roster and calculate impact score.
        
        Args:
            team_roster: List of player dictionaries (already filtered from statistics)
            team_id: Sportradar team UUID
            team_abbr: Team abbreviation
            season: Season year
            week: Week number
        
        Returns:
            Dictionary with team impact calculations
        """
        logger.info(f"Team {team_abbr}: Processing {len(team_roster)} players who played")
        
        if not team_roster:
            logger.warning(f"No players found for team {team_abbr}")
            return {
                'total_impact_score': 0.0,
                'avg_player_impact': 0.0,
                'active_player_count': 0,
                'tier_1_count': 0,
                'tier_2_count': 0,
                'tier_3_count': 0,
                'tier_4_count': 0,
                'tier_5_count': 0,
                'qb1_active': False,
                'rb1_active': False,
                'wr1_active': False,
                'edge1_active': False,
                'cb1_active': False,
                'lt_active': False,
                's1_active': False
            }
        
        # Step 1: Standardize positions and assign depth
        mapped_positions = self._map_and_assign_depth(team_roster)
        
        # Step 2: Assign weights with PFF grades
        weighted_players = self._assign_weights_with_pff(mapped_positions, team_abbr, season)
        
        # Step 3: Calculate team impact scores
        impact_data = self._calculate_team_impact(weighted_players)
        
        return impact_data
    
    def _map_and_assign_depth(self, players: List[Dict]) -> List[Dict]:
        """
        Standardize positions and assign depth chart order.
        
        Args:
            players: Raw player list from Sportradar
        
        Returns:
            Players with standard_position and position_key assigned
        """
        # Standardize each player's position
        mapped = []
        for player in players:
            std_player = self.position_mapper.map_player_position(player)
            mapped.append(std_player)
        
        # Group by position and assign depth
        position_groups = {}
        for player in mapped:
            pos = player.get('standard_position', 'UNKNOWN')
            if pos not in position_groups:
                position_groups[pos] = []
            position_groups[pos].append(player)
        
        # Assign position_key based on depth order
        result = []
        for position, players_at_pos in position_groups.items():
            # Sort by jersey number or name as tiebreaker (Sportradar doesn't give depth)
            players_at_pos.sort(key=lambda p: (p.get('jersey', 99), p.get('name', '')))
            
            for depth, player in enumerate(players_at_pos, start=1):
                player['position_key'] = self.position_mapper.create_position_key(position, depth)
                player['depth_order'] = depth
                result.append(player)
        
        logger.info(f"Mapped {len(result)} players with position keys")
        return result
    
    def _extract_players_from_statistics(self, team_stats: Dict[str, Any]) -> List[Dict]:
        """
        Extract all players who played from game statistics.
        No filtering - includes everyone who appears in any stat category.
        
        Args:
            team_stats: Statistics for one team (home or away) from Sportradar
                       Structure: {rushing: {players: [...]}, passing: {players: [...]}, ...}
        
        Returns:
            List of player dicts with id, name, position
        """
        players_dict = {}
        
        # All stat categories
        all_categories = [
            'rushing', 'receiving', 'passing', 'defense',
            'punts', 'kick_returns', 'punt_returns', 'kickoffs', 
            'field_goals', 'extra_points'
        ]
        
        for category in all_categories:
            if category in team_stats and 'players' in team_stats[category]:
                for player in team_stats[category]['players']:
                    player_id = player.get('id')
                    
                    # Add every player who appears (no filtering)
                    if player_id and player_id not in players_dict:
                        players_dict[player_id] = {
                            'id': player_id,
                            'name': player.get('name', 'Unknown'),
                            'position': player.get('position', 'UNKNOWN')
                        }
        
        players = list(players_dict.values())
        logger.info(f"Extracted {len(players)} players who played (no filters)")
        
        return players
    
    def _assign_weights_with_pff(self, mapped_positions: List[Dict], 
                                 team: str, season: int) -> List[Dict]:
        """
        Assign fixed position weights and fetch PFF grades from database.
        
        Weight is purely positional (Boyd's methodology). PFF grade is used
        downstream as the quality multiplier: player_impact = weight × pff_grade.
        Grade tier is tracked for observability only.
        
        Args:
            mapped_positions: Players with position_key assigned
            team: Team abbreviation for PFF lookup
            season: Season year
        
        Returns:
            Players with weights, tiers, and PFF grades assigned
        """
        weighted_players = []
        
        for player in mapped_positions:
            player_name = player.get('name', player.get('player_name', 'Unknown'))
            pff_grade = self.pff_fetcher.get_player_grade(
                player_id=player.get('id', player.get('player_id', '')),
                player_name=player_name,
                team=team,
                position=player.get('standard_position', player.get('position', '')),
                season=season
            )
            
            grade_tier = self.weight_assigner._get_grade_tier(pff_grade)
            
            # Fixed weight lookup -- position importance only
            position_key = player['position_key']
            weight = self.weight_assigner.position_weights.get(position_key)
            
            # Fallback: strip depth number (QB3 → QB, CB4 → CB)
            if weight is None:
                base_position = position_key.rstrip('0123456789')
                weight = self.weight_assigner.position_weights.get(base_position, 0.0)
            
            tier = self.weight_assigner._get_tier_from_weight(weight)
            
            weighted_player = player.copy()
            weighted_player['player_name'] = player_name
            weighted_player['weight'] = weight
            weighted_player['tier'] = tier
            weighted_player['pff_grade'] = pff_grade
            weighted_player['grade_tier'] = grade_tier
            
            weighted_players.append(weighted_player)
        
        logger.info(f"Assigned weights to {len(weighted_players)} players")
        return weighted_players
    
    def _calculate_team_impact(self, weighted_players: List[Dict]) -> Dict[str, Any]:
        """
        Calculate aggregate team impact scores from weighted players.
        
        Formula: Player Impact = Weight × PFF Grade
        Team Impact = Σ(Weight × Grade) for all active players
        
        Args:
            weighted_players: List of players with weights and tiers
        
        Returns:
            Dictionary with impact metrics
        """
        # Calculate total impact using Boyd's formula: weight × player quality
        total_impact = 0.0
        player_details = []
        
        for player in weighted_players:
            weight = player.get('weight', 0.0)
            pff_grade = player.get('pff_grade', 70.0)
            
            # Individual player impact = weight × PFF grade
            player_impact = weight * pff_grade
            total_impact += player_impact
            
            # Store player details for logging and database
            player_details.append({
                'player_name': player.get('player_name', 'Unknown'),
                'position_key': player['position_key'],
                'pff_grade': round(pff_grade, 1),
                'grade_tier': player.get('grade_tier', 'N/A'),
                'weight': round(weight, 3),
                'tier': player['tier'],
                'individual_impact': round(player_impact, 2)
            })
        
        # Count by tier
        tier_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for player in weighted_players:
            tier = player.get('tier', 5)
            tier_counts[tier] += 1
        
        # Check key position flags
        position_flags = {
            'qb1_active': any(p['position_key'] == 'QB1' for p in weighted_players),
            'rb1_active': any(p['position_key'] == 'RB1' for p in weighted_players),
            'wr1_active': any(p['position_key'] == 'WR1' for p in weighted_players),
            'edge1_active': any(p['position_key'] == 'EDGE1' for p in weighted_players),
            'cb1_active': any(p['position_key'] == 'CB1' for p in weighted_players),
            'lt_active': any(p['position_key'] == 'LT' for p in weighted_players),
            's1_active': any(p['position_key'] == 'S1' for p in weighted_players),
        }
        
        # Log detailed player breakdown (top 15 by individual impact)
        top_players = sorted(player_details, key=lambda p: p['individual_impact'], reverse=True)[:15]
        logger.info(f"Top 15 players by individual impact:")
        for p in top_players:
            logger.info(f"  {p['position_key']:10} {p['player_name'][:20]:20} "
                       f"PFF:{p['pff_grade']:5.1f} Weight:{p['weight']:.3f} Impact:{p['individual_impact']:.2f}")
        
        active_count = len(weighted_players)
        avg_impact = round(total_impact / active_count, 2) if active_count > 0 else 0.0

        logger.info(f"TOTAL IMPACT: {total_impact:.2f} | AVG: {avg_impact:.2f} from {active_count} active players")
        
        # Sort player_details by impact for storage
        player_details.sort(key=lambda x: x['individual_impact'], reverse=True)
        
        return {
            'total_impact_score': round(total_impact, 2),
            'avg_player_impact': avg_impact,
            'active_player_count': active_count,
            'tier_1_count': tier_counts[1],
            'tier_2_count': tier_counts[2],
            'tier_3_count': tier_counts[3],
            'tier_4_count': tier_counts[4],
            'tier_5_count': tier_counts[5],
            'player_details': player_details,
            **position_flags
        }
