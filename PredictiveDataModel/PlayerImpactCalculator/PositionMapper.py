"""
PositionMapper - Maps raw Sportradar depth chart positions to standardized position keys

Takes: Raw depth chart JSON from Sportradar
Returns: Structured position mappings for each team

Example:
    Input: {"name": "LWR", "depth": 1, "player": "Ja'Marr Chase"}
    Output: {"position_key": "WR1", "player": "Ja'Marr Chase", "depth_order": 1}
"""

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class PositionMapper:
    """Maps Sportradar positions to standardized position keys (QB1, WR2, EDGE1, etc.)"""
    
    def __init__(self):
        """Initialize with position mapping rules"""
        
        # Define which raw positions map to which position groups
        self.OFFENSE_WR_POSITIONS = ['LWR', 'RWR', 'WR']  # Wide receiver variants
        self.OFFENSE_RB_POSITIONS = ['RB', 'FB']          # Running back variants
        self.OFFENSE_TE_POSITIONS = ['TE']                # Tight end
        self.OFFENSE_OL_POSITIONS = ['LT', 'RT', 'LG', 'RG', 'C']  # Offensive line
        
        self.DEFENSE_EDGE_POSITIONS = ['LDE', 'RDE', 'RUSH', 'DE']  # Edge rushers (different names!)
        self.DEFENSE_DT_POSITIONS = ['DT', 'NT', 'LDT', 'RDT']      # Defensive tackles
        self.DEFENSE_LB_POSITIONS = ['MLB', 'WLB', 'SLB', 'LB', 'ILB', 'OLB']  # Linebackers
        self.DEFENSE_CB_POSITIONS = ['LCB', 'RCB', 'CB', 'NB']      # Cornerbacks
        self.DEFENSE_S_POSITIONS = ['FS', 'SS', 'S']                # Safeties
    
    def map_team_depth_chart(self, team_data):
        """
        Map all positions for a single team from raw depth chart
        
        Args:
            team_data (dict): Single team's data from depth chart API
            
        Returns:
            list: Mapped positions with standardized keys
            
        Example team_data structure:
            {
                "alias": "CIN",
                "offense": [{"position": {"name": "LWR", "players": [...]}}],
                "defense": [{"position": {"name": "LDE", "players": [...]}}]
            }
        """
        mapped_positions = []
        team_alias = team_data.get('alias')
        
        logger.info(f"Mapping positions for team: {team_alias}")
        
        # Map offense positions
        mapped_positions.extend(self._map_offense(team_data.get('offense', []), team_alias))
        
        # Map defense positions
        mapped_positions.extend(self._map_defense(team_data.get('defense', []), team_alias))
        
        logger.info(f"Mapped {len(mapped_positions)} positions for {team_alias}")
        
        return mapped_positions
    
    def _map_offense(self, offense_positions, team_alias):
        """Map offensive positions"""
        mapped = []
        
        # Map wide receivers (WR1, WR2, WR3)
        mapped.extend(self._map_wide_receivers(offense_positions))
        
        # Map other offensive positions with simple 1:1 mapping
        simple_offense_map = {
            'QB': 'QB',      # QB depth 1→QB1, depth 2→QB2
            'RB': 'RB',      # RB depth 1→RB1, depth 2→RB2
            'FB': 'FB',
            'TE': 'TE',      # TE depth 1→TE1, depth 2→TE2
            'LT': 'LT',
            'RT': 'RT',
            'LG': 'LG',
            'RG': 'RG',
            'C': 'C'
        }
        
        for pos_group in offense_positions:
            position = pos_group.get('position', {})
            pos_name = position.get('name')
            
            if pos_name in simple_offense_map:
                base_key = simple_offense_map[pos_name]
                players = position.get('players', [])
                
                for player in players:
                    depth = player.get('depth', 1)
                    # Add depth number for positions that have it (QB1, QB2, RB1, RB2, TE1, TE2)
                    if pos_name in ['QB', 'RB', 'TE']:
                        position_key = f"{base_key}{depth}"
                    else:
                        position_key = base_key
                    
                    mapped.append({
                        'position_key': position_key,
                        'sportradar_position': pos_name,
                        'player_id': player.get('id'),
                        'player_name': player.get('name'),
                        'depth_order': depth,
                        'jersey': player.get('jersey'),
                        'position_group': 'OFFENSE'
                    })
        
        return mapped
    
    def _map_defense(self, defense_positions, team_alias):
        """Map defensive positions"""
        mapped = []
        
        # Map edge rushers (EDGE1, EDGE2)
        mapped.extend(self._map_edge_rushers(defense_positions))
        
        # Map other defensive positions with simple mapping
        simple_defense_map = {
            'DT': 'DT',      # DT depth 1→DT1, depth 2→DT2
            'NT': 'NT',
            'LDT': 'DT',     # Left DT → DT
            'RDT': 'DT',     # Right DT → DT
            'MLB': 'LB',     # Middle LB → LB1
            'WLB': 'LB',     # Weak LB → LB
            'SLB': 'LB',     # Strong LB → LB
            'LB': 'LB',
            'ILB': 'LB',
            'OLB': 'LB',
            'LCB': 'CB',     # Left CB → CB
            'RCB': 'CB',     # Right CB → CB
            'CB': 'CB',
            'NB': 'CB',      # Nickel back → CB
            'FS': 'S',       # Free safety → S
            'SS': 'S',       # Strong safety → S
            'S': 'S'
        }
        
        # Track position counters for auto-numbering
        position_counters = {}
        
        for pos_group in defense_positions:
            position = pos_group.get('position', {})
            pos_name = position.get('name')
            
            # Skip edge positions (already handled)
            if pos_name in self.DEFENSE_EDGE_POSITIONS:
                continue
            
            if pos_name in simple_defense_map:
                base_key = simple_defense_map[pos_name]
                players = position.get('players', [])
                
                for player in players:
                    depth = player.get('depth', 1)
                    
                    # Auto-number: DT1, DT2, LB1, LB2, CB1, CB2, S1, S2
                    if base_key not in position_counters:
                        position_counters[base_key] = 0
                    
                    if depth == 1:  # Only number starters
                        position_counters[base_key] += 1
                        position_key = f"{base_key}{position_counters[base_key]}"
                    else:
                        # Backups get base position (e.g., "CB" instead of "CB3")
                        position_key = base_key
                    
                    mapped.append({
                        'position_key': position_key,
                        'sportradar_position': pos_name,
                        'player_id': player.get('id'),
                        'player_name': player.get('name'),
                        'depth_order': depth,
                        'jersey': player.get('jersey'),
                        'position_group': 'DEFENSE'
                    })
        
        return mapped
    
    def _map_wide_receivers(self, offense_positions):
        """
        Map all WR variants (LWR, RWR, WR) to WR1, WR2, WR3
        
        Strategy: Use position priority
        - LWR → WR1
        - RWR → WR2
        - WR (slot) → WR3
        """
        mapped = []
        
        # Position priority mapping
        wr_position_map = {
            'LWR': 'WR1',
            'RWR': 'WR2',
            'WR': 'WR3'
        }
        
        for pos_group in offense_positions:
            position = pos_group.get('position', {})
            pos_name = position.get('name')
            
            # Check if this is a WR position
            if pos_name in wr_position_map:
                position_key = wr_position_map[pos_name]
                players = position.get('players', [])
                
                # Map each player at this position
                for player in players:
                    mapped.append({
                        'position_key': position_key,
                        'sportradar_position': pos_name,
                        'player_id': player.get('id'),
                        'player_name': player.get('name'),
                        'depth_order': player.get('depth'),
                        'jersey': player.get('jersey'),
                        'position_group': 'OFFENSE'
                    })
        
        return mapped
    
    def _map_edge_rushers(self, defense_positions):
        """
        Map all edge rusher variants (LDE, RDE, RUSH, DE) to EDGE1, EDGE2
        
        Strategy: Use position priority
        - LDE or RUSH → EDGE1
        - RDE → EDGE2
        - Generic DE → Sort by depth, assign EDGE1/EDGE2
        """
        mapped = []
        
        # Position priority mapping
        edge_position_map = {
            'LDE': 'EDGE1',
            'RUSH': 'EDGE1',  # Baltimore uses this
            'RDE': 'EDGE2'
        }
        
        # Track if we've assigned EDGE1/EDGE2 already
        edge_assignments = {}
        
        for pos_group in defense_positions:
            position = pos_group.get('position', {})
            pos_name = position.get('name')
            
            # Check if this is an edge position
            if pos_name in self.DEFENSE_EDGE_POSITIONS:
                players = position.get('players', [])
                
                # Get position key from mapping, or handle generic DE
                if pos_name in edge_position_map:
                    position_key = edge_position_map[pos_name]
                elif pos_name == 'DE':
                    # Generic DE - assign EDGE1 if not taken, else EDGE2
                    if 'EDGE1' not in edge_assignments:
                        position_key = 'EDGE1'
                    else:
                        position_key = 'EDGE2'
                else:
                    continue
                
                # Map each player at this position
                for player in players:
                    mapped.append({
                        'position_key': position_key,
                        'sportradar_position': pos_name,
                        'player_id': player.get('id'),
                        'player_name': player.get('name'),
                        'depth_order': player.get('depth'),
                        'jersey': player.get('jersey'),
                        'position_group': 'DEFENSE'
                    })
                    
                    # Track that we've assigned this position
                    if player.get('depth') == 1:
                        edge_assignments[position_key] = True
        
        return mapped


# Test the mapper with real data
if __name__ == "__main__":
    # We can test this with the depth chart data we already fetched
    print("PositionMapper ready for testing")


