import pandas as pd
import numpy as np
from DatabaseConnection import DatabaseConnection

# Connect to database
db = DatabaseConnection()
conn = db.get_connection()

# SQL Query (your simplified version)
query = """
SELECT 
    season,
    week,
    home_team,
    away_team,
    home_score,
    away_score,
    spread_line
FROM games
WHERE (home_team = :team OR away_team = :team)
  AND game_type = 'REG'
  AND home_score IS NOT NULL
  AND spread_line IS NOT NULL
  AND season = ANY(:seasons)
ORDER BY season ASC, week ASC
"""

# Test with a team
team = 'KC'
seasons = [2024, 2025]

# Run query
data = conn.run(query, team=team, seasons=seasons)
df = pd.DataFrame(data, columns=['season', 'week', 'home_team', 'away_team', 'home_score', 'away_score', 'spread_line'])

print(f"✅ Team: {team}")
print(f"✅ Loaded {len(df)} games")
print(df.head())


df['was_home'] = np.where(df['home_team'] == team, True, False)

df['points_scored'] = np.where(df['was_home'], df['home_score'],df['away_score'])

df['opponent_scored'] = np.where(df['was_home'], df['away_score'],df['home_score'])

df['margin'] = df['points_scored']- df['opponent_scored']

df['team_spread'] = np.where(df['was_home'], df['spread_line'], -df['spread_line'])

df['ats_covered'] = np.where(df['margin']> df['team_spread'], 1, 0)

df['is_close_game'] = np.where(np.abs(df['spread_line']) <3, True,False)


filtered_games = df[df['ats_covered'].notna()]

close_game = filtered_games[filtered_games['is_close_game'] == True]
not_close_game = filtered_games[filtered_games['is_close_game'] == False]

close_game_ats_rate = close_game['ats_covered'].mean() if len(close_game) > 0 else 0.5
not_close_game_ats_rate = not_close_game['ats_covered'].mean() if len(not_close_game) > 0 else 0.5