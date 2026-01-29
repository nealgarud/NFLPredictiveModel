"""Debug script to see what the game roster API actually returns"""
import requests
import json

API_KEY = "bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm"
BASE_URL = "https://api.sportradar.com/nfl/official/trial/v7/en"
GAME_ID = "b00ae1c5-f3f4-41bb-990f-231d1d8751e5"

# Try to get game roster
url = f"{BASE_URL}/games/{GAME_ID}/roster.json"

headers = {
    "accept": "application/json",
    "x-api-key": API_KEY
}

print(f"Fetching game roster: {url}\n")
response = requests.get(url, headers=headers)

print(f"Status Code: {response.status_code}\n")

if response.status_code == 200:
    data = response.json()
    
    # Pretty print the structure
    print("=== RESPONSE STRUCTURE ===")
    print(json.dumps(data, indent=2)[:3000])  # First 3000 chars
    
    # Check for players
    print("\n\n=== CHECKING FOR PLAYERS ===")
    
    if 'home' in data:
        home = data['home']
        print(f"Home team: {home.get('alias', 'Unknown')}")
        
        if 'players' in home:
            players = home['players']
            print(f"  - Found {len(players)} players")
            if len(players) > 0:
                print(f"  - Sample player keys: {players[0].keys()}")
                print(f"  - Sample player: {json.dumps(players[0], indent=4)}")
        else:
            print("  - NO 'players' key found")
            print(f"  - Available keys: {home.keys()}")
    
    if 'away' in data:
        away = data['away']
        print(f"\nAway team: {away.get('alias', 'Unknown')}")
        
        if 'players' in away:
            players = away['players']
            print(f"  - Found {len(players)} players")
            if len(players) > 0:
                print(f"  - Sample player keys: {players[0].keys()}")
                print(f"  - Sample player: {json.dumps(players[0], indent=4)}")
        else:
            print("  - NO 'players' key found")
            print(f"  - Available keys: {away.keys()}")
    
else:
    print(f"Error: {response.status_code}")
    print(response.text)

