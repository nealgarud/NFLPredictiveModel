"""
PlayerWeightAssigner - Combines Boyd's position values with Madden ratings

Takes: Mapped positions from PositionMapper
Returns: Players with assigned weights based on position + player quality

Weight = Boyd's Position Importance × Madden Rating Tier
"""

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class PlayerWeightAssigner:
    """Assigns weights combining Boyd's position methodology with Madden player ratings"""
    
    def __init__(self, madden_data=None):
        """
        Args:
            madden_data: Optional DataFrame with columns [player_id, overallrating]
                        If provided, uses tiered weights based on Madden ratings
                        If None, defaults to 'average' tier
        """
        self.madden_data = madden_data
        self.use_madden = madden_data is not None
        
        # Madden rating tier ranges
        self.rating_tiers = {
            'elite': (92, 100),    # 92+
            'good': (84, 91),      # 84-91
            'average': (72, 83),   # 72-83
            'below': (0, 71)       # <72
        }
        
        # Position weights by tier (Boyd's methodology adjusted by player quality)
        # Format: position_key: {tier: weight}
        self.position_tier_weights = {
            # Quarterbacks - Most critical position
            'QB1': {'elite': 1.000, 'good': 0.900, 'average': 0.800, 'below': 0.700},
            'QB2': {'elite': 0.100, 'good': 0.090, 'average': 0.080, 'below': 0.070},
            
            # Running Backs
            'RB1': {'elite': 0.475, 'good': 0.428, 'average': 0.380, 'below': 0.333},
            'RB2': {'elite': 0.175, 'good': 0.158, 'average': 0.140, 'below': 0.123},
            
            # Wide Receivers
            'WR1': {'elite': 0.425, 'good': 0.383, 'average': 0.340, 'below': 0.298},
            'WR2': {'elite': 0.325, 'good': 0.293, 'average': 0.260, 'below': 0.228},
            'WR3': {'elite': 0.150, 'good': 0.135, 'average': 0.120, 'below': 0.105},
            
            # Tight Ends
            'TE1': {'elite': 0.300, 'good': 0.270, 'average': 0.240, 'below': 0.210},
            'TE2': {'elite': 0.150, 'good': 0.135, 'average': 0.120, 'below': 0.105},
            
            # Offensive Line
            'LT': {'elite': 0.400, 'good': 0.360, 'average': 0.320, 'below': 0.280},
            'RT': {'elite': 0.275, 'good': 0.248, 'average': 0.220, 'below': 0.193},
            'LG': {'elite': 0.150, 'good': 0.135, 'average': 0.120, 'below': 0.105},
            'RG': {'elite': 0.150, 'good': 0.135, 'average': 0.120, 'below': 0.105},
            'C': {'elite': 0.275, 'good': 0.248, 'average': 0.220, 'below': 0.193},
            
            # Edge Rushers
            'EDGE1': {'elite': 0.400, 'good': 0.360, 'average': 0.320, 'below': 0.280},
            'EDGE2': {'elite': 0.300, 'good': 0.270, 'average': 0.240, 'below': 0.210},
            
            # Defensive Tackles
            'DT1': {'elite': 0.250, 'good': 0.225, 'average': 0.200, 'below': 0.175},
            'DT2': {'elite': 0.150, 'good': 0.135, 'average': 0.120, 'below': 0.105},
            'NT': {'elite': 0.250, 'good': 0.225, 'average': 0.200, 'below': 0.175},
            
            # Linebackers
            'LB1': {'elite': 0.200, 'good': 0.180, 'average': 0.160, 'below': 0.140},
            'LB2': {'elite': 0.175, 'good': 0.158, 'average': 0.140, 'below': 0.123},
            'LB': {'elite': 0.175, 'good': 0.158, 'average': 0.140, 'below': 0.123},
            
            # Cornerbacks
            'CB1': {'elite': 0.375, 'good': 0.338, 'average': 0.300, 'below': 0.263},
            'CB2': {'elite': 0.175, 'good': 0.158, 'average': 0.140, 'below': 0.123},
            'CB3': {'elite': 0.150, 'good': 0.135, 'average': 0.120, 'below': 0.105},
            'CB': {'elite': 0.150, 'good': 0.135, 'average': 0.120, 'below': 0.105},
            
            # Safeties
            'S1': {'elite': 0.250, 'good': 0.225, 'average': 0.200, 'below': 0.175},
            'S2': {'elite': 0.150, 'good': 0.135, 'average': 0.120, 'below': 0.105},
            'S': {'elite': 0.150, 'good': 0.135, 'average': 0.120, 'below': 0.105},
        }
        
        logger.info(f"PlayerWeightAssigner initialized (Madden mode: {self.use_madden})")
    
    def assign_weights(self, mapped_positions):
        """
        Assign weights to all players based on position and quality.
        
        Args:
            mapped_positions: List of dicts with position_key, player_id, depth_order
            
        Returns:
            List of dicts with added 'weight' and 'tier' fields
        """
        weighted_players = []
        
        for player in mapped_positions:
            weight = self._calculate_weight(player)
            tier = self._get_tier_from_weight(weight)
            
            weighted_player = player.copy()
            weighted_player['weight'] = weight
            weighted_player['tier'] = tier
            
            weighted_players.append(weighted_player)
        
        logger.info(f"Assigned weights to {len(weighted_players)} players")
        return weighted_players
    
    def _calculate_weight(self, player):
        """Calculate weight for a single player"""
        position_key = player['position_key']
        
        if self.use_madden:
            # Get player's Madden rating and determine tier
            rating = self._get_madden_rating(player['player_id'])
            rating_tier = self._get_rating_tier(rating)
        else:
            # Default to 'average' tier if no Madden data
            rating_tier = 'average'
        
        # Look up weight for this position + tier combination
        weights = self.position_tier_weights.get(position_key, {})
        weight = weights.get(rating_tier, 0.0)
        
        return weight
    
    def _get_madden_rating(self, player_id):
        """Look up player's Madden overall rating from DataFrame"""
        if self.madden_data is None:
            return 78  # Middle of 'average' tier (72-83)
        
        # Find player in Madden data
        player_row = self.madden_data[self.madden_data['player_id'] == player_id]
        
        if len(player_row) == 0:
            # Player not found in Madden data (rookie, practice squad, etc.)
            return 78  # Default to average tier
        
        return player_row['overallrating'].values[0]
    
    def _get_rating_tier(self, rating):
        """Determine tier (elite/good/average/below) based on Madden rating"""
        for tier_name, (min_rating, max_rating) in self.rating_tiers.items():
            if min_rating <= rating <= max_rating:
                return tier_name
        
        return 'below'  # Fallback for edge cases
    
    def _get_tier_from_weight(self, weight):
        """
        Determine overall tier (1-5) based on final weight.
        Used for grouping players by impact level.
        """
        if weight >= 0.70:
            return 1  # Critical (QB1)
        elif weight >= 0.35:
            return 2  # High impact (RB1, WR1, EDGE1, CB1, LT)
        elif weight >= 0.20:
            return 3  # Medium impact (WR2, TE1, DT1, S1)
        elif weight >= 0.10:
            return 4  # Lower impact (WR3, RB2, LB1)
        else:
            return 5  # Depth


# Test the weight assigner
if __name__ == "__main__":
    # Example: Test without Madden data (uses 'average' tier)
    assigner = PlayerWeightAssigner()
    
    test_players = [
        {'position_key': 'QB1', 'player_id': 'test1', 'player_name': 'Test QB'},
        {'position_key': 'WR1', 'player_id': 'test2', 'player_name': 'Test WR'},
        {'position_key': 'EDGE1', 'player_id': 'test3', 'player_name': 'Test EDGE'}
    ]
    
    weighted = assigner.assign_weights(test_players)
    
    print("PlayerWeightAssigner Test:")
    print("=" * 60)
    for player in weighted:
        print(f"{player['position_key']:8} - {player['player_name']:15} - Weight: {player['weight']:.3f} (Tier {player['tier']})")

