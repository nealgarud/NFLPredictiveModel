"""
Test PositionMapper with real Sportradar depth chart data
"""

import requests
from PositionMapper import PositionMapper

API_KEY = "Chc55Ab5gsvTOhwrgZ6n4XuuNZfblx5Js14Pcx9c"
BASE_URL = "https://api.sportradar.com/nfl/official/trial/v7/en"

def test_position_mapper():
    """Test the mapper with real Bengals depth chart data"""
    
    # Get depth chart data
    url = f"{BASE_URL}/seasons/2024/REG/01/depth_charts.json"
    params = {"api_key": API_KEY}
    
    print("Fetching depth chart...")
    response = requests.get(url, params=params)
    data = response.json()
    
    # Find Bengals
    bengals = None
    for team in data['teams']:
        if team['alias'] == 'CIN':
            bengals = team
            break
    
    if not bengals:
        print("Bengals not found!")
        return
    
    print(f"\nFound: {bengals['market']} {bengals['name']}")
    print("=" * 80)
    
    # Create mapper and map positions
    mapper = PositionMapper()
    mapped_positions = mapper.map_team_depth_chart(bengals)
    
    print(f"\nMapped {len(mapped_positions)} total positions\n")
    
    # Show WR mappings
    print("WIDE RECEIVERS:")
    print("-" * 80)
    wrs = [p for p in mapped_positions if 'WR' in p['position_key']]
    for wr in sorted(wrs, key=lambda x: (x['position_key'], x['depth_order'])):
        print(f"  {wr['position_key']:6} (depth {wr['depth_order']}) - {wr['player_name']:25} [{wr['sportradar_position']}]")
    
    # Show EDGE mappings
    print("\nEDGE RUSHERS:")
    print("-" * 80)
    edges = [p for p in mapped_positions if 'EDGE' in p['position_key']]
    for edge in sorted(edges, key=lambda x: (x['position_key'], x['depth_order'])):
        print(f"  {edge['position_key']:6} (depth {edge['depth_order']}) - {edge['player_name']:25} [{edge['sportradar_position']}]")
    
    # Show QB mappings
    print("\nQUARTERBACKS:")
    print("-" * 80)
    qbs = [p for p in mapped_positions if 'QB' in p['position_key']]
    for qb in sorted(qbs, key=lambda x: (x['position_key'], x['depth_order'])):
        print(f"  {qb['position_key']:6} (depth {qb['depth_order']}) - {qb['player_name']:25}")
    
    # Show CBs
    print("\nCORNERBACKS:")
    print("-" * 80)
    cbs = [p for p in mapped_positions if 'CB' in p['position_key']]
    for cb in sorted(cbs, key=lambda x: (x['position_key'], x['depth_order']))[:6]:
        print(f"  {cb['position_key']:6} (depth {cb['depth_order']}) - {cb['player_name']:25} [{cb['sportradar_position']}]")
    
    # Count by position group
    print("\n\nSUMMARY:")
    print("-" * 80)
    offense = [p for p in mapped_positions if p['position_group'] == 'OFFENSE']
    defense = [p for p in mapped_positions if p['position_group'] == 'DEFENSE']
    print(f"Offense positions: {len(offense)}")
    print(f"Defense positions: {len(defense)}")
    print(f"Total: {len(mapped_positions)}")

if __name__ == "__main__":
    test_position_mapper()

