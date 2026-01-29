"""
Player Impact Lambda Handler - Supabase Version
Calculate player impact for a game using ACTIVE rosters from Sportradar + Madden ratings from Supabase
"""

import json
import os
import logging
import pg8000
import ssl
from typing import Dict, Any, List, Tuple

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
        
        # Fetch game roster from Sportradar
        logger.info(f"Fetching active roster from Sportradar for game {game_id}")
        game_roster = _sportradar_client.get_game_roster(game_id)
        
        # Extract teams
        home_team_data = game_roster.get('home', {})
        away_team_data = game_roster.get('away', {})
        
        home_abbr = home_team_data.get('alias', 'UNK').upper()
        away_abbr = away_team_data.get('alias', 'UNK').upper()
        
        logger.info(f"Game: {away_abbr} @ {home_abbr}")
        
        # Calculate impact for both teams using ACTIVE players
        away_impact, away_players = _calculate_team_impact_from_roster(
            away_team_data,
            season,
            _position_mapper,
            _weight_assigner,
            away_abbr
        )
        
        home_impact, home_players = _calculate_team_impact_from_roster(
            home_team_data,
            season,
            _position_mapper,
            _weight_assigner,
            home_abbr
        )
        
        differential = away_impact - home_impact
        advantage = "away" if differential > 0 else "home" if differential < 0 else "neutral"
        
        logger.info(f"✓ Impact calculated: {away_abbr}={away_impact:.2f}, {home_abbr}={home_impact:.2f}, diff={differential:.2f}")
        
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
        madden_rating = _get_madden_rating_from_supabase(player_name, team_abbr, season)
        
        # Create player dict for weight assignment
        player_dict = {
            'player_id': player.get('id'),
            'player_name': player_name,
            'raw_position': raw_position,
            'position_key': standard_position,
            'depth_order': 1,
            'overallrating': madden_rating,
            'madden_found': madden_rating > 70
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


def _get_madden_rating_from_supabase(player_name: str, team: str, season: int) -> int:
    """
    Look up player's Madden rating from Supabase player_ratings table
    
    Returns:
        int: Madden overall rating (default 70 if not found)
    """
    
    # Check cache first (cache key: "season-team-player_name")
    cache_key = f"{season}-{team}-{player_name}"
    global _cached_ratings
    
    if cache_key in _cached_ratings:
        return _cached_ratings[cache_key]
    
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # Query by player_name, team, and season
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
        cursor.close()
        
        if result and result[0]:
            rating = int(result[0])
            _cached_ratings[cache_key] = rating
            return rating
        else:
            # Not found - return default
            logger.debug(f"Player not found in Supabase: {player_name} ({team}, {season})")
            _cached_ratings[cache_key] = 70
            return 70
    
    except Exception as e:
        logger.warning(f"Error querying Supabase for {player_name}: {str(e)}")
        return 70


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

