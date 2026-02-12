# Player Impact Calculator

A modular system for calculating injury impact on NFL teams using **REAL DATA** from Sportradar API, S3 historical data, Madden ratings, and Supabase storage.

## 🚀 NEW: Real Data Integration

This system now integrates with:
- **Sportradar API**: Live NFL depth charts, injuries, and game rosters
- **AWS S3**: Historical game data (2022, 2023, 2024) and Madden CSV ratings
- **Supabase**: PostgreSQL database for storing player ratings and injury calculations

## 🏗️ Architecture

The system is composed of 9 interconnected modules that work together in a pipeline:

```
SportradarClient → PositionMapper → S3DataLoader (Madden) → PlayerWeightAssigner → InjuryImpactCalculator → GameProcessor → SupabaseStorage
```

### Module Overview

| Module | Purpose | Input | Output |
|--------|---------|-------|--------|
| **SportradarClient** | Fetch real-time NFL data | API key | Depth charts, rosters, injuries |
| **S3DataLoader** | Load historical data & Madden ratings | S3 bucket | CSV DataFrames |
| **PositionMapper** | Standardize positions | Raw depth chart | Mapped players by position |
| **MaddenRatingMapper** | Get player ratings | Player ID | Madden rating (30-99) |
| **PlayerWeightAssigner** | Calculate impact weights | Mapped players + ratings | Weighted players |
| **InjuryImpactCalculator** | Calculate injury impact | Weighted players + roster | Impact metrics |
| **GameProcessor** | Orchestrate pipeline | Game IDs + team IDs | Full game analysis |
| **SupabaseStorage** | Store/retrieve data | Injury impacts | Database records |

---

## 📦 Module Details

### 1. SportradarClient
**Purpose:** Fetch NFL data from Sportradar API

**Methods:**
- `get_depth_chart(season, week, season_type)` - Weekly depth charts
- `get_injuries(season, week, season_type)` - Current injury reports  
- `get_game_roster(game_id)` - Game-specific active/inactive status
- `get_team_roster(team_id, season)` - Full team roster
- `get_player_profile(player_id)` - Detailed player profile

**API Configuration:**
```bash
# Environment variables
SPORTRADAR_API_KEY=bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm
SPORTRADAR_BASE_URL=https://api.sportradar.com/nfl/official/trial/v7/en
```

**Rate Limiting:** Built-in 1 request/second throttling for trial API

---

### 2. S3DataLoader
**Purpose:** Load historical game data and Madden ratings from AWS S3

**Methods:**
- `load_madden_ratings(season)` - Load Madden CSV for a season
- `load_historical_games(season)` - Load game data for a year
- `load_all_historical_games(seasons)` - Load multiple seasons
- `list_available_madden_files()` - List Madden CSVs in S3
- `list_available_game_data_files()` - List game data CSVs in S3

**S3 Configuration:**
```python
bucket = 'sportsdatacollection'
paths = [
    's3://sportsdatacollection/raw-data/2024.csv',
    's3://sportsdatacollection/raw-data/2023.csv',
    's3://sportsdatacollection/raw-data/2022.csv',
    's3://sportsdatacollection/madden-ratings/*.csv'
]
```

**Caching:** Automatically caches loaded DataFrames in memory

---

### 3. PositionMapper
**Purpose:** Standardize NFL position names across data sources

**Supported Positions:**
- `QB` - Quarterback
- `RB` - Running Back
- `WR` - Wide Receiver
- `TE` - Tight End
- `LT/RT/LG/RG/C` - Offensive Line
- `DE/DT/NT` - Defensive Line
- `LB/MLB/OLB/ILB` - Linebackers
- `CB/S/FS/SS` - Secondary

**Methods:**
- `map_position(raw_position)` - Convert raw position to standard
- `map_team_depth_chart(team_data)` - Map entire team's depth chart

---

### 4. MaddenRatingMapper
**Purpose:** Look up player ratings from Madden NFL dataset

**CSV Format Expected:**
```csv
player_name,overall_rating,position,team
Patrick Mahomes,99,QB,KC
Josh Allen,95,QB,BUF
...
```

**Methods:**
- `get_rating(player_name, position)` - Get player's Madden rating
- Default rating: 70 ("average") if player not found

---

### 5. PlayerWeightAssigner
**Purpose:** Calculate impact weights using position-adjusted Madden ratings

**Weighting Formula:**
```python
# QB: Higher floor (matters more)
qb_weight = (rating - 30) / 70  # 30-99 range

# RB: Lower ceiling (matters less)  
rb_weight = (rating - 50) / 50  # 50-99 range
```

**Position Value Multipliers:**
Based on Boyd's LBAM methodology:
- QB: 5.00x (most important)
- LT/RT: 2.30x
- CB: 1.60x
- DE: 1.50x
- WR: 1.35x
- C: 1.15x
- ...and more

**Methods:**
- `assign_weights(mapped_players)` - Calculate weights for all players

---

### 6. InjuryImpactCalculator
**Purpose:** Calculate team-level injury impact scores

**Calculation Logic:**
1. Identify inactive starters (compare depth chart vs game roster)
2. Sum raw impact (starter weights)
3. Apply replacement adjustment (backup weights if available)

**Output Metrics:**
```python
{
    'inactive_starter_count': 3,           # Number of starters out
    'raw_injury_score': 2.45,              # Total weight of inactive starters
    'replacement_adjusted_score': 1.82,    # Accounting for backup quality
    'inactive_starters': [...]             # List of inactive player details
}
```

**Methods:**
- `calculate_impact(weighted_players, game_roster)` - Calculate impact for one team

---

### 7. GameProcessor
**Purpose:** Orchestrate the full pipeline for a single game

**Process Flow:**
```
1. Fetch weekly depth chart (all teams)
2. Fetch game roster (active/inactive)
3. Extract home team depth chart
4. Extract away team depth chart  
5. Extract home team roster
6. Extract away team roster
7. Process home team → injury impact
8. Process away team → injury impact
9. Calculate net advantage
10. Return results
```

**Methods:**
- `process_game(game_id, home_team_id, away_team_id, season, week, season_type='REG')`

**Output:**
```python
{
    'game_id': '...',
    'home_team_id': '...',
    'away_team_id': '...',
    'home_impact': {...},      # Home team metrics
    'away_impact': {...},      # Away team metrics
    'net_injury_advantage': 0.63  # Positive = home advantage
}
```

---

### 8. SupabaseStorage
**Purpose:** Store and retrieve player ratings and injury calculations in PostgreSQL

**Database Tables:**
- `player_ratings` - Player weights and Madden ratings
- `injury_impact` - Game-by-game injury impact calculations
- `inactive_players` - Tracking which players were out each game

**Methods:**
- `store_player_rating(player_data)` - Store/update player rating
- `store_player_ratings_batch(players)` - Bulk insert player ratings
- `get_player_rating(player_id)` - Retrieve player rating
- `store_injury_impact(impact_data)` - Store game injury impact
- `get_game_injury_impact(game_id)` - Retrieve injury impacts for a game
- `store_inactive_player(inactive_data)` - Record inactive player

**Supabase Configuration:**
```bash
# Environment variables
SUPABASE_DB_HOST=db.xxx.supabase.co
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=your_password
SUPABASE_DB_PORT=5432  # or 6543 for pooler
```

**Schema:**
```sql
-- Player ratings with weights
CREATE TABLE player_ratings (
    player_id VARCHAR(255) PRIMARY KEY,
    player_name VARCHAR(255),
    position VARCHAR(50),
    team VARCHAR(10),
    madden_rating INTEGER,
    position_key VARCHAR(50),
    weight DECIMAL(10, 4),
    tier INTEGER,
    season INTEGER,
    updated_at TIMESTAMP
);

-- Injury impact per game/team
CREATE TABLE injury_impact (
    id SERIAL PRIMARY KEY,
    game_id VARCHAR(255),
    team_id VARCHAR(255),
    season INTEGER,
    week INTEGER,
    total_injury_score DECIMAL(10, 4),
    replacement_adjusted_score DECIMAL(10, 4),
    inactive_starter_count INTEGER,
    tier_breakdowns (tier_1_out, tier_2_out, etc.),
    key_position_flags (qb1_active, rb1_active, etc.),
    UNIQUE(game_id, team_id)
);
```

---

## 🚀 Quick Start

### Installation

1. Install dependencies:
```bash
cd PredictiveDataModel/PlayerImpactCalculator
pip install -r requirements.txt
```

2. Set environment variables:
```bash
# Sportradar API
export SPORTRADAR_API_KEY=bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm

# Supabase Database
export SUPABASE_DB_HOST=db.xxx.supabase.co
export SUPABASE_DB_PASSWORD=your_password
export SUPABASE_DB_NAME=postgres
export SUPABASE_DB_USER=postgres
export SUPABASE_DB_PORT=5432

# AWS credentials (for S3 access)
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
```

### Basic Usage with Real Data

```python
from SportradarClient import SportradarClient
from PositionMapper import PositionMapper
from PlayerWeightAssigner import PlayerWeightAssigner
from InjuryImpactCalculator import InjuryImpactCalculator
from game_processor import GameProcessor
from S3DataLoader import S3DataLoader
from SupabaseStorage import SupabaseStorage

# Initialize components
client = SportradarClient(api_key='bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm')
s3_loader = S3DataLoader(bucket_name='sportsdatacollection')
storage = SupabaseStorage()

# Load Madden ratings from S3
madden_df = s3_loader.load_madden_ratings(season=2025)

# Initialize pipeline
mapper = PositionMapper()
assigner = PlayerWeightAssigner(madden_data=madden_df)
calculator = InjuryImpactCalculator()

# Create game processor
processor = GameProcessor(client, mapper, assigner, calculator)

# Process a game (fetches live data from Sportradar)
result = processor.process_game(
    game_id="game-uuid",
    home_team_id="home-uuid",
    away_team_id="away-uuid",
    season=2025,
    week=10
)

# Store results in Supabase
storage.store_injury_impact({
    'game_id': result['game_id'],
    'team_id': result['home_team_id'],
    'season': 2025,
    'week': 10,
    'season_type': 'REG',
    **result['home_impact']
})

print(f"Net advantage: {result['net_injury_advantage']}")
```

See `example_usage.py` for a complete working example with all real data sources.

---

## 📊 Understanding the Output

### Net Injury Advantage
- **Positive value** → Home team has advantage (less injured)
- **Negative value** → Away team has advantage (less injured)
- **Zero** → Both teams equally impacted

### Impact Score Interpretation
- `0.0-1.0` - Minor impact (backups, low-value positions)
- `1.0-3.0` - Moderate impact (starters at mid-value positions)
- `3.0-5.0` - Major impact (star QB, elite LT, etc.)
- `5.0+` - Catastrophic impact (multiple star injuries)

### Replacement Adjustment
The difference between raw score and adjusted score shows backup quality:
- **Small difference** → High-quality backup available
- **Large difference** → Significant drop-off to backup

---

## 🧪 Testing

Run tests for individual modules:

```bash
# Test position mapping
python -m pytest test_position_mapper.py

# Test weight assignment
python -m pytest test_player_weight_assigner.py

# Test injury calculation
python -m pytest test_injury_impact_calculator.py
```

---

## 🔧 Configuration

### Position Value Multipliers
Edit `PlayerWeightAssigner.py` to adjust position importance:

```python
self.position_values = {
    'QB': 5.0,    # Modify these values
    'LT': 2.3,
    'CB': 1.6,
    # ... etc
}
```

### Rating Curves
Edit `PlayerWeightAssigner.py` to adjust rating-to-weight conversion:

```python
def _calculate_position_weight(self, rating, position):
    if position == 'QB':
        return (rating - 30) / 70  # Adjust floor/ceiling
    # ...
```

---

## 📝 Data Sources & Requirements

### Sportradar API
- **API Key:** `bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm`
- **Base URL:** `https://api.sportradar.com/nfl/official/trial/v7/en`
- **Endpoints Used:**
  - `/seasons/{year}/{type}/{week}/depth_charts.json`
  - `/seasons/{year}/{type}/{week}/injuries.json`
  - `/games/{game_id}/roster.json`

### AWS S3 Bucket: `sportsdatacollection`
**Historical Game Data:**
- `s3://sportsdatacollection/raw-data/2024.csv`
- `s3://sportsdatacollection/raw-data/2023.csv`
- `s3://sportsdatacollection/raw-data/2022.csv`

**Madden Ratings:**
- `s3://sportsdatacollection/madden-ratings/*.csv`

**Expected CSV Columns:**
- Madden: `player_id`, `player_name`, `overallrating`, `position`, `team`
- Games: Varies by source (automatically handled)

### Supabase PostgreSQL
- **Connection:** Uses `pg8000` with SSL
- **Tables:** Auto-created on first run
  - `player_ratings` - Player weights and ratings
  - `injury_impact` - Game-by-game calculations
  - `inactive_players` - Injury tracking

---

## 🤝 Contributing

When adding new features:
1. Keep modules focused on single responsibility
2. Add logging for debugging
3. Handle missing data gracefully (default values)
4. Update this README with new functionality

---

## 📚 References

- **Position Values:** Boyd's LBAM (Lineup-Based Adjustment Method)
- **API Documentation:** [Sportradar NFL API](https://developer.sportradar.com/docs/read/american_football/NFL_v7)
- **Madden Ratings:** EA Sports Madden NFL

---

## 🐛 Common Issues

### Issue: "Team not found in depth chart"
**Solution:** Verify team UUID matches Sportradar format (not NFL.com or other sources)

### Issue: "Player not found in Madden data"
**Solution:** System defaults to rating=70 (average). S3DataLoader handles missing columns gracefully.

### Issue: "API rate limit exceeded"
**Solution:** Built-in 1 req/sec throttling. Trial API allows limited calls. Use caching for repeated requests.

### Issue: "S3 file not found"
**Solution:** Check bucket name and file paths. Use `list_available_*_files()` methods to verify.

### Issue: "Supabase connection timeout"
**Solution:** Verify environment variables. Use port 5432 for direct connection or 6543 for pooler.

### Issue: "Missing AWS credentials"
**Solution:** Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables or configure AWS CLI.

---

## 📧 Support

For questions or issues, check:
1. This README
2. `example_usage.py` for working code
3. Module docstrings for detailed method documentation

