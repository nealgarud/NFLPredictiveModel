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
        away_score
    FROM games 
    WHERE season = 2024 
        AND game_type = 'REG'
        AND home_score IS NOT NULL
        AND away_score IS NOT NULL
    ORDER BY gameday, game_id
"""

# Run query
rows = conn.run(query)

# Convert to DataFrame
columns = ['game_id', 'season', 'week', 'gameday', 
           'home_team', 'away_team', 'home_score', 'away_score']

games_df = pd.DataFrame(rows, columns=columns)

print(f"✅ Loaded {len(games_df)} games")
print(games_df.head())

# =====================
# YOUR PANDAS CODE BELOW
# =====================

#HOME PERSPECTIVE
home_games = games_df.copy()
home_games['team'] = games_df['home_team']
home_games['gameday'] = games_df['gameday']
home_games['won'] = games_df['home_score']> games_df['away_score']

#AWAY PERSPECTIVE
away_games = games_df.copy()
away_games['team'] = games_df['away_team']
away_games['gameday'] = games_df['gameday']
away_games['won'] = games_df['away_score']> games_df['home_score']

#COMBINE
all_games = pd.concat([home_games, away_games], ignore_index = True)

all_games= all_games.sort_values(by = ['team','gameday'])
# This is the critical line you'll write:
all_games['wins_last_5'] = (
    all_games
    .groupby('team')['won']
    .transform(lambda x: x.shift(1).rolling(5, min_periods=1).sum())
)
all_games['games_last_5'] = (
    all_games.groupby('team')['won']
    .transform(lambda x: x.shift(1).rolling(5, min_periods=1).count())
)
all_games['form_rate'] = all_games['wins_last_5'] / all_games['games_last_5']
 
all_games= all_games.sort_values(by = ['form_rate'], ascending = False)


print("\n📊 Current Form (Latest Game Per Team):")
latest_form = all_games.groupby('team').tail(1)
print(latest_form[['team', 'wins_last_5', 'games_last_5', 'form_rate']]
      .sort_values('form_rate', ascending=False)
      .head(10))