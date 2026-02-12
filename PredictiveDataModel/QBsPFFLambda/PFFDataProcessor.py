"""
PFFDataProcessor.py
THE MEAT AND POTATOES
Processes PFF CSV data, transforms it, and writes to database in batches
"""

import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal
from DatabaseUtils import DatabaseUtils

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class PFFDataProcessor:
    """
    Core data processing class
    Handles data transformation, validation, batching, and database writes
    """
    
    def __init__(self, db_utils: DatabaseUtils, batch_size: int = 50):
        """
        Initialize processor
        
        Args:
            db_utils: DatabaseUtils instance for database operations
            batch_size: Number of rows to process in each batch
        """
        self.db_utils = db_utils
        self.batch_size = batch_size
        logger.info(f"PFFDataProcessor initialized (batch_size={batch_size})")
    
    def clean_value(self, value: Any, data_type: str = 'str') -> Any:
        """
        Clean and convert CSV values to appropriate database types
        
        Args:
            value: Raw CSV value (usually a string)
            data_type: Target type ('str', 'int', 'decimal')
        
        Returns:
            Cleaned value or None
        """
        # Handle empty/null values
        if value is None or value == '' or str(value).strip() == '':
            return None
        
        try:
            if data_type == 'int':
                # Handle values like "1.0" -> 1
                return int(float(str(value).strip()))
            
            elif data_type == 'decimal':
                return Decimal(str(value).strip())
            
            elif data_type == 'str':
                return str(value).strip()
            
            else:
                return value
        
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to convert value '{value}' to {data_type}: {e}")
            return None
    
    def normalize_team_abbreviation(self, team: str) -> str:
        """
        Normalize team abbreviations to standard format
        
        Args:
            team: Raw team abbreviation from CSV
        
        Returns:
            Standardized team abbreviation
        """
        if not team:
            return 'UNK'
        
        team = str(team).strip().upper()
        
        # Handle special cases
        team_mapping = {
            'LA': 'LAR',      # Los Angeles Rams
            'LAR': 'LAR',
            'LAC': 'LAC',     # Los Angeles Chargers
            'HST': 'HOU',     # Houston (sometimes abbreviated HST in PFF)
            'BLT': 'BAL',     # Baltimore (sometimes BLT)
            'CLV': 'CLE',     # Cleveland (sometimes CLV)
            'ARZ': 'ARI',     # Arizona
            # Add more mappings as needed
        }
        
        return team_mapping.get(team, team)
    
    def _get_value(self, row: Dict[str, Any], *possible_keys: str, default=None):
        """
        Get value from row using multiple possible column names
        
        Args:
            row: CSV row dictionary
            *possible_keys: Multiple possible column names to try
            default: Default value if none found
        
        Returns:
            First matching value found, or default
        """
        for key in possible_keys:
            if key in row and row[key] not in [None, '', 'None']:
                return row[key]
        return default
    
    def transform_row(self, row: Dict[str, Any], season: int) -> Dict[str, Any]:
        """
        Transform CSV row to database format. Maps CSV columns 1:1.
        """
        def get(k, dtype='str', default=None):
            val = self._get_value(row, k, default=default)
            if val is None:
                return default
            return self.clean_value(val, dtype)

        return {
            'player': get('player', 'str'),
            'player_id': get('player_id', 'str'),
            'position': get('position', 'str', 'QB'),
            'team': self.normalize_team_abbreviation(get('team_name', 'str') or ''),
            'franchise_id': get('franchise_id', 'int'),
            'season': season,
            'player_game_count': get('player_game_count', 'int'),
            'accuracy_percent': get('accuracy_percent', 'decimal'),
            'aimed_passes': get('aimed_passes', 'int'),
            'attempts': get('attempts', 'int'),
            'avg_depth_of_target': get('avg_depth_of_target', 'decimal'),
            'avg_time_to_throw': get('avg_time_to_throw', 'decimal'),
            'bats': get('bats', 'int'),
            'big_time_throws': get('big_time_throws', 'int'),
            'btt_rate': get('btt_rate', 'decimal'),
            'completion_percent': get('completion_percent', 'decimal'),
            'completions': get('completions', 'int'),
            'declined_penalties': get('declined_penalties', 'int'),
            'def_gen_pressures': get('def_gen_pressures', 'int'),
            'drop_rate': get('drop_rate', 'decimal'),
            'dropbacks': get('dropbacks', 'int'),
            'drops': get('drops', 'int'),
            'first_downs': get('first_downs', 'int'),
            'grades_hands_fumble': get('grades_hands_fumble', 'decimal'),
            'grades_offense': get('grades_offense', 'decimal'),
            'grades_pass': get('grades_pass', 'decimal'),
            'grades_run': get('grades_run', 'decimal'),
            'hit_as_threw': get('hit_as_threw', 'int'),
            'interceptions': get('interceptions', 'int'),
            'passing_snaps': get('passing_snaps', 'int'),
            'penalties': get('penalties', 'int'),
            'pressure_to_sack_rate': get('pressure_to_sack_rate', 'decimal'),
            'qb_rating': get('qb_rating', 'decimal'),
            'sack_percent': get('sack_percent', 'decimal'),
            'sacks': get('sacks', 'int'),
            'scrambles': get('scrambles', 'int'),
            'spikes': get('spikes', 'int'),
            'thrown_aways': get('thrown_aways', 'int'),
            'touchdowns': get('touchdowns', 'int'),
            'turnover_worthy_plays': get('turnover_worthy_plays', 'int'),
            'twp_rate': get('twp_rate', 'decimal'),
            'yards': get('yards', 'int'),
            'ypa': get('ypa', 'decimal'),
        }
    
    def validate_row(self, row: Dict[str, Any]) -> bool:
        """
        Validate that a row has required fields
        
        Args:
            row: Transformed row dictionary
        
        Returns:
            True if valid, False otherwise
        """
        required_fields = ['player', 'season']
        
        for field in required_fields:
            if not row.get(field):
                logger.warning(f"Row missing required field '{field}': {row}")
                return False
        
        return True
    
    def build_upsert_query(self) -> str:
        """Build SQL UPSERT matching CSV columns."""
        cols = [
            'player', 'player_id', 'position', 'team', 'franchise_id', 'season', 'player_game_count',
            'accuracy_percent', 'aimed_passes', 'attempts', 'avg_depth_of_target', 'avg_time_to_throw',
            'bats', 'big_time_throws', 'btt_rate', 'completion_percent', 'completions',
            'declined_penalties', 'def_gen_pressures', 'drop_rate', 'dropbacks', 'drops', 'first_downs',
            'grades_hands_fumble', 'grades_offense', 'grades_pass', 'grades_run',
            'hit_as_threw', 'interceptions', 'passing_snaps', 'penalties',
            'pressure_to_sack_rate', 'qb_rating', 'sack_percent', 'sacks',
            'scrambles', 'spikes', 'thrown_aways', 'touchdowns', 'turnover_worthy_plays', 'twp_rate',
            'yards', 'ypa'
        ]
        placeholders = ', '.join(['%s'] * len(cols))
        col_list = ', '.join(cols)
        update_cols = ', '.join(f"{c} = EXCLUDED.{c}" for c in cols if c not in ('player', 'team', 'season'))
        return f"""
            INSERT INTO qb_pff_ratings ({col_list}, created_at, updated_at)
            VALUES ({placeholders}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (player, team, season)
            DO UPDATE SET {update_cols}, updated_at = CURRENT_TIMESTAMP
        """
    
    def row_to_tuple(self, row: Dict[str, Any]) -> tuple:
        """Convert row dict to tuple matching build_upsert_query column order."""
        cols = [
            'player', 'player_id', 'position', 'team', 'franchise_id', 'season', 'player_game_count',
            'accuracy_percent', 'aimed_passes', 'attempts', 'avg_depth_of_target', 'avg_time_to_throw',
            'bats', 'big_time_throws', 'btt_rate', 'completion_percent', 'completions',
            'declined_penalties', 'def_gen_pressures', 'drop_rate', 'dropbacks', 'drops', 'first_downs',
            'grades_hands_fumble', 'grades_offense', 'grades_pass', 'grades_run',
            'hit_as_threw', 'interceptions', 'passing_snaps', 'penalties',
            'pressure_to_sack_rate', 'qb_rating', 'sack_percent', 'sacks',
            'scrambles', 'spikes', 'thrown_aways', 'touchdowns', 'turnover_worthy_plays', 'twp_rate',
            'yards', 'ypa'
        ]
        return tuple(row[c] for c in cols)
    
    def process_and_store(self, csv_rows: List[Dict[str, Any]], season: int) -> int:
        """
        THE MAIN METHOD
        Process CSV rows and store them in database in batches
        
        Args:
            csv_rows: List of raw CSV rows
            season: Year/season for this data
        
        Returns:
            Total number of rows processed
        """
        logger.info(f"Processing {len(csv_rows)} rows for season {season}")
        
        # Transform all rows
        transformed_rows = []
        for raw_row in csv_rows:
            transformed = self.transform_row(raw_row, season)
            if self.validate_row(transformed):
                transformed_rows.append(transformed)
        
        logger.info(f"✓ Transformed {len(transformed_rows)} valid rows")
        
        # Process in batches
        total_inserted = 0
        query = self.build_upsert_query()
        
        for i in range(0, len(transformed_rows), self.batch_size):
            batch = transformed_rows[i:i + self.batch_size]
            batch_tuples = [self.row_to_tuple(row) for row in batch]
            
            logger.info(f"Processing batch {i // self.batch_size + 1}: {len(batch)} rows")
            
            try:
                rows_affected = self.db_utils.execute_batch(query, batch_tuples)
                total_inserted += rows_affected
            except Exception as e:
                logger.error(f"Failed to process batch: {e}")
                raise
        
        logger.info(f"✓ COMPLETE: {total_inserted} rows upserted to database")
        return total_inserted

