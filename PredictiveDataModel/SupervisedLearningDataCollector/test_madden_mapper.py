"""
Test MaddenRatingMapper with real Madden data
"""

import pandas as pd
from MaddenRatingMapper import MaddenRatingMapper

# Load real Madden data
madden_df = pd.read_parquet('c:/Users/nealg/Downloads/2022.parquet')

print("Loaded Madden data:")
print(f"Total players: {len(madden_df)}")
print(f"Columns: {madden_df.columns.tolist()[:5]}...\n")

# Create mapper
mapper = MaddenRatingMapper(madden_df)

# Test with some example players
test_cases = [
    ('00-0033873', 'QB1', 'Patrick Mahomes'),  # Elite QB
    ('00-0036355', 'QB1', 'Bryce Young'),      # Below average QB
    ('00-0035704', 'WR1', "Ja'Marr Chase"),    # Elite WR
    ('00-0036945', 'EDGE1', 'Micah Parsons'),  # Elite EDGE
]

print("=" * 80)
print("Testing MaddenRatingMapper:")
print("=" * 80)

for player_id, position_key, name in test_cases:
    # Get player's actual rating from DataFrame
    player_row = madden_df[madden_df['player_id'] == player_id]
    
    if len(player_row) > 0:
        actual_rating = player_row['overallrating'].values[0]
        
        # Calculate adjusted weight
        weight = mapper.calculate_adjusted_weight(player_id, position_key)
        
        print(f"\n{name} ({position_key}):")
        print(f"  Madden Rating: {actual_rating}")
        print(f"  Adjusted Weight: {weight:.3f}")
        print(f"  Base Weight: {mapper.base_position_weights.get(position_key, 0.0):.3f}")
    else:
        print(f"\n{name}: Not found in Madden data")

print("\n" + "=" * 80)


