# AWS Lambda Deployment with Layers
## Solution for 50 MB Limit

---

## 📦 Your Deployment Package

**File:** `nfl-lambda-lean.zip` (WITHOUT pandas/numpy)  
**Size:** ~12 MB  
**Contains:**
- Your 11 Python application files
- boto3, botocore, psycopg2-binary

**Missing (will add via Layer):**
- pandas
- numpy

---

## 🎯 Step-by-Step Deployment with S3

### Step 1: Upload Lean Package to S3

```bash
# Upload your deployment package to S3
aws s3 cp nfl-lambda-lean.zip s3://sportsdatacollection/lambda/

# Verify upload
aws s3 ls s3://sportsdatacollection/lambda/
```

### Step 2: Create Lambda Function from S3

```bash
aws lambda create-function \
  --function-name NFLPredictiveModel \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR-ACCOUNT-ID:role/LambdaExecutionRole \
  --handler Lambda_function.lambda_handler \
  --code S3Bucket=sportsdatacollection,S3Key=lambda/nfl-lambda-lean.zip \
  --timeout 900 \
  --memory-size 1024 \
  --environment Variables="{SUPABASE_DB_HOST=db.abc123.supabase.co,SUPABASE_DB_NAME=postgres,SUPABASE_DB_USER=postgres,SUPABASE_DB_PASSWORD=QtL0eNHRxeqva7Je,SUPABASE_DB_PORT=6543}"
```

**OR via AWS Console:**
1. Go to Lambda Console → Create function
2. Choose "Upload from" → "Amazon S3 location"
3. Enter: `s3://sportsdatacollection/lambda/nfl-lambda-lean.zip`
4. Set handler: `Lambda_function.lambda_handler`
5. Set runtime: Python 3.11

### Step 3: Add AWS Data Wrangler Layer (includes pandas + numpy)

AWS provides a public layer with pandas and numpy pre-installed!

**Option A: Via AWS Console (Easiest)**
1. Go to your Lambda function
2. Scroll down to "Layers"
3. Click "Add a layer"
4. Choose "AWS layers"
5. Select **"AWSSDKPandas-Python311"** (formerly AWS Data Wrangler)
6. Choose latest version
7. Click "Add"

**Option B: Via AWS CLI**

```bash
# Find the latest AWSSDKPandas layer ARN for your region
# US East 1 example:
aws lambda update-function-configuration \
  --function-name NFLPredictiveModel \
  --layers arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python311:13
```

**Layer ARNs by Region:**
- **us-east-1:** `arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python311:13`
- **us-west-2:** `arn:aws:lambda:us-west-2:336392948345:layer:AWSSDKPandas-Python311:13`
- **eu-west-1:** `arn:aws:lambda:eu-west-1:336392948345:layer:AWSSDKPandas-Python311:13`

> 💡 Check [AWS SDK for pandas Layers](https://aws-sdk-pandas.readthedocs.io/en/stable/layers.html) for other regions

### Step 4: Configure S3 Trigger for `raw-data/` folder

**Via AWS Console:**
1. Go to S3 → `sportsdatacollection` bucket
2. Click "Properties" tab
3. Scroll to "Event notifications"
4. Click "Create event notification"
5. Configure:
   - **Name:** `NFLDataProcessor`
   - **Prefix:** `raw-data/`
   - **Suffix:** `.txt`
   - **Event types:** ☑️ All object create events
   - **Destination:** Lambda function
   - **Lambda function:** NFLPredictiveModel
6. Click "Save changes"

**Via AWS CLI:**

```bash
# Add permission for S3 to invoke Lambda
aws lambda add-permission \
  --function-name NFLPredictiveModel \
  --statement-id s3-raw-data-trigger \
  --action lambda:InvokeFunction \
  --principal s3.amazonaws.com \
  --source-arn arn:aws:s3:::sportsdatacollection

# Create S3 event notification
aws s3api put-bucket-notification-configuration \
  --bucket sportsdatacollection \
  --notification-configuration file://s3-notification.json
```

**s3-notification.json:**
```json
{
  "LambdaFunctionConfigurations": [
    {
      "Id": "NFLDataProcessorTrigger",
      "LambdaFunctionArn": "arn:aws:lambda:REGION:ACCOUNT-ID:function:NFLPredictiveModel",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {
          "FilterRules": [
            {
              "Name": "prefix",
              "Value": "raw-data/"
            },
            {
              "Name": "suffix",
              "Value": ".txt"
            }
          ]
        }
      }
    }
  ]
}
```

### Step 5: Set Environment Variables

In Lambda Console → Configuration → Environment variables:

```
SUPABASE_DB_HOST=db.abc123.supabase.co
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=QtL0eNHRxeqva7Je
SUPABASE_DB_PORT=6543
```

---

## 🧪 Test Your Setup

### Test 1: Upload a file to S3

```bash
# Upload test file to trigger Lambda
aws s3 cp your-nfl-data.txt s3://sportsdatacollection/raw-data/test-data.txt

# Watch CloudWatch logs
aws logs tail /aws/lambda/NFLPredictiveModel --follow
```

### Test 2: Manual Lambda Test

Create `test-event.json`:
```json
{
  "Records": [
    {
      "s3": {
        "bucket": {
          "name": "sportsdatacollection"
        },
        "object": {
          "key": "raw-data/your-file.txt"
        }
      }
    }
  ]
}
```

Test via console or CLI:
```bash
aws lambda invoke \
  --function-name NFLPredictiveModel \
  --payload file://test-event.json \
  response.json

cat response.json
```

---

## 📋 Complete Workflow

Here's how your data processing will work:

1. **Upload File:**
   ```bash
   aws s3 cp nfl-games-2024.txt s3://sportsdatacollection/raw-data/
   ```

2. **S3 Triggers Lambda** (automatically)
   - Event: File uploaded to `raw-data/` folder
   - Lambda function: `NFLPredictiveModel` executes

3. **Lambda Processes Data:**
   - Reads file from S3
   - Parses game data
   - Connects to Supabase
   - Inserts/updates games
   - Calculates team statistics
   - Calculates ATS metrics
   - Updates team_rankings

4. **View Results:**
   - Check CloudWatch Logs
   - Query Supabase database

---

## 🔍 Verify Layer is Working

Test that pandas/numpy are available:

```python
# In Lambda test console
import pandas as pd
import numpy as np

def lambda_handler(event, context):
    print(f"Pandas version: {pd.__version__}")
    print(f"Numpy version: {np.__version__}")
    return {
        'statusCode': 200,
        'body': 'Libraries loaded successfully!'
    }
```

---

## ⚠️ Troubleshooting

### Issue: "No module named 'pandas'"
**Solution:** Make sure AWS SDK for pandas Layer is added

### Issue: "Version mismatch"
**Solution:** Use AWSSDKPandas-Python311 layer (matches your Python 3.11 runtime)

### Issue: S3 trigger not firing
**Solution:** 
- Check Lambda has S3 invoke permission
- Verify prefix/suffix filters are correct
- Check CloudWatch logs for errors

### Issue: "Unable to connect to database"
**Solution:**
- Verify environment variables are set correctly
- Check Lambda has internet access (no VPC or NAT Gateway configured)
- Test connection from Lambda to Supabase

---

## 💰 Cost Estimate

**Lambda Pricing:**
- First 1M requests/month: FREE
- After: $0.20 per 1M requests
- Compute: $0.0000166667 per GB-second

**Example:** 
- 1,000 files processed per month
- 30 seconds average processing time
- 1 GB memory
- **Cost:** ~$0.50/month

**S3 Pricing:**
- Storage: $0.023 per GB/month
- Requests: Minimal for this use case

**Supabase:**
- Free tier: 500 MB database
- Check your plan for limits

---

## 📝 Quick Command Reference

```bash
# Upload new code version
aws s3 cp nfl-lambda-lean.zip s3://sportsdatacollection/lambda/
aws lambda update-function-code \
  --function-name NFLPredictiveModel \
  --s3-bucket sportsdatacollection \
  --s3-key lambda/nfl-lambda-lean.zip

# View recent logs
aws logs tail /aws/lambda/NFLPredictiveModel --since 1h

# Test function
aws lambda invoke --function-name NFLPredictiveModel response.json

# List layers
aws lambda list-layers

# Upload test file
aws s3 cp test.txt s3://sportsdatacollection/raw-data/
```

---

## ✅ Deployment Checklist

- [ ] Upload `nfl-lambda-lean.zip` to S3
- [ ] Create Lambda function from S3
- [ ] Add AWSSDKPandas-Python311 layer
- [ ] Set environment variables (Supabase credentials)
- [ ] Configure S3 trigger for `raw-data/` folder
- [ ] Set timeout to 900 seconds
- [ ] Set memory to 1024 MB
- [ ] Test with sample file upload
- [ ] Verify data in Supabase
- [ ] Monitor CloudWatch logs

---

**Package Location:** `C:\Users\nealg\Nfl Predictive Model\NFLPredictiveModel\PredictiveDataModel\nfl-lambda-lean.zip`

**S3 Bucket:** `sportsdatacollection`  
**S3 Folder:** `raw-data/`  
**Ready to Deploy:** ✅ YES (with Lambda Layer)

