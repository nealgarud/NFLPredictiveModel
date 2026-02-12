```markdown
# Complete Player Impact Workflow - ML Training & Prediction

## 🎯 Overview

You have TWO Lambdas working together:

### Lambda 1: Historical Data Collection (One-Time / Weekly)
**Purpose:** Build ML training dataset  
**Name:** `HistoricalGamesBatchProcessor`  
**What it does:**
1. Processes ALL games from 2022-2025
2. For each game, fetches active roster from Sportradar
3. Calculates player impact based on who actually played
4. Stores in Supabase with game outcomes

### Lambda 2: Spread Prediction (Real-Time)
**Purpose:** Predict spread coverage using player impact  
**Name:** `SpreadPredictionCalculator` (your existing Lambda)  
**What it does:**
1. Takes current matchup
2. Queries Supabase for injury impact data
3. Combines with ATS, home/away, situational factors
4. Predicts spread coverage

---

## 📊 Complete Data Flow

```
Step 1: Build Historical Dataset (Lambda 1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sportradar API (all games 2022-2025)
   ↓ game_id, teams, outcomes
S3: 2022.csv, 2023.csv, 2024.csv (player ratings)
   ↓ Madden ratings
Calculate: Who played? What was their impact?
   ↓
Supabase: injury_impact table
   ├── game_id
   ├── team_id  
   ├── replacement_adjusted_score
   ├── inactive_starter_count
   ├── qb1_active, rb1_active, etc.
   └── game outcome / spread result

Step 2: Use Data for Predictions (Lambda 2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Input: BAL vs BUF, spread -3.5
   ↓
Query Supabase: Historical injury impact for BAL & BUF
   ↓
Calculate: Current impact differential
   ↓
Combine with existing factors:
   - 35% Situational ATS
   - 25% Overall ATS  
   - 25% Home/Away
   - 15% Player Impact ← NEW!
   ↓
Output: Pick BAL -3.5, 68% confidence
```

---

## 🚀 Deployment Steps

### Step 1: Deploy Historical Data Collection Lambda

```powershell
cd "C:\Users\nealg\Nfl Predictive Model\NFLPredictiveModel\PredictiveDataModel"

# Update verify script to include new handler
# Then rebuild package
.\verify_and_fix_package.ps1

# Create Lambda function
aws lambda create-function `
    --function-name HistoricalGamesBatchProcessor `
    --runtime python3.11 `
    --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-s3-supabase-role `
    --handler HistoricalGamesBatchProcessor.lambda_handler `
    --zip-file fileb://playerimpact-lambda-light.zip `
    --timeout 900 `
    --memory-size 1024 `
    --environment Variables="{SPORTRADAR_API_KEY=bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm,SUPABASE_DB_HOST=your_host,SUPABASE_DB_PASSWORD=your_password}"
```

### Step 2: Run Historical Data Collection (One Time)

**Test with limited games first:**
```json
{
  "mode": "full",
  "seasons": [2024],
  "max_games": 10
}
```

**Then run full batch:**
```json
{
  "mode": "full",
  "seasons": [2022, 2023, 2024]
}
```

**This will:**
- Process ~500-600 games
- Take ~30-45 minutes
- Store all data in Supabase

### Step 3: Verify Data in Supabase

```sql
-- Check total games processed
SELECT COUNT(*) FROM injury_impact;

-- Check average injury impact by team
SELECT team_id, 
       AVG(replacement_adjusted_score) as avg_impact,
       AVG(inactive_starter_count) as avg_starters_out
FROM injury_impact
WHERE season = 2024
GROUP BY team_id
ORDER BY avg_impact DESC;

-- Check key position impacts
SELECT 
    season,
    SUM(CASE WHEN qb1_active = false THEN 1 ELSE 0 END) as qb1_inactive_games,
    SUM(CASE WHEN rb1_active = false THEN 1 ELSE 0 END) as rb1_inactive_games
FROM injury_impact
GROUP BY season;
```

### Step 4: Integrate with Prediction Lambda

Add to your existing `SpreadPredictionCalculator.py`:

```python
from player_impact_integration import PlayerImpactIntegration

class SpreadPredictionCalculator:
    # Update weights
    SITUATIONAL_ATS_WEIGHT = 0.35  # Reduced from 40%
    OVERALL_ATS_WEIGHT = 0.25      # Reduced from 30%
    HOME_AWAY_WEIGHT = 0.25        # Reduced from 30%
    PLAYER_IMPACT_WEIGHT = 0.15    # NEW!
    
    def __init__(self):
        self.db = DatabaseConnection()
        self.player_impact = PlayerImpactIntegration()  # NEW!
    
    def predict_spread_coverage(self, team_a, team_b, spread, team_a_home, seasons):
        # ... your existing code ...
        
        # Add player impact
        player_impact_score = self.player_impact.get_player_impact_for_matchup(
            team_a, team_b
        )
        
        # Combine all factors
        final_score = (
            situational_ats * self.SITUATIONAL_ATS_WEIGHT +
            overall_ats * self.OVERALL_ATS_WEIGHT +
            home_away * self.HOME_AWAY_WEIGHT +
            player_impact_score * self.PLAYER_IMPACT_WEIGHT  # NEW!
        )
        
        # ... rest of your logic ...
```

---

## 📋 S3 Bucket Structure

```
s3://player-data-nfl-predictive-model/
├── 2022.csv    ← Player Madden ratings for 2022
├── 2023.csv    ← Player Madden ratings for 2023
├── 2024.csv    ← Player Madden ratings for 2024
```

**CSV Format:**
```csv
player_id,player_name,overallrating,position,team
player_123,Patrick Mahomes,99,QB,KC
player_456,Josh Allen,95,QB,BUF
```

---

## 🗄️ Supabase Schema

```sql
CREATE TABLE injury_impact (
    id SERIAL PRIMARY KEY,
    game_id VARCHAR(255),
    team_id VARCHAR(255),
    season INTEGER,
    week INTEGER,
    season_type VARCHAR(10),
    
    -- Impact scores
    total_injury_score DECIMAL(10,4),
    replacement_adjusted_score DECIMAL(10,4),
    inactive_starter_count INTEGER,
    
    -- Tier breakdowns
    tier_1_out INTEGER,
    tier_2_out INTEGER,
    tier_3_out INTEGER,
    tier_4_out INTEGER,
    tier_5_out INTEGER,
    
    -- Key position flags
    qb1_active BOOLEAN,
    rb1_active BOOLEAN,
    wr1_active BOOLEAN,
    edge1_active BOOLEAN,
    cb1_active BOOLEAN,
    lt_active BOOLEAN,
    s1_active BOOLEAN,
    
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, team_id)
);
```

---

## 🧪 Testing

### Test Historical Collection (Small Batch)
```json
{
  "mode": "full",
  "seasons": [2024],
  "weeks": [1, 2],
  "max_games": 20
}
```

### Test Prediction with Player Impact
```json
{
  "team_a": "KC",
  "team_b": "BUF",
  "spread": -2.5,
  "team_a_home": true,
  "seasons": [2024]
}
```

---

## 📊 Expected Results

After running historical collection, you should have:

- **~500-600 game records** in Supabase
- **1000-1200 team-game records** (2 per game)
- **Data for ML training** on how injuries affect spread outcomes

**Sample Query Results:**
```
Teams with worst injury impact (2024):
1. Team A: avg_impact = 3.2, avg_starters_out = 4.5
2. Team B: avg_impact = 2.8, avg_starters_out = 3.8

QB1 inactive games: 45 (high impact)
RB1 inactive games: 120 (moderate impact)
```

---

## ⚙️ Configuration

### Environment Variables

**Both Lambdas:**
```
SPORTRADAR_API_KEY=bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm
SUPABASE_DB_HOST=db.xxx.supabase.co
SUPABASE_DB_PASSWORD=your_password
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PORT=5432
```

### IAM Permissions

**Lambda Role needs:**
- S3 read access to `player-data-nfl-predictive-model`
- Internet access to call Sportradar API
- VPC access if Supabase is in private subnet

---

## 🎯 Next Steps

1. ✅ Deploy `HistoricalGamesBatchProcessor` Lambda
2. ✅ Run historical data collection (test with 10 games first)
3. ✅ Verify data in Supabase
4. ✅ Integrate `PlayerImpactIntegration` into prediction Lambda
5. ✅ Test predictions with player impact factor
6. ✅ Train ML model on Supabase data
7. ✅ Schedule weekly updates for new games

---

## 💡 Tips

- **Start small:** Process 10-20 games first to verify everything works
- **Rate limits:** Sportradar trial has 1 req/sec limit (built-in throttling)
- **Costs:** ~500 games = ~$0.02 Lambda + negligible S3/Supabase
- **Updates:** Schedule Lambda weekly to process new games
- **ML Training:** Export Supabase data to train your model

---

## 🔄 Weekly Update Schedule

After initial historical load, schedule Lambda weekly:

```python
# CloudWatch Event Rule
schedule(rate(7 days))

# Lambda event
{
  "mode": "incremental",
  "seasons": [2024],
  "weeks": "current"  # Only process latest week
}
```

This keeps your training data current! 🚀
```

