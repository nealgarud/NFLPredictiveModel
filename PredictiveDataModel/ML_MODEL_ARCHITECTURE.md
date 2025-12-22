# 🤖 NFL Spread Prediction ML Model - Architecture & Implementation

## 🎯 Goal
Build a machine learning model that:
1. Pulls training data from Supabase
2. Trains on historical ATS performance
3. Integrates with chatbot seamlessly
4. Provides predictions with confidence and explainability

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXISTING ARCHITECTURE                         │
│  User → OpenAI Chatbot → FastAPI → [SpreadPredictionCalculator] │
└─────────────────────────────────────────────────────────────────┘
                                            ↓ REPLACE WITH ↓
┌─────────────────────────────────────────────────────────────────┐
│                     NEW ML ARCHITECTURE                          │
│  User → OpenAI Chatbot → FastAPI → [MLSpreadPredictor]          │
│                                      ↓                           │
│                              Trained ML Model                    │
│                                      ↓                           │
│                              Feature Engineering                 │
│                                      ↓                           │
│                            Supabase Database                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Data Flow

### **Training Pipeline (Run Weekly)**
```
1. Extract Data
   ↓
   Query Supabase for games + team_rankings (2022-2024)
   
2. Feature Engineering
   ↓
   Calculate features for each game:
   • Last 5 games ATS record (both teams)
   • Home/Away splits (win %, ATS %, avg margin)
   • Season-to-date stats (offensive/defensive rank)
   • Spread range (2-4, 4-7, etc.)
   • Head-to-head history
   • Rest days
   • Division game flag
   
3. Train Model
   ↓
   XGBoost Classifier (favored covers: Yes/No)
   Train-Test Split: 80/20
   Cross-validation: 5-fold
   
4. Save Model
   ↓
   Save to: models/spread_predictor_v{version}.pkl
   
5. Evaluate
   ↓
   Metrics: Accuracy, Precision, Recall, AUC
   Feature Importance: Top 10 features
```

### **Prediction Pipeline (Real-time)**
```
1. User Query
   ↓
   "GB @ PIT, Packers -2.5"
   
2. Feature Extraction
   ↓
   Query Supabase for:
   • Last 5 games for both teams
   • Season stats
   • Home/away splits
   • Historical matchups
   
3. Feature Engineering
   ↓
   Transform raw data into model features
   
4. Model Prediction
   ↓
   • Probability: 0.0 - 1.0 (favored covers)
   • Confidence: Based on prediction probability
   
5. Explainability
   ↓
   SHAP values: Which features drove prediction?
   
6. Response
   ↓
   "Bet on GB -2.5"
   "61% chance they cover"
   "78% confidence"
   "Key factors: GB 4-1 ATS last 5, PIT 38% home ATS"
```

---

## 🎲 Model Choice: XGBoost

### **Why XGBoost?**
✅ **High accuracy** for tabular data  
✅ **Fast training** (<1 minute on your dataset)  
✅ **Built-in feature importance**  
✅ **Handles missing values**  
✅ **Prevents overfitting** (regularization)  
✅ **Explainable** (SHAP integration)  

### **Alternatives Considered**
- ❌ **Neural Networks**: Overkill, needs more data, less interpretable
- ❌ **Logistic Regression**: Too simple, misses interactions
- ✅ **Random Forest**: Good alternative, but XGBoost usually better
- ❌ **SVM**: Slower, less interpretable

---

## 📈 Feature Engineering (20+ Features)

### **Team Performance (Last 5 Games)**
1. `fav_last5_ats_wins` - Favored team ATS wins in last 5
2. `fav_last5_ats_rate` - Favored team ATS rate in last 5
3. `und_last5_ats_wins` - Underdog team ATS wins in last 5
4. `und_last5_ats_rate` - Underdog team ATS rate in last 5
5. `fav_last5_margin_avg` - Favored team avg margin last 5
6. `und_last5_margin_avg` - Underdog team avg margin last 5

### **Home/Away Splits**
7. `fav_location_ats_rate` - Favored team ATS rate at location
8. `fav_location_win_rate` - Favored team win rate at location
9. `und_location_ats_rate` - Underdog team ATS rate at location
10. `und_location_win_rate` - Underdog team win rate at location

### **Season Stats (Cumulative)**
11. `fav_season_ats_rate` - Favored team season ATS rate
12. `und_season_ats_rate` - Underdog team season ATS rate
13. `fav_offensive_rank` - Favored team offensive rank
14. `fav_defensive_rank` - Favored team defensive rank
15. `und_offensive_rank` - Underdog team offensive rank
16. `und_defensive_rank` - Underdog team defensive rank

### **Spread Characteristics**
17. `spread_value` - Absolute spread value
18. `spread_range` - Categorical (0-2, 2-4, 4-7, etc.)
19. `total_line` - Over/under line

### **Matchup Context**
20. `div_game` - Boolean (division game)
21. `h2h_fav_ats_rate` - Head-to-head ATS rate (last 3 years)
22. `week_number` - Week of season (1-18)

### **Advanced (Optional)**
23. `fav_rest_days` - Days since last game
24. `und_rest_days` - Days since last game
25. `fav_times_favored` - How often team is favored
26. `und_times_underdog` - How often team is underdog

### **Target Variable**
- `favored_covers` - Boolean (1 = favored covered, 0 = underdog covered)

---

## 🛠️ Implementation Plan

### **Phase 1: Data Preparation (Week 1)**

#### **File 1: `MLDataPreparation.py`**
```python
"""
Extract and prepare training data from Supabase
Output: CSV file with features + target variable
"""

class MLDataPreparation:
    def extract_training_data(self, seasons=[2022, 2023, 2024]):
        """
        Query all games + calculate features
        Returns: DataFrame with ~1500 rows, 25+ columns
        """
        pass
    
    def calculate_last_5_features(self, team, game_date):
        """Calculate last 5 games stats for a team"""
        pass
    
    def calculate_season_features(self, team, season, week):
        """Calculate season-to-date stats"""
        pass
    
    def calculate_home_away_splits(self, team, location, season):
        """Calculate home/away performance"""
        pass
```

**Output:** `training_data_2022_2024.csv`

---

### **Phase 2: Model Training (Week 1)**

#### **File 2: `MLModelTrainer.py`**
```python
"""
Train XGBoost model on prepared data
Save model + evaluation metrics
"""

import xgboost as xgb
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score

class MLModelTrainer:
    def train_model(self, data_path):
        """
        Train XGBoost classifier
        Returns: Trained model + metrics
        """
        # Load data
        df = pd.read_csv(data_path)
        
        # Split features/target
        X = df.drop(['favored_covers', 'game_id'], axis=1)
        y = df['favored_covers']
        
        # Train-test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Train XGBoost
        model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            random_state=42
        )
        
        model.fit(X_train, y_train)
        
        # Evaluate
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]
        
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'auc': roc_auc_score(y_test, y_proba),
            'report': classification_report(y_test, y_pred)
        }
        
        return model, metrics
    
    def save_model(self, model, version):
        """Save model to disk"""
        joblib.dump(model, f'models/spread_predictor_v{version}.pkl')
```

**Output:** `models/spread_predictor_v1.pkl`

---

### **Phase 3: Prediction Engine (Week 2)**

#### **File 3: `MLSpreadPredictor.py`**
```python
"""
Real-time prediction engine (replaces SpreadPredictionCalculator)
"""

import joblib
import shap
from typing import Dict

class MLSpreadPredictor:
    def __init__(self, model_path='models/spread_predictor_v1.pkl'):
        self.model = joblib.load(model_path)
        self.db = DatabaseConnection()
        self.explainer = shap.TreeExplainer(self.model)
    
    def predict_spread_coverage(
        self, 
        team_a: str, 
        team_b: str, 
        spread: float,
        team_a_home: bool,
        current_season: int = 2025,
        current_week: int = 9
    ) -> Dict:
        """
        Predict which team covers the spread
        
        Returns:
        {
            'prediction': 'GB',
            'probability': 0.61,  # 61% chance favored covers
            'confidence': 0.78,   # How confident (based on proba)
            'explanation': {
                'top_factors': [
                    'GB 4-1 ATS last 5 games (80%)',
                    'PIT 38% ATS at home this season',
                    'GB ranked #3 offense vs PIT #18 defense'
                ],
                'key_stats': {
                    'fav_last5_ats_rate': 0.80,
                    'und_location_ats_rate': 0.38,
                    'offensive_matchup': '+15 rank advantage'
                }
            }
        }
        """
        # 1. Extract features
        features = self._extract_features(
            team_a, team_b, spread, team_a_home, 
            current_season, current_week
        )
        
        # 2. Make prediction
        proba = self.model.predict_proba([features])[0]
        favored_covers_proba = proba[1]
        
        # 3. Calculate confidence
        confidence = self._calculate_confidence(favored_covers_proba)
        
        # 4. Generate explanation
        explanation = self._explain_prediction(features, favored_covers_proba)
        
        # 5. Build response
        favored_team = team_a if spread < 0 else team_b
        underdog_team = team_b if spread < 0 else team_a
        
        recommended_bet = favored_team if favored_covers_proba > 0.5 else underdog_team
        
        return {
            'matchup': f"{team_a} @ {team_b}" if not team_a_home else f"{team_b} @ {team_a}",
            'spread_line': f"{favored_team} {abs(spread):+.1f}",
            'prediction': {
                'recommended_bet': recommended_bet,
                'probability': round(max(favored_covers_proba, 1-favored_covers_proba), 3),
                'confidence': confidence,
                'favored_covers_probability': round(favored_covers_proba, 3)
            },
            'explanation': explanation
        }
    
    def _extract_features(self, team_a, team_b, spread, team_a_home, season, week):
        """Query database and calculate all 25+ features"""
        features = {}
        
        # Determine roles
        if spread < 0:
            fav, und = team_a, team_b
            fav_home = team_a_home
        else:
            fav, und = team_b, team_a
            fav_home = not team_a_home
        
        # Last 5 games features
        fav_last5 = self._get_last_5_games(fav, season, week)
        und_last5 = self._get_last_5_games(und, season, week)
        
        features['fav_last5_ats_wins'] = fav_last5['ats_wins']
        features['fav_last5_ats_rate'] = fav_last5['ats_rate']
        features['und_last5_ats_wins'] = und_last5['ats_wins']
        features['und_last5_ats_rate'] = und_last5['ats_rate']
        
        # Home/Away splits
        fav_location = 'home' if fav_home else 'away'
        und_location = 'away' if fav_home else 'home'
        
        fav_splits = self._get_location_splits(fav, fav_location, season)
        und_splits = self._get_location_splits(und, und_location, season)
        
        features['fav_location_ats_rate'] = fav_splits['ats_rate']
        features['und_location_ats_rate'] = und_splits['ats_rate']
        
        # Season stats
        fav_stats = self._get_season_stats(fav, season)
        und_stats = self._get_season_stats(und, season)
        
        features['fav_season_ats_rate'] = fav_stats['ats_cover_rate']
        features['und_season_ats_rate'] = und_stats['ats_cover_rate']
        features['fav_offensive_rank'] = fav_stats['offensive_rank']
        features['fav_defensive_rank'] = fav_stats['defensive_rank']
        
        # Spread characteristics
        features['spread_value'] = abs(spread)
        features['spread_range'] = self._categorize_spread(abs(spread))
        
        return list(features.values())
    
    def _calculate_confidence(self, probability):
        """
        Convert probability to confidence score
        
        Logic:
        - 50% = 0% confidence (coin flip)
        - 60% = 40% confidence
        - 70% = 60% confidence
        - 80% = 80% confidence
        - 90%+ = 95% confidence
        """
        edge = abs(probability - 0.5)
        confidence = min(edge * 2, 0.95)
        return round(confidence, 3)
    
    def _explain_prediction(self, features, probability):
        """
        Use SHAP to explain which features drove the prediction
        
        Returns top 3-5 factors in plain English
        """
        # Calculate SHAP values
        shap_values = self.explainer.shap_values(features)
        
        # Get top features by absolute SHAP value
        feature_importance = sorted(
            enumerate(abs(shap_values)), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        
        # Convert to human-readable explanations
        explanations = []
        for idx, importance in feature_importance:
            feature_name = self.feature_names[idx]
            feature_value = features[idx]
            
            explanation = self._format_explanation(
                feature_name, feature_value, importance
            )
            explanations.append(explanation)
        
        return {
            'top_factors': explanations,
            'confidence_note': self._get_confidence_note(probability)
        }
    
    def _format_explanation(self, feature_name, value, importance):
        """Convert feature into human-readable text"""
        if feature_name == 'fav_last5_ats_rate':
            return f"Favored team {value*100:.0f}% ATS in last 5 games"
        elif feature_name == 'und_location_ats_rate':
            return f"Underdog {value*100:.0f}% ATS at their location"
        # ... more formatting rules ...
        
    def _get_confidence_note(self, probability):
        """Add context about confidence level"""
        if probability > 0.65:
            return "High confidence - strong historical trends support this pick"
        elif probability > 0.55:
            return "Moderate confidence - some supporting factors"
        else:
            return "Low confidence - close to coin flip, consider avoiding"
```

---

### **Phase 4: API Integration (Week 2)**

#### **Update: `api_server.py`**
```python
# Replace SpreadPredictionCalculator with MLSpreadPredictor
from MLSpreadPredictor import MLSpreadPredictor

# Initialize ML predictor instead
predictor = MLSpreadPredictor(model_path='models/spread_predictor_v1.pkl')

@app.post("/predict", response_model=PredictionResponse)
def predict_spread(request: PredictionRequest):
    """Now uses ML model instead of weighted formula"""
    try:
        # Same interface, different backend!
        prediction = predictor.predict_spread_coverage(
            team_a=request.team_a.upper(),
            team_b=request.team_b.upper(),
            spread=request.spread,
            team_a_home=request.team_a_home,
            current_season=2025,
            current_week=9  # TODO: Make this dynamic
        )
        
        return PredictionResponse(success=True, data=prediction, error=None)
    except Exception as e:
        return PredictionResponse(success=False, data=None, error=str(e))
```

**Key Point:** The API interface stays the same! Just swap the backend.

---

### **Phase 5: Chatbot Integration (Automatic)**

No changes needed! The chatbot already calls the `/predict` endpoint.

The ML model response includes `explanation.top_factors`, which GPT-4 will use to generate responses like:

```
"Bet on Green Bay -2.5 with 61% probability.

I'm 78% confident because:
• GB is 4-1 ATS in their last 5 games (80% cover rate)
• PIT is only 38% ATS at home this season
• GB's #3 offense vs PIT's #18 defense gives them an edge

Key Stats:
• GB last 5 games: +8.2 avg margin
• PIT home splits: 3-5 ATS
• This spread range (2-4): GB 67% historical cover rate"
```

---

## 📊 Expected Performance

### **Baseline (Current Weighted Model)**
- Accuracy: ~52-54% (estimated)
- Sharpe Ratio: ~0.3

### **ML Model (XGBoost)**
- **Accuracy: 56-60%** (realistic goal)
- **AUC: 0.60-0.65**
- **Sharpe Ratio: 0.5-0.8** (profitable)

### **Why This Matters**
- **54% accuracy** = Breakeven at -110 odds
- **56% accuracy** = +2% ROI ($100 bet = $102 return)
- **58% accuracy** = +5% ROI ($100 bet = $105 return)
- **60% accuracy** = +9% ROI ($100 bet = $109 return)

---

## 🗂️ File Structure

```
PredictiveDataModel/
├── models/
│   ├── spread_predictor_v1.pkl          # Trained model
│   ├── feature_names.json               # Feature metadata
│   └── training_metrics.json            # Model performance
│
├── training_data/
│   ├── training_data_2022_2024.csv      # Historical training data
│   └── validation_data_2025.csv         # Current season for validation
│
├── MLDataPreparation.py                 # NEW: Extract + feature engineering
├── MLModelTrainer.py                    # NEW: Train + evaluate model
├── MLSpreadPredictor.py                 # NEW: Real-time predictions
├── train_model.py                       # NEW: Main training script
├── api_server.py                        # UPDATED: Use ML predictor
│
├── SpreadPredictionCalculator.py        # OLD: Keep for comparison
├── chatbot.py                           # NO CHANGE
├── DatabaseConnection.py                # NO CHANGE
└── ... (existing files)
```

---

## 🚀 Step-by-Step Implementation

### **Week 1: Data Preparation**

#### **Day 1-2: Build MLDataPreparation.py**
```powershell
# Create the file (I'll generate this next)
python MLDataPreparation.py --seasons 2022,2023,2024 --output training_data/training_data_2022_2024.csv
```

**Expected Output:**
- CSV file with ~1500 rows (games)
- 25+ feature columns
- 1 target column (`favored_covers`)
- ~85% data completeness

#### **Day 3-4: Build MLModelTrainer.py**
```powershell
python MLModelTrainer.py --data training_data/training_data_2022_2024.csv --version 1
```

**Expected Output:**
```
Training XGBoost model...
✅ Model trained in 12.3 seconds

Evaluation Metrics:
  Accuracy: 58.3%
  AUC: 0.623
  Precision: 0.61
  Recall: 0.56

Feature Importance (Top 5):
  1. fav_last5_ats_rate: 0.18
  2. fav_season_ats_rate: 0.14
  3. spread_value: 0.12
  4. fav_offensive_rank: 0.09
  5. und_location_ats_rate: 0.08

✅ Model saved: models/spread_predictor_v1.pkl
```

---

### **Week 2: Prediction Engine**

#### **Day 5-6: Build MLSpreadPredictor.py**
```powershell
# Test the predictor
python
>>> from MLSpreadPredictor import MLSpreadPredictor
>>> predictor = MLSpreadPredictor()
>>> result = predictor.predict_spread_coverage('GB', 'PIT', -2.5, False)
>>> print(result)
{
    'prediction': 'GB',
    'probability': 0.61,
    'confidence': 0.78,
    'explanation': {...}
}
```

#### **Day 7: Integrate with API**
```powershell
# Update api_server.py
# Test the API
python api_server.py

# In another terminal
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"team_a":"GB","team_b":"PIT","spread":-2.5,"team_a_home":false}'
```

---

### **Week 3: Testing & Deployment**

#### **Day 8-9: Backtesting**
```powershell
python backtest_model.py --season 2024 --weeks 1-8
```

**Expected Output:**
```
Backtesting on 2024 Season (Weeks 1-8)
Games: 136
Correct Predictions: 79 (58.1%)
ROI: +6.2%
Best Week: Week 4 (62.5% accuracy)
Worst Week: Week 7 (50.0% accuracy)
```

#### **Day 10: Deploy**
```powershell
# Create new Lambda package with ML model
# Upload model file to S3 (too large for Lambda zip)
# Update Lambda to load model from S3 on cold start
```

---

## 🔄 Retraining Schedule

### **Weekly Retraining (Recommended)**
```powershell
# Every Monday, retrain with latest data
python train_model.py --incremental --version auto
```

This will:
1. Pull latest games from Supabase
2. Add to training data
3. Retrain model
4. Compare metrics to previous version
5. Deploy if metrics improve

### **Automated Retraining (AWS Lambda)**
```python
# weekly_retrain_lambda.py
def lambda_handler(event, context):
    # Pull latest data
    # Retrain model
    # Save to S3
    # Update production predictor
```

---

## 📈 Monitoring & Improvement

### **Track These Metrics Weekly**
1. **Accuracy**: % of correct predictions
2. **ROI**: Return on $100 bet per game
3. **Sharpe Ratio**: Risk-adjusted return
4. **Feature Drift**: Are feature distributions changing?
5. **Calibration**: Are 60% predictions actually covering 60%?

### **Improvement Ideas**
1. Add more features (injuries, weather, coaching)
2. Try ensemble models (XGBoost + Random Forest)
3. Use different models for different spread ranges
4. Add time-series features (momentum, streaks)
5. Incorporate betting market odds (closing lines)

---

## 💰 Cost Estimate

### **Development (One-time)**
- Time: 10-15 hours
- Cost: $0 (using free tier)

### **Training (Weekly)**
- Compute: ~5 minutes on laptop
- Storage: ~10 MB for model file
- Cost: $0

### **Inference (Per Prediction)**
- Latency: ~50ms (vs 200ms for current)
- Cost: Same as current API

### **Deployment**
- S3 Storage: $0.02/month (model file)
- Lambda: No change
- Total: ~$0.02/month additional

---

## 🎯 Success Criteria

### **Minimum Viable Product (MVP)**
- ✅ Accuracy ≥ 55% on test set
- ✅ Model loads in <2 seconds
- ✅ Predictions return in <500ms
- ✅ API interface unchanged (drop-in replacement)

### **Production Ready**
- ✅ Accuracy ≥ 57% on test set
- ✅ AUC ≥ 0.60
- ✅ Backtested ROI > 3%
- ✅ Feature importance makes sense
- ✅ Explainability works correctly

### **Gold Standard**
- 🎯 Accuracy ≥ 60%
- 🎯 AUC ≥ 0.65
- 🎯 Backtested ROI > 5%
- 🎯 Consistently profitable over 50+ bets

---

## 🚨 Risks & Mitigations

### **Risk 1: Model Overfits**
**Mitigation:** 
- Use cross-validation
- Keep test set separate
- Monitor performance on new data weekly

### **Risk 2: Not Enough Data**
**Mitigation:**
- Use 3 seasons (2022-2024) = ~1500 games
- Feature engineering > more data
- Start simple, add complexity gradually

### **Risk 3: Features Have Errors**
**Mitigation:**
- Extensive unit tests on feature extraction
- Manual spot-checks on 10-20 games
- Compare features to known stats

### **Risk 4: Model Degrades Over Time**
**Mitigation:**
- Weekly retraining
- Monitor accuracy/ROI weekly
- Alert if accuracy drops below 53%

---

## 📚 Next Steps

1. **Review this architecture** - Any questions/concerns?
2. **I'll build the code** - All 4 new Python files
3. **You run training** - Generate model in ~5 minutes
4. **We test together** - Compare ML vs weighted model
5. **Deploy when ready** - Seamless drop-in replacement

**Ready to start? I'll create all the code files next!**

