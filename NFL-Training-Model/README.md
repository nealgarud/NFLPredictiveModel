# NFL Spread Prediction - Training Data Preparation

This module prepares training data for the NFL spread prediction XGBoost model by extracting features from historical game data.

## Overview

The `prepare_training_data.py` script:
1. Queries completed regular season games (2024-2025) from Supabase
2. Calculates 20+ features for each game using existing feature logic
3. Creates target variable (did favorite cover the spread?)
4. Outputs a clean CSV file ready for ML training

## Features Generated

### Team Form (2 features)
- `fav_recent_form`: Favored team's win rate in last 5 games
- `und_recent_form`: Underdog team's win rate in last 5 games

### Situational (3 features)
- `is_divisional`: Boolean flag for division games
- `fav_div_ats`: Favored team's ATS rate in division games
- `und_div_ats`: Underdog team's ATS rate in division games

### Contextual (3 features)
- `fav_bye_week`: Favored team coming off bye week
- `und_bye_week`: Underdog team coming off bye week
- `is_prime_time`: Game is TNF/SNF/MNF
- `spread_magnitude`: Categorized spread (0-3, 3-7, 7-10, 10+)

### Performance (2 features)
- `fav_close_game_perf`: Favored team's ATS in close games (spread < 3)
- `fav_after_loss_perf`: Favored team's ATS after previous loss

### Core (6 features)
- `fav_sit_ats`: Situational ATS (spread range + location)
- `fav_overall_ats`: Overall ATS rate
- `fav_home_away_wr`: Win rate at current location
- `und_sit_ats`: Underdog situational ATS
- `und_overall_ats`: Underdog overall ATS
- `und_home_away_wr`: Underdog win rate at location

### Target Variable
- `target_favorite_covered`: 1 if favorite covered, 0 if not

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your Supabase credentials:

```bash
cp .env.example .env
```

Edit `.env` with your actual database connection details.

### 3. Ensure DatabaseConnection is Accessible

The script imports `DatabaseConnection` from:
```
../PredictiveDataModel/DataIngestionLambda/DatabaseConnection.py
```

Make sure this path is correct relative to the script location.

## Usage

### Basic Usage

```bash
python prepare_training_data.py
```

This will:
- Query games from 2024 and 2025 seasons
- Generate features for each game
- Save output to `training_data.csv`

### Programmatic Usage

```python
from prepare_training_data import TrainingDataPreparator

# Initialize
preparator = TrainingDataPreparator()

# Generate training data
df = preparator.prepare_training_data(
    seasons=[2024, 2025],
    output_file='my_training_data.csv'
)

print(f"Generated {len(df)} training samples")
```

## Output Format

CSV file with columns:

```
game_id, season, week, gameday, home_team, away_team, spread_line,
favored_team, underdog_team, favored_home, spread_magnitude,
fav_recent_form, und_recent_form, is_divisional, fav_div_ats, und_div_ats,
fav_bye_week, und_bye_week, is_prime_time,
fav_close_game_perf, fav_after_loss_perf,
fav_sit_ats, fav_overall_ats, fav_home_away_wr,
und_sit_ats, und_overall_ats, und_home_away_wr,
target_favorite_covered
```

## Data Leakage Prevention

**CRITICAL**: The script prevents data leakage by:
- Only using games BEFORE the current game when calculating features
- Using `gameday < :current_gameday` filters in all queries
- Never including the current game in any rolling calculations

This ensures the model learns from truly historical data only.

## EC2 Deployment

### Transfer Files

```bash
# SCP the entire folder to EC2
scp -i your-key.pem -r NFL-Training-Model ec2-user@your-instance:/home/ec2-user/

# SSH into EC2
ssh -i your-key.pem ec2-user@your-instance
```

### Install Python Dependencies

```bash
cd NFL-Training-Model
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Set Environment Variables

```bash
# Edit .env file
nano .env

# Or export directly
export SUPABASE_DB_HOST=db.xxx.supabase.co
export SUPABASE_DB_PASSWORD=your_password
```

### Run Training Data Preparation

```bash
python prepare_training_data.py
```

### Expected Output

```
2026-01-21 10:00:00 - INFO - ✅ Database connection established
2026-01-21 10:00:01 - INFO - 🏈 Starting training data preparation for seasons: [2024, 2025]
2026-01-21 10:00:02 - INFO - ✅ Retrieved 544 completed games
2026-01-21 10:00:02 - INFO - Processing game 50/544...
2026-01-21 10:00:05 - INFO - Processing game 100/544...
...
2026-01-21 10:05:30 - INFO - ✅ Created DataFrame with 540 rows and 28 columns
2026-01-21 10:05:30 - INFO - 🧹 Filtered out 4 rows with missing features
2026-01-21 10:05:30 - INFO - 💾 Training data saved to: training_data.csv
2026-01-21 10:05:30 - INFO - ================================================================================
2026-01-21 10:05:30 - INFO - 📊 TRAINING DATA SUMMARY
2026-01-21 10:05:30 - INFO - ================================================================================
2026-01-21 10:05:30 - INFO - 
2026-01-21 10:05:30 - INFO - 📈 Dataset Size:
2026-01-21 10:05:30 - INFO -   Total games: 540
2026-01-21 10:05:30 - INFO -   Total features: 20
2026-01-21 10:05:30 - INFO - 
2026-01-21 10:05:30 - INFO - ⚖️ Target Distribution:
2026-01-21 10:05:30 - INFO -   Favorite covered (1): 270 (50.0%)
2026-01-21 10:05:30 - INFO -   Favorite didn't cover (0): 270 (50.0%)
2026-01-21 10:05:30 - INFO - ✅ Success! Training data saved with 540 samples
```

## Next Steps

After generating `training_data.csv`:

1. **Exploratory Data Analysis**: Analyze feature distributions and correlations
2. **Feature Engineering**: Create interaction features if needed
3. **Model Training**: Train XGBoost model with hyperparameter tuning
4. **Model Evaluation**: Test on holdout set, analyze feature importance
5. **Deploy**: Replace manual weights in SpreadPredictionCalculator with ML predictions

## Future Enhancements

### Player Data Features (TODO)
When QB stats and injury data are deployed:

```python
# Add to _calculate_game_features method:
features['fav_qb_rating'] = self._get_qb_rating(favored_team, game['gameday'])
features['und_qb_rating'] = self._get_qb_rating(underdog_team, game['gameday'])
features['fav_key_injuries'] = self._count_key_injuries(favored_team, game['gameday'])
features['und_key_injuries'] = self._count_key_injuries(underdog_team, game['gameday'])
```

### Weather Data
- Temperature, wind speed, precipitation
- Indoor vs outdoor venue

### Advanced Metrics
- DVOA (Defense-adjusted Value Over Average)
- Offensive/defensive efficiency ratings
- Rest days (not just bye weeks)

## Troubleshooting

### Issue: "No module named DatabaseConnection"

**Solution**: Ensure the path to DatabaseConnection is correct:
```python
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'PredictiveDataModel', 'DataIngestionLambda'))
```

### Issue: "Connection timeout"

**Solution**: 
1. Check EC2 security group allows outbound to Supabase (port 5432)
2. Verify .env credentials are correct
3. Use connection pooler port 6543 if on Lambda/serverless

### Issue: "Too many rows with missing values"

**Solution**: 
- Early season games may lack sufficient history
- Consider filtering to games after week 6
- Adjust `min_periods` in rolling calculations

## Performance

- Processing ~500 games takes approximately **5-10 minutes**
- Memory usage: ~500MB
- Database queries: ~6,000 (parallelized per game)

To optimize:
- Cache team statistics between games
- Use batch queries where possible
- Consider multiprocessing for feature calculation

## License

Internal use only - NFL Predictive Model Project

## Contact

For questions or issues, contact: Neal





