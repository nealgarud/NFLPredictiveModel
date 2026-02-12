# Lambda Architecture - NFLPredictiveModel

## Folder Structure

```
NFLPredictiveModel/
│
├── playerimpact/                          # Lambda 1: Player Impact Calculator
│   ├── lambda_function.py                 # Handler (main entry point)
│   ├── requirements.txt
│   ├── SportradarClient.py
│   ├── S3DataLoader.py
│   ├── MaddenRatingMapper.py
│   ├── PlayerWeightAssigner.py
│   └── ... (all player impact modules)
│
├── predictivedatamodel/                   # Lambda 2: XGBoost Spread Prediction
│   ├── lambda_function.py                 # Handler (XGBoost prediction)
│   ├── requirements.txt
│   ├── DatabaseConnection.py
│   ├── models/                            # ML model files
│   │   ├── latest_model.pkl              # Trained XGBoost model
│   │   └── latest_features.json          # Feature names
│   └── FeatureExtractor.py               # Extract features for prediction
│
├── chatbotAPI/                            # Lambda 3: Chatbot Interface
│   ├── lambda_function.py                 # Handler (FastAPI + Mangum)
│   ├── requirements.txt
│   ├── main.py                           # FastAPI app
│   └── ... (chatbot logic)
│
├── ML-Training/                           # LOCAL ONLY (not deployed to Lambda)
│   ├── generate_training_data.py         # Step 1: Create training data
│   ├── train_xgboost_model.py            # Step 2: Train model
│   ├── requirements.txt
│   ├── training_data.csv                 # Generated locally
│   └── models/                            # Trained models (copy to predictivedatamodel/)
│       ├── latest_model.pkl
│       └── latest_features.json
│
└── shared/                                # Shared utilities (optional)
    ├── DatabaseConnection.py             # Shared DB connection
    └── utils.py
```

---

## Lambda Details

### **1. playerimpact/**
- **AWS Lambda Name:** `playerimpact`
- **Purpose:** Calculate player impact for a game using Madden ratings
- **Handler:** `lambda_function.lambda_handler`
- **Event:**
  ```json
  {
    "game_id": "abc123",
    "season": 2024,
    "team_a": "BAL",
    "team_b": "BUF"
  }
  ```
- **Response:** Player impact differential

---

### **2. predictivedatamodel/**
- **AWS Lambda Name:** `predictivedatamodel`
- **Purpose:** ML-based spread prediction (XGBoost)
- **Handler:** `lambda_function.lambda_handler`
- **Event:**
  ```json
  {
    "team_a": "BAL",
    "team_b": "BUF",
    "spread_line": 2.5,
    "spread_favorite": "team_a"
  }
  ```
- **Response:** Probability favorite covers spread
- **Model Storage:** 
  - Option 1: Include `models/` in Lambda ZIP (< 250MB)
  - Option 2: Load from S3 on cold start

---

### **3. chatbotAPI/**
- **AWS Lambda Name:** `chatbotAPI`
- **Purpose:** User-facing chatbot API (FastAPI)
- **Handler:** `lambda_function.handler` (Mangum wrapper)
- **Calls:** `playerimpact` and `predictivedatamodel` Lambdas
- **API Gateway:** REST or HTTP API

---

## ML Model Workflow

### **WHERE IS ML STORED?**

#### **Training (Local or EC2):**
```
Your Computer / EC2 Instance
  ↓
ML-Training/generate_training_data.py  (queries Supabase)
  ↓
ML-Training/train_xgboost_model.py     (trains model)
  ↓
ML-Training/models/latest_model.pkl    (saved locally)
```

#### **Deployment (Lambda):**
```
ML-Training/models/latest_model.pkl
  ↓ COPY TO ↓
predictivedatamodel/models/latest_model.pkl
  ↓ ZIP AND DEPLOY ↓
AWS Lambda: predictivedatamodel
  ↓ Loads model on cold start ↓
Cached in memory for warm starts
```

**Answer: NO EC2 for inference!**
- ✅ Train on local machine or EC2 (one-time/periodic)
- ✅ Deploy model files TO Lambda package
- ✅ Lambda loads model into memory (cached on warm starts)
- ❌ No separate EC2 instance needed for predictions

---

## Deployment Steps

### **Lambda 1: playerimpact**
```bash
cd playerimpact
pip install -r requirements.txt -t .
zip -r playerimpact.zip .
aws lambda update-function-code --function-name playerimpact --zip-file fileb://playerimpact.zip
```

### **Lambda 2: predictivedatamodel**
```bash
# 1. Train model (local or EC2)
cd ML-Training
python train_xgboost_model.py
# Creates: models/latest_model.pkl

# 2. Copy model to Lambda folder
cp -r models/ ../predictivedatamodel/

# 3. Deploy Lambda
cd ../predictivedatamodel
pip install -r requirements.txt -t .
zip -r predictivedatamodel.zip .
aws lambda update-function-code --function-name predictivedatamodel --zip-file fileb://predictivedatamodel.zip
```

### **Lambda 3: chatbotAPI**
```bash
cd chatbotAPI
pip install -r requirements.txt -t .
zip -r chatbotAPI.zip .
aws lambda update-function-code --function-name chatbotAPI --zip-file fileb://chatbotAPI.zip
```

---

## Why This Structure?

✅ **Clean separation** - Each Lambda is self-contained  
✅ **Folder = Lambda name** - Easy to find  
✅ **ML-Training separate** - Not deployed, just for model training  
✅ **No EC2 needed** - Lambda handles inference  
✅ **Easy deployment** - `cd folder && zip && deploy`  

---

## Model Size Considerations

### If `latest_model.pkl` is large (> 50 MB):

**Option 1: Lambda Layers**
```
predictivedatamodel/
  ├── lambda_function.py       # Code only
  └── requirements.txt

Lambda Layer:
  └── models/
      └── latest_model.pkl     # Model in layer
```

**Option 2: S3 + Download on Cold Start**
```python
# In lambda_function.py
import boto3

def load_model_from_s3():
    s3 = boto3.client('s3')
    s3.download_file('your-bucket', 'models/latest_model.pkl', '/tmp/latest_model.pkl')
    return joblib.load('/tmp/latest_model.pkl')
```

**Option 3: EFS (if model is huge > 250 MB)**
- Mount EFS to Lambda
- Store model on EFS
- Lambda reads directly from EFS

---

## Next Steps

1. ✅ Reorganize folders (I'll do this next)
2. ✅ Create `lambda_function.py` handlers for each
3. ✅ Move modules to correct Lambda folders
4. ✅ Update import paths
5. ✅ Create deployment scripts

Ready to reorganize? I'll create the new structure now.

