"""
SQL + Python Practice Exercises
Work through these to build your SQL and Python implementation skills
"""
import pandas as pd
from DatabaseConnection import DatabaseConnection

# Connect to database
db = DatabaseConnection()
conn = db.get_connection()

# ============================================================================
# EXERCISE 1: Basic SELECT with Filtering
# ============================================================================
# Task: Get all games for Kansas City Chiefs in 2024
# Expected columns: season, week, home_team, away_team, home_score, away_score

def exercise_1():
    """Get KC games from 2024"""
    query = """
    -- Your SQL here
    """
    
    # Uncomment when ready:
    # data = conn.run(query, team='KC', season=2024)
    # df = pd.DataFrame(data, columns=['season', 'week', 'home_team', 'away_team', 'home_score', 'away_score'])
    # print(f"Found {len(df)} games")
    # return df
    pass

# ============================================================================
# EXERCISE 2: Aggregation (GROUP BY)
# ============================================================================
# Task: Get win count for each team in 2024
# Expected columns: team, wins, games_played

def exercise_2():
    """Get team win counts"""
    query = """
    -- Your SQL here
    -- Hint: Use CASE to determine wins, GROUP BY team
    """
    
    # Uncomment when ready:
    # data = conn.run(query, season=2024)
    # df = pd.DataFrame(data, columns=['team', 'wins', 'games_played'])
    # df['win_rate'] = df['wins'] / df['games_played']
    # print(df.sort_values('win_rate', ascending=False))
    # return df
    pass

# ============================================================================
# EXERCISE 3: CASE Statement
# ============================================================================
# Task: Classify teams as Strong (10+ wins), Mediocre (7-9 wins), Weak (<7 wins)
# Expected columns: team, wins, classification

def exercise_3():
    """Classify teams by strength"""
    query = """
    -- Your SQL here
    -- Hint: Use CASE in SELECT to create classification
    """
    
    # Uncomment when ready:
    # data = conn.run(query, season=2024)
    # df = pd.DataFrame(data, columns=['team', 'wins', 'classification'])
    # print(df)
    # return df
    pass

# ============================================================================
# EXERCISE 4: Multiple Conditions (AND/OR)
# ============================================================================
# Task: Get games where KC is home team AND won by 7+ points
# Expected columns: season, week, home_team, away_team, margin

def exercise_4():
    """Get KC home blowouts"""
    query = """
    -- Your SQL here
    -- Hint: Calculate margin = home_score - away_score
    """
    
    # Uncomment when ready:
    # data = conn.run(query, team='KC')
    # df = pd.DataFrame(data, columns=['season', 'week', 'home_team', 'away_team', 'margin'])
    # print(df)
    # return df
    pass

# ============================================================================
# EXERCISE 5: Aggregation with HAVING
# ============================================================================
# Task: Get teams that played more than 10 games in 2024
# Expected columns: team, games_played

def exercise_5():
    """Get teams with many games"""
    query = """
    -- Your SQL here
    -- Hint: Use HAVING to filter groups
    """
    
    # Uncomment when ready:
    # data = conn.run(query, season=2024)
    # df = pd.DataFrame(data, columns=['team', 'games_played'])
    # print(df)
    # return df
    pass

# ============================================================================
# EXERCISE 6: INNER JOIN
# ============================================================================
# Task: Get games with full team names (if you have a teams table)
# Expected columns: season, week, home_team_name, away_team_name

def exercise_6():
    """Get games with team names"""
    # Note: This assumes you have a teams table
    # If not, skip this exercise
    query = """
    -- Your SQL here
    -- Hint: JOIN games with teams table
    """
    
    # Uncomment when ready:
    # data = conn.run(query, season=2024)
    # df = pd.DataFrame(data, columns=['season', 'week', 'home_team_name', 'away_team_name'])
    # print(df.head())
    # return df
    pass

# ============================================================================
# EXERCISE 7: Subquery
# ============================================================================
# Task: Get games where the home team has 10+ wins in that season
# Expected columns: season, week, home_team, away_team

def exercise_7():
    """Get games with strong home teams"""
    query = """
    -- Your SQL here
    -- Hint: Use subquery to find teams with 10+ wins
    """
    
    # Uncomment when ready:
    # data = conn.run(query, season=2024)
    # df = pd.DataFrame(data, columns=['season', 'week', 'home_team', 'away_team'])
    # print(df)
    # return df
    pass

# ============================================================================
# EXERCISE 8: Window Function (LAG)
# ============================================================================
# Task: Get each team's games with previous game's result
# Expected columns: team, season, week, won, prev_won

def exercise_8():
    """Get games with previous result"""
    query = """
    -- Your SQL here
    -- Hint: Use LAG() OVER (PARTITION BY team ORDER BY season, week)
    """
    
    # Uncomment when ready:
    # data = conn.run(query, season=2024)
    # df = pd.DataFrame(data, columns=['team', 'season', 'week', 'won', 'prev_won'])
    # print(df.head(20))
    # return df
    pass

# ============================================================================
# EXERCISE 9: Multiple Seasons (ANY)
# ============================================================================
# Task: Get team stats across multiple seasons
# Expected columns: team, season, wins, games

def exercise_9():
    """Get stats for multiple seasons"""
    query = """
    -- Your SQL here
    -- Hint: Use ANY(:seasons) in WHERE clause
    """
    
    # Uncomment when ready:
    # data = conn.run(query, seasons=[2024, 2025])
    # df = pd.DataFrame(data, columns=['team', 'season', 'wins', 'games'])
    # print(df)
    # return df
    pass

# ============================================================================
# EXERCISE 10: Complex ATS Calculation
# ============================================================================
# Task: Calculate ATS coverage for a team, split by home/away
# Expected columns: location, games, ats_covered, ats_rate

def exercise_10():
    """Get ATS by location"""
    query = """
    -- Your SQL here
    -- Hint: Use CASE to determine location and ATS coverage
    -- GROUP BY location
    """
    
    # Uncomment when ready:
    # data = conn.run(query, team='KC', seasons=[2024, 2025])
    # df = pd.DataFrame(data, columns=['location', 'games', 'ats_covered', 'ats_rate'])
    # print(df)
    # return df
    pass

# ============================================================================
# SOLUTIONS (Uncomment to see answers)
# ============================================================================

def solution_1():
    """Solution for Exercise 1"""
    query = """
    SELECT season, week, home_team, away_team, home_score, away_score
    FROM games
    WHERE (home_team = :team OR away_team = :team)
      AND season = :season
      AND game_type = 'REG'
    ORDER BY week
    """
    data = conn.run(query, team='KC', season=2024)
    df = pd.DataFrame(data, columns=['season', 'week', 'home_team', 'away_team', 'home_score', 'away_score'])
    return df

def solution_2():
    """Solution for Exercise 2"""
    query = """
    SELECT 
        CASE 
            WHEN home_team = :team THEN home_team
            ELSE away_team
        END as team,
        SUM(CASE 
            WHEN (home_team = :team AND home_score > away_score)
                 OR (away_team = :team AND away_score > home_score)
            THEN 1 ELSE 0 
        END) as wins,
        COUNT(*) as games_played
    FROM games
    WHERE (home_team = :team OR away_team = :team)
      AND season = :season
      AND game_type = 'REG'
      AND home_score IS NOT NULL
    GROUP BY team
    """
    # Actually, let's do it for all teams:
    query_all = """
    WITH team_games AS (
        SELECT home_team as team, season, week,
               CASE WHEN home_score > away_score THEN 1 ELSE 0 END as won
        FROM games
        WHERE season = :season AND game_type = 'REG' AND home_score IS NOT NULL
        UNION ALL
        SELECT away_team as team, season, week,
               CASE WHEN away_score > home_score THEN 1 ELSE 0 END as won
        FROM games
        WHERE season = :season AND game_type = 'REG' AND home_score IS NOT NULL
    )
    SELECT 
        team,
        SUM(won) as wins,
        COUNT(*) as games_played
    FROM team_games
    GROUP BY team
    ORDER BY wins DESC
    """
    data = conn.run(query_all, season=2024)
    df = pd.DataFrame(data, columns=['team', 'wins', 'games_played'])
    df['win_rate'] = df['wins'] / df['games_played']
    return df

# Run solutions to test
if __name__ == "__main__":
    print("Running Exercise 1 solution...")
    df1 = solution_1()
    print(df1.head())
    
    print("\nRunning Exercise 2 solution...")
    df2 = solution_2()
    print(df2.head(10))

