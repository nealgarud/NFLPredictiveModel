"""
Test script to explore Sportradar API responses
Run this to see what data we're actually working with
"""

import requests
import json

# Your API key
API_KEY = "Chc55Ab5gsvTOhwrgZ6n4XuuNZfblx5Js14Pcx9c"
BASE_URL = "https://api.sportradar.com/nfl/official/trial/v7/en"

# Let's test the depth chart endpoint for 2024 season, week 1
def test_depth_chart():
    print("=" * 60)
    print("Testing: DEPTH CHART Endpoint")
    print("=" * 60)
    
    url = f"{BASE_URL}/seasons/2024/REG/01/depth_charts.json"
    params = {"api_key": API_KEY}
    
    print(f"URL: {url}")
    print(f"Making request...\n")
    
    response = requests.get(url, params=params)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        # Pretty print the first team to see structure
        print("\n" + "=" * 60)
        print("SUCCESS! Here's what we got back:")
        print("=" * 60)
        
        # Show the top-level keys
        print(f"\nTop-level keys: {list(data.keys())}")
        
        # If there's a teams array, show the first team
        if 'teams' in data:
            print(f"\nNumber of teams: {len(data['teams'])}")
            print("\nFirst team structure:")
            print(json.dumps(data['teams'][0], indent=2))
        else:
            print("\nFull response:")
            print(json.dumps(data, indent=2))
            
    else:
        print(f"ERROR: {response.status_code}")
        print(f"Response: {response.text}")

if __name__ == "__main__":
    test_depth_chart()
    
    print("\n\n" + "=" * 60)
    print("QUESTIONS TO DISCUSS:")
    print("=" * 60)
    print("1. What fields do we see in the response?")
    print("2. How are players organized? (by team? by position?)")
    print("3. What's the depth_order or ranking system?")
    print("4. Do we see position names like 'QB', 'WR', 'DE'?")
    print("5. What's the player ID format? (UUID?)")

