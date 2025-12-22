# 🤖 NFL Prediction Chatbot - Complete Setup Guide

## Architecture Overview

```
┌─────────────────┐
│   User Input    │
│ (Chat/SMS/Web)  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│   OpenAI GPT-4 API      │
│  (Function Calling)     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   FastAPI Backend       │
│  (Prediction Service)   │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ SpreadPredictionCalc    │
│   (Your Algorithm)      │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Supabase PostgreSQL    │
│  (Historical Data)      │
└─────────────────────────┘
```

---

## 📋 Prerequisites

1. **OpenAI API Key**: Get from https://platform.openai.com/api-keys
2. **Supabase Credentials**: Already configured
3. **Python 3.11+**: Already installed
4. **AWS Account**: For deployment (optional for local testing)

---

## 🚀 Step 1: Local Setup & Testing

### 1.1 Install Dependencies

```powershell
cd "C:\Users\nealg\Nfl Predictive Model\NFLPredictiveModel\PredictiveDataModel"
pip install -r requirements.txt
```

### 1.2 Set Environment Variables

```powershell
# Supabase (already set, but verify)
$env:SUPABASE_DB_HOST = "db.bodckgmwvhzythotvfgp.supabase.co"
$env:SUPABASE_DB_NAME = "postgres"
$env:SUPABASE_DB_USER = "postgres"
$env:SUPABASE_DB_PASSWORD = "QtL0eNHRxeqva7Je"
$env:SUPABASE_DB_PORT = "5432"

# OpenAI API Key (get from https://platform.openai.com/api-keys)
$env:OPENAI_API_KEY = "sk-your-openai-api-key-here"
```

### 1.3 Start the API Server

```powershell
python api_server.py
```

**Expected Output:**
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Test the API:**
```powershell
# Open new terminal and test
curl http://localhost:8000/health
```

### 1.4 Test the Chatbot (Command Line)

```powershell
# Open new terminal
python chatbot.py
```

**Example Conversation:**
```
You: Who covers GB @ PIT with Packers -2.5?

Bot: Based on the 2024-2025 data, here's my prediction for GB @ PIT 
with Green Bay favored by 2.5 points:

🎯 Prediction: Green Bay -2.5 ✅
Confidence: 53.9%

Key Factors:
• Situational ATS: GB 66.7% (2-1) vs PIT 33.3% (1-3) in this spot
• Overall ATS: PIT 60.9% vs GB 47.7%
• Home/Away: PIT 63.6% home win rate vs GB 55.6% away

The Packers' strong performance as road favorites (2-1 ATS) gives them 
the edge despite Pittsburgh's better overall ATS record this season.
```

---

## 🌐 Step 2: Deploy to AWS (3 Options)

### **Option A: AWS Lambda + API Gateway** (Recommended for low cost)

#### Benefits:
- ✅ Pay per request (very cheap)
- ✅ Auto-scaling
- ✅ No server management

#### Limitations:
- ⚠️ Cold starts (1-3 second delay on first request)
- ⚠️ 15-minute timeout

#### Deployment Steps:

1. **Create Lambda Function**
```powershell
# Create deployment package
cd PredictiveDataModel
mkdir chatbot_lambda
cp SpreadPredictionCalculator.py chatbot_lambda/
cp DatabaseConnection.py chatbot_lambda/
cp api_server.py chatbot_lambda/
cp *.py chatbot_lambda/  # Copy all needed files

# Create lambda_handler.py
```

2. **Create `lambda_handler.py`:**
```python
from mangum import Mangum
from api_server import app

handler = Mangum(app)
```

3. **Install dependencies:**
```powershell
pip install mangum -t chatbot_lambda/
pip install fastapi -t chatbot_lambda/
pip install pydantic -t chatbot_lambda/
# ... install all requirements
```

4. **Create ZIP:**
```powershell
Compress-Archive -Path chatbot_lambda\* -DestinationPath chatbot-lambda.zip -Force
```

5. **Upload to Lambda:**
- Go to AWS Lambda Console
- Create new function: `nfl-prediction-chatbot`
- Runtime: Python 3.11
- Upload `chatbot-lambda.zip`
- Set handler: `lambda_handler.handler`
- Add environment variables (Supabase credentials)
- Increase timeout to 30 seconds
- Increase memory to 512 MB

6. **Create API Gateway:**
- Create HTTP API
- Add integration to Lambda function
- Deploy to stage (e.g., `prod`)
- Get invoke URL: `https://xxxxx.execute-api.us-east-1.amazonaws.com/prod`

---

### **Option B: AWS ECS (Fargate)** (Recommended for production)

#### Benefits:
- ✅ No cold starts
- ✅ Full Docker control
- ✅ Better for sustained traffic

#### Cost: ~$15-30/month for 0.25 vCPU, 0.5 GB RAM

#### Deployment Steps:

1. **Create Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

2. **Build and Push to ECR:**
```powershell
# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 838319850663.dkr.ecr.us-east-1.amazonaws.com

# Create ECR repository
aws ecr create-repository --repository-name nfl-prediction-api

# Build image
docker build -t nfl-prediction-api .

# Tag image
docker tag nfl-prediction-api:latest 838319850663.dkr.ecr.us-east-1.amazonaws.com/nfl-prediction-api:latest

# Push to ECR
docker push 838319850663.dkr.ecr.us-east-1.amazonaws.com/nfl-prediction-api:latest
```

3. **Create ECS Service:**
- Go to ECS Console
- Create Cluster (Fargate)
- Create Task Definition
  - Use your ECR image
  - Set environment variables
  - 0.25 vCPU, 0.5 GB memory
- Create Service
  - Enable load balancer (ALB)
  - Set desired count: 1
- Get ALB DNS name

---

### **Option C: EC2 Instance** (Simplest)

#### Benefits:
- ✅ Full control
- ✅ Easy to debug

#### Cost: ~$5-10/month for t2.micro/t3.micro

#### Deployment Steps:

1. **Launch EC2 Instance:**
- AMI: Amazon Linux 2023
- Type: t3.micro
- Security Group: Allow port 8000

2. **SSH and Setup:**
```bash
# SSH into instance
ssh -i your-key.pem ec2-user@your-instance-ip

# Install Python 3.11
sudo yum install python3.11 -y

# Clone/upload your code
# ... upload files ...

# Install dependencies
pip3.11 install -r requirements.txt

# Set environment variables
export SUPABASE_DB_HOST="..."
# ... set all env vars ...

# Run with systemd (persistent)
sudo nano /etc/systemd/system/nfl-api.service
```

3. **Create systemd service:**
```ini
[Unit]
Description=NFL Prediction API
After=network.target

[Service]
User=ec2-user
WorkingDirectory=/home/ec2-user/nfl-api
Environment="SUPABASE_DB_HOST=..."
ExecStart=/usr/bin/python3.11 -m uvicorn api_server:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Start service
sudo systemctl start nfl-api
sudo systemctl enable nfl-api
```

---

## 🔌 Step 3: Integrate with Chat Interfaces

### **Option 1: Web Chat Widget**

Create `chatbot_widget.html`:
```html
<!DOCTYPE html>
<html>
<head>
    <title>NFL Prediction Chatbot</title>
    <script>
        const API_URL = 'YOUR_API_ENDPOINT';  // From Step 2
        const OPENAI_KEY = 'YOUR_OPENAI_KEY';
        
        async function sendMessage() {
            const userInput = document.getElementById('user-input').value;
            // ... implement chat logic using fetch() to call your API
        }
    </script>
</head>
<body>
    <div id="chat-container">
        <div id="messages"></div>
        <input id="user-input" type="text" placeholder="Ask about any game...">
        <button onclick="sendMessage()">Send</button>
    </div>
</body>
</html>
```

---

### **Option 2: Twilio SMS Bot**

```python
from twilio.rest import Client
from flask import Flask, request
from chatbot import NFLPredictionChatbot

app = Flask(__name__)
chatbot = NFLPredictionChatbot(api_base_url='YOUR_API_URL')

@app.route('/sms', methods=['POST'])
def sms_reply():
    user_message = request.form['Body']
    response = chatbot.chat(user_message)
    
    # Send SMS back via Twilio
    # ... implementation ...
    
    return str(response)
```

---

### **Option 3: Slack Bot**

```python
from slack_bolt import App
from chatbot import NFLPredictionChatbot

app = App(token="YOUR_SLACK_TOKEN")
chatbot = NFLPredictionChatbot(api_base_url='YOUR_API_URL')

@app.message()
def handle_message(message, say):
    response = chatbot.chat(message['text'])
    say(response)

if __name__ == "__main__":
    app.start(port=3000)
```

---

### **Option 4: Discord Bot**

```python
import discord
from chatbot import NFLPredictionChatbot

client = discord.Client()
chatbot = NFLPredictionChatbot(api_base_url='YOUR_API_URL')

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    response = chatbot.chat(message.content)
    await message.channel.send(response)

client.run('YOUR_DISCORD_TOKEN')
```

---

## 💰 Cost Estimates

### API Costs:
- **OpenAI GPT-4 Turbo**: ~$0.01-0.03 per prediction
- **AWS Lambda**: ~$0.0000002 per request (essentially free for <1M requests/month)
- **ECS Fargate**: ~$15-30/month (24/7 running)
- **EC2 t3.micro**: ~$7.50/month (24/7 running)

### Recommended Setup:
- **Development**: Local testing (FREE)
- **Production (low traffic)**: Lambda + API Gateway (~$5-10/month with OpenAI)
- **Production (high traffic)**: ECS Fargate (~$30-50/month)

---

## 🧪 Testing Queries

```
1. "Who covers GB @ PIT with Packers -2.5?"
2. "Should I bet on Detroit -7.5 at home against Chicago?"
3. "What's your confidence on Ravens +3 at Buffalo?"
4. "Give me your best bet for this week"
5. "How do you calculate your predictions?"
```

---

## 🔒 Security Best Practices

1. **Never commit API keys** to Git
2. **Use AWS Secrets Manager** for production
3. **Enable CORS** only for your domains
4. **Rate limit** your API (use AWS API Gateway throttling)
5. **Monitor costs** with AWS Cost Alerts

---

## 📊 Monitoring

### CloudWatch Metrics (for Lambda/ECS):
- Request count
- Error rate
- Latency (p50, p99)
- OpenAI API costs

### Logs:
- CloudWatch Logs for Lambda/ECS
- Track prediction accuracy over time

---

## 🎯 Next Steps

1. ✅ Test locally with `python chatbot.py`
2. ✅ Deploy API to AWS (choose Option A, B, or C)
3. ✅ Get OpenAI API key
4. ✅ Test predictions via API
5. ✅ Build chat interface (web/SMS/Slack)
6. 📈 Monitor and optimize

---

## 🆘 Troubleshooting

### "Database connection failed"
- Check Supabase credentials
- Verify security group/firewall allows outbound on 5432

### "OpenAI API error"
- Verify OPENAI_API_KEY is set
- Check API quota/billing

### "Cold start timeout" (Lambda)
- Increase Lambda timeout to 30s
- Increase memory to 512 MB
- Consider provisioned concurrency

---

## 📞 Support

For issues, check:
1. CloudWatch Logs
2. API health endpoint: `GET /health`
3. Test prediction endpoint directly: `POST /predict`

---

**🏈 You're ready to deploy! Let me know which deployment option you want to use and I'll help you set it up.**

