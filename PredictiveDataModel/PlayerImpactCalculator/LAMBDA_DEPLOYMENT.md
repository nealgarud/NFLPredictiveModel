# Lambda Deployment Guide - PlayerImpactCalculator

Complete guide to deploy the PlayerImpactCalculator as an AWS Lambda function.

---

## ✅ Current Setup Verification

### S3 Configuration
Your data is already configured correctly:

**Bucket:** `sportsdatacollection`

**Data Sources:**
```
✅ s3://sportsdatacollection/raw-data/2024.csv
✅ s3://sportsdatacollection/raw-data/2023.csv  
✅ s3://sportsdatacollection/raw-data/2022.csv
✅ s3://sportsdatacollection/madden-ratings/*.csv (all Madden CSVs)
```

**S3DataLoader** automatically reads from these paths ✓

---

## 📦 Creating Lambda Deployment Package

### Option 1: Automated Script (Recommended)

Create `create_lambda_package.sh`:

```bash
#!/bin/bash

echo "Creating PlayerImpactCalculator Lambda deployment package..."

# Create clean directory
rm -rf lambda_package
mkdir lambda_package

# Copy PlayerImpactCalculator modules
echo "Copying modules..."
cp PlayerImpactCalculator/*.py lambda_package/
cp -r ../PredictionAPILambda/PlayerImpactFeature.py lambda_package/

# Install dependencies to package
echo "Installing dependencies..."
pip install --target lambda_package \
    requests \
    boto3 \
    pandas \
    numpy \
    pg8000

# Create ZIP file
echo "Creating ZIP file..."
cd lambda_package
zip -r ../playerimpact-lambda.zip . -x "*.pyc" -x "__pycache__/*"
cd ..

echo "✓ Lambda package created: playerimpact-lambda.zip"
echo "Size: $(du -h playerimpact-lambda.zip | cut -f1)"
```

**Run:**
```bash
cd PredictiveDataModel
chmod +x create_lambda_package.sh
./create_lambda_package.sh
```

### Option 2: Manual Steps (Windows)

**PowerShell script** (`create_lambda_package.ps1`):

```powershell
Write-Host "Creating PlayerImpactCalculator Lambda package..."

# Create clean directory
if (Test-Path lambda_package) { Remove-Item -Recurse lambda_package }
New-Item -ItemType Directory lambda_package

# Copy modules
Write-Host "Copying modules..."
Copy-Item PlayerImpactCalculator\*.py lambda_package\
Copy-Item PredictionAPILambda\PlayerImpactFeature.py lambda_package\

# Install dependencies
Write-Host "Installing dependencies..."
pip install --target lambda_package `
    requests `
    boto3 `
    pandas `
    numpy `
    pg8000

# Create ZIP
Write-Host "Creating ZIP..."
Compress-Archive -Path lambda_package\* -DestinationPath playerimpact-lambda.zip -Force

Write-Host "✓ Package created: playerimpact-lambda.zip"
```

**Run:**
```powershell
cd PredictiveDataModel
.\create_lambda_package.ps1
```

---

## 🚀 Deploying to AWS Lambda

### Step 1: Create Lambda Function

**AWS Console:**
1. Go to AWS Lambda console
2. Click "Create function"
3. Choose "Author from scratch"
4. Function name: `PlayerImpactProcessor`
5. Runtime: **Python 3.11** (or 3.10)
6. Architecture: **x86_64**
7. Create function

### Step 2: Upload Deployment Package

**Option A: Direct Upload (< 50MB)**
1. In Lambda function page
2. Code tab → Upload from → .zip file
3. Select `playerimpact-lambda.zip`
4. Click Save

**Option B: S3 Upload (> 50MB)**
```bash
# Upload to S3 first
aws s3 cp playerimpact-lambda.zip s3://sportsdatacollection/lambda-packages/

# Update Lambda from S3
aws lambda update-function-code \
    --function-name PlayerImpactProcessor \
    --s3-bucket sportsdatacollection \
    --s3-key lambda-packages/playerimpact-lambda.zip
```

### Step 3: Configure Lambda

**Environment Variables:**
```
SPORTRADAR_API_KEY=bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm
SUPABASE_DB_HOST=db.xxx.supabase.co
SUPABASE_DB_PASSWORD=your_password
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PORT=5432
```

**Basic Settings:**
- **Memory:** 1024 MB (minimum for pandas/numpy)
- **Timeout:** 5 minutes (300 seconds)
- **Handler:** `PlayerImpactFeature.lambda_handler` (if using Lambda handler)

**IAM Role Permissions:**
Add S3 read access:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::sportsdatacollection",
        "arn:aws:s3:::sportsdatacollection/*"
      ]
    }
  ]
}
```

---

## 🎯 Lambda Handler Options

### Option 1: Standalone Player Impact Lambda

Create `lambda_handler.py` in the package:

```python
"""
Lambda handler for PlayerImpactCalculator
"""
import json
import logging
from PlayerImpactFeature import PlayerImpactFeature

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize feature (loads once per Lambda container)
feature = None

def lambda_handler(event, context):
    """
    Calculate player impact differential between two teams
    
    Event structure:
    {
        "team_a": "KC",
        "team_b": "GB",
        "season": 2025
    }
    """
    global feature
    
    try:
        # Initialize on cold start
        if feature is None:
            logger.info("Initializing PlayerImpactFeature...")
            feature = PlayerImpactFeature(bucket_name='sportsdatacollection')
            feature.calculate_player_weights(season=2025)
            logger.info("✓ Feature initialized and weights calculated")
        
        # Parse event
        team_a = event.get('team_a')
        team_b = event.get('team_b')
        season = event.get('season', 2025)
        
        if not team_a or not team_b:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'team_a and team_b required'})
            }
        
        # Calculate impact differential
        logger.info(f"Calculating impact: {team_a} vs {team_b}")
        result = feature.calculate_impact_differential(team_a, team_b, season)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'data': result
            })
        }
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }
```

### Option 2: Integration with Existing Prediction Lambda

Update `SpreadPredictionCalculator.py` to include player impact:

```python
# Add at top of SpreadPredictionCalculator
from PlayerImpactFeature import PlayerImpactFeature

class SpreadPredictionCalculator:
    # Update weights to include player impact
    SITUATIONAL_ATS_WEIGHT = 0.35  # 35% (reduced from 40%)
    OVERALL_ATS_WEIGHT = 0.25      # 25% (reduced from 30%)
    HOME_AWAY_WEIGHT = 0.25        # 25% (reduced from 30%)
    PLAYER_IMPACT_WEIGHT = 0.15    # 15% (NEW!)
    
    def __init__(self):
        self.db = DatabaseConnection()
        self.player_impact = PlayerImpactFeature()
        self.player_impact.calculate_player_weights(2025)
    
    def predict_spread_coverage(self, team_a, team_b, spread, team_a_home, seasons):
        # ... existing calculations ...
        
        # NEW: Add player impact
        player_impact_score = self.player_impact.get_feature_for_prediction(
            team_a, team_b, season=2025
        )
        
        # Incorporate into final score
        final_score = (
            situational_ats * self.SITUATIONAL_ATS_WEIGHT +
            overall_ats * self.OVERALL_ATS_WEIGHT +
            home_away * self.HOME_AWAY_WEIGHT +
            player_impact_score * self.PLAYER_IMPACT_WEIGHT  # NEW!
        )
        
        # ... rest of logic ...
```

---

## 🧪 Testing the Lambda

### Test Event

Create test event in Lambda console:

```json
{
  "team_a": "KC",
  "team_b": "GB",
  "season": 2025
}
```

### Expected Response

```json
{
  "statusCode": 200,
  "body": {
    "success": true,
    "data": {
      "team_a": "KC",
      "team_b": "GB",
      "team_a_total_impact": 18.45,
      "team_b_total_impact": 16.23,
      "raw_differential": 2.22,
      "normalized_differential": 0.111,
      "advantage": "team_a"
    }
  }
}
```

### AWS CLI Test

```bash
aws lambda invoke \
    --function-name PlayerImpactProcessor \
    --payload '{"team_a":"KC","team_b":"GB","season":2025}' \
    response.json

cat response.json
```

---

## 📊 Data Flow Summary

```
S3 Bucket (sportsdatacollection)
├── raw-data/
│   ├── 2024.csv  ──────────┐
│   ├── 2023.csv  ──────────┤
│   └── 2022.csv  ──────────┤──> Historical game data
└── madden-ratings/         │
    └── *.csv  ─────────────┘──> Player ratings
                                   │
                                   ↓
                          Lambda Function
                          (PlayerImpactCalculator)
                                   │
                                   ↓
                          S3DataLoader loads CSVs
                                   │
                                   ↓
                          PlayerWeightAssigner
                          calculates weights
                                   │
                                   ↓
                          PlayerImpactFeature
                          computes impact scores
                                   │
                                   ↓
                          Returns impact differential
                                   │
                                   ↓
                          Supabase (optional storage)
```

---

## ✅ Pre-Deployment Checklist

- [ ] All CSV files uploaded to `s3://sportsdatacollection/`
- [ ] Madden ratings have correct columns: `player_id`, `player_name`, `overallrating`, `position`, `team`
- [ ] AWS credentials configured (`aws configure`)
- [ ] Lambda IAM role has S3 read permissions
- [ ] Environment variables set (if using Supabase)
- [ ] Deployment package created (`playerimpact-lambda.zip`)
- [ ] Memory set to at least 1024 MB
- [ ] Timeout set to 5 minutes

---

## 🚀 Quick Deploy Commands

```bash
# 1. Create package
cd PredictiveDataModel
./create_lambda_package.sh  # or PowerShell script on Windows

# 2. Create Lambda function
aws lambda create-function \
    --function-name PlayerImpactProcessor \
    --runtime python3.11 \
    --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-s3-role \
    --handler PlayerImpactFeature.lambda_handler \
    --zip-file fileb://playerimpact-lambda.zip \
    --timeout 300 \
    --memory-size 1024

# 3. Set environment variables
aws lambda update-function-configuration \
    --function-name PlayerImpactProcessor \
    --environment Variables="{SPORTRADAR_API_KEY=bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm}"

# 4. Test
aws lambda invoke \
    --function-name PlayerImpactProcessor \
    --payload '{"team_a":"KC","team_b":"GB"}' \
    output.json
```

---

## 📝 Package Contents

Your `playerimpact-lambda.zip` should contain:

```
playerimpact-lambda.zip/
├── PlayerImpactFeature.py        # Main feature calculator
├── S3DataLoader.py               # Loads data from S3
├── PositionMapper.py             # Position standardization
├── PlayerWeightAssigner.py       # Weight calculation
├── MaddenRatingMapper.py         # Madden rating mapping
├── InjuryImpactCalculator.py    # Injury calculations
├── SportradarClient.py           # API client
├── SupabaseStorage.py            # Database (optional)
├── game_processor.py             # Game processing
├── __init__.py                   # Module init
├── lambda_handler.py             # Lambda entry point (optional)
└── [dependencies]/               # boto3, pandas, numpy, etc.
    ├── pandas/
    ├── numpy/
    ├── boto3/
    └── ...
```

---

## 🎯 You're Ready to Deploy!

Based on your setup:

✅ **API Integration:** PlayerImpactFeature ready  
✅ **Lambda Configuration:** Instructions provided  
✅ **S3 Files:** Already uploaded to `sportsdatacollection`  
✅ **Data Processing:** S3DataLoader configured for your URIs  

**Next Steps:**
1. Run deployment script to create ZIP
2. Upload to Lambda
3. Configure environment variables
4. Test with sample teams
5. Integrate with prediction API

**Your deployment package will:**
- Load Madden ratings from S3 automatically
- Process player weights using the uploaded CSVs
- Calculate team impact scores
- Return impact differential for predictions

🚀 **Ready to deploy!**

