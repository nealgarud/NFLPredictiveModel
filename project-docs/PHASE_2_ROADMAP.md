# Phase 2 Development Roadmap

## Current State Assessment

### ✅ What's Working (Phase 1)
- Team-level prediction model (Situational ATS, Overall ATS, Home/Away)
- Lambda API with `/predict` endpoint
- PostgreSQL database with historical game data (2024-2025)
- Hybrid baseline model (Vegas efficiency + team intelligence)
- Key number adjustments
- Spread penalty system

### 🔍 What's Explored But Not Integrated
From `featureDevelopment.py`:
- ✅ Rolling form calculation (last 5 games win rate)
- ✅ Home/away performance splits
- ✅ Opponent strength classification (incomplete)
- ✅ Divisional game flag (`div_game` column exists in DB)

**Problem**: These features are calculated but NOT used in `SpreadPredictionCalculator.py`

### ❌ What's Missing (High Impact)
1. **Recent Form/Trending** - Team's current momentum
2. **Divisional Game Performance** - Teams play differently in division games
3. **Opponent Strength Adjustment** - Account for strength of schedule
4. **Rest Days Impact** - Short week vs long rest
5. **Player/Injury Data** - Phase 2 (requires new schema)

---

## Prioritized Feature List

### 🎯 TIER 1: Quick Wins (Use Existing Data)
**Impact**: High | **Effort**: Low | **Timeline**: 1-2 weeks

#### Feature 1: Recent Form Integration
**Why**: Teams on hot streaks cover more. Current model uses season-long averages.

**What exists**: 
- `featureDevelopment.py` has rolling form calculation
- Formula: `wins_in_last_5_games / 5`

**What to build**:
- Add `_calc_recent_form()` method to `SpreadPredictionCalculator`
- Query last 5 games for each team (excluding current game)
- Weight: 15-20% of team intelligence
- Adjust formula: `Final = Baseline + Team_Adj + Form_Adj + Key_Adj - Spread_Penalty`

**Validation**: 
- Compare predictions with/without form
- Backtest on 2024 games
- Target: +1-2% accuracy improvement

**Files to modify**:
- `chatbot_final/SpreadPredictionCalculator.py`
- Add new method, integrate into `predict_spread_coverage()`

---

#### Feature 2: Divisional Game Performance
**Why**: Division games are tighter. Underdogs cover more (familiarity factor).

**What exists**:
- `div_game` column in `games` table
- Historical data available

**What to build**:
- Add `_calc_divisional_performance()` method
- Query ATS performance in division vs non-division games
- Adjustment: +2-3% for underdog in division game, -1-2% for favorite
- Only apply if both teams are in same division

**Validation**:
- Calculate historical ATS differential: division vs non-division
- Expected: Underdogs cover ~3-5% more in division games

**Files to modify**:
- `chatbot_final/SpreadPredictionCalculator.py`
- Add divisional check in `predict_spread_coverage()`

---

### 🎯 TIER 2: Medium Effort (Complete Existing Work)
**Impact**: Medium-High | **Effort**: Medium | **Timeline**: 2-3 weeks

#### Feature 3: Opponent Strength Adjustment
**Why**: Beating weak teams doesn't mean you'll beat strong teams. Need strength of schedule.

**What exists**:
- `featureDevelopment.py` started this (lines 140-160 incomplete)
- Logic: Calculate team win rate, classify opponents as Strong/Mediocre/Weak

**What to build**:
- Complete opponent strength classification
- Calculate team's ATS performance vs each strength tier
- Adjustment: If facing strong opponent, reduce favored probability by 2-3%
- If facing weak opponent, increase favored probability by 1-2%

**Validation**:
- Query: "How do teams perform ATS vs strong/weak opponents?"
- Expected: Strong teams cover less vs strong opponents

**Files to modify**:
- `chatbot_final/SpreadPredictionCalculator.py`
- Add `_calc_opponent_strength()` method
- Integrate into prediction formula

---

#### Feature 4: Rest Days Impact
**Why**: Short rest (Thursday games) hurts favorites more. Long rest helps.

**What exists**:
- `gameday` column in `games` table
- Can calculate days between games

**What to build**:
- Add `_calc_rest_days()` method
- Query previous game date, calculate days rest
- Adjustment:
  - Short rest (3-4 days): -2% for favorite, +1% for underdog
  - Normal rest (6-7 days): No adjustment
  - Long rest (8+ days): +1% for favorite

**Validation**:
- Calculate ATS performance by rest days
- Expected: Short rest favorites cover ~2-3% less

**Files to modify**:
- `chatbot_final/SpreadPredictionCalculator.py`
- Add rest days calculation

---

### 🎯 TIER 3: High Effort (New Data Sources)
**Impact**: High | **Effort**: High | **Timeline**: 4-6 weeks

#### Feature 5: Player/Injury Impact
**Why**: Backup QB starting changes everything. Star WR out = offensive decline.

**What to build**:
- New database schema (players, player_game_stats, injuries tables)
- Data collection pipeline (nflverse API or scraping)
- QB impact calculator
- Injury impact classifier

**See**: Full Phase 2 plan in ideation document

**Timeline**: Month 1 (schema + data), Month 2 (impact studies), Month 3 (integration)

---

## Development Plan: Next 30 Days

### Week 1: Recent Form Integration
**Goal**: Add recent form to prediction model

**Tasks**:
1. ✅ Review `featureDevelopment.py` rolling form logic
2. Build `_calc_recent_form()` method in `SpreadPredictionCalculator`
3. Query last 5 games for each team (exclude current game)
4. Integrate into prediction formula (15-20% weight)
5. Test with known scenarios (hot team vs cold team)
6. Deploy to Lambda, test via API

**Deliverable**: Predictions now include recent form factor

**Success Criteria**:
- Form factor calculated correctly
- Predictions change meaningfully for teams on streaks
- No breaking changes to existing API

---

### Week 2: Divisional Game Performance
**Goal**: Account for division game dynamics

**Tasks**:
1. Query divisional ATS performance from database
2. Build `_calc_divisional_performance()` method
3. Add division check (are teams in same division?)
4. Apply adjustment: +2-3% underdog, -1-2% favorite
5. Test with division vs non-division matchups
6. Deploy and validate

**Deliverable**: Predictions account for division game familiarity

**Success Criteria**:
- Division games identified correctly
- Underdog probability increases in division games
- Historical validation: Division underdogs cover more

---

### Week 3: Opponent Strength Adjustment
**Goal**: Complete opponent strength feature

**Tasks**:
1. Complete opponent strength classification from `featureDevelopment.py`
2. Calculate team win rates (season or rolling)
3. Classify opponents: Strong (>0.588 win rate), Weak (<0.412), Mediocre (middle)
4. Query ATS performance vs each tier
5. Build `_calc_opponent_strength()` method
6. Integrate adjustment into formula
7. Test and validate

**Deliverable**: Predictions account for opponent quality

**Success Criteria**:
- Opponent strength correctly classified
- Adjustments applied appropriately
- Strong teams vs strong opponents: probability decreases

---

### Week 4: Rest Days Impact
**Goal**: Account for rest advantage/disadvantage

**Tasks**:
1. Build `_calc_rest_days()` method
2. Query previous game date for each team
3. Calculate days between games
4. Apply adjustments based on rest days
5. Test with Thursday games (short rest)
6. Test with teams coming off bye (long rest)
7. Deploy and validate

**Deliverable**: Predictions account for rest days

**Success Criteria**:
- Rest days calculated correctly
- Short rest favorites penalized appropriately
- Long rest teams get boost

---

## Implementation Guidelines

### Code Structure

**New Calculator Methods** (add to `SpreadPredictionCalculator.py`):

```python
def _calc_recent_form(
    self, 
    team: str, 
    current_season: int, 
    current_week: int,
    seasons: list
) -> Dict:
    """
    Calculate team's recent form (last 5 games win rate)
    Returns: {'form_rate': 0.60, 'games_count': 5}
    """
    pass

def _calc_divisional_performance(
    self,
    favored: str,
    underdog: str,
    seasons: list
) -> Dict:
    """
    Calculate ATS performance in division vs non-division games
    Returns: {'divisional_ats': 0.55, 'non_divisional_ats': 0.48, 'is_divisional': True}
    """
    pass

def _calc_opponent_strength(
    self,
    team: str,
    opponent: str,
    seasons: list
) -> Dict:
    """
    Classify opponent strength and team's ATS performance vs that tier
    Returns: {'opponent_tier': 'Strong', 'ats_vs_tier': 0.45}
    """
    pass

def _calc_rest_days(
    self,
    team: str,
    game_date: str,
    seasons: list
) -> Dict:
    """
    Calculate days rest for team before this game
    Returns: {'rest_days': 6, 'rest_category': 'Normal'}
    """
    pass
```

### Integration Pattern

**Update `predict_spread_coverage()` method**:

```python
# After calculating existing factors (situational_ats, overall_ats, home_away_perf)

# NEW: Calculate recent form
favored_form = self._calc_recent_form(favored_team, season, week, seasons)
underdog_form = self._calc_recent_form(underdog_team, season, week, seasons)

# NEW: Check if divisional game
divisional_data = self._calc_divisional_performance(favored_team, underdog_team, seasons)

# NEW: Opponent strength
favored_opp_strength = self._calc_opponent_strength(favored_team, underdog_team, seasons)
underdog_opp_strength = self._calc_opponent_strength(underdog_team, favored_team, seasons)

# NEW: Rest days
favored_rest = self._calc_rest_days(favored_team, game_date, seasons)
underdog_rest = self._calc_rest_days(underdog_team, game_date, seasons)

# Enhanced formula
team_intelligence = (
    0.35 * situational_ats['favored_normalized'] +  # Reduced from 0.40
    0.25 * overall_ats['favored_normalized'] +      # Reduced from 0.30
    0.25 * home_away_perf['favored_normalized'] +   # Reduced from 0.30
    0.15 * favored_form['form_rate']                 # NEW
)

# Apply adjustments
form_adjustment = (favored_form['form_rate'] - 0.5) * 0.15
divisional_adjustment = divisional_data.get('adjustment', 0.0)
opponent_adjustment = favored_opp_strength.get('adjustment', 0.0)
rest_adjustment = favored_rest.get('adjustment', 0.0)

# Final probability
favored_prob = baseline_prob + team_adjustment + form_adjustment + \
               divisional_adjustment + opponent_adjustment + rest_adjustment + \
               key_adjustment - spread_penalty
```

---

## Testing Strategy

### Unit Tests (for each new method)

```python
# test_recent_form.py
def test_calc_recent_form():
    calc = SpreadPredictionCalculator()
    form = calc._calc_recent_form('KC', 2024, 10, [2024, 2025])
    assert 0 <= form['form_rate'] <= 1
    assert form['games_count'] <= 5

# test_divisional_performance.py
def test_divisional_game_detection():
    calc = SpreadPredictionCalculator()
    # KC and DEN are in same division
    div_data = calc._calc_divisional_performance('KC', 'DEN', [2024, 2025])
    assert div_data['is_divisional'] == True
```

### Integration Tests

```python
# test_enhanced_prediction.py
def test_prediction_with_form():
    predictor = SpreadPredictionCalculator()
    result = predictor.predict_spread_coverage(
        team_a='KC',
        team_b='BUF',
        spread=-3.5,
        team_a_home=True,
        seasons=[2024, 2025]
    )
    
    # Check new factors are included
    assert 'recent_form' in result['breakdown']
    assert 'divisional_adjustment' in result['breakdown']
    assert 'opponent_strength' in result['breakdown']
```

### Backtesting

```python
# Backtest on 2024 season
# Compare Phase 1 vs Phase 2 predictions
# Metrics: Accuracy, ROC-AUC, ROI
```

---

## Success Metrics

### Technical Metrics
- ✅ All 4 Tier 1 features integrated
- ✅ Unit tests written (>80% coverage)
- ✅ No breaking changes to API
- ✅ Lambda deployment successful

### Performance Metrics
- **Accuracy**: Phase 2 > Phase 1 by +1-2%
- **ROC-AUC**: Phase 2 > Phase 1 by +0.02-0.03
- **Confidence**: Predictions more calibrated (confidence matches accuracy)

### Validation Metrics
- Recent form: Hot teams (5-0 last 5) have +3-5% higher cover probability
- Divisional: Underdogs cover +3-5% more in division games
- Opponent strength: Strong teams vs strong opponents: -2-3% adjustment
- Rest days: Short rest favorites cover -2-3% less

---

## Next Steps (After 30 Days)

### Month 2: Refinement & Validation
- Backtest all features on 2024 season
- Tune adjustment weights based on results
- A/B test Phase 1 vs Phase 2 in production
- Document findings

### Month 3: Player/Injury Data (Phase 2 Tier 3)
- Design player schema
- Build data collection pipeline
- QB impact study
- Injury impact classifier

---

## Files to Create/Modify

### New Files
- `PredictiveDataModel/chatbot_final/tests/test_recent_form.py`
- `PredictiveDataModel/chatbot_final/tests/test_divisional.py`
- `PredictiveDataModel/chatbot_final/tests/test_opponent_strength.py`
- `PredictiveDataModel/chatbot_final/tests/test_rest_days.py`

### Modified Files
- `PredictiveDataModel/chatbot_final/SpreadPredictionCalculator.py` (add 4 new methods + integration)
- `PredictiveDataModel/README.md` (update with Phase 2 features)

### Documentation
- `PredictiveDataModel/PHASE_2_ROADMAP.md` (this file)
- `PredictiveDataModel/PHASE_2_IMPLEMENTATION_LOG.md` (track progress)

---

## Decision Log

### Why These Features First?
1. **Use existing data** - No new data sources needed
2. **High impact** - Each addresses a known prediction weakness
3. **Incremental** - Can build and test one at a time
4. **Validatable** - Can measure improvement with backtesting

### Why Not Player Data Yet?
- Requires new schema and data collection
- More complex, higher risk
- Better to validate team-level improvements first
- Player data is Phase 2 Tier 3 (Month 3+)

---

**Status**: 🚀 Ready to Start  
**Next Action**: Begin Week 1 - Recent Form Integration  
**Timeline**: 4 weeks for Tier 1 features

