"""
Player Impact Lambda Handler - V2
Calculate player impact for a game using ACTIVE rosters from Sportradar + Madden ratings
"""

import json
import os
import logging
import pandas as pd
from typing import Dict, Any, List, Tuple

# Import local modules
from S3DataLoader import S3DataLoader
from PlayerWeightAssigner import PlayerWeightAssigner
from SportradarClient import SportradarClient
from PositionMapper import PositionMapper

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global cache for warm starts
_s3_loader = None
_weight_assigner = None
_sportradar_client = None
_position_mapper = None
_cached_madden_ratings = {}


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
    global _s3_loader, _weight_assigner, _sportradar_client, _position_mapper, _cached_madden_ratings
    
    try:
        # Initialize on cold start
        if _s3_loader is None:
            bucket_name = os.environ.get('PLAYER_DATA_BUCKET', 'player-data-nfl-predictive-model')
            _s3_loader = S3DataLoader(bucket_name=bucket_name)
            _weight_assigner = PlayerWeightAssigner()
            _sportradar_client = SportradarClient()
            _position_mapper = PositionMapper()
            logger.info(f"Cold start - Initialized with bucket: {bucket_name}")
        else:
            logger.info("Warm start - Using cached instances")
        
        # Parse event
        game_id = event.get('game_id')
        season = event.get('season', 2024)
        
        if not game_id:
            raise KeyError("game_id is required")
        
        logger.info(f"Calculating impact for game: {game_id} (Season {season})")
        
        # Load Madden ratings (cached per season)
        if season not in _cached_madden_ratings:
            logger.info(f"Loading Madden ratings for season {season}")
            madden_data = _s3_loader.load_madden_ratings(season)
            _cached_madden_ratings[season] = madden_data
        else:
            logger.info(f"Using cached Madden ratings for season {season}")
            madden_data = _cached_madden_ratings[season]
        
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
            madden_data,
            _position_mapper,
            _weight_assigner,
            away_abbr
        )
        
        home_impact, home_players = _calculate_team_impact_from_roster(
            home_team_data,
            madden_data,
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
                'away_active_players': away_players,
                'home_active_players': home_players
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
    madden_data: pd.DataFrame,
    position_mapper: PositionMapper,
    weight_assigner: PlayerWeightAssigner,
    team_abbr: str
) -> Tuple[float, List[Dict[str, Any]]]:
    """
    Calculate team impact score from Sportradar roster data + Madden ratings
    
    Args:
        team_data: Team data from Sportradar game roster
        madden_data: DataFrame with Madden ratings
        position_mapper: PositionMapper instance
        weight_assigner: PlayerWeightAssigner instance
        team_abbr: Team abbreviation (e.g., 'KC', 'SF')
    
    Returns:
        Tuple of (total_impact_score, list_of_active_players_with_details)
    """
    players = team_data.get('players', [])
    
    if len(players) == 0:
        logger.warning(f"No players found for team {team_abbr}")
        return 0.0, []
    
    logger.info(f"Processing {len(players)} players for {team_abbr}")
    
    # Filter ACTIVE players only
    active_players = [p for p in players if p.get('playing_status') == 'ACT']
    logger.info(f"Found {len(active_players)} ACTIVE players for {team_abbr}")
    
    if len(active_players) == 0:
        logger.warning(f"No active players found for team {team_abbr}")
        return 0.0, []
    
    # Build list of players with Madden ratings and mapped positions
    players_with_data = []
    
    for player in active_players:
        player_id = player.get('id')
        player_name = player.get('name', 'Unknown')
        raw_position = player.get('position', 'Unknown')
        
        # Standardize position using PositionMapper
        standard_position = position_mapper.standardize_position(raw_position)
        
        # Look up Madden rating
        madden_rating = _get_madden_rating(player_id, player_name, madden_data)
        
        # Create player dict for weight assignment
        player_dict = {
            'player_id': player_id,
            'player_name': player_name,
            'raw_position': raw_position,
            'position_key': standard_position,  # This is what PlayerWeightAssigner needs
            'depth_order': 1,  # Simplified - assume all are starters for now
            'overallrating': madden_rating,
            'madden_found': madden_rating > 70  # Flag if we found them in Madden data
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
    
    # Log sample players for debugging
    if len(player_details) > 0:
        logger.info(f"Sample player for {team_abbr}: {player_details[0]}")
    
    logger.info(f"Total impact for {team_abbr}: {total_impact:.2f} ({len(weighted_players)} active players)")
    
    # Sort players by impact (highest first)
    player_details.sort(key=lambda x: x['impact'], reverse=True)
    
    return total_impact, player_details


def _get_madden_rating(player_id: str, player_name: str, madden_data: pd.DataFrame) -> int:
    """
    Look up player's Madden overall rating
    
    Args:
        player_id: Sportradar player ID
        player_name: Player name (for fallback matching)
        madden_data: DataFrame with Madden ratings
    
    Returns:
        int: Madden overall rating (default 70 if not found)
    """
    if madden_data.empty:
        return 70
    
    # Try exact player_id match first
    if 'player_id' in madden_data.columns:
        matches = madden_data[madden_data['player_id'] == player_id]
        if len(matches) > 0:
            return int(matches.iloc[0]['overallrating'])
    
    # Fallback: Try name matching (fuzzy)
    if 'player_name' in madden_data.columns and player_name != 'Unknown':
        name_matches = madden_data[madden_data['player_name'].str.contains(player_name, case=False, na=False)]
        if len(name_matches) > 0:
            logger.debug(f"Matched player by name: {player_name}")
            return int(name_matches.iloc[0]['overallrating'])
    
    # Not found - return default "average" rating
    logger.debug(f"Player not found in Madden data: {player_name} ({player_id})")
    return 70


# For local testing
if __name__ == "__main__":
    test_event = {
        "game_id": "c93e7c59-84e8-4e6c-9a10-8a9fc89d06a9",  # Example game ID
        "season": 2024
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(json.loads(result['body']), indent=2))

