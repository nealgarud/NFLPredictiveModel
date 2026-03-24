"""
Train XGBoost Model for NFL Spread Prediction
Replaces manual weights in SpreadPredictionCalculator.py

This script:
1. Loads training_data.csv
2. Splits into train/validation/test sets
3. Trains XGBoost classifier
4. Evaluates performance
5. Saves model for deployment
"""

import pandas as pd
import numpy as np
import xgboost as xgb
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split  # noqa: F401 (kept for any downstream use)
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
import joblib
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class XGBoostTrainer:
    """Train and evaluate XGBoost model for spread prediction"""
    
    def __init__(self, data_file='training_data.csv'):
        """Initialize trainer with training data"""
        logger.info(f"Loading training data from {data_file}...")
        self.df = pd.read_csv(data_file)
        logger.info(f"✓ Loaded {len(self.df)} samples")
        
        self.model = None
        self.feature_names = None
        self.metrics = {}
    
    def prepare_data(self, train_seasons=(2022, 2023), test_season=2024):
        """
        Prepare train/validation/test splits using a time-based split.

        Train set : all games from train_seasons (2022 + 2023)
        Validation: 15% random sample held out from the train set
        Test set  : all games from test_season (2024)

        This mirrors real deployment — the model never sees future seasons
        during training, and the test set is a fixed "answer key" that
        stays identical across v1.0, v2.0, etc. for fair comparison.
        """
        logger.info(
            "Preparing time-based split: train=%s  test=%d",
            list(train_seasons), test_season,
        )

        # Identify feature columns (exclude metadata and target)
        exclude_cols = ['game_id', 'season', 'week', 'home_team', 'away_team',
                        'home_score', 'away_score', 'actual_margin', 'ats_result',
                        'favorite_team', 'underdog_team', 'favorite_covered']
        self.feature_names = [col for col in self.df.columns if col not in exclude_cols]

        logger.info(f"Features ({len(self.feature_names)}): {self.feature_names}")

        train_mask = self.df['season'].isin(train_seasons)
        test_mask  = self.df['season'] == test_season

        train_df = self.df[train_mask].copy()
        test_df  = self.df[test_mask].copy()

        X_all_train = train_df[self.feature_names]
        y_all_train = train_df['favorite_covered']
        X_test      = test_df[self.feature_names]
        y_test      = test_df['favorite_covered']

        # Hold out 15% of the training set as validation (shuffled within train seasons only)
        X_train, X_val, y_train, y_val = train_test_split(
            X_all_train, y_all_train, test_size=0.15, random_state=42, stratify=y_all_train
        )

        logger.info(
            "✓ Train: %d (%s) | Validation: %d (%s) | Test: %d (%d)",
            len(X_train), list(train_seasons),
            len(X_val),   list(train_seasons),
            len(X_test),  test_season,
        )
        logger.info(f"  Train target dist: {y_train.value_counts().to_dict()}")
        logger.info(f"  Val target dist:   {y_val.value_counts().to_dict()}")
        logger.info(f"  Test target dist:  {y_test.value_counts().to_dict()}")

        self.X_train = X_train
        self.X_val   = X_val
        self.X_test  = X_test
        self.y_train = y_train
        self.y_val   = y_val
        self.y_test  = y_test

        return X_train, X_val, X_test, y_train, y_val, y_test
    
    def train_model(self, params=None):
        """
        Train XGBoost classifier
        
        Args:
            params: XGBoost parameters (uses defaults if None)
        """
        logger.info("Training XGBoost model...")
        
        if params is None:
            params = {
                'objective': 'binary:logistic',
                'eval_metric': 'logloss',
                'max_depth': 6,
                'learning_rate': 0.1,
                'n_estimators': 200,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'random_state': 42,
                'scale_pos_weight': 1,  # Adjust if classes imbalanced
                'tree_method': 'hist',
                'device': 'cpu'
            }
        
        logger.info(f"Model parameters: {params}")
        
        self.model = xgb.XGBClassifier(**params)
        
        # Train with early stopping on validation set
        self.model.fit(
            self.X_train, 
            self.y_train,
            eval_set=[(self.X_val, self.y_val)],
            verbose=10
        )
        
        logger.info(f"✓ Model trained ({self.model.n_estimators} trees)")
        
        return self.model
    
    def evaluate_model(self):
        """Evaluate model on validation and test sets"""
        logger.info("\n" + "="*60)
        logger.info("MODEL EVALUATION")
        logger.info("="*60)
        
        # Validation set
        y_val_pred = self.model.predict(self.X_val)
        y_val_proba = self.model.predict_proba(self.X_val)[:, 1]
        
        val_metrics = {
            'accuracy': accuracy_score(self.y_val, y_val_pred),
            'precision': precision_score(self.y_val, y_val_pred),
            'recall': recall_score(self.y_val, y_val_pred),
            'f1': f1_score(self.y_val, y_val_pred),
            'roc_auc': roc_auc_score(self.y_val, y_val_proba)
        }
        
        logger.info("\nVALIDATION SET:")
        for metric, value in val_metrics.items():
            logger.info(f"  {metric.upper()}: {value:.4f}")
        
        # Test set
        y_test_pred = self.model.predict(self.X_test)
        y_test_proba = self.model.predict_proba(self.X_test)[:, 1]
        
        test_metrics = {
            'accuracy': accuracy_score(self.y_test, y_test_pred),
            'precision': precision_score(self.y_test, y_test_pred),
            'recall': recall_score(self.y_test, y_test_pred),
            'f1': f1_score(self.y_test, y_test_pred),
            'roc_auc': roc_auc_score(self.y_test, y_test_proba)
        }
        
        logger.info("\nTEST SET:")
        for metric, value in test_metrics.items():
            logger.info(f"  {metric.upper()}: {value:.4f}")
        
        # Confusion matrix
        cm = confusion_matrix(self.y_test, y_test_pred)
        logger.info(f"\nConfusion Matrix (Test):")
        logger.info(f"  [[TN={cm[0,0]}, FP={cm[0,1]}],")
        logger.info(f"   [FN={cm[1,0]}, TP={cm[1,1]}]]")
        
        self.metrics = {
            'validation': val_metrics,
            'test': test_metrics,
            'confusion_matrix': cm.tolist()
        }
        
        return test_metrics
    
    def get_feature_importance(self, top_n=20):
        """Get and display feature importance"""
        logger.info("\n" + "="*60)
        logger.info("FEATURE IMPORTANCE")
        logger.info("="*60)
        
        importance = self.model.feature_importances_
        feature_importance = pd.DataFrame({
            'feature': self.feature_names,
            'importance': importance
        }).sort_values('importance', ascending=False)
        
        logger.info(f"\nTop {top_n} Most Important Features:")
        for idx, row in feature_importance.head(top_n).iterrows():
            logger.info(f"  {row['feature']:30} {row['importance']:.4f}")
        
        self.feature_importance = feature_importance
        
        return feature_importance
    
    def save_model(self, model_dir='models'):
        """Save trained model and metadata"""
        import os
        os.makedirs(model_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save model
        model_path = os.path.join(model_dir, f'xgboost_spread_model_{timestamp}.pkl')
        joblib.dump(self.model, model_path)
        logger.info(f"✓ Model saved to {model_path}")
        
        # Save feature names
        features_path = os.path.join(model_dir, f'feature_names_{timestamp}.json')
        with open(features_path, 'w') as f:
            json.dump(self.feature_names, f, indent=2)
        logger.info(f"✓ Feature names saved to {features_path}")
        
        # Save metrics
        metrics_path = os.path.join(model_dir, f'model_metrics_{timestamp}.json')
        with open(metrics_path, 'w') as f:
            json.dump(self.metrics, f, indent=2)
        logger.info(f"✓ Metrics saved to {metrics_path}")
        
        # Save feature importance
        importance_path = os.path.join(model_dir, f'feature_importance_{timestamp}.csv')
        self.feature_importance.to_csv(importance_path, index=False)
        logger.info(f"✓ Feature importance saved to {importance_path}")
        
        # Save latest model (for easy loading)
        latest_model_path = os.path.join(model_dir, 'latest_model.pkl')
        joblib.dump(self.model, latest_model_path)
        
        latest_features_path = os.path.join(model_dir, 'latest_features.json')
        with open(latest_features_path, 'w') as f:
            json.dump(self.feature_names, f, indent=2)
        
        logger.info(f"✓ Latest model saved to {model_dir}/latest_model.pkl")
        
        return model_path
    
    def plot_feature_importance(self, top_n=15, save_path='feature_importance.png'):
        """Plot feature importance"""
        plt.figure(figsize=(10, 8))
        top_features = self.feature_importance.head(top_n)
        
        plt.barh(range(len(top_features)), top_features['importance'])
        plt.yticks(range(len(top_features)), top_features['feature'])
        plt.xlabel('Importance')
        plt.title(f'Top {top_n} Most Important Features')
        plt.gca().invert_yaxis()
        plt.tight_layout()
        plt.savefig(save_path)
        logger.info(f"✓ Feature importance plot saved to {save_path}")
        plt.close()
    
    def plot_confusion_matrix(self, save_path='confusion_matrix.png'):
        """Plot confusion matrix"""
        cm = np.array(self.metrics['confusion_matrix'])
        
        plt.figure(figsize=(8, 6))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                    xticklabels=['Underdog', 'Favorite'],
                    yticklabels=['Underdog', 'Favorite'])
        plt.ylabel('Actual')
        plt.xlabel('Predicted')
        plt.title('Confusion Matrix (Test Set)')
        plt.tight_layout()
        plt.savefig(save_path)
        logger.info(f"✓ Confusion matrix saved to {save_path}")
        plt.close()


def main():
    """Main training pipeline"""
    
    print("\n" + "="*60)
    print("XGBOOST NFL SPREAD PREDICTION MODEL - TRAINING")
    print("="*60 + "\n")
    
    # Initialize trainer
    trainer = XGBoostTrainer(data_file='training_data.csv')
    
    # Prepare data — time-based split: train 2023, test 2024
    trainer.prepare_data(train_seasons=(2023,), test_season=2024)
    
    # Train model
    trainer.train_model()
    
    # Evaluate
    test_metrics = trainer.evaluate_model()
    
    # Feature importance
    trainer.get_feature_importance(top_n=20)
    
    # Save model
    model_path = trainer.save_model(model_dir='models')
    
    # Create visualizations
    trainer.plot_feature_importance(save_path='models/feature_importance.png')
    trainer.plot_confusion_matrix(save_path='models/confusion_matrix.png')
    
    print("\n" + "="*60)
    print("✓ TRAINING COMPLETE!")
    print("="*60)
    print(f"\nModel saved to: {model_path}")
    print(f"Test Accuracy: {test_metrics['accuracy']:.4f}")
    print(f"Test ROC-AUC: {test_metrics['roc_auc']:.4f}")
    print("\nNext steps:")
    print("1. Review feature importance and metrics")
    print("2. Deploy model to Lambda (use XGBoostPredictionLambda)")
    print("3. Replace SpreadPredictionCalculator.py")
    print("\n")


if __name__ == "__main__":
    main()

