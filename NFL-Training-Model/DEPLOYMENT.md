# EC2 Deployment Guide - NFL Training Model

Complete step-by-step guide for deploying the training data preparation script on AWS EC2.

## Prerequisites

- AWS EC2 instance (t3.medium or larger recommended)
- SSH key pair for EC2 access
- Supabase database credentials
- Python 3.8+ installed on EC2

## Step-by-Step Deployment

### 1. Prepare Local Files

Ensure your local `NFL-Training-Model` folder has:
- `prepare_training_data.py`
- `requirements.txt`
- `config.py`
- `test_connection.py`
- `.gitignore`

### 2. Transfer Files to EC2

```bash
# Navigate to project root
cd "C:\Users\nealg\Nfl Predictive Model\NFLPredictiveModel"

# SCP the entire folder to EC2
scp -i /path/to/your-key.pem -r NFL-Training-Model ec2-user@your-ec2-ip:/home/ec2-user/

# Also transfer DatabaseConnection.py (dependency)
scp -i /path/to/your-key.pem \
    PredictiveDataModel/DataIngestionLambda/DatabaseConnection.py \
    ec2-user@your-ec2-ip:/home/ec2-user/NFL-Training-Model/
```

**Windows PowerShell Alternative:**
```powershell
# Using pscp (PuTTY)
pscp -i C:\path\to\your-key.ppk -r NFL-Training-Model ec2-user@your-ec2-ip:/home/ec2-user/
```

### 3. Connect to EC2

```bash
ssh -i /path/to/your-key.pem ec2-user@your-ec2-ip
```

### 4. Set Up Python Environment

```bash
# Navigate to project folder
cd NFL-Training-Model

# Update system packages
sudo yum update -y  # Amazon Linux
# OR
sudo apt-get update  # Ubuntu

# Install Python 3 and pip (if not already installed)
sudo yum install python3 python3-pip -y  # Amazon Linux
# OR
sudo apt-get install python3 python3-pip -y  # Ubuntu

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### 5. Configure Environment Variables

```bash
# Option 1: Create .env file
nano .env
```

Add the following (replace with your actual values):
```env
SUPABASE_DB_HOST=db.xxxxxx.supabase.co
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=your_actual_password
SUPABASE_DB_PORT=5432
```

Save: `Ctrl+X`, then `Y`, then `Enter`

```bash
# Option 2: Export directly in shell
export SUPABASE_DB_HOST=db.xxxxxx.supabase.co
export SUPABASE_DB_NAME=postgres
export SUPABASE_DB_USER=postgres
export SUPABASE_DB_PASSWORD=your_actual_password
export SUPABASE_DB_PORT=5432
```

### 6. Load Environment Variables

```bash
# If using .env file, install and use python-dotenv
pip install python-dotenv

# Or manually export from .env
export $(cat .env | xargs)
```

### 7. Test Connection

```bash
# Run connection test
python test_connection.py
```

**Expected Output:**
```
✅ Successfully imported DatabaseConnection

============================================================
🔍 Testing NFL Training Model Database Connection
============================================================

1️⃣ Testing database connection...
   ✅ Connection established

2️⃣ Checking available games...
   ✅ Games found:
      Season 2025: 272 games
      Season 2024: 272 games
      Total: 544 games

3️⃣ Verifying required columns...
   ✅ All required columns present
      Sample game: KC vs DET (Week 1, 2024)

4️⃣ Checking team data...
   ✅ Found 32 teams
      Perfect! All 32 NFL teams present

5️⃣ Checking environment configuration...
   ✅ All environment variables set

============================================================
✅ All checks passed! Ready to generate training data.
============================================================
```

### 8. Run Training Data Preparation

```bash
# Run the main script
python prepare_training_data.py
```

**Monitoring Progress:**
The script will output progress every 50 games:
```
2026-01-21 14:30:00 - INFO - ✅ Database connection established
2026-01-21 14:30:01 - INFO - 🏈 Starting training data preparation for seasons: [2024, 2025]
2026-01-21 14:30:02 - INFO - ✅ Retrieved 544 completed games
2026-01-21 14:30:10 - INFO - Processing game 50/544...
2026-01-21 14:30:18 - INFO - Processing game 100/544...
...
```

**Expected Runtime:** 5-15 minutes for ~500 games

### 9. Verify Output

```bash
# Check if CSV was created
ls -lh training_data.csv

# View first few rows
head -5 training_data.csv

# Count total rows
wc -l training_data.csv

# Check file size
du -h training_data.csv
```

**Expected Output:**
```
-rw-r--r-- 1 ec2-user ec2-user 150K Jan 21 14:35 training_data.csv
540 training_data.csv  # ~540 rows (games)
150K training_data.csv  # ~150KB file size
```

### 10. Download Training Data to Local Machine

```bash
# From your local machine (new terminal)
scp -i /path/to/your-key.pem \
    ec2-user@your-ec2-ip:/home/ec2-user/NFL-Training-Model/training_data.csv \
    C:/Users/nealg/Downloads/
```

## Troubleshooting

### Issue 1: "ModuleNotFoundError: No module named 'DatabaseConnection'"

**Cause:** DatabaseConnection.py not in correct location

**Solution:**
```bash
# Copy DatabaseConnection.py to current directory
cp ../PredictiveDataModel/DataIngestionLambda/DatabaseConnection.py .

# OR update path in prepare_training_data.py
nano prepare_training_data.py
# Adjust the sys.path.append line to match your directory structure
```

### Issue 2: "Connection timeout" or "Connection refused"

**Cause:** EC2 cannot reach Supabase database

**Solution:**
```bash
# 1. Check EC2 security group allows outbound traffic on port 5432
# AWS Console → EC2 → Security Groups → Outbound Rules → Add Rule:
#    Type: PostgreSQL, Port: 5432, Destination: 0.0.0.0/0

# 2. Test direct connection
psql "postgresql://postgres:password@db.xxx.supabase.co:5432/postgres"

# 3. Try Supabase connection pooler (port 6543)
export SUPABASE_DB_PORT=6543
```

### Issue 3: "pg8000 not found"

**Cause:** Dependencies not installed

**Solution:**
```bash
# Ensure venv is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep pg8000
```

### Issue 4: "Too many missing values"

**Cause:** Early season games lack sufficient historical data

**Solution:**
```bash
# Edit prepare_training_data.py to start from Week 6+
nano prepare_training_data.py

# Add filter in _query_completed_games:
# WHERE week >= 6

# Or increase min_periods in rolling calculations
```

### Issue 5: Script runs very slowly

**Cause:** Network latency or inefficient queries

**Solutions:**
```bash
# 1. Use larger EC2 instance (more CPU/RAM)
# Switch to t3.large or t3.xlarge

# 2. Use Supabase connection pooler
export SUPABASE_DB_PORT=6543

# 3. Add caching (future enhancement)
# Cache team stats to reduce redundant queries
```

## Performance Optimization

### Use Screen/Tmux for Long-Running Jobs

```bash
# Install screen
sudo yum install screen -y

# Start screen session
screen -S nfl-training

# Run script
python prepare_training_data.py

# Detach: Ctrl+A, then D
# Reattach later: screen -r nfl-training
```

### Run as Background Job

```bash
# Run in background and log output
nohup python prepare_training_data.py > training.log 2>&1 &

# Check progress
tail -f training.log

# Check if still running
ps aux | grep prepare_training_data
```

### Schedule with Cron (Weekly Updates)

```bash
# Edit crontab
crontab -e

# Add weekly job (every Sunday at 2 AM)
0 2 * * 0 /home/ec2-user/NFL-Training-Model/venv/bin/python \
    /home/ec2-user/NFL-Training-Model/prepare_training_data.py >> \
    /home/ec2-user/NFL-Training-Model/cron.log 2>&1
```

## Security Best Practices

### 1. Secure Environment Variables

```bash
# Set restrictive permissions on .env
chmod 600 .env

# Never commit .env to git
echo ".env" >> .gitignore
```

### 2. Use IAM Roles (Recommended)

Instead of storing credentials in .env:
1. Create IAM role with database access
2. Attach role to EC2 instance
3. Use AWS Secrets Manager for database password

### 3. Rotate Database Password

Update password periodically in:
- Supabase dashboard
- EC2 .env file
- Any other services using the database

## Monitoring & Logging

### View Real-Time Logs

```bash
# If using nohup
tail -f training.log

# If using screen
screen -r nfl-training
```

### Check Disk Space

```bash
# Before running
df -h

# If low on space
sudo yum clean all  # Clear package cache
rm -rf ~/.cache/*   # Clear user cache
```

### Monitor Memory Usage

```bash
# Real-time monitoring
htop

# Or basic monitoring
top
```

## Next Steps After Deployment

1. **Data Validation**: Check training_data.csv for quality
2. **Exploratory Analysis**: Analyze feature distributions
3. **Model Training**: Train XGBoost model on the data
4. **Model Deployment**: Replace manual weights with ML predictions
5. **Automated Updates**: Schedule weekly retraining

## Cost Optimization

- **Stop EC2 when not in use**: Save on compute costs
- **Use Spot Instances**: 70% cheaper for non-critical jobs
- **S3 Storage**: Store training data in S3 instead of EBS
- **Lambda Alternative**: Run as AWS Lambda for sporadic jobs

## Backup Strategy

```bash
# Backup training data to S3
aws s3 cp training_data.csv s3://your-bucket/nfl-training/training_data_$(date +%Y%m%d).csv

# Backup entire folder
tar -czf nfl-training-backup.tar.gz NFL-Training-Model/
aws s3 cp nfl-training-backup.tar.gz s3://your-bucket/backups/
```

## Support

For issues or questions:
- Check CloudWatch logs (if using Lambda)
- Review EC2 system logs: `/var/log/messages`
- Test database connection with `psql`
- Verify network connectivity with `ping` and `telnet`

---

**Last Updated:** 2026-01-21  
**Author:** Neal

