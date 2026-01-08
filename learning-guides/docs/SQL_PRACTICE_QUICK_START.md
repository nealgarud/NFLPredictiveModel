# SQL/Pandas Practice - Quick Start Guide

## 📋 Your Current Skill Level

### ✅ **You've Got This (Mastered):**
- Basic queries (SELECT/FROM/WHERE)
- Grouping & aggregations (GROUP BY/HAVING)
- CASE statements (conditional logic)
- Subqueries with UNION ALL
- Data perspective thinking (home/away splits)
- Basic functions (ABS, DISTINCT, SUM, COUNT, AVG)

### 🎯 **Needs Practice (Priority Order):**
1. **JOINs & Merges** ← Start here today
2. Complex subqueries
3. Window functions (advanced)
4. Multi-table aggregations
5. Nested CASE logic

---

## 🏋️ How to Use This Practice Framework

### **During Gym/Driving (Mental Practice):**
1. Open `SQL_PANDAS_PRACTICE_DAILY.md`
2. Read ONE feature description
3. Think through the SQL/Pandas logic
4. Don't write code yet - just plan the approach

### **Evening Dev Session (Actual Coding):**
1. Write the SQL query
2. Write the Pandas equivalent
3. Test on your NFL data
4. Compare approaches

---

## 📚 Today's Focus: JOINs & Merges

**Concept:** Combining data from multiple tables/dataframes

### SQL JOIN Types:
```sql
-- INNER JOIN: Only matching records
SELECT *
FROM games g
INNER JOIN teams t ON g.home_team = t.team_id

-- LEFT JOIN: All games, even if team data missing
SELECT *
FROM games g
LEFT JOIN teams t ON g.home_team = t.team_id
```

### Pandas Merge Types:
```python
# INNER merge (default)
games.merge(teams, left_on='home_team', right_on='team_id', how='inner')

# LEFT merge
games.merge(teams, left_on='home_team', right_on='team_id', how='left')
```

### When to Use:
- **INNER JOIN**: Only want records where both tables have matching data
- **LEFT JOIN**: Want all records from left table, even if right table missing
- **Multiple JOINs**: Common pattern - join to same table twice (home team + away team)

---

## 🎯 Start With: Feature 5 (Divisional Records)

Why? It requires JOINs but uses concepts you already know.

**Your Tables:**
- `games`: home_team, away_team, home_score, away_score
- `teams`: team_id, division

**Challenge:** 
- Join games to teams table twice (once for home team, once for away team)
- Filter where both teams are in same division
- Calculate divisional win/loss records

**Think Through:**
1. How do I join games to teams for home_team?
2. How do I join again for away_team?
3. How do I filter for same division?
4. How do I calculate wins/losses?

---

## 💡 Practice Schedule Suggestion

### **Week 1: Foundation Review + JOINs**
- Day 1: Feature 1 (Win Streaks) - review concepts
- Day 2: Feature 2 (Betting by Spread Range) - CASE practice
- Day 3: Feature 3 (Head-to-Head) - aggregation patterns
- Day 4: Feature 4 (Home Field Advantage) - split perspectives
- Day 5: Feature 5 (Divisional Records) - **JOINs practice**

### **Week 2: Advanced Patterns**
- Window functions
- Complex subqueries
- Multi-table aggregations

---

## 🔍 Quick Reference: SQL → Pandas Translation

| SQL | Pandas |
|-----|--------|
| `SELECT * FROM table` | `df` |
| `WHERE condition` | `df[df['col'] == value]` |
| `GROUP BY col` | `df.groupby('col')` |
| `HAVING condition` | `.filter()` after groupby |
| `ORDER BY col` | `df.sort_values('col')` |
| `CASE WHEN...` | `np.where()` or `.apply()` |
| `JOIN table ON key` | `df.merge(other_df, on='key')` |
| `UNION ALL` | `pd.concat([df1, df2])` |
| `SUM(col)` | `df['col'].sum()` |
| `COUNT(*)` | `len(df)` or `df['col'].count()` |
| `AVG(col)` | `df['col'].mean()` |

---

## ✅ Next Steps

1. Read `SQL_PANDAS_PRACTICE_DAILY.md` for all practice features
2. Start with Feature 1-4 to reinforce concepts
3. Focus on Feature 5 for JOINs practice
4. One feature per day during gym/driving time
5. Write actual code in evening session

Ready to start? Pick Feature 1 and think through it during your next gym break! 💪

