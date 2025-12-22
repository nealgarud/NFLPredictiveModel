import pandas as pd
import numpy as np
from DatabaseConnection import DatabaseConnection

# Connect to database
db = DatabaseConnection()
conn = db.get_connection()

# =====================
# SQL QUERIES
# =====================

# Query 1: Check if team lost their previous game (before current game)
check_previous_loss_query = """
SELECT 
    CASE 
        WHEN (home_team = :team AND home_score < away_score)
             OR (away_team = :team AND away_score < home_score)
        THEN 1  -- Lost
        ELSE 0   -- Won or tied
    END as lost_previous_game
FROM games
WHERE (home_team = :team OR away_team = :team)
    AND season = ANY(:seasons)
    AND game_type = 'REG'
    AND home_score IS NOT NULL
    AND (
        (:current_season IS NULL OR season < :current_season) 
        OR (:current_season IS NOT NULL AND season = :current_season AND (:current_week IS NULL OR week < :current_week))
    )
ORDER BY season DESC, week DESC, gameday DESC
LIMIT 1
"""

# Query 2: Get all team games with results and ATS coverage
team_games_query = """
SELECT 
    season,
    week,
    gameday,
    CASE 
        WHEN (home_team = :team AND home_score > away_score)
             OR (away_team = :team AND away_score > home_score)
        THEN 1  -- Won
        WHEN (home_team = :team AND home_score < away_score)
             OR (away_team = :team AND away_score < home_score)
        THEN 0  -- Lost
        ELSE 0.5  -- Tied
    END as game_result,
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
current_season = 2024
current_week = 10

# Run Query 1: Check if coming off loss
prev_loss_check = conn.run(
    check_previous_loss_query,
    team=team,
    seasons=seasons,
    current_season=current_season,
    current_week=current_week
)
coming_off_loss = prev_loss_check[0][0] == 1 if prev_loss_check and len(prev_loss_check) > 0 else False
print(f"✅ Team: {team}")
print(f"Coming off loss: {coming_off_loss}")

# Run Query 2: Get all games
data = conn.run(team_games_query, team=team, seasons=seasons)
df = pd.DataFrame(data, columns=['season', 'week', 'gameday', 'game_result', 'ats_covered'])

print(f"\n✅ Loaded {len(df)} games")
print(df.head(10))

# =====================
# YOUR PANDAS CODE BELOW
# =====================

# 1. Filter out NULL ats_covered values
filtered_games = df[df['ats_covered'].notna()]
# 2. Create column indicating if previous game was a loss
#    Hint: Use .shift(1) to look at previous row's game_result
filtered_games['prev_game'] = filtered_games['game_result'].shift(1)
# 3. Split into "after loss" vs "after win" games
after_loss = filtered_games[filtered_games['prev_game'] == 0]
after_win = filtered_games[filtered_games['prev_game'] == 1]
# 4. Calculate mean ATS rate for each group
loss_avg_ats_rate = after_loss['ats_covered'].mean() if len(after_loss) > 0 else 0.5
win_avg_ats_rate = after_win['ats_covered'].mean() if len(after_win) > 0 else 0.5

# 5. Count games in each group
count_losses = len(after_loss)
count_wins = len(after_win)
# 6. Calculate adjustment based on performance difference

# 6. Calculate adjustment based on performance difference
if coming_off_loss:
    win_loss_differential = loss_avg_ats_rate - win_avg_ats_rate
    # Scale the difference (0.015 = 1.5% per 0.1 difference in ATS rate)
    adjustment_rate = win_loss_differential * 0.15
else:
    adjustment_rate = 0.0