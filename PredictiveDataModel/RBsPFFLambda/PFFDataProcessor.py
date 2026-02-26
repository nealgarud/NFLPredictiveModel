"""
PFFDataProcessor.py
Processes and transforms PFF (Pro Football Focus) data for Running Backs (RBs).
Handles data cleaning, validation, and batch insertion into PostgreSQL database.
"""

import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal
from DatabaseUtils import DatabaseUtils


logger = logging.getLogger()
logger.setLevel(logging.INFO)


class PFFDataProcessor:
    """
    Processes PFF running back statistics and stores them in the database.
    Handles data transformation, validation, and batch upsert operations.
    """

    def __init__(self, db_utils: DatabaseUtils, batch_size: int = 50):
        """
        Initialize the PFF data processor.
        
        Args:
            db_utils: Database utility instance for executing queries
            batch_size: Number of rows to process in each batch (default: 50)
        """
        self.db_utils = db_utils
        self.batch_size = batch_size
        logger.info(f"PFFDataProcessor initialized (batch_size={batch_size})")
    
    def clean_value(self, value: Any, data_type: str = 'str') -> Any:
        """
        Clean and convert a value to the specified data type.
        
        Args:
            value: Raw value from CSV
            data_type: Target data type ('str', 'int', or 'decimal')
        
        Returns:
            Cleaned and converted value, or None if conversion fails
        """
        if value is None or value == '' or str(value).strip() == '':
            return None
        try:
            if data_type == 'int':
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
        Normalize team abbreviations to match database standards.
        Handles various PFF naming conventions and maps them to consistent values.
        
        Args:
            team: Raw team abbreviation from PFF data
        
        Returns:
            Normalized team abbreviation
        """
        if not team:
            return 'UNK'

        team = str(team).strip().upper()

        # Map PFF team abbreviations to standard NFL abbreviations
        team_mapping = {
            'LA': 'LAR',      # Los Angeles Rams
            'LAR': 'LAR',
            'LAC': 'LAC',     # Los Angeles Chargers
            'HST': 'HOU',     # Houston (sometimes abbreviated HST in PFF)
            'BLT': 'BAL',     # Baltimore (sometimes BLT)
            'CLV': 'CLE',     # Cleveland (sometimes CLV)
            'ARZ': 'ARI',     # Arizona
        }
        
        return team_mapping.get(team, team)

    def _get_value(self, row: Dict[str, Any], *possible_keys: str, default=None) -> Any:
        """
        Attempt to retrieve a value from multiple possible keys in a row.
        Useful for handling variations in CSV column names.
        
        Args:
            row: Data row dictionary
            *possible_keys: Variable number of possible key names to try
            default: Default value if none of the keys exist
        
        Returns:
            First non-null value found, or default
        """
        for key in possible_keys:
            if key in row and row[key] not in [None, '', 'None']:
                return row[key]
        return default
    
    def transform_row(self, row: Dict[str, Any], season: int) -> Dict[str, Any]:
        """
        Transform a raw CSV row into the format expected by the database.
        Cleans values, normalizes team names, and adds season information.
        
        Args:
            row: Raw row from CSV file
            season: Season year to associate with the data
        
        Returns:
            Transformed dictionary ready for database insertion
        """
        def get(k, dtype='str', default=None):
            """Helper function to get and clean a value from the row"""
            val = self._get_value(row, k, default=default)
            if val is None:
                return default
            return self.clean_value(val, dtype)

        # Extract and transform all RB-specific fields
        return {
            'player': get('player', 'str'),
            'player_id': get('player_id', 'str'),
            'position': get('position', 'str'),
            'team_name': self.normalize_team_abbreviation(get('team_name', 'str')),
            'season': season,
            'player_game_count': get('player_game_count', 'int'),
            'attempts': get('attempts', 'int'),
            'avoided_tackles': get('avoided_tackles', 'int'),
            'breakaway_attempts': get('breakaway_attempts', 'int'),
            'breakaway_percent': get('breakaway_percent', 'decimal'),
            'breakaway_yards': get('breakaway_yards', 'int'),
            'declined_penalties': get('declined_penalties', 'int'),
            'designed_yards': get('designed_yards', 'int'),
            'drops': get('drops', 'int'),
            'elu_recv_mtf': get('elu_recv_mtf', 'decimal'),
            'elu_rush_mtf': get('elu_rush_mtf', 'decimal'),
            'elu_yco': get('elu_yco', 'decimal'),
            'elusive_rating': get('elusive_rating', 'decimal'),
            'explosive': get('explosive', 'int'),
            'first_downs': get('first_downs', 'int'),
            'franchise_id': get('franchise_id', 'int'),
            'fumbles': get('fumbles', 'int'),
            'gap_attempts': get('gap_attempts', 'int'),
            'grades_hands_fumble': get('grades_hands_fumble', 'decimal'),
            'grades_offense': get('grades_offense', 'decimal'),
            'grades_offense_penalty': get('grades_offense_penalty', 'decimal'),
            'grades_pass': get('grades_pass', 'decimal'),
            'grades_pass_block': get('grades_pass_block', 'decimal'),
            'grades_pass_route': get('grades_pass_route', 'decimal'),
            'grades_run': get('grades_run', 'decimal'),
            'grades_run_block': get('grades_run_block', 'decimal'),
            'longest': get('longest', 'int'),
            'penalties': get('penalties', 'int'),
            'rec_yards': get('rec_yards', 'int'),
            'receptions': get('receptions', 'int'),
            'routes': get('routes', 'int'),
            'run_plays': get('run_plays', 'int'),
            'scramble_yards': get('scramble_yards', 'int'),
            'scrambles': get('scrambles', 'int'),
            'targets': get('targets', 'int'),
            'total_touches': get('total_touches', 'int'),
            'touchdowns': get('touchdowns', 'int'),
            'yards': get('yards', 'int'),
            'yards_after_contact': get('yards_after_contact', 'int'),
            'yco_attempt': get('yco_attempt', 'decimal'),
            'ypa': get('ypa', 'decimal'),
            'yprr': get('yprr', 'decimal'),
            'zone_attempts': get('zone_attempts', 'int'),
        }
            
    def validate_row(self, row: Dict[str, Any]) -> bool:
        """
        Validate that a row contains all required fields.
        
        Args:
            row: Transformed data row
        
        Returns:
            True if row is valid, False otherwise
        """
        required_fields = ['player', 'season']
        for field in required_fields:
            if not row.get(field):
                logger.warning(f"Row missing required field '{field}': {row}")
                return False
        return True

    def build_upsert_query(self) -> str:
        """
        Build the SQL UPSERT query for inserting/updating RB PFF data.
        Uses PostgreSQL's ON CONFLICT clause to handle duplicates.
        
        Returns:
            Parameterized SQL query string
        """
        cols = [
            "player", "player_id", "position", "team_name", "season", "player_game_count",
            "attempts", "avoided_tackles", "breakaway_attempts", "breakaway_percent",
            "breakaway_yards", "declined_penalties", "designed_yards", "drops",
            "elu_recv_mtf", "elu_rush_mtf", "elu_yco", "elusive_rating", "explosive",
            "first_downs", "franchise_id", "fumbles", "gap_attempts", "grades_hands_fumble",
            "grades_offense", "grades_offense_penalty", "grades_pass", "grades_pass_block",
            "grades_pass_route", "grades_run", "grades_run_block", "longest", "penalties",
            "rec_yards", "receptions", "routes", "run_plays", "scramble_yards", "scrambles",
            "targets", "total_touches", "touchdowns", "yards", "yards_after_contact",
            "yco_attempt", "ypa", "yprr", "zone_attempts"
        ]

        placeholders = ','.join(['%s'] * len(cols))
        col_list = ', '.join(cols)
        update_cols = ', '.join(f"{c} = EXCLUDED.{c}" for c in cols if c not in ('player', 'team_name', 'season'))

        return f"""
            INSERT INTO rb_pff_ratings ({col_list}, created_at, updated_at)
            VALUES ({placeholders}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (player, team_name, season)
            DO UPDATE SET {update_cols}, updated_at = CURRENT_TIMESTAMP
        """
    
    def row_to_tuple(self, row: Dict[str, Any]) -> tuple:
        """
        Convert a transformed row dictionary to a tuple for batch insertion.
        
        Args:
            row: Transformed data row
        
        Returns:
            Tuple of values in the correct column order
        """
        cols = [
            "player", "player_id", "position", "team_name", "season", "player_game_count",
            "attempts", "avoided_tackles", "breakaway_attempts", "breakaway_percent",
            "breakaway_yards", "declined_penalties", "designed_yards", "drops",
            "elu_recv_mtf", "elu_rush_mtf", "elu_yco", "elusive_rating", "explosive",
            "first_downs", "franchise_id", "fumbles", "gap_attempts", "grades_hands_fumble",
            "grades_offense", "grades_offense_penalty", "grades_pass", "grades_pass_block",
            "grades_pass_route", "grades_run", "grades_run_block", "longest", "penalties",
            "rec_yards", "receptions", "routes", "run_plays", "scramble_yards", "scrambles",
            "targets", "total_touches", "touchdowns", "yards", "yards_after_contact",
            "yco_attempt", "ypa", "yprr", "zone_attempts"
        ]
        return tuple(row.get(c) for c in cols)

    def process_and_store(self, csv_rows: List[Dict[str, Any]], season: int) -> int:
        """
        Process raw CSV rows and store them in the database using batch operations.
        Transforms, validates, and inserts data in configurable batch sizes.
        
        Args:
            csv_rows: List of raw CSV row dictionaries
            season: Season year for the data
        
        Returns:
            Total number of rows successfully inserted/updated
        """
        logger.info(f"Processing {len(csv_rows)} rows for season {season}")
        
        # Transform and validate all rows
        transformed_rows = []
        for raw_row in csv_rows:
            transformed = self.transform_row(raw_row, season)
            if self.validate_row(transformed):
                transformed_rows.append(transformed)
        
        logger.info(f"✓ Transformed {len(transformed_rows)} valid rows")

        # Batch insert/update to database
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