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
        div_game
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
           'home_team', 'away_team', 'home_score', 
           'away_score', 'div_game']

games_df = pd.DataFrame(rows, columns=columns)

print(f"✅ Loaded {len(games_df)} games")
print(f"Division games: {games_df['div_game'].sum()}")
print(games_df.head())

# =====================
# YOUR PANDAS CODE BELOW
# =====================

#SPLIT PERSPECTIVES
home_games = games_df.copy()
home_games['team'] = games_df['home_team']
home_games['won'] = games_df['home_score']> games_df['away_score']

away_games = games_df.copy()
away_games['team'] = games_df['away_team']
away_games['won'] = games_df['away_score']> games_df['home_score']

#COMBINE
all_games = pd.concat([home_games, away_games], ignore_index = True)

#Filter by division and non-division games

division_games = all_games[all_games['div_game']== True]

non_division_games = all_games[all_games['div_game']== False]


division_game_stats = division_games.groupby('team')['won'].agg(['sum','count']).reset_index()
division_game_stats.columns = ['team', 'div_wins', 'div_games']
division_game_stats['div_win_rate'] = division_game_stats['div_wins']/division_game_stats['div_games']


non_division_game_stats = non_division_games.groupby('team')['won'].agg(['sum','count']).reset_index()
non_division_game_stats.columns = ['team', 'non_div_wins', 'non_div_games']
non_division_game_stats['non_div_win_rate'] = non_division_game_stats['non_div_wins']/non_division_game_stats['non_div_games']

#merging divsion and non division game stats

all_game_stats = pd.merge(division_game_stats, non_division_game_stats, on='team', how= 'outer')

all_game_stats['div_advantage'] = all_game_stats['div_win_rate'] - all_game_stats['non_div_win_rate']
#Sort by division record and non division record

all_games_stats = all_game_stats.sort_values(by=['div_win_rate', 'non_div_win_rate', 'div_advantage'], ascending = False)

# Calculate advantage
all_game_stats['div_advantage'] = all_game_stats['div_win_rate'] - all_game_stats['non_div_win_rate']

# View 1: Best division performers
print("\n📊 Best Division Performers:")
print(all_game_stats[['team', 'div_wins', 'div_games', 'div_win_rate', 'div_advantage']]
      .sort_values('div_win_rate', ascending=False)
      .head(10))

# View 2: Best non-division performers  
print("\n📊 Best Non-Division Performers:")
print(all_game_stats[['team', 'non_div_wins', 'non_div_games', 'non_div_win_rate', 'div_advantage']]
      .sort_values('non_div_win_rate', ascending=False)
      .head(10))

# View 3: Biggest division advantage
print("\n📊 Teams That Dominate Their Division:")
print(all_game_stats[['team', 'div_win_rate', 'non_div_win_rate', 'div_advantage']]
      .sort_values('div_advantage', ascending=False)
      .head(10))