"""
Debug script to trace spread range calculations
"""

def get_spread_range(spread):
    """Categorize spread into range"""
    if spread <= 2:
        return "0-2"
    elif spread <= 4:
        return "2-4"
    elif spread <= 7:
        return "4-7"
    elif spread <= 10:
        return "7-10"
    else:
        return "10+"

# Test cases from user
test_cases = [
    ("GB -1.5 @ HOU", -1.5, "GB", "HOU", False),
    ("GB -3.5 @ HOU", -3.5, "GB", "HOU", False),
]

for desc, spread, team_a, team_b, team_a_home in test_cases:
    print(f"\n{'='*60}")
    print(f"Test: {desc}")
    print(f"{'='*60}")
    
    # Determine roles
    if spread < 0:
        favored_team = team_a
        underdog_team = team_b
        favored_home = team_a_home
    else:
        favored_team = team_b
        underdog_team = team_a
        favored_home = not team_a_home
    
    spread_abs = abs(spread)
    spread_range = get_spread_range(spread_abs)
    
    # Parse spread range
    if spread_range == "10+":
        min_spread, max_spread = 10, 100
    else:
        parts = spread_range.split('-')
        min_spread = int(float(parts[0]))
        max_spread = int(float(parts[1]))
    
    print(f"\nInput:")
    print(f"  team_a: {team_a} (away)")
    print(f"  team_b: {team_b} (home)")
    print(f"  spread: {spread}")
    print(f"  team_a_home: {team_a_home}")
    
    print(f"\nDerived:")
    print(f"  favored_team: {favored_team}")
    print(f"  underdog_team: {underdog_team}")
    print(f"  favored_home: {favored_home}")
    print(f"  spread_abs: {spread_abs}")
    print(f"  spread_range: {spread_range}")
    print(f"  min_spread: {min_spread}")
    print(f"  max_spread: {max_spread}")
    
    # Favored team query (away favorite)
    favored_location = "home" if favored_home else "away"
    print(f"\nFavored Team Query ({favored_team} as {favored_location} favorite):")
    if favored_location == "away":
        print(f"  Query: WHERE away_team = '{favored_team}'")
        print(f"         AND ABS(spread_line) BETWEEN {min_spread} AND {max_spread}")
        print(f"         AND spread_line < 0")
        print(f"  This will match games where {favored_team} is away favorite with spread {min_spread} to {max_spread}")
    
    # Underdog team query (home underdog)
    underdog_location = "away" if favored_home else "home"
    print(f"\nUnderdog Team Query ({underdog_team} as {underdog_location} underdog):")
    if underdog_location == "home":
        print(f"  Query: WHERE home_team = '{underdog_team}'")
        print(f"         AND ABS(spread_line) BETWEEN {min_spread} AND {max_spread}")
        print(f"         AND spread_line < 0")
        print(f"  This will match games where {underdog_team} is home underdog with spread {min_spread} to {max_spread}")

print("\n" + "="*60)
print("ANALYSIS")
print("="*60)
print("\nBoth queries are looking for the SAME spread range!")
print("This is CORRECT - we want to compare how teams perform in similar situations.")
print("\nThe issue might be:")
print("1. Not enough data in database for these specific situations")
print("2. The normalization is creating weird probabilities")
print("3. Other factors (Overall ATS, Home/Away) are dominating the calculation")



