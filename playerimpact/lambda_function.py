"""
Player Impact Lambda Handler - Supabase Version
Calculate player impact for a game using ACTIVE rosters from Sportradar + Madden ratings from Supabase
"""

import json
import os
import logging
import pg8000
import ssl
from typing import Dict, Any, List, Tuple, Optional

# Import local modules
from PlayerWeightAssigner import PlayerWeightAssigner
from SportradarClient import SportradarClient
from PositionMapper import PositionMapper

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global cache for warm starts
_db_conn = None
_weight_assigner = None
_sportradar_client = None
_position_mapper = None
_cached_ratings = {}  # Cache ratings by season


def lambda_handler(event, context):
    """
    AWS Lambda handler for player impact calculation using ACTIVE rosters
    
    Event format:
    {
        "game_id": "abc-123-def-456",  # Sportradar game UUID
        "season": 2024
    }
    
    Returns:
    {
        "game_id": "abc-123-def-456",
        "away_team": "KC",
        "home_team": "SF",
        "away_impact": 85.5,
        "home_impact": 82.3,
        "differential": 3.2,
        "advantage": "away",
        "away_active_players": [...],
        "home_active_players": [...]
    }
    """
    global _weight_assigner, _sportradar_client, _position_mapper
    
    try:
        # Initialize on cold start
        if _weight_assigner is None:
            _weight_assigner = PlayerWeightAssigner()
            _sportradar_client = SportradarClient()
            _position_mapper = PositionMapper()
            logger.info("Cold start - Initialized components")
        else:
            logger.info("Warm start - Using cached instances")
        
        # Parse event
        game_id = event.get('game_id')
        season = event.get('season', 2024)
        
        if not game_id:
            raise KeyError("game_id is required")
        
        logger.info(f"Calculating impact for game: {game_id} (Season {season})")
        
        # Fetch game statistics from Sportradar (shows who actually played!)
        logger.info(f"Fetching game statistics from Sportradar for game {game_id}")
        game_stats = _sportradar_client.get_game_statistics(game_id)
        
        # Fetch game roster (shows who was active/inactive for the game)
        logger.info(f"Fetching game roster from Sportradar for game {game_id}")
        game_roster = _sportradar_client.get_game_roster(game_id)
        
        # Extract teams from statistics
        home_team_stats = game_stats.get('statistics', {}).get('home', {})
        away_team_stats = game_stats.get('statistics', {}).get('away', {})
        
        # Extract teams from roster
        home_team_roster = game_roster.get('home', {})
        away_team_roster = game_roster.get('away', {})
        
        home_abbr = home_team_stats.get('market', 'UNK')[:3].upper() if 'market' in home_team_stats else 'HOME'
        away_abbr = away_team_stats.get('market', 'UNK')[:3].upper() if 'market' in away_team_stats else 'AWAY'
        
        # Try to get alias from summary if available
        if 'summary' in game_stats:
            home_abbr = game_stats['summary'].get('home', {}).get('alias', home_abbr).upper()
            away_abbr = game_stats['summary'].get('away', {}).get('alias', away_abbr).upper()
        
        logger.info(f"Game: {away_abbr} @ {home_abbr}")
        
        # Calculate impact for both teams using players who ACTUALLY PLAYED
        away_impact, away_players = _calculate_team_impact_from_statistics(
            away_team_stats,
            season,
            _position_mapper,
            _weight_assigner,
            away_abbr
        )
        
        home_impact, home_players = _calculate_team_impact_from_statistics(
            home_team_stats,
            season,
            _position_mapper,
            _weight_assigner,
            home_abbr
        )
        
        differential = away_impact - home_impact
        advantage = "away" if differential > 0 else "home" if differential < 0 else "neutral"
        
        # Calculate injury impact for both teams (compare roster vs statistics)
        away_injury = _calculate_injury_impact_dual_api(away_team_roster, away_team_stats, away_abbr, season, _position_mapper)
        home_injury = _calculate_injury_impact_dual_api(home_team_roster, home_team_stats, home_abbr, season, _position_mapper)
        
        logger.info(f"✓ Impact calculated: {away_abbr}={away_impact:.2f}, {home_abbr}={home_impact:.2f}, diff={differential:.2f}")
        logger.info(f"✓ Injury impact: {away_abbr}={away_injury['total_injury_score']:.2f}, {home_abbr}={home_injury['total_injury_score']:.2f}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'game_id': game_id,
                'season': season,
                'away_team': away_abbr,
                'home_team': home_abbr,
                'away_impact': round(away_impact, 2),
                'home_impact': round(home_impact, 2),
                'differential': round(differential, 2),
                'advantage': advantage,
                'away_injury_impact': away_injury,
                'home_injury_impact': home_injury,
                'away_active_players': away_players[:20],  # Top 20 for response size
                'home_active_players': home_players[:20]
            })
        }
    
    except KeyError as e:
        logger.error(f"Missing required field: {e}")
        return {
            'statusCode': 400,
            'body': json.dumps({
                'success': False,
                'error': f'Missing required field: {e}'
            })
        }
    
    except Exception as e:
        logger.error(f"Error calculating player impact: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }


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


def _calculate_team_impact_from_roster(
    team_data: Dict[str, Any],
    season: int,
    position_mapper: PositionMapper,
    weight_assigner: PlayerWeightAssigner,
    team_abbr: str
) -> Tuple[float, List[Dict[str, Any]]]:
    """
    Calculate team impact score from Sportradar roster data + Madden ratings from Supabase
    """
    players = team_data.get('players', [])
    
    if len(players) == 0:
        logger.warning(f"No players found for team {team_abbr}")
        return 0.0, []
    
    logger.info(f"Processing {len(players)} total players for {team_abbr}")
    
    # DEBUG: Log sample player to see actual field values
    if len(players) > 0:
        sample = players[0]
        logger.info(f"Sample player for {team_abbr}: {sample.get('name')} - in_game_status={sample.get('in_game_status')}, status={sample.get('status')}")
    
    # Filter ACTIVE players only (using in_game_status field)
    active_players = [p for p in players if p.get('in_game_status') == 'active']
    logger.info(f"Found {len(active_players)} ACTIVE players (in_game_status='active') for {team_abbr}")
    
    if len(active_players) == 0:
        logger.warning(f"No active players found for team {team_abbr}")
        return 0.0, []
    
    # Build list of players with Madden ratings and mapped positions
    players_with_data = []
    
    for player in active_players:
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
    
    logger.info(f"Matched {len(players_with_data)} active players with data for {team_abbr}")
    
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
    
    logger.info(f"Total impact for {team_abbr}: {total_impact:.2f} ({len(weighted_players)} active players)")
    
    # Sort players by impact (highest first)
    player_details.sort(key=lambda x: x['impact'], reverse=True)
    
    return total_impact, player_details


def _normalize_player_name(name):
    """
    Normalize player name for better matching (matches ETL normalization)
    
    Examples:
        "A.J. Brown" -> "aj brown"
        "Patrick Mahomes II" -> "patrick mahomes"
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
    
    # Remove periods (A.J. -> AJ)
    normalized = normalized.replace('.', '')
    
    # Replace hyphens with spaces
    normalized = normalized.replace('-', ' ')
    
    # Remove extra whitespace
    normalized = ' '.join(normalized.split())
    
    return normalized.strip()


def _get_madden_rating_from_supabase(player_name: str, team: str, season: int) -> tuple:
    """
    Look up player's Madden rating from Supabase player_ratings table
    Uses multiple fallback strategies for better matching
    
    Returns:
        tuple: (rating: int, found: bool)
    """
    
    # Check cache first
    cache_key = f"{season}-{team}-{player_name}"
    global _cached_ratings
    
    if cache_key in _cached_ratings:
        return _cached_ratings[cache_key]
    
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # STRATEGY 1: Exact match (name + team + season)
        query = """
            SELECT overall_rating 
            FROM player_ratings 
            WHERE player_name = %s 
            AND team = %s 
            AND season = %s
            LIMIT 1
        """
        
        cursor.execute(query, (player_name, team, season))
        result = cursor.fetchone()
        
        if result and result[0]:
            rating = int(result[0])
            cursor.close()
            _cached_ratings[cache_key] = (rating, True)
            return (rating, True)
        
        # STRATEGY 2: Normalized name match (handles A.J. vs AJ, Jr. vs Jr, etc.)
        normalized_name = _normalize_player_name(player_name)
        if normalized_name:
            query = """
                SELECT overall_rating 
                FROM player_ratings 
                WHERE normalized_name = %s 
                AND team = %s 
                AND season = %s
                LIMIT 1
            """
            
            cursor.execute(query, (normalized_name, team, season))
            result = cursor.fetchone()
            
            if result and result[0]:
                rating = int(result[0])
                cursor.close()
                logger.debug(f"Found via normalized name: {player_name} -> {normalized_name} = {rating}")
                _cached_ratings[cache_key] = (rating, True)
                return (rating, True)
        
        # STRATEGY 3: Name-only match (ignore team - useful for traded players or team abbr mismatches)
        query = """
            SELECT overall_rating, team
            FROM player_ratings 
            WHERE normalized_name = %s 
            AND season = %s
            LIMIT 1
        """
        
        cursor.execute(query, (normalized_name, season))
        result = cursor.fetchone()
        
        if result and result[0]:
            rating = int(result[0])
            matched_team = result[1]
            cursor.close()
            logger.debug(f"Found via name-only: {player_name} ({team} -> {matched_team}) = {rating}")
            _cached_ratings[cache_key] = (rating, True)
            return (rating, True)
        
        cursor.close()
        
        # NOT FOUND - return default
        logger.debug(f"Player not found: {player_name} ({team}, {season}) [normalized: {normalized_name}]")
        _cached_ratings[cache_key] = (70, False)
        return (70, False)
    
    except Exception as e:
        logger.warning(f"Error querying Supabase for {player_name}: {str(e)}")
        return (70, False)


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


def _find_replacement(position: str, all_players: List[Dict], inactive_player_ids: set) -> Dict:
    """Find the backup who replaced an injured starter"""
    
    # Get active players at this position (not in inactive set)
    active_at_position = [
        p for p in all_players 
        if p['position'] == position 
        and p['player_id'] not in inactive_player_ids
        and p['is_active']
    ]
    
    # Sort by rating descending
    active_at_position.sort(key=lambda p: p['rating'], reverse=True)
    
    # Return next best (should be index 1, but we'll take index 0 of remaining)
    if len(active_at_position) > 1:
        return active_at_position[1]  # Second best = replacement
    elif len(active_at_position) == 1:
        return active_at_position[0]  # Only one active
    
    return None


def _empty_injury_impact(team_abbr: str) -> Dict:
    """Return empty injury impact structure"""
    return {
        'team_id': team_abbr,
        'total_injury_score': 0.0,
        'inactive_starter_count': 0,
        'inactive_starters': [],
        'elite_out': 0,
        'high_out': 0,
        'medium_out': 0,
        'depth_out': 0,
        'qb1_active': True,
        'rb1_active': True,
        'wr1_active': True,
        'te1_active': True,
        'lt_active': True,
        'edge1_active': True,
        'cb1_active': True,
        's1_active': True
    }


def _get_db_connection():
    """Get or create Supabase database connection (reuse across invocations)"""
    global _db_conn
    
    # Reuse existing connection if available
    if _db_conn is not None:
        try:
            # Test if connection is still alive
            cursor = _db_conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return _db_conn
        except:
            # Connection is dead, create new one
            logger.info("Database connection dead, reconnecting...")
            _db_conn = None
    
    # Create new connection
    db_host = os.environ.get('SUPABASE_DB_HOST')
    db_password = os.environ.get('SUPABASE_DB_PASSWORD')
    db_name = os.environ.get('SUPABASE_DB_NAME', 'postgres')
    db_user = os.environ.get('SUPABASE_DB_USER', 'postgres')
    db_port = int(os.environ.get('SUPABASE_DB_PORT', 5432))
    
    if not db_host or not db_password:
        raise ValueError("SUPABASE_DB_HOST and SUPABASE_DB_PASSWORD must be set")
    
    _db_conn = pg8000.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password,
        port=db_port,
        timeout=30,
        ssl_context=True
    )
    
    logger.info("Connected to Supabase")
    return _db_conn


if __name__ == "__main__":
    # Test locally
    test_event = {
        "game_id": "b00ae1c5-f3f4-41bb-990f-231d1d8751e5",
        "season": 2024
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(json.loads(result['body']), indent=2))

