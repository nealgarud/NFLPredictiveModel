# SQL & Pandas Practice Assessment

## ✅ What You've Mastered (From Gym/Driving Practice)

### Core SQL Concepts:
1. **Basic Queries** - SELECT/FROM/WHERE ✅
   - Filtering rows
   - Multiple conditions with AND/OR
   - Handling NULL values

2. **Grouping & Aggregations** - GROUP BY/HAVING ✅
   - Understanding WHERE vs HAVING
   - Aggregations: SUM(), COUNT(), AVG()
   - Filtering groups after aggregation

3. **Conditional Logic** - CASE statements ✅
   - np.where() equivalent
   - Multiple WHEN/THEN conditions
   - Understanding when to use vs direct calculations

4. **Subqueries & UNION ALL** ✅
   - Splitting perspectives (home/away)
   - Combining results
   - Creating intermediate tables
   - Subquery aliases (team_records pattern)

5. **Data Thinking** ✅
   - Game-level vs team-level analysis
   - Understanding when to split perspectives
   - Calculating margins and differences

6. **Functions** ✅
   - ABS() for absolute values
   - DISTINCT for unique values
   - Basic mathematical operations

---

## 🎯 What You Need to Strengthen

### Priority 1: JOINs & Merges (You Identified This)
**Why:** Most real-world queries need multiple tables
**Practice Focus:**
- INNER JOIN (matching records only)
- LEFT JOIN (keep all from left table)
- Multiple table joins
- Join conditions and keys

### Priority 2: Complex Subqueries
**Why:** Your current subqueries are simple - need nested patterns
**Practice Focus:**
- Subqueries in SELECT clause
- Correlated subqueries
- EXISTS vs IN
- Performance considerations

### Priority 3: Window Functions (Advanced)
**Why:** Time series analysis, rankings, running totals
**Practice Focus:**
- ROW_NUMBER(), RANK(), DENSE_RANK()
- LAG() and LEAD() for time series
- PARTITION BY vs GROUP BY
- OVER() clause patterns

### Priority 4: Multi-Table Aggregations
**Why:** Real features need data from multiple sources
**Practice Focus:**
- Joining before aggregating
- Aggregating then joining
- Deciding the right order

### Priority 5: More Complex CASE Logic
**Why:** Betting analysis has nuanced conditions
**Practice Focus:**
- Nested CASE statements
- CASE in aggregations
- CASE with window functions

---

## 📊 Practice Framework Structure

### Phase 1: Concept Reinforcement (This Week)
- 1 feature/day
- Start with single-table problems
- Build up to multi-table
- Focus on syntax + logic

### Phase 2: Feature Implementation (Next Week)
- Describe real features from your project
- You write SQL + Pandas
- Compare approaches
- Optimize queries

### Phase 3: Advanced Patterns (Week 3+)
- Window functions
- Complex aggregations
- Performance optimization
- Real-world edge cases

---

## 🎯 Today's Focus: JOINs & Merges

**Goal:** Understand how to combine data from multiple tables/dataframes

**Key Concepts:**
- SQL: JOIN (INNER, LEFT, RIGHT, FULL)
- Pandas: merge() with different how='inner/left/right/outer'
- Understanding join keys
- When to join vs when to filter

