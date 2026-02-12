## **HistoricalGamesBatchProcessor** (`PredictionAPILambda/HistoricalGamesBatchProcessor.py`)
   - **Purpose:** One-time batch job to populate player impact features
   - **What it does:**
     - Loops through all games 2022-2025
     - Fetches active rosters from Sportradar API
     - Calculates player impact using Madden ratings
     - Stores in Supabase `player_impact` table
   - **When to run:** Once, before training the model
   - **Not a permanent Lambda** - just a data preparation script

### 2. **generate_training_data.py**
   - **Purpose:** Create `training_data.csv` for XGBoost
   - **Features calculated:**
     - Recent form (last 5 games)
     - ATS records
     - Home/away performance
     - Head-to-head records
     - Divisional games
     - Spread categories
     - Player impact (from step 1)
   - **Output:** `training_data.csv` (~500-1000 rows)

### 3. **train_xgboost_model.py**
   - **Purpose:** Train XGBoost classifier
   - **What it does:**
     - Loads `training_data.csv`
     - Splits 70% train / 10% val / 20% test
     - Trains XGBoost model
     - Evaluates accuracy, precision, recall, ROC-AUC
     - Saves model to `models/latest_model.pkl`
   - **Output:** Trained model + feature importance + metrics

### 4. **XGBoostPredictionLambda.py**
   - **Purpose:** REPLACES `SpreadPredictionCalculator.py`
   - **What it does:**
     - Loads trained XGBoost model
     - Receives matchup (team_a vs team_b, spread)
     - Extracts features from Supabase
     - Returns ML prediction (probability favorite covers)
   - **Deploy as Lambda** - this is your new prediction API

---

## Complete Workflow

### Phase 1: Data Preparation (ONE-TIME)

```bash
# Step 1: Run batch processor to populate player impact
# Deploy HistoricalGamesBatchProcessor to Lambda
# Invoke with:
{
  "start_season": 2022,
  "end_season": 2025
}
# This takes ~30-60 minutes (processes all games)

# Step 2: Generate training data
cd ML-Training
pip install -r requirements.txt
python generate_training_data.py
# Output: training_data.csv
```

### Phase 2: Model Training (LOCAL or EC2)

```bash
# Train XGBoost model
python train_xgboost_model.py

# Output:
# - models/latest_model.pkl (trained model)
# - models/latest_features.json (feature names)
# - models/model_metrics_XXXXXX.json (accuracy, etc.)
# - models/feature_importance.png (visualization)
# - models/confusion_matrix.png (test results)
```

### Phase 3: Deployment

```bash
# Deploy XGBoostPredictionLambda
# 1. Upload models/ folder to S3 or include in Lambda package
# 2. Create Lambda with XGBoostPredictionLambda.py as handler
# 3. Set environment variables:
#    MODEL_PATH=models/latest_model.pkl
#    FEATURES_PATH=models/latest_features.json
# 4. Test with:
{
  "team_a": "BAL",
  "team_b": "BUF",
  "spread_line": 2.5,
  "spread_favorite": "team_a"
}
```

### Phase 4: Retire Old System

```bash
# SCRAP these files:
# - SpreadPredictionCalculator.py (manual weights)
# - All the manual weight calculation logic

# KEEP these:
# - XGBoostPredictionLambda.py (new ML prediction)
# - DatabaseConnection.py (still needed)
# - PlayerImpactFeature.py (still needed for future updates)
```

---

## Your 3 Lambdas (UPDATED)

### 1. **playerimpact** Lambda
   - **Purpose:** Calculate player impact for a single game
   - **Handler:** `PlayerImpactFeature.lambda_handler`
   - **Keep this** - still useful for live predictions

### 2. **predictivedatamodel** Lambda ← **REPLACE THIS**
   - **OLD:** Uses `SpreadPredictionCalculator.py` with manual weights
   - **NEW:** Use `XGBoostPredictionLambda.py` with ML model
   - **Handler:** `XGBoostPredictionLambda.lambda_handler`

### 3. **chatbotAPI** Lambda
   - **Purpose:** Chatbot interface
   - **Update to call new XGBoost prediction API**
   - **Keep this**

---

## Expected Performance

Based on typical NFL spread prediction models:

### Baseline (Manual Weights)
- Accuracy: ~52-55%
- Essentially betting intuition codified

### XGBoost (ML Model)
- **Target Accuracy:** 55-60%
- **ROC-AUC:** 0.58-0.65
- Learns complex feature interactions automatically
- Updates easily with new data

### Key Advantages of ML Approach
✅ No manual weight tuning  
✅ Discovers non-linear patterns  
✅ Handles feature interactions  
✅ Easy to retrain with new seasons  
✅ Feature importance shows what matters  

---

## Retraining the Model (Future)

When you want to update the model with new data:

```bash
# 1. Run batch processor for new season
# Event: { "start_season": 2026, "end_season": 2026 }

# 2. Regenerate training data
python generate_training_data.py

# 3. Retrain model
python train_xgboost_model.py

# 4. Redeploy Lambda with new model
# Upload new models/latest_model.pkl to S3 or Lambda package
```

---

## File Structure

```
PredictiveDataModel/
├── ML-Training/                      ← NEW! ML training scripts
│   ├── generate_training_data.py
│   ├── train_xgboost_model.py
│   ├── requirements.txt
│   ├── README.md (this file)
│   ├── training_data.csv            ← Generated
│   └── models/                       ← Generated
│       ├── latest_model.pkl
│       ├── latest_features.json
│       └── model_metrics_*.json
│
├── PredictionAPILambda/
│   ├── XGBoostPredictionLambda.py   ← NEW! Replaces SpreadPredictionCalculator
│   ├── SpreadPredictionCalculator.py  ← DEPRECATE
│   ├── PlayerImpactFeature.py       ← Keep
│   ├── HistoricalGamesBatchProcessor.py  ← One-time use
│   └── DatabaseConnection.py        ← Keep
│
└── PlayerImpactCalculator/          ← Keep (used by batch processor)
    ├── SportradarClient.py
    ├── S3DataLoader.py
    └── ... (all modules)
```

---

## Quick Start

```bash
# 1. Install dependencies
cd ML-Training
pip install -r requirements.txt

# 2. Set environment variables
export SUPABASE_DB_HOST=db.xxx.supabase.co
export SUPABASE_DB_PASSWORD=your_password
export SUPABASE_DB_NAME=postgres
export SUPABASE_DB_USER=postgres
export SUPABASE_DB_PORT=5432

# 3. Generate training data
python generate_training_data.py

# 4. Train model
python train_xgboost_model.py

# 5. Review results
ls models/
cat models/model_metrics_*.json
```

---

## Troubleshooting

**Q: "No games found" error**  
A: Check database connection and ensure games table has data for 2022-2025

**Q: "No player impact data found"**  
A: Run `HistoricalGamesBatchProcessor` first to populate `player_impact` table

**Q: Model accuracy is low (~50%)**  
A: This is normal for NFL spreads. Even 53% is profitable. Focus on ROC-AUC > 0.55

**Q: How to add more features?**  
A: Edit `_calculate_game_features()` in `generate_training_data.py`, regenerate data, retrain

**Q: Can I use this for moneyline predictions?**  
A: Yes, change target from `favorite_covered` to `favorite_won` (straight up winner)

---

## Next Steps

1. ✅ Run `python generate_training_data.py`
2. ✅ Run `python train_xgboost_model.py`
3. ✅ Review `models/feature_importance.png`
4. ✅ Deploy `XGBoostPredictionLambda` to AWS
5. ✅ Update `chatbotAPI` to call new prediction Lambda
6. ✅ Deprecate `SpreadPredictionCalculator.py`

---

**Questions? Issues?** Check the training logs and model metrics first!

