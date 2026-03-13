# TeamDataLambda

Ingests PFF team grade CSVs from S3 into three Supabase tables:
`pff_team_offense`, `pff_team_defense`, `pff_team_special_teams`.

---

## S3 Layout

Bucket: `team_data_nfl`

```
team_data_nfl/
    2022/team_grades.csv
    2023/team_grades.csv
    2024/team_grades.csv
```

## Source CSV Columns

```
team, season, record, pf, pa, overall, offense, passing,
pass_block, receiving, run, run_block, defense, run_defense,
tackling, pass_rush, coverage, special_teams
```

## Table → Column Mapping

| CSV column     | Table                   | DB column            |
|----------------|-------------------------|----------------------|
| team           | all                     | team                 |
| season (event) | all                     | season               |
| record         | pff_team_offense        | wins, losses, ties   |
| pf             | pff_team_offense        | points_for           |
| overall        | pff_team_offense        | overall_grade        |
| offense        | pff_team_offense        | offense_grade        |
| passing        | pff_team_offense        | passing_grade        |
| pass_block     | pff_team_offense        | pass_block_grade     |
| receiving      | pff_team_offense        | receiving_grade      |
| run            | pff_team_offense        | run_grade            |
| run_block      | pff_team_offense        | run_block_grade      |
| pa             | pff_team_defense        | points_against       |
| defense        | pff_team_defense        | defense_grade        |
| run_defense    | pff_team_defense        | run_defense_grade    |
| tackling       | pff_team_defense        | tackling_grade       |
| pass_rush      | pff_team_defense        | pass_rush_grade      |
| coverage       | pff_team_defense        | coverage_grade       |
| special_teams  | pff_team_special_teams  | special_teams_grade  |

## Setup

### 1. Create Supabase Tables
Run `create_tables.sql` in the Supabase SQL Editor once.

### 2. Deploy Lambda

```powershell
# Zip and deploy (standard zip Lambda — no Docker needed)
cd TeamDataLambda
Compress-Archive -Path *.py, requirements.txt -DestinationPath deployment.zip -Force

aws lambda create-function `
    --function-name TeamDataLambda `
    --runtime python3.11 `
    --handler lambda_function.lambda_handler `
    --zip-file fileb://deployment.zip `
    --role arn:aws:iam::838319850663:role/lambda-execution-role `
    --timeout 60 `
    --environment "Variables={SUPABASE_DB_HOST=...,SUPABASE_DB_NAME=postgres,SUPABASE_DB_USER=...,SUPABASE_DB_PASSWORD=...,SUPABASE_DB_PORT=6543}"
```

### 3. Upload CSVs and Process

```powershell
# Place your CSVs in TeamDataLambda\data\
#   2022_team_grades.csv
#   2023_team_grades.csv
#   2024_team_grades.csv

.\upload_and_process.ps1
```

### Adding a new season each year

```powershell
.\upload_and_process.ps1 -Seasons 2025
```

## Lambda Invoke Formats

```json
// Single season
{"bucket": "team_data_nfl", "season": 2024}

// Multiple seasons (initial load)
{"bucket": "team_data_nfl", "seasons": [2022, 2023, 2024]}
```

## Files

| File                  | Purpose                                    |
|-----------------------|--------------------------------------------|
| `lambda_function.py`  | Handler — parses event, orchestrates flow  |
| `TeamDataProcessor.py`| Transforms CSV rows, upserts to 3 tables   |
| `S3FileReader.py`     | Reads CSVs from S3 (shared utility)        |
| `DatabaseUtils.py`    | Supabase connection (shared utility)       |
| `create_tables.sql`   | DDL — run once in Supabase SQL Editor      |
| `upload_and_process.ps1` | Upload CSVs to S3 + invoke Lambda       |
