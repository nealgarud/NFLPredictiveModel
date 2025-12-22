# Daily SQL/Pandas Practice Sessions

## How This Works

1. **I describe a feature** (no code, just requirements)
2. **You write SQL queries + Pandas code** to solve it
3. **We review** your approach
4. **Compare** SQL vs Pandas patterns

---

## Practice Feature 1: Team Win Streaks

### Feature Description:
Calculate the current win streak for each team in a season.

**Requirements:**
- Input: `games` table with `season`, `week`, `home_team`, `away_team`, `home_score`, `away_score`
- Output: For each team, show their current win streak (how many consecutive wins)
- Consider: Teams can win at home OR away
- Edge case: What if a team hasn't played yet this season? (streak = 0)
- Edge case: What about ties? (don't count as wins, but reset streak)

**Your Task:**
Write both SQL and Pandas code to calculate win streaks.

**Think About:**
- How do you determine if a team won?
- How do you handle consecutive wins?
- Do you need to order by week?
- Should you filter by season first?

**Hints:**
- SQL: Might need window functions (ROW_NUMBER, LAG) or recursive CTEs
- Pandas: groupby + shift() or cumulative logic

---

## My Attempt (Review After Solution)

```sql
-- Initial thinking (needs refinement):
SELECT team, won 
FROM (
    SELECT home_team as team,
           CASE WHEN home_score > away_score THEN 1 ELSE 0 END as won
    FROM games
    UNION ALL
    SELECT away_team as team,
           CASE WHEN away_score > home_score THEN 1 ELSE 0 END as won
    FROM games
) team_games

-- Missing: Ordering by week and tracking consecutive wins!
```

**See `FEATURE_1_WIN_STREAKS_SOLUTION.md` for complete walkthrough**

**✅ Solution Notes:**
- Split perspectives: ✅ Got this part right!
- Order by week: ❌ Missing - critical for streaks
- Track consecutive wins: ❌ Missing - need LAG()/shift() to compare current vs previous
- Get most recent streak: ❌ Missing - need to filter to max week per team

**Similar Practice Question:** Calculate **current loss streaks** (same logic, count consecutive losses instead)

---

## Practice Feature 2: Betting Performance by Spread Range

### Feature Description:
Analyze team ATS (Against The Spread) performance when the spread is in different ranges.

**Requirements:**
- Input: `games` table with `spread_line`, `home_score`, `away_score`, `home_team`, `away_team`
- Output: For each team, calculate:
  - ATS win rate when spread is 0-3 points (close games)
  - ATS win rate when spread is 3.5-7 points (moderate favorites)
  - ATS win rate when spread is 7.5+ points (heavy favorites)
- Show: team, spread_range, games_played, ats_wins, ats_losses, ats_win_rate

**Your Task:**
Write SQL and Pandas to calculate this.

**Think About:**
- How do you classify games into spread ranges?
- How do you determine if a team covered the spread?
- How do you split home vs away perspectives?
- How do you group by team AND spread range?

**Hints:**
- SQL: CASE to classify spread ranges, UNION ALL for home/away split
- Pandas: np.where() for classification, similar split approach

---

## Practice Feature 3: Head-to-Head Records

### Feature Description:
Calculate the head-to-head record between all team pairs.

**Requirements:**
- Input: `games` table
- Output: For each pair of teams (e.g., KC vs BAL), show:
  - team1, team2, games_played, team1_wins, team2_wins, ties
  - Only show pairs that have played each other
  - KC vs BAL should appear as one row (not also BAL vs KC)

**Your Task:**
Write SQL and Pandas code.

**Think About:**
- How do you create pairs? (need to normalize: always team1 < team2 alphabetically)
- How do you count wins for each team in the pair?
- How do you handle the perspective split?

**Hints:**
- SQL: CASE with LEAST/GREATEST to normalize pairs, UNION ALL for home/away
- Pandas: Create normalized pair column, groupby pair, aggregate

---

## Practice Feature 4: Home Field Advantage Analysis

### Feature Description:
Calculate each team's home field advantage by comparing their home vs away performance.

**Requirements:**
- Input: `games` table
- Output: For each team, show:
  - home_win_rate (wins at home / games at home)
  - away_win_rate (wins away / games away)
  - home_advantage (home_win_rate - away_win_rate)
  - home_points_scored_avg
  - away_points_scored_avg
  - home_points_allowed_avg
  - away_points_allowed_avg

**Your Task:**
Write SQL and Pandas code.

**Think About:**
- Do you need two separate queries/splits? (home games vs away games)
- How do you combine them to show one row per team?
- What if a team hasn't played home/away games yet?

**Hints:**
- SQL: Two subqueries (home stats, away stats), then JOIN on team
- Pandas: Two groupbys, then merge on team

---

## Practice Feature 5: Divisional Records (Requires JOIN)

### Feature Description:
Calculate each team's record within their division.

**Requirements:**
- Input: 
  - `games` table: `home_team`, `away_team`, `home_score`, `away_score`, `season`, `week`
  - `teams` table: `team_id`, `division` (e.g., 'AFC West', 'NFC East')
- Output: For each team, show:
  - division
  - divisional_wins
  - divisional_losses
  - divisional_win_rate
  - total_games (all games)
  - divisional_games

**Your Task:**
Write SQL and Pandas code.

**Think About:**
- How do you identify divisional games? (both teams in same division)
- How do you join teams table to games table?
- How do you filter for divisional matchups only?
- Do you need the teams table twice? (once for home, once for away)

**Hints:**
- SQL: JOIN games to teams twice (home_team join, away_team join), filter where divisions match
- Pandas: merge games with teams twice, filter where divisions match

---

## Practice Feature 6: Streak Analysis (Advanced Window Functions)

### Feature Description:
For each team, find their longest win streak and longest losing streak in a season.

**Requirements:**
- Input: `games` table with scores
- Output: For each team and season:
  - longest_win_streak (consecutive wins)
  - longest_loss_streak (consecutive losses)
  - current_streak (wins or losses)
  - current_streak_type ('W' or 'L')

**Your Task:**
Write SQL and Pandas code.

**Think About:**
- How do you identify streaks?
- Do you need to order games chronologically?
- How do you reset the streak counter when result changes?
- How do you find the maximum streak?

**Hints:**
- SQL: Window functions with PARTITION BY team, ORDER BY week, cumulative logic
- Pandas: groupby + apply with custom function, or shift() to detect changes

---

## Progress Tracking

- [ ] Feature 1: Team Win Streaks
- [ ] Feature 2: Betting Performance by Spread Range
- [ ] Feature 3: Head-to-Head Records
- [ ] Feature 4: Home Field Advantage Analysis
- [ ] Feature 5: Divisional Records (JOINs)
- [ ] Feature 6: Streak Analysis (Window Functions)

---

## Simple Practice Questions (Building on Your Strengths)

**New:** See `SIMPLE_PRACTICE_QUESTIONS.md` for 2 additional questions that reinforce:
- CASE statements
- UNION ALL for perspective splits
- GROUP BY aggregations
- Simple subqueries

These are easier than Features 1-6 and focus on concepts you've already mastered.

---

## Daily Gym Practice (Column Creation Focus)

**New:** See `GYM_SQL_PRACTICE_DAY_2.md` for 8 questions:
- Questions 1-5: Conceptual review (column creation, CASE statements)
- Questions 6-7: Leveling up (GROUP BY, aggregations) with guidance
- Question 8: Advanced (multiple aggregations, trends)

These build directly on your gym practice from yesterday!

---

## Notes

- Start with Features 1-4 (single table, concepts you know)
- Or try Simple Practice Questions first (even easier)
- Or try Daily Gym Practice (column creation focus)
- Move to Feature 5 when ready for JOINs
- Feature 6 is advanced (window functions)
- Practice 1 per day during gym/driving time
- Write actual code in evening dev session
- We'll review together after you attempt

