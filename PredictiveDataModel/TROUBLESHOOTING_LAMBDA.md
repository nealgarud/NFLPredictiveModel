# 🔧 Troubleshooting: Lambda Error

## ❌ Current Error

```
{"message": "Error", "error": "'Records'"}
```

**What this means:** Lambda is receiving an S3 event format, not an API Gateway event format.

---

## 🔍 **Root Cause**

One of these is happening:

1. **Wrong Lambda function** - You might have deployed to `PredictiveDataModel` (the S3 one) instead of `ChatbotPredictionAPI`
2. **Wrong integration** - API Gateway is pointing to the wrong Lambda
3. **S3 trigger exists** - There's an S3 trigger on `ChatbotPredictionAPI` that shouldn't be there

---

## ✅ **Solution: Check Lambda Function Name**

### **Step 1: Verify Which Lambda You Created**

Go to Lambda Console: https://console.aws.amazon.com/lambda

You should see **TWO** Lambda functions:

```
1. PredictiveDataModel          ← OLD (for S3 data ingestion)
2. ChatbotPredictionAPI         ← NEW (for chatbot API)
```

**Question:** Did you upload `chatbot-api-lambda.zip` to the CORRECT Lambda?

---

## 🔧 **Fix Option 1: You Uploaded to Wrong Lambda**

If you accidentally uploaded to `PredictiveDataModel`:

1. Go to Lambda Console
2. Find `PredictiveDataModel`
3. **Don't change it!** This is your data pipeline Lambda
4. Create a NEW Lambda function called `ChatbotPredictionAPI`
5. Upload `chatbot-api-lambda.zip` to the NEW one

---

## 🔧 **Fix Option 2: API Gateway Points to Wrong Lambda**

1. Go to API Gateway Console
2. Select your API: `ChatbotAPI`
3. Click **"Integrations"** in left sidebar
4. Verify it points to: `ChatbotPredictionAPI` (NOT `PredictiveDataModel`)

If it's wrong:
- Click "Edit" on the integration
- Change Lambda function to: `ChatbotPredictionAPI`
- Save

---

## 🔧 **Fix Option 3: Check Lambda Handler**

If the Lambda is correct, check the handler:

1. Go to Lambda: `ChatbotPredictionAPI`
2. Scroll to "Runtime settings"
3. Handler should be: `api_handler.handler`
4. If it says `lambda_function.lambda_handler`, change it!

---

## 📋 **Step-by-Step: Create Correct Lambda**

### **1. Create New Lambda Function**

```
Function name: ChatbotPredictionAPI
Runtime: Python 3.11
Architecture: x86_64
Handler: api_handler.handler  ← IMPORTANT
```

### **2. Upload Code**

```
Code source → Upload from → .zip file
Select: chatbot-api-lambda.zip
Wait for upload to complete
```

### **3. Configure**

```
Memory: 512 MB
Timeout: 30 seconds
```

### **4. Add Environment Variables**

```
SUPABASE_DB_HOST = db.bodckgmwvhzythotvfgp.supabase.co
SUPABASE_DB_NAME = postgres
SUPABASE_DB_USER = postgres
SUPABASE_DB_PASSWORD = QtL0eNHRxeqva7Je
SUPABASE_DB_PORT = 5432
```

### **5. Verify Handler**

```
Runtime settings → Edit
Handler: api_handler.handler
```

### **6. Remove S3 Trigger (if exists)**

```
Configuration → Triggers
If you see S3 trigger → Remove it
Should have NO triggers
```

---

## 🔗 **Update API Gateway Integration**

1. Go to API Gateway Console
2. Select: `ChatbotAPI`
3. Click "Integrations" in left sidebar
4. Click "Edit" on your integration
5. Change to: `ChatbotPredictionAPI`
6. Save

---

## 🧪 **Test Lambda Directly**

Before testing through API Gateway, test Lambda directly:

1. Go to Lambda: `ChatbotPredictionAPI`
2. Click "Test" tab
3. Create test event:

```json
{
  "rawPath": "/health",
  "requestContext": {
    "http": {
      "method": "GET",
      "path": "/health"
    }
  }
}
```

4. Click "Test"

**Expected Response:**
```json
{
  "statusCode": 200,
  "headers": {
    "content-type": "application/json"
  },
  "body": "{\"status\":\"healthy\",\"database\":\"connected\",\"predictor\":\"initialized\"}"
}
```

**If you get the 'Records' error here too:**
- Wrong handler (`lambda_function.lambda_handler` instead of `api_handler.handler`)
- Wrong code uploaded (uploaded data pipeline code instead of chatbot code)

---

## 📸 **What to Check**

### **In Lambda Console:**

```
Function: ChatbotPredictionAPI

Code:
├─ Files should include:
│  ├─ api_handler.py         ← YOUR NEW FILE
│  ├─ SpreadPredictionCalculator.py
│  ├─ DatabaseConnection.py
│  └─ fastapi/, pydantic/, mangum/ folders

NOT:
├─ lambda_function.py        ← OLD FILE (wrong!)
├─ TextFileParser.py         ← OLD FILE (wrong!)
├─ GameRepository.py         ← OLD FILE (wrong!)
```

If you see the OLD files, you uploaded the wrong zip or to the wrong Lambda!

---

## ✅ **Correct Setup Checklist**

- [ ] Lambda function named: `ChatbotPredictionAPI`
- [ ] Uploaded: `chatbot-api-lambda.zip` (NOT the old data pipeline zip)
- [ ] Handler: `api_handler.handler`
- [ ] Memory: 512 MB
- [ ] Timeout: 30 seconds
- [ ] Environment variables: 5 Supabase vars
- [ ] NO S3 triggers
- [ ] API Gateway integration points to: `ChatbotPredictionAPI`

---

## 🎯 **Quick Fix Command**

If you need to recreate everything:

```powershell
# Verify you have the right package
Get-Item chatbot-api-lambda.zip

# Should show:
# Name: chatbot-api-lambda.zip
# Size: ~2.83 MB
```

Then:
1. Create NEW Lambda: `ChatbotPredictionAPI`
2. Upload THIS zip file
3. Set handler: `api_handler.handler`
4. Add environment variables
5. Update API Gateway to use this Lambda
6. Test

---

## 📞 **What to Tell Me**

Please check:

1. **Which Lambda did you upload the zip to?**
   - `PredictiveDataModel` (wrong - this is the S3 data pipeline)
   - `ChatbotPredictionAPI` (correct - this is the new API)

2. **What's the handler set to?**
   - `lambda_function.lambda_handler` (wrong)
   - `api_handler.handler` (correct)

3. **What files do you see in the Lambda code editor?**
   - List the files you see

Once you tell me, I can give you exact fix steps!

