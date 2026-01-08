from typing import List, Dict, Any

class DuplicateHandler:
    """Handle duplicate detection and upsert logic"""
    
    @staticmethod
    def generate_upsert_query(table: str, columns: List[str], conflict_columns: List[str], 
                             update_columns: List[str]) -> str:
        """
        Generate PostgreSQL UPSERT query
        
        Args:
            table: Table name
            columns: All columns to insert
            conflict_columns: Columns that define uniqueness (primary key)
            update_columns: Columns to update on conflict
            
        Returns:
            SQL query string
        """
        placeholders = ', '.join(['%s'] * len(columns))
        columns_str = ', '.join(columns)
        conflict_str = ', '.join(conflict_columns)
        
        # Build UPDATE SET clause
        update_set = ', '.join([f"{col} = EXCLUDED.{col}" for col in update_columns])
        
        query = f"""
            INSERT INTO {table} ({columns_str})
            VALUES ({placeholders})
            ON CONFLICT ({conflict_str})
            DO UPDATE SET
                {update_set},
                updated_at = CURRENT_TIMESTAMP
        """
        
        return query
    
    @staticmethod
    def check_exists(cursor, table: str, conditions: Dict[str, Any]) -> bool:
        """
        Check if record exists
        
        Args:
            cursor: Database cursor
            table: Table name
            conditions: Dictionary of column: value conditions
            
        Returns:
            True if exists, False otherwise
        """
        where_clause = ' AND '.join([f"{k} = %s" for k in conditions.keys()])
        query = f"SELECT 1 FROM {table} WHERE {where_clause} LIMIT 1"
        
        cursor.execute(query, tuple(conditions.values()))
        return cursor.fetchone() is not None