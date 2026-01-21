"""
SupabaseStorage - Store and retrieve player ratings and injury impact data in Supabase

Handles:
- Storing player ratings (Madden + position weights)
- Storing injury impact calculations per game
- Querying historical injury impacts
- Caching player data
"""

import pg8000.native
import os
import logging
import ssl
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class SupabaseStorage:
    """Store NFL player and injury data in Supabase PostgreSQL"""
    
    def __init__(self):
        """Initialize Supabase connection"""
        self.connection = self._create_connection()
        self._ensure_tables_exist()
        logger.info("SupabaseStorage initialized")
    
    def _create_connection(self):
        """Create Supabase database connection using pg8000"""
        try:
            logger.info("Connecting to Supabase...")
            
            # Create SSL context
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connection = pg8000.native.Connection(
                host=os.environ.get('SUPABASE_DB_HOST'),
                database=os.environ.get('SUPABASE_DB_NAME', 'postgres'),
                user=os.environ.get('SUPABASE_DB_USER', 'postgres'),
                password=os.environ.get('SUPABASE_DB_PASSWORD'),
                port=int(os.environ.get('SUPABASE_DB_PORT', 5432)),
                timeout=30,
                ssl_context=ssl_context
            )
            
            logger.info("✓ Connected to Supabase")
            return connection
            
        except Exception as e:
            logger.error(f"✗ Supabase connection failed: {e}")
            raise
    
    def _ensure_tables_exist(self):
        """Create tables if they don't exist"""
        try:
            # Player ratings table
            self.connection.run("""
                CREATE TABLE IF NOT EXISTS player_ratings (
                    player_id VARCHAR(255) PRIMARY KEY,
                    player_name VARCHAR(255),
                    position VARCHAR(50),
                    team VARCHAR(10),
                    madden_rating INTEGER,
                    position_key VARCHAR(50),
                    weight DECIMAL(10, 4),
                    tier INTEGER,
                    season INTEGER,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Create index on player lookups
            self.connection.run("""
                CREATE INDEX IF NOT EXISTS idx_player_ratings_season 
                ON player_ratings(season, position_key);
            """)
            
            # Injury impact table
            self.connection.run("""
                CREATE TABLE IF NOT EXISTS injury_impact (
                    id SERIAL PRIMARY KEY,
                    game_id VARCHAR(255) NOT NULL,
                    team_id VARCHAR(255) NOT NULL,
                    season INTEGER NOT NULL,
                    week INTEGER NOT NULL,
                    season_type VARCHAR(10),
                    total_injury_score DECIMAL(10, 4),
                    replacement_adjusted_score DECIMAL(10, 4),
                    inactive_starter_count INTEGER,
                    tier_1_out INTEGER,
                    tier_2_out INTEGER,
                    tier_3_out INTEGER,
                    tier_4_out INTEGER,
                    tier_5_out INTEGER,
                    qb1_active BOOLEAN,
                    rb1_active BOOLEAN,
                    wr1_active BOOLEAN,
                    edge1_active BOOLEAN,
                    cb1_active BOOLEAN,
                    lt_active BOOLEAN,
                    s1_active BOOLEAN,
                    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(game_id, team_id)
                );
            """)
            
            # Create index for game queries
            self.connection.run("""
                CREATE INDEX IF NOT EXISTS idx_injury_impact_game 
                ON injury_impact(game_id, team_id);
            """)
            
            # Create index for season/week queries
            self.connection.run("""
                CREATE INDEX IF NOT EXISTS idx_injury_impact_season_week 
                ON injury_impact(season, week, season_type);
            """)
            
            # Inactive players table (tracks which players were out)
            self.connection.run("""
                CREATE TABLE IF NOT EXISTS inactive_players (
                    id SERIAL PRIMARY KEY,
                    game_id VARCHAR(255) NOT NULL,
                    team_id VARCHAR(255) NOT NULL,
                    player_id VARCHAR(255) NOT NULL,
                    player_name VARCHAR(255),
                    position_key VARCHAR(50),
                    weight DECIMAL(10, 4),
                    tier INTEGER,
                    replacement_value DECIMAL(10, 4),
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Create index for player tracking
            self.connection.run("""
                CREATE INDEX IF NOT EXISTS idx_inactive_players_game 
                ON inactive_players(game_id, team_id);
            """)
            
            logger.info("✓ Database tables verified/created")
            
        except Exception as e:
            logger.error(f"Error ensuring tables exist: {e}")
            raise
    
    def store_player_rating(self, player_data: Dict[str, Any]) -> bool:
        """
        Store or update a player's rating data
        
        Args:
            player_data: Dict with keys [player_id, player_name, position, team, 
                        madden_rating, position_key, weight, tier, season]
                        
        Returns:
            bool: True if successful
        """
        try:
            # Use upsert (INSERT ... ON CONFLICT UPDATE)
            self.connection.run("""
                INSERT INTO player_ratings 
                (player_id, player_name, position, team, madden_rating, 
                 position_key, weight, tier, season, updated_at)
                VALUES (:player_id, :player_name, :position, :team, :madden_rating,
                        :position_key, :weight, :tier, :season, CURRENT_TIMESTAMP)
                ON CONFLICT (player_id) 
                DO UPDATE SET
                    player_name = EXCLUDED.player_name,
                    position = EXCLUDED.position,
                    team = EXCLUDED.team,
                    madden_rating = EXCLUDED.madden_rating,
                    position_key = EXCLUDED.position_key,
                    weight = EXCLUDED.weight,
                    tier = EXCLUDED.tier,
                    season = EXCLUDED.season,
                    updated_at = CURRENT_TIMESTAMP;
            """, **player_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Error storing player rating: {e}")
            return False
    
    def store_player_ratings_batch(self, players: List[Dict[str, Any]]) -> int:
        """
        Store multiple player ratings in a batch
        
        Args:
            players: List of player data dictionaries
            
        Returns:
            int: Number of players stored successfully
        """
        stored_count = 0
        for player in players:
            if self.store_player_rating(player):
                stored_count += 1
        
        logger.info(f"Stored {stored_count}/{len(players)} player ratings")
        return stored_count
    
    def get_player_rating(self, player_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a player's rating data
        
        Args:
            player_id: Sportradar player UUID
            
        Returns:
            Dict with player data or None if not found
        """
        try:
            result = self.connection.run("""
                SELECT player_id, player_name, position, team, madden_rating,
                       position_key, weight, tier, season
                FROM player_ratings
                WHERE player_id = :player_id
                LIMIT 1;
            """, player_id=player_id)
            
            if result:
                row = result[0]
                return {
                    'player_id': row[0],
                    'player_name': row[1],
                    'position': row[2],
                    'team': row[3],
                    'madden_rating': row[4],
                    'position_key': row[5],
                    'weight': float(row[6]),
                    'tier': row[7],
                    'season': row[8]
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting player rating: {e}")
            return None
    
    def store_injury_impact(self, impact_data: Dict[str, Any]) -> bool:
        """
        Store injury impact calculation for a team in a game
        
        Args:
            impact_data: Dict with injury impact metrics
            
        Returns:
            bool: True if successful
        """
        try:
            self.connection.run("""
                INSERT INTO injury_impact
                (game_id, team_id, season, week, season_type,
                 total_injury_score, replacement_adjusted_score, inactive_starter_count,
                 tier_1_out, tier_2_out, tier_3_out, tier_4_out, tier_5_out,
                 qb1_active, rb1_active, wr1_active, edge1_active, cb1_active, lt_active, s1_active,
                 calculated_at)
                VALUES (:game_id, :team_id, :season, :week, :season_type,
                        :total_injury_score, :replacement_adjusted_score, :inactive_starter_count,
                        :tier_1_out, :tier_2_out, :tier_3_out, :tier_4_out, :tier_5_out,
                        :qb1_active, :rb1_active, :wr1_active, :edge1_active, :cb1_active, :lt_active, :s1_active,
                        CURRENT_TIMESTAMP)
                ON CONFLICT (game_id, team_id)
                DO UPDATE SET
                    season = EXCLUDED.season,
                    week = EXCLUDED.week,
                    season_type = EXCLUDED.season_type,
                    total_injury_score = EXCLUDED.total_injury_score,
                    replacement_adjusted_score = EXCLUDED.replacement_adjusted_score,
                    inactive_starter_count = EXCLUDED.inactive_starter_count,
                    tier_1_out = EXCLUDED.tier_1_out,
                    tier_2_out = EXCLUDED.tier_2_out,
                    tier_3_out = EXCLUDED.tier_3_out,
                    tier_4_out = EXCLUDED.tier_4_out,
                    tier_5_out = EXCLUDED.tier_5_out,
                    qb1_active = EXCLUDED.qb1_active,
                    rb1_active = EXCLUDED.rb1_active,
                    wr1_active = EXCLUDED.wr1_active,
                    edge1_active = EXCLUDED.edge1_active,
                    cb1_active = EXCLUDED.cb1_active,
                    lt_active = EXCLUDED.lt_active,
                    s1_active = EXCLUDED.s1_active,
                    calculated_at = CURRENT_TIMESTAMP;
            """, **impact_data)
            
            logger.info(f"✓ Stored injury impact for game {impact_data['game_id']}, team {impact_data['team_id']}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing injury impact: {e}")
            return False
    
    def store_inactive_player(self, inactive_data: Dict[str, Any]) -> bool:
        """
        Store inactive player record
        
        Args:
            inactive_data: Dict with [game_id, team_id, player_id, player_name, 
                          position_key, weight, tier, replacement_value]
                          
        Returns:
            bool: True if successful
        """
        try:
            self.connection.run("""
                INSERT INTO inactive_players
                (game_id, team_id, player_id, player_name, position_key, 
                 weight, tier, replacement_value, recorded_at)
                VALUES (:game_id, :team_id, :player_id, :player_name, :position_key,
                        :weight, :tier, :replacement_value, CURRENT_TIMESTAMP);
            """, **inactive_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Error storing inactive player: {e}")
            return False
    
    def get_game_injury_impact(self, game_id: str) -> List[Dict[str, Any]]:
        """
        Get injury impact for both teams in a game
        
        Args:
            game_id: Sportradar game UUID
            
        Returns:
            List of injury impact records (one per team)
        """
        try:
            results = self.connection.run("""
                SELECT game_id, team_id, season, week, season_type,
                       total_injury_score, replacement_adjusted_score, inactive_starter_count,
                       tier_1_out, tier_2_out, tier_3_out, tier_4_out, tier_5_out,
                       qb1_active, rb1_active, wr1_active, edge1_active, cb1_active, lt_active, s1_active
                FROM injury_impact
                WHERE game_id = :game_id
                ORDER BY team_id;
            """, game_id=game_id)
            
            impacts = []
            for row in results:
                impacts.append({
                    'game_id': row[0],
                    'team_id': row[1],
                    'season': row[2],
                    'week': row[3],
                    'season_type': row[4],
                    'total_injury_score': float(row[5]),
                    'replacement_adjusted_score': float(row[6]),
                    'inactive_starter_count': row[7],
                    'tier_1_out': row[8],
                    'tier_2_out': row[9],
                    'tier_3_out': row[10],
                    'tier_4_out': row[11],
                    'tier_5_out': row[12],
                    'qb1_active': row[13],
                    'rb1_active': row[14],
                    'wr1_active': row[15],
                    'edge1_active': row[16],
                    'cb1_active': row[17],
                    'lt_active': row[18],
                    's1_active': row[19]
                })
            
            return impacts
            
        except Exception as e:
            logger.error(f"Error getting game injury impact: {e}")
            return []
    
    def close(self):
        """Close database connection"""
        if self.connection:
            try:
                self.connection.close()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")


# Test the storage
if __name__ == "__main__":
    print("SupabaseStorage - Testing...")
    
    try:
        storage = SupabaseStorage()
        print("✓ Storage initialized")
        
        # Test storing a player rating
        test_player = {
            'player_id': 'test_player_123',
            'player_name': 'Test Player',
            'position': 'QB',
            'team': 'KC',
            'madden_rating': 99,
            'position_key': 'QB1',
            'weight': 1.000,
            'tier': 1,
            'season': 2025
        }
        
        success = storage.store_player_rating(test_player)
        print(f"✓ Stored player rating: {success}")
        
        # Test retrieving the player
        retrieved = storage.get_player_rating('test_player_123')
        print(f"✓ Retrieved player: {retrieved['player_name'] if retrieved else 'Not found'}")
        
        storage.close()
        print("✓ Test complete")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()

