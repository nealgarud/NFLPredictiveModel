# Phase 3 Development Roadmap

## Phase 2 Completion Status ✅

### Completed Features (Phase 2)
1. ✅ **Recent Form** - Last 5 games win rate
2. ✅ **Divisional Performance** - ATS in division vs non-division games
3. ✅ **Opponent Strength** - Performance vs Strong/Mediocre/Weak opponents
4. ✅ **Performance After Loss** - Bounce-back effect analysis

**Current Model**: Team-level predictions with 4 contextual adjustments

---

## Phase 3 Vision: Advanced Context & Player Impact

**Goal**: Enhance predictions with player-level data, advanced context, and model refinement

**Timeline**: 8-12 weeks (1 hour/day research + development)

---

## 🎯 TIER 1: Model Refinement (Weeks 1-2)
**Impact**: High | **Effort**: Medium | **Uses Existing Data**

### Feature 5: Weather Impact
**Why**: Outdoor games in bad weather affect scoring and spreads

**What to build**:
- Query games with weather data (if available in DB)
- Calculate ATS performance by weather conditions
- Adjustment: Cold/rainy games favor underdogs (lower scoring)

**Research (1 hour)**:
- NFL weather impact studies
- How weather affects total points vs spreads
- Data sources: Weather API integration?

**SQL**: Filter games by `gameday`, join weather data
**Pandas**: Group by weather conditions, calculate ATS rates

---

### Feature 6: Prime Time Performance
**Why**: Teams perform differently in primetime (Sunday/Monday night)

**What to build**:
- Identify primetime games (Sunday/Monday night)
- Calculate ATS performance in primetime vs regular games
- Adjustment: Some teams elevate, others struggle under lights

**Research (1 hour)**:
- Historical primetime ATS data
- Which teams are "primetime teams"?
- Home vs away primetime splits

**SQL**: Filter by `gameday` time or add `is_primetime` flag
**Pandas**: Split primetime vs regular, calculate differential

---

### Feature 7: Bye Week Impact
**Why**: Teams coming off bye week have rest advantage

**What to build**:
- Identify games where team had bye in previous week
- Calculate ATS performance after bye week
- Adjustment: +2-3% for team coming off bye

**Research (1 hour)**:
- Historical bye week ATS performance
- Does rest help favorites or underdogs more?
- How long does bye week advantage last?

**SQL**: Check if previous game was 2+ weeks ago
**Pandas**: Filter games after bye, calculate ATS rate

---

## 🎯 TIER 2: Player-Level Features (Weeks 3-6)
**Impact**: Very High | **Effort**: High | **Requires New Data**

### Feature 8: Starting QB Impact
**Why**: Backup QB starting changes everything (biggest single factor)

**What to build**:
- New table: `player_game_stats` (QB starts per game)
- Calculate team ATS with starter vs backup QB
- Adjustment: -3-5% if backup QB starting

**Research (1 hour)**:
- NFLverse R package (has Python wrapper) - player stats
- ESPN API - player info
- How to identify backup QB starts from game data?

**SQL**: New schema needed
```sql
CREATE TABLE player_game_stats (
    game_id VARCHAR(50),
    team_id VARCHAR(10),
    player_id VARCHAR(20),
    position VARCHAR(10),
    is_starter BOOLEAN,
    ...
);
```

**Pandas**: Group by QB type (starter/backup), calculate ATS differential

---

### Feature 9: Key Player Injuries
**Why**: Star WR/RB out = offensive decline not in season averages

**What to build**:
- New table: `injuries` (player status per week)
- Identify key position players (WR1, RB1, Edge Rusher)
- Calculate ATS impact when key players out

**Research (1 hour)**:
- Injury report data sources (NFL.com, ESPN)
- Which positions matter most for ATS?
- Historical injury impact studies

**SQL**: New schema needed
```sql
CREATE TABLE injuries (
    player_id VARCHAR(20),
    team_id VARCHAR(10),
    week INT,
    season INT,
    injury_status VARCHAR(20), -- Out, Questionable, Doubtful
    position VARCHAR(10)
);
```

**Pandas**: Filter games with key injuries, calculate ATS differential

---

### Feature 10: QB Efficiency Trends
**Why**: Recent QB performance > season average

**What to build**:
- Calculate QB passer rating last 3 games
- Compare to season average
- Adjustment: Hot QB = +1-2%, Cold QB = -1-2%

**Research (1 hour)**:
- QB passer rating calculation
- How to get QB stats per game?
- Which QB metrics correlate with ATS?

**SQL**: Join `player_game_stats` with `games`
**Pandas**: Rolling window (last 3 games), calculate trend

---

## 🎯 TIER 3: Advanced Analytics (Weeks 7-8)
**Impact**: Medium-High | **Effort**: High | **Requires ML/Stats**

### Feature 11: Coaching Change Impact
**Why**: New coach = different schemes, team adjusts

**What to build**:
- Track coaching changes by season
- Calculate ATS performance first 4 games with new coach
- Adjustment: -1-2% for team with new coach (adjustment period)

**Research (1 hour)**:
- How to track coaching changes?
- Historical data on coaching change impact
- Does it affect favorites or underdogs more?

**SQL**: New table or manual tracking
**Pandas**: Filter games by coach tenure, calculate ATS

---

### Feature 12: Home Field Advantage by Stadium
**Why**: Some stadiums provide bigger home advantage (12th man effect)

**What to build**:
- Calculate home ATS by stadium/venue
- Identify "tough places to play"
- Adjustment: +1-2% for home team at difficult venues

**Research (1 hour)**:
- Which NFL stadiums have biggest home advantage?
- Outdoor cold weather stadiums vs domes
- Historical home/away splits by venue

**SQL**: Group by `home_team` (proxy for stadium), calculate home ATS
**Pandas**: Aggregate by team, rank by home advantage

---

## 🎯 TIER 4: Model Optimization (Weeks 9-12)
**Impact**: High | **Effort**: Medium | **Refinement**

### Feature 13: Dynamic Weight Tuning
**Why**: Current weights are static, should adjust based on data quality

**What to build**:
- Adjust feature weights based on sample size
- If situational data sparse, reduce its weight
- Increase weight of features with more data

**Research (1 hour)**:
- Bayesian updating for weights
- How to quantify data quality?
- Weight optimization algorithms

**Python**: Dynamic weight calculation based on `MIN_GAMES` thresholds

---

### Feature 14: Confidence Intervals
**Why**: Predictions need uncertainty estimates

**What to build**:
- Calculate confidence based on sample sizes
- Low sample = wider confidence interval
- High sample = narrow confidence interval

**Research (1 hour)**:
- Statistical confidence intervals
- How to calculate for probability estimates?
- Binomial confidence intervals

**Python**: Statistical formulas (Wilson score, Clopper-Pearson)

---

### Feature 15: Backtesting Framework
**Why**: Need to validate all features on historical data

**What to build**:
- Iterate through all 2024 games chronologically
- Run prediction with data available BEFORE game
- Compare to actual result, calculate accuracy/ROI

**Research (1 hour)**:
- Time-series cross-validation
- How to simulate betting strategy?
- Performance metrics (accuracy, ROC-AUC, ROI)

**Python**: Backtesting class, performance metrics

---

## 📚 Learning Plan: 1 Hour/Day Research

### Week 1: Weather & Context Features
- **Monday**: Research weather impact on NFL spreads
- **Tuesday**: Research primetime performance data
- **Wednesday**: Research bye week advantage
- **Thursday**: Build Feature 5 (Weather) - SQL + Pandas
- **Friday**: Build Feature 6 (Primetime) - SQL + Pandas
- **Weekend**: Build Feature 7 (Bye Week) - SQL + Pandas

### Week 2: Model Refinement
- **Monday**: Test all 3 features, tune adjustments
- **Tuesday**: Integration testing
- **Wednesday**: Deploy to Lambda, validate
- **Thursday**: Document findings
- **Friday**: Plan Week 3 (Player data)

### Week 3-4: Player Data Setup
- **Week 3**: Research data sources (NFLverse, ESPN API)
- **Week 4**: Design schema, build data collection pipeline

### Week 5-6: QB Impact
- **Week 5**: Build QB impact calculator
- **Week 6**: Integrate, test, validate

### Week 7-8: Injuries & Advanced
- **Week 7**: Build injury impact feature
- **Week 8**: Coaching change, stadium advantage

### Week 9-12: Optimization
- **Week 9**: Dynamic weights, confidence intervals
- **Week 10**: Backtesting framework
- **Week 11**: Model tuning based on backtest results
- **Week 12**: Final validation, documentation

---

## 🛠️ Skills to Develop

### SQL (Priority: High)
- Window functions (LAG, LEAD for previous game analysis)
- Complex JOINs (player data with games)
- Subqueries and CTEs
- Performance optimization

### Python (Priority: High)
- Conditional logic (if/else for adjustments)
- Data structures (dicts, lists for feature storage)
- Error handling (try/except for edge cases)
- Function design (clean, reusable methods)

### Pandas (Priority: Medium - You're good here)
- Advanced groupby operations
- Window functions (.rolling())
- Multi-index DataFrames
- Performance optimization

### Statistics (Priority: Medium)
- Confidence intervals
- Statistical significance testing
- Regression analysis (for feature importance)

---

## 📊 Success Metrics

### Technical
- ✅ All Tier 1 features integrated (Weeks 1-2)
- ✅ Player data pipeline working (Week 4)
- ✅ QB impact validated (Week 6)
- ✅ Backtesting framework complete (Week 10)

### Performance
- **Accuracy**: Phase 3 > Phase 2 by +2-3%
- **ROI**: Positive returns in simulated betting
- **Confidence**: Predictions have uncertainty estimates

---

## 🚀 Next Steps (Monday)

1. **Research Session (1 hour)**:
   - Topic: Weather impact on NFL spreads
   - Questions to answer:
     - How much does weather affect scoring?
     - Which weather conditions matter most?
     - Do we have weather data in our DB?
   - Resources: NFL analytics blogs, research papers

2. **After Research**:
   - Decide: Build weather feature or skip to primetime?
   - If building: Design SQL query, outline Pandas logic
   - If skipping: Move to primetime research

---

## 📝 Notes

- **Start Simple**: Tier 1 features use existing data, easier to build
- **Validate Each Feature**: Test before moving to next
- **Document Learnings**: Write down what works/doesn't work
- **Iterate**: Adjust based on backtesting results

**Remember**: You're building a research-driven model. Each feature should be validated with data, not assumptions.

---

**Status**: 🚀 Ready to Start Phase 3  
**Next Action**: Monday research session - Weather Impact  
**Timeline**: 8-12 weeks for full Phase 3

