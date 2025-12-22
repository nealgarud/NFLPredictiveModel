# SQL Quick Reference Cheat Sheet

## Your Python Pattern
```python
from DatabaseConnection import DatabaseConnection
import pandas as pd

db = DatabaseConnection()
conn = db.get_connection()

query = "SELECT ... FROM ... WHERE ..."
data = conn.run(query, param1=value1, param2=value2)
df = pd.DataFrame(data, columns=['col1', 'col2', ...])
```

---

## SQL Syntax Quick Reference

### SELECT Basics
```sql
SELECT column1, column2, column3
FROM table_name
WHERE condition
ORDER BY column1 DESC
LIMIT 10
```

### WHERE Conditions
```sql
WHERE column = 'value'
WHERE column > 10
WHERE column BETWEEN 5 AND 10
WHERE column IN ('val1', 'val2')
WHERE column IS NULL
WHERE column IS NOT NULL
WHERE column LIKE 'K%'        -- Starts with K
WHERE column ILIKE 'kc'      -- Case-insensitive
WHERE col1 = 'A' AND col2 > 10
WHERE col1 = 'A' OR col2 > 10
```

### Aggregation
```sql
SELECT 
    team,
    COUNT(*) as total,           -- Count rows
    SUM(wins) as total_wins,     -- Sum
    AVG(wins) as avg_wins,       -- Average
    MAX(wins) as max_wins,       -- Maximum
    MIN(wins) as min_wins,       -- Minimum
    COUNT(DISTINCT season)       -- Count unique
FROM table
GROUP BY team
HAVING COUNT(*) > 10             -- Filter groups
```

### CASE Statement
```sql
SELECT 
    team,
    CASE 
        WHEN wins > 10 THEN 'Strong'
        WHEN wins > 7 THEN 'Mediocre'
        ELSE 'Weak'
    END as classification
FROM teams
```

### JOINs
```sql
-- INNER JOIN (only matching)
SELECT *
FROM table1 t1
INNER JOIN table2 t2 ON t1.id = t2.id

-- LEFT JOIN (all from left)
SELECT *
FROM table1 t1
LEFT JOIN table2 t2 ON t1.id = t2.id
```

### Subquery
```sql
SELECT *
FROM games
WHERE home_team IN (
    SELECT team FROM teams WHERE wins > 10
)
```

### Window Functions
```sql
-- Previous value
LAG(column, 1) OVER (PARTITION BY team ORDER BY season, week)

-- Next value
LEAD(column, 1) OVER (PARTITION BY team ORDER BY season, week)

-- Row number
ROW_NUMBER() OVER (PARTITION BY team ORDER BY wins DESC)

-- Running total
SUM(wins) OVER (PARTITION BY team ORDER BY season, week)
```

### CTE (Common Table Expression)
```sql
WITH temp_table AS (
    SELECT team, COUNT(*) as games
    FROM games
    GROUP BY team
)
SELECT * FROM temp_table WHERE games > 10
```

---

## Common Patterns for Your Project

### Get Team Games
```sql
SELECT *
FROM games
WHERE (home_team = :team OR away_team = :team)
  AND season = ANY(:seasons)
ORDER BY season, week
```

### Calculate Wins
```sql
SELECT 
    team,
    SUM(CASE 
        WHEN (home_team = :team AND home_score > away_score)
             OR (away_team = :team AND away_score > home_score)
        THEN 1 ELSE 0 
    END) as wins
FROM games
WHERE (home_team = :team OR away_team = :team)
GROUP BY team
```

### Calculate ATS
```sql
CASE 
    WHEN (home_team = :team AND spread_line > 0 
          AND (home_score - away_score) > spread_line)
         OR (away_team = :team AND spread_line < 0 
             AND (away_score - home_score) > ABS(spread_line))
    THEN 1
    WHEN (home_team = :team AND spread_line > 0 
          AND (home_score - away_score) <= spread_line)
         OR (away_team = :team AND spread_line < 0 
             AND (away_score - home_score) <= ABS(spread_line))
    THEN 0
    ELSE NULL
END as ats_covered
```

### Get Opponent
```sql
CASE 
    WHEN home_team = :team THEN away_team
    ELSE home_team
END as opponent
```

### Filter by Date Range
```sql
WHERE gameday >= :start_date 
  AND gameday <= :end_date
```

### Exclude Current Game
```sql
WHERE (season < :current_season
   OR (season = :current_season AND week < :current_week))
```

---

## Python Implementation Patterns

### Single Parameter
```python
query = "SELECT * FROM games WHERE team = :team"
data = conn.run(query, team='KC')
```

### Multiple Parameters
```python
query = """
SELECT * FROM games 
WHERE team = :team AND season = :season
"""
data = conn.run(query, team='KC', season=2024)
```

### List Parameter
```python
query = "SELECT * FROM games WHERE season = ANY(:seasons)"
data = conn.run(query, seasons=[2024, 2025])
```

### Convert to DataFrame
```python
data = conn.run(query, team='KC')
df = pd.DataFrame(data, columns=['col1', 'col2', 'col3'])
```

### Handle Empty Results
```python
data = conn.run(query, team='KC')
if not data:
    return pd.DataFrame(columns=['col1', 'col2'])
df = pd.DataFrame(data, columns=['col1', 'col2'])
```

---

## Common Errors & Fixes

### Error: "column does not exist"
**Fix:** Check column names match database exactly (case-sensitive)

### Error: "syntax error at or near"
**Fix:** Check quotes, commas, parentheses

### Error: "parameter :param not found"
**Fix:** Make sure parameter name in query matches Python variable

### Error: "division by zero"
**Fix:** Add NULL check or use CASE to handle zero

### Error: "ambiguous column"
**Fix:** Use table aliases: `SELECT t1.team FROM teams t1`

---

## Performance Tips

1. **Filter early** - Use WHERE before GROUP BY
2. **Use indexes** - Filter on indexed columns (team, season, week)
3. **Limit results** - Use LIMIT for large queries
4. **Avoid SELECT *** - Only select columns you need
5. **Use aggregation in SQL** - Don't fetch all rows then aggregate in Python

---

## Debugging SQL

### Print the query
```python
print(query)  # See what SQL you're running
```

### Test with simple query first
```python
# Start simple
query = "SELECT * FROM games LIMIT 5"
data = conn.run(query)
print(data)  # See raw data structure
```

### Check column names
```python
# Get one row to see structure
query = "SELECT * FROM games LIMIT 1"
data = conn.run(query)
print(data[0] if data else "No data")  # See tuple structure
```

