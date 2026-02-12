# QB PFF Lambda - ETL Pipeline

**Purpose**: Extract QB PFF ratings from S3, transform them, and load into Supabase PostgreSQL database.

---

## 📁 File Structure

```
QBsPFFLambda/
├── lambda_function.py       # Main Lambda handler (orchestrator)
├── S3FileReader.py          # Reads CSV files from S3
├── PFFDataProcessor.py      # ⭐ MEAT & POTATOES - data transformation & batching
├── DatabaseUtils.py         # Database connection & query utilities
├── sql_schema.sql           # Database table schema
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

---

## 🏗️ Architecture

### Data Flow:
```
S3 Bucket (pff-ratings-csvs)
    ↓
S3FileReader.py → Reads CSVs
    ↓
PFFDataProcessor.py → Transforms & validates
    ↓
DatabaseUtils.py → Batch writes to DB
    ↓
Supabase (qb_pff_ratings table)
```

---

## 📊 S3 Structure

```
s3://neal-nitya-qb-bucket/
└── QBs/
    ├── passing_summary.csv
    ├── passing_summary (1).csv
    └── *.csv (all QB CSV files in this folder)
```

---

## 🗄️ Database Table

**Table**: `qb_pff_ratings`

**Key Columns**:
- `player_name` - Player's full name
- `team_abbreviation` - 3-letter team code (LAR, KC, etc.)
- `season` - Year (2022, 2023, 2024)
- `grades_offense` - ⭐ Primary PFF grade (60-99)
- `grades_pass` - Passing grade
- `grades_run` - QB rushing grade
- `attempts`, `completions`, `pass_yards`, `pass_touchdowns`, `interceptions`

**Unique Constraint**: `(player_name, team_abbreviation, season)`

---

## 🔧 Classes Explained

### 1. **lambda_function.py** (The Orchestrator)
- Entry point for AWS Lambda
- Parses event parameters
- Initializes all components
- Coordinates the ETL flow
- Returns success/error response

### 2. **S3FileReader.py** (The Reader)
- Connects to S3 using boto3
- Lists files in folder
- Reads CSV files
- Parses CSVs into Python dictionaries

### 3. **PFFDataProcessor.py** (⭐ THE MEAT & POTATOES)
- **Transforms** raw CSV data into database format
- **Cleans** values (handles nulls, converts types)
- **Normalizes** team abbreviations
- **Validates** required fields
- **Batches** data for efficient inserts
- **Builds** SQL UPSERT queries
- **Writes** to database in chunks

### 4. **DatabaseUtils.py** (The Connector)
- Manages PostgreSQL connection
- Executes queries with error handling
- Supports batch operations
- Context manager support
- Transaction management (commit/rollback)

---

## 🚀 Lambda Event Format

### Single Season:
```json
{
  "bucket": "neal-nitya-qb-bucket",
  "season": 2024,
  "s3_prefix": "QBs/"
}
```

### Multiple Seasons (array + template):
```json
{
  "bucket": "neal-nitya-qb-bucket",
  "season": [2022, 2023, 2024],
  "s3_prefix_template": "QBs/QBs-{season}/"
}
```
Use `{season}` placeholder for per-season S3 paths.

### Multiple Seasons (shared prefix):
```json
{
  "bucket": "neal-nitya-qb-bucket",
  "season": [2022, 2023, 2024],
  "s3_prefix": "QBs/"
}
```

### Legacy format (explicit per-season configs):
```json
{
  "bucket": "neal-nitya-qb-bucket",
  "seasons": [
    {"season": 2022, "s3_prefix": "QBs/QBs-2022/"},
    {"season": 2023, "s3_prefix": "QBs/QBs-2023/"},
    {"season": 2024, "s3_prefix": "QBs/QBs-2024/"}
  ]
}
```

---

## 🔐 Environment Variables

Required Lambda environment variables:

```bash
DB_HOST=xxx.supabase.co
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=your-password
```

---

## 📦 Deployment

### 1. Create SQL Table:
```bash
psql -h your-db-host -U postgres -d postgres -f sql_schema.sql
```

### 2. Create Lambda Deployment Package:
```bash
# Install dependencies
pip install -r requirements.txt -t .

# Create ZIP
zip -r qb-pff-lambda.zip *.py

# Upload to AWS Lambda
aws lambda update-function-code \
  --function-name QBsPFFLambda \
  --zip-file fileb://qb-pff-lambda.zip
```

### 3. Set Environment Variables in AWS Lambda Console

### 4. Test Lambda:
```bash
aws lambda invoke \
  --function-name QBsPFFLambda \
  --payload '{"bucket":"pff-ratings-csvs","season":2024,"s3_prefix":"QBs/QBs-2024/QBs_2024/"}' \
  response.json
```

---

## 🧪 Local Testing

```python
# Set environment variables
export DB_HOST=xxx.supabase.co
export DB_USER=postgres
export DB_PASSWORD=your-password
export DB_NAME=postgres

# Run locally
python lambda_function.py
```

---

## 📝 Key Learnings

### Why 4 Classes?
1. **Separation of Concerns**: Each class has one job
2. **Testability**: Easy to unit test each component
3. **Reusability**: Can use S3FileReader for other Lambdas
4. **Maintainability**: Changes to DB logic don't affect S3 logic

### Why Batching?
- **Performance**: Faster than row-by-row inserts
- **Database Load**: Reduces connection overhead
- **Lambda Limits**: Prevents timeout on large datasets

### Why UPSERT?
- **Idempotency**: Can re-run Lambda safely
- **Updates**: Handles updated PFF grades
- **No Duplicates**: Unique constraint prevents dupes

---

## 🎯 Next Steps

1. **Practice**: Copy this structure for RBs, WRs, OL, DEF
2. **Modify**: Adjust column mappings for each position
3. **Test**: Run locally before deploying to AWS
4. **Monitor**: Check CloudWatch logs for errors

---

## 🐛 Common Issues

### Issue: "No module named 'pg8000'"
**Fix**: Install dependencies in Lambda layer or deployment package

### Issue: Connection timeout
**Fix**: Ensure Lambda has VPC access to Supabase (or use public endpoint)

### Issue: "Missing required field"
**Fix**: Check CSV column names match transform_row() expectations

---

**Author**: Built for NFL Predictive Model  
**Date**: February 2026

