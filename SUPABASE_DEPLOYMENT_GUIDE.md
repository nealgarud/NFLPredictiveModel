# 🚀 Supabase + AWS Lambda Deployment Guide
## NFL Predictive Model

---

## 📦 Updated Package Information

**File Name:** `nfl-lambda-deployment-supabase.zip`  
**Size:** 53.1 MB  
**Python Version:** 3.11  
**Database:** Supabase PostgreSQL  
**Created:** October 19, 2025

---

## ✅ What Changed for Supabase

### 1. **DatabaseConnection.py** - Updated for Supabase
- Changed environment variable names to `SUPABASE_*` prefix
- Added `sslmode='require'` (Supabase requires SSL)
- Supports both direct connection (port 5432) and connection pooling (port 6543)

### 2. **TeamRankingsRepository.py** - Added ATS Metrics
- Added 5 new columns for Against The Spread (ATS) performance:
  - `ats_wins` - Number of times team covered the spread
  - `ats_losses` - Number of times team failed to cover
  - `ats_pushes` - Number of times the spread was exact
  - `ats_cover_rate` - Win rate against the spread
  - `avg_spread_margin` - Average margin vs. the spread

### 3. **BettingAnalyzer.py** - Calculate ATS Performance
- Enhanced betting metrics calculation
- Calculates how teams perform against betting spreads
- Tracks cover rate and spread margins
- Handles edge cases (no betting data, pushes, etc.)

---

## 🗄️ Supabase Database Schema

Your Supabase database has 3 tables:

### Table 1: `teams` (Reference Data)
```sql
CREATE TABLE teams (
    team_id VARCHAR(10) PRIMARY KEY,
    team_name VARCHAR(100),
    team_city VARCHAR(100),
    abbreviation VARCHAR(10),
    conference VARCHAR(3),
    division VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
✅ Already populated with all 32 NFL teams

### Table 2: `games` (Game Data)
```sql
CREATE TABLE games (
    game_id VARCHAR(20) PRIMARY KEY,
    season INTEGER NOT NULL,
    game_type VARCHAR(10) NOT NULL,
    week INTEGER NOT NULL,
    gameday DATE,
    weekday VARCHAR(10),
    gametime VARCHAR(10),
    away_team VARCHAR(3) NOT NULL,
    away_score INTEGER,
    home_team VARCHAR(3) NOT NULL,
    home_score INTEGER,
    location VARCHAR(50),
    away_moneyline INTEGER,
    home_moneyline INTEGER,
    spread_line DECIMAL(4,1),
    total_line DECIMAL(4,1),
    div_game BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
✅ Compatible with GameRepository.py

### Table 3: `team_rankings` (Calculated Metrics)
```sql
CREATE TABLE team_rankings (
    team_id VARCHAR(10) NOT NULL,
    season INT NOT NULL,
    
    -- Win/Loss Stats
    games_played INT DEFAULT 0,
    wins INT DEFAULT 0,
    losses INT DEFAULT 0,
    ties INT DEFAULT 0,
    win_rate DECIMAL(5,3),
    
    -- Scoring Stats
    total_points_scored INT DEFAULT 0,
    total_points_allowed INT DEFAULT 0,
    avg_points_scored DECIMAL(6,2),
    avg_points_allowed DECIMAL(6,2),
    point_differential INT DEFAULT 0,
    avg_point_differential DECIMAL(6,2),
    
    -- Rankings
    offensive_rank INT,
    defensive_rank INT,
    overall_rank INT,
    
    -- Home Performance
    home_games INT DEFAULT 0,
    home_wins INT DEFAULT 0,
    home_losses INT DEFAULT 0,
    home_win_rate DECIMAL(5,3),
    home_avg_points_scored DECIMAL(6,2),
    home_avg_points_allowed DECIMAL(6,2),
    
    -- Away Performance
    away_games INT DEFAULT 0,
    away_wins INT DEFAULT 0,
    away_losses INT DEFAULT 0,
    away_win_rate DECIMAL(5,3),
    away_avg_points_scored DECIMAL(6,2),
    away_avg_points_allowed DECIMAL(6,2),
    
    -- Division Performance
    div_games INT DEFAULT 0,
    div_wins INT DEFAULT 0,
    div_losses INT DEFAULT 0,
    div_win_rate DECIMAL(5,3),
    
    -- Betting Metrics
    avg_spread_line DECIMAL(5,2),
    avg_total_line DECIMAL(5,2),
    times_favored INT DEFAULT 0,
    times_underdog INT DEFAULT 0,
    
    -- ATS (Against The Spread) Metrics
    ats_wins INT DEFAULT 0,
    ats_losses INT DEFAULT 0,
    ats_pushes INT DEFAULT 0,
    ats_cover_rate DECIMAL(5,3),
    avg_spread_margin DECIMAL(6,2),
    
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (team_id, season)
);
```
✅ Enhanced with ATS metrics

---

## 🔐 Your Supabase Connection Details

**Project URL:** `db.abc123.supabase.co`  
**Database Name:** `postgres`  
**User:** `postgres`  
**Port:** `5432` (direct) or `6543` (pooler - recommended for Lambda)

> ⚠️ **Security Note:** Your password is `QtL0eNHRxeqva7Je` - Keep this secure!

---

## 🚀 AWS Lambda Deployment Steps

### Step 1: Upload Lambda Package to AWS

#### Option A: AWS Console (Easy)
1. Go to [AWS Lambda Console](https://console.aws.amazon.com/lambda)
2. Click **"Create function"** or select existing function
3. Choose **"Upload from"** → **".zip file"**
4. Upload `nfl-lambda-deployment-supabase.zip`
5. Click **"Save"**

#### Option B: AWS CLI (Advanced)
```bash
# Navigate to the package directory
cd "C:\Users\nealg\Nfl Predictive Model\NFLPredictiveModel"

# Create new Lambda function
aws lambda create-function \
  --function-name NFLPredictiveModel \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR-ACCOUNT-ID:role/NFLPredictiveLambdaRole \
  --handler Lambda_function.lambda_handler \
  --zip-file fileb://nfl-lambda-deployment-supabase.zip \
  --timeout 900 \
  --memory-size 1024

# Or update existing function
aws lambda update-function-code \
  --function-name NFLPredictiveModel \
  --zip-file fileb://nfl-lambda-deployment-supabase.zip
```

### Step 2: Configure Lambda Settings

**Basic Settings:**
- **Runtime:** Python 3.11
- **Handler:** `Lambda_function.lambda_handler`
- **Timeout:** 900 seconds (15 minutes)
- **Memory:** 1024 MB (adjust based on data size)

### Step 3: Set Environment Variables

In Lambda Console → Configuration → Environment variables, add:

```bash
SUPABASE_DB_HOST=db.abc123.supabase.co
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=QtL0eNHRxeqva7Je
SUPABASE_DB_PORT=6543
```

> 💡 **Tip:** Use port `6543` for connection pooling (better for Lambda) or `5432` for direct connection

**Better Security Option - Use AWS Secrets Manager:**

```bash
# Store password in Secrets Manager
aws secretsmanager create-secret \
  --name nfl-supabase-db-password \
  --secret-string "QtL0eNHRxeqva7Je"

# Update Lambda code to retrieve from Secrets Manager
```

### Step 4: Configure IAM Role

Your Lambda needs these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::YOUR-BUCKET-NAME",
        "arn:aws:s3:::YOUR-BUCKET-NAME/*"
      ]
    }
  ]
}
```

### Step 5: Set Up S3 Trigger

1. **Create S3 Bucket** (if not exists):
```bash
aws s3 mb s3://nfl-predictive-data
```

2. **Add Lambda Permission**:
```bash
aws lambda add-permission \
  --function-name NFLPredictiveModel \
  --statement-id s3-trigger \
  --action lambda:InvokeFunction \
  --principal s3.amazonaws.com \
  --source-arn arn:aws:s3:::nfl-predictive-data
```

3. **Configure S3 Event Notification**:
   - In S3 Console → Your bucket → Properties → Event notifications
   - Create event notification
   - Event type: **All object create events**
   - Destination: **Lambda function**
   - Lambda function: **NFLPredictiveModel**
   - Suffix filter: `.txt`

---

## 🧪 Testing Your Deployment

### Test 1: Manual Lambda Invocation

Create `test-event.json`:
```json
{
  "Records": [
    {
      "s3": {
        "bucket": {
          "name": "nfl-predictive-data"
        },
        "object": {
          "key": "test/nfl-games-2024.txt"
        }
      }
    }
  ]
}
```

Test via AWS Console:
1. Go to Lambda → Your function → Test tab
2. Create new test event with the JSON above
3. Click **Test**
4. Check execution results

### Test 2: Upload File to S3

```bash
# Upload a test file
aws s3 cp your-nfl-data.txt s3://nfl-predictive-data/test/

# Monitor CloudWatch logs
aws logs tail /aws/lambda/NFLPredictiveModel --follow
```

### Test 3: Direct Database Connection Test

You can test Supabase connection directly:

```python
import psycopg2

conn = psycopg2.connect(
    host="db.abc123.supabase.co",
    database="postgres",
    user="postgres",
    password="QtL0eNHRxeqva7Je",
    port=5432,
    sslmode='require'
)

cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM games")
print(f"Total games: {cursor.fetchone()[0]}")
cursor.close()
conn.close()
```

---

## 📊 Expected Lambda Behavior

### Input File Format
CSV/Text file with game data:
```csv
game_id,season,game_type,week,gameday,weekday,gametime,away_team,away_score,home_team,home_score,location,away_moneyline,home_moneyline,spread_line,total_line,div_game
2024_01_KC_BAL,2024,REG,1,2024-09-05,Thursday,8:20PM,KC,27,BAL,20,M&T Bank Stadium,110,-130,-3.5,46.5,false
```

### Processing Flow
1. **Extract:** Lambda triggered by S3 upload
2. **Parse:** Text file converted to DataFrame
3. **Store Games:** Upsert into `games` table
4. **Calculate Stats:** Compute team statistics
5. **Calculate ATS:** Calculate betting performance
6. **Calculate Rankings:** Rank teams by performance
7. **Store Rankings:** Upsert into `team_rankings` table

### Success Response
```json
{
  "statusCode": 200,
  "body": {
    "message": "Success",
    "games_processed": 267,
    "seasons_updated": [2024, 2025]
  }
}
```

---

## 🔍 Monitoring & Debugging

### CloudWatch Logs

View logs in real-time:
```bash
aws logs tail /aws/lambda/NFLPredictiveModel --follow
```

Filter for errors:
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/NFLPredictiveModel \
  --filter-pattern "ERROR"
```

### Supabase Dashboard Monitoring

1. Go to [Supabase Dashboard](https://supabase.com/dashboard/project/bodckgmwvhzythotvfgp)
2. Navigate to **Database** → **Tables**
3. Check row counts in `games` and `team_rankings`
4. Use SQL Editor to query results:

```sql
-- Check recent games
SELECT * FROM games 
ORDER BY created_at DESC 
LIMIT 10;

-- Check team rankings for current season
SELECT team_id, wins, losses, win_rate, overall_rank
FROM team_rankings
WHERE season = 2024
ORDER BY overall_rank;

-- Check ATS performance
SELECT team_id, ats_wins, ats_losses, ats_cover_rate
FROM team_rankings
WHERE season = 2024
ORDER BY ats_cover_rate DESC;
```

### Key Metrics to Monitor

**Lambda Metrics:**
- Duration (should be < 900 seconds)
- Memory usage (optimize if consistently high)
- Error count (should be 0)
- Invocations count

**Database Metrics (Supabase):**
- Connection count
- Query performance
- Table sizes

---

## ⚠️ Troubleshooting

### Issue 1: "Unable to connect to database"
**Symptoms:** Lambda times out or connection error  
**Solutions:**
- Verify Supabase credentials are correct
- Check that Lambda has internet access (requires NAT Gateway if in VPC)
- Verify port 5432/6543 is accessible
- Try direct connection (5432) vs pooler (6543)

### Issue 2: "SSL connection required"
**Symptoms:** `FATAL: no pg_hba.conf entry`  
**Solution:** ✅ Already fixed - `sslmode='require'` added to connection

### Issue 3: "Task timed out"
**Symptoms:** Lambda execution exceeds timeout  
**Solutions:**
- Increase timeout to 900 seconds (max)
- Use connection pooling (port 6543)
- Optimize batch size if processing large files

### Issue 4: "Memory limit exceeded"
**Symptoms:** Lambda runs out of memory  
**Solutions:**
- Increase memory allocation to 2048 MB or higher
- Process files in chunks for very large datasets

### Issue 5: "Column does not exist"
**Symptoms:** SQL error about missing column  
**Solution:** Verify all columns exist in Supabase:
```sql
-- Check games table columns
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'games';

-- Check team_rankings columns
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'team_rankings';
```

---

## 🎯 Supabase-Specific Features

### Connection Pooling (Recommended for Lambda)

Use port **6543** for connection pooling:
```bash
SUPABASE_DB_PORT=6543
```

Benefits:
- Faster connection establishment
- Better for serverless (Lambda)
- Handles concurrent connections better

### Direct Connection

Use port **5432** for direct connection:
```bash
SUPABASE_DB_PORT=5432
```

Use when:
- You need transaction isolation
- Long-running connections
- Administrative tasks

### Supabase Studio (GUI)

Access your database via Supabase Studio:
1. Go to [Your Project](https://supabase.com/dashboard/project/bodckgmwvhzythotvfgp)
2. Click **Table Editor** to view data
3. Click **SQL Editor** to run queries
4. Use **Database** → **Roles** to manage permissions

---

## 🔒 Security Best Practices

### ✅ Implemented
- SSL/TLS encryption (`sslmode='require'`)
- Environment variables for credentials
- Unique constraint on (team_id, season)
- Primary keys on all tables

### 🎯 Recommended Improvements

1. **Use AWS Secrets Manager**:
```python
import boto3
import json

def get_secret(secret_name):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# In DatabaseConnection.py
secret = get_secret('nfl-supabase-credentials')
password = secret['password']
```

2. **Create Read-Only User** for queries:
```sql
-- In Supabase SQL Editor
CREATE USER nfl_reader WITH PASSWORD 'secure_password';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO nfl_reader;
```

3. **Enable Row Level Security (RLS)** if exposing via API:
```sql
ALTER TABLE games ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_rankings ENABLE ROW LEVEL SECURITY;
```

---

## 📈 Performance Optimization

### Database Indexes

Your schema already has good indexes:
```sql
CREATE INDEX idx_games_season_week ON games(season, week);
CREATE INDEX idx_team_rankings_season ON team_rankings(season);
CREATE INDEX idx_team_rankings_offensive ON team_rankings(offensive_rank);
CREATE INDEX idx_team_rankings_defensive ON team_rankings(defensive_rank);
```

### Lambda Optimization Tips

1. **Reuse database connections** ✅ Already implemented via Singleton pattern
2. **Use connection pooling** ✅ Configured with port 6543
3. **Batch inserts** (Future enhancement)
4. **Provision concurrency** for high-traffic scenarios

---

## 📝 Quick Reference Commands

### Check Lambda Status
```bash
aws lambda get-function --function-name NFLPredictiveModel
```

### View Recent Logs
```bash
aws logs tail /aws/lambda/NFLPredictiveModel --since 1h
```

### Update Lambda Code
```bash
aws lambda update-function-code \
  --function-name NFLPredictiveModel \
  --zip-file fileb://nfl-lambda-deployment-supabase.zip
```

### Test Database Connection
```bash
psql "postgresql://postgres:QtL0eNHRxeqva7Je@db.abc123.supabase.co:5432/postgres?sslmode=require"
```

### Query Latest Rankings
```sql
SELECT t.team_name, r.wins, r.losses, r.win_rate, r.overall_rank, r.ats_cover_rate
FROM team_rankings r
JOIN teams t ON r.team_id = t.team_id
WHERE r.season = 2024
ORDER BY r.overall_rank;
```

---

## 🆘 Support Resources

- **Supabase Docs:** https://supabase.com/docs
- **AWS Lambda Docs:** https://docs.aws.amazon.com/lambda/
- **psycopg2 Docs:** https://www.psycopg.org/docs/
- **Your Supabase Project:** https://supabase.com/dashboard/project/bodckgmwvhzythotvfgp

---

## ✅ Deployment Checklist

- [ ] Lambda function created with Python 3.11
- [ ] `nfl-lambda-deployment-supabase.zip` uploaded
- [ ] Handler set to `Lambda_function.lambda_handler`
- [ ] Timeout set to 900 seconds
- [ ] Memory set to 1024 MB (or higher)
- [ ] Environment variables configured (SUPABASE_*)
- [ ] IAM role has S3 and CloudWatch permissions
- [ ] S3 bucket created
- [ ] S3 trigger configured for `.txt` files
- [ ] Supabase tables created (`teams`, `games`, `team_rankings`)
- [ ] Database connection tested
- [ ] Test file uploaded to S3
- [ ] CloudWatch logs reviewed
- [ ] Supabase data verified

---

**Package Location:** `C:\Users\nealg\Nfl Predictive Model\NFLPredictiveModel\nfl-lambda-deployment-supabase.zip`

**Ready to Deploy:** ✅ YES  
**Database:** ✅ Supabase PostgreSQL  
**ATS Metrics:** ✅ Included  
**Last Updated:** October 19, 2025

