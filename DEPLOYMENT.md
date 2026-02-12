# Deployment Guide - NFL Predictive Model Lambdas

Complete guide to deploying all 3 Lambda functions.

---

## Prerequisites

✅ AWS Account with Lambda access  
✅ AWS CLI configured  
✅ Supabase database with game data  
✅ S3 bucket with Madden ratings  
✅ Sportradar API key  

---

## Lambda 1: playerimpact

### Step 1: Package Lambda

```powershell
cd playerimpact

# Install dependencies
pip install -r requirements.txt -t .

# Create ZIP (PowerShell)
Compress-Archive -Path * -DestinationPath playerimpact.zip -Force
```

### Step 2: Deploy to AWS

**Option A: AWS Console**
1. Go to Lambda Console
2. Create/Update function: `playerimpact`
3. Runtime: Python 3.11
4. Upload `playerimpact.zip`
5. Handler: `lambda_function.lambda_handler`

**Option B: AWS CLI**
```bash
aws lambda create-function \
  --function-name playerimpact \
  --runtime python3.11 \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://playerimpact.zip \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --timeout 30 \
  --memory-size 512
```

### Step 3: Set Environment Variables

```
SPORTRADAR_API_KEY = bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm
PLAYER_DATA_BUCKET = sportsdatacollection
```

### Step 4: Test

```json
{
  "team_a": "BAL",
  "team_b": "BUF",
  "season": 2024
}
```

Expected response: Player impact scores

---

## Lambda 2: predictivedatamodel

### Step 1: Train Model (LOCAL FIRST!)

```powershell
cd ML-Training

# Install training dependencies
pip install -r requirements.txt

# Set Supabase credentials
$env:SUPABASE_DB_HOST="db.xxx.supabase.co"
$env:SUPABASE_DB_PASSWORD="your_password"

# Generate training data
python generate_training_data.py

# Train XGBoost model
python train_xgboost_model.py

# Copy trained model to Lambda folder
Copy-Item -Recurse models\ ..\predictivedatamodel\
```

### Step 2: Package Lambda

```powershell
cd predictivedatamodel

# Install dependencies
pip install -r requirements.txt -t .

# Verify models/ folder exists and contains:
# - latest_model.pkl
# - latest_features.json

# Create ZIP
Compress-Archive -Path * -DestinationPath predictivedatamodel.zip -Force
```

### Step 3: Deploy to AWS

**Important:** This ZIP will be larger (~50-200 MB) due to XGBoost + model

**Option A: AWS Console**
1. If ZIP > 50 MB, upload to S3 first:
   ```bash
   aws s3 cp predictivedatamodel.zip s3://your-bucket/lambdas/
   ```
2. Lambda Console → Upload from S3

**Option B: AWS CLI (if < 50 MB)**
```bash
aws lambda create-function \
  --function-name predictivedatamodel \
  --runtime python3.11 \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://predictivedatamodel.zip \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --timeout 30 \
  --memory-size 1024
```

**Option C: Use Lambda Layers (Recommended for large packages)**
See section below on Lambda Layers.

### Step 4: Set Environment Variables

```
SUPABASE_DB_HOST = db.xxx.supabase.co
SUPABASE_DB_PASSWORD = your_password
SUPABASE_DB_NAME = postgres
SUPABASE_DB_USER = postgres
SUPABASE_DB_PORT = 5432
```

### Step 5: Test

```json
{
  "team_a": "BAL",
  "team_b": "BUF",
  "spread_line": 2.5,
  "spread_favorite": "team_a"
}
```

Expected response: ML prediction with probabilities

---

## Lambda 3: chatbotAPI

### Step 1: Package Lambda

```powershell
cd chatbotAPI

# Install dependencies
pip install -r requirements.txt -t .

# Create ZIP
Compress-Archive -Path * -DestinationPath chatbotAPI.zip -Force
```

### Step 2: Deploy to AWS

```bash
aws lambda create-function \
  --function-name chatbotAPI \
  --runtime python3.11 \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://chatbotAPI.zip \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --timeout 30 \
  --memory-size 256
```

### Step 3: Grant Permissions

chatbotAPI needs permission to invoke the other Lambdas:

```bash
# Allow chatbotAPI to invoke playerimpact
aws lambda add-permission \
  --function-name playerimpact \
  --statement-id AllowChatbotInvoke \
  --action lambda:InvokeFunction \
  --principal arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role

# Allow chatbotAPI to invoke predictivedatamodel
aws lambda add-permission \
  --function-name predictivedatamodel \
  --statement-id AllowChatbotInvoke \
  --action lambda:InvokeFunction \
  --principal arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role
```

### Step 4: Test

```json
{
  "action": "full_analysis",
  "team_a": "BAL",
  "team_b": "BUF",
  "spread_line": 2.5,
  "spread_favorite": "team_a",
  "season": 2024
}
```

Expected response: Combined prediction + player impact

---

## Lambda Layers (Optional - Reduces Package Size)

### Create Layer for Dependencies

**For predictivedatamodel (heavy dependencies):**

```powershell
# Create layer structure
New-Item -ItemType Directory -Path layer\python
pip install xgboost scikit-learn joblib pandas numpy -t layer\python

# Create layer ZIP
cd layer
Compress-Archive -Path python -DestinationPath ../xgboost-layer.zip -Force
cd ..

# Upload layer
aws lambda publish-layer-version \
  --layer-name xgboost-dependencies \
  --zip-file fileb://xgboost-layer.zip \
  --compatible-runtimes python3.11
```

**Then attach layer to predictivedatamodel Lambda:**
1. Lambda Console → Configuration → Layers
2. Add Layer → Custom Layer → xgboost-dependencies

**Rebuild predictivedatamodel ZIP without heavy dependencies:**
```powershell
cd predictivedatamodel
# Only include code + models (no xgboost, sklearn, etc.)
Compress-Archive -Path lambda_function.py,models -DestinationPath predictivedatamodel-light.zip -Force
```

---

## Troubleshooting

### playerimpact Issues

**"No Madden data found"**
- Check S3 bucket permissions
- Verify files exist: `2022.csv`, `2023.csv`, `2024.csv` in bucket root
- Check `PLAYER_DATA_BUCKET` environment variable

### predictivedatamodel Issues

**"Model files not found"**
- Verify `models/latest_model.pkl` exists in ZIP
- Check file structure: `unzip -l predictivedatamodel.zip`

**"Unable to import module 'xgboost'"**
- Use Lambda Layer for dependencies (see above)
- Or increase memory (larger = faster cold starts)

### chatbotAPI Issues

**"Unable to invoke Lambda"**
- Check IAM permissions for Lambda invoke
- Verify Lambda function names match exactly

---

## Post-Deployment Checklist

✅ All 3 Lambdas deployed  
✅ Environment variables set  
✅ Test each Lambda individually  
✅ Test chatbotAPI full_analysis  
✅ Set up API Gateway (if needed)  
✅ Monitor CloudWatch logs  
✅ Clean up old PredictiveDataModel/ folder  

---

## Redeployment (After Model Retraining)

```bash
# 1. Retrain model
cd ML-Training
python train_xgboost_model.py

# 2. Copy new model to Lambda
cp -r models/ ../predictivedatamodel/

# 3. Repackage Lambda
cd ../predictivedatamodel
Compress-Archive -Path * -DestinationPath predictivedatamodel.zip -Force

# 4. Update Lambda
aws lambda update-function-code \
  --function-name predictivedatamodel \
  --zip-file fileb://predictivedatamodel.zip
```

---

**Need help?** Check CloudWatch logs for each Lambda function.

