"""
PlayerWeightAssigner - Combines Boyd's position values with PFF grades

Takes: Mapped positions from PositionMapper
Returns: Players with assigned weights based on position importance + PFF grade

Weight = Fixed Boyd's Position Importance (by position/depth)
Player Impact = Weight × PFF Grade (calculated downstream in GameImpactProcessor)
Grade tiers (elite/good/average/below) are tracked for observability but do NOT affect weights.
"""

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class PlayerWeightAssigner:
    """Assigns weights combining Boyd's position methodology with PFF player grades"""
    
    def __init__(self, pff_data_fetcher=None):
        """
        Args:
            pff_data_fetcher: Function that fetches PFF grades from database
                             Should accept (player_id, position, season) and return grade (0-100)
                             If None, defaults to average PFF grade (70.0)
        """
        self.pff_data_fetcher = pff_data_fetcher
        self.use_pff = pff_data_fetcher is not None
        
        # PFF grade tier ranges (tracked for observability, NOT used for weight calculation)
        self.grade_tiers = {
            'elite': (85, 100),
            'good': (75, 84),
            'average': (60, 74),
            'below': (0, 59)
        }
        
        # Fixed position weights based on Boyd's methodology.
        # Weight reflects position importance only; player quality comes from PFF grade.
        # Player Impact = position_weight × pff_grade (computed in GameImpactProcessor)
        self.position_weights = {
            # Quarterbacks
            'QB1': 1.000, 'QB2': 0.100, 'QB': 0.900,
            # Running Backs
            'RB1': 0.475, 'RB2': 0.175, 'RB': 0.325,
            # Wide Receivers
            'WR1': 0.425, 'WR2': 0.325, 'WR3': 0.150, 'WR': 0.300,
            # Tight Ends
            'TE1': 0.300, 'TE2': 0.150, 'TE': 0.225,
            # Offensive Line
            'LT': 0.400, 'RT': 0.275, 'LG': 0.150, 'RG': 0.150, 'C': 0.275,
            'T': 0.338, 'G': 0.150, 'OL': 0.250,
            # Edge Rushers
            'EDGE1': 0.400, 'EDGE2': 0.300, 'EDGE': 0.350, 'DE': 0.350,
            # Defensive Tackles
            'DT1': 0.250, 'DT2': 0.150, 'DT': 0.200, 'NT': 0.250,
            # Linebackers
            'LB1': 0.200, 'LB2': 0.175, 'LB': 0.175,
            # Cornerbacks
            'CB1': 0.375, 'CB2': 0.175, 'CB3': 0.150, 'CB': 0.150,
            # Safeties
            'S1': 0.250, 'S2': 0.150, 'S': 0.150,
        }
        
        logger.info(f"PlayerWeightAssigner initialized (PFF mode: {self.use_pff})")
    
    def assign_weights(self, mapped_positions, season):
        """
        Assign weights to all players based on position and PFF quality.
        
        Args:
            mapped_positions: List of dicts with position_key, player_id, depth_order
            season: Season year to fetch PFF grades for
            
        Returns:
            List of dicts with added 'weight', 'tier', and 'pff_grade' fields
        """
        weighted_players = []
        
        for player in mapped_positions:
            weight, pff_grade, grade_tier = self._calculate_weight(player, season)
            tier = self._get_tier_from_weight(weight)
            
            weighted_player = player.copy()
            weighted_player['weight'] = weight
            weighted_player['tier'] = tier
            weighted_player['pff_grade'] = pff_grade
            weighted_player['grade_tier'] = grade_tier
            
            weighted_players.append(weighted_player)
        
        logger.info(f"Assigned weights to {len(weighted_players)} players")
        return weighted_players
    
    def _calculate_weight(self, player, season):
        """
        Calculate weight for a single player.
        Weight is fixed by position; PFF grade is fetched for downstream impact calculation.
        Grade tier is determined for observability only.
        """
        position_key = player['position_key']
        
        if self.use_pff:
            pff_grade = self._get_pff_grade(player, season)
        else:
            pff_grade = 70.0
        
        grade_tier = self._get_grade_tier(pff_grade)
        
        # Fixed weight lookup -- position importance only, no tier adjustment
        weight = self.position_weights.get(position_key, 0.0)
        
        return weight, pff_grade, grade_tier
    
    def _get_pff_grade(self, player, season):
        """
        Fetch player's PFF grade from database.
        
        Logic:
        - QB: Use grades_offense or grades_pass
        - RB: Use grades_offense or grades_run  
        - WR/TE: Use grades_offense or grades_pass_route
        - OL: Average of grades_pass_block and grades_run_block
        - Defense: Use grades_defense
        """
        if self.pff_data_fetcher is None:
            return 70.0  # Middle of 'average' tier (60-74)
        
        try:
            grade = self.pff_data_fetcher(
                player_id=player.get('player_id'),
                position=player.get('position'),
                season=season
            )
            return grade if grade is not None else 70.0
        except Exception as e:
            logger.warning(f"Failed to fetch PFF grade for player {player.get('player_id')}: {e}")
            return 70.0
    
    def _get_grade_tier(self, grade):
        """Determine tier (elite/good/average/below) based on PFF grade"""
        for tier_name, (min_grade, max_grade) in self.grade_tiers.items():
            if min_grade <= grade <= max_grade:
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
    # Example: Test without PFF data (uses 'average' tier)
    assigner = PlayerWeightAssigner()
    
    test_players = [
        {'position_key': 'QB1', 'player_id': 'test1', 'player_name': 'Test QB', 'position': 'QB'},
        {'position_key': 'WR1', 'player_id': 'test2', 'player_name': 'Test WR', 'position': 'WR'},
        {'position_key': 'EDGE1', 'player_id': 'test3', 'player_name': 'Test EDGE', 'position': 'DE'}
    ]
    
    weighted = assigner.assign_weights(test_players, 2024)
    
    print("PlayerWeightAssigner Test:")
    print("=" * 60)
    for player in weighted:
        print(f"{player['position_key']:8} - {player['player_name']:15} - Weight: {player['weight']:.3f} (Tier {player['tier']})")
