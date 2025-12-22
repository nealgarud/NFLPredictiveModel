# NFL Spread Prediction Formula - Complete Explanation

## Overview

The `SpreadPredictionCalculator` (used in the ChatbotPredictiveAPI Lambda) predicts which team will cover the spread using a **weighted three-factor model**.

## The Formula

```
Favored_Cover_Probability = 
    (0.40 × Situational_ATS_Normalized) +
    (0.30 × Overall_ATS_Normalized) +
    (0.30 × Home_Away_Win_Rate_Normalized)

Underdog_Cover_Probability = 1 - Favored_Cover_Probability
```

### Weights:
- **Situational ATS**: 40% (most predictive)
- **Overall ATS**: 30% (historical consistency)
- **Home/Away Performance**: 30% (location impact)

## Jets @ Patriots Example (Patriots -5.5)

### Setup:
- **Favored Team**: Patriots (NE) - Home
- **Underdog Team**: Jets (NYJ) - Away
- **Spread**: -5.5 (Patriots favored by 5.5 points)
- **Spread Range**: 4-7 (since 4 < 5.5 ≤ 7)

---

## Factor 1: Situational ATS (40% Weight)

**What it measures**: How teams perform Against The Spread (ATS) in similar situations.

### Queries:
1. **Patriots**: ATS record as home favorite with spread 4-7
   ```sql
   SELECT COUNT(*) as total_games,
          SUM(CASE WHEN spread_line > 0 AND (home_score - away_score) > spread_line 
              THEN 1 ELSE 0 END) as ats_wins
   FROM games
   WHERE season IN (2024, 2025)
     AND home_team = 'NE'
     AND spread_line BETWEEN 4 AND 7
     AND game_type = 'REG'
   ```

2. **Jets**: ATS record as away underdog with spread 4-7
   ```sql
   SELECT COUNT(*) as total_games,
          SUM(CASE WHEN spread_line > 0 AND (away_score - home_score) > -spread_line 
              THEN 1 ELSE 0 END) as ats_wins
   FROM games
   WHERE season IN (2024, 2025)
     AND away_team = 'NYJ'
     AND spread_line BETWEEN 4 AND 7
     AND game_type = 'REG'
   ```

### Calculation:
```
Patriots_ATS_Rate = Patriots_ATS_Wins / Patriots_Total_Games
Jets_ATS_Rate = Jets_ATS_Wins / Jets_Total_Games

# Normalize (so they sum to 1.0)
Total_Rate = Patriots_ATS_Rate + Jets_ATS_Rate
Patriots_Normalized = Patriots_ATS_Rate / Total_Rate
Jets_Normalized = Jets_ATS_Rate / Total_Rate
```

### Example:
- Patriots: 6-4 ATS in this situation = 60% rate
- Jets: 4-6 ATS in this situation = 40% rate
- Normalized: Patriots = 0.60/(0.60+0.40) = **0.60**
- Normalized: Jets = 0.40/(0.60+0.40) = **0.40**

---

## Factor 2: Overall ATS (30% Weight)

**What it measures**: Overall ATS performance across all games (2024-2025).

### Query:
```sql
SELECT team_id, season, games_played, ats_wins, ats_losses, ats_cover_rate
FROM team_rankings
WHERE team_id IN ('NE', 'NYJ')
  AND season IN (2024, 2025)
```

### Calculation:
```
# Weighted average by games played
Patriots_Overall_ATS = SUM(ats_cover_rate × games_played) / SUM(games_played)
Jets_Overall_ATS = SUM(ats_cover_rate × games_played) / SUM(games_played)

# Normalize
Total_Rate = Patriots_Overall_ATS + Jets_Overall_ATS
Patriots_Normalized = Patriots_Overall_ATS / Total_Rate
Jets_Normalized = Jets_Overall_ATS / Total_Rate
```

### Example:
- Patriots: 48% overall ATS
- Jets: 52% overall ATS
- Normalized: Patriots = 0.48/(0.48+0.52) = **0.48**
- Normalized: Jets = 0.52/(0.48+0.52) = **0.52**

---

## Factor 3: Home/Away Performance (30% Weight)

**What it measures**: Win rate based on location (not ATS, just wins).

### Query:
```sql
SELECT team_id, season, home_games, home_wins, away_games, away_wins,
       home_win_rate, away_win_rate
FROM team_rankings
WHERE team_id IN ('NE', 'NYJ')
  AND season IN (2024, 2025)
```

### Calculation:
```
# Patriots at home, Jets away
Patriots_Home_Win_Rate = SUM(home_win_rate × home_games) / SUM(home_games)
Jets_Away_Win_Rate = SUM(away_win_rate × away_games) / SUM(away_games)

# Normalize
Total_Rate = Patriots_Home_Win_Rate + Jets_Away_Win_Rate
Patriots_Normalized = Patriots_Home_Win_Rate / Total_Rate
Jets_Normalized = Jets_Away_Win_Rate / Total_Rate
```

### Example:
- Patriots: 65% home win rate
- Jets: 35% away win rate
- Normalized: Patriots = 0.65/(0.65+0.35) = **0.65**
- Normalized: Jets = 0.35/(0.65+0.35) = **0.35**

---

## Final Calculation

### Patriots Cover Probability:
```
Patriots_Prob = (0.40 × 0.60) + (0.30 × 0.48) + (0.30 × 0.65)
              = 0.240 + 0.144 + 0.195
              = 0.579
              = 57.9%
```

### Jets Cover Probability:
```
Jets_Prob = 1 - 0.579
          = 0.421
          = 42.1%
```

### Recommendation:
- **Bet On**: Patriots (higher probability)
- **Confidence**: 57.9%
- **Edge**: 7.9% (57.9% - 50%)
- **Confidence Level**: MODERATE (55-60% range)

---

## Confidence Levels

- **STRONG**: > 60% confidence 🔥
- **MODERATE**: 55-60% confidence ✅
- **WEAK**: < 55% confidence ⚠️

---

## Key Points

1. **Normalization**: Each factor normalizes the two teams' rates so they sum to 1.0. This ensures fair comparison.

2. **Weighted Average**: The three normalized values are weighted (40%, 30%, 30%) and summed.

3. **Database Dependent**: The actual prediction requires real historical data from your database.

4. **Spread Ranges**: 
   - 0-2: Toss-up games
   - 2-4: Close games
   - 4-7: Moderate favorites (Jets @ Patriots falls here)
   - 7-10: Strong favorites
   - 10+: Heavy favorites

5. **Seasons**: Uses 2024-2025 data by default (configurable).

---

## To Get Actual Answer

Run the prediction script with your database connection:

```bash
python run_jets_pats_prediction.py
```

This will query your actual database and give you the real prediction based on historical Patriots and Jets data.


