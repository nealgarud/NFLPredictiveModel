# Feature 1: Team Win Streaks - Complete Solution Walkthrough

## The Problem
Calculate the **current win streak** for each team in a season (how many consecutive wins right now).

## 🎯 Quick Concept Reference

**Don't understand window functions?** Read `WINDOW_FUNCTIONS_EXPLAINED.md` first!

**Key Concepts:**
- **PARTITION BY** = "Look at each team separately, but keep all rows"
- **LAG()** = "Get the previous row's value" (like looking backwards)
- **ROWS UNBOUNDED PRECEDING** = "From the very first row up to current row"
- **Cumulative SUM** = "Add up values as you go through rows"

**The Logic Flow:**
1. Split home/away perspectives ✅
2. Order by week (chronological) ✅
3. Compare current game to previous game (LAG) → Detect breaks
4. Count breaks cumulatively → Create streak groups
5. Count wins within each group → Get streak length
6. Get most recent streak → Final answer

## Step-by-Step Logic

### Step 1: Split Perspectives (Home/Away)
You got this part right! Each team plays both home and away, so we need one row per team per game.

**What we need:**
- For each game, create 2 rows:
  - Row 1: home_team's perspective (won = home_score > away_score)
  - Row 2: away_team's perspective (won = away_score > home_score)

### Step 2: Order Games Chronologically
This is CRITICAL - streaks are about consecutive games, so we MUST order by week.

### Step 3: Track Consecutive Wins (The Hard Part)
This is where it gets tricky. We need to:
1. Identify when a win happens
2. Count consecutive wins
3. Reset counter when loss/ties occur
4. Get the MOST RECENT streak value

**The Key Insight:**
- Use a "streak group" identifier - each time the result changes (win → loss or loss → win), create a new group
- Within each streak group, count consecutive games
- The LAST streak group = current streak

---

## SQL Solution

```sql
-- Step 1: Create team-level game results with win/loss indicator
WITH team_games AS (
    -- Home team perspective
    SELECT 
        season,
        week,
        home_team as team,
        CASE 
            WHEN home_score > away_score THEN 1  -- Win
            WHEN home_score < away_score THEN 0  -- Loss
            ELSE NULL  -- Tie (breaks streak)
        END as won
    FROM games
    WHERE season = 2024  -- Filter to specific season
        AND home_score IS NOT NULL
        AND away_score IS NOT NULL
    
    UNION ALL
    
    -- Away team perspective
    SELECT 
        season,
        week,
        away_team as team,
        CASE 
            WHEN away_score > home_score THEN 1  -- Win
            WHEN away_score < home_score THEN 0  -- Loss
            ELSE NULL  -- Tie
        END as won
    FROM games
    WHERE season = 2024
        AND home_score IS NOT NULL
        AND away_score IS NOT NULL
),

-- Step 2: Order games and identify streak breaks
-- ⚠️ CONCEPT BREAKDOWN - See WINDOW_FUNCTIONS_EXPLAINED.md for details
-- 
-- LAG(won) OVER (PARTITION BY team ORDER BY week):
--   - PARTITION BY team = "Look at each team separately"
--   - ORDER BY week = "In chronological order"
--   - LAG(won) = "Get the previous game's result"
--   Result: Compare current game to previous game (same team)
--
-- SUM(...) OVER (PARTITION BY team ORDER BY week ROWS UNBOUNDED PRECEDING):
--   - PARTITION BY team = "For each team separately"
--   - ORDER BY week = "In chronological order"
--   - ROWS UNBOUNDED PRECEDING = "From first game to current game"
--   - SUM(...) = "Count how many streak breaks happened so far"
--   Result: Each streak gets a unique group number (1, 2, 3, etc.)
--
ordered_games AS (
    SELECT 
        team,
        season,
        week,
        won,
        -- Compare current result to previous game's result
        LAG(won) OVER (PARTITION BY team ORDER BY week) as prev_won,
        -- Create streak group: new group when result changes or is NULL
        SUM(CASE 
            WHEN won IS NULL OR won != LAG(won) OVER (PARTITION BY team ORDER BY week) 
            THEN 1 
            ELSE 0 
        END) OVER (PARTITION BY team ORDER BY week ROWS UNBOUNDED PRECEDING) as streak_group
    FROM team_games
    WHERE won IS NOT NULL  -- Exclude ties from streak calculation
),

-- Step 3: Count consecutive wins within each streak group
streak_counts AS (
    SELECT 
        team,
        week,
        won,
        streak_group,
        -- Count wins in current streak group
        SUM(won) OVER (PARTITION BY team, streak_group ORDER BY week) as current_streak,
        -- Get the latest week for each team
        MAX(week) OVER (PARTITION BY team) as max_week
    FROM ordered_games
)

-- Step 4: Get the current streak (most recent game's streak value)
SELECT 
    team,
    MAX(CASE WHEN week = max_week THEN current_streak ELSE 0 END) as win_streak
FROM streak_counts
GROUP BY team
ORDER BY win_streak DESC;
```

**Simpler Alternative (If window functions are confusing):**

```sql
-- Simpler approach using cumulative logic
WITH team_games AS (
    SELECT 
        season,
        week,
        home_team as team,
        CASE WHEN home_score > away_score THEN 1 ELSE 0 END as won
    FROM games
    WHERE season = 2024 AND home_score IS NOT NULL
    
    UNION ALL
    
    SELECT 
        season,
        week,
        away_team as team,
        CASE WHEN away_score > home_score THEN 1 ELSE 0 END as won
    FROM games
    WHERE season = 2024 AND away_score IS NOT NULL
),

ordered_games AS (
    SELECT 
        team,
        week,
        won,
        LAG(won) OVER (PARTITION BY team ORDER BY week) as prev_won
    FROM team_games
    ORDER BY team, week
),

streaks AS (
    SELECT 
        team,
        week,
        won,
        -- If current result matches previous, continue streak; else reset
        CASE 
            WHEN won = 1 AND prev_won = 1 THEN 1  -- Continuing win streak
            WHEN won = 1 AND (prev_won = 0 OR prev_won IS NULL) THEN 1  -- Starting new win streak
            ELSE 0  -- Loss or not a win
        END as is_continuing_streak,
        -- Create streak counter (resets on loss)
        SUM(CASE WHEN won = 1 THEN 1 ELSE -999 END) 
            OVER (PARTITION BY team ORDER BY week 
                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as streak_counter
    FROM ordered_games
)

SELECT 
    team,
    MAX(CASE WHEN week = (SELECT MAX(week) FROM streaks s2 WHERE s2.team = streaks.team) 
             THEN streak_counter ELSE 0 END) as win_streak
FROM streaks
GROUP BY team;
```

---

## Pandas Solution

```python
import pandas as pd
import numpy as np

def calculate_win_streaks(games_df, season=2024):
    """
    Calculate current win streak for each team in a season.
    
    Args:
        games_df: DataFrame with columns: season, week, home_team, away_team, 
                  home_score, away_score
        season: Season to analyze
    
    Returns:
        DataFrame with columns: team, win_streak
    """
    # Filter to season and completed games
    season_games = games_df[
        (games_df['season'] == season) &
        games_df['home_score'].notna() &
        games_df['away_score'].notna()
    ].copy()
    
    if len(season_games) == 0:
        return pd.DataFrame(columns=['team', 'win_streak'])
    
    # Step 1: Create home team perspective
    home_games = season_games.copy()
    home_games['team'] = home_games['home_team']
    home_games['won'] = np.where(
        home_games['home_score'] > home_games['away_score'], 1,
        np.where(home_games['home_score'] < home_games['away_score'], 0, np.nan)
    )
    home_games = home_games[['season', 'week', 'team', 'won']]
    
    # Step 2: Create away team perspective
    away_games = season_games.copy()
    away_games['team'] = away_games['away_team']
    away_games['won'] = np.where(
        away_games['away_score'] > away_games['home_score'], 1,
        np.where(away_games['away_score'] < away_games['home_score'], 0, np.nan)
    )
    away_games = away_games[['season', 'week', 'team', 'won']]
    
    # Step 3: Combine perspectives
    all_games = pd.concat([home_games, away_games], ignore_index=True)
    
    # Step 4: Sort by team and week (CRITICAL for streaks)
    all_games = all_games.sort_values(['team', 'week']).reset_index(drop=True)
    
    # Step 5: Filter out ties (they break streaks)
    all_games = all_games[all_games['won'].notna()].copy()
    
    # Step 6: Calculate streaks using shift() and cumsum()
    all_games['prev_won'] = all_games.groupby('team')['won'].shift(1)
    
    # Identify streak breaks (when result changes or starts)
    all_games['streak_break'] = (
        (all_games['won'] != all_games['prev_won']) | 
        (all_games['prev_won'].isna())
    )
    
    # Create streak group ID (new group at each break)
    all_games['streak_group'] = all_games.groupby('team')['streak_break'].cumsum()
    
    # Step 7: Calculate streak length within each group
    # Only count wins in streak
    all_games['streak_length'] = all_games.groupby(['team', 'streak_group'])['won'].cumsum()
    
    # Step 8: Get the most recent streak for each team
    # Get max week per team, then get streak at that week
    max_weeks = all_games.groupby('team')['week'].transform('max')
    current_games = all_games[all_games['week'] == max_weeks]
    
    # Get the streak value at the most recent game
    current_streaks = current_games.groupby('team')['streak_length'].last().reset_index()
    current_streaks.columns = ['team', 'win_streak']
    
    # Handle teams with no games (streak = 0)
    all_teams = pd.concat([home_games['team'], away_games['team']]).unique()
    result = pd.DataFrame({'team': all_teams})
    result = result.merge(current_streaks, on='team', how='left')
    result['win_streak'] = result['win_streak'].fillna(0).astype(int)
    
    return result.sort_values('win_streak', ascending=False)


# Alternative Pandas Solution (Even Simpler)
def calculate_win_streaks_simple(games_df, season=2024):
    """Simpler approach using apply() function"""
    
    season_games = games_df[
        (games_df['season'] == season) &
        games_df['home_score'].notna() &
        games_df['away_score'].notna()
    ].copy()
    
    # Create team games
    home_games = pd.DataFrame({
        'team': season_games['home_team'],
        'week': season_games['week'],
        'won': (season_games['home_score'] > season_games['away_score']).astype(int)
    })
    
    away_games = pd.DataFrame({
        'team': season_games['away_team'],
        'week': season_games['week'],
        'won': (season_games['away_score'] > season_games['home_score']).astype(int)
    })
    
    all_games = pd.concat([home_games, away_games], ignore_index=True)
    all_games = all_games.sort_values(['team', 'week'])
    
    def calculate_streak(group):
        """Calculate current streak for a single team"""
        wins = group['won'].values
        if len(wins) == 0:
            return 0
        
        # Count consecutive wins from the end
        streak = 0
        for i in range(len(wins) - 1, -1, -1):  # Start from most recent
            if wins[i] == 1:
                streak += 1
            else:
                break
        
        return streak
    
    streaks = all_games.groupby('team').apply(calculate_streak).reset_index()
    streaks.columns = ['team', 'win_streak']
    
    return streaks.sort_values('win_streak', ascending=False)
```

---

## Key Concepts Explained

**📚 FULL BREAKDOWN:** See `WINDOW_FUNCTIONS_EXPLAINED.md` for detailed explanation of:
- PARTITION BY vs GROUP BY
- LAG() function
- ROWS UNBOUNDED PRECEDING
- Step-by-step trace through example data

### 1. **LAG() Window Function (SQL)**
```sql
LAG(won) OVER (PARTITION BY team ORDER BY week)
```
- Gets the value from the previous row
- `PARTITION BY team` = restart for each team
- `ORDER BY week` = chronological order
- Compare current vs previous to detect streak breaks

### 2. **shift() in Pandas**
```python
all_games['prev_won'] = all_games.groupby('team')['won'].shift(1)
```
- Same as LAG() - gets previous value
- `groupby('team')` = restart for each team

### 3. **Cumulative Sum with Reset**
- When result changes, create new "streak group"
- Count wins within each streak group
- The last group's count = current streak

### 4. **Getting Most Recent Value**
- Find max week per team
- Filter to that week
- Get streak value at that point

---

## Your Similar Practice Question

**Practice Feature: Current Loss Streaks**

Same structure, but track **consecutive losses** instead of wins.

**Requirements:**
- Input: Same `games` table
- Output: For each team, show their current **loss streak** (consecutive losses)
- Edge cases: Wins and ties reset the loss streak

**Think About:**
- Same logic, but `won = 0` instead of `won = 1`
- Count consecutive losses from most recent game
- What if team hasn't played? (streak = 0)
- What resets the streak? (wins OR ties)

Try it! Use the same pattern but flip the logic.

