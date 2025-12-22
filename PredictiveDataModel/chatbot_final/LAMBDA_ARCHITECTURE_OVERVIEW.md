# ChatBot Predictive API Lambda - High-Level Architecture Overview

## Executive Summary

The ChatBot Predictive API is an AWS Lambda function that predicts NFL game spread coverage probabilities using historical team performance data. It implements a hybrid prediction model combining team-specific intelligence (situational ATS, overall ATS, home/away performance) with NFL key number adjustments and spread difficulty factors.

---

## Architecture Components

### 1. **Lambda Handler (`lambda_function.py`)**
- **Purpose**: HTTP request router and API Gateway interface
- **Key Features**:
  - Direct Lambda handler (no FastAPI/Mangum dependency)
  - CORS support with OPTIONS preflight handling
  - Path-based routing (`/`, `/health`, `/teams`, `/predict`)
  - Error handling with structured JSON responses
  - Singleton predictor initialization (reused across invocations)

**Endpoints**:
- `GET /` or `/health`: Health check with database connectivity test
- `GET /teams`: Returns list of all 32 NFL teams (hardcoded)
- `POST /predict`: Main prediction endpoint

**Request Format** (`/predict`):
```json
{
  "team_a": "GB",
  "team_b": "HOU",
  "spread": -2.5,
  "team_a_home": true,
  "seasons": [2024, 2025]
}
```

**Response Format**:
```json
{
  "success": true,
  "data": {
    "matchup": "GB @ HOU",
    "spread_line": "GB -2.5",
    "favored_team": "GB",
    "underdog_team": "HOU",
    "prediction": {
      "favored_cover_probability": 0.548,
      "underdog_cover_probability": 0.452,
      "recommended_bet": "GB",
      "confidence": 0.548,
      "edge": 0.048
    },
    "breakdown": {
      "situational_ats": {...},
      "overall_ats": {...},
      "home_away": {...}
    }
  }
}
```

---

### 2. **Database Connection (`DatabaseConnection.py`)**
- **Purpose**: Singleton PostgreSQL connection manager for Supabase
- **Technology**: `pg8000.native` (pure Python PostgreSQL driver)
- **Key Features**:
  - Singleton pattern (single connection instance)
  - SSL context configuration (certificate verification disabled for Supabase pooler)
  - Automatic reconnection on connection loss
  - Environment variable configuration:
    - `SUPABASE_DB_HOST`
    - `SUPABASE_DB_NAME` (default: 'postgres')
    - `SUPABASE_DB_USER` (default: 'postgres')
    - `SUPABASE_DB_PASSWORD`
    - `SUPABASE_DB_PORT` (default: 5432)
  - Connection pooling support (port 6543 recommended for Lambda)

**Connection Lifecycle**:
1. First access creates connection
2. Subsequent accesses reuse connection
3. Connection health checked via `SELECT 1`
4. Auto-reconnect on failure

---

### 3. **Spread Prediction Calculator (`SpreadPredictionCalculator.py`)**
- **Purpose**: Core prediction engine implementing hybrid NFL spread coverage model
- **Size**: ~530 lines
- **Dependencies**: `pandas`, `numpy`, `pg8000`, `DatabaseConnection`

#### 3.1 Prediction Model Architecture

**Baseline Philosophy**: 
- Starts from 50/50 baseline (Vegas efficiency assumption)
- Applies team intelligence as adjustments
- Allows non-linear probability changes (larger spreads can indicate mismatches, not just difficulty)

**Core Formula**:
```
Final_Probability = Baseline(0.50) + Team_Adjustment + Key_Adjustment - Spread_Penalty
```

Where:
- `Team_Adjustment = (Team_Intelligence - 0.5) × Adjustment_Factor × Data_Quality`
- `Key_Adjustment = -Key_Impact × 0.15` (penalty for crossing key numbers)
- `Spread_Penalty = f(spread_abs)` (tiered penalty based on spread magnitude)

#### 3.2 Team Intelligence Calculation

**Three Weighted Factors** (when sufficient data):
1. **Situational ATS (40% weight)**: Historical performance in similar spread ranges
2. **Overall ATS (30% weight)**: All-time ATS performance
3. **Home/Away Performance (30% weight)**: Location-specific win rate

**Data Quality Handling**:
- Minimum threshold: 3 games for situational data
- If insufficient: Falls back to Overall ATS (50%) + Home/Away (50%)
- Data quality factor: `min(1.0, total_games / 10.0)` scales adjustment strength

**Adjustment Factor Scaling**:
- Base: ±20% adjustment (`adjustment_factor = 0.4`)
- Large spreads (>6): ±24% adjustment (mismatches allow stronger team signals)

#### 3.3 Key Number System

**NFL Key Numbers** (common margins of victory):
```python
KEY_NUMBERS = {
    3: 0.1552,   # Field goal - 15.52% of games
    7: 0.1018,   # Touchdown - 10.18% of games
    10: 0.0688,  # FG + TD - 6.88% of games
    6: 0.0701,   # TD no PAT - 7.01% of games
    4: 0.0543,   # FG + Safety - 5.43% of games
    14: 0.0432,  # Two TDs - 4.32% of games
    17: 0.0289,  # TD + FG + TD - 2.89% of games
}
```

**Key Number Detection**:
- Checks if spread is within ±0.5 of a key number
- Example: Spread 6.5 or 7.5 triggers key number 7
- Applies penalty: `-key_impact × 0.15` (15% of key probability)

#### 3.4 Spread Penalty System

**Tiered Penalty Structure** (minimal to preserve team intelligence):
- **≤3 points**: `spread_abs × 0.005` (0.5% per point)
- **3-7 points**: `0.015 + (spread_abs - 3) × 0.008` (~0.5-1.5% total)
- **>7 points**: `0.047 + (spread_abs - 7) × 0.01` (~1.5-3% for large spreads)

**Rationale**: Larger spreads indicate better teams (mismatches), so penalty is minimal to allow team intelligence to dominate.

#### 3.5 Probability Bounds

- **Clamping**: `max(0.30, min(0.70, probability))`
- **Rationale**: Prevents extreme predictions while allowing team intelligence to drive results

---

### 4. **Database Query Methods**

#### 4.1 Situational ATS (`_calc_situational_ats`)
- **Purpose**: Historical ATS performance in specific spread ranges
- **Spread Ranges**: "0-2", "2-4", "4-7", "7-10", "10+"
- **Query Logic**:
  - Filters games by spread range, season, game type (REG only)
  - Calculates ATS wins: `(team_score - opponent_score) > ABS(spread_line)`
  - Handles home/away perspective separately
  - Returns: `{total_games, ats_wins, win_rate, normalized_rate}` for both favored and underdog

#### 4.2 Overall ATS (`_calc_overall_ats`)
- **Purpose**: All-time ATS performance regardless of spread
- **Query Logic**:
  - Aggregates all games for each team
  - Calculates overall ATS win rate
  - Returns normalized rates for both teams

#### 4.3 Home/Away Performance (`_calc_home_away_performance`)
- **Purpose**: Location-specific win rate (not ATS, actual wins)
- **Query Logic**:
  - Filters by home/away location
  - Calculates win rate: `(wins / total_games)`
  - Returns normalized rates for both teams

**Normalization**: All rates normalized to 0-1 scale using min-max normalization for consistent weighting.

---

## Data Flow

```
1. API Request → Lambda Handler
   ↓
2. Parse request (team_a, team_b, spread, team_a_home, seasons)
   ↓
3. SpreadPredictionCalculator.predict_spread_coverage()
   ↓
4. Determine favored/underdog roles based on spread sign
   ↓
5. Query Database (3 parallel queries):
   - Situational ATS (spread range + location)
   - Overall ATS (all games)
   - Home/Away Performance (location-specific)
   ↓
6. Calculate Team Intelligence (weighted combination)
   ↓
7. Apply Baseline (0.50) + Adjustments:
   - Team Adjustment (from intelligence)
   - Key Number Adjustment (if applicable)
   - Spread Penalty (tiered)
   ↓
8. Clamp to bounds (0.30 - 0.70)
   ↓
9. Build Response Dictionary
   ↓
10. Return JSON via API Gateway
```

---

## Key Design Decisions

### 1. **Baseline-Driven Approach**
- Starts from 50/50 (Vegas efficiency)
- Team intelligence is an adjustment, not replacement
- Prevents overconfidence in sparse data scenarios

### 2. **Non-Linear Spread Handling**
- Larger spreads can have higher probabilities (mismatch indicator)
- Team intelligence matters more for large spreads
- Minimal spread penalty preserves team signals

### 3. **Data Quality Scaling**
- Adjustments scaled by data quality factor
- Falls back gracefully when situational data is sparse
- Prevents wild swings from small sample sizes

### 4. **Key Number Integration**
- Hybrid approach: Team intelligence + NFL scoring patterns
- Key numbers penalize probability (harder to cover across common margins)
- Subtle adjustment (15% of key probability) to not override team factors

### 5. **Independent Team Calculations**
- Favored and underdog probabilities calculated separately
- Each team's intelligence derived from their own historical perspective
- Currently underdog_prob = 1 - favored_prob (work in progress for independent calculation)

---

## Dependencies & Deployment

### Python Packages:
- `pg8000` (PostgreSQL driver)
- `pandas` (data manipulation - via AWS Lambda Layer)
- `numpy` (numerical operations - via AWS Lambda Layer)
- Standard library: `json`, `os`, `logging`, `typing`, `ssl`

### AWS Lambda Configuration:
- **Runtime**: Python 3.x
- **Layers**: AWS SDK Pandas Layer (provides pandas/numpy)
- **Environment Variables**: Supabase database credentials
- **Memory**: 128 MB (as seen in CloudWatch logs)
- **Timeout**: Default (likely 30-60 seconds)

### Deployment Package:
- `lambda_function.py` (entry point)
- `SpreadPredictionCalculator.py` (core logic)
- `DatabaseConnection.py` (database manager)
- `pg8000/` (PostgreSQL driver package)
- `asn1crypto/`, `dateutil/`, `scramp/`, `six.py` (pg8000 dependencies)

---

## Database Schema (Inferred)

### `games` Table:
- `season` (integer)
- `home_team` (string, team abbreviation)
- `away_team` (string, team abbreviation)
- `spread_line` (float, positive for home favorite, negative for away favorite)
- `home_score` (integer, nullable)
- `away_score` (integer, nullable)
- `game_type` (string, e.g., 'REG' for regular season)

**Query Patterns**:
- Filter by season, team, spread range, game type
- Calculate ATS results: `(team_score - opponent_score) > ABS(spread_line)`
- Aggregate wins, losses, total games

---

## Performance Characteristics

### Cold Start:
- Database connection establishment: ~2.6-2.8 seconds (from CloudWatch logs)
- Predictor initialization: Minimal (singleton pattern)

### Warm Invocation:
- Database query execution: ~50-150ms
- Prediction calculation: <10ms (in-memory)
- Total response time: ~100-200ms (excluding cold start)

### Scalability:
- Stateless design (except singleton connection)
- Connection pooling recommended (Supabase port 6543)
- No caching layer (queries database on every request)

---

## Error Handling

### Database Errors:
- Connection failures: Auto-reconnect
- Query errors: Caught and returned as 500 with error message
- Type mismatches: Handled with explicit conversions (Decimal → float, None → 0)

### Validation:
- Missing required parameters: 400 Bad Request
- Invalid team abbreviations: Not validated (relies on database)
- Invalid spread values: Handled by float conversion

### Logging:
- CloudWatch logs for debugging
- Print statements for calculation breakdown (visible in CloudWatch)
- Error tracebacks included in responses (development mode)

---

## Future Enhancements (Inferred from Code Comments)

1. **Independent Underdog Calculation**: Currently `underdog_prob = 1 - favored_prob`, but code structure suggests plans for independent calculation based on underdog's historical performance.

2. **Caching Layer**: No caching currently - could cache team statistics to reduce database queries.

3. **Advanced Features**: 
   - Weather adjustments
   - Injury impact
   - Recent form weighting
   - Opponent strength adjustments

---

## Testing & Validation

### Test Scenarios:
- Jets @ Patriots, spread -5.5 (Patriots favored at home)
- Falcons @ Commanders, spread -1.5 (Falcons favored on road)
- Green Bay @ Houston, various spreads (2.5, 3.5, 6.5, 7.5, 8.5, 10.5)

### Validation Checks:
- Probability decreases generally as spread increases (with exceptions for mismatches)
- Key numbers (3, 7, 10) properly penalize probabilities
- Data quality scaling prevents extreme predictions on sparse data
- CORS handling works for web interface

---

## Integration Points

### External Services:
- **Supabase PostgreSQL**: Historical game data
- **AWS API Gateway**: HTTP endpoint exposure
- **AWS S3**: Static HTML interface (`nfl-prediction.html`)

### Frontend Interface:
- Simple HTML form with team selectors, spread input
- JavaScript fetch API to call Lambda endpoint
- Displays prediction results (probabilities, recommended bet, confidence)

---

## Code Quality Patterns

1. **Singleton Pattern**: DatabaseConnection ensures single connection instance
2. **Separation of Concerns**: Handler, Calculator, Database layers separated
3. **Type Hints**: Python type annotations for clarity
4. **Error Handling**: Try-catch blocks with structured error responses
5. **Logging**: CloudWatch-compatible print statements
6. **Documentation**: Docstrings for all public methods

---

## Summary

The ChatBot Predictive API Lambda is a production-ready NFL spread prediction service that combines:
- **Team-specific intelligence** (historical ATS performance)
- **NFL scoring patterns** (key number adjustments)
- **Spread difficulty factors** (tiered penalties)
- **Data quality awareness** (graceful degradation)

The model prioritizes team intelligence over linear spread penalties, allowing for realistic predictions where strong teams in mismatches (large spreads) can have higher cover probabilities than close games (small spreads).

