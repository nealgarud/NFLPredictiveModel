class PlayerWeightAssigner:
    """
    Assigns weights combining Boyd's position values + Madden ratings.
    
    Logic: Position importance × Player quality tier
    """
    
    def __init__(self, madden_data=None):
        """
        Args:
            madden_data: DataFrame with columns [player_id, overallrating]
        """
        self.madden_data = madden_data
        self.use_madden = madden_data is not None
        
        # Define rating tiers
        self.rating_tiers = {
            'elite': (92, 100),
            'good': (84, 91),
            'average': (72, 83),
            'below': (0, 71)
        }
        
        # Position weights by tier (Boyd's methodology adjusted)
        self.position_tier_weights = {
            # QB - Most critical
            'QB1': {'elite': 1.000, 'good': 0.900, 'average': 0.800, 'below': 0.700},
            'QB2': {'elite': 0.100, 'good': 0.090, 'average': 0.080, 'below': 0.070},
            
            # RB
            'RB1': {'elite': 0.475, 'good': 0.428, 'average': 0.380, 'below': 0.333},
            'RB2': {'elite': 0.175, 'good': 0.158, 'average': 0.140, 'below': 0.123},
            
            # WR
            'WR1': {'elite': 0.425, 'good': 0.383, 'average': 0.340, 'below': 0.298},
            'WR2': {'elite': 0.325, 'good': 0.293, 'average': 0.260, 'below': 0.228},
            'WR3': {'elite': 0.150, 'good': 0.135, 'average': 0.120, 'below': 0.105},
            
            # EDGE
            'EDGE1': {'elite': 0.400, 'good': 0.360, 'average': 0.320, 'below': 0.280},
            'EDGE2': {'elite': 0.300, 'good': 0.270, 'average': 0.240, 'below': 0.210},
            
            # CB
            'CB1': {'elite': 0.375, 'good': 0.338, 'average': 0.300, 'below': 0.263},
            'CB2': {'elite': 0.175, 'good': 0.158, 'average': 0.140, 'below': 0.123},
            
            # ... continue for all positions
        }
    
    def assign_weights(self, mapped_positions):
        """
        Assign final weights to all players.
        
        If madden_data provided: Use tiered weights based on rating
        If not: Use 'good' tier as default
        """
        weighted_players = []
        
        for player in mapped_positions:
            weight = self._calculate_weight(player)
            tier = self._get_tier_from_weight(weight)
            
            weighted_player = player.copy()
            weighted_player['weight'] = weight
            weighted_player['tier'] = tier
            weighted_players.append(weighted_player)
        
        return weighted_players
    
    def _calculate_weight(self, player):
        """Calculate weight for a single player"""
        position_key = player['position_key']
        
        if self.use_madden:
            # Get player's Madden rating
            rating = self._get_madden_rating(player['player_id'])
            rating_tier = self._get_rating_tier(rating)
        else:
            # Default to 'good' tier if no Madden data
            rating_tier = 'good'
        
        # Look up weight for this position + tier
        weights = self.position_tier_weights.get(position_key, {})
        weight = weights.get(rating_tier, 0.0)
        
        return weight
    
    def _get_madden_rating(self, player_id):
        """Look up player's Madden rating from DataFrame"""
        if self.madden_data is None:
            return 84  # Default to 'good' tier
        
        player_row = self.madden_data[self.madden_data['player_id'] == player_id]
        if len(player_row) == 0:
            return 84  # Player not found, default to 'good'
        
        return player_row['overallrating'].values[0]
    
    def _get_rating_tier(self, rating):
        """Determine tier based on rating"""
        for tier_name, (min_rating, max_rating) in self.rating_tiers.items():
            if min_rating <= rating <= max_rating:
                return tier_name
        return 'below'  # Fallback
    
    def _get_tier_from_weight(self, weight):
        """Determine overall tier (1-5) based on weight"""
        if weight >= 0.90:
            return 1  # Critical
        elif weight >= 0.35:
            return 2  # High
        elif weight >= 0.20:
            return 3  # Medium
        elif weight >= 0.10:
            return 4  # Lower
        else:
            return 5  # Depth