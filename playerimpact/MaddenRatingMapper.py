"""
MaddenRatingMapper - Adjusts player weights based on Madden ratings

Purpose: Not all QB1s are equal! Patrick Mahomes vs Bryce Young should have different weights.

Approach:
1. Start with Boyd's base position values (QB = 1.0, RB1 = 0.475, etc.)
2. Adjust by player quality using Madden rating
3. Different positions have different rating scales (QB matters more than RB)

Formula: final_weight = base_position_weight × madden_quality_multiplier
"""

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class MaddenRatingMapper:
    """Maps Madden ratings to weight multipliers for different positions"""
    
    def __init__(self, madden_data):
        """
        Args:
            madden_data: DataFrame with columns [player_id, overallrating]
        """
        self.madden_data = madden_data
        
        # Boyd's base position values (from PlayerWeightAssigner)
        # These are the "perfect player" weights
        self.base_position_weights = {
            'QB1': 1.000,
            'RB1': 0.475,
            'WR1': 0.425,
            'WR2': 0.325,
            'EDGE1': 0.400,
            'CB1': 0.375,
            # ... we'll add more as needed
        }
        
        logger.info("MaddenRatingMapper initialized")
    
    def calculate_adjusted_weight(self, player_id, position_key):
        """
        Calculate player's weight based on position + Madden rating.
        
        Args:
            player_id: Sportradar player ID
            position_key: Standardized position (QB1, WR2, etc.)
        
        Returns:
            float: Adjusted weight
        
        Example:
            Mahomes (QB1, 99 rating) → 0.986
            Young (QB1, 73 rating) → 0.614
        """
        # Step 1: Get base position weight
        base_weight = self.base_position_weights.get(position_key, 0.0)
        
        # Step 2: Get player's Madden rating
        rating = self._get_player_rating(player_id)
        
        # Step 3: Calculate quality multiplier based on position type
        multiplier = self._calculate_quality_multiplier(rating, position_key)
        
        # Step 4: Calculate final weight
        final_weight = base_weight * multiplier
        
        return final_weight
    
    def _get_player_rating(self, player_id):
    
        if self.madden_data is None:
            return 68  # Default to average
    
    # Filter DataFrame to find this player
        player_row = self.madden_data[self.madden_data['player_id'] == player_id]
    
    # Check if player was found
        if len(player_row) == 0:
        # Player not in Madden data (rookie, practice squad, etc.)
            return 68  # Default to average
    
    # Return the player's overall rating
        return player_row['overallrating'].values[0]

    def _calculate_quality_multiplier(self, rating, position_key):
        """Calculate quality multiplier based on rating and position"""
        logger.info(f"Calculating multiplier for {position_key} with rating {rating}")
        
        if position_key.startswith('QB'):
            position_type = 'QB'
        elif position_key.startswith('RB'):
            position_type = 'RB'
        elif position_key.startswith('WR'):
            position_type = 'WR'
        elif position_key.startswith('TE'):
            position_type = 'TE'
        elif position_key.startswith('EDGE'):
            position_type = 'EDGE'
        elif position_key.startswith('CB'):
            position_type = 'CB'
        elif position_key.startswith('DT'):
            position_type = 'DT'
        elif position_key.startswith('LB'):
            position_type = 'LB'
        else:
            position_type = 'S'

        if position_type == 'QB':
            multiplier = (rating - 30) / 70
        elif position_type == 'RB':
            multiplier = (rating - 50) / 50
        elif position_type == 'WR':
            multiplier = (rating - 40) / 60
        elif position_type == 'TE':
            multiplier = (rating - 45) / 55
        elif position_type == 'EDGE':
            multiplier = (rating - 40) / 60
        elif position_type == 'CB':
            multiplier = (rating - 40) / 60
        elif position_type == 'DT':
            multiplier = (rating - 45) / 55
        elif position_type == 'LB':
            multiplier = (rating - 45) / 55
        else:
            multiplier = (rating - 45) / 65
        
        logger.info(f"Calculated multiplier: {multiplier}")
        return multiplier


# Test
if __name__ == "__main__":
    print("MaddenRatingMapper - Ready to build!")


