# 🔍 Lambda Verification Checklist

## ✅ What to Check

### **1. Handler Setting**
```
Lambda Console → ChatbotPredictionAPI → Runtime settings

Should show:
  Handler: api_handler.handler
```

**If wrong:** Click "Edit" → Change to `api_handler.handler` → Save

---

### **2. Environment Variables**
```
Lambda Console → Configuration → Environment variables

Should have exactly 5 variables:
```

| Key | Value |
|-----|-------|
| SUPABASE_DB_HOST | db.bodckgmwvhzythotvfgp.supabase.co |
| SUPABASE_DB_NAME | postgres |
| SUPABASE_DB_USER | postgres |
| SUPABASE_DB_PASSWORD | QtL0eNHRxeqva7Je |
| SUPABASE_DB_PORT | 5432 |

**If missing:** Click "Edit" → Add missing variables → Save

---

### **3. Code Files**
```
Lambda Console → Code tab

File list should include:
  ✅ api_handler.py
  ✅ SpreadPredictionCalculator.py
  ✅ DatabaseConnection.py
  ✅ fastapi/ folder
  ✅ pydantic/ folder
  ✅ mangum/ folder
```

**If wrong files:** Re-upload `chatbot-api-lambda.zip`

---

### **4. Memory & Timeout**
```
Lambda Console → Configuration → General configuration

Should show:
  Memory: 512 MB
  Timeout: 30 seconds
```

**If wrong:** Click "Edit" → Set correct values → Save

---

### **5. CloudWatch Logs**
```
Lambda Console → Monitor → View CloudWatch Logs → Latest log stream

Look for error messages like:
  - "Handler 'xxx' not found"
  - "ModuleNotFoundError"
  - "Database connection failed"
```

---

## 🔧 **Most Common Fix**

**90% of "Internal Server Error" is wrong handler!**

1. Go to Lambda → Runtime settings
2. Click "Edit"
3. Change to: `api_handler.handler`
4. Save
5. Test again

---

## 🧪 **Test Lambda Directly**

Before testing through API Gateway, test Lambda directly:

1. Lambda Console → Test tab
2. Create test event:

```json
{
  "rawPath": "/health",
  "requestContext": {
    "http": {
      "method": "GET",
      "path": "/health"
    }
  },
  "headers": {}
}
```

3. Click "Test"

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

**If you get an error:** Read the error message - it will tell you exactly what's wrong!

---

## 📋 **Quick Troubleshooting**

| Error | Cause | Fix |
|-------|-------|-----|
| "Handler not found" | Wrong handler setting | Change to `api_handler.handler` |
| "No module named 'fastapi'" | Wrong code uploaded | Re-upload chatbot-api-lambda.zip |
| "Database connection failed" | Missing env vars | Add 5 Supabase variables |
| "Timeout" | Lambda needs more time | Increase timeout to 30 sec |

---

## ✅ **After Fixing**

Test your API:
```powershell
curl https://bck79rw0nf.execute-api.us-east-1.amazonaws.com/Deployment/health
```

Should return:
```json
{
  "status": "healthy",
  "database": "connected",
  "predictor": "initialized"
}
```


















