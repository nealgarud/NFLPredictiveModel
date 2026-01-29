"""
Madden ETL Lambda
Processes Madden CSV files from S3 and stores cleaned data in Supabase
"""

import json
import os
import logging
import boto3
import pandas as pd
import pg8000
import ssl

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global S3 client
s3_client = None


def lambda_handler(event, context):
    """
    Process Madden CSV files and store in Supabase
    
    Event format:
    {
        "seasons": [2022, 2023, 2024]  # Optional, defaults to all
    }
    """
    global s3_client
    
    try:
        # Initialize S3 client
        if s3_client is None:
            s3_client = boto3.client('s3')
            logger.info("S3 client initialized")
        
        # Get configuration from environment
        bucket_name = os.environ.get('PLAYER_DATA_BUCKET', 'player-data-nfl-predictive-model')
        seasons = event.get('seasons', [2022, 2023, 2024])
        
        logger.info(f"Processing seasons: {seasons} from bucket: {bucket_name}")
        
        # Process each season
        results = {}
        for season in seasons:
            logger.info(f"Processing season {season}...")
            result = process_season(season, bucket_name)
            results[season] = result
            logger.info(f"Season {season}: {result}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'message': 'ETL completed successfully',
                'results': results
            })
        }
    
    except Exception as e:
        logger.error(f"ETL failed: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }


def process_season(season, bucket_name):
    """Process a single season CSV and store in Supabase"""
    
    # Read CSV from S3
    csv_key = f"{season}.csv"
    logger.info(f"Reading s3://{bucket_name}/{csv_key}")
    
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=csv_key)
        csv_content = response['Body'].read().decode('utf-8')
        
        # Parse CSV
        from io import StringIO
        df = pd.read_csv(StringIO(csv_content), low_memory=False)
        
        logger.info(f"Loaded {len(df)} rows from {csv_key}")
        logger.info(f"Columns: {list(df.columns)[:10]}...")  # First 10 columns
        
        # Clean and transform data
        cleaned_data = clean_madden_data(df, season)
        
        logger.info(f"Cleaned data: {len(cleaned_data)} players")
        
        # Store in Supabase
        stored_count = store_in_supabase(cleaned_data, season)
        
        return {
            'rows_read': len(df),
            'rows_cleaned': len(cleaned_data),
            'rows_stored': stored_count
        }
    
    except Exception as e:
        logger.error(f"Error processing season {season}: {str(e)}")
        raise


def normalize_player_name(name):
    """
    Normalize player name for better matching
    
    Examples:
        "A.J. Brown" -> "aj brown"
        "Patrick Mahomes II" -> "patrick mahomes"
        "JuJu Smith-Schuster" -> "juju smith schuster"
    """
    if not name or name == 'nan':
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
    
    # Replace hyphens with spaces (Smith-Schuster -> Smith Schuster)
    normalized = normalized.replace('-', ' ')
    
    # Remove extra whitespace
    normalized = ' '.join(normalized.split())
    
    return normalized.strip()


def clean_madden_data(df, season):
    """
    Extract and clean relevant columns from Madden CSV
    
    Expected columns (by index):
    - [11]: unique_id (e.g., ZACHWILSON_19990803)
    - [2]: player_name (e.g., Zach Wilson)
    - [6]: position (e.g., QB)
    - [3]: team (e.g., DEN)
    - Need to find: overallrating
    """
    
    cleaned_players = []
    
    # Log all column names for debugging
    logger.info(f"CSV Columns ({len(df.columns)} total): {list(df.columns)[:20]}")  # First 20
    
    # Try to identify the overallrating column
    rating_col = None
    rating_col_index = None
    
    # Method 1: Search by name (case-insensitive)
    for idx, col in enumerate(df.columns):
        col_lower = str(col).lower()
        if 'overallrating' in col_lower or (col_lower == 'overall'):
            rating_col = col
            rating_col_index = idx
            logger.info(f"Found rating column by name: '{col}' at index {idx}")
            break
    
    # Log ALL column indices and names for debugging
    logger.info(f"Column index mapping: {list(enumerate(df.columns))[:20]}")
    
    # Check what's at index 13 specifically
    logger.info(f"Column at index 13: '{df.columns[13] if len(df.columns) > 13 else 'N/A'}'")
    logger.info(f"Sample value at index 13: {df.iloc[0].values[13] if len(df.iloc[0].values) > 13 else 'N/A'}")
    
    # Method 2: If not found, try index 13 directly
    if rating_col is None:
        logger.warning("Could not find 'overallrating' column by name, will use index 13")
        logger.info(f"Sample row values: {df.iloc[0].values[:20]}")  # First 20 values
    
    # Get column names or indices
    columns = list(df.columns)
    skipped_count = 0
    invalid_rating_count = 0
    debug_sample_count = 0  # Log first 3 players in detail
    
    for idx, row in df.iterrows():
        try:
            # Extract data by column index (more reliable than names)
            values = row.values
            
            if len(values) < 14:
                skipped_count += 1
                continue  # Skip incomplete rows
            
            player_id = str(values[11]).strip() if pd.notna(values[11]) else None
            player_name = str(values[2]).strip() if pd.notna(values[2]) else None
            position = str(values[6]).strip() if pd.notna(values[6]) else None
            team = str(values[3]).strip().upper() if pd.notna(values[3]) else None
            
            # Get rating - ALWAYS try index 13 first (most reliable)
            overall_rating = None
            rating_source = None
            
            # Method 1: Try column index 13 (known position in Madden CSVs)
            if len(values) > 13:
                overall_rating = values[13]
                rating_source = f"index_13"
            # Method 2: Fallback to column name
            elif rating_col and rating_col in df.columns:
                overall_rating = row[rating_col]
                rating_source = f"column_{rating_col}"
            
            # Debug logging for first 3 players
            if debug_sample_count < 3 and player_name:
                logger.info(f"DEBUG Player {debug_sample_count + 1}: {player_name} ({team})")
                logger.info(f"  - Raw rating value: {overall_rating} from {rating_source}")
                logger.info(f"  - Value at index 13: {values[13] if len(values) > 13 else 'N/A'}")
                if rating_col:
                    logger.info(f"  - Value from '{rating_col}' column: {row[rating_col]}")
                debug_sample_count += 1
                
            # Convert to int
            if pd.notna(overall_rating):
                try:
                    # Convert to float first, then int
                    rating_float = float(overall_rating)
                    # Check if it's a valid number (not NaN)
                    if not pd.isna(rating_float):
                        overall_rating = int(rating_float)
                    else:
                        overall_rating = None
                except (ValueError, TypeError):
                    overall_rating = None
            else:
                overall_rating = None
            
            # Skip if missing critical data
            if not player_id or not player_name or player_id == 'nan':
                skipped_count += 1
                continue
            
            # Validate rating range
            if overall_rating is None or overall_rating == 0 or overall_rating < 40 or overall_rating > 99:
                invalid_rating_count += 1
                overall_rating = 70
            
            # Normalize player name for matching
            normalized_name = normalize_player_name(player_name)
            
            cleaned_players.append({
                'player_id': player_id,
                'player_name': player_name,
                'normalized_name': normalized_name,  # NEW: For better matching
                'position': position if position and position != 'nan' else 'UNKNOWN',
                'team': team if team and team != 'nan' else 'FA',
                'overall_rating': overall_rating,
                'season': season
            })
        
        except Exception as e:
            logger.debug(f"Error processing row {idx}: {str(e)}")
            skipped_count += 1
            continue
    
    logger.info(f"Processed {len(df)} rows: {len(cleaned_players)} valid, {skipped_count} skipped, {invalid_rating_count} defaulted to 70")
    
    # Log sample of cleaned data
    if len(cleaned_players) > 0:
        sample = cleaned_players[0]
        logger.info(f"Sample cleaned player: {sample['player_name']} ({sample['team']}, {sample['position']}) = {sample['overall_rating']}")
    
    return cleaned_players


def store_in_supabase(players_data, season):
    """Store cleaned player data in Supabase"""
    
    if len(players_data) == 0:
        logger.warning(f"No data to store for season {season}")
        return 0
    
    # Connect to Supabase
    conn = get_supabase_connection()
    cursor = conn.cursor()
    
    try:
        # Create table if it doesn't exist and add normalized_name column
        create_table_if_not_exists(cursor)
        conn.commit()  # Commit table structure changes
        logger.info("Table structure updated")
        
        # Delete existing data for this season (for idempotency)
        cursor.execute(f"DELETE FROM player_ratings WHERE season = {season}")
        conn.commit()
        logger.info(f"Cleared existing data for season {season}")
        
        # Batch insert
        insert_query = """
            INSERT INTO player_ratings 
            (player_id, player_name, normalized_name, position, team, overall_rating, season)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (player_id, season) DO UPDATE SET
                player_name = EXCLUDED.player_name,
                normalized_name = EXCLUDED.normalized_name,
                position = EXCLUDED.position,
                team = EXCLUDED.team,
                overall_rating = EXCLUDED.overall_rating,
                updated_at = NOW()
        """
        
        # Insert in batches
        batch_size = 100
        total_inserted = 0
        
        for i in range(0, len(players_data), batch_size):
            batch = players_data[i:i + batch_size]
            for player in batch:
                try:
                    # Validate rating is a proper integer
                    rating = player['overall_rating']
                    if not isinstance(rating, int) or rating < 40 or rating > 99:
                        rating = 70
                    
                    cursor.execute(insert_query, (
                        player['player_id'],
                        player['player_name'],
                        player['normalized_name'],
                        player['position'],
                        player['team'],
                        rating,
                        player['season']
                    ))
                    total_inserted += 1
                except Exception as e:
                    logger.warning(f"Failed to insert player {player.get('player_name')}: {str(e)}")
                    continue
            
            # Commit each batch
            conn.commit()
            if (i + batch_size) % 500 == 0:
                logger.info(f"Inserted {total_inserted} players so far...")
        
        logger.info(f"Inserted {total_inserted} players for season {season}")
        
        return total_inserted
    
    finally:
        cursor.close()
        conn.close()


def get_supabase_connection():
    """Create Supabase database connection"""
    
    db_host = os.environ.get('SUPABASE_DB_HOST')
    db_password = os.environ.get('SUPABASE_DB_PASSWORD')
    db_name = os.environ.get('SUPABASE_DB_NAME', 'postgres')
    db_user = os.environ.get('SUPABASE_DB_USER', 'postgres')
    db_port = int(os.environ.get('SUPABASE_DB_PORT', 5432))
    
    if not db_host or not db_password:
        raise ValueError("SUPABASE_DB_HOST and SUPABASE_DB_PASSWORD must be set")
    
    # Connect using standard DBAPI
    conn = pg8000.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password,
        port=db_port,
        timeout=30,
        ssl_context=True  # Enable SSL
    )
    
    logger.info("Connected to Supabase")
    return conn


def create_table_if_not_exists(cursor):
    """Create player_ratings table if it doesn't exist and add normalized_name column"""
    
    # Step 1: Create base table if it doesn't exist
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS player_ratings (
        id SERIAL PRIMARY KEY,
        player_id VARCHAR(255) NOT NULL,
        player_name VARCHAR(255),
        position VARCHAR(50),
        team VARCHAR(10),
        overall_rating INTEGER,
        season INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(player_id, season)
    );
    """
    
    cursor.execute(create_table_sql)
    logger.info("Ensured player_ratings table exists")
    
    # Step 2: Add normalized_name column if it doesn't exist (for existing tables)
    try:
        add_column_sql = """
        ALTER TABLE player_ratings 
        ADD COLUMN IF NOT EXISTS normalized_name VARCHAR(255);
        """
        cursor.execute(add_column_sql)
        logger.info("Added normalized_name column (if not exists)")
    except Exception as e:
        logger.warning(f"Could not add normalized_name column (may already exist): {str(e)}")
    
    # Step 3: Create indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_player_id ON player_ratings(player_id)",
        "CREATE INDEX IF NOT EXISTS idx_season ON player_ratings(season)",
        "CREATE INDEX IF NOT EXISTS idx_player_season ON player_ratings(player_id, season)",
        "CREATE INDEX IF NOT EXISTS idx_normalized_name ON player_ratings(normalized_name, season)"
    ]
    
    for index_sql in indexes:
        try:
            cursor.execute(index_sql)
        except Exception as e:
            logger.warning(f"Could not create index: {str(e)}")
    
    logger.info("Created all indexes")


if __name__ == "__main__":
    # Test locally
    test_event = {
        "seasons": [2024]
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(json.loads(result['body']), indent=2))

