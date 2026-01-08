# Quick Reference Guide - NFL Predictive Model

## 🔥 Most Important Commands

### Deployment Package Creation
```bash
cd PredictiveDataModel
mkdir lambda_package
pip install -r requirements.txt -t lambda_package/
cp *.py lambda_package/
cd lambda_package && zip -r ../deployment.zip . && cd ..
```

### Upload to Lambda
```bash
aws lambda update-function-code \
  --function-name NFLPredictiveModel \
  --zip-file fileb://deployment.zip
```

### View Logs
```bash
aws logs tail /aws/lambda/NFLPredictiveModel --follow
```

---

## 📊 Useful SQL Queries

### Check Current Data
```sql
-- Count games by season
SELECT season, COUNT(*) as game_count
FROM games
GROUP BY season
ORDER BY season;

-- View top 10 teams by overall rank (current season)
SELECT team_id, overall_rank, wins, losses, win_rate, 
       offensive_rank, defensive_rank
FROM team_rankings
WHERE season = 2024
ORDER BY overall_rank
LIMIT 10;
```

### Data Validation
```sql
-- Check for duplicate games
SELECT game_id, COUNT(*)
FROM games
GROUP BY game_id
HAVING COUNT(*) > 1;

-- Verify ranking calculations
SELECT team_id, season, wins, losses, ties, games_played,
       wins + losses + ties as calculated_total
FROM team_rankings
WHERE wins + losses + ties != games_played;
```

### Performance Queries
```sql
-- Best offensive teams
SELECT team_id, season, avg_points_scored, offensive_rank
FROM team_rankings
WHERE season = 2024
ORDER BY offensive_rank
LIMIT 10;

-- Best defensive teams
SELECT team_id, season, avg_points_allowed, defensive_rank
FROM team_rankings
WHERE season = 2024
ORDER BY defensive_rank
LIMIT 10;

-- Home vs Away performance
SELECT team_id, season,
       home_win_rate,
       away_win_rate,
       home_win_rate - away_win_rate as home_advantage
FROM team_rankings
WHERE season = 2024
ORDER BY home_advantage DESC;
```

### Betting Analysis
```sql
-- Teams most often favored
SELECT team_id, season, times_favored, times_underdog,
       avg_spread_line
FROM team_rankings
WHERE season = 2024
ORDER BY times_favored DESC;

-- Compare betting lines to performance
SELECT team_id, avg_spread_line, avg_point_differential,
       avg_spread_line - avg_point_differential as line_vs_actual
FROM team_rankings
WHERE season = 2024
ORDER BY line_vs_actual DESC;
```

---

## 🔧 Environment Setup

### Required Environment Variables
```bash
DB_HOST=your-rds-endpoint.rds.amazonaws.com
DB_NAME=nfl_predictive
DB_USER=admin
DB_PASSWORD=your-password
DB_PORT=5432
```

### Set in Lambda
```bash
aws lambda update-function-configuration \
  --function-name NFLPredictiveModel \
  --environment Variables="{
    DB_HOST=your-endpoint.rds.amazonaws.com,
    DB_NAME=nfl_predictive,
    DB_USER=admin,
    DB_PASSWORD=your-password,
    DB_PORT=5432
  }"
```

---

## 🚨 Troubleshooting Quick Fixes

### Lambda Timeout
```bash
aws lambda update-function-configuration \
  --function-name NFLPredictiveModel \
  --timeout 900
```

### Out of Memory
```bash
aws lambda update-function-configuration \
  --function-name NFLPredictiveModel \
  --memory-size 2048
```

### View Recent Errors
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/NFLPredictiveModel \
  --filter-pattern "ERROR" \
  --start-time $(date -u -d '1 hour ago' +%s)000
```

---

## 📁 Project Files Cheat Sheet

### Core Lambda Files
- `Lambda_function.py` - Main entry point (lambda_handler)
- `data_orchestrator_pipeline.py` - Full pipeline orchestrator

### Data Processing
- `TextFileParser.py` - Parses input .txt files
- `AggregateCalculator.py` - Calculates team stats
- `BettingAnalyzer.py` - Analyzes betting data
- `RankingsCalculator.py` - Generates rankings

### Infrastructure
- `S3Handler.py` - S3 read/write operations
- `DatabaseConnection.py` - PostgreSQL connection manager
- `GameRepository.py` - Games table CRUD
- `TeamRankingsRepository.py` - Rankings table CRUD
- `DuplicateHandler.py` - Upsert logic

### Configuration
- `requirements.txt` - Python dependencies
- `DEPLOYMENT.md` - Full deployment guide
- `ISSUES_FIXED.md` - All fixes documented

---

## 🎯 Common Tasks

### Add New Metric
1. Modify `AggregateCalculator.py` or `BettingAnalyzer.py`
2. Update `team_rankings` table schema
3. Update `TeamRankingsRepository.py` columns list
4. Redeploy Lambda

### Change Logging Level
In each .py file:
```python
logger.setLevel(logging.DEBUG)  # or INFO, WARNING, ERROR
```

### Test Locally (without Lambda)
```python
# Create test event
event = {
    'Records': [{
        's3': {
            'bucket': {'name': 'your-bucket'},
            'object': {'key': 'path/to/file.txt'}
        }
    }]
}

# Import and run
from Lambda_function import lambda_handler
result = lambda_handler(event, None)
print(result)
```

---

## 📊 Monitoring Queries

### Lambda Performance
```bash
# Average duration last 24 hours
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=NFLPredictiveModel \
  --start-time $(date -u -d '24 hours ago' --iso-8601) \
  --end-time $(date -u --iso-8601) \
  --period 3600 \
  --statistics Average

# Error count
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=NFLPredictiveModel \
  --start-time $(date -u -d '24 hours ago' --iso-8601) \
  --end-time $(date -u --iso-8601) \
  --period 3600 \
  --statistics Sum
```

---

## 🔐 Security Quick Checks

- [ ] RDS is not publicly accessible
- [ ] Lambda is in private subnet
- [ ] Security group only allows Lambda → RDS on port 5432
- [ ] Environment variables don't contain sensitive data in plain text
- [ ] IAM role follows least privilege
- [ ] CloudWatch Logs retention set (not indefinite)
- [ ] S3 bucket has encryption enabled
- [ ] Database password is complex

---

**Quick Help**: For detailed info, see [DEPLOYMENT.md](DEPLOYMENT.md)


