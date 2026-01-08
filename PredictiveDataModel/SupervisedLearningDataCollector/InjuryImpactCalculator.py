"""
InjuryImpactCalculator - Calculates injury impact by handling depth chart promotions

Takes: 
- Weighted players (from PlayerWeightAssigner)
- Game roster (ACTIVE/INACTIVE status from Sportradar)

Returns:
- Injury impact scores
- Tier breakdowns
- Key position flags
"""

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class InjuryImpactCalculator:
    """Calculates injury impact when starters are out"""
    
    def __init__(self):
        """Initialize the calculator"""
        # TODO: What should we initialize here?
        # Think: Do we need any configuration? Any data structures?
        pass
    
    def calculate_impact(self, weighted_players, game_roster):
        """
        Main method: Calculate injury impact for one team
        
        Args:
            weighted_players: List of dicts with [position_key, player_id, weight, depth_order, tier]
            game_roster: List of dicts with [player_id, roster_status (ACTIVE/INACTIVE)]
        
        Returns:
            dict: {
                'total_injury_score': float,
                'replacement_adjusted_score': float,
                'inactive_starter_count': int,
                'tier_1_out': int,
                'tier_2_out': int,
                'tier_3_out': int,
                'tier_4_out': int,
                'tier_5_out': int,
                'qb1_active': bool,
                'rb1_active': bool,
                'wr1_active': bool,
                'edge1_active': bool,
                'cb1_active': bool,
                'lt_active': bool,
                's1_active': bool
            }
        """
        # YOUR TURN: Build this step by step! 💪
        
        # Step 1: Find inactive starters
        inactive_starters = self._find_inactive_starters(weighted_players, game_roster)

        
        # Step 2: Calculate replacement-adjusted score (loop through inactive starters)
        total_replacement_value = 0.0
        for inactive_starter in inactive_starters:
            value_lost = self._calculate_replacement_value(inactive_starter, weighted_players, game_roster)
            total_replacement_value += value_lost
        # Step 3: Calculate simple injury score
        total_injury_score = self._calculate_injury_score(inactive_starters)
        
        # Step 4: Count tier breakdowns
        tier_counts = {1:0, 2:0, 3:0,4:0,5:0}
    
        for player in inactive_starters:
            tier = player['tier']
            tier_counts[tier]+=1
        
         # 5️⃣ Set key position flags
        key_positions = ['QB1', 'RB1', 'WR1', 'EDGE1', 'CB1', 'LT', 'S1']
        position_flags = {}
        for pos in key_positions:
            # Check if starter at this position is active
            position_flags[f"{pos.lower()}_active"] = self._is_position_starter_active(
            pos, weighted_players, game_roster)
    
    # 6️⃣ Build result dictionary
        return {
        'total_injury_score': total_injury_score,
        'replacement_adjusted_score': total_replacement_value,
        'inactive_starter_count': len(inactive_starters),
        'tier_1_out': tier_counts[1],
        'tier_2_out': tier_counts[2],
        'tier_3_out': tier_counts[3],
        'tier_4_out': tier_counts[4],
        'tier_5_out': tier_counts[5],
        **position_flags  # Unpack position flags into result
    }
    
   
    def _is_player_active(self, player_id, game_roster):
    
        for player in game_roster:  # ← ONE loop, not nested
            if player['player_id'] == player_id:  # ← Find the RIGHT player
             # Now check THIS player's status
                if player['roster_status'] == 'ACTIVE':
                    return True
                else:
                   return False
    
    # If we finished the loop and never found the player
        return True  # Assume active if not listed


    def _find_inactive_starters(self, weighted_players, game_roster):
        inactive_starters = []  # Empty list to collect results
    
    # Loop through all weighted players
# Inside the _find_inactive_starters method:

        for player in weighted_players:
            if player['depth_order'] == 1:  # ← ADD THIS CHECK
                player_id = player['player_id']
    
    # Call the helper method we wrote earlier
            is_active = self._is_player_active(player_id, game_roster)
    
    # Now use the result
            if not is_active:  # If player is NOT active (inactive)
                inactive_starters.append(player)
        # Do something
            return inactive_starters


    def _calculate_injury_score(self, inactive_starters):
  
        total_score = 0.0  # Start at zero

    # YOUR CODE: Loop through inactive_starters
       
      
    
        for player in inactive_starters:
            total_score += player['weight']  # ✅ Just add the weight directly!
    
   
    # YOUR CODE: Add each player's weight to total_score
    
        return total_score
    
    
    def _calculate_replacement_value(self, inactive_starter, weighted_players, game_roster):
        """
        Calculate value lost when a starter is out
        
        Args:
            inactive_starter: Single dict of the inactive starter
            weighted_players: Full list of all weighted players for the team
            game_roster: List with player_id and roster_status
        
        Returns:
            float: Value lost (starter_weight - replacement_weight)
        """
        position_key = inactive_starter['position_key']
        starter_weight = inactive_starter['weight']

        players_at_position = [ 
            p for p in weighted_players if p['position_key'] == position_key]

        players_at_position.sort(key=lambda x: x['depth_order'])

        backup = players_at_position[1] if len(players_at_position) > 1 else None
        third_stringer = players_at_position[2] if len(players_at_position) > 2 else None

        if backup and not self._is_player_active(backup['player_id'], game_roster):
            replacement = third_stringer
        else:
            replacement = backup

        if replacement:
            replacement_weight = replacement['weight']
        else:
            replacement_weight = 0
        
            
        value_lost = starter_weight - replacement_weight
        return value_lost


    def _is_position_starter_active(self, position_key, weighted_players, game_roster):
        """
        Check if the starter at a given position is active
        
        Args:
            position_key: Position to check (e.g., 'QB1', 'EDGE1')
            weighted_players: Full list of weighted players
            game_roster: List with player_id and roster_status
        
        Returns:
            bool: True if starter is active, False if inactive
        """
        starter = None  # Initialize to None
        
        # Loop through all players
        for player in weighted_players:
            # Check if this player matches the position_key AND is a starter (depth_order == 1)
            if player['position_key'] == position_key and player['depth_order'] == 1:
                starter = player
                break  # Found it, stop looking
        
        # If starter exists, check if they're active
        if starter:
            return self._is_player_active(starter['player_id'], game_roster)
        else:
            return True  # If position not found, assume active


# Test area
if __name__ == "__main__":
    print("InjuryImpactCalculator - Ready to build!")

