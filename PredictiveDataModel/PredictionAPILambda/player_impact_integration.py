"""
Player Impact Integration - Add to SpreadPredictionCalculator

This shows how to integrate player impact data into your existing prediction model.

Add this as a new factor alongside:
- Situational ATS (40%)
- Overall ATS (30%)
- Home/Away Performance (30%)
- Player Impact (NEW!)
"""

from SupabaseStorage import SupabaseStorage
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class PlayerImpactIntegration:
    """Fetch and calculate player impact for spread predictions"""
    
    def __init__(self):
        """Initialize with Supabase connection"""
        self.storage = SupabaseStorage()
    
    def get_player_impact_for_matchup(self, team_a, team_b, game_id=None):
        """
        Get player impact differential for a matchup
        
        Args:
            team_a: Team abbreviation
            team_b: Team abbreviation  
            game_id: Optional - if you have the specific game_id
            
        Returns:
            float: Impact differential (-1 to +1)
                   Positive = team_a advantage
                   Negative = team_b advantage
        """
        
        if game_id:
            # Get impact from specific game
            impacts = self.storage.get_game_injury_impact(game_id)
            
            team_a_impact = next((i for i in impacts if i['team_id'] == team_a), None)
            team_b_impact = next((i for i in impacts if i['team_id'] == team_b), None)
            
            if team_a_impact and team_b_impact:
                # Calculate differential
                diff = (team_b_impact['replacement_adjusted_score'] - 
                       team_a_impact['replacement_adjusted_score'])
                
                # Normalize to -1 to +1 range
                normalized = diff / 10.0  # Assuming max impact is ~10
                return max(min(normalized, 1.0), -1.0)
        
        # If no game_id, use historical average
        return self._get_historical_impact_average(team_a, team_b)
    
    def _get_historical_impact_average(self, team_a, team_b):
        """Get average historical injury impact for these teams"""
        # Query Supabase for average injury scores
        # This would need custom SQL query
        
        # Placeholder - return neutral if no data
        return 0.0


# Example: How to add to SpreadPredictionCalculator
"""
In your SpreadPredictionCalculator.py:

class SpreadPredictionCalculator:
    # Update weights to include player impact
    SITUATIONAL_ATS_WEIGHT = 0.35  # 35% (reduced from 40%)
    OVERALL_ATS_WEIGHT = 0.25      # 25% (reduced from 30%)
    HOME_AWAY_WEIGHT = 0.25        # 25% (reduced from 30%)
    PLAYER_IMPACT_WEIGHT = 0.15    # 15% (NEW!)
    
    def __init__(self):
        self.db = DatabaseConnection()
        self.player_impact = PlayerImpactIntegration()  # NEW!
    
    def predict_spread_coverage(self, team_a, team_b, spread, team_a_home, seasons):
        # ... existing code ...
        
        # NEW: Calculate player impact
        player_impact_score = self.player_impact.get_player_impact_for_matchup(
            team_a, team_b
        )
        
        # If team_a has injury advantage (positive score), boost their chances
        # If team_b has advantage (negative score), boost team_b
        
        # Incorporate into final prediction
        final_score = (
            situational_ats * self.SITUATIONAL_ATS_WEIGHT +
            overall_ats * self.OVERALL_ATS_WEIGHT +
            home_away * self.HOME_AWAY_WEIGHT +
            player_impact_score * self.PLAYER_IMPACT_WEIGHT  # NEW!
        )
        
        # ... rest of prediction logic ...
"""

