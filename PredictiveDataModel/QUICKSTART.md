# Quick Start - Player Impact Lambda

## 🎯 What You're Building

Two Lambdas that work together:
1. **HistoricalGamesBatchProcessor** - Builds ML training data from all past games
2. **Your existing Prediction Lambda** - Uses that data to predict spreads

---

## ⚡ Deploy in 3 Commands

```powershell
# 1. Build package
cd "C:\Users\nealg\Nfl Predictive Model\NFLPredictiveModel\PredictiveDataModel"
.\verify_and_fix_package.ps1

# 2. Create Lambda
aws lambda create-function `
    --function-name HistoricalGamesBatchProcessor `
    --runtime python3.11 `
    --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-exec-role `
    --handler HistoricalGamesBatchProcessor.lambda_handler `
    --zip-file fileb://playerimpact-lambda-light.zip `
    --timeout 900 `
    --memory-size 1024

# 3. Add environment variables
aws lambda update-function-configuration `
    --function-name HistoricalGamesBatchProcessor `
    --environment Variables="{SPORTRADAR_API_KEY=bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm,SUPABASE_DB_HOST=your_host,SUPABASE_DB_PASSWORD=your_password,SUPABASE_DB_NAME=postgres,SUPABASE_DB_USER=postgres,SUPABASE_DB_PORT=5432}"
```

---

## 🧪 Test with 10 Games First

AWS Lambda Console → Test with this JSON:

```json
{
  "mode": "full",
  "seasons": [2024],
  "max_games": 10
}
```

**Expected output:**
```
✓ Loaded 1,500+ player ratings from 2024.csv
✓ Found 272 games for season 2024
✓ Limited to 10 games for testing
✓ Stored game abc123... - Home: 2 out, Away: 3 out
...
✓ Total games processed: 10
```

---

## 🚀 Run Full Historical Collection

Once test works, run all games:

```json
{
  "mode": "full",
  "seasons": [2022, 2023, 2024]
}
```

This processes ~500-600 games → stores in Supabase

**Takes:** ~30-45 minutes  
**Cost:** ~$0.02

---

## ✅ What Gets Stored in Supabase

For EACH game + team:
- `game_id`, `team_id`, `season`, `week`
- `replacement_adjusted_score` - injury impact
- `inactive_starter_count` - how many starters out
- `qb1_active`, `rb1_active`, etc. - key position flags
- Tier breakdowns (tier_1_out through tier_5_out)

**~1,000-1,200 records total** (2 per game)

---

## 🔗 Integrate with Prediction Lambda

See `COMPLETE_WORKFLOW.md` for full integration guide.

**Quick version:**
1. Add `player_impact_integration.py` to your prediction Lambda
2. Query Supabase for injury data
3. Add as 4th factor (15% weight) to your existing formula

---

## 📊 Verify Data

Query Supabase:

```sql
SELECT COUNT(*) FROM injury_impact;
-- Should see ~1,000-1,200 records

SELECT team_id, AVG(replacement_adjusted_score) as avg_impact
FROM injury_impact
WHERE season = 2024
GROUP BY team_id
ORDER BY avg_impact DESC
LIMIT 10;
-- See which teams had worst injuries
```

---

## 🎯 You're Done!

Now you have:
- ✅ Historical injury data for ALL games 2022-2024
- ✅ Player impact calculations based on who actually played
- ✅ Data ready for ML training
- ✅ Ready to integrate into predictions

**Next:** Train your ML model to see how player impact affects spread outcomes! 🚀

