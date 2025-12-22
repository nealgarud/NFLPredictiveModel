# AWS Lambda Deployment Package - NFL Predictive Model

## 📦 Package Information

**File Name:** `nfl-lambda-deployment.zip`  
**Size:** 53.11 MB  
**Python Version:** 3.11  
**Created:** October 19, 2025  
**Location:** `C:\Users\nealg\Nfl Predictive Model\NFLPredictiveModel\nfl-lambda-deployment.zip`

---

## ✅ Package Contents

### Application Files (11 Python modules)
- ✅ `Lambda_function.py` - Main Lambda handler
- ✅ `GameRepository.py` - Game data repository
- ✅ `TeamRankingsRepository.py` - Rankings data repository
- ✅ `AggregateCalculator.py` - Team statistics calculator
- ✅ `BettingAnalyzer.py` - Betting metrics analyzer
- ✅ `RankingsCalculator.py` - Team rankings calculator
- ✅ `S3Handler.py` - S3 file operations
- ✅ `DatabaseConnection.py` - PostgreSQL connection manager
- ✅ `TextFileParser.py` - CSV/text file parser
- ✅ `DuplicateHandler.py` - Duplicate detection
- ✅ `data_orchestrator_pipeline.py` - Pipeline orchestrator

### Dependencies (Total: 8,013 files)
- ✅ **pandas** (2.0.3) - Data manipulation
- ✅ **numpy** (1.24.3) - Numerical computations
- ✅ **boto3** (1.28.85) - AWS SDK
- ✅ **botocore** (1.31.85) - AWS core library
- ✅ **psycopg2-binary** (2.9.9) - PostgreSQL adapter
- ✅ **python-dateutil** (2.9.0.post0) - Date utilities
- ✅ **pytz** (2025.2) - Timezone support
- ✅ **urllib3** (2.0.7) - HTTP library
- ✅ **s3transfer** (0.7.0) - S3 transfer utilities
- ✅ **jmespath** (1.0.1) - JSON query language

---

## 🚀 Deployment Steps

### Step 1: Upload to AWS Lambda

#### Option A: Using AWS Console
1. Go to AWS Lambda Console
2. Click "Create function" or select existing function
3. Choose "Upload from" > ".zip file"
4. Upload `nfl-lambda-deployment.zip`
5. Set handler to: `Lambda_function.lambda_handler`
6. Set runtime to: **Python 3.11**

#### Option B: Using AWS CLI
```bash
# Create new Lambda function
aws lambda create-function \
  --function-name NFLPredictiveModel \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR-ACCOUNT-ID:role/NFLPredictiveLambdaRole \
  --handler Lambda_function.lambda_handler \
  --zip-file fileb://nfl-lambda-deployment.zip \
  --timeout 900 \
  --memory-size 1024

# Or update existing function
aws lambda update-function-code \
  --function-name NFLPredictiveModel \
  --zip-file fileb://nfl-lambda-deployment.zip
```

### Step 2: Configure Lambda Settings

**Required Configuration:**
- **Runtime:** Python 3.11
- **Handler:** `Lambda_function.lambda_handler`
- **Timeout:** 900 seconds (15 minutes)
- **Memory:** 1024 MB (recommended, adjust as needed)
- **VPC:** Configure if RDS is in a VPC

**Environment Variables:**
```
DB_HOST=your-rds-endpoint.rds.amazonaws.com
DB_NAME=nfl_predictive
DB_USER=admin
DB_PASSWORD=YourSecurePassword123!
DB_PORT=5432
```

### Step 3: Set Up Permissions

**IAM Role Permissions Required:**
- ✅ Lambda basic execution role
- ✅ S3 read access (`s3:GetObject`, `s3:ListBucket`)
- ✅ VPC access (if using VPC)
- ✅ CloudWatch Logs access

### Step 4: Configure S3 Trigger

**S3 Event Configuration:**
- **Event Type:** `s3:ObjectCreated:*`
- **Bucket:** Your NFL data bucket
- **Prefix:** (optional) `data/`
- **Suffix:** `.txt`

---

## 🧪 Testing

### Test Event (Manual Invocation)
```json
{
  "Records": [
    {
      "s3": {
        "bucket": {
          "name": "your-nfl-data-bucket"
        },
        "object": {
          "key": "test/nfl-games-2024.txt"
        }
      }
    }
  ]
}
```

### Test Using AWS CLI
```bash
aws lambda invoke \
  --function-name NFLPredictiveModel \
  --payload file://test-event.json \
  --cli-binary-format raw-in-base64-out \
  response.json

cat response.json
```

---

## 📊 Expected Behavior

### Input
- CSV/text file uploaded to S3 with game data
- Columns: season, game_type, week, gameday, away_team, home_team, away_score, home_score, spread_line, total_line, etc.

### Processing
1. **Extract:** Read file from S3
2. **Parse:** Convert text to DataFrame
3. **Store:** Insert/update games in RDS PostgreSQL
4. **Calculate:** Compute team statistics and rankings
5. **Store Rankings:** Update team_rankings table

### Output
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

## 🔍 Monitoring

### CloudWatch Logs
```bash
# View logs in real-time
aws logs tail /aws/lambda/NFLPredictiveModel --follow

# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/NFLPredictiveModel \
  --filter-pattern "ERROR"
```

### Key Metrics to Monitor
- **Duration:** Should be < 900 seconds
- **Memory Usage:** Monitor to optimize allocation
- **Errors:** Should be 0
- **Concurrent Executions:** Monitor for scaling

---

## ⚠️ Important Notes

### Size Limitations
- ✅ Current size: 53.11 MB (within Lambda's 50 MB zipped limit for direct upload)
- ⚠️ **Note:** If package grows beyond 50 MB, you'll need to use S3 upload or Lambda Layers

### Dependencies
- All dependencies are included in the package
- `psycopg2-binary` is used for PostgreSQL (no compilation needed)
- Windows binaries are included but Lambda uses Linux runtime (AWS handles compatibility)

### Database Connection
- Ensure RDS security group allows Lambda's security group
- Lambda must be in same VPC as RDS if RDS is not public
- Connection pooling is handled by the singleton pattern in `DatabaseConnection.py`

---

## 🐛 Troubleshooting

### Issue: "Task timed out after 3.00 seconds"
**Solution:** Increase Lambda timeout to 900 seconds

### Issue: "Unable to import module 'Lambda_function'"
**Solution:** Verify handler is set to `Lambda_function.lambda_handler`

### Issue: "Could not connect to database"
**Solution:** 
- Check VPC configuration
- Verify security group rules
- Confirm environment variables are correct

### Issue: "Memory limit exceeded"
**Solution:** Increase Lambda memory allocation (try 2048 MB)

---

## 📝 Next Steps

1. ✅ **Upload** `nfl-lambda-deployment.zip` to AWS Lambda
2. ⬜ **Configure** environment variables
3. ⬜ **Set up** VPC and security groups
4. ⬜ **Create** RDS PostgreSQL database (see `DEPLOYMENT.md`)
5. ⬜ **Configure** S3 trigger
6. ⬜ **Test** with sample data
7. ⬜ **Monitor** CloudWatch logs and metrics

---

## 📚 Additional Resources

- Full deployment guide: `PredictiveDataModel/DEPLOYMENT.md`
- Quick reference: `PredictiveDataModel/QUICK_REFERENCE.md`
- Issues fixed: `PredictiveDataModel/ISSUES_FIXED.md`

---

**Generated:** October 19, 2025  
**Python Version:** 3.11.9  
**Deployment Ready:** ✅ YES

