# RBs PFF Lambda

AWS Lambda function for ingesting Running Back (RB) Pro Football Focus (PFF) statistics from S3 into a PostgreSQL database.

## Overview

This ETL pipeline reads RB PFF CSV data from S3, transforms and validates the data, then performs batch upsert operations into a Supabase/PostgreSQL database.

## Architecture

### Components

1. **lambda_function.py** - Main Lambda handler that orchestrates the ETL pipeline
2. **S3FileReader.py** - Reads and parses CSV files from S3 buckets
3. **PFFDataProcessor.py** - Transforms, validates, and batch-processes RB statistics
4. **DatabaseUtils.py** - PostgreSQL connection and query execution utilities

### Data Flow

```
S3 Bucket (CSV files) 
    ↓
S3FileReader (read & parse)
    ↓
PFFDataProcessor (transform & validate)
    ↓
DatabaseUtils (batch upsert)
    ↓
PostgreSQL Database (rb_pff_ratings table)
```

## Lambda Event Format

### Single Season
```json
{
  "bucket": "neal-nitya-rb-bucket",
  "season": 2024,
  "s3_prefix": "RBs/2024/"
}
```

### Multiple Seasons
```json
{
  "bucket": "neal-nitya-rb-bucket",
  "season": [2023, 2024],
  "s3_prefix_template": "RBs/{season}/"
}
```

## Environment Variables

The Lambda function requires the following environment variables:

- `PLAYER_DATA_BUCKET` - Default S3 bucket name (optional if passed in event)
- `SUPABASE_DB_HOST` or `DB_HOST` - Database host
- `SUPABASE_DB_PORT` or `DB_PORT` - Database port (default: 5432)
- `SUPABASE_DB_NAME` or `DB_NAME` - Database name
- `SUPABASE_DB_USER` or `DB_USER` - Database user
- `SUPABASE_DB_PASSWORD` or `DB_PASSWORD` - Database password

## Database Schema

The Lambda upserts data into the `rb_pff_ratings` table with the following key fields:

### Identification
- `player` - Player name
- `player_id` - Unique player identifier
- `position` - Position (RB)
- `team_name` - Normalized team abbreviation
- `season` - Season year
- `franchise_id` - Franchise identifier

### Performance Metrics
- `attempts` - Rush attempts
- `yards` - Total rushing yards
- `touchdowns` - Total touchdowns
- `receptions` - Pass receptions
- `rec_yards` - Receiving yards
- `total_touches` - Combined rush attempts + receptions
- `first_downs` - First downs gained

### Advanced Metrics
- `yards_after_contact` - YAC (Yards After Contact)
- `avoided_tackles` - Tackles avoided
- `elusive_rating` - PFF elusive rating
- `explosive` - Explosive plays (15+ yards)
- `breakaway_yards` - Yards on breakaway runs
- `ypa` - Yards per attempt
- `yprr` - Yards per route run

### PFF Grades
- `grades_offense` - Overall offensive grade
- `grades_run` - Run blocking grade
- `grades_pass` - Pass blocking grade
- `grades_pass_route` - Pass route grade
- `grades_hands_fumble` - Ball security grade

### Penalties & Errors
- `fumbles` - Total fumbles
- `drops` - Dropped passes
- `penalties` - Total penalties
- `declined_penalties` - Declined penalties

## Key Features

### Data Cleaning
- Handles null/empty values
- Type conversion (int, decimal, string)
- Team abbreviation normalization (LA → LAR, HST → HOU, etc.)

### Batch Processing
- Configurable batch size (default: 50 rows)
- Efficient batch upsert operations
- Transaction rollback on errors

### Conflict Resolution
- Uses PostgreSQL `ON CONFLICT` clause
- Unique constraint: `(player, team_name, season)`
- Updates existing records, inserts new ones

### Error Handling
- Validates required fields before insertion
- Logs warnings for invalid rows
- Comprehensive error logging with stack traces

## Deployment

### Package Lambda
```bash
cd RBsPFFLambda
pip install -r requirements.txt -t .
zip -r lambda_package.zip .
```

### Lambda Configuration
- **Runtime**: Python 3.11+
- **Memory**: 512 MB (minimum)
- **Timeout**: 5 minutes
- **IAM Role Permissions**:
  - S3 read access (`s3:GetObject`, `s3:ListBucket`)
  - CloudWatch Logs write access

## Testing Locally

```python
from lambda_function import lambda_handler

event = {
    "bucket": "neal-nitya-rb-bucket",
    "season": 2024,
    "s3_prefix": "RBs/2024/"
}

result = lambda_handler(event, None)
print(result)
```

## Logging

The function logs:
- ETL pipeline progress
- Row counts at each stage
- Batch processing details
- Validation warnings
- Error stack traces

Example output:
```
RB PFF Lambda Handler Started
Event: {"bucket": "neal-nitya-rb-bucket", "season": 2024}
Initializing ETL components
Processing Season 2024
Step 1: Reading CSV files from S3
Found 1 CSV files to process
✓ Parsed 450 rows from CSV
✓ Total rows loaded: 450
Step 2: Processing and storing rows in database
✓ Transformed 448 valid rows
Processing batch 1: 50 rows
✓ Batch executed: 50 rows affected
...
✓ COMPLETE: 448 rows upserted to database
```

## Error Responses

### Success (200)
```json
{
  "statusCode": 200,
  "body": {
    "success": true,
    "message": "Successfully processed 450 RB records across 1 seasons",
    "total_rows": 450,
    "seasons_processed": 1,
    "details": [
      {
        "season": 2024,
        "rows_processed": 450,
        "status": "success"
      }
    ]
  }
}
```

### Failure (500)
```json
{
  "statusCode": 500,
  "body": {
    "success": false,
    "error": "Database connection failed",
    "message": "RB PFF data ingestion failed"
  }
}
```

## Maintenance

### Adding New Fields
1. Update CSV column list in `PFFDataProcessor.transform_row()`
2. Add to `build_upsert_query()` column list
3. Add to `row_to_tuple()` column list
4. Update database schema

### Team Abbreviation Mapping
Add new mappings to `normalize_team_abbreviation()` in `PFFDataProcessor.py`:
```python
team_mapping = {
    'OLD': 'NEW',
    ...
}
```
