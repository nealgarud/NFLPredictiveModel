from SportradarClient import SportradarClient
from PlayerWeightAssigner import PlayerWeightAssigner
from PositionMapper import PositionMapper
import logging
from typing import Dict, Any, List, Tuple, Optional
logger = logging.getLogger()

class ImpactCalculator:
    def __init__(self, db_connection):
        self.sportradar = SportradarClient()
        self.weight_assigner = PlayerWeightAssigner()
        self.position_mapper = PositionMapper()
        self.db_conn = db_connection  # For Madden ratings
        self._cached_ratings = {}  # Cache to avoid repeated DB queries
        
        

    def calculate_game_impact(self,game,season):
        sportradar_id = game['sportradar_id']
        game_id = game['game_id']
        week = game['week']

        logger.info(f"Processing game {game_id}: {game['away_team']} @ {game['home_team']}")
        
         # STEP 1: Fetch data from Sportradar
        logger.debug(f"Fetching game statistics for {sportradar_id}")
        game_stats = self.sportradar_client.get_game_statistics(sportradar_id)
        
        logger.debug(f"Fetching game roster for {sportradar_id}")
        game_roster = self.sportradar_client.get_game_roster(sportradar_id)
        
        # STEP 2: Extract team data
        home_team_stats = game_stats.get('statistics', {}).get('home', {})
        away_team_stats = game_stats.get('statistics', {}).get('away', {})
        home_team_roster = game_roster.get('home', {})
        away_team_roster = game_roster.get('away', {})

       #STEP 3: Get Team Abbreviations
        home_abbr = game['home_team']
        away_abbr = game['away_team']
        logger.info(f"Calculating impact for: {away_abbr} @ {home_abbr}")

        away_impact, away_players 
        pass



    def _calculate_team_impact_from_statistics(
        team_stats: Dict[str, Any],
        season: int,
        position_mapper: PositionMapper,
        weight_assigner: PlayerWeightAssigner,
        team_abbr: str
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """
    Calculate team impact score from Game Statistics API (players who actually played!)
    """
    
    # Extract ALL unique players who contributed in ANY stat category
        players_dict = {}
    
        # OFFENSIVE CATEGORIES
        offensive_categories = ['rushing', 'receiving', 'passing']
        for category in offensive_categories:
            if category in team_stats and 'players' in team_stats[category]:
                for player in team_stats[category]['players']:
                    player_id = player.get('id')
                    if player_id and player_id not in players_dict:
                        players_dict[player_id] = {
                            'id': player_id,
                            'name': player.get('name', 'Unknown'),
                            'position': player.get('position', 'Unknown')
                        }
    
        # DEFENSIVE CATEGORY
        if 'defense' in team_stats and 'players' in team_stats['defense']:
            for player in team_stats['defense']['players']:
                player_id = player.get('id')
                if player_id and player_id not in players_dict:
                    players_dict[player_id] = {
                        'id': player_id,
                        'name': player.get('name', 'Unknown'),
                        'position': player.get('position', 'Unknown')
                    }
        
        # SPECIAL TEAMS CATEGORIES
        special_teams = ['punts', 'kick_returns', 'punt_returns', 'kickoffs', 'field_goals', 'extra_points']
        for category in special_teams:
            if category in team_stats and 'players' in team_stats[category]:
                for player in team_stats[category]['players']:
                    player_id = player.get('id')
                    if player_id and player_id not in players_dict:
                        players_dict[player_id] = {
                            'id': player_id,
                            'name': player.get('name', 'Unknown'),
                            'position': player.get('position', 'Unknown')
                        }
        
        players = list(players_dict.values())
        
        if len(players) == 0:
            logger.warning(f"No players found in statistics for team {team_abbr}")
            return 0.0, []
        
        logger.info(f"Found {len(players)} players who PLAYED for {team_abbr}")
        
        # Build list of players with Madden ratings and mapped positions
        players_with_data = []
        
        for player in players:
            player_name = player.get('name', 'Unknown')
            raw_position = player.get('position', 'Unknown')
            
            # Standardize position using PositionMapper
            standard_position = position_mapper.standardize_position(raw_position)
            
            # Look up Madden rating from Supabase
            madden_rating, found_in_db = _get_madden_rating_from_supabase(player_name, team_abbr, season)
            
            # Create player dict for weight assignment
            player_dict = {
                'player_id': player.get('id'),
                'player_name': player_name,
                'raw_position': raw_position,
                'position_key': standard_position,
                'depth_order': 1,
                'overallrating': madden_rating,
                'madden_found': found_in_db
            }
            
            players_with_data.append(player_dict)
        
        logger.info(f"Matched {len(players_with_data)} players with data for {team_abbr}")
        
        # Assign weights using PlayerWeightAssigner
        if len(players_with_data) == 0:
            return 0.0, []
        
        weighted_players = weight_assigner.assign_weights(players_with_data)
        
        # Calculate total impact
        total_impact = 0.0
        player_details = []
        
        for player in weighted_players:
            weight = player.get('weight', 0.0)
            rating = player.get('overallrating', 70)
            impact = weight * rating
            
            total_impact += impact
            
            # Build detailed player info for response
            player_details.append({
                'name': player.get('player_name', 'Unknown'),
                'position': player.get('raw_position', 'Unknown'),
                'position_key': player.get('position_key', 'Unknown'),
                'rating': rating,
                'weight': round(weight, 3),
                'impact': round(impact, 2),
                'madden_found': player.get('madden_found', False)
            })
        
        logger.info(f"Total impact for {team_abbr}: {total_impact:.2f} ({len(weighted_players)} players who played)")
        
        # Sort players by impact (highest first)
        player_details.sort(key=lambda x: x['impact'], reverse=True)
        
        return total_impact, player_details
    def _calculate_injury_impact_dual_api(
    team_roster: Dict[str, Any],
    team_stats: Dict[str, Any],
    team_abbr: str,
    season: int,
    position_mapper: PositionMapper
) -> Dict[str, Any]:
        """
    Calculate injury impact by comparing Game Roster API (active/inactive) vs Game Statistics API (who played)
    
    Args:
        team_roster: Home/Away team from Game Roster API (shows active/inactive status)
        team_stats: Home/Away team from Game Statistics API (shows who played)
        team_abbr: Team abbreviation
        season: Season year
        position_mapper: Position mapper instance
    
    Returns:
        Dict with injury metrics including inactive starters and key positions out
    """
    
    # STEP 1: Extract all players from roster (active + inactive)
    all_roster_players = {}
    if 'players' in team_roster:
        for player in team_roster['players']:
            player_id = player.get('id')
            if player_id:
                all_roster_players[player_id] = {
                    'id': player_id,
                    'name': player.get('name', 'Unknown'),
                    'position': player.get('position', 'Unknown'),
                    'jersey': player.get('jersey'),
                    'status': player.get('in_game_status', 'unknown').lower()  # 'active' or 'inactive'
                }
    
    # STEP 2: Extract players who actually played (from statistics)
    players_who_played = {}
    
    # Collect from all stat categories
    stat_categories = ['rushing', 'receiving', 'passing', 'defense', 'punts', 'kick_returns', 'punt_returns', 'kickoffs']
    for category in stat_categories:
        if category in team_stats and 'players' in team_stats[category]:
            for player in team_stats[category]['players']:
                player_id = player.get('id')
                if player_id:
                    players_who_played[player_id] = {
                        'id': player_id,
                        'name': player.get('name'),
                        'position': player.get('position')
                    }
    
    logger.info(f"{team_abbr}: {len(all_roster_players)} on roster, {len(players_who_played)} actually played")
    
    if len(all_roster_players) == 0:
        return _empty_injury_impact(team_abbr)
    
    # STEP 3: Identify inactive players (marked inactive OR didn't play)
    inactive_player_ids = {
        player_id for player_id, player in all_roster_players.items()
        if player['status'] == 'inactive' or player_id not in players_who_played
    }
    
    # STEP 4: Log inactive players for debugging
    logger.info(f"{team_abbr}: {len(inactive_player_ids)} total inactive players")
    
    # Build full roster with ratings for position analysis
    all_players_with_ratings = []
    for player_id, player in all_roster_players.items():
        player_name = player.get('name', 'Unknown')
        raw_position = player.get('position', 'Unknown')
        standard_position = position_mapper.standardize_position(raw_position)
        
        rating, found = _get_madden_rating_from_supabase(player_name, team_abbr, season)
        
        all_players_with_ratings.append({
            'player_id': player_id,
            'player_name': player_name,
            'position': standard_position,
            'raw_position': raw_position,
            'rating': rating,
            'is_active': player_id not in inactive_player_ids,
            'status': player.get('status', 'unknown')
        })
    
    # Identify expected starters (top-rated player per position)
    position_groups = {}
    for player in all_players_with_ratings:
        pos = player['position']
        if pos not in position_groups:
            position_groups[pos] = []
        position_groups[pos].append(player)
    
    # Get expected starter for each position (highest rated)
    expected_starters = []
    for pos, players_at_pos in position_groups.items():
        if len(players_at_pos) > 0:
            # Sort by rating descending
            players_at_pos.sort(key=lambda p: p['rating'], reverse=True)
            expected_starters.append(players_at_pos[0])  # Top player = starter
    
    # Calculate injury impact
    total_injury_score = 0
    inactive_starters = []
    key_positions_out = {
        'qb1_active': True,
        'rb1_active': True,
        'wr1_active': True,
        'te1_active': True,
        'lt_active': True,
        'edge1_active': True,
        'cb1_active': True,
        's1_active': True
    }
    
    for starter in expected_starters:
        if not starter['is_active']:
            # Starter is OUT
            inactive_starters.append(starter)
            starter_rating = starter['rating']
            
            # Find replacement (next highest rated active player at position)
            replacement = _find_replacement(
                starter['position'],
                all_players_with_ratings,
                inactive_player_ids
            )
            
            if replacement:
                # Net impact = starter rating - replacement rating
                impact = starter_rating - replacement['rating']
            else:
                # No replacement - full starter rating as impact
                impact = starter_rating
            
            total_injury_score += impact
            
            # Track key position status
            pos = starter['position']
            if pos == 'QB':
                key_positions_out['qb1_active'] = False
            elif pos == 'RB':
                key_positions_out['rb1_active'] = False
            elif pos == 'WR':
                key_positions_out['wr1_active'] = False
            elif pos == 'TE':
                key_positions_out['te1_active'] = False
            elif pos == 'LT':
                key_positions_out['lt_active'] = False
            elif pos == 'EDGE':
                key_positions_out['edge1_active'] = False
            elif pos == 'CB':
                key_positions_out['cb1_active'] = False
            elif pos == 'S':
                key_positions_out['s1_active'] = False
    
    # Calculate tier breakdown of inactive starters
    tier_breakdown = {
        'elite_out': 0,      # 90+ rating
        'high_out': 0,       # 80-89
        'medium_out': 0,     # 70-79
        'depth_out': 0       # <70
    }
    
    for player in inactive_starters:
        rating = player['rating']
        if rating >= 90:
            tier_breakdown['elite_out'] += 1
        elif rating >= 80:
            tier_breakdown['high_out'] += 1
        elif rating >= 70:
            tier_breakdown['medium_out'] += 1
        else:
            tier_breakdown['depth_out'] += 1
    
    return {
        'team_id': team_abbr,
        'total_injury_score': round(total_injury_score, 2),
        'inactive_starter_count': len(inactive_starters),
        'inactive_starters': [
            {
                'name': p['player_name'],
                'position': p['position'],
                'rating': p['rating'],
                'status': p['status']
            } 
            for p in inactive_starters
        ],
        **tier_breakdown,
        **key_positions_out
    }
