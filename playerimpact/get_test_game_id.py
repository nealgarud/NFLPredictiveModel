"""
Helper script to fetch a valid game_id for testing the playerimpact Lambda
"""

import os
import sys
from SportradarClient import SportradarClient

def get_recent_game_id():
    """Fetch a recent game ID for testing"""
    
    # Initialize Sportradar client (will use SPORTRADAR_API_KEY env var)
    client = SportradarClient()
    
    # Get 2024 season schedule for Week 18 (Final regular season week)
    print("Fetching 2024 season Week 18 schedule...")
    schedule = client.get_weekly_schedule(season=2024, week=18, season_type='REG')
    
    # Extract games
    weeks = schedule.get('weeks', [])
    if len(weeks) == 0:
        print("No weeks found in schedule")
        return None
    
    games = weeks[0].get('games', [])
    if len(games) == 0:
        print("No games found in week")
        return None
    
    print(f"\nFound {len(games)} game(s) in 2024 Week 18 (Regular Season):\n")
    
    for i, game in enumerate(games, 1):
        game_id = game.get('id')
        home = game.get('home', {})
        away = game.get('away', {})
        
        home_alias = home.get('alias', 'UNK')
        away_alias = away.get('alias', 'UNK')
        
        scheduled = game.get('scheduled', 'Unknown date')
        
        print(f"{i}. {away_alias} @ {home_alias}")
        print(f"   Game ID: {game_id}")
        print(f"   Scheduled: {scheduled}")
        print()
    
    # Return the first game ID for testing
    first_game_id = games[0].get('id')
    first_away = games[0].get('away', {}).get('alias', 'UNK')
    first_home = games[0].get('home', {}).get('alias', 'UNK')
    
    print(f"Use this test event:")
    print(f"""
{{
  "game_id": "{first_game_id}",
  "season": 2024
}}
    """)
    
    print(f"Game: {first_away} @ {first_home}")
    
    return first_game_id


if __name__ == "__main__":
    # Check for API key
    if not os.environ.get('SPORTRADAR_API_KEY'):
        print("ERROR: SPORTRADAR_API_KEY environment variable not set")
        print("\nSet it with:")
        print('$env:SPORTRADAR_API_KEY = "your-api-key-here"')
        sys.exit(1)
    
    try:
        game_id = get_recent_game_id()
        if game_id:
            print(f"\nSuccess! Game ID: {game_id}")
        else:
            print("\nFailed to get game ID")
            sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

