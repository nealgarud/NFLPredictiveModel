# 🚀 Lambda Chatbot - Quick Deployment Guide

## ⚡ Quick Start (30 minutes)

### Step 1: Create Lambda Package (5 minutes)

```powershell
cd "C:\Users\nealg\Nfl Predictive Model\NFLPredictiveModel\PredictiveDataModel"

# Run deployment script
.\deploy_chatbot_lambda.ps1
```

**Expected Output:**
```
🚀 NFL Chatbot Lambda Deployment Script
============================================================
📦 Step 1: Preparing deployment folder...
   ✅ Created chatbot_lambda folder
📁 Step 2: Copying core files...
   ✅ Copied api_handler.py
   ✅ Copied SpreadPredictionCalculator.py
   ✅ Copied DatabaseConnection.py
📚 Step 3: Installing dependencies...
   ✅ Installed Python dependencies
🧹 Step 4: Cleaning up unnecessary files...
   ✅ Removed unnecessary files
📦 Step 5: Creating deployment package...
   ✅ Created chatbot-api-lambda.zip

✅ Deployment package ready!
📦 File: chatbot-api-lambda.zip
📊 Size: 12.3 MB
```

---

### Step 2: Create Lambda Function (10 minutes)

1. **Go to AWS Lambda Console**
   ```
   https://console.aws.amazon.com/lambda
   ```

2. **Create Function**
   - Click "Create function"
   - Choose "Author from scratch"
   - **Function name:** `ChatbotPredictionAPI`
   - **Runtime:** Python 3.11
   - **Architecture:** x86_64
   - Click "Create function"

3. **Upload Code**
   - In the Code tab, click "Upload from"
   - Select ".zip file"
   - Upload: `chatbot-api-lambda.zip`
   - Wait for upload (may take 30-60 seconds)

4. **Configure Handler**
   - Scroll down to "Runtime settings"
   - Click "Edit"
   - **Handler:** `api_handler.handler` ⚠️ IMPORTANT!
   - Click "Save"

5. **Configure Function Settings**
   - Go to "Configuration" tab
   - Click "General configuration" → "Edit"
   - **Memory:** 512 MB
   - **Timeout:** 30 seconds
   - Click "Save"

6. **Add Environment Variables**
   - Go to "Configuration" tab
   - Click "Environment variables" → "Edit"
   - Add the following:
   
   ```
   Key: SUPABASE_DB_HOST
   Value: db.bodckgmwvhzythotvfgp.supabase.co

   Key: SUPABASE_DB_NAME
   Value: postgres

   Key: SUPABASE_DB_USER
   Value: postgres

   Key: SUPABASE_DB_PASSWORD
   Value: QtL0eNHRxeqva7Je

   Key: SUPABASE_DB_PORT
   Value: 5432
   ```
   
   - Click "Save"

7. **Test Function**
   - Go to "Test" tab
   - Click "Create new test event"
   - Event name: `HealthCheck`
   - Replace JSON with:
   ```json
   {
     "rawPath": "/health",
     "requestContext": {
       "http": {
         "method": "GET"
       }
     }
   }
   ```
   - Click "Test"
   
   **Expected Response:**
   ```json
   {
     "statusCode": 200,
     "body": "{\"status\":\"healthy\",\"database\":\"connected\",\"predictor\":\"initialized\"}"
   }
   ```

---

### Step 3: Create API Gateway (10 minutes)

1. **Go to API Gateway Console**
   ```
   https://console.aws.amazon.com/apigateway
   ```

2. **Create HTTP API**
   - Click "Create API"
   - Choose "HTTP API" → Click "Build"
   - **API name:** `ChatbotAPI`
   - Click "Next"

3. **Add Integration**
   - Click "Add integration"
   - **Integration type:** Lambda
   - **Lambda function:** `ChatbotPredictionAPI`
   - **Version:** $LATEST
   - Click "Next"

4. **Configure Routes**
   - The wizard auto-creates routes
   - Click "Next"

5. **Configure Stages**
   - **Stage name:** `prod`
   - **Auto-deploy:** Yes
   - Click "Next"

6. **Review and Create**
   - Review settings
   - Click "Create"

7. **Enable CORS**
   - Select your API
   - Click "CORS" in left menu
   - Click "Configure"
   - **Access-Control-Allow-Origin:** `*`
   - **Access-Control-Allow-Methods:** GET, POST, OPTIONS
   - **Access-Control-Allow-Headers:** `*`
   - Click "Save"

8. **Get Invoke URL**
   - Go to "Stages" → "prod"
   - Copy the **Invoke URL**
   - It looks like: `https://abc123xyz.execute-api.us-east-1.amazonaws.com`

9. **Test API**
   ```powershell
   # Replace with your actual URL
   curl https://YOUR-API-URL.execute-api.us-east-1.amazonaws.com/health
   ```
   
   **Expected Response:**
   ```json
   {
     "status": "healthy",
     "database": "connected",
     "predictor": "initialized"
   }
   ```

---

### Step 4: Test Prediction Endpoint (5 minutes)

```powershell
# Test prediction (replace with your API URL)
$apiUrl = "https://YOUR-API-URL.execute-api.us-east-1.amazonaws.com"

$body = @{
    team_a = "GB"
    team_b = "PIT"
    spread = -2.5
    team_a_home = $false
    seasons = @(2024, 2025)
} | ConvertTo-Json

Invoke-RestMethod -Uri "$apiUrl/predict" -Method POST -Body $body -ContentType "application/json"
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "matchup": "GB @ PIT",
    "spread_line": "GB -2.5",
    "favored_team": "GB",
    "underdog_team": "PIT",
    "prediction": {
      "recommended_bet": "GB",
      "probability": 0.539,
      "confidence": 0.078,
      "favored_cover_probability": 0.539
    },
    "breakdown": {
      "situational_ats": {...},
      "overall_ats": {...},
      "home_away": {...}
    }
  },
  "error": null
}
```

---

## 🎯 Where Your Equation Runs

```
User Query
  ↓
API Gateway: https://YOUR-API-URL.amazonaws.com/predict
  ↓
Lambda: ChatbotPredictionAPI
  ↓
api_handler.py (receives request)
  ↓
SpreadPredictionCalculator.py ← YOUR EQUATION HERE
  ├─ Queries Supabase for situational ATS
  ├─ Queries Supabase for overall ATS
  ├─ Queries Supabase for home/away splits
  └─ Calculates: 0.40 × situational + 0.30 × overall + 0.30 × home_away
  ↓
Returns prediction with confidence
```

---

## 🔍 Monitoring & Debugging

### View Lambda Logs
1. Go to Lambda Console
2. Select `ChatbotPredictionAPI`
3. Click "Monitor" tab
4. Click "View CloudWatch Logs"
5. Click latest log stream

### Common Issues

**Issue: "Predictor not initialized"**
- Check environment variables are set correctly
- Verify Supabase credentials
- Check CloudWatch logs for connection errors

**Issue: "Database connection failed"**
- Verify Supabase host/port/credentials
- Check Lambda has internet access (default VPC)
- Test connection in Lambda test console

**Issue: "Handler not found"**
- Verify handler is set to: `api_handler.handler`
- Check zip file contains `api_handler.py`
- Redeploy if necessary

---

## 💰 Cost Breakdown

| Service | Free Tier | After Free Tier |
|---------|-----------|-----------------|
| Lambda | 1M requests/month free | $0.20 per 1M requests |
| API Gateway | 1M requests/month free | $1.00 per 1M requests |
| CloudWatch Logs | 5GB free | $0.50 per GB |
| **Total** | **FREE for < 1M requests** | **~$1.20 per 1M** |

**Example:** 1,000 predictions/month = FREE ✅

---

## 📋 Quick Reference

### Lambda Function Details
- **Name:** `ChatbotPredictionAPI`
- **Runtime:** Python 3.11
- **Handler:** `api_handler.handler`
- **Memory:** 512 MB
- **Timeout:** 30 seconds

### API Gateway Details
- **Name:** `ChatbotAPI`
- **Type:** HTTP API
- **Stage:** prod
- **CORS:** Enabled

### Environment Variables
```
SUPABASE_DB_HOST=db.bodckgmwvhzythotvfgp.supabase.co
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=QtL0eNHRxeqva7Je
SUPABASE_DB_PORT=5432
```

### Endpoints
- `GET /` - Root (API info)
- `GET /health` - Health check
- `GET /teams` - List teams
- `POST /predict` - Get prediction (YOUR EQUATION)

---

## 🚀 You're Done!

Your chatbot API is now live! 

**API URL:** `https://YOUR-API-URL.execute-api.us-east-1.amazonaws.com`

### Next Steps:
1. ✅ Test all endpoints
2. ✅ Set up web interface (S3 or local)
3. ✅ Connect OpenAI chatbot
4. ✅ Start getting predictions!

---

## 🆘 Need Help?

**Check Logs:**
```
AWS Console → Lambda → ChatbotPredictionAPI → Monitor → View CloudWatch Logs
```

**Test Locally:**
```powershell
# Run api_handler.py locally
cd PredictiveDataModel
python api_handler.py
# Visit: http://localhost:8000/health
```

**Redeploy:**
```powershell
# Recreate package
.\deploy_chatbot_lambda.ps1

# Re-upload in Lambda Console
# Code tab → Upload from .zip file
```

---

🎉 **Congratulations! Your NFL prediction chatbot is live on AWS!** 🏈

