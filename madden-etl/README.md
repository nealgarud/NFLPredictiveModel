# Madden ETL Lambda

Processes Madden player rating CSV files from S3 and stores cleaned data in Supabase.

## What It Does

1. Reads CSV files from S3 (`2022.csv`, `2023.csv`, `2024.csv`)
2. Extracts relevant columns:
   - `player_id`: Unique identifier (e.g., `ZACHWILSON_19990803`)
   - `player_name`: Player name (e.g., `Zach Wilson`)
   - `position`: Position abbreviation (e.g., `QB`)
   - `team`: Team abbreviation (e.g., `DEN`)
   - `overall_rating`: Madden overall rating (e.g., `74`)
3. Stores in Supabase `player_ratings` table

## Environment Variables Required

- `PLAYER_DATA_BUCKET`: S3 bucket name (default: `player-data-nfl-predictive-model`)
- `SUPABASE_DB_HOST`: Supabase database host
- `SUPABASE_DB_PASSWORD`: Supabase database password
- `SUPABASE_DB_NAME`: Database name (default: `postgres`)
- `SUPABASE_DB_USER`: Database user (default: `postgres`)
- `SUPABASE_DB_PORT`: Database port (default: `5432`)

## Deployment

```powershell
# Package
cd madden-etl
Compress-Archive -Path lambda_function.py -DestinationPath madden-etl.zip -Force

# Deploy
aws lambda update-function-code --function-name madden-etl --zip-file fileb://madden-etl.zip
```

## Test Event

```json
{
  "seasons": [2022, 2023, 2024]
}
```

## Supabase Table

```sql
CREATE TABLE player_ratings (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(255) NOT NULL,
    player_name VARCHAR(255),
    position VARCHAR(50),
    team VARCHAR(10),
    overall_rating INTEGER,
    season INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(player_id, season)
);

CREATE INDEX idx_player_id ON player_ratings(player_id);
CREATE INDEX idx_season ON player_ratings(season);
CREATE INDEX idx_player_season ON player_ratings(player_id, season);
```

## After Running

The `player_ratings` table will contain cleaned data that can be queried by `playerimpact` Lambda.

