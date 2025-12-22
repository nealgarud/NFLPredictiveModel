# Window Functions Explained - The Streak Logic

## Core Concepts You Need to Understand

### 1. **PARTITION BY** - "Group But Don't Collapse"

**What it does:** Creates separate "windows" for each group, but keeps all rows (unlike GROUP BY which collapses rows).

**Analogy:** 
- GROUP BY = "Put all KC games in one bucket, give me summary stats"
- PARTITION BY = "Look at KC games separately, but show me EACH game with its stats"

**Example:**
```sql
-- GROUP BY (collapses rows)
SELECT team, COUNT(*) as games
FROM games
GROUP BY team
-- Result: 1 row per team

-- PARTITION BY (keeps all rows)
SELECT team, week, COUNT(*) OVER (PARTITION BY team) as total_games
FROM games
-- Result: ALL rows, but each row shows its team's total games
```

**In our streak problem:**
```sql
LAG(won) OVER (PARTITION BY team ORDER BY week)
```
Translation: "For each team separately, look at their games in week order, and get the previous game's result"

---

### 2. **LAG()** - "Look at Previous Row"

**What it does:** Gets the value from the previous row in the ordered set.

**Analogy:** Like looking in your rearview mirror - "What was the value in the row before this one?"

**Simple Example:**
```
Week | Team | Score | LAG(Score)
-----|------|-------|----------
1    | KC   | 27    | NULL (no previous row)
2    | KC   | 31    | 27 (previous week's score)
3    | KC   | 24    | 31 (previous week's score)
```

**In our problem:**
```sql
LAG(won) OVER (PARTITION BY team ORDER BY week) as prev_won
```

This means:
- For KC's week 1 game: `prev_won = NULL` (no previous game)
- For KC's week 2 game: `prev_won = won value from week 1`
- For KC's week 3 game: `prev_won = won value from week 2`

**Why we need it:** To compare current game result to previous game result to detect streak breaks!

---

### 3. **ROWS UNBOUNDED PRECEDING** - "From Start to Current Row"

**What it does:** Defines the window range for calculations.

**Options:**
- `ROWS UNBOUNDED PRECEDING` = "From the very first row up to current row"
- `ROWS BETWEEN 1 PRECEDING AND CURRENT ROW` = "Just previous row and current row"
- `ROWS BETWEEN 2 PRECEDING AND 1 FOLLOWING` = "2 rows before, current, 1 row after"

**Visual Example:**
```
Row | Value | SUM() OVER (ROWS UNBOUNDED PRECEDING)
----|-------|-------------------------------------
1   | 10    | 10 (just row 1)
2   | 20    | 30 (rows 1+2)
3   | 15    | 45 (rows 1+2+3)
4   | 5     | 50 (rows 1+2+3+4)
```

**In our problem:**
```sql
SUM(CASE ... END) OVER (PARTITION BY team ORDER BY week ROWS UNBOUNDED PRECEDING) as streak_group
```

This means: "For each team, starting from their first game, count how many times the result changed (streak breaks), and give each streak a unique group number"

---

## How They Work Together: The Streak Logic

Let's trace through an example step by step:

### Example Data: KC Chiefs Season
```
Week | Team | Won | What happened
-----|------|-----|-------------
1    | KC   | 1   | Win
2    | KC   | 1   | Win (continuing streak)
3    | KC   | 0   | Loss (streak breaks!)
4    | KC   | 1   | Win (new streak starts)
5    | KC   | 1   | Win (continuing streak)
```

### Step 1: Add Previous Game's Result (LAG)

```sql
SELECT 
    team,
    week,
    won,
    LAG(won) OVER (PARTITION BY team ORDER BY week) as prev_won
FROM team_games
```

**Result:**
```
Week | Team | Won | Prev_Won | Meaning
-----|------|-----|----------|--------
1    | KC   | 1   | NULL     | First game (no previous)
2    | KC   | 1   | 1        | Previous was win (streak continues!)
3    | KC   | 0   | 1        | Previous was win, now loss (BREAK!)
4    | KC   | 1   | 0        | Previous was loss, now win (new streak!)
5    | KC   | 1   | 1        | Previous was win (streak continues!)
```

---

### Step 2: Identify Streak Breaks

```sql
SELECT 
    team,
    week,
    won,
    prev_won,
    CASE 
        WHEN won != prev_won OR prev_won IS NULL 
        THEN 1  -- Streak break or first game
        ELSE 0  -- Streak continues
    END as is_break
FROM ordered_games
```

**Result:**
```
Week | Won | Prev_Won | Is_Break | Meaning
-----|-----|----------|----------|--------
1    | 1   | NULL     | 1        | First game (starts group 1)
2    | 1   | 1        | 0        | Same result (still group 1)
3    | 0   | 1        | 1        | Changed! (starts group 2)
4    | 1   | 0        | 1        | Changed! (starts group 3)
5    | 1   | 1        | 0        | Same result (still group 3)
```

---

### Step 3: Create Streak Groups (Cumulative Sum)

```sql
SELECT 
    team,
    week,
    won,
    SUM(is_break) OVER (PARTITION BY team ORDER BY week ROWS UNBOUNDED PRECEDING) as streak_group
FROM ...
```

**How it works:**
- `SUM(is_break)` = Count how many breaks happened so far
- `OVER (PARTITION BY team ORDER BY week ROWS UNBOUNDED PRECEDING)` = For each team, from first game to current game

**Result:**
```
Week | Won | Is_Break | Streak_Group | Meaning
-----|-----|----------|--------------|--------
1    | 1   | 1        | 1            | First break = group 1
2    | 1   | 0        | 1            | No new break, still group 1
3    | 0   | 1        | 2            | Second break = group 2
4    | 1   | 1        | 3            | Third break = group 3
5    | 1   | 0        | 3            | No new break, still group 3
```

**Key Insight:** All games with the same `streak_group` are consecutive games with the same result!

---

### Step 4: Count Wins in Each Streak Group

```sql
SELECT 
    team,
    week,
    won,
    streak_group,
    SUM(won) OVER (PARTITION BY team, streak_group ORDER BY week) as current_streak
FROM ...
```

**How it works:**
- `PARTITION BY team, streak_group` = Look at each streak separately
- `SUM(won)` = Count wins within this streak
- `ORDER BY week` = Count cumulatively as weeks progress

**Result:**
```
Week | Won | Streak_Group | Current_Streak | Meaning
-----|-----|--------------|----------------|--------
1    | 1   | 1            | 1              | 1 win in group 1
2    | 1   | 1            | 2              | 2 wins in group 1
3    | 0   | 2            | 0              | 0 wins in group 2 (loss streak)
4    | 1   | 3            | 1              | 1 win in group 3
5    | 1   | 3            | 2              | 2 wins in group 3 (CURRENT!)
```

---

### Step 5: Get Most Recent Streak

```sql
SELECT 
    team,
    MAX(CASE WHEN week = max_week THEN current_streak ELSE 0 END) as win_streak
FROM streak_counts
GROUP BY team
```

**How it works:**
- `max_week` = Latest week this team played (week 5 for KC)
- Filter to `week = max_week` (only week 5)
- Get `current_streak` at that week (which is 2)

**Final Result:**
```
Team | Win_Streak
-----|-----------
KC   | 2         (2 consecutive wins currently)
```

---

## Pandas Equivalent (Easier to Understand?)

```python
import pandas as pd

# Step 1: LAG = shift()
df['prev_won'] = df.groupby('team')['won'].shift(1)

# Step 2: Identify breaks
df['is_break'] = (df['won'] != df['prev_won']) | df['prev_won'].isna()

# Step 3: Create streak groups (cumulative sum)
df['streak_group'] = df.groupby('team')['is_break'].cumsum()

# Step 4: Count wins in each streak
df['current_streak'] = df.groupby(['team', 'streak_group'])['won'].cumsum()

# Step 5: Get most recent streak
max_weeks = df.groupby('team')['week'].transform('max')
current = df[df['week'] == max_weeks]
result = current.groupby('team')['current_streak'].last()
```

**Key Pandas Functions:**
- `.shift(1)` = LAG (get previous row's value)
- `.cumsum()` = Cumulative sum (like SUM() OVER ROWS UNBOUNDED PRECEDING)
- `.groupby().transform()` = PARTITION BY (keeps all rows)

---

## Visual Summary: The Flow

```
Original Data
    ↓
[PARTITION BY team] → Separate each team's games
    ↓
[ORDER BY week] → Put games in chronological order
    ↓
[LAG(won)] → Compare current to previous game
    ↓
[Detect breaks] → When result changes
    ↓
[Cumulative sum of breaks] → Create streak group IDs
    ↓
[Count wins per group] → Calculate streak length
    ↓
[Get most recent] → Filter to latest week
    ↓
Final Answer: Current win streak per team
```

---

## Common Mistakes

### ❌ Wrong: Using LAG without PARTITION BY
```sql
LAG(won) OVER (ORDER BY week)  -- WRONG!
```
This compares KC's week 2 to BAL's week 1! We need to compare within the same team.

### ✅ Correct: Using LAG with PARTITION BY
```sql
LAG(won) OVER (PARTITION BY team ORDER BY week)  -- RIGHT!
```
This compares KC's week 2 to KC's week 1.

### ❌ Wrong: Forgetting ORDER BY
```sql
SUM(won) OVER (PARTITION BY team)  -- WRONG!
```
This doesn't know which order to count in! Could be random.

### ✅ Correct: Including ORDER BY
```sql
SUM(won) OVER (PARTITION BY team ORDER BY week)  -- RIGHT!
```
This counts wins chronologically.

---

## Quick Reference

| SQL Window Function | Pandas Equivalent | What It Does |
|-------------------|-------------------|--------------|
| `PARTITION BY col` | `.groupby('col')` | Separate groups, keep all rows |
| `ORDER BY col` | `.sort_values('col')` | Order rows within window |
| `LAG(value)` | `.shift(1)` | Get previous row's value |
| `SUM() OVER (...)` | `.cumsum()` | Cumulative sum |
| `ROWS UNBOUNDED PRECEDING` | (default in cumsum) | From start to current |

---

## Practice Question

Try this simpler version first:

**Calculate running total of wins per team:**

```sql
SELECT 
    team,
    week,
    won,
    SUM(won) OVER (PARTITION BY team ORDER BY week ROWS UNBOUNDED PRECEDING) as total_wins_so_far
FROM team_games
```

**Expected:**
```
Team | Week | Won | Total_Wins_So_Far
-----|------|-----|------------------
KC   | 1    | 1   | 1
KC   | 2    | 1   | 2
KC   | 3    | 0   | 2 (no change)
KC   | 4    | 1   | 3
```

Once you understand this, the streak logic is just adding the "detect breaks" step!

