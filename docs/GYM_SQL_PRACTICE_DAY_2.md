# Gym SQL Practice - Day 2 💪

Building on yesterday's work: Column creation, CASE statements, subqueries.

---

## Part 1: Conceptual Review (Questions 1-5)

These reinforce what you learned yesterday. Focus on syntax and logic.

---

### Question 1: Point Differential (Away Team Perspective)

**Goal:** Create column called `away_margin` showing away team's point differential.

**Think Through:**
- From away team's perspective, what's the calculation?
- Positive = away win, negative = home win
- Simple math or CASE needed?

**Write:**
- SQL query with the column
- Pandas equivalent

**Hint:** Similar to yesterday's margin, but flip the perspective!

---

### Question 2: Win/Loss Indicator

**Goal:** Create column called `home_result` showing 'W' if home team won, 'L' if lost, 'T' if tied.

**Think Through:**
- What's the condition for each outcome?
- How many WHEN statements needed?
- What about ties (equal scores)?

**Write:**
- SQL with CASE statement
- Pandas equivalent

**Hint:** Three-way CASE (W/L/T), not just two!

---

### Question 3: Favorite Covers Spread

**Goal:** Create column called `favorite_covers` showing TRUE if the favored team covered the spread, FALSE otherwise.

**Given:**
- `spread_line` = -7 means home favored by 7
- Home covers if: `(home_score - away_score) >= spread_line` (when negative)
- Away covers if: `(away_score - home_score) >= abs(spread_line)` (when positive)

**Think Through:**
- How do you determine who was favored? (from Question 3 yesterday)
- How do you calculate if they covered?
- Need nested CASE? (first determine favorite, then check if covered)

**Write:**
- SQL with nested or multi-step CASE
- Pandas equivalent

**Hint:** Two-step logic - who's favored, then did they cover?

---

### Question 4: Scoring Category

**Goal:** Create column called `scoring_level` showing:
- 'Very High' if total points > 60
- 'High' if total points 50-60
- 'Medium' if total points 40-49
- 'Low' if total points < 40

**Think Through:**
- Multiple WHEN statements needed?
- Order matters! (check highest first)
- What's total points calculation?

**Write:**
- SQL with multiple WHEN statements
- Pandas equivalent

**Hint:** Four categories = four WHEN statements (or use ranges)!

---

### Question 5: Home Team Margin Category

**Goal:** Create column `margin_category` showing:
- 'Blowout Win' if home wins by 14+
- 'Comfortable Win' if home wins by 7-13
- 'Close Win' if home wins by 1-6
- 'Close Loss' if home loses by 1-6
- 'Comfortable Loss' if home loses by 7-13
- 'Blowout Loss' if home loses by 14+

**Think Through:**
- How many categories? (6!)
- Do you need ABS() for losses?
- Or check positive/negative margin separately?

**Write:**
- SQL with comprehensive CASE
- Pandas equivalent

**Hint:** Can use nested CASE or multiple WHENs!

---

## Part 2: Leveling Up (Questions 6-7 with Guidance)

These introduce aggregations and grouping - new concepts with hints!

---

### Question 6: Average Points Per Game (Per Team)

**Goal:** Calculate each team's average points scored per game for a season.

**Requirements:**
- Input: `games` table with `home_team`, `away_team`, `home_score`, `away_score`, `season`
- Output: For each team and season:
  - `team`
  - `season`
  - `avg_points_scored` (average points they scored)
  - `games_played` (total games)

**Think Through:**
- This needs perspective split! (home vs away)
- How do you combine home and away scores?
- What aggregation function for average?
- What to GROUP BY?

**Your Approach (Write It Out):**
1. Step 1: Create home team perspective
   - Select `home_team as team`, `home_score as points_scored`, `season`
2. Step 2: Create away team perspective
   - Select `away_team as team`, `away_score as points_scored`, `season`
3. Step 3: Combine with UNION ALL
4. Step 4: Aggregate with GROUP BY team, season
   - AVG(points_scored) as avg_points_scored
   - COUNT(*) as games_played

**Guidance Hints:**
- SQL: `AVG()` function for average
- SQL: `COUNT(*)` for number of games
- SQL: `GROUP BY team, season` to aggregate per team/season
- Pandas: `groupby(['team', 'season'])['points_scored'].agg({'avg': 'mean', 'count': 'count'})`

**Write:**
- SQL query with UNION ALL and GROUP BY
- Pandas equivalent

---

### Question 7: Teams That Never Lost at Home (Single Season)

**Goal:** Find teams that went undefeated at home in a given season.

**Requirements:**
- Input: `games` table
- Output: List of teams that never lost a home game (only wins and ties allowed)
- Show: `team`, `season`, `home_wins`, `home_losses`, `home_ties`

**Think Through:**
- Filter to home games only first?
- How do you identify a home loss? (home_score < away_score)
- How do you find teams NOT in the "lost at home" list?
- Or aggregate and filter to teams with home_losses = 0?

**Your Approach (Write It Out):**
1. Step 1: Filter to home games for a season
2. Step 2: Determine result for each game (win/loss/tie)
3. Step 3: Aggregate by team
   - Count wins, losses, ties
4. Step 4: Filter to teams where home_losses = 0
   - Use HAVING or WHERE with subquery?

**Guidance Hints:**
- SQL: Use `CASE` to classify each game as win/loss/tie
- SQL: `GROUP BY home_team, season`
- SQL: `SUM(CASE WHEN ... THEN 1 ELSE 0 END)` to count wins/losses
- SQL: `HAVING SUM(CASE WHEN home_score < away_score THEN 1 ELSE 0 END) = 0`
- Pandas: `groupby('home_team')['result'].value_counts()` or similar

**Write:**
- SQL query with GROUP BY and HAVING
- Pandas equivalent

---

### Question 8: Point Differential Trend (Advanced Concept)

**Goal:** For each team, show if their margin is improving or declining (compare recent games vs earlier games).

**Requirements:**
- Input: `games` table with `season`, `week`
- Output: For each team and season:
  - `team`
  - `season`
  - `avg_margin_first_half` (average margin in weeks 1-9)
  - `avg_margin_second_half` (average margin in weeks 10-18)
  - `trend` ('Improving' if second > first, 'Declining' if second < first, 'Steady' if equal)

**Think Through:**
- Need to split perspectives (home/away)
- Need to filter by week ranges (1-9 vs 10-18)
- Need to calculate margin for each game
- Need to aggregate twice (two separate averages)
- Then compare them

**Your Approach (Write It Out):**
1. Step 1: Create team perspective (UNION ALL for home/away)
2. Step 2: Calculate margin per game
3. Step 3: Add `season_half` column (CASE: week <= 9 then 'First', else 'Second')
4. Step 4: Group by team, season, season_half
   - Calculate AVG(margin) for each half
5. Step 5: Combine the two halves (might need subquery or self-join)
6. Step 6: Compare and create trend column

**Guidance Hints:**
- SQL: Use subquery to calculate first half stats
- SQL: Use another subquery for second half stats
- SQL: JOIN them together, or use CASE with GROUP BY
- Alternative: Pivot the data (advanced - optional)
- Pandas: Two separate groupbys, then merge

**Write:**
- SQL query (this is complex - multiple steps)
- Pandas equivalent

**Note:** This one is HARD! Don't worry if it takes time. Focus on breaking it into steps.

---

## Answer Format Template

For each question, write:

### SQL Solution:
```sql
-- Step 1: [What you're doing]
-- Step 2: [What you're doing]
SELECT ...
FROM ...
WHERE ...
```

### Pandas Solution:
```python
# Step 1: [What you're doing]
# Step 2: [What you're doing]
df['column'] = ...
```

### Explanation:
- Why did you use CASE vs simple calculation?
- What was your thought process?
- Any tricky parts?

---

## Practice Schedule

**During Gym (Between Sets):**
- Questions 1-3: Think through logic
- Questions 4-5: Review syntax patterns
- Questions 6-7: Plan approach with guidance
- Question 8: Break into steps mentally

**Evening Dev Session:**
- Write actual SQL queries
- Write Pandas code
- Test on your NFL data
- Review and compare

---

## Key Concepts Checklist

After completing, make sure you can:
- [ ] Create calculated columns (simple math)
- [ ] Use CASE statements (conditional logic)
- [ ] Understand WHEN/THEN/ELSE/END structure
- [ ] Use subqueries to reference calculated columns
- [ ] Split perspectives with UNION ALL
- [ ] Group and aggregate with GROUP BY
- [ ] Filter groups with HAVING
- [ ] Combine multiple aggregation steps

---

## Tips

1. **Questions 1-5:** Review syntax from yesterday
2. **Question 6:** First GROUP BY problem - use guidance!
3. **Question 7:** First HAVING problem - builds on Question 6
4. **Question 8:** Advanced - break into smaller pieces

Take your time. Focus on understanding, not speed!

Ready to start? Question 1 after your next set! 💪

