# PFF Game Processor Lambda

**AWS Lambda function for calculating NFL game player impact using PFF grades.**

Processes games in batches by querying `game_id_mapping` table, fetching rosters from Sportradar, calculating weighted player impact using PFF grades, and storing results back in `game_id_mapping`.

---

## Overview

This Lambda replaces Madden-based player impact calculations with **PFF (Pro Football Focus) grades**.

### Workflow

1. **Query** `game_id_mapping` table for games to process (filtered by season/week)
2. **Extract** `sportradar_id` for each game
3. **Fetch** active rosters from Sportradar API
4. **Map** player positions (QB1, WR2, EDGE1, etc.)
5. **Retrieve** PFF grades from database (position-specific tables)
6. **Calculate** weighted impact scores for home and away teams
7. **Update** `game_id_mapping` with impact data

---

## Architecture

### Components

1. **lambda_function.py** - Main handler and batch orchestration
2. **GameImpactProcessor.py** - Core game processing logic
3. **PlayerWeightAssigner.py** - Assigns weights using PFF grades + position importance
4. **PositionMapper.py** - Standardizes positions across data sources
5. **SportradarClient.py** - Fetches game rosters from Sportradar API
6. **PFFDataFetcher.py** - Fetches PFF grades with caching
7. **DatabaseUtils.py** - Database operations (fetch games, fetch grades, store results)

### Data Flow

```
game_id_mapping (query games to process)
    ↓
Extract sportradar_id
    ↓
Sportradar API (fetch active roster)
    ↓
Position Mapper (QB1, WR2, EDGE1)
    ↓
PFF Database (fetch grades by position)
    ↓
PlayerWeightAssigner (weight = position × PFF tier)
    ↓
GameImpactProcessor (aggregate home/away scores)
    ↓
game_id_mapping (UPDATE with impact scores)
```

---

## PFF Grade Mapping

### Position → Table → Column

| Position | PFF Table | Grade Column | Notes |
|----------|-----------|--------------|-------|
| QB | `qb_pff_ratings` | `grades_offense` | Overall QB grade |
| RB | `rb_pff_ratings` | `grades_offense` | Overall RB grade |
| WR | `wr_pff_ratings` | `grades_offense` | Overall WR grade |
| TE | `wr_pff_ratings` | `grades_offense` | TEs in WR table |
| LT/RT/LG/RG/C | `oline_pff_ratings` | `(grades_pass_block + grades_run_block) / 2` | Averaged |
| DE/DT/LB/CB/S | `defense_pff_ratings` | `grades_defense` | Overall defense grade |

### PFF Grade Tiers

| Tier | Grade Range | Description | Weight Modifier |
|------|-------------|-------------|-----------------|
| 1 | 85-100 | Elite | 1.5x |
| 2 | 75-84 | Good | 1.2x |
| 3 | 60-74 | Average | 1.0x |
| 4 | <60 | Below Average | 0.8x |

---

## Lambda Event Formats

### 1. Process All Games (Default)

```json
{}
```

### 2. Filter by Season

```json
{
  "season": 2024
}
```

### 3. Filter by Season and Week

```json
{
  "season": 2024,
  "week": 10
}
```

### 4. Limit Number of Games

```json
{
  "season": 2024,
  "limit": 50
}
```

### 5. Single Game (Testing Only)

```json
{
  "game_id": "2024_10_BUF_KC",
  "sportradar_id": "abc-123-def-456",
  "season": 2024,
  "week": 10,
  "home_team": "KC",
  "away_team": "BUF"
}
```

---

## Environment Variables

Set these in AWS Lambda configuration:

| Variable | Description | Example |
|----------|-------------|---------|
| `SPORTRADAR_API_KEY` | Sportradar API key | `abc123...` |
| `DB_HOST` | PostgreSQL host | `your-db.supabase.co` |
| `DB_NAME` | Database name | `postgres` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASSWORD` | Database password | `your-password` |
| `DB_PORT` | Database port | `5432` |

---

## Database Schema

### Alter `game_id_mapping` Table

**Run this SQL script ONCE before first deployment:**

```sql
-- File: alter_game_mapping_table.sql

-- Add home team impact columns
ALTER TABLE game_id_mapping 
ADD COLUMN IF NOT EXISTS home_total_impact DECIMAL(10,4),
ADD COLUMN IF NOT EXISTS home_active_players INTEGER,
ADD COLUMN IF NOT EXISTS home_tier_1_count INTEGER,
ADD COLUMN IF NOT EXISTS home_tier_2_count INTEGER,
ADD COLUMN IF NOT EXISTS home_tier_3_count INTEGER,
ADD COLUMN IF NOT EXISTS home_tier_4_count INTEGER,
ADD COLUMN IF NOT EXISTS home_tier_5_count INTEGER,
ADD COLUMN IF NOT EXISTS home_qb1_active BOOLEAN,
ADD COLUMN IF NOT EXISTS home_rb1_active BOOLEAN,
ADD COLUMN IF NOT EXISTS home_wr1_active BOOLEAN,
ADD COLUMN IF NOT EXISTS home_edge1_active BOOLEAN,
ADD COLUMN IF NOT EXISTS home_cb1_active BOOLEAN,
ADD COLUMN IF NOT EXISTS home_lt_active BOOLEAN,
ADD COLUMN IF NOT EXISTS home_s1_active BOOLEAN;

-- Add away team impact columns
ALTER TABLE game_id_mapping 
ADD COLUMN IF NOT EXISTS away_total_impact DECIMAL(10,4),
ADD COLUMN IF NOT EXISTS away_active_players INTEGER,
ADD COLUMN IF NOT EXISTS away_tier_1_count INTEGER,
ADD COLUMN IF NOT EXISTS away_tier_2_count INTEGER,
ADD COLUMN IF NOT EXISTS away_tier_3_count INTEGER,
ADD COLUMN IF NOT EXISTS away_tier_4_count INTEGER,
ADD COLUMN IF NOT EXISTS away_tier_5_count INTEGER,
ADD COLUMN IF NOT EXISTS away_qb1_active BOOLEAN,
ADD COLUMN IF NOT EXISTS away_rb1_active BOOLEAN,
ADD COLUMN IF NOT EXISTS away_wr1_active BOOLEAN,
ADD COLUMN IF NOT EXISTS away_edge1_active BOOLEAN,
ADD COLUMN IF NOT EXISTS away_cb1_active BOOLEAN,
ADD COLUMN IF NOT EXISTS away_lt_active BOOLEAN,
ADD COLUMN IF NOT EXISTS away_s1_active BOOLEAN;

-- Add impact differential
ALTER TABLE game_id_mapping
ADD COLUMN IF NOT EXISTS impact_differential DECIMAL(10,4),
ADD COLUMN IF NOT EXISTS impact_calculated_at TIMESTAMP;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_game_mapping_impact_diff 
ON game_id_mapping(impact_differential DESC);

CREATE INDEX IF NOT EXISTS idx_game_mapping_season_week_impact 
ON game_id_mapping(season, week) 
WHERE home_total_impact IS NOT NULL;
```

### Impact Differential

`impact_differential = home_total_impact - away_total_impact`

- **Positive** = home team has roster advantage
- **Negative** = away team has roster advantage

---

## Deployment

### 1. Run Database Migration

```bash
psql -h your_host -U your_user -d your_db -f alter_game_mapping_table.sql
```

### 2. Create Deployment Package

```bash
cd PFFGameProcessor
python create_zip.py
```

This creates `pff_game_processor.zip` (~15MB).

### 3. Upload to AWS Lambda

- **Function name**: `PFFGameProcessor`
- **Runtime**: Python 3.11
- **Handler**: `lambda_function.lambda_handler`
- **Timeout**: 300 seconds (5 minutes)
- **Memory**: 512 MB

### 4. Set Environment Variables

Configure the environment variables listed above in the Lambda console.

---

## Example Output

### Batch Mode (Process Week 10 of 2024 Season)

**Input:**
```json
{
  "season": 2024,
  "week": 10
}
```

**Output:**
```json
{
  "statusCode": 200,
  "body": {
    "success": true,
    "games_processed": 14,
    "total_games": 14,
    "filters": {
      "season": 2024,
      "week": 10,
      "limit": null
    },
    "results": [
      {
        "game_id": "2024_10_BUF_KC",
        "success": true,
        "impact_differential": 3.245,
        "home_impact": 45.675,
        "away_impact": 42.430
      },
      {
        "game_id": "2024_10_SF_TB",
        "success": true,
        "impact_differential": -1.120,
        "home_impact": 41.890,
        "away_impact": 43.010
      }
    ]
  }
}
```

### What Happens

1. Lambda queries `game_id_mapping` for all games in season 2024, week 10
2. For each game:
   - Fetches active roster from Sportradar
   - Calculates weighted PFF impact for home and away teams
   - Updates `game_id_mapping` with `home_total_impact`, `away_total_impact`, and `impact_differential`
3. Returns summary of processed games

---

## Testing

### Test Event: Single Week

```json
{
  "season": 2024,
  "week": 1,
  "limit": 5
}
```

This processes the first 5 games from Week 1 of 2024.

### Test Event: Entire Season

```json
{
  "season": 2023
}
```

This processes all games from 2023 (may take 5-10 minutes depending on API rate limits).

---

## Key Differences from Madden Version

| Aspect | Madden Version | PFF Version |
|--------|----------------|-------------|
| **Data Source** | Madden ratings (static, game-based) | PFF grades (real performance data) |
| **Grade Range** | 0-99 (Madden OVR) | 0-100 (PFF grades) |
| **Tiers** | Based on Madden rating buckets | Based on PFF grade ranges (85+, 75-84, etc.) |
| **Storage** | Separate `madden_game_player_impact` table | Updates `game_id_mapping` directly |
| **OL Grades** | Single Madden rating | Averaged `(pass_block + run_block) / 2` |
| **Query Logic** | Fetches Madden from separate table | Fetches PFF from position-specific tables |
| **Realism** | Based on video game ratings | Based on actual NFL performance analysis |

---

## Workflow Integration

This Lambda fits into the larger NFL prediction pipeline:

```
1. GameIdMapper Lambda
   └── Creates game_id_mapping with sportradar_id

2. PFF Position Lambdas (QB, RB, WR, OL, DEF)
   └── Populate position-specific PFF tables

3. PFFGameProcessor Lambda (THIS)
   └── Calculates impact and updates game_id_mapping

4. ML Training Pipeline
   └── Uses game_id_mapping with impact data for predictions
```

---

## Advantages of PFF Over Madden

1. **Real Performance Data**: PFF grades based on actual NFL film analysis
2. **Weekly Updates**: PFF grades updated after each game
3. **Position-Specific**: Separate grades for pass blocking, run blocking, coverage, etc.
4. **Granular**: More detailed than a single Madden OVR rating
5. **Injury Impact**: PFF accounts for actual player performance, not just name recognition
6. **ML-Ready**: More predictive for game outcomes than video game ratings

---

## Maintenance

### Re-Processing Games

To re-calculate impact for already processed games, just re-run the Lambda with the same filters. The UPDATE query will overwrite existing values.

### Adding New Columns

If you need additional impact metrics (e.g., `home_wr_corps_strength`), add them to `alter_game_mapping_table.sql` and update `DatabaseUtils.update_game_impact()` to include the new columns.

### API Rate Limits

Sportradar API has rate limits (1 call/second for trial tier). The Lambda includes `time.sleep(1.1)` between games to stay within limits.

---

## Troubleshooting

### "No games found to process"

- Check that `game_id_mapping` has rows with non-null `sportradar_id`
- Verify season/week filters match actual data

### "Authentication error" (database)

- Verify environment variables are set correctly
- Check for leading/trailing whitespace in DB credentials

### "Sportradar API error"

- Verify `SPORTRADAR_API_KEY` is valid
- Check API rate limits (trial tier is 1 call/sec)

### "PFF grade not found for player X"

- Player may not have PFF data for that season
- Check player name spelling in PFF tables
- Verify team abbreviation matches between Sportradar and PFF data

---

## Support

For issues or questions, check:
- Lambda CloudWatch logs for detailed error messages
- Sportradar API documentation
- PFF data ETL Lambda logs (QB, RB, WR, OL, DEF)
