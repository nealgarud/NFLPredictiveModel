"""
Test the player profile API to see what stats we can use for ranking
We'll test with known players to see what data is available
"""

import requests
import json

API_KEY = "Chc55Ab5gsvTOhwrgZ6n4XuuNZfblx5Js14Pcx9c"
BASE_URL = "https://api.sportradar.com/nfl/official/trial/v7/en"

def get_player_profile(player_id, player_name):
    """Get detailed profile for a specific player"""
    url = f"{BASE_URL}/players/{player_id}/profile.json"
    params = {"api_key": API_KEY}
    
    print("=" * 80)
    print(f"PLAYER PROFILE: {player_name}")
    print("=" * 80)
    print(f"URL: {url}\n")
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Show top-level keys
        print(f"Top-level keys: {list(data.keys())}\n")
        
        # Show basic info
        if 'name' in data:
            print(f"Name: {data.get('name')}")
        if 'position' in data:
            print(f"Position: {data.get('position')}")
        if 'jersey' in data:
            print(f"Jersey: #{data.get('jersey')}")
        
        # Check for stats
        if 'seasons' in data:
            print(f"\nSeasons available: {len(data['seasons'])}")
            # Show most recent season stats
            if data['seasons']:
                recent = data['seasons'][-1]
                print(f"\nMost recent season: {recent.get('year')} {recent.get('type')}")
                
                # Look for receiving stats
                if 'teams' in recent:
                    for team in recent['teams']:
                        print(f"\nTeam: {team.get('market')} {team.get('name')}")
                        if 'statistics' in team:
                            stats = team['statistics']
                            if 'receiving' in stats:
                                rec = stats['receiving']
                                print(f"\nReceiving Stats:")
                                print(f"  Targets: {rec.get('targets', 0)}")
                                print(f"  Receptions: {rec.get('receptions', 0)}")
                                print(f"  Yards: {rec.get('yards', 0)}")
                                print(f"  TDs: {rec.get('touchdowns', 0)}")
                                print(f"  Avg: {rec.get('avg_yards', 0):.1f}")
        
        # Print full structure for first player
        if player_name == "First Player":
            print("\n\nFULL JSON STRUCTURE:")
            print(json.dumps(data, indent=2))
        
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    
    print("\n")

# First, let's get some player IDs from the depth chart
def get_bengals_wr_ids():
    """Get Bengals WR player IDs from depth chart"""
    url = f"{BASE_URL}/seasons/2024/REG/01/depth_charts.json"
    params = {"api_key": API_KEY}
    
    response = requests.get(url, params=params)
    data = response.json()
    
    # Find Bengals
    for team in data['teams']:
        if team['alias'] == 'CIN':
            print("Found Bengals WRs in depth chart:")
            print("=" * 80)
            wrs = []
            for pos_group in team['offense']:
                position = pos_group['position']
                pos_name = position['name']
                if 'WR' in pos_name:
                    print(f"\n{pos_name}:")
                    for player in position['players'][:2]:  # Top 2 per position
                        print(f"  {player['name']} (ID: {player['id']}, depth: {player['depth']})")
                        wrs.append({
                            'id': player['id'],
                            'name': player['name'],
                            'position': pos_name,
                            'depth': player['depth']
                        })
            print("\n")
            return wrs
    return []

if __name__ == "__main__":
    # Get Bengals WR IDs
    bengals_wrs = get_bengals_wr_ids()
    
    if bengals_wrs:
        print(f"\nFound {len(bengals_wrs)} WRs. Testing player profile API...\n")
        
        # Test with first 3 WRs
        for wr in bengals_wrs[:3]:
            get_player_profile(wr['id'], wr['name'])
            print("\n" + "="*80 + "\n")
    else:
        print("Could not find Bengals WRs")



