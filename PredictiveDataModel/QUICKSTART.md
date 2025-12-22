# 🚀 NFL Prediction Chatbot - Quick Start

## ⏱️ 5-Minute Local Setup

### Step 1: Install Dependencies (1 min)
```powershell
cd "C:\Users\nealg\Nfl Predictive Model\NFLPredictiveModel\PredictiveDataModel"
pip install fastapi uvicorn openai requests pydantic
```

### Step 2: Set Environment Variables (1 min)
```powershell
# Already set (Supabase), but verify:
$env:SUPABASE_DB_HOST = "db.bodckgmwvhzythotvfgp.supabase.co"
$env:SUPABASE_DB_NAME = "postgres"
$env:SUPABASE_DB_USER = "postgres"
$env:SUPABASE_DB_PASSWORD = "QtL0eNHRxeqva7Je"
$env:SUPABASE_DB_PORT = "5432"

# NEW: Get OpenAI key from https://platform.openai.com/api-keys
$env:OPENAI_API_KEY = "sk-your-key-here"
```

### Step 3: Start API Server (30 sec)
```powershell
python api_server.py
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 4: Test It! (2 min)

**Option A: Command Line Chat**
Open new terminal:
```powershell
python chatbot.py
```

**Option B: Web Interface**
1. Open `static/chat.html` in browser
2. Update line 225: `const OPENAI_KEY = 'your-key-here';`
3. Chat away!

**Option C: Direct API Test**
```powershell
# Test prediction
curl -X POST http://localhost:8000/predict `
  -H "Content-Type: application/json" `
  -d '{\"team_a\":\"GB\",\"team_b\":\"PIT\",\"spread\":-2.5,\"team_a_home\":false}'
```

---

## 📝 Example Queries

```
"Who covers GB @ PIT with Packers -2.5?"
"Should I bet on Detroit -7.5 at home against Chicago?"
"Ravens +3 at Buffalo, give me your prediction"
"What's your confidence on 49ers -6 at Seattle?"
```

---

## 🎯 How It Works

```
Your Question → GPT-4 (understands question)
              ↓
         Extracts: Teams, Spread, Location
              ↓
         Calls Your Algorithm
              ↓
         Calculates:
           • Situational ATS (40%)
           • Overall ATS (30%)
           • Home/Away (30%)
              ↓
         Returns Prediction
              ↓
         GPT-4 (explains in natural language)
              ↓
         You Get Clear Recommendation!
```

---

## 🐛 Troubleshooting

### "Database connection failed"
- Check Supabase status
- Verify credentials

### "OpenAI API error"
- Get key: https://platform.openai.com/api-keys
- Check billing/quota

### "Can't connect to API"
- Make sure `python api_server.py` is running
- Check firewall

---

## 💰 Costs

- **Local Testing**: FREE (except OpenAI usage)
- **OpenAI API**: ~$0.01-0.03 per prediction
- **Production (AWS)**:
  - Lambda: ~$5-10/month
  - ECS: ~$30/month
  - EC2: ~$10/month

---

## 📚 Full Documentation

See `CHATBOT_SETUP.md` for:
- AWS deployment options
- SMS/Slack/Discord integration
- Production best practices
- Monitoring & scaling

---

## ✅ Verification

Run test suite:
```powershell
python test_chatbot.py
```

Expected:
```
✅ Prediction Calculator
✅ API Server
✅ OpenAI Chatbot

🎉 ALL TESTS PASSED!
```

---

## 🎉 You're Done!

Your chatbot is now:
- ✅ Using your custom NFL prediction algorithm
- ✅ Powered by GPT-4 for natural conversations
- ✅ Connected to your Supabase historical data
- ✅ Ready to give betting insights!

**Next**: Deploy to AWS (see `CHATBOT_SETUP.md`)

