# Sportradar API Endpoints Reference

Complete reference for all Sportradar NFL API endpoints used in PlayerImpactCalculator.

**API Key:** `bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm`  
**Base URL:** `https://api.sportradar.com/nfl/official/trial/v7/en`

---

## 📊 Core Endpoints (Required for Injury Impact)

### 1. Weekly Schedule ⭐ CRITICAL
**Get all games for a week to obtain game_ids**

```bash
curl --request GET \
     --url https://api.sportradar.com/nfl/official/trial/v7/en/seasons/2025/REG/10/schedule.json \
     --header 'accept: application/json' \
     --header 'x-api-key: bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm'
```

**Method:** `client.get_weekly_schedule(season=2025, week=10, season_type='REG')`

**Response Structure:**
```json
{
  "week": {
    "number": 10,
    "games": [
      {
        "id": "ca9d8f84-8e7b-4ee7-a310-54c2e3ca4edc",
        "home": {
          "id": "home-team-uuid",
          "name": "Kansas City Chiefs"
        },
        "away": {
          "id": "away-team-uuid",
          "name": "Denver Broncos"
        },
        "scheduled": "2025-11-10T18:00:00+00:00",
        "status": "scheduled"
      }
    ]
  }
}
```

**Use Case:** Start here to get game_ids for processing

---

### 2. Weekly Depth Charts
**Get position depth charts for all teams**

```bash
curl --request GET \
     --url https://api.sportradar.com/nfl/official/trial/v7/en/seasons/2025/REG/10/depth_charts.json \
     --header 'accept: application/json' \
     --header 'x-api-key: bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm'
```

**Method:** `client.get_depth_chart(season=2025, week=10, season_type='REG')`

**Use Case:** Determine who are starters vs backups at each position

---

### 3. Weekly Injuries
**Get injury status for all teams**

```bash
curl --request GET \
     --url https://api.sportradar.com/nfl/official/trial/v7/en/seasons/2025/REG/10/injuries.json \
     --header 'accept: application/json' \
     --header 'x-api-key: bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm'
```

**Method:** `client.get_injuries(season=2025, week=10, season_type='REG')`

**Use Case:** Check injury designations (Questionable, Doubtful, Out, IR)

---

### 4. Game Roster ⭐ CRITICAL
**Get active/inactive players for a specific game**

```bash
curl --request GET \
     --url https://api.sportradar.com/nfl/official/trial/v7/en/games/ca9d8f84-8e7b-4ee7-a310-54c2e3ca4edc/roster.json \
     --header 'accept: application/json' \
     --header 'x-api-key: bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm'
```

**Method:** `client.get_game_roster(game_id='ca9d8f84-8e7b-4ee7-a310-54c2e3ca4edc')`

**Response Structure:**
```json
{
  "home": {
    "id": "team-uuid",
    "name": "Kansas City Chiefs",
    "players": [
      {
        "id": "player-uuid",
        "name": "Patrick Mahomes",
        "position": "QB",
        "jersey_number": "15",
        "roster_status": "ACTIVE"
      }
    ]
  },
  "away": { ... }
}
```

**Use Case:** Determine who actually played in the game (ACTIVE vs INACTIVE)

---

## 📈 Additional Endpoints (Optional but Useful)

### 5. Season Schedule
**Get entire season schedule**

```bash
curl --request GET \
     --url https://api.sportradar.com/nfl/official/trial/v7/en/seasons/2025/REG/schedule.json \
     --header 'accept: application/json' \
     --header 'x-api-key: bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm'
```

**Method:** `client.get_season_schedule(season=2025, season_type='REG')`

**Use Case:** Batch process entire season, get all game_ids at once

---

### 6. Game Summary
**Get final stats and boxscore**

```bash
curl --request GET \
     --url https://api.sportradar.com/nfl/official/trial/v7/en/games/ca9d8f84-8e7b-4ee7-a310-54c2e3ca4edc/summary.json \
     --header 'accept: application/json' \
     --header 'x-api-key: bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm'
```

**Method:** `client.get_game_summary(game_id='ca9d8f84-8e7b-4ee7-a310-54c2e3ca4edc')`

**Use Case:** Get final score, team stats, player performance

---

### 7. Team Roster
**Get full season roster for a team**

```bash
curl --request GET \
     --url https://api.sportradar.com/nfl/official/trial/v7/en/teams/TEAM-UUID/full_roster.json \
     --header 'accept: application/json' \
     --header 'x-api-key: bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm'
```

**Method:** `client.get_team_roster(team_id='team-uuid', season=2025)`

**Use Case:** Get complete team roster with player IDs

---

### 8. Player Profile
**Get detailed player information**

```bash
curl --request GET \
     --url https://api.sportradar.com/nfl/official/trial/v7/en/players/PLAYER-UUID/profile.json \
     --header 'accept: application/json' \
     --header 'x-api-key: bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm'
```

**Method:** `client.get_player_profile(player_id='player-uuid')`

**Use Case:** Get player details, stats, biographical info

---

### 9. Standings
**Get current standings**

```bash
curl --request GET \
     --url https://api.sportradar.com/nfl/official/trial/v7/en/seasons/2025/REG/standings.json \
     --header 'accept: application/json' \
     --header 'x-api-key: bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm'
```

**Method:** `client.get_standings(season=2025, season_type='REG')`

**Use Case:** Get wins, losses, division standings

---

## 🔄 Typical Workflow

### Process a Single Game
```python
from SportradarClient import SportradarClient

client = SportradarClient(api_key='bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm')

# 1. Get game info from schedule
schedule = client.get_weekly_schedule(2025, 10, 'REG')
game = schedule['week']['games'][0]
game_id = game['id']

# 2. Get depth chart for the week
depth_chart = client.get_depth_chart(2025, 10, 'REG')

# 3. Get who was active/inactive
roster = client.get_game_roster(game_id)

# 4. Calculate injury impact (using other modules)
# ... process with GameProcessor ...
```

### Process Entire Week
```python
# Get all games
schedule = client.get_weekly_schedule(2025, 10, 'REG')

# Loop through each game
for game in schedule['week']['games']:
    game_id = game['id']
    roster = client.get_game_roster(game_id)
    # ... process each game ...
```

---

## ⚡ Rate Limits

**Trial API:**
- **1 request per second** (auto-throttled in SportradarClient)
- **1,000 requests per month**

**Tips:**
- Cache API responses when possible
- Use weekly endpoints (depth_chart, injuries) instead of querying per team
- Process games in batches with delays

---

## 🎯 Quick Reference Table

| Endpoint | Required for Injury Impact? | Rate Impact |
|----------|---------------------------|-------------|
| Weekly Schedule | ⭐ YES (to get game_ids) | 1 req/week |
| Weekly Depth Charts | ⭐ YES | 1 req/week |
| Weekly Injuries | Optional | 1 req/week |
| Game Roster | ⭐ YES | 1 req/game |
| Game Summary | Optional | 1 req/game |
| Season Schedule | Optional | 1 req/season |
| Team Roster | Optional | 1 req/team |
| Player Profile | Optional | 1 req/player |
| Standings | Optional | 1 req/season |

**Total for 1 week of games (16 games):**
- Schedule: 1 request
- Depth Chart: 1 request
- Game Rosters: 16 requests
- **Total: ~18 requests per week**

---

## 📝 Finding IDs

### How to get Team IDs?
```python
# From weekly schedule
schedule = client.get_weekly_schedule(2025, 10)
for game in schedule['week']['games']:
    print(f"{game['away']['name']}: {game['away']['id']}")
    print(f"{game['home']['name']}: {game['home']['id']}")
```

### How to get Game IDs?
```python
# From weekly schedule (recommended)
schedule = client.get_weekly_schedule(2025, 10)
game_ids = [game['id'] for game in schedule['week']['games']]
```

### How to get Player IDs?
```python
# From team roster
roster = client.get_team_roster('team-uuid')
for player in roster['players']:
    print(f"{player['name']}: {player['id']}")
```

---

## 🚀 Example: Process Week 10

```bash
# Run automated week processing
python process_weekly_games.py --season 2025 --week 10 --type REG
```

This will:
1. Call `get_weekly_schedule()` to get all game IDs
2. Call `get_depth_chart()` for week data
3. For each game, call `get_game_roster()`
4. Calculate injury impact
5. Store in Supabase

**API calls for Week 10 (16 games):**
- 1 schedule request
- 1 depth chart request
- 16 game roster requests
- **Total: 18 requests** (~18 seconds with rate limiting)

---

## 📞 Need Help?

- **API Documentation:** https://developer.sportradar.com/docs/read/american_football/NFL_v7
- **Test Endpoint:** Use `test_integration.py` to verify API access
- **Rate Limits:** Check your dashboard at https://developer.sportradar.com

**Already Configured:**
- ✅ API Key: `bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm`
- ✅ Rate limiting built-in
- ✅ Error handling included
- ✅ Logging for all requests

