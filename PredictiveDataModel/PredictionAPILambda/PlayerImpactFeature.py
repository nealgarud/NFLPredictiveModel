"""
PlayerImpactFeature - Calculate player impact ratings from Madden data for predictions

Integrates with NFL Prediction Lambda to add player-level injury/rating impact to spread predictions.

This module:
1. Loads Madden ratings from S3
2. Calculates player weights based on position and rating
3. Computes team-level impact scores for games
4. Returns impact differential as a prediction feature
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Optional, Tuple
import sys
import os

# Add PlayerImpactCalculator to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'PlayerImpactCalculator'))

from S3DataLoader import S3DataLoader
from PlayerWeightAssigner import PlayerWeightAssigner
from PositionMapper import PositionMapper

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class PlayerImpactFeature:
    """
    Calculate player impact feature for spread predictions
    
    Uses Madden ratings to weight player importance and calculate
    team strength based on available/injured players.
    """
    
    def __init__(self, bucket_name: str = 'player-data-nfl-predictive-model'):
        """
        Initialize with S3 bucket for player/Madden data
        
        Args:
            bucket_name: S3 bucket containing player data CSVs
                        Default: player-data-nfl-predictive-model
        """
        self.bucket_name = bucket_name
        self.s3_loader = S3DataLoader(bucket_name=bucket_name)
        
        # Cache for loaded data
        self._madden_df: Optional[pd.DataFrame] = None
        self._player_weights: Dict[str, Dict] = {}  # {player_id: {weight, tier, position}}
        self._team_rosters: Dict[str, list] = {}  # {team_abbr: [player_dicts]}
        
        logger.info(f"PlayerImpactFeature initialized (bucket: {bucket_name})")
    
    def load_madden_ratings(self, season: int = 2025, force_reload: bool = False) -> pd.DataFrame:
        """
        Load Madden ratings from S3
        
        Args:
            season: Season year
            force_reload: Force reload even if cached
            
        Returns:
            DataFrame with Madden ratings
        """
        if self._madden_df is not None and not force_reload:
            logger.info("Using cached Madden ratings")
            return self._madden_df
        
        logger.info(f"Loading Madden ratings for {season} from S3...")
        self._madden_df = self.s3_loader.load_madden_ratings(season=season)
        logger.info(f"✓ Loaded {len(self._madden_df)} player ratings")
        
        return self._madden_df
    
    def calculate_player_weights(self, season: int = 2025) -> Dict[str, Dict]:
        """
        Calculate weights for all players based on Madden ratings
        
        Args:
            season: Season year
            
        Returns:
            Dict mapping player_id to {weight, tier, position, rating}
        """
        # Load Madden data
        madden_df = self.load_madden_ratings(season)
        
        if madden_df.empty:
            logger.warning("No Madden data available, using default weights")
            return {}
        
        # Initialize weight assigner
        weight_assigner = PlayerWeightAssigner(madden_data=madden_df)
        position_mapper = PositionMapper()
        
        logger.info("Calculating player weights...")
        player_weights = {}
        
        for idx, row in madden_df.iterrows():
            try:
                # Get player info
                player_id = row.get('player_id', f'unknown_{idx}')
                player_name = row.get('player_name', 'Unknown')
                raw_position = row.get('position', 'UNKNOWN')
                madden_rating = row.get('overallrating', 70)
                team = row.get('team', 'UNK')
                
                # Standardize position
                standard_position = position_mapper.standardize_position(raw_position)
                
                # Assume depth_order = 1 for now (starters)
                # In real scenario, get from depth chart
                position_key = position_mapper.create_position_key(standard_position, 1)
                
                # Create player dict for weight assignment
                player_dict = {
                    'player_id': player_id,
                    'player_name': player_name,
                    'position': standard_position,
                    'position_key': position_key,
                    'depth_order': 1
                }
                
                # Calculate weight
                weighted_players = weight_assigner.assign_weights([player_dict])
                
                if weighted_players:
                    weighted = weighted_players[0]
                    player_weights[player_id] = {
                        'player_name': player_name,
                        'weight': weighted['weight'],
                        'tier': weighted['tier'],
                        'position': standard_position,
                        'position_key': position_key,
                        'rating': madden_rating,
                        'team': team
                    }
            
            except Exception as e:
                logger.warning(f"Error processing player {row.get('player_name', 'Unknown')}: {e}")
                continue
        
        self._player_weights = player_weights
        logger.info(f"✓ Calculated weights for {len(player_weights)} players")
        
        return player_weights
    
    def get_team_impact_score(self, team_abbr: str, season: int = 2025) -> float:
        """
        Calculate total impact score for a team based on player ratings
        
        Args:
            team_abbr: Team abbreviation (e.g., 'KC', 'GB')
            season: Season year
            
        Returns:
            float: Team impact score (sum of player weights)
        """
        # Ensure weights are calculated
        if not self._player_weights:
            self.calculate_player_weights(season)
        
        # Sum weights for all players on this team
        team_score = 0.0
        player_count = 0
        
        for player_id, player_data in self._player_weights.items():
            if player_data['team'].upper() == team_abbr.upper():
                team_score += player_data['weight']
                player_count += 1
        
        logger.info(f"Team {team_abbr}: {player_count} players, impact score = {team_score:.2f}")
        return team_score
    
    def get_position_group_impact(self, team_abbr: str, position_group: str, season: int = 2025) -> float:
        """
        Calculate impact score for a specific position group
        
        Args:
            team_abbr: Team abbreviation
            position_group: 'offense', 'defense', or specific position
            season: Season year
            
        Returns:
            float: Position group impact score
        """
        if not self._player_weights:
            self.calculate_player_weights(season)
        
        # Define position groups
        offensive_positions = ['QB', 'RB', 'WR', 'TE', 'LT', 'RT', 'LG', 'RG', 'C', 'OL']
        defensive_positions = ['EDGE', 'DT', 'NT', 'LB', 'CB', 'S', 'DL', 'DB']
        
        score = 0.0
        for player_id, player_data in self._player_weights.items():
            if player_data['team'].upper() != team_abbr.upper():
                continue
            
            position = player_data['position']
            
            if position_group.lower() == 'offense' and position in offensive_positions:
                score += player_data['weight']
            elif position_group.lower() == 'defense' and position in defensive_positions:
                score += player_data['weight']
            elif position_group.upper() == position:
                score += player_data['weight']
        
        return score
    
    def calculate_impact_differential(
        self, 
        team_a: str, 
        team_b: str, 
        season: int = 2025,
        normalize: bool = True
    ) -> Dict:
        """
        Calculate player impact differential between two teams
        
        This is the KEY METHOD for prediction integration.
        Returns impact advantage for team_a vs team_b.
        
        Args:
            team_a: Team A abbreviation
            team_b: Team B abbreviation
            season: Season year
            normalize: Normalize to 0-1 range
            
        Returns:
            Dict with impact scores and differential
        """
        # Get team impact scores
        team_a_score = self.get_team_impact_score(team_a, season)
        team_b_score = self.get_team_impact_score(team_b, season)
        
        # Calculate raw differential
        raw_differential = team_a_score - team_b_score
        
        # Calculate by position groups
        team_a_offense = self.get_position_group_impact(team_a, 'offense', season)
        team_b_offense = self.get_position_group_impact(team_b, 'offense', season)
        
        team_a_defense = self.get_position_group_impact(team_a, 'defense', season)
        team_b_defense = self.get_position_group_impact(team_b, 'defense', season)
        
        # Normalize if requested (scale to roughly -1 to +1)
        if normalize:
            # Average team score is around 15-20, so divide by 20
            normalized_differential = raw_differential / 20.0
        else:
            normalized_differential = raw_differential
        
        result = {
            'team_a': team_a,
            'team_b': team_b,
            'team_a_total_impact': team_a_score,
            'team_b_total_impact': team_b_score,
            'team_a_offense': team_a_offense,
            'team_b_offense': team_b_offense,
            'team_a_defense': team_a_defense,
            'team_b_defense': team_b_defense,
            'raw_differential': raw_differential,
            'normalized_differential': normalized_differential,
            'advantage': 'team_a' if raw_differential > 0 else 'team_b' if raw_differential < 0 else 'neutral'
        }
        
        logger.info(f"Impact Differential: {team_a} vs {team_b}")
        logger.info(f"  {team_a}: {team_a_score:.2f} | {team_b}: {team_b_score:.2f}")
        logger.info(f"  Differential: {raw_differential:.2f} (normalized: {normalized_differential:.2f})")
        logger.info(f"  Advantage: {result['advantage']}")
        
        return result
    
    def get_top_players_by_team(self, team_abbr: str, top_n: int = 10, season: int = 2025) -> list:
        """
        Get top N players by weight for a team
        
        Args:
            team_abbr: Team abbreviation
            top_n: Number of top players to return
            season: Season year
            
        Returns:
            List of player dicts sorted by weight (descending)
        """
        if not self._player_weights:
            self.calculate_player_weights(season)
        
        # Filter by team
        team_players = [
            {**player_data, 'player_id': player_id}
            for player_id, player_data in self._player_weights.items()
            if player_data['team'].upper() == team_abbr.upper()
        ]
        
        # Sort by weight
        team_players.sort(key=lambda x: x['weight'], reverse=True)
        
        return team_players[:top_n]
    
    def get_feature_for_prediction(
        self, 
        team_a: str, 
        team_b: str, 
        season: int = 2025
    ) -> float:
        """
        Get normalized player impact feature for prediction model
        
        This returns a single float value that can be added to your
        spread prediction formula.
        
        Args:
            team_a: Team A abbreviation
            team_b: Team B abbreviation
            season: Season year
            
        Returns:
            float: Normalized impact differential (-1 to +1)
                  Positive = team_a advantage
                  Negative = team_b advantage
        """
        result = self.calculate_impact_differential(team_a, team_b, season, normalize=True)
        return result['normalized_differential']


# Test the feature
if __name__ == "__main__":
    print("PlayerImpactFeature - Testing...")
    
    try:
        feature = PlayerImpactFeature(bucket_name='sportsdatacollection')
        print("✓ Feature initialized")
        
        # Load and calculate weights
        print("\nCalculating player weights from Madden ratings...")
        weights = feature.calculate_player_weights(season=2025)
        print(f"✓ Calculated {len(weights)} player weights")
        
        # Test team impact
        print("\nCalculating team impact scores...")
        team_a = 'KC'
        team_b = 'GB'
        
        result = feature.calculate_impact_differential(team_a, team_b, season=2025)
        
        print(f"\n{team_a} vs {team_b}:")
        print(f"  {team_a} Impact: {result['team_a_total_impact']:.2f}")
        print(f"  {team_b} Impact: {result['team_b_total_impact']:.2f}")
        print(f"  Differential: {result['normalized_differential']:.3f}")
        print(f"  Advantage: {result['advantage']}")
        
        # Show top players
        print(f"\nTop 5 players for {team_a}:")
        top_players = feature.get_top_players_by_team(team_a, top_n=5)
        for i, player in enumerate(top_players, 1):
            print(f"  {i}. {player['player_name']:20} ({player['position_key']:6}) - Weight: {player['weight']:.3f}, Rating: {player['rating']}")
        
        print("\n✓ Test complete!")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


# Lambda Handler for AWS Lambda deployment
import json

# Global instance for Lambda container reuse
_feature_instance = None

def lambda_handler(event, context):
    """
    AWS Lambda handler for PlayerImpactFeature
    
    Event structure:
    {
        "team_a": "KC",
        "team_b": "GB",
        "season": 2025
    }
    
    Returns:
    {
        "statusCode": 200,
        "body": {
            "success": true,
            "data": {...}
        }
    }
    """
    global _feature_instance
    
    try:
        # Initialize on cold start (reuse across warm invocations)
        if _feature_instance is None:
            logger.info("Cold start - Initializing PlayerImpactFeature...")
            _feature_instance = PlayerImpactFeature(bucket_name='player-data-nfl-predictive-model')
            _feature_instance.calculate_player_weights(season=2025)
            logger.info("✓ Feature initialized with player weights cached")
        else:
            logger.info("Warm start - Using cached feature instance")
        
        # Parse event
        team_a = event.get('team_a')
        team_b = event.get('team_b')
        season = event.get('season', 2025)
        
        # Validate input
        if not team_a or not team_b:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'success': False,
                    'error': 'team_a and team_b are required parameters'
                })
            }
        
        logger.info(f"Calculating impact: {team_a} vs {team_b} (Season {season})")
        
        # Calculate impact differential
        result = _feature_instance.calculate_impact_differential(
            team_a=team_a.upper(),
            team_b=team_b.upper(),
            season=season,
            normalize=True
        )
        
        logger.info(f"✓ Impact calculated: {result['advantage']} has advantage ({result['normalized_differential']:.3f})")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'data': result
            })
        }
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }

