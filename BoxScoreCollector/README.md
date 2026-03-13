# BoxScoreCollector Lambda

Collects per-player per-game box score statistics from Sportradar and computes
a "performance surprise" metric by comparing actual game performance against
the pre-game PFF-based expected impact.

## What It Does

For each game in `game_id_mapping`:
1. Calls `GET /games/{sportradar_id}/statistics.json` — player stats by category
2. Calls `GET /games/{sportradar_id}/summary.json` — quarter-by-quarter scoring
3. Parses and upserts one row per player into `player_game_stats`
4. Calculates team-level actual impact (0–100 scale, 50 = league avg)
5. Compares to pre-game expected impact (from `game_id_mapping.home_avg_impact`)
6. Stores `performance_surprise` and `box_score_collected_at` on `game_id_mapping`

## Prerequisites

Run these SQL files in Supabase SQL Editor **before** invoking this Lambda:

```sql
-- 1. Create the player_game_stats table
BoxScoreCollector/create_player_game_stats.sql

-- 2. Add game script + surprise columns to game_id_mapping
BoxScoreCollector/alter_game_id_mapping.sql
```

## Setup

### Environment Variables (same as PFFGameProcessor)

| Variable | Description |
|---|---|
| `SPORTRADAR_API_KEY` | Sportradar API key |
| `SUPABASE_DB_HOST` | Supabase DB host |
| `SUPABASE_DB_PORT` | DB port (default 5432) |
| `SUPABASE_DB_NAME` | Database name |
| `SUPABASE_DB_USER` | DB user |
| `SUPABASE_DB_PASSWORD` | DB password |

### Deployment

```powershell
$env:PATH += ";C:\Program Files\Amazon\AWSCLIV2"
$dir = "c:\Users\nealg\Nfl Predictive Model\NFLPredictiveModel\BoxScoreCollector"

# Install dependencies
pip install -r "$dir\requirements.txt" --target "$dir\package"

# Copy SportradarClient from PFFGameProcessor
Copy-Item "..\PFFGameProcessor\SportradarClient.py" "$dir\"

# Package
Compress-Archive -Path "$dir\package\*", "$dir\lambda_function.py", "$dir\BoxScoreParser.py", "$dir\GameImpactCalculator.py", "$dir\DatabaseUtils.py", "$dir\SportradarClient.py" -DestinationPath "$dir\deployment.zip" -Force

# Create Lambda (first time)
aws lambda create-function `
    --function-name BoxScoreCollector `
    --runtime python3.11 `
    --handler lambda_function.lambda_handler `
    --zip-file "fileb://$dir\deployment.zip" `
    --timeout 900 `
    --memory-size 256 `
    --role arn:aws:iam::838319850663:role/lambda-execution-role

# Or update existing
aws lambda update-function-code `
    --function-name BoxScoreCollector `
    --zip-file "fileb://$dir\deployment.zip"
```

## Test Triggers

### Single game (Super Bowl LIX)
```json
{
    "game_id": "2024_22_KC_PHI",
    "sportradar_id": "<sportradar-uuid>",
    "season": 2024,
    "week": 22,
    "home_team": "PHI",
    "away_team": "KC"
}
```

### One week
```json
{"season": 2024, "week": 10}
```

### Full season batch (~272 games, ~10 min at 2 calls/game + rate limit)
```json
{"season": 2024}
```

### All seasons
```json
{"seasons": [2022, 2023, 2024]}
```

### Force re-collect (re-runs already-processed games)
```json
{"force": true, "season": 2024}
```

## Rate Limiting

Sportradar trial tier: 1 req/sec. This Lambda makes **2 API calls per game**
(statistics + summary), so it sleeps 2.1 seconds between games.

- 1 week  (~16 games)  ≈ 1 minute
- 1 season (~272 games) ≈ 10 minutes
- 3 seasons (~816 games) ≈ 30 minutes (set Lambda timeout to 900s)

## Output

### `player_game_stats` table
One row per player per game with all rushing/passing/receiving/defense/ST stats
plus the computed `actual_impact_score` (0–100).

### `game_id_mapping` new columns
| Column | Description |
|---|---|
| `home_q1_points` – `home_q4_points` | Home team points by quarter |
| `away_q1_points` – `away_q4_points` | Away team points by quarter |
| `home_led_at_half` | Boolean |
| `halftime_margin` | home − away at halftime |
| `home_actual_game_impact` | Weighted team actual impact score |
| `away_actual_game_impact` | |
| `home_performance_surprise` | actual − expected impact |
| `away_performance_surprise` | |
| `performance_surprise_diff` | home_surprise − away_surprise |
| `box_score_collected_at` | Timestamp |

## Training Data Integration

After running BoxScoreCollector, regenerate training data:
```bash
python ML-Training/generate_training_data.py
```

New features added automatically:
- `home_rolling_3g_surprise`, `away_rolling_3g_surprise`, `rolling_3g_surprise_diff`
- `home_rolling_5g_surprise`, `away_rolling_5g_surprise`, `rolling_5g_surprise_diff`
- `q1_margin` through `q4_margin`
- `halftime_margin`, `home_led_at_half`

## Architecture

```
BoxScoreCollector/
├── lambda_function.py      # Lambda handler + orchestration
├── BoxScoreParser.py       # Sportradar JSON → player stat dicts
├── GameImpactCalculator.py # Position-specific impact formulas
├── DatabaseUtils.py        # DB reads/writes
├── SportradarClient.py     # Copied from PFFGameProcessor (shared)
├── create_player_game_stats.sql
├── alter_game_id_mapping.sql
└── requirements.txt
```
