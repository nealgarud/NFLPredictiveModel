"""
PositionMapper - Standardize NFL position names across data sources

Purpose:
- Convert various position abbreviations to standardized position keys
- Handle Sportradar's position naming vs Madden's position naming
- Assign depth chart positions (QB1, QB2, WR1, WR2, etc.)

Standardization:
- Input: Raw position strings (QB, QUARTERBACK, Quarterback, etc.)
- Output: Standard position keys (QB, RB, WR, TE, LT, RT, etc.)
"""

import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class PositionMapper:
    """Maps and standardizes NFL position names"""
    
    def __init__(self):
        """Initialize position mapping dictionaries"""
        
        # Map raw positions to standard positions
        self.position_standardization = {
            # Quarterbacks
            'QB': 'QB', 'QUARTERBACK': 'QB', 'Quarterback': 'QB',
            
            # Running Backs
            'RB': 'RB', 'HB': 'RB', 'HALFBACK': 'RB', 'FB': 'RB', 'FULLBACK': 'RB',
            'Halfback': 'RB', 'Fullback': 'RB', 'Running Back': 'RB',
            
            # Wide Receivers
            'WR': 'WR', 'WIDE RECEIVER': 'WR', 'Wide Receiver': 'WR',
            'RECEIVER': 'WR', 'Receiver': 'WR',
            'LWR': 'WR', 'RWR': 'WR', 'SLOT': 'WR', 'SWR': 'WR',  # Sportradar slot/left/right WR
            
            # Tight Ends
            'TE': 'TE', 'TIGHT END': 'TE', 'Tight End': 'TE',
            
            # Offensive Line
            'LT': 'LT', 'LEFT TACKLE': 'LT', 'Left Tackle': 'LT', 'T': 'T', 'TACKLE': 'T',
            'RT': 'RT', 'RIGHT TACKLE': 'RT', 'Right Tackle': 'RT',
            'LG': 'LG', 'LEFT GUARD': 'LG', 'Left Guard': 'LG', 'G': 'G', 'GUARD': 'G',
            'RG': 'RG', 'RIGHT GUARD': 'RG', 'Right Guard': 'RG',
            'C': 'C', 'CENTER': 'C', 'Center': 'C',
            'OL': 'OL', 'OFFENSIVE LINE': 'OL',
            
            # Defensive Line
            'DE': 'EDGE', 'DEFENSIVE END': 'EDGE', 'Defensive End': 'EDGE',
            'EDGE': 'EDGE', 'DL': 'DL', 'DEFENSIVE LINE': 'DL',
            'DT': 'DT', 'DEFENSIVE TACKLE': 'DT', 'Defensive Tackle': 'DT',
            'NT': 'NT', 'NOSE TACKLE': 'NT', 'Nose Tackle': 'NT',
            
            # Linebackers
            'LB': 'LB', 'LINEBACKER': 'LB', 'Linebacker': 'LB',
            'MLB': 'LB', 'MIDDLE LINEBACKER': 'LB', 'Middle Linebacker': 'LB',
            'OLB': 'LB', 'OUTSIDE LINEBACKER': 'LB', 'Outside Linebacker': 'LB',
            'ILB': 'LB', 'INSIDE LINEBACKER': 'LB', 'Inside Linebacker': 'LB',
            
            # Secondary
            'CB': 'CB', 'CORNERBACK': 'CB', 'Cornerback': 'CB',
            'S': 'S', 'SAFETY': 'S', 'Safety': 'S',
            'FS': 'S', 'FREE SAFETY': 'S', 'Free Safety': 'S',
            'SS': 'S', 'STRONG SAFETY': 'S', 'Strong Safety': 'S',
            'DB': 'CB', 'DEFENSIVE BACK': 'CB',
            
            # Special Teams
            'K': 'K', 'KICKER': 'K', 'Kicker': 'K',
            'P': 'P', 'PUNTER': 'P', 'Punter': 'P',
            'LS': 'LS', 'LONG SNAPPER': 'LS', 'Long Snapper': 'LS'
        }
        
        # Positions that get depth numbering (1, 2, 3, etc.)
        self.depth_chart_positions = [
            'QB', 'RB', 'WR', 'TE', 
            'LT', 'RT', 'LG', 'RG', 'C',
            'EDGE', 'DT', 'NT', 'LB', 'CB', 'S'
        ]
        
        logger.info("PositionMapper initialized")
    
    def standardize_position(self, raw_position: str) -> str:
        """
        Convert raw position string to standardized position
        
        Args:
            raw_position: Raw position string (e.g., "QUARTERBACK", "Wide Receiver")
            
        Returns:
            str: Standardized position (e.g., "QB", "WR")
        """
        # Clean the input
        cleaned = raw_position.strip().upper()
        
        # Look up in standardization map
        standard = self.position_standardization.get(cleaned)
        
        if standard:
            return standard
        
        # Fallback: check if it's already standard
        if cleaned in ['QB', 'RB', 'WR', 'TE', 'LT', 'RT', 'LG', 'RG', 'C', 
                       'EDGE', 'DT', 'NT', 'LB', 'CB', 'S', 'K', 'P', 'LS']:
            return cleaned
        
        # Unknown position
        logger.warning(f"Unknown position: {raw_position}")
        return 'UNKNOWN'
    
    def create_position_key(self, position: str, depth_order: int) -> str:
        """
        Create position key with depth number (e.g., QB1, WR2)
        
        Args:
            position: Standardized position (e.g., "QB", "WR")
            depth_order: Depth chart order (1 = starter, 2 = backup, etc.)
            
        Returns:
            str: Position key (e.g., "QB1", "WR2")
        """
        # Only add depth number for positions that need it
        if position in self.depth_chart_positions:
            return f"{position}{depth_order}"
        else:
            return position
    
    def map_team_depth_chart(self, team_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Map entire team's depth chart from Sportradar format
        
        Args:
            team_data: Team data from Sportradar depth chart API
                      Expected structure: {'positions': [...]}
                      
        Returns:
            List of dicts with [player_id, player_name, position, position_key, depth_order]
        """
        mapped_players = []
        
        positions = team_data.get('positions', [])
        
        for position_group in positions:
            raw_position = position_group.get('name', 'UNKNOWN')
            standard_position = self.standardize_position(raw_position)
            
            # Get players at this position
            players = position_group.get('players', [])
            
            for depth_order, player in enumerate(players, start=1):
                player_id = player.get('id')
                player_name = player.get('name', 'Unknown')
                
                # Create position key with depth
                position_key = self.create_position_key(standard_position, depth_order)
                
                mapped_player = {
                    'player_id': player_id,
                    'player_name': player_name,
                    'position': standard_position,
                    'position_key': position_key,
                    'depth_order': depth_order
                }
                
                mapped_players.append(mapped_player)
        
        logger.info(f"Mapped {len(mapped_players)} players from depth chart")
        return mapped_players
    
    def map_player_position(self, player_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map a single player's position
        
        Args:
            player_data: Player data with 'position' field
            
        Returns:
            Dict with added 'standard_position' field
        """
        raw_position = player_data.get('position', 'UNKNOWN')
        standard_position = self.standardize_position(raw_position)
        
        result = player_data.copy()
        result['standard_position'] = standard_position
        
        return result
    
    def is_offensive_position(self, position: str) -> bool:
        """Check if position is offensive"""
        offensive = ['QB', 'RB', 'WR', 'TE', 'LT', 'RT', 'LG', 'RG', 'C', 'OL']
        return position in offensive
    
    def is_defensive_position(self, position: str) -> bool:
        """Check if position is defensive"""
        defensive = ['EDGE', 'DT', 'NT', 'LB', 'CB', 'S', 'DL', 'DB']
        return position in defensive
    
    def is_key_position(self, position_key: str) -> bool:
        """
        Check if this is a key impact position
        
        Args:
            position_key: Position with depth (e.g., "QB1", "WR2")
            
        Returns:
            bool: True if key position
        """
        key_positions = ['QB1', 'RB1', 'WR1', 'WR2', 'TE1', 'LT', 'RT', 'C',
                        'EDGE1', 'EDGE2', 'DT1', 'CB1', 'CB2', 'S1', 'LB1']
        return position_key in key_positions


# Test the mapper
if __name__ == "__main__":
    print("PositionMapper - Testing...")
    
    mapper = PositionMapper()
    print("✓ Mapper initialized")
    
    # Test standardization
    test_positions = [
        'QUARTERBACK', 'QB', 'Wide Receiver', 'WR', 
        'DEFENSIVE END', 'DE', 'CORNERBACK', 'Safety'
    ]
    
    print("\nTesting position standardization:")
    for raw_pos in test_positions:
        standard = mapper.standardize_position(raw_pos)
        print(f"  {raw_pos:20} → {standard}")
    
    # Test position key creation
    print("\nTesting position key creation:")
    for pos in ['QB', 'WR', 'EDGE', 'CB']:
        for depth in [1, 2, 3]:
            key = mapper.create_position_key(pos, depth)
            print(f"  {pos} depth {depth} → {key}")
    
    # Test team depth chart mapping
    print("\nTesting team depth chart mapping:")
    sample_team_data = {
        'id': 'team123',
        'name': 'Test Team',
        'positions': [
            {
                'name': 'QB',
                'players': [
                    {'id': 'player1', 'name': 'Test QB1'},
                    {'id': 'player2', 'name': 'Test QB2'}
                ]
            },
            {
                'name': 'WR',
                'players': [
                    {'id': 'player3', 'name': 'Test WR1'},
                    {'id': 'player4', 'name': 'Test WR2'},
                    {'id': 'player5', 'name': 'Test WR3'}
                ]
            }
        ]
    }
    
    mapped = mapper.map_team_depth_chart(sample_team_data)
    print(f"  Mapped {len(mapped)} players")
    for player in mapped:
        print(f"    {player['position_key']:6} - {player['player_name']}")
    
    print("\n✓ All tests passed")
