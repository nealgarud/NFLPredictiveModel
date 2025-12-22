from DatabaseConnection import DatabaseConnection
import pandas as pd
import numpy as np

# Connect to database
db = DatabaseConnection()
conn = db.get_connection()

# Query games table
query = """
    SELECT 
        game_id, season, week, gameday,
        home_team, home_score, away_team, away_score,
        spread_line, div_game
    FROM games 
    WHERE season IN (2024, 2025) AND game_type = 'REG'
    ORDER BY season, week, gameday
"""

# pg8000 returns list of tuples, convert to DataFrame
rows = conn.run(query)
columns = ['game_id', 'season', 'week', 'gameday', 
           'home_team', 'home_score', 'away_team', 'away_score',
           'spread_line', 'div_game']
games_df = pd.DataFrame(rows, columns=columns)
# Split perspectives by home and away teams

home_games= games_df.copy()
home_games['team'] = home_games['home_team']
home_games['won'] = home_games['home_score']> home_games['away_score']
home_games['game_date'] = pd.to_datetime(home_games['gameday'])

print(f"✅ Created home perspective: {len(home_games)} rows")
print("\nSample home game:")
print(home_games[['game_date', 'team', 'won', 'home_score', 'away_score']].head(3))


away_games= games_df.copy()
away_games['team'] = away_games['away_team']
away_games['won'] = away_games['away_score']> away_games['home_score']
away_games['game_date'] = pd.to_datetime(away_games['gameday'])
print(f"✅ Created away perspective: {len(away_games)} rows")
print("\nSample away game:")
print(away_games[['game_date', 'team', 'won', 'home_score', 'away_score']].head(3))

all_games = pd.concat([home_games, away_games])
all_games = all_games.sort_values(['team','game_date'])
print(f"\n✅ Combined home and away games: {len(all_games)} rows")
print("\nAll games sample (sorted by team, then date):")
print(all_games[['game_date', 'team', 'won','home_score', 'away_score']].head(6))

print("Calculate Rolling form")

#converting won to integer for rolling calculations
all_games['won_int'] = all_games['won'].astype(int)

all_games['wins_in_window'] = (
    all_games.groupby('team')['won_int']
    .transform(lambda x: x.shift(1).rolling(window=5, min_periods=1).sum())
)
first_team = all_games['team'].iloc[0]
print(all_games[all_games['team'] == first_team][['game_date', 'team', 'won_int', 'wins_in_window']].head(6))


all_games['games_in_window'] = (
    all_games.groupby('team')['won_int']
    .transform(lambda x: x.shift(1).rolling(window=5, min_periods=1).count())
)

all_games['team_form'] = all_games['wins_in_window']/all_games['games_in_window']

# Fill NaN (first game) with 0.5 (neutral)
all_games['team_form'] = all_games['team_form'].fillna(0.5)

print("\n✅ Calculated team_form")

# Get each team's CURRENT form (their most recent game)
team_current_form = all_games.groupby('team')['team_form'].last().sort_values(ascending=True)

print("\nTeam forms (current, sorted best to worst):")
print(team_current_form)

#home performance splits
home_performance= home_games.groupby('team')['won'].agg(['sum','count']).reset_index()
home_performance.columns= ['team','home_wins','home_games']
home_performance['home_win_rate'] = home_performance['home_wins']/home_performance['home_games']
print("\nHome performance:")
print(home_performance)
#away performance splits
away_performance = away_games.groupby('team')['won'].agg(['sum','count']).reset_index()
away_performance.columns= ['team','away_wins','away_games']
away_performance['away_win_rate'] = away_performance['away_wins']/away_performance['away_games']
print("\nAway performance:")
print(away_performance)

#merge home and away performance
overall_performance = home_performance.merge(away_performance, on= 'team', how= 'outer')
print("\nOverall performance:")
print(overall_performance)

#home advantage
overall_performance['home_advantage'] = overall_performance['home_win_rate']- overall_performance['away_win_rate']

print("\nHome advantage (sorted):")
print(overall_performance[['team', 'home_win_rate', 'away_win_rate', 'home_advantage']].sort_values('home_advantage', ascending=False))

# Categorize teams
overall_performance['location_preference'] = np.where(
    overall_performance['home_advantage'] > 0.3,
    'Home Merchant',
    np.where(
        overall_performance['home_advantage'] < -0.2,
        'Away Merchant',
        'Neutral'
    )
)
print("\nFeature 2 Complete - Team Location Preferences:")
print(overall_performance[['team', 'home_advantage', 'location_preference']].sort_values('home_advantage', ascending=False).head(10))

# ============================================
# FEATURE 3: Game Difficulty Classifier
# ============================================
print("\n" + "="*60)
print("FEATURE 3: Game Difficulty Classifier")
print("="*60)

games_df['game_difficulty'] = np.where(
    abs(games_df['spread_line']) <= 3,
    'Toss-up',
    np.where(
        abs(games_df['spread_line']) <= 7,
        'Moderate',
        'Mismatch'
    )
)

print("\n✅ Feature 3 Complete - Game Difficulty:")
print(games_df[['home_team','away_team','spread_line','game_difficulty']].head(10))

#building out a strong vs weak team perfoormance feature

#1 calculate each teams record
team_strength = all_games.groupby('team')['won'].agg(['sum','count']).reset_index()
team_strength.columns= ['team', 'wins', 'games']
team_strength['win_rate'] = team_strength['wins']/team_strength['games']

#2 Identify each opponent for each game -> conditional columning

all_games['opponent'] = np.where(
    all_games['home_team'] == all_games['team'],
    all_games['away_team'],
    all_games['home_team']
)

#3 merge team strength to get opponent strength -> left join on opponent
all_games = all_games.merge(team_strength, left_on='opponent', right_on='team', how='left', suffixes=('', '_opponent'))


#4 classify opponent strength
all_games['opponent_strength']= np.where(all_games['win_rate']> (10/17),"strong team", np_where(["all_games"]))