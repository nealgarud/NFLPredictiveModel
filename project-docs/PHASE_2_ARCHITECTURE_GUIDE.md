# Phase 2 Architecture & Implementation Guide

## System Design Overview

### Current Architecture (Phase 1)

```
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway / Lambda                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         SpreadPredictionCalculator                    │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │  Team Intelligence Layer                        │  │   │
│  │  │  • Situational ATS (40%)                       │  │   │
│  │  │  • Overall ATS (30%)                          │  │   │
│  │  │  • Home/Away Performance (30%)                 │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │  Adjustment Layer                                │  │   │
│  │  │  • Key Number Penalty                          │  │   │
│  │  │  • Spread Penalty                               │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│                          ↓                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         DatabaseConnection (Singleton)                │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          ↓
            ┌─────────────────────────┐
            │   Supabase PostgreSQL    │
            │   • games table          │
            │   • team_rankings table  │
            └─────────────────────────┘
```

### Enhanced Architecture (Phase 2)

```
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway / Lambda                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         SpreadPredictionCalculator                    │   │
│  │                                                        │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │  Team Intelligence Layer (Enhanced)            │  │   │
│  │  │  • Situational ATS (35%)                        │  │   │
│  │  │  • Overall ATS (25%)                           │  │   │
│  │  │  • Home/Away Performance (25%)                 │  │   │
│  │  │  • Recent Form (15%) ← NEW                      │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  │                                                        │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │  Contextual Factors Layer (NEW)                │  │   │
│  │  │  • Divisional Game Adjustment                   │  │   │
│  │  │  • Opponent Strength Adjustment                 │  │   │
│  │  │  • Rest Days Adjustment                         │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  │                                                        │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │  Adjustment Layer (Existing)                   │  │   │
│  │  │  • Key Number Penalty                          │  │   │
│  │  │  • Spread Penalty                               │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│                          ↓                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         DatabaseConnection (Singleton)                │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          ↓
            ┌─────────────────────────┐
            │   Supabase PostgreSQL    │
            │   • games table          │
            │     - season, week       │
            │     - gameday (DATE)      │
            │     - div_game (BOOLEAN)  │
            │     - home/away teams     │
            │     - scores              │
            └─────────────────────────┘
```

---

## Data Flow Architecture

### Prediction Request Flow

```
1. API Request
   ↓
2. SpreadPredictionCalculator.predict_spread_coverage()
   ↓
3. PARALLEL QUERIES (all execute simultaneously):
   ├─→ Situational ATS Query
   ├─→ Overall ATS Query
   ├─→ Home/Away Performance Query
   ├─→ Recent Form Query (NEW)
   ├─→ Divisional Performance Query (NEW)
   ├─→ Opponent Strength Query (NEW)
   └─→ Rest Days Query (NEW)
   ↓
4. CALCULATE FACTORS:
   ├─→ Team Intelligence (weighted combination)
   ├─→ Contextual Adjustments (additive)
   └─→ Spread/Key Adjustments (subtractive)
   ↓
5. FINAL PROBABILITY:
   Baseline(0.50) + Team_Adj + Context_Adj + Key_Adj - Spread_Penalty
   ↓
6. Response JSON
```

---

## Component Design

### 1. SpreadPredictionCalculator Class Structure

```python
class SpreadPredictionCalculator:
    """
    Main prediction engine
    """
    
    # Existing methods (Phase 1)
    def predict_spread_coverage(...)  # Main entry point
    def _calc_situational_ats(...)     # Situational ATS
    def _calc_overall_ats(...)         # Overall ATS
    def _calc_home_away_performance(...)  # Home/Away
    def _calculate_key_number_impact(...)  # Key numbers
    def _get_spread_range(...)         # Spread bucketing
    
    # NEW methods (Phase 2)
    def _calc_recent_form(...)         # Last 5 games win rate
    def _calc_divisional_performance(...)  # Division game ATS
    def _calc_opponent_strength(...)   # Opponent tier classification
    def _calc_rest_days(...)           # Days between games
```

### 2. New Calculator Methods Design

#### Method: `_calc_recent_form()`

**Purpose**: Calculate team's win rate in last 5 games (momentum indicator)

**Input**:
- `team`: Team abbreviation (e.g., 'KC')
- `current_season`: Season of game being predicted
- `current_week`: Week of game being predicted
- `seasons`: List of seasons to query (e.g., [2024, 2025])

**Logic**:
1. Query all games for team BEFORE current game (chronologically)
2. Filter: `season < current_season OR (season = current_season AND week < current_week)`
3. Order by season DESC, week DESC
4. Take last 5 games
5. Calculate win rate: `wins / games_count`
6. If < 5 games available, use what's available (min_periods=1)

**SQL Query Pattern**:
```sql
SELECT 
    season, week, gameday,
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
ORDER BY season DESC, week DESC
LIMIT 5
```

**Output**:
```python
{
    'form_rate': 0.60,        # Win rate (0.0 to 1.0)
    'games_count': 5,        # Number of games used
    'wins': 3,              # Wins in last 5
    'losses': 2             # Losses in last 5
}
```

**Integration**: Add to team intelligence calculation with 15% weight

---

#### Method: `_calc_divisional_performance()`

**Purpose**: Calculate ATS performance in division vs non-division games

**Input**:
- `favored`: Favored team abbreviation
- `underdog`: Underdog team abbreviation
- `seasons`: List of seasons

**Logic**:
1. Check if teams are in same division (query `teams` table or hardcode divisions)
2. Query all games where favored team played, split by `div_game` flag
3. Calculate ATS win rate for:
   - Division games (`div_game = TRUE`)
   - Non-division games (`div_game = FALSE`)
4. Calculate differential: `divisional_ats - non_divisional_ats`

**SQL Query Pattern** (Division games):
```sql
SELECT 
    COUNT(*) as total_games,
    SUM(CASE 
        WHEN (home_team = :favored AND spread_line > 0 
              AND (home_score - away_score) > spread_line)
        OR (away_team = :favored AND spread_line < 0 
            AND (away_score - home_score) > ABS(spread_line))
        THEN 1 ELSE 0 
    END) as ats_wins
FROM games
WHERE (home_team = :favored OR away_team = :favored)
    AND season = ANY(:seasons)
    AND game_type = 'REG'
    AND div_game = TRUE
    AND home_score IS NOT NULL
```

**Output**:
```python
{
    'is_divisional': True,              # Are teams in same division?
    'divisional_ats': 0.55,            # ATS win rate in division games
    'non_divisional_ats': 0.48,        # ATS win rate in non-division
    'differential': 0.07,              # Difference
    'adjustment': 0.02                 # Applied adjustment (+2% for underdog)
}
```

**Integration**: Apply adjustment only if `is_divisional = True`

---

#### Method: `_calc_opponent_strength()`

**Purpose**: Classify opponent strength and team's ATS performance vs that tier

**Input**:
- `team`: Team abbreviation
- `opponent`: Opponent team abbreviation
- `seasons`: List of seasons

**Logic**:
1. Calculate opponent's win rate (season or rolling)
2. Classify tier:
   - Strong: Win rate > 0.588 (10+ wins in 17 games)
   - Weak: Win rate < 0.412 (7 or fewer wins)
   - Mediocre: Between 0.412 and 0.588
3. Query team's ATS performance vs opponents in that tier
4. Compare to team's overall ATS

**SQL Query Pattern** (Opponent win rate):
```sql
SELECT 
    team,
    SUM(CASE 
        WHEN (home_team = team AND home_score > away_score)
        OR (away_team = team AND away_score > home_score)
        THEN 1 ELSE 0 
    END)::FLOAT / COUNT(*) as win_rate
FROM games
WHERE (home_team = :opponent OR away_team = :opponent)
    AND season = ANY(:seasons)
    AND game_type = 'REG'
    AND home_score IS NOT NULL
GROUP BY team
```

**Output**:
```python
{
    'opponent_tier': 'Strong',         # 'Strong', 'Mediocre', 'Weak'
    'opponent_win_rate': 0.65,        # Opponent's win rate
    'ats_vs_tier': 0.45,               # Team's ATS vs this tier
    'overall_ats': 0.52,               # Team's overall ATS
    'adjustment': -0.02                # Applied adjustment (-2% for strong opponent)
}
```

**Integration**: Apply adjustment based on opponent tier

---

#### Method: `_calc_rest_days()`

**Purpose**: Calculate days rest between previous game and current game

**Input**:
- `team`: Team abbreviation
- `game_date`: Date of game being predicted (DATE or string)
- `seasons`: List of seasons

**Logic**:
1. Query team's most recent game BEFORE current game
2. Calculate days between: `current_game_date - previous_game_date`
3. Classify:
   - Short rest: 3-4 days (Thursday games)
   - Normal rest: 6-7 days (Sunday games)
   - Long rest: 8+ days (bye week, Monday to Sunday)

**SQL Query Pattern**:
```sql
SELECT 
    gameday,
    season,
    week
FROM games
WHERE (home_team = :team OR away_team = :team)
    AND season = ANY(:seasons)
    AND game_type = 'REG'
    AND gameday < :game_date
    AND home_score IS NOT NULL
ORDER BY gameday DESC
LIMIT 1
```

**Output**:
```python
{
    'rest_days': 6,                     # Days between games
    'rest_category': 'Normal',          # 'Short', 'Normal', 'Long'
    'previous_game_date': '2024-10-13', # Date of previous game
    'adjustment': 0.0                  # Applied adjustment (0 for normal)
}
```

**Integration**: Apply adjustment based on rest category

---

## Enhanced Prediction Formula

### Phase 1 Formula (Current)
```python
favored_prob = baseline(0.50) + team_adjustment + key_adjustment - spread_penalty
```

### Phase 2 Formula (Enhanced)
```python
# Step 1: Calculate team intelligence (weighted)
team_intelligence = (
    0.35 * situational_ats['favored_normalized'] +  # Reduced from 0.40
    0.25 * overall_ats['favored_normalized'] +       # Reduced from 0.30
    0.25 * home_away_perf['favored_normalized'] +   # Reduced from 0.30
    0.15 * recent_form['form_rate']                  # NEW
)

# Step 2: Apply team adjustment
team_adjustment = (team_intelligence - 0.5) * adjustment_factor * data_quality_factor

# Step 3: Apply contextual adjustments
contextual_adjustment = (
    divisional_adjustment +      # +2% underdog, -1% favorite in division games
    opponent_adjustment +         # -2% vs strong, +1% vs weak
    rest_adjustment               # -2% short rest, +1% long rest
)

# Step 4: Apply key number and spread penalties
penalty_adjustment = key_adjustment - spread_penalty

# Step 5: Final probability
favored_prob = baseline(0.50) + team_adjustment + contextual_adjustment + penalty_adjustment

# Step 6: Clamp to bounds
favored_prob = max(0.30, min(0.70, favored_prob))
```

---

## Implementation Steps

### Step 1: Recent Form Integration

**File**: `PredictiveDataModel/chatbot_final/SpreadPredictionCalculator.py`

**Tasks**:
1. Add `_calc_recent_form()` method (after line ~400, with other calc methods)
2. Update `predict_spread_coverage()` to call `_calc_recent_form()` for both teams
3. Modify team intelligence calculation to include form (reduce other weights)
4. Add form data to response breakdown

**Code Location**:
- Add method: After `_calc_home_away_performance()` method
- Integration: In `predict_spread_coverage()`, around line 100-110
- Response: In return dictionary, add to `breakdown` section

**Testing**:
- Test with team on 5-0 streak (form_rate should be 1.0)
- Test with team on 0-5 streak (form_rate should be 0.0)
- Test with team with <5 games (should use available games)

---

### Step 2: Divisional Game Performance

**File**: `PredictiveDataModel/chatbot_final/SpreadPredictionCalculator.py`

**Tasks**:
1. Add division mapping (hardcode or query from `teams` table)
2. Add `_calc_divisional_performance()` method
3. Update `predict_spread_coverage()` to check if divisional game
4. Apply adjustment only if `is_divisional = True`

**Code Location**:
- Division mapping: Class constant or helper method
- Add method: After `_calc_recent_form()` method
- Integration: In `predict_spread_coverage()`, after calculating team intelligence
- Adjustment: Add to `contextual_adjustment` calculation

**Testing**:
- Test with KC vs DEN (same division, AFC West)
- Test with KC vs BUF (different divisions)
- Verify underdog gets +2-3% boost in division games

---

### Step 3: Opponent Strength Adjustment

**File**: `PredictiveDataModel/chatbot_final/SpreadPredictionCalculator.py`

**Tasks**:
1. Add `_calc_opponent_strength()` method
2. Calculate opponent win rate
3. Classify tier (Strong/Mediocre/Weak)
4. Query team's ATS vs that tier
5. Apply adjustment based on tier

**Code Location**:
- Add method: After `_calc_divisional_performance()` method
- Integration: In `predict_spread_coverage()`, after divisional check
- Adjustment: Add to `contextual_adjustment` calculation

**Testing**:
- Test with strong team (KC) vs weak opponent (CAR)
- Test with strong team vs strong opponent (KC vs BUF)
- Verify adjustments: -2% vs strong, +1% vs weak

---

### Step 4: Rest Days Impact

**File**: `PredictiveDataModel/chatbot_final/SpreadPredictionCalculator.py`

**Tasks**:
1. Add `_calc_rest_days()` method
2. Query previous game date for each team
3. Calculate days between games
4. Classify rest category
5. Apply adjustment based on category

**Code Location**:
- Add method: After `_calc_opponent_strength()` method
- Integration: In `predict_spread_coverage()`, need to pass `game_date` parameter
- Adjustment: Add to `contextual_adjustment` calculation

**Note**: Current API doesn't pass `game_date`. Options:
- Add `game_date` parameter to API request
- Or calculate from `season` and `week` (estimate game date)

**Testing**:
- Test with Thursday game (short rest, 3-4 days)
- Test with Sunday game (normal rest, 6-7 days)
- Test with team coming off bye (long rest, 14+ days)

---

## Database Schema Reference

### `games` Table (Relevant Columns)

```sql
game_id VARCHAR(20) PRIMARY KEY
season INTEGER
week INTEGER
gameday DATE                    -- For rest days calculation
game_type VARCHAR(10)           -- Filter: 'REG' for regular season
home_team VARCHAR(3)
away_team VARCHAR(3)
home_score INTEGER              -- NULL if game not played yet
away_score INTEGER              -- NULL if game not played yet
spread_line DECIMAL(4,1)        -- Positive = home favored, Negative = away favored
div_game BOOLEAN                -- TRUE if divisional game
```

### Query Patterns

**Get team's games (for form calculation)**:
```sql
WHERE (home_team = :team OR away_team = :team)
    AND season = ANY(:seasons)
    AND game_type = 'REG'
    AND home_score IS NOT NULL
```

**Get games before specific week**:
```sql
AND (season < :current_season 
     OR (season = :current_season AND week < :current_week))
```

**Calculate win**:
```sql
CASE 
    WHEN home_team = :team AND home_score > away_score THEN 1
    WHEN away_team = :team AND away_score > home_score THEN 1
    ELSE 0
END as won
```

**Calculate ATS win (favored team)**:
```sql
CASE 
    WHEN spread_line > 0 AND home_team = :team 
         AND (home_score - away_score) > spread_line THEN 1
    WHEN spread_line < 0 AND away_team = :team 
         AND (away_score - home_score) > ABS(spread_line) THEN 1
    ELSE 0
END as ats_win
```

---

## Integration Pattern

### Method Call Sequence

```python
def predict_spread_coverage(self, team_a, team_b, spread, team_a_home, seasons):
    # ... existing code to determine favored/underdog ...
    
    # EXISTING queries (Phase 1)
    situational_ats = self._calc_situational_ats(...)
    overall_ats = self._calc_overall_ats(...)
    home_away_perf = self._calc_home_away_performance(...)
    
    # NEW queries (Phase 2) - all can run in parallel
    favored_form = self._calc_recent_form(favored_team, season, week, seasons)
    underdog_form = self._calc_recent_form(underdog_team, season, week, seasons)
    
    divisional_data = self._calc_divisional_performance(favored_team, underdog_team, seasons)
    
    favored_opp_strength = self._calc_opponent_strength(favored_team, underdog_team, seasons)
    underdog_opp_strength = self._calc_opponent_strength(underdog_team, favored_team, seasons)
    
    # Rest days (need game_date - may need to add to API)
    favored_rest = self._calc_rest_days(favored_team, game_date, seasons)
    underdog_rest = self._calc_rest_days(underdog_team, game_date, seasons)
    
    # Enhanced team intelligence calculation
    team_intelligence = (
        0.35 * situational_ats['favored_normalized'] +
        0.25 * overall_ats['favored_normalized'] +
        0.25 * home_away_perf['favored_normalized'] +
        0.15 * favored_form['form_rate']  # NEW
    )
    
    # Contextual adjustments
    divisional_adj = divisional_data.get('adjustment', 0.0) if divisional_data['is_divisional'] else 0.0
    opponent_adj = favored_opp_strength.get('adjustment', 0.0)
    rest_adj = favored_rest.get('adjustment', 0.0)
    
    contextual_adjustment = divisional_adj + opponent_adj + rest_adj
    
    # ... rest of calculation ...
    
    # Enhanced response
    return {
        # ... existing fields ...
        'breakdown': {
            'situational_ats': situational_ats,
            'overall_ats': overall_ats,
            'home_away': home_away_perf,
            'recent_form': {  # NEW
                'favored': favored_form,
                'underdog': underdog_form
            },
            'divisional': divisional_data,  # NEW
            'opponent_strength': {  # NEW
                'favored_vs': favored_opp_strength,
                'underdog_vs': underdog_opp_strength
            },
            'rest_days': {  # NEW
                'favored': favored_rest,
                'underdog': underdog_rest
            }
        }
    }
```

---

## Error Handling Patterns

### Database Query Errors

```python
def _calc_recent_form(self, team, current_season, current_week, seasons):
    try:
        conn = self.db.get_connection()
        # ... query ...
        if not results:
            return {'form_rate': 0.5, 'games_count': 0, 'wins': 0, 'losses': 0}
        # ... calculate ...
    except Exception as e:
        print(f"Error calculating recent form for {team}: {e}")
        return {'form_rate': 0.5, 'games_count': 0, 'wins': 0, 'losses': 0}  # Neutral default
```

### Missing Data Handling

- **No games found**: Return neutral values (0.5 for rates, 0 for adjustments)
- **Insufficient games**: Use available games (min_periods=1 for rolling calculations)
- **NULL scores**: Filter out games where `home_score IS NULL` (game not played yet)

---

## Testing Strategy

### Unit Test Structure

```python
# test_recent_form.py
def test_calc_recent_form_hot_streak():
    """Team on 5-0 streak should have form_rate = 1.0"""
    calc = SpreadPredictionCalculator()
    form = calc._calc_recent_form('KC', 2024, 10, [2024, 2025])
    assert form['form_rate'] == 1.0
    assert form['games_count'] == 5
    assert form['wins'] == 5

def test_calc_recent_form_insufficient_games():
    """Team with <5 games should use available games"""
    calc = SpreadPredictionCalculator()
    form = calc._calc_recent_form('NEW_TEAM', 2024, 3, [2024, 2025])
    assert form['games_count'] <= 3
    assert 0 <= form['form_rate'] <= 1
```

### Integration Test Structure

```python
# test_enhanced_prediction.py
def test_prediction_includes_form():
    """Prediction should include recent form in breakdown"""
    predictor = SpreadPredictionCalculator()
    result = predictor.predict_spread_coverage(
        team_a='KC', team_b='BUF', spread=-3.5,
        team_a_home=True, seasons=[2024, 2025]
    )
    assert 'recent_form' in result['breakdown']
    assert 'favored' in result['breakdown']['recent_form']
    assert 'underdog' in result['breakdown']['recent_form']
```

---

## Deployment Checklist

### Before Deploying Each Feature

- [ ] Method implemented and tested locally
- [ ] Unit tests written and passing
- [ ] Integration test confirms feature appears in response
- [ ] No breaking changes to existing API
- [ ] Error handling for edge cases (no data, insufficient games)
- [ ] Code follows existing patterns (pg8000 queries, error handling)
- [ ] Lambda deployment package created
- [ ] Tested in Lambda environment

### Deployment Order

1. **Feature 1: Recent Form** → Deploy → Test → Validate
2. **Feature 2: Divisional Performance** → Deploy → Test → Validate
3. **Feature 3: Opponent Strength** → Deploy → Test → Validate
4. **Feature 4: Rest Days** → Deploy → Test → Validate

**Do NOT deploy all at once**. Deploy one feature, test, then move to next.

---

## Key Design Principles

1. **Backward Compatibility**: Existing API responses should still work
2. **Graceful Degradation**: Missing data returns neutral values, doesn't break
3. **Additive Changes**: New features add to response, don't remove existing fields
4. **Consistent Patterns**: Follow existing code patterns (pg8000 queries, error handling)
5. **Incremental Testing**: Test each feature independently before combining

---

## Next Steps

1. Start with **Feature 1: Recent Form** (simplest, highest impact)
2. Build `_calc_recent_form()` method following the design above
3. Integrate into `predict_spread_coverage()` method
4. Test locally, then deploy to Lambda
5. Validate predictions change meaningfully for teams on streaks
6. Move to Feature 2, repeat process

---

**Status**: Ready for Implementation  
**Start Here**: Feature 1 - Recent Form Integration  
**File**: `PredictiveDataModel/chatbot_final/SpreadPredictionCalculator.py`
