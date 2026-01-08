# Question 1: Home vs Away Win Rates - Template

## SQL Template Structure

```sql
-- Step 1: Create home team perspective
SELECT 
    home_team as team,     -- ✅ FIXED: Need to select home_team and alias it as team
    season,                 -- ✅ FIXED: Need season column!
    CASE 
        WHEN home_score > away_score THEN 1  -- ✅ CASE logic is correct!
        ELSE 0
    END as won
FROM games
WHERE home_score IS NOT NULL AND away_score IS NOT NULL  -- ✅ FIXED: Filter completed games

UNION ALL

-- Step 2: Create away team perspective  
SELECT 
    away_team as team,     -- ✅ FIXED: Need to select away_team and alias it as team
    season,                 -- ✅ FIXED: Need season column!
    CASE 
        WHEN away_score > home_score THEN 1  -- ✅ CASE logic is correct!
        ELSE 0
    END as won
FROM games
WHERE home_score IS NOT NULL AND away_score IS NOT NULL  -- ✅ FIXED: Filter completed games

-- Step 3: Aggregate the combined results
-- GROUP BY what columns?
-- What aggregations do you need?
-- How do you calculate the rates?
```

## Pandas Template Structure

```python
# Step 1: Create home team perspective
home_games = games_df.copy()
home_games['team'] = ___
home_games['won'] = np.where(___, 1, 0)  # Home win condition
home_games = home_games[['__', '__', 'won']]  # What columns to keep?

# Step 2: Create away team perspective
away_games = games_df.copy()
away_games['team'] = ___
away_games['won'] = np.where(___, 1, 0)  # Away win condition
away_games = away_games[['__', '__', 'won']]  # What columns to keep?

# Step 3: Combine perspectives
all_games = pd.concat([home_games, away_games], ignore_index=True)

# Step 4: Aggregate
# How do you group? What do you aggregate?
# How do you calculate rates?
```

## Fill-In Questions to Guide You

### For SQL:
1. **SELECT columns in Step 1 (home perspective):**
   - Team column: `___ as team`
   - Season column: `___ as season`
   - Win indicator: `CASE WHEN ___ THEN 1 ELSE 0 END as won`

2. **FROM clause:**
   - Table name: `FROM ___`

3. **WHERE clause (if needed):**
   - Filter by season? `WHERE season = ___`
   - Filter completed games? `WHERE home_score IS NOT NULL AND away_score IS NOT NULL`

4. **UNION ALL:**
   - Exact same structure but for away team perspective

5. **Final SELECT (aggregation):**
   - `SELECT team, season, ...`
   - `FROM (combined subquery)`
   - `GROUP BY team, season`
   - Aggregations: `SUM(won)`, `COUNT(*)`
   - Calculations: `SUM(won) / COUNT(*)` or use `AVG(won)`

### For Pandas:
1. **Home perspective:**
   - `home_games['team'] = games_df['___']`
   - `home_games['won'] = np.where(games_df['___'] > games_df['___'], 1, 0)`
   - Keep: `['team', 'season', 'won']`

2. **Away perspective:**
   - `away_games['team'] = games_df['___']`
   - `away_games['won'] = np.where(games_df['___'] > games_df['___'], 1, 0)`
   - Keep: `['team', 'season', 'won']`

3. **Combine:**
   - `pd.concat([home_games, away_games])`

4. **Aggregate:**
   - `all_games.groupby(['team', 'season'])['won'].agg({...})`
   - Or separate aggregations and merge

## Expected Output Columns

Your final result should have:
- `team`
- `season`
- `home_wins`
- `home_games`
- `home_win_rate`
- `away_wins`
- `away_games`
- `away_win_rate`

## Hint: Think About Splitting Again

You might need to split perspectives TWICE:
- Once for home games (team = home_team)
- Once for away games (team = away_team)
- Then in final aggregation, separate home stats vs away stats

How do you know if a game was home or away in the final aggregation?
- Option 1: Add a column like `was_home = 1` for home games, `was_home = 0` for away games
- Option 2: Keep them separate and aggregate separately, then merge

