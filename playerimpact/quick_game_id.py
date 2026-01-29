"""Quick script to get a game ID"""
import requests
import json

API_KEY = "bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm"
BASE_URL = "https://api.sportradar.com/nfl/official/trial/v7/en"

# Get full 2024 regular season schedule
url = f"{BASE_URL}/games/2024/REG/schedule.json"

headers = {
    "accept": "application/json",
    "x-api-key": API_KEY
}

print(f"Fetching: {url}")
response = requests.get(url, headers=headers)

if response.status_code == 200:
    data = response.json()
    
    # Get weeks
    weeks = data.get('weeks', [])
    
    if len(weeks) > 0:
        # Get last week with games
        last_week = weeks[-1]
        week_num = last_week.get('sequence', 'Unknown')
        games = last_week.get('games', [])
        
        if len(games) > 0:
            first_game = games[0]
            game_id = first_game['id']
            home = first_game['home']['alias']
            away = first_game['away']['alias']
            
            print(f"\nFound game from Week {week_num}:")
            print(f"  {away} @ {home}")
            print(f"  Game ID: {game_id}")
            print(f"\nTest Event:")
            print(json.dumps({
                "game_id": game_id,
                "season": 2024
            }, indent=2))
        else:
            print("No games found")
    else:
        print("No weeks found")
else:
    print(f"Error: {response.status_code}")
    print(response.text)

