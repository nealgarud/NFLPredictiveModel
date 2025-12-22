# ✅ Deployment Package Ready!

## 📦 What Was Created

**File:** `chatbot-api-lambda.zip`  
**Size:** 2.83 MB (well under 50 MB limit!)  
**Created:** October 29, 2025 at 5:31 PM

### Package Contents:
```
chatbot-api-lambda.zip (2.83 MB)
├── Core Files:
│   ├── api_handler.py              ← Lambda entry point
│   ├── SpreadPredictionCalculator.py ← YOUR EQUATION
│   └── DatabaseConnection.py        ← Supabase connector
│
└── Dependencies (13 packages):
    ├── fastapi/                     ← Web framework
    ├── pydantic/                    ← Data validation
    ├── mangum/                      ← Lambda adapter
    ├── pg8000/                      ← PostgreSQL driver
    ├── starlette/                   ← ASGI framework
    ├── anyio/                       ← Async support
    └── ... (7 more packages)
```

---

## 🚀 Next Steps: Deploy to AWS Lambda

### Step 1: Go to AWS Lambda Console
```
https://console.aws.amazon.com/lambda
```

### Step 2: Create Function
1. Click **"Create function"**
2. Choose **"Author from scratch"**
3. **Function name:** `ChatbotPredictionAPI`
4. **Runtime:** Python 3.11
5. **Architecture:** x86_64
6. Click **"Create function"**

### Step 3: Upload Your Package
1. In the **Code** tab
2. Click **"Upload from"** → **".zip file"**
3. Click **"Upload"**
4. Select: `chatbot-api-lambda.zip`
5. Wait for upload to complete (30-60 seconds)

### Step 4: Configure Handler
1. Scroll down to **"Runtime settings"**
2. Click **"Edit"**
3. **Handler:** `api_handler.handler` ⚠️ **IMPORTANT!**
4. Click **"Save"**

### Step 5: Configure Function Settings
1. Go to **"Configuration"** tab
2. Click **"General configuration"** → **"Edit"**
3. **Memory:** 512 MB
4. **Timeout:** 30 seconds
5. Click **"Save"**

### Step 6: Add Environment Variables
1. Stay in **"Configuration"** tab
2. Click **"Environment variables"** → **"Edit"**
3. Click **"Add environment variable"** for each:

```
SUPABASE_DB_HOST = db.bodckgmwvhzythotvfgp.supabase.co
SUPABASE_DB_NAME = postgres
SUPABASE_DB_USER = postgres
SUPABASE_DB_PASSWORD = QtL0eNHRxeqva7Je
SUPABASE_DB_PORT = 5432
```

4. Click **"Save"**

### Step 7: Test Your Function
1. Go to **"Test"** tab
2. Click **"Create new test event"**
3. **Event name:** `HealthCheck`
4. Replace JSON with:
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
5. Click **"Test"**

**Expected Response:**
```json
{
  "statusCode": 200,
  "body": "{\"status\":\"healthy\",\"database\":\"connected\",\"predictor\":\"initialized\"}"
}
```

---

## 🌐 After Lambda Works: Create API Gateway

Follow these steps to make your Lambda accessible via HTTPS:

### Step 1: Go to API Gateway
```
https://console.aws.amazon.com/apigateway
```

### Step 2: Create HTTP API
1. Click **"Create API"**
2. Choose **"HTTP API"** → Click **"Build"**
3. **API name:** `ChatbotAPI`
4. Click **"Next"**

### Step 3: Add Lambda Integration
1. Click **"Add integration"**
2. **Integration type:** Lambda
3. **Lambda function:** `ChatbotPredictionAPI`
4. Click **"Next"**

### Step 4: Configure Routes
- Auto-configured routes are created
- Click **"Next"**

### Step 5: Configure Stages
- **Stage name:** `prod`
- **Auto-deploy:** Yes
- Click **"Next"**

### Step 6: Create
- Review settings
- Click **"Create"**

### Step 7: Enable CORS
1. Select your API
2. Click **"CORS"** in left menu
3. **Access-Control-Allow-Origin:** `*`
4. **Access-Control-Allow-Methods:** GET, POST, OPTIONS
5. **Access-Control-Allow-Headers:** `*`
6. Click **"Save"**

### Step 8: Get Your API URL
1. Go to **"Stages"** → **"prod"**
2. Copy the **Invoke URL**
3. Example: `https://abc123xyz.execute-api.us-east-1.amazonaws.com`

---

## 🧪 Test Your API

### Test Health Endpoint
```powershell
# Replace with your actual API URL
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

### Test Prediction Endpoint
```powershell
$apiUrl = "https://YOUR-API-URL.execute-api.us-east-1.amazonaws.com"

$body = @{
    team_a = "GB"
    team_b = "PIT"
    spread = -2.5
    team_a_home = $false
} | ConvertTo-Json

Invoke-RestMethod -Uri "$apiUrl/predict" -Method POST -Body $body -ContentType "application/json"
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "matchup": "GB @ PIT",
    "prediction": {
      "recommended_bet": "GB",
      "probability": 0.539,
      "confidence": 0.078
    }
  }
}
```

---

## 📍 Where Your Files Are

```
C:\Users\nealg\Nfl Predictive Model\NFLPredictiveModel\PredictiveDataModel\
├── chatbot-api-lambda.zip          ← READY TO UPLOAD
├── chatbot_lambda/                  ← Source folder (can be deleted after upload)
├── api_handler.py                   ← Lambda handler (source)
├── SpreadPredictionCalculator.py   ← Your equation (source)
└── LAMBDA_DEPLOYMENT_GUIDE.md       ← Full deployment guide
```

---

## 🎯 What Happens When Deployed

```
User → OpenAI GPT-4 → API Gateway → Lambda → Your Equation → Supabase → Prediction
```

1. User asks: "Who covers GB @ PIT -2.5?"
2. OpenAI extracts: team_a=GB, team_b=PIT, spread=-2.5
3. Calls your API: POST /predict
4. API Gateway routes to Lambda
5. Lambda runs api_handler.py
6. Calls SpreadPredictionCalculator.py (YOUR EQUATION)
7. Queries Supabase for ATS data
8. Calculates: 40% situational + 30% overall + 30% home/away
9. Returns prediction
10. User sees result

---

## 💰 Cost

| Service | Cost |
|---------|------|
| Lambda (1M requests free tier) | $0 |
| API Gateway (1M requests free tier) | $0 |
| **Total for first 1M requests** | **$0** |

After free tier: ~$1.20 per million requests

---

## 🆘 Troubleshooting

### "Predictor not initialized"
- Check environment variables are set
- Verify Supabase credentials
- Check CloudWatch logs

### "Handler not found"
- Verify handler is: `api_handler.handler`
- Check Lambda uploaded correctly
- Redeploy if necessary

### "Database connection failed"
- Test Supabase credentials
- Check Lambda has internet access
- Verify port 5432 is accessible

---

## 📚 Additional Resources

- **Full Guide:** `LAMBDA_DEPLOYMENT_GUIDE.md`
- **Architecture:** See detailed diagrams in guide
- **Monitoring:** CloudWatch Logs in Lambda console
- **AWS Docs:** https://docs.aws.amazon.com/lambda/

---

## ✅ Checklist

### Before AWS:
- [x] Created deployment package
- [x] Package size under 50 MB (2.83 MB ✓)
- [x] Core files included
- [x] Dependencies installed

### AWS Lambda (15 min):
- [ ] Created function: `ChatbotPredictionAPI`
- [ ] Uploaded: `chatbot-api-lambda.zip`
- [ ] Set handler: `api_handler.handler`
- [ ] Configured: 512 MB, 30 sec timeout
- [ ] Added Supabase environment variables
- [ ] Tested /health endpoint

### API Gateway (10 min):
- [ ] Created HTTP API: `ChatbotAPI`
- [ ] Added Lambda integration
- [ ] Enabled CORS
- [ ] Deployed to prod stage
- [ ] Copied invoke URL
- [ ] Tested endpoints

### Final:
- [ ] Tested /health
- [ ] Tested /teams
- [ ] Tested /predict
- [ ] API returning predictions ✓

---

🎉 **You're ready to deploy! Follow the steps above to go live in 30 minutes!**

