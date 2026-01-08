# Cursor Development Prompt: NFL Roster & Injury Data Pipeline

## Project Context

**Objective**: Build a data collection pipeline that captures player availability and injury impact for NFL games. This data will be used for supervised learning to predict spread coverage outcomes.

**The Core Learning Question:**
> "How does player availability (especially key positions) correlate with spread coverage outcomes?"

**Example Insight We Want to Discover:**
> "When Micah Parsons (EDGE1, Tier 2) is OUT, the Cowboys' injury_impact increases by 0.40, the line shifts ~2.5 points, and they cover 15% less often as favorites."

---

## Current System State

**Existing Infrastructure:**
- Supabase PostgreSQL database
- `games` table with ~1,100 games (2022-2025) using `game_id` format: `2024_01_KC_BAL`
- `team_rankings` table with season-level ATS statistics
- `teams` table with 32 NFL teams
- Existing Lambda pipeline for game data processing
- `DatabaseConnection.py` using pg8000 for Supabase

**Data Source:**
- Sportradar NFL API (trial tier)
- API Key: `Chc55Ab5gsvTOhwrgZ6n4XuuNZfblx5Js14Pcx9c`
- Base URL: `https://api.sportradar.com/nfl/official/trial/v7/en`

**Endpoints Needed:**
1. **Game Roster**: `/games/{game_id}/roster.json` — WHO ACTUALLY PLAYED (ground truth)
2. **Depth Chart**: `/seasons/{year}/{type}/{week}/depth_charts.json` — POSITION MAPPING (used at runtime, not stored)
3. **Injuries**: `/seasons/{year}/{type}/{week}/injuries.json` — INJURY DETAILS (used at runtime, not stored)

---

## What We're Building

### Database Tables (4 Total)

**Table 1**: `position_weights` — Static reference for Boyd's position value methodology  
**Table 2**: `game_id_mapping` — Links internal game IDs to Sportradar UUIDs  
**Table 3**: `game_rosters` — 2 rows per game (home + away), contains:
- Key players (~20 per team)
- Their positions (mapped from depth chart at runtime)
- Their availability status
- Injury details (if applicable)
- Position weights and value calculations
- Aggregated team injury impact

**Table 4**: `game_injury_features` — 1 row per game, ML-ready features calculated from `game_rosters`

### Data Flow

```
FOR EACH GAME:
│
├── 1. Map internal_game_id to sportradar_game_id
│
├── 2. Call Sportradar APIs (depth chart + injuries used for mapping, not stored)
│
├── 3. Process rosters:
│       └── Map players to positions (QB1, WR2, EDGE1)
│       └── Identify injuries and calculate value_lost
│       └── Handle "next man up" (WR3 slides to WR2 role)
│
├── 4. Store in game_rosters (2 rows: home + away)
│
└── 5. Aggregate into game_injury_features (1 row per game)
```

---

## Table Schemas

### Table 1: position_weights

```sql
CREATE TABLE position_weights (
    position_key        VARCHAR(20) PRIMARY KEY,
    position_group      VARCHAR(10) NOT NULL,
    weight              DECIMAL(4,3) NOT NULL,
    tier                INTEGER NOT NULL,
    description         VARCHAR(100)
);
```

**Seed with Boyd's methodology (~40 rows):**
- QB1: 1.000 (Tier 1)
- RB1: 0.475 (Tier 2)
- WR1: 0.425 (Tier 2)
- WR2: 0.325 (Tier 3)
- EDGE1: 0.400 (Tier 2)
- etc.

### Table 2: game_id_mapping

```sql
CREATE TABLE game_id_mapping (
    internal_game_id    VARCHAR(50) PRIMARY KEY,
    sportradar_game_id  VARCHAR(50) UNIQUE,
    season              INTEGER NOT NULL,
    week                INTEGER NOT NULL,
    home_team           VARCHAR(3) NOT NULL,
    away_team           VARCHAR(3) NOT NULL,
    game_date           DATE
);
```

### Table 3: game_rosters

```sql
CREATE TABLE game_rosters (
    id                  SERIAL PRIMARY KEY,
    internal_game_id    VARCHAR(50) REFERENCES game_id_mapping(internal_game_id),
    sportradar_game_id  VARCHAR(50),
    team_id             VARCHAR(3) NOT NULL,
    season              INTEGER NOT NULL,
    week                INTEGER NOT NULL,
    is_home             BOOLEAN NOT NULL,
    
    roster_data         JSONB,
    notable_injuries    JSONB,
    
    total_injury_impact DECIMAL(5,3),
    offense_impact      DECIMAL(4,3),
    defense_impact      DECIMAL(4,3),
    tier1_impact        DECIMAL(4,3),
    tier2_impact        DECIMAL(4,3),
    
    qb1_active          BOOLEAN,
    wr1_active          BOOLEAN,
    rb1_active          BOOLEAN,
    edge1_active        BOOLEAN,
    cb1_active          BOOLEAN,
    
    created_at          TIMESTAMP DEFAULT NOW(),
    UNIQUE(internal_game_id, team_id)
);
```

**roster_data JSONB structure:**
```json
{
  "players": [
    {
      "player_id": "sportradar-uuid",
      "player_name": "Tee Higgins",
      "position_group": "OFFENSE",
      "position_key": "WR2",
      "effective_position": "WR2",
      "depth_order": 1,
      "roster_status": "OUT",
      "position_weight": 0.325,
      "effective_weight": 0.000,
      "value_lost": 0.325,
      "injury": {
        "type": "Hamstring",
        "status": "OUT",
        "duration": "3-5 weeks"
      }
    }
  ]
}
```

**notable_injuries JSONB structure:**
```json
[
  {
    "player": "Tee Higgins",
    "position": "WR2",
    "tier": 3,
    "injury": "Hamstring",
    "status": "OUT",
    "value_lost": 0.275,
    "replacement": "Andrei Iosivas"
  }
]
```

### Table 4: game_injury_features

```sql
CREATE TABLE game_injury_features (
    internal_game_id    VARCHAR(50) PRIMARY KEY REFERENCES game_id_mapping(internal_game_id),
    sportradar_game_id  VARCHAR(50),
    season              INTEGER NOT NULL,
    week                INTEGER NOT NULL,
    home_team           VARCHAR(3) NOT NULL,
    away_team           VARCHAR(3) NOT NULL,
    
    home_injury_impact  DECIMAL(5,3),
    away_injury_impact  DECIMAL(5,3),
    injury_differential DECIMAL(5,3),
    
    offense_differential DECIMAL(4,3),
    defense_differential DECIMAL(4,3),
    
    home_qb1_active     BOOLEAN,
    away_qb1_active     BOOLEAN,
    qb_advantage        VARCHAR(10),
    
    spread_line         DECIMAL(4,1),
    home_score          INTEGER,
    away_score          INTEGER,
    home_covered        BOOLEAN,
    
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);
```

---

## File Structure

```
SupervisedLearningDataCollector/
│
├── lambda_function.py
│
├── clients/
│   └── SportradarClient.py          ← INTERACTIVE SESSION 1
│
├── processors/
│   ├── PositionMapper.py            ← INTERACTIVE SESSION 2
│   └── GameRosterProcessor.py       ← CURSOR BUILDS
│
├── calculators/
│   └── InjuryImpactCalculator.py    ← INTERACTIVE SESSION 3
│
├── repositories/
│   ├── GameIdMappingRepository.py   ← CURSOR BUILDS
│   ├── GameRosterRepository.py      ← CURSOR BUILDS
│   └── InjuryFeatureRepository.py   ← CURSOR BUILDS
│
├── config.py                         ← INTERACTIVE SESSION 1
├── DatabaseConnection.py             ← CURSOR BUILDS (copy existing)
└── requirements.txt                  ← CURSOR BUILDS
```

---

## 🤝 INTERACTIVE SESSION 1: API Exploration & Config Setup

**Files to build together:**
- `clients/SportradarClient.py`
- `config.py` (position weights section)
- SQL schema creation scripts

**What we're doing:**
- Calling Sportradar endpoints manually to explore responses
- Understanding actual JSON response structure
- Identifying which fields we need
- Defining position weight values (Boyd's methodology)
- Creating database tables based on real data

**Why interactive:** Need to see actual API responses to understand data structure. Docs don't show everything. Need to discuss design decisions.

**Key Questions to Answer:**
1. What does the depth chart API actually return?
2. How are players organized? (We've seen: `offense`, `defense`, `special_teams` arrays)
3. How do we handle rate limiting (1 req/sec)?
4. What error handling do we need?
5. Which position weights matter most?

---

## 🤝 INTERACTIVE SESSION 2: Position Mapping Logic

**Files to build together:**
- `processors/PositionMapper.py`

**What we're doing:**
- Mapping raw positions (QB, WR, DE, LOLB, ROLB) to standardized keys (QB1, WR2, EDGE1)
- Using depth chart data to determine position hierarchy
- Handling edge cases:
  - Player listed at multiple positions
  - Defensive scheme differences (3-4 vs 4-3)
  - How to determine WR1 vs WR2 vs WR3
  - Offensive line positions (LT vs RT, LG vs RG)

**Why interactive:** This is the intellectual core. Many edge cases to work through. Need to make design decisions based on real data.

**Key Edge Cases:**
- Sportradar returns `"LWR"` and `"RWR"` — which is WR1?
- `"LOLB"` and `"ROLB"` — how do we determine EDGE1 vs EDGE2?
- What if a player is listed at multiple positions?
- How do we handle generic positions like `"OL"` or `"DL"`?

---

## 🤝 INTERACTIVE SESSION 3: Injury Impact Calculation

**Files to build together:**
- `calculators/InjuryImpactCalculator.py`

**What we're doing:**
- Calculating `value_lost` when starter is out
- Handling "next man up" logic (WR3 slides to WR2)
- Determining `effective_weight` for backup playing up
- Aggregating team-level injury impact
- Tracing through real examples:
  - "Parsons OUT → Cowboys injury_impact = ?"
  - "Higgins OUT, Iosivas promoted → Bengals injury_impact = ?"

**Why interactive:** Need to trace the math on real data to verify logic. This is where we calculate the features the ML model will learn from.

**"Next Man Up" Logic:**
```
STARTER OUT:
├── Starter gets: effective_weight = 0, value_lost = full position_weight
├── Backup gets: effective_position = starter's position
├── Backup's effective_weight = their position_weight × promotion_factor
└── Net value_lost = starter_weight - backup_effective_weight

EXAMPLE - Tee Higgins (WR2) OUT:
├── Higgins: effective_weight = 0, value_lost = 0.325
├── Iosivas (WR3): effective_position = WR2
├── Iosivas: effective_weight = 0.150 × 1.33 = 0.200 (doesn't fully replace WR2)
└── Net value_lost = 0.325 - 0.200 = 0.125 added to team injury_impact
```

---

## 🤖 CURSOR BUILDS INDEPENDENTLY

After the 3 interactive sessions, Cursor will build these files using the patterns we established:

### Repositories (Standard CRUD Operations)

**`repositories/GameIdMappingRepository.py`**
- Upsert game ID mappings (internal ↔ Sportradar)
- Query by season/week/teams
- Standard pg8000 patterns

**`repositories/GameRosterRepository.py`**
- Upsert roster data with JSONB
- Query by game_id or team
- Handle JSONB column updates

**`repositories/InjuryFeatureRepository.py`**
- Upsert calculated features
- Query for ML training data
- Join with games table

### Processors

**`processors/GameRosterProcessor.py`**
- Orchestrates the full roster processing flow
- Uses `PositionMapper` (from Session 2)
- Uses `InjuryImpactCalculator` (from Session 3)
- Calls Sportradar API via `SportradarClient` (from Session 1)
- Stores results via repositories

### Orchestration

**`lambda_function.py`**
- Main Lambda handler with modes:
  - `backfill` — Process historical seasons
  - `weekly` — Process current week
  - `single_game` — Process one game (testing)
- Error handling and logging
- Progress tracking

### Infrastructure

**`DatabaseConnection.py`**
- Copy from existing `PredictiveDataModel/DatabaseConnection.py`
- Minimal or no changes needed

**`requirements.txt`**
```
pg8000
requests
```

---

## Key Positions to Track (Per Team Per Game)

### Offense (10)

| Position | Weight | Tier |
|----------|--------|------|
| QB1 | 1.000 | 1 |
| RB1 | 0.475 | 2 |
| WR1 | 0.425 | 2 |
| WR2 | 0.325 | 3 |
| WR3 | 0.150 | 4 |
| TE1 | 0.300 | 3 |
| LT | 0.400 | 2 |
| RT | 0.275 | 3 |
| C | 0.275 | 3 |
| RB2 | 0.175 | 4 |

### Defense (10)

| Position | Weight | Tier |
|----------|--------|------|
| EDGE1 | 0.400 | 2 |
| EDGE2 | 0.300 | 3 |
| DT1 | 0.250 | 3 |
| LB1 | 0.200 | 4 |
| LB2 | 0.175 | 4 |
| CB1 | 0.375 | 2 |
| CB2 | 0.175 | 4 |
| S1 | 0.250 | 3 |
| S2 | 0.150 | 4 |
| DT2 | 0.150 | 4 |

---

## Environment Variables

```bash
# Supabase Database
SUPABASE_DB_HOST=db.xxxx.supabase.co
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=your-password
SUPABASE_DB_PORT=5432

# Sportradar API
SPORTRADAR_API_KEY=Chc55Ab5gsvTOhwrgZ6n4XuuNZfblx5Js14Pcx9c
SPORTRADAR_BASE_URL=https://api.sportradar.com/nfl/official/trial/v7/en
SPORTRADAR_RATE_LIMIT_MS=1000
```

---

## Success Criteria

After all sessions complete:

- [ ] `position_weights` seeded with ~40 positions
- [ ] `game_id_mapping` populated for 2022-2025 seasons
- [ ] `game_rosters` contains 2 rows per game (home + away)
- [ ] `game_injury_features` calculated for all historical games
- [ ] Can query: "Show me all games where EDGE1 was out"
- [ ] Can query: "What's the average injury_differential when home team covers?"
- [ ] Features ready to join with `games` table for ML training

---

## Session Order

```
Session 1 (Interactive): SportradarClient.py + config.py + Schema SQL
    ↓
Session 2 (Interactive): PositionMapper.py
    ↓
Session 3 (Interactive): InjuryImpactCalculator.py
    ↓
Session 4 (Cursor Builds): Repositories + GameRosterProcessor + lambda_function.py
    ↓
Session 5 (Run & Validate): Backfill historical data, verify calculations
```

---

## Current Progress

✅ **COMPLETED:**
- Sportradar API key obtained
- Test script created (`test_sportradar_api.py`)
- Depth chart API successfully called
- Response structure analyzed

**READY FOR:** Interactive Session 1 - Building SportradarClient.py together

