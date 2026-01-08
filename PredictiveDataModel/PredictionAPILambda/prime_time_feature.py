import pandas as pd
import numpy as np
from DatabaseConnection import DatabaseConnection

# Connect to database
db = DatabaseConnection()
conn = db.get_connection()

# SQL Query
query = """
    SELECT 
        game_id,
        season,
        week,
        gameday,
        home_team,
        away_team,
        home_score,
        away_score,
        spread_line
    FROM games 
    WHERE season = 2024 
        AND game_type = 'REG'
        AND spread_line IS NOT NULL
        AND home_score IS NOT NULL
        AND away_score IS NOT NULL
    ORDER BY gameday
"""

# Run query
rows = conn.run(query)

# Convert to DataFrame
columns = ['game_id', 'season', 'week', 'gameday', 
           'home_team', 'away_team', 'home_score', 
           'away_score', 'spread_line']

games_df = pd.DataFrame(rows, columns=columns)

print(f"✅ Loaded {len(games_df)} games")
print(games_df.head())

# Convert gameday to datetime
games_df['gameday'] = pd.to_datetime(games_df['gameday'])

# Extract day and hour
games_df['day_of_week'] = games_df['gameday'].dt.day_name()
games_df['hour'] = games_df['gameday'].dt.hour

# Classify game type
games_df['game_type'] = np.where(
    games_df['day_of_week'] == 'Thursday',
    'TNF',
    np.where(
        (games_df['day_of_week'] == 'Sunday') & (games_df['hour'] >= 20),  # ← Both conditions
        'SNF',
        np.where(
            games_df['day_of_week'] == 'Monday',  # ← Comma was missing
            'MNF',
            'Regular'
        )
    )
)

# Boolean flag
games_df['is_prime_time'] = games_df['game_type'] != 'Regular'

# Verify results
print("\n✅ Game type breakdown:")
print(games_df['game_type'].value_counts())
print(f"\nPrime time games: {games_df['is_prime_time'].sum()}")

# Create perspectives
home_games = games_df.copy()
home_games['team'] = home_games['home_team']  # Fixed: no 's'
home_games['wins'] = home_games['home_score'] > home_games['away_score']

away_games = games_df.copy()
away_games['team'] = away_games['away_team']  # Fixed: no 's'
away_games['wins'] = away_games['away_score'] > away_games['home_score']  # Fixed: away_games not home_games

# Combine
all_games = pd.concat([home_games, away_games], ignore_index=True)

# Filter prime time
prime_time_games = all_games[all_games['is_prime_time'] == True]  # Can use == True or == 1

# Aggregate by team
prime_time_stats = prime_time_games.groupby('team').agg({
    'wins': ['sum', 'count']  # Fixed: aggregate 'wins', not 'won' and 'games'
}).reset_index()  # Fixed: added reset_index()

# Rename columns
prime_time_stats.columns = ['team', 'wins', 'games']  # Fixed: matches agg output

# Calculate win rate
prime_time_stats['win_rate'] = prime_time_stats['wins'] / prime_time_stats['games']

# Print results
print("\n📊 Prime Time Win Rates (Top 10):")
print(prime_time_stats.sort_values('win_rate', ascending=False).head(10))