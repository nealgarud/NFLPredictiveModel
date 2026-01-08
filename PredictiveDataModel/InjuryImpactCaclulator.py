class InjuryImpactCalculator:
    def __init__(self, position_weights):
        # Store position weights (QB1: 1.000, WR1: 0.425, etc.)
      
        pass
    
    def calculate_game_impact(self, mapped_positions, game_roster):
        # Main method: calculate injury impact for one team
        # 1. Match mapped_positions with game_roster (by player_id)
        # 2. Find which starters are inactive
        # 3. Calculate value_lost for each inactive starter
        # 4. Sum up total injury_score
        pass
    
    def _calculate_next_man_up(self, position_key, mapped_positions, game_roster):
        # Helper: handle backup promotion
        # If WR1 starter is out, who replaces him?
        pass
    
    def _get_tier_breakdown(self, inactive_players):
        # Helper: count how many Tier 1, Tier 2, Tier 3 players out
        pass