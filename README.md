# NFL Predictive Model

Machine Learning-powered NFL spread prediction system with player impact analysis.

## Architecture

This project consists of 3 AWS Lambda functions:

### 1. **playerimpact/** - Player Impact Calculator
- Calculates player impact using Madden ratings and Sportradar API
- Loads data from S3 (Madden CSVs)
- Returns team impact scores and differentials

### 2. **predictivedatamodel/** - XGBoost Spread Predictor
- ML-based spread prediction using XGBoost
- Replaces manual weight calculations
- Returns probability that favorite covers spread

### 3. **chatbotAPI/** - Chatbot Interface
- User-facing API
- Orchestrates calls to playerimpact and predictivedatamodel
- Can be connected to API Gateway

### 4. **ML-Training/** - Training Scripts (Local Only)
- Not deployed as Lambda
- Run locally or on EC2 to train XGBoost model
- Outputs models that are deployed to predictivedatamodel/

---

## Project Structure

```
NFLPredictiveModel/
│
├── playerimpact/                  # Lambda 1
│   ├── lambda_function.py
│   ├── requirements.txt
│   └── ... (modules)
│
├── predictivedatamodel/           # Lambda 2
│   ├── lambda_function.py
│   ├── requirements.txt
│   └── models/                   # XGBoost model files (copy from ML-Training)
│
├── chatbotAPI/                    # Lambda 3
│   ├── lambda_function.py
│   └── requirements.txt
│
├── ML-Training/                   # Local training (not a Lambda)
│   ├── generate_training_data.py
│   ├── train_xgboost_model.py
│   └── models/                   # Train here, copy to predictivedatamodel/
│
└── PredictiveDataModel/          # Legacy (to be cleaned up)
    └── ... (old structure)
```

---

## Quick Start

### Deploy Lambdas

Each Lambda folder contains:
- `lambda_function.py` - Handler (entry point)
- `requirements.txt` - Dependencies
- Supporting modules

**Deploy process:**
1. Install dependencies: `pip install -r requirements.txt -t .`
2. Create ZIP: `zip -r lambda.zip .`
3. Upload to AWS Lambda

See individual Lambda README files for details.

### Train ML Model

```bash
cd ML-Training
pip install -r requirements.txt

# Set environment variables for Supabase
export SUPABASE_DB_HOST=...
export SUPABASE_DB_PASSWORD=...

# Generate training data
python generate_training_data.py

# Train model
python train_xgboost_model.py

# Copy trained model to Lambda
cp -r models/ ../predictivedatamodel/
```

---

## Environment Variables

### playerimpact
```
SPORTRADAR_API_KEY=your_api_key
PLAYER_DATA_BUCKET=sportsdatacollection
```

### predictivedatamodel
```
SUPABASE_DB_HOST=db.xxx.supabase.co
SUPABASE_DB_PASSWORD=your_password
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PORT=5432
```

### chatbotAPI
```
(None required - invokes other Lambdas via boto3)
```

---

## Documentation

- [Lambda Architecture](LAMBDA_ARCHITECTURE.md) - Detailed architecture
- `playerimpact/README.md` - Player Impact Lambda docs
- `predictivedatamodel/README.md` - Prediction Lambda docs
- `chatbotAPI/README.md` - Chatbot API docs
- `ML-Training/README.md` - Training workflow

---

## Testing Locally

Each Lambda has a `__main__` block for local testing:

```bash
# Test playerimpact
cd playerimpact
python lambda_function.py

# Test predictivedatamodel (requires trained model)
cd predictivedatamodel
python lambda_function.py

# Test chatbotAPI (requires other Lambdas deployed)
cd chatbotAPI
python lambda_function.py
```

---

## Next Steps

1. ✅ Train ML model (see ML-Training/README.md)
2. ✅ Deploy Lambdas to AWS
3. ✅ Set environment variables
4. ✅ Test with API Gateway or Lambda console
5. ✅ Clean up legacy PredictiveDataModel/ folder

---

**Questions?** Check individual Lambda README files or LAMBDA_ARCHITECTURE.md

