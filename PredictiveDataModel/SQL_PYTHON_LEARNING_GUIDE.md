# SQL + Python Implementation Guide

## Your Current Setup
- **Database**: PostgreSQL (Supabase)
- **Python Library**: `pg8000.native`
- **Pattern**: `conn.run(query, **params)` → `pd.DataFrame(data, columns=...)`

---

## Part 1: SQL Fundamentals

### 1. Basic SELECT (You know this)
```sql
SELECT column1, column2
FROM table_name
WHERE condition
```

**Your example:**
```sql
SELECT season, week, gameday
FROM games
WHERE home_team = 'KC'
```

---

### 2. Filtering (WHERE clause)

**Operators:**
```sql
-- Comparison
WHERE wins > 10
WHERE wins >= 10
WHERE wins < 10
WHERE wins = 10
WHERE wins != 10  -- or <>
WHERE wins BETWEEN 8 AND 12

-- Text matching
WHERE team = 'KC'
WHERE team LIKE 'K%'        -- Starts with K
WHERE team LIKE '%C'         -- Ends with C
WHERE team ILIKE 'kc'        -- Case-insensitive

-- NULL checks
WHERE wins IS NULL
WHERE wins IS NOT NULL

-- Multiple conditions
WHERE wins > 10 AND losses < 5
WHERE wins > 10 OR losses < 5
WHERE team IN ('KC', 'BUF', 'GB')
WHERE team NOT IN ('KC', 'BUF')
```

**Your example:**
```sql
WHERE (home_team = :team OR away_team = :team)
    AND season = ANY(:seasons)
    AND game_type = 'REG'
    AND home_score IS NOT NULL
```

---

### 3. Aggregation (GROUP BY)

**Aggregate functions:**
```sql
SELECT 
    team,
    COUNT(*) as total_games,           -- Count rows
    SUM(wins) as total_wins,          -- Sum values
    AVG(wins) as avg_wins,            -- Average
    MAX(wins) as max_wins,            -- Maximum
    MIN(wins) as min_wins,            -- Minimum
    COUNT(DISTINCT season) as seasons -- Count unique
FROM games
WHERE season = 2024
GROUP BY team
HAVING COUNT(*) > 10                  -- Filter groups (not rows!)
ORDER BY total_wins DESC
```

**Key difference:**
- `WHERE` filters **rows** before grouping
- `HAVING` filters **groups** after grouping

**Your example:**
```sql
SELECT 
    team,
    COUNT(*) as games,
    SUM(CASE WHEN home_score > away_score THEN 1 ELSE 0 END) as wins
FROM games
WHERE season = ANY(:seasons)
GROUP BY team
```

---

### 4. CASE Statements (You use this!)

**Simple CASE:**
```sql
SELECT 
    team,
    CASE 
        WHEN wins > 10 THEN 'Strong'
        WHEN wins > 7 THEN 'Mediocre'
        ELSE 'Weak'
    END as strength
FROM teams
```

**Your example:**
```sql
CASE 
    WHEN (home_team = :team AND spread_line > 0 AND (home_score - away_score) > spread_line)
         OR (away_team = :team AND spread_line < 0 AND (away_score - home_score) > ABS(spread_line))
    THEN 1
    WHEN (home_team = :team AND spread_line > 0 AND (home_score - away_score) <= spread_line)
         OR (away_team = :team AND spread_line < 0 AND (away_score - home_score) <= ABS(spread_line))
    THEN 0
    ELSE NULL
END as ats_covered
```

---

### 5. JOINs (Critical!)

**INNER JOIN** - Only matching rows:
```sql
SELECT 
    g.season,
    g.week,
    t.team_name,
    g.home_score,
    g.away_score
FROM games g
INNER JOIN teams t ON g.home_team = t.team_abbrev
WHERE g.season = 2024
```

**LEFT JOIN** - All rows from left, matching from right:
```sql
SELECT 
    t.team_abbrev,
    t.team_name,
    COUNT(g.game_id) as games_played
FROM teams t
LEFT JOIN games g ON t.team_abbrev = g.home_team OR t.team_abbrev = g.away_team
GROUP BY t.team_abbrev, t.team_name
```

**Multiple JOINs:**
```sql
SELECT 
    g.season,
    g.week,
    ht.team_name as home_team,
    at.team_name as away_team,
    g.home_score,
    g.away_score
FROM games g
INNER JOIN teams ht ON g.home_team = ht.team_abbrev
INNER JOIN teams at ON g.away_team = at.team_abbrev
```

**Self JOIN** (same table twice):
```sql
-- Get head-to-head records
SELECT 
    g1.home_team as team1,
    g1.away_team as team2,
    COUNT(*) as games_played
FROM games g1
WHERE g1.home_team = 'KC' AND g1.away_team = 'BUF'
GROUP BY g1.home_team, g1.away_team
```

---

### 6. Subqueries

**Subquery in WHERE:**
```sql
SELECT *
FROM games
WHERE home_team IN (
    SELECT team_abbrev 
    FROM teams 
    WHERE division = 'AFC West'
)
```

**Subquery in SELECT:**
```sql
SELECT 
    team,
    wins,
    (SELECT AVG(wins) FROM teams) as league_avg
FROM teams
```

**Correlated subquery:**
```sql
SELECT 
    g1.season,
    g1.week,
    g1.home_team,
    (SELECT COUNT(*) 
     FROM games g2 
     WHERE g2.home_team = g1.home_team 
       AND g2.season = g1.season 
       AND g2.week < g1.week) as games_played
FROM games g1
```

---

### 7. Window Functions (Advanced but powerful!)

**ROW_NUMBER:**
```sql
SELECT 
    team,
    season,
    wins,
    ROW_NUMBER() OVER (PARTITION BY season ORDER BY wins DESC) as rank
FROM teams
```

**LAG/LEAD (like pandas shift):**
```sql
SELECT 
    team,
    season,
    week,
    wins,
    LAG(wins, 1) OVER (PARTITION BY team ORDER BY season, week) as prev_wins,
    LEAD(wins, 1) OVER (PARTITION BY team ORDER BY season, week) as next_wins
FROM team_stats
```

**Running totals:**
```sql
SELECT 
    team,
    season,
    week,
    wins,
    SUM(wins) OVER (PARTITION BY team ORDER BY season, week) as running_total
FROM team_stats
```

---

### 8. Common Table Expressions (CTEs) - Makes complex queries readable

```sql
WITH team_stats AS (
    SELECT 
        team,
        COUNT(*) as games,
        SUM(wins) as total_wins
    FROM games
    WHERE season = 2024
    GROUP BY team
),
team_rankings AS (
    SELECT 
        team,
        games,
        total_wins,
        ROW_NUMBER() OVER (ORDER BY total_wins DESC) as rank
    FROM team_stats
)
SELECT * FROM team_rankings WHERE rank <= 10
```

---

## Part 2: Python Implementation Patterns

### Pattern 1: Simple Query → DataFrame

```python
from DatabaseConnection import DatabaseConnection
import pandas as pd

db = DatabaseConnection()
conn = db.get_connection()

# Query
query = """
SELECT team, wins, losses
FROM teams
WHERE season = :season
"""

# Execute
data = conn.run(query, season=2024)

# Convert to DataFrame
df = pd.DataFrame(data, columns=['team', 'wins', 'losses'])
```

---

### Pattern 2: Parameterized Queries (Always use this!)

**Single parameter:**
```python
query = """
SELECT * FROM games
WHERE home_team = :team
"""
data = conn.run(query, team='KC')
```

**Multiple parameters:**
```python
query = """
SELECT * FROM games
WHERE home_team = :team
  AND season = :season
  AND week = :week
"""
data = conn.run(query, team='KC', season=2024, week=5)
```

**List parameter (ANY):**
```python
query = """
SELECT * FROM games
WHERE season = ANY(:seasons)
"""
data = conn.run(query, seasons=[2024, 2025])
```

---

### Pattern 3: Aggregation → Summary DataFrame

```python
query = """
SELECT 
    team,
    COUNT(*) as games,
    SUM(CASE WHEN home_score > away_score THEN 1 ELSE 0 END) as wins
FROM games
WHERE season = ANY(:seasons)
GROUP BY team
ORDER BY wins DESC
"""

data = conn.run(query, seasons=[2024, 2025])
df = pd.DataFrame(data, columns=['team', 'games', 'wins'])
df['win_rate'] = df['wins'] / df['games']
```

---

### Pattern 4: JOIN → Merged DataFrame

```python
query = """
SELECT 
    g.season,
    g.week,
    g.home_team,
    g.away_team,
    t.team_name as home_team_name
FROM games g
INNER JOIN teams t ON g.home_team = t.team_abbrev
WHERE g.season = :season
"""

data = conn.run(query, season=2024)
df = pd.DataFrame(data, columns=['season', 'week', 'home_team', 'away_team', 'home_team_name'])
```

---

### Pattern 5: Error Handling

```python
from DatabaseConnection import DatabaseConnection
import pandas as pd
import logging

logger = logging.getLogger()

def get_team_stats(team: str, season: int) -> pd.DataFrame:
    """Get team stats with error handling"""
    try:
        db = DatabaseConnection()
        conn = db.get_connection()
        
        query = """
        SELECT team, wins, losses
        FROM teams
        WHERE team = :team AND season = :season
        """
        
        data = conn.run(query, team=team, season=season)
        
        if not data:
            logger.warning(f"No data found for {team} in {season}")
            return pd.DataFrame(columns=['team', 'wins', 'losses'])
        
        return pd.DataFrame(data, columns=['team', 'wins', 'losses'])
        
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        raise
```

---

### Pattern 6: Multiple Queries → Combine Results

```python
# Query 1: Home games
home_query = """
SELECT team, COUNT(*) as home_games
FROM games
WHERE home_team = :team
GROUP BY team
"""

# Query 2: Away games
away_query = """
SELECT team, COUNT(*) as away_games
FROM games
WHERE away_team = :team
GROUP BY team
"""

# Execute both
home_data = conn.run(home_query, team='KC')
away_data = conn.run(away_query, team='KC')

# Convert to DataFrames
home_df = pd.DataFrame(home_data, columns=['team', 'home_games'])
away_df = pd.DataFrame(away_data, columns=['team', 'away_games'])

# Merge
combined = home_df.merge(away_df, on='team', how='outer')
combined['total_games'] = combined['home_games'].fillna(0) + combined['away_games'].fillna(0)
```

---

### Pattern 7: Window Functions → Pre-calculated Features

```python
query = """
SELECT 
    team,
    season,
    week,
    wins,
    LAG(wins, 1) OVER (PARTITION BY team ORDER BY season, week) as prev_wins,
    SUM(wins) OVER (PARTITION BY team ORDER BY season, week) as running_total
FROM team_stats
WHERE team = :team
ORDER BY season, week
"""

data = conn.run(query, team='KC')
df = pd.DataFrame(data, columns=['team', 'season', 'week', 'wins', 'prev_wins', 'running_total'])
```

---

## Part 3: Common SQL Patterns for Your Project

### Pattern A: Calculate ATS Coverage

```python
def get_ats_coverage(team: str, seasons: list) -> pd.DataFrame:
    query = """
    SELECT 
        season,
        week,
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
    ORDER BY season ASC, week ASC
    """
    
    data = conn.run(query, team=team, seasons=seasons)
    return pd.DataFrame(data, columns=['season', 'week', 'ats_covered'])
```

---

### Pattern B: Get Opponent Stats

```python
def get_opponent_stats(team: str, seasons: list) -> pd.DataFrame:
    query = """
    SELECT 
        CASE 
            WHEN home_team = :team THEN away_team
            ELSE home_team
        END as opponent,
        COUNT(*) as games_played,
        SUM(CASE 
            WHEN (home_team = :team AND home_score > away_score)
                 OR (away_team = :team AND away_score > home_score)
            THEN 1 ELSE 0 
        END) as wins_against
    FROM games
    WHERE (home_team = :team OR away_team = :team)
      AND season = ANY(:seasons)
      AND game_type = 'REG'
      AND home_score IS NOT NULL
    GROUP BY opponent
    ORDER BY games_played DESC
    """
    
    data = conn.run(query, team=team, seasons=seasons)
    return pd.DataFrame(data, columns=['opponent', 'games_played', 'wins_against'])
```

---

### Pattern C: Recent Form (Last N Games)

```python
def get_recent_form(team: str, seasons: list, current_season: int, current_week: int, n: int = 5) -> pd.DataFrame:
    query = """
    SELECT 
        season,
        week,
        gameday,
        CASE 
            WHEN home_team = :team AND home_score > away_score THEN 1
            WHEN away_team = :team AND away_score > home_score THEN 1
            ELSE 0
        END as won
    FROM games
    WHERE (home_team = :team OR away_team = :team)
      AND season = ANY(:seasons)
      AND game_type = 'REG'
      AND home_score IS NOT NULL
      AND (
          season < :current_season
          OR (season = :current_season AND week < :current_week)
      )
    ORDER BY season DESC, week DESC, gameday DESC
    LIMIT :n
    """
    
    data = conn.run(query, 
                   team=team, 
                   seasons=seasons, 
                   current_season=current_season, 
                   current_week=current_week,
                   n=n)
    return pd.DataFrame(data, columns=['season', 'week', 'gameday', 'won'])
```

---

## Part 4: SQL Best Practices

### ✅ DO:
1. **Always use parameterized queries** - Prevents SQL injection
2. **Filter in SQL** - Use WHERE to reduce data before Python
3. **Use indexes** - Filter on indexed columns (team, season, week)
4. **Limit results** - Use LIMIT for large queries
5. **Use CASE** - Calculate logic in SQL when possible
6. **Use CTEs** - Break complex queries into readable parts

### ❌ DON'T:
1. **Don't use string formatting** - `f"WHERE team = '{team}'"` is dangerous!
2. **Don't fetch all data** - Always filter in SQL first
3. **Don't do calculations in Python** - Use SQL aggregation when possible
4. **Don't ignore NULLs** - Handle them explicitly

---

## Part 5: Learning Path

### Week 1: Basics
- [ ] SELECT, WHERE, ORDER BY
- [ ] Parameterized queries in Python
- [ ] Convert results to DataFrame

### Week 2: Aggregation
- [ ] GROUP BY, HAVING
- [ ] COUNT, SUM, AVG, MAX, MIN
- [ ] CASE statements

### Week 3: JOINs
- [ ] INNER JOIN
- [ ] LEFT JOIN
- [ ] Multiple JOINs

### Week 4: Advanced
- [ ] Subqueries
- [ ] Window functions (LAG, LEAD, ROW_NUMBER)
- [ ] CTEs

---

## Practice Exercises

### Exercise 1: Team Win Rate
Write SQL to get each team's win rate for 2024:
```python
# Your code here
```

### Exercise 2: Head-to-Head
Write SQL to get KC vs BUF head-to-head record:
```python
# Your code here
```

### Exercise 3: Recent Performance
Write SQL to get each team's last 5 games:
```python
# Your code here
```

---

## Resources

- **PostgreSQL Docs**: https://www.postgresql.org/docs/
- **SQL Tutorial**: https://www.w3schools.com/sql/
- **pg8000 Docs**: https://github.com/tlocke/pg8000

