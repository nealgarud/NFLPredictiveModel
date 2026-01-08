import pandas as pd
import numpy as np
from DatabaseConnection import DatabaseConnection

# Connect to database
db = DatabaseConnection()
conn = db.get_connection()

# =====================
# SQL QUERIES
# =====================

# Query: Get all team games with dates and ATS result
# Need to identify games where team had bye week before (gap of 2+ weeks)
team_games_query = """
SELECT 
    season,
    week,
    gameday,
    CASE 
        WHEN (home_team = :team AND spread_line > 0 AND (home_score - away_score) > spread_line)
             OR (away_team = :team AND spread_line < 0 AND (away_score - home_score) > ABS(spread_line))
        THEN 1
        WHEN (home_team = :team AND spread_line > 0 AND (home_score - away_score) <= spread_line)
             OR (away_team = :team AND spread_line < 0 AND (away_score - home_score) <= ABS(spread_line))
        THEN 0
        ELSE NULL
    END as ats_covered
FROM games
WHERE (home_team = :team OR away_team = :team)
    AND season = ANY(:seasons)
    AND game_type = 'REG'
    AND home_score IS NOT NULL
    AND spread_line IS NOT NULL
ORDER BY season ASC, week ASC, gameday ASC
"""

# =====================
# TEST WITH A TEAM
# =====================
team = 'KC'  # Change this to test different teams
seasons = [2024, 2025]

# Run query
data = conn.run(team_games_query, team=team, seasons=seasons)
df = pd.DataFrame(data, columns=['season', 'week', 'gameday', 'ats_covered'])

print(f"✅ Team: {team}")
print(f"✅ Loaded {len(df)} games")
print(df.head(10))

# Convert gameday to datetime for date calculations
df['gameday'] = pd.to_datetime(df['gameday'])

# =====================
# YOUR PANDAS CODE BELOW
# =====================

# Step 1: Filter out NULL ats_covered values
filtered_games = df[df['ats_covered'].notna()]

# Step 2: Calculate days between games
#    Hint: Use .shift(1) to get previous game's date
#    Calculate: current_gameday - previous_gameday
#    This gives you days rest between games
filtered_games['previous_gameday'] = filtered_games['gameday'].shift(1)
filtered_games['rest_days'] = (filtered_games['gameday'] - filtered_games['previous_gameday']).dt.days

# Step 3: Identify games after bye week
#    Hint: Bye week = gap of 14+ days (2 weeks) between games
#    Create 'came_after_bye' column using conditional columnning
#    If days_between >= 14, then True, else False
filtered_games['came_after_bye'] = np.where(filtered_games['rest_days'] >= 14, True, False)

# Step 4: Split into "after bye" vs "normal rest" games
after_bye = filtered_games[filtered_games['came_after_bye'] == True]
normal_rest = filtered_games[filtered_games['came_after_bye'] == False]

# Step 5: Calculate mean ATS rate for each group
after_bye_ats_rate = after_bye['ats_covered'].mean() if len(after_bye) > 0 else 0.5
normal_rest_ats_rate = normal_rest['ats_covered'].mean() if len(normal_rest) > 0 else 0.5

# Step 6: Count games in each group
count_bye = len(after_bye)
count_normal_rest = len(normal_rest)

# Step 7: Calculate adjustment
#    If team performs better after bye: positive adjustment
#    If team performs worse after bye: negative adjustment
#    Formula: (ats_after_bye - ats_normal_rest) * scaling_factor
#    Only apply if current game is after bye week
differential_in_performance = after_bye_ats_rate - normal_rest_ats_rate
adjustment_rate = differential_in_performance * 0.15  # 15% of the difference

