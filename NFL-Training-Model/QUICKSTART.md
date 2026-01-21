# Quick Start Guide - NFL Training Model

Get training data generated in 5 minutes.

## Prerequisites

✅ Python 3.8+  
✅ Supabase credentials  
✅ NFL game data in database (2024-2025)

## Installation (Local)

```bash
# 1. Navigate to folder
cd NFL-Training-Model

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set environment variables
export SUPABASE_DB_HOST=db.xxx.supabase.co
export SUPABASE_DB_PASSWORD=your_password
export SUPABASE_DB_USER=postgres
export SUPABASE_DB_NAME=postgres
export SUPABASE_DB_PORT=5432

# 4. Test connection
python test_connection.py

# 5. Generate training data
python prepare_training_data.py
```

## Installation (EC2)

```bash
# 1. Upload files
scp -i your-key.pem -r NFL-Training-Model ec2-user@your-ip:/home/ec2-user/

# 2. SSH into EC2
ssh -i your-key.pem ec2-user@your-ip

# 3. Setup
cd NFL-Training-Model
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Configure
export SUPABASE_DB_HOST=db.xxx.supabase.co
export SUPABASE_DB_PASSWORD=your_password
# ... other env vars

# 5. Run
python test_connection.py
python prepare_training_data.py

# 6. Download results
# From local machine:
scp -i your-key.pem ec2-user@your-ip:/home/ec2-user/NFL-Training-Model/training_data.csv ./
```

## What You Get

**Output:** `training_data.csv` with ~540 rows

**Columns:**
- Game metadata: game_id, season, week, teams, spread
- 20+ features: recent form, divisional ATS, bye weeks, prime time, etc.
- Target: favorite_covered (1 or 0)

## Next Steps

1. **EDA**: Analyze feature distributions
2. **Split Data**: Train/validation/test sets
3. **Train Model**: XGBoost with hyperparameter tuning
4. **Evaluate**: Accuracy, precision, recall, feature importance
5. **Deploy**: Replace manual weights in SpreadPredictionCalculator

## Common Issues

| Issue | Solution |
|-------|----------|
| "No module DatabaseConnection" | Copy DatabaseConnection.py to current folder |
| "Connection timeout" | Check EC2 security group, try port 6543 |
| "Too many missing values" | Filter to Week 6+, adjust min_periods |
| Script slow | Use t3.large EC2, enable connection pooling |

## File Structure

```
NFL-Training-Model/
├── prepare_training_data.py  # Main script
├── test_connection.py         # Connection tester
├── config.py                  # Configuration settings
├── requirements.txt           # Python dependencies
├── README.md                  # Full documentation
├── DEPLOYMENT.md              # EC2 deployment guide
├── QUICKSTART.md              # This file
└── .gitignore                 # Git ignore patterns
```

## Resources

- **Full Docs**: See `README.md`
- **EC2 Guide**: See `DEPLOYMENT.md`
- **Config Options**: See `config.py`

## Support

Questions? Check:
1. `test_connection.py` output for diagnostics
2. Script logs for detailed errors
3. `DEPLOYMENT.md` troubleshooting section

---

**Ready to train your model? Run `python prepare_training_data.py` now! 🏈**

