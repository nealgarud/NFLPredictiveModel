# Simple Practice Questions (Based on Your Strengths)

These build on what you already know: CASE statements, UNION ALL, GROUP BY, aggregations.

---

## Practice Question 1: Home vs Away Win Rates

### Feature Description:
Calculate each team's win rate at home vs away (simple version - no complex joins).

**Requirements:**
- Input: `games` table with `home_team`, `away_team`, `home_score`, `away_score`, `season`
- Output: For each team and season, show:
  - `team`
  - `season`
  - `home_wins` (count of wins at home)
  - `home_games` (count of games at home)
  - `home_win_rate` (home_wins / home_games)
  - `away_wins` (count of wins away)
  - `away_games` (count of games away)
  - `away_win_rate` (away_wins / away_games)

**Think About:**
- You'll need to split perspectives (home games vs away games)
- Use CASE to determine wins
- Use UNION ALL to combine
- Group by team and season
- Calculate win rates (wins / total games)

**Hints:**
- SQL: Two subqueries (home stats, away stats), then combine
- Pandas: Two separate groupbys, then merge on team/season
- Use CASE for wins, COUNT for games
- Divide wins by total games for rate

**Your Strengths This Uses:**
- ✅ CASE statements (determine wins)
- ✅ UNION ALL (combine home/away perspectives)
- ✅ GROUP BY (aggregate per team/season)
- ✅ Basic aggregations (COUNT, SUM)
- ✅ Simple calculations (division)

**📝 Template Available:** See `QUESTION_1_TEMPLATE.md` for structured fill-in-the-blank template to guide your solution!

---

## Practice Question 2: Teams That Beat Strong Opponents

### Feature Description:
Find teams that have a winning record (win rate > 0.5) when playing against teams with winning records.

**Requirements:**
- Input: `games` table with `home_team`, `away_team`, `home_score`, `away_score`, `season`
- Output: For each team and season, show:
  - `team`
  - `season`
  - `games_vs_winning_teams` (how many games against teams with winning records)
  - `wins_vs_winning_teams` (how many wins against those teams)
  - `win_rate_vs_winning_teams` (wins / games)
  - Only show teams where `win_rate_vs_winning_teams > 0.5`

**Think About:**
- Step 1: Calculate each team's overall win rate for the season
- Step 2: Identify which teams have winning records (win rate > 0.5)
- Step 3: For each game, check if opponent has winning record
- Step 4: Calculate wins/games against winning teams only
- Step 5: Filter to teams with win rate > 0.5 vs winning teams

**Approach:**
1. First query: Calculate overall win rates for all teams (this tells us who has a "winning record")
2. Second query: For each game, determine if opponent has winning record
3. Third query: Count wins/games where opponent had winning record
4. Filter final results

**Hints:**
- You'll need a subquery to calculate overall win rates first
- Use IN or EXISTS to check if opponent has winning record
- Use CASE to determine wins in games vs winning teams
- GROUP BY team and season

**Your Strengths This Uses:**
- ✅ CASE statements (determine wins)
- ✅ UNION ALL (split home/away perspectives)
- ✅ GROUP BY (aggregate statistics)
- ✅ Subqueries (calculate win rates first)
- ✅ Filtering (HAVING clause or WHERE with subquery)

**Note:** This one is slightly harder because it requires a subquery, but uses concepts you know!

---

## Answer Structure Template

For each question, write:

### SQL Solution:
```sql
-- Step 1: [What you're doing first]
-- Step 2: [What you're doing second]
-- etc.
```

### Pandas Solution:
```python
# Step 1: [What you're doing first]
# Step 2: [What you're doing second]
# etc.
```

### Explanation:
- Why did you split perspectives?
- What aggregations did you use?
- How did you calculate the rates?

---

## Tips

1. **Start with Question 1** - It's more straightforward
2. **For Question 2** - Break it into steps (calculate win rates first, then use them)
3. **Test your logic** - Walk through with sample data
4. **Compare SQL vs Pandas** - Same logic, different syntax

Good luck! These build directly on what you already know. 💪

