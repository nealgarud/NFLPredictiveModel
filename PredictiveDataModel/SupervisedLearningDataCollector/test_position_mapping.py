"""
Test script to explore position mapping across different teams
This helps us understand how to map Sportradar positions to standardized keys
"""

import requests
import json

API_KEY = "Chc55Ab5gsvTOhwrgZ6n4XuuNZfblx5Js14Pcx9c"
BASE_URL = "https://api.sportradar.com/nfl/official/trial/v7/en"

def get_team_positions(team_alias):
    """Get positions for a specific team from depth chart"""
    url = f"{BASE_URL}/seasons/2024/REG/01/depth_charts.json"
    params = {"api_key": API_KEY}
    
    response = requests.get(url, params=params)
    data = response.json()
    
    # Find the team
    for team in data['teams']:
        if team['alias'] == team_alias:
            return team
    return None

def show_team_offense(team_alias):
    """Show offensive positions for a team"""
    print("=" * 80)
    print(f"TEAM: {team_alias}")
    print("=" * 80)
    
    team = get_team_positions(team_alias)
    if not team:
        print(f"Team {team_alias} not found")
        return
    
    print(f"\n{team['market']} {team['name']}\n")
    
    # Show offense positions
    print("OFFENSIVE POSITIONS:")
    print("-" * 80)
    for pos_group in team['offense']:
        position = pos_group['position']
        pos_name = position['name']
        players = position['players']
        
        print(f"\n{pos_name}:")
        for player in players[:3]:  # Show top 3
            depth = player.get('depth', '?')
            name = player.get('name', 'Unknown')
            print(f"  {depth}. {name}")
    
    # Show defense positions
    print("\n\nDEFENSIVE POSITIONS:")
    print("-" * 80)
    for pos_group in team['defense']:
        position = pos_group['position']
        pos_name = position['name']
        players = position['players']
        
        print(f"\n{pos_name}:")
        for player in players[:3]:  # Show top 3
            depth = player.get('depth', '?')
            name = player.get('name', 'Unknown')
            print(f"  {depth}. {name}")

if __name__ == "__main__":
    # Let's look at a few different teams to see patterns
    
    teams_to_check = [
        'KC',   # Kansas City Chiefs (known for Mahomes)
        'BAL',  # Baltimore Ravens (known for Lamar Jackson)
        'SF',   # San Francisco 49ers
        'BUF'   # Buffalo Bills (known for Josh Allen)
    ]
    
    for team in teams_to_check:
        show_team_offense(team)
        print("\n\n")

