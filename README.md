# NFL Predictive Model

Machine Learning-powered NFL spread prediction system with player impact analysis and AI chatbot.

## Architecture

```
User
  │
  ▼
API Gateway
  ├── POST /predict  ──►  XGBoostPredictionLambda  ──►  S3 (model)
  │                                │                ──►  Supabase (features)
  │
  └── POST /chat    ──►  BedrockChatLambda  ──►  Amazon Bedrock (Claude 3 Haiku)
                                   │         ──►  XGBoostPredictionLambda
```

---

## Lambda Functions

### 1. `XGBoostPredictionLambda/` — ML Spread Predictor
- Deployed as a **Docker container image** (ECR) — required because xgboost has native Linux binaries
- Loads trained model + feature list from S3 on cold start
- Queries Supabase for team rankings, situational features, and player impact averages
- Builds 61-feature vector and runs XGBoost inference
- Returns predicted margin, ATS pick, and confidence

**Input:**
```json
{
  "home_team": "BAL",
  "away_team": "BUF",
  "spread_line": -2.5,
  "div_game": false,
  "season": 2025
}
```

### 2. `BedrockChatLambda/` — AI Chatbot
- Deployed as a **standard zip** (only uses boto3, already in Lambda runtime)
- Accepts natural language questions ("Who covers GB @ PIT -2.5?")
- Uses Claude 3 Haiku (Amazon Bedrock) with tool use to extract game params
- Invokes XGBoostPredictionLambda for the ML prediction
- Returns a natural language betting analysis

**Input:**
```json
{
  "message": "Who covers GB @ PIT with Packers -2.5?"
}
```

### 3. `playerimpact/` — Player Impact Calculator
- Calculates per-game player impact using Madden ratings + Sportradar API
- Feeds into `game_id_mapping` table, which XGBoostPredictionLambda uses for impact features

### 4. `chatbotAPI/` — Legacy Chatbot Interface
- Simple Lambda invoker (pre-Bedrock chatbot)
- Superseded by BedrockChatLambda

---

## Project Structure

```
NFLPredictiveModel/
│
├── XGBoostPredictionLambda/       # ML inference Lambda (Docker/ECR)
│   ├── lambda_function.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── BedrockChatLambda/             # AI chatbot Lambda (zip)
│   ├── lambda_function.py
│   └── requirements.txt
│
├── ML-Training/                   # Local training (not deployed)
│   ├── generate_training_data.py  # Pull from Supabase → CSV
│   ├── train_model.py             # Train XGBoost → models/
│   └── models/
│       ├── nfl_spread_model_latest.json
│       └── feature_names.json
│
├── playerimpact/                  # Player impact Lambda
├── chatbotAPI/                    # Legacy chatbot Lambda
├── PredictiveDataModel/           # Data pipeline Lambda (S3 → Supabase)
│
└── deploy.ps1                     # One-shot deployment script
```

---

## Deployment

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- AWS CLI configured (`aws configure`)
- Model trained (`ML-Training/models/nfl_spread_model_latest.json` exists)

### Option A: One-shot script
1. Edit `deploy.ps1` — set `$AWS_ACCOUNT_ID` and `$AWS_REGION` at the top
2. Run from the `NFLPredictiveModel/` folder:
   ```powershell
   .\deploy.ps1
   ```
   This will: upload model to S3 → create ECR repo → build + push Docker image → update both Lambdas.

### Option B: Manual steps

**Upload model to S3**
```powershell
aws s3 cp ML-Training/models/nfl_spread_model_latest.json s3://nfl-predictive-model-artifacts/models/nfl_spread_model_latest.json
aws s3 cp ML-Training/models/feature_names.json s3://nfl-predictive-model-artifacts/models/feature_names.json
```

**Build and push Docker image (XGBoostPredictionLambda)**
```powershell
# Authenticate Docker with ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

# Create ECR repo (first time only)
aws ecr create-repository --repository-name xgboost-prediction-lambda --region us-east-1

# Build
docker build -t <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/xgboost-prediction-lambda:latest XGBoostPredictionLambda/

# Push
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/xgboost-prediction-lambda:latest

# Update Lambda
aws lambda update-function-code \
  --function-name XGBoostPredictionLambda \
  --image-uri <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/xgboost-prediction-lambda:latest
```

**Deploy BedrockChatLambda (zip)**
```powershell
Compress-Archive -Force -Path BedrockChatLambda/lambda_function.py -DestinationPath BedrockChatLambda/deployment.zip
aws lambda update-function-code --function-name BedrockChatLambda --zip-file fileb://BedrockChatLambda/deployment.zip
```

---

## Environment Variables

### XGBoostPredictionLambda
| Variable | Value |
|---|---|
| `S3_BUCKET` | `nfl-predictive-model-artifacts` |
| `SUPABASE_DB_HOST` | `db.xxx.supabase.co` |
| `SUPABASE_DB_PASSWORD` | your password |
| `SUPABASE_DB_NAME` | `postgres` |
| `SUPABASE_DB_USER` | `postgres` |
| `SUPABASE_DB_PORT` | `6543` |

### BedrockChatLambda
| Variable | Value |
|---|---|
| `XGBOOST_LAMBDA_NAME` | `XGBoostPredictionLambda` |
| `BEDROCK_MODEL_ID` | `anthropic.claude-3-haiku-20240307-v1:0` |

---

## IAM Permissions

### XGBoostPredictionLambda execution role needs:
- `s3:GetObject` on `arn:aws:s3:::nfl-predictive-model-artifacts/*`

### BedrockChatLambda execution role needs:
- `bedrock:InvokeModel` on `arn:aws:bedrock:*::foundation-model/anthropic.claude-3-haiku-*`
- `lambda:InvokeFunction` on the XGBoostPredictionLambda ARN

---

## Amazon Bedrock Setup

1. AWS Console → **Amazon Bedrock** → **Model access** (left sidebar)
2. Click **Manage model access**
3. Find **Anthropic** → check **Claude 3 Haiku**
4. Click **Save changes**
5. Wait for status: **Access granted** (usually instant)

---

## Training the Model

```powershell
cd ML-Training

# Set Supabase credentials
cp .env.example .env   # fill in your values

# Pull data from Supabase into CSV
python generate_training_data.py

# Train XGBoost (saves to models/)
python train_model.py
```

Then re-run `deploy.ps1` to push the new model to S3 and redeploy.

---

## Documentation
- [Lambda Architecture](LAMBDA_ARCHITECTURE.md) — detailed architecture
- [ML Training README](ML-Training/README.md) — training workflow
