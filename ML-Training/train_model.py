"""
Train XGBoost Model for NFL Spread Prediction

What this does (like you're 5):
  1. Opens the CSV (our recipe book of past games)
  2. Splits it: 2022-2023 = study material, 2024 = the test
  3. Tells XGBoost: "learn what makes the home team win by X points"
  4. Checks how close the guesses are on 2024 games it never saw
  5. Saves the trained brain to a file we can deploy

Why time-based split?
  You can't study with tomorrow's answers. If we randomly mixed
  2024 games into training, the model would "cheat" by learning
  patterns that only exist because it saw the future.
"""

import os
import pandas as pd
import numpy as np
import xgboost as xgb
import joblib
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. LOAD DATA
#    Read the CSV that generate_training_data.py created.
# ---------------------------------------------------------------------------

def load_data(path='training_data.csv'):
    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df)} rows, {len(df.columns)} columns")
    return df


# ---------------------------------------------------------------------------
# 2. PICK FEATURES & TARGET
#
#    FEATURES = the inputs the model looks at to make a prediction.
#    TARGET   = what we want the model to predict.
#
#    We predict ACTUAL MARGIN (home_score - away_score).
#    Then at prediction time we compare our predicted margin to the
#    Vegas spread to decide: does the home team cover?
#
#    We DROP metadata columns (game_id, team names, scores) because:
#      - game_id is just a label, not a pattern
#      - team names are strings, not numbers
#      - scores ARE the answer -- if we gave them to the model it
#        would just memorize "home_score - away_score" and learn nothing
# ---------------------------------------------------------------------------

METADATA_COLS = [
    'game_id', 'season', 'week',
    'home_team', 'away_team',
    'home_score', 'away_score',
    'actual_margin', 'ats_result',
]

TARGET = 'actual_margin'


def get_feature_columns(df):
    return [c for c in df.columns if c not in METADATA_COLS]


# ---------------------------------------------------------------------------
# 3. TIME-BASED SPLIT
#
#    Train on 2022 + 2023.  Test on 2024.
#    This simulates reality: you only know the past when predicting.
# ---------------------------------------------------------------------------

def split_data(df):
    train = df[df['season'] == 2023].copy()
    test  = df[df['season'] == 2024].copy()

    features = get_feature_columns(df)

    X_train = train[features]
    y_train = train[TARGET]
    X_test  = test[features]
    y_test  = test[TARGET]

    logger.info(f"Train: {len(X_train)} games (2023, using 2022 team features)")
    logger.info(f"Test:  {len(X_test)} games (2024)")
    logger.info(f"Features: {len(features)}")

    return X_train, y_train, X_test, y_test, test


# ---------------------------------------------------------------------------
# 4. TRAIN XGBOOST
#
#    XGBoost builds decision trees one at a time. Each new tree tries to
#    fix the mistakes the previous trees made. Think of it like:
#      Tree 1: "teams that score more PPG usually win" (rough guess)
#      Tree 2: "but if the defense is bad, subtract some points"
#      Tree 3: "division games are closer than expected"
#      ...500 trees later: pretty good predictions.
#
#    KEY PARAMETERS:
#      n_estimators    = how many trees to build (more = smarter but slower)
#      max_depth       = how complex each tree can be (too high = memorizes)
#      learning_rate   = how much each tree is allowed to change the answer
#                        (lower = learns slowly but more accurately)
#      subsample       = only show each tree 80% of the data (prevents memorizing)
#      early_stopping  = stop adding trees if we're not improving anymore
# ---------------------------------------------------------------------------

def train_model(X_train, y_train, X_test, y_test):
    model = xgb.XGBRegressor(
        n_estimators=500,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=1.0,
        reg_lambda=1.0,
        random_state=42,
        early_stopping_rounds=50,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_train, y_train), (X_test, y_test)],
        verbose=50,
    )

    logger.info(f"Best iteration: {model.best_iteration}")
    return model


# ---------------------------------------------------------------------------
# 5. EVALUATE
#
#    Three things we care about:
#
#    MAE  = Mean Absolute Error. On average, how many points off are we?
#           Example: MAE of 10 means we're typically wrong by 10 points.
#
#    RMSE = Root Mean Squared Error. Like MAE but punishes big misses more.
#           If you're off by 3 on most games but off by 30 on one,
#           RMSE will be much higher than MAE.
#
#    ATS ACCURACY = The money metric. For each game:
#           1. Model predicts home team wins by X
#           2. Vegas says home team wins by Y (the spread)
#           3. If model says X > Y and the home team actually DID win by
#              more than Y, that's a correct ATS pick.
#           Above 52.4% = profitable (covers the vig/juice).
#           Above 55% = very good.
#           Above 60% = you're probably overfitting or lying.
# ---------------------------------------------------------------------------

def evaluate(model, X_test, y_test, test_df):
    preds = model.predict(X_test)

    mae  = np.mean(np.abs(preds - y_test))
    rmse = np.sqrt(np.mean((preds - y_test) ** 2))

    spread = test_df['spread_line'].values
    actual = y_test.values

    # ATS: did model and reality agree on which side covers?
    model_pick_home_covers = preds > spread
    actual_home_covered    = actual > spread
    ats_correct = (model_pick_home_covers == actual_home_covered).sum()
    ats_total   = len(actual)
    ats_acc     = ats_correct / ats_total

    logger.info("=" * 60)
    logger.info("MODEL EVALUATION (2024 season)")
    logger.info("=" * 60)
    logger.info(f"  MAE:          {mae:.2f} points")
    logger.info(f"  RMSE:         {rmse:.2f} points")
    logger.info(f"  ATS Accuracy: {ats_correct}/{ats_total} = {ats_acc:.1%}")
    logger.info(f"  Profitable?   {'YES' if ats_acc > 0.524 else 'NO'} (need >52.4%)")

    return {'mae': mae, 'rmse': rmse, 'ats_accuracy': ats_acc, 'ats_correct': int(ats_correct), 'ats_total': ats_total}


# ---------------------------------------------------------------------------
# 6. FEATURE IMPORTANCE
#
#    XGBoost tells us which columns it leaned on most.
#    If "ppg_diff" is #1, it means the gap in scoring between
#    the two teams was the strongest signal for predicting margins.
#    If a feature has near-zero importance, it's noise -- we can drop it.
# ---------------------------------------------------------------------------

def show_feature_importance(model, feature_names, top_n=20):
    importance = model.feature_importances_
    fi = pd.DataFrame({'feature': feature_names, 'importance': importance})
    fi = fi.sort_values('importance', ascending=False)

    logger.info(f"\nTop {top_n} features:")
    for _, row in fi.head(top_n).iterrows():
        bar = '#' * int(row['importance'] * 200)
        logger.info(f"  {row['feature']:30s} {row['importance']:.4f}  {bar}")

    return fi


# ---------------------------------------------------------------------------
# 7. SAVE MODEL
#
#    Two formats:
#      .json  = XGBoost native (smaller, loads faster in Lambda)
#      .pkl   = Python pickle (works with joblib, more flexible)
#    We also save the feature list so the prediction Lambda knows
#    which columns to provide, in which order.
# ---------------------------------------------------------------------------

def save_model(model, feature_names, metrics, feature_importance):
    model_dir = os.path.join(os.path.dirname(__file__), 'models')
    os.makedirs(model_dir, exist_ok=True)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    model_path = os.path.join(model_dir, f'nfl_spread_model_{ts}.json')
    model.save_model(model_path)
    logger.info(f"Model saved: {model_path}")

    latest_path = os.path.join(model_dir, 'nfl_spread_model_latest.json')
    model.save_model(latest_path)

    feat_path = os.path.join(model_dir, 'feature_names.json')
    with open(feat_path, 'w') as f:
        json.dump(feature_names, f, indent=2)

    metrics_path = os.path.join(model_dir, 'metrics.json')
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2, default=str)

    fi_path = os.path.join(model_dir, 'feature_importance.csv')
    feature_importance.to_csv(fi_path, index=False)

    logger.info(f"All artifacts saved to {model_dir}/")
    return model_path


# ---------------------------------------------------------------------------
# 8. MAIN PIPELINE  --  Run everything in order
# ---------------------------------------------------------------------------

def main():
    print("\n" + "=" * 60)
    print("NFL SPREAD PREDICTION - XGBOOST TRAINING")
    print("=" * 60 + "\n")

    data_path = os.path.join(os.path.dirname(__file__), 'training_data.csv')
    df = load_data(data_path)

    X_train, y_train, X_test, y_test, test_df = split_data(df)

    model = train_model(X_train, y_train, X_test, y_test)

    metrics = evaluate(model, X_test, y_test, test_df)

    fi = show_feature_importance(model, get_feature_columns(df))

    save_model(model, get_feature_columns(df), metrics, fi)

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"  MAE:          {metrics['mae']:.2f} pts")
    print(f"  ATS Accuracy: {metrics['ats_accuracy']:.1%}")
    print(f"\nNext: deploy model to S3 + update XGBoostPredictionLambda")


if __name__ == "__main__":
    main()
