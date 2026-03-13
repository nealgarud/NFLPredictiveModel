"""
GameIDMapper Lambda
Maps internal game IDs to Sportradar UUIDs for entire NFL seasons.

Input: {"season": 2024} or {"seasons": [2022, 2023, 2024]}
"""

import requests
import json
import logging
import os
import time
from datetime import datetime
from DatabaseUtils import DatabaseUtils

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuration
SPORTRADAR_API_KEY = os.environ.get('SPORTRADAR_API_KEY')
SPORTRADAR_BASE_URL = "https://api.sportradar.com/nfl/official/trial/v7/en"


def lambda_handler(event, context):
    """
    Main entry point for GameIDMapper Lambda.
    Maps internal game IDs to Sportradar UUIDs.
    
    Input:
        {"season": 2024}  OR  {"seasons": [2022, 2023, 2024]}
    
    Output:
        {
            "statusCode": 200,
            "body": {
                "success": true,
                "mappings_created": 272,
                "seasons_processed": [2024]
            }
        }
    """
    try:
        # Log incoming request
        logger.info(f"GameIDMapper invoked with event: {json.dumps(event)}")
        
        # Extract input parameters
        season = event.get('season')
        seasons = event.get('seasons')
        
        # Validate: Must provide at least one
        if not season and not seasons:
            logger.warning("No season parameter provided")
            return error_response(400, "Must provide 'season' or 'seasons' parameter")
        
        # Normalize to list
        seasons_to_process = [season] if season else seasons
        logger.info(f"Will process {len(seasons_to_process)} seasons: {seasons_to_process}")
        
        # Process each season with rate limiting
        total_mappings = 0
        for idx, s in enumerate(seasons_to_process):
            logger.info(f"Starting processing for season {s} ({idx + 1}/{len(seasons_to_process)})")
            
            # Main work happens here
            mappings_count = process_season(s)
            total_mappings += mappings_count
            
            logger.info(f"Completed season {s}: {mappings_count} mappings created")
            
            # Rate limiting: Wait between seasons (except after last)
            if idx < len(seasons_to_process) - 1:
                logger.info("Waiting 2 seconds before next season...")
                time.sleep(2)
        
        # Return success
        logger.info(f"All seasons processed successfully. Total mappings: {total_mappings}")
        return success_response({
            "mappings_created": total_mappings,
            "seasons_processed": seasons_to_process,
            "message": f"Successfully created {total_mappings} game ID mappings"
        })
        
    except Exception as e:
        # Log full error with stack trace
        logger.error(f"Lambda execution failed: {str(e)}", exc_info=True)
        return error_response(500, f"Internal error: {str(e)}")


def process_season(season):
    """
    Process a single season and create game ID mappings.
    
    Flow:
        1. Fetch schedule from Sportradar API
        2. Parse response and extract mappings
        3. Write mappings to database
    
    Args:
        season (int): NFL season year (e.g., 2024)
    
    Returns:
        int: Number of mappings created
    
    Raises:
        Exception: If any step fails (API call, parsing, or database write)
    """
    logger.info(f"=== Starting process_season({season}) ===")
    
    try:
        # STEP 1: Fetch schedule from Sportradar API
        logger.info(f"Step 1: Fetching schedule from Sportradar for {season}...")
        schedule_data = fetch_season_schedule(season)
        logger.info(f"Successfully fetched schedule data")
        
        # STEP 2: Extract mappings from API response
        logger.info(f"Step 2: Extracting game mappings from schedule...")
        mappings = extract_mappings(schedule_data, season)
        logger.info(f"Extracted {len(mappings)} game mappings")
        
        # Validation: Make sure we got some games
        if not mappings or len(mappings) == 0:
            logger.warning(f"No games found for season {season}")
            return 0
        
        # STEP 3: Write mappings to database
        logger.info(f"Step 3: Writing {len(mappings)} mappings to database...")
        insert_mappings(mappings)
        logger.info(f"Successfully wrote {len(mappings)} mappings to database")
        
        logger.info(f"=== Completed process_season({season}): {len(mappings)} mappings ===")
        return len(mappings)
        
    except Exception as e:
        # If anything fails, log and re-raise
        logger.error(f"Failed to process season {season}: {str(e)}", exc_info=True)
        raise  # Re-raise so lambda_handler catches it


def fetch_season_schedule(season):
    """
    Fetch full regular season schedule from Sportradar API.
    
    Args:
        season (int): NFL season year (2024)
    
    Returns:
        dict: Schedule data with weeks and games
    """
    # Validate API key
    if not SPORTRADAR_API_KEY:
        raise Exception("SPORTRADAR_API_KEY environment variable not set")
    
    # Build request
    url = f"{SPORTRADAR_BASE_URL}/games/{season}/REG/schedule.json"
    params = {'api_key': SPORTRADAR_API_KEY}
    headers = {'Accept': 'application/json'}
    
    logger.info(f"Fetching schedule from Sportradar for season {season}")
    
    try:
        # Call API
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Parse JSON
        schedule_data = response.json()
        
        # Validate structure
        if 'weeks' not in schedule_data:
            raise Exception("API response missing 'weeks' field")
        
        logger.info(f"Fetched {len(schedule_data['weeks'])} weeks of data")
        return schedule_data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API error: {e}")
        raise Exception(f"Failed to fetch schedule for season {season}: {str(e)}")


def extract_mappings(schedule_data, season):
    """
    Parse Sportradar schedule and extract game ID mappings.
    
    Args:
        schedule_data (dict): Response from Sportradar API
        season (int): NFL season year (2025)
    
    Returns:
        list: List of mapping dictionaries, e.g.:
            [
                {
                    'game_id': '2025_01_DAL_PHI',
                    'sportradar_id': '56779053-89da-4939-bc22-9669ae1fe05a',
                    'season': 2025,
                    'week': 1,
                    'home_team': 'PHI',
                    'away_team': 'DAL',
                    'game_date': '2025-09-05 00:20:00'
                },
                ...
            ]
    """
    mappings = []
    
    # Loop through weeks
    for week in schedule_data['weeks']:
        week_number = week['sequence']
        
        # Loop through games in this week
        for game in week.get('games', []):
            try:
                # Extract required fields
                sportradar_id = game['id']
                home_alias = game['home']['alias']
                away_alias = game['away']['alias']
                scheduled = game.get('scheduled')
                
                # Build internal game_id
                game_id = f"{season}_{week_number:02d}_{away_alias}_{home_alias}"
                
                # Parse game date
                game_date = parse_game_date(scheduled) if scheduled else None
                
                # Create mapping record
                mapping = {
                    'game_id': game_id,
                    'sportradar_id': sportradar_id,
                    'season': season,
                    'week': week_number,
                    'home_team': home_alias,
                    'away_team': away_alias,
                    'game_date': game_date
                }
                
                mappings.append(mapping)
                logger.debug(f"Extracted: {game_id} → {sportradar_id}")
                
            except KeyError as e:
                logger.warning(f"Skipping game with missing field {e}: {game.get('id', 'unknown')}")
                continue
    
    logger.info(f"Extracted {len(mappings)} game mappings from schedule")
    return mappings


def insert_mappings(mappings):
    """
    Batch insert game ID mappings to database.
    
    Args:
        mappings (list[dict]): List of mapping dictionaries
    
    Returns:
        int: Number of mappings inserted/updated
    """
    if not mappings:
        logger.warning("No mappings to insert")
        return 0

    logger.info(f"Batch inserting {len(mappings)} mappings to database")
    
    db = DatabaseUtils()

    try: 
        # UPSERT Query — skips rows where the sportradar_id is already owned
        # by a different game_id (handles JAC/JAX duplicate legacy data).
        query = """
            INSERT INTO game_id_mapping
                (game_id, sportradar_id, season, week, home_team, away_team, game_date)
            SELECT %s, %s, %s, %s, %s, %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM game_id_mapping
                WHERE sportradar_id = %s
            )
            ON CONFLICT(game_id)
            DO UPDATE SET 
                sportradar_id = EXCLUDED.sportradar_id,
                season = EXCLUDED.season,
                week = EXCLUDED.week,
                home_team = EXCLUDED.home_team,
                away_team = EXCLUDED.away_team,
                game_date = EXCLUDED.game_date,
                updated_at = NOW()
        """
        
        # Prepare batch data — sportradar_id repeated for the WHERE NOT EXISTS check
        batch_data = [
            (
                m['game_id'],
                m['sportradar_id'],
                m['season'],
                m['week'],
                m['home_team'],
                m['away_team'],
                m['game_date'],
                m['sportradar_id'],  # for WHERE NOT EXISTS subquery
            )
            for m in mappings
        ]
        
        # Execute batch insert
        rows_affected = db.execute_batch(query, batch_data)
        logger.info(f"Successfully inserted/updated {rows_affected} mappings")
        return rows_affected
        
    except Exception as e:
        logger.error(f"Failed to insert mappings: {e}", exc_info=True)
        raise
        
    finally:
        db.close()


def parse_game_date(iso_timestamp):
    """
    Parse ISO 8601 timestamp to datetime.
    
    Args:
        iso_timestamp (str): "2025-09-05T00:20:00+00:00"
    
    Returns:
        datetime: Python datetime object
    """
    try:
        # Handle both 'Z' and '+00:00' timezone formats
        timestamp = iso_timestamp.replace('Z', '+00:00')
        return datetime.fromisoformat(timestamp)
    except (ValueError, AttributeError) as e:
        logger.warning(f"Failed to parse date '{iso_timestamp}': {e}")
        return None


def success_response(data):
    """Format successful Lambda response."""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "success": True,
            **data
        })
    }


def error_response(status_code, message):
    """Format error Lambda response."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "success": False,
            "error": message
        })
    }

