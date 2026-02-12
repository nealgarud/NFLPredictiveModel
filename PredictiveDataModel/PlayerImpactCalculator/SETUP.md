# PlayerImpactCalculator Setup Guide

Complete setup instructions for integrating real NFL data sources.

## 📋 Prerequisites

1. **Python 3.8+** installed
2. **AWS Account** with S3 access
3. **Supabase Account** (free tier works)
4. **Sportradar API Key** (trial or paid)

---

## 🔧 Step-by-Step Setup

### 1. Install Dependencies

```bash
cd PredictiveDataModel/PlayerImpactCalculator
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```bash
# Sportradar API
SPORTRADAR_API_KEY=bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm

# AWS S3
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret

# Supabase
SUPABASE_DB_HOST=db.xxx.supabase.co
SUPABASE_DB_PASSWORD=your_password
```

### 3. Verify S3 Data Access

Test S3 connection and list available files:

```python
from S3DataLoader import S3DataLoader

loader = S3DataLoader(bucket_name='sportsdatacollection')

# Check Madden files
print("Madden ratings:", loader.list_available_madden_files())

# Check game data files
print("Game data:", loader.list_available_game_data_files())
```

Expected output:
```
Madden ratings: ['madden-ratings/madden_2025.csv', ...]
Game data: ['raw-data/2024.csv', 'raw-data/2023.csv', 'raw-data/2022.csv']
```

### 4. Initialize Supabase Database

The database tables will be created automatically on first run. To manually create them:

```python
from SupabaseStorage import SupabaseStorage

storage = SupabaseStorage()  # Tables auto-created
print("✓ Database initialized")
```

This creates three tables:
- `player_ratings` - Player weights and Madden ratings
- `injury_impact` - Game-by-game injury calculations
- `inactive_players` - Tracking inactive players per game

### 5. Test Sportradar API Access

```python
from SportradarClient import SportradarClient

client = SportradarClient(api_key='bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm')

# Fetch 2025 Week 10 injuries
injuries = client.get_injuries(season=2025, week=10, season_type='REG')
print(f"✓ Fetched injuries for {len(injuries.get('week', {}).get('teams', []))} teams")
```

### 6. Run Complete Example

```bash
python example_usage.py
```

This will:
1. Connect to Sportradar API
2. Load Madden ratings from S3
3. Process a game (update with real game IDs)
4. Store results in Supabase

---

## 🗃️ Data Source Details

### Sportradar API

**API Key:** `bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm`

**Available Endpoints:**
```
GET /seasons/2025/REG/10/injuries.json
GET /seasons/2025/REG/10/depth_charts.json
GET /games/{game_id}/roster.json
```

**Rate Limits:**
- Trial: 1 request/second (auto-throttled)
- Need game_id? Get from schedule endpoint or UI

### AWS S3 Bucket: `sportsdatacollection`

**Historical Game Data:**
- `s3://sportsdatacollection/raw-data/2024.csv`
- `s3://sportsdatacollection/raw-data/2023.csv`
- `s3://sportsdatacollection/raw-data/2022.csv`

**Madden Ratings:**
- `s3://sportsdatacollection/madden-ratings/*.csv`

**Access:**
- Use IAM role (if running on AWS)
- Or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY

### Supabase PostgreSQL

**Connection Info:**
- Host: `db.{project-ref}.supabase.co`
- Port: `5432` (direct) or `6543` (pooler)
- Database: `postgres`
- User: `postgres`

**Find Your Credentials:**
1. Go to Supabase Dashboard
2. Project Settings → Database
3. Copy connection string details

---

## 🧪 Testing Your Setup

### Quick Test Script

Create `test_setup.py`:

```python
import os
from SportradarClient import SportradarClient
from S3DataLoader import S3DataLoader
from SupabaseStorage import SupabaseStorage

print("Testing PlayerImpactCalculator Setup...")
print("="*60)

# Test 1: Sportradar API
try:
    client = SportradarClient(api_key=os.environ.get('SPORTRADAR_API_KEY'))
    injuries = client.get_injuries(2025, 10, 'REG')
    print("✓ Sportradar API: Connected")
except Exception as e:
    print(f"✗ Sportradar API: {e}")

# Test 2: S3 Data
try:
    loader = S3DataLoader()
    files = loader.list_available_madden_files()
    print(f"✓ S3 Access: {len(files)} Madden files found")
except Exception as e:
    print(f"✗ S3 Access: {e}")

# Test 3: Supabase
try:
    storage = SupabaseStorage()
    storage.close()
    print("✓ Supabase: Connected")
except Exception as e:
    print(f"✗ Supabase: {e}")

print("="*60)
print("Setup complete! Run example_usage.py to process a game.")
```

Run:
```bash
python test_setup.py
```

---

## 🔑 Getting API Keys & Credentials

### Sportradar API Key

Already provided: `bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm`

Or get your own:
1. Go to https://developer.sportradar.com
2. Sign up for free trial
3. Create NFL API project
4. Copy API key

### AWS Credentials

**Option 1: IAM Role (recommended for AWS)**
- Run on EC2, Lambda, or ECS
- Attach IAM role with S3 read permissions

**Option 2: Access Keys**
1. AWS Console → IAM → Users
2. Create user or use existing
3. Security Credentials → Create Access Key
4. Save Access Key ID and Secret Access Key

**Required S3 Permissions:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::sportsdatacollection",
        "arn:aws:s3:::sportsdatacollection/*"
      ]
    }
  ]
}
```

### Supabase Setup

1. Go to https://supabase.com
2. Create new project (free tier works)
3. Wait for provisioning (~2 minutes)
4. Project Settings → Database
5. Copy:
   - Host
   - Database password (set during project creation)
   - Port (5432 for direct, 6543 for pooler)

---

## 🐛 Troubleshooting

### "SPORTRADAR_API_KEY not set"
**Solution:** Export environment variable or add to .env file

### "Access Denied" when accessing S3
**Solution:** 
- Check AWS credentials
- Verify IAM permissions include `s3:GetObject` for `sportsdatacollection` bucket
- Try: `aws s3 ls s3://sportsdatacollection/` to test CLI access

### "Connection timeout" to Supabase
**Solution:**
- Verify SUPABASE_DB_HOST is correct
- Check firewall/network restrictions
- Try port 6543 (pooler) if 5432 fails
- Ensure IP is whitelisted (Supabase → Settings → Database → Connection Pooling)

### "No Madden files found"
**Solution:**
- Verify bucket name: `sportsdatacollection`
- Check file paths match S3 structure
- Use `loader.list_available_madden_files()` to see actual paths

### "Rate limit exceeded" (Sportradar)
**Solution:**
- Built-in throttling: 1 req/second
- Cache API responses when possible
- Upgrade to paid plan for higher limits

---

## 📚 Next Steps

1. **Run Example:** `python example_usage.py`
2. **Read Documentation:** Check `README.md` for module details
3. **Explore Data:** Query Supabase to see stored results
4. **Integrate:** Use in your prediction models

---

## 💡 Tips

- **Development:** Use direct connection (port 5432)
- **Production/Lambda:** Use pooler (port 6543)
- **Caching:** S3DataLoader caches loaded data automatically
- **Rate Limiting:** SportradarClient has built-in throttling
- **Logging:** Set `LOG_LEVEL=DEBUG` for detailed output

---

## 📞 Support

If you encounter issues:
1. Check this setup guide
2. Review README.md troubleshooting section
3. Verify all environment variables are set
4. Test each component individually (Sportradar, S3, Supabase)

Happy predicting! 🏈

