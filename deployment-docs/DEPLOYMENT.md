# AWS Lambda Deployment Guide
## NFL Predictive Model

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [AWS Infrastructure Setup](#aws-infrastructure-setup)
3. [Database Setup](#database-setup)
4. [Lambda Deployment](#lambda-deployment)
5. [Environment Variables](#environment-variables)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required AWS Services
- **AWS Lambda**: Serverless compute
- **Amazon RDS (PostgreSQL)**: Database for game data and rankings
- **Amazon S3**: Storage for input data files
- **CloudWatch Logs**: For monitoring and debugging
- **IAM**: For permissions and roles

### Required Tools
- AWS CLI configured with appropriate credentials
- Python 3.11 (Lambda runtime)
- PostgreSQL client (for database setup)

---

## AWS Infrastructure Setup

### 1. Create S3 Bucket

```bash
# Create S3 bucket for NFL data
aws s3 mb s3://nfl-predictive-data --region us-east-1

# Enable versioning (optional but recommended)
aws s3api put-bucket-versioning \
  --bucket nfl-predictive-data \
  --versioning-configuration Status=Enabled
```

### 2. Create RDS PostgreSQL Database

```bash
# Create DB subnet group (adjust subnet IDs)
aws rds create-db-subnet-group \
  --db-subnet-group-name nfl-db-subnet \
  --db-subnet-group-description "NFL DB Subnet Group" \
  --subnet-ids subnet-xxxxx subnet-yyyyy

# Create security group for RDS
aws ec2 create-security-group \
  --group-name nfl-rds-sg \
  --description "Security group for NFL RDS" \
  --vpc-id vpc-xxxxx

# Add inbound rule (allow Lambda's security group)
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxx \
  --protocol tcp \
  --port 5432 \
  --source-group sg-yyyyy

# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier nfl-predictive-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15.4 \
  --master-username admin \
  --master-user-password 'YourSecurePassword123!' \
  --allocated-storage 20 \
  --db-subnet-group-name nfl-db-subnet \
  --vpc-security-group-ids sg-xxxxx \
  --backup-retention-period 7 \
  --no-publicly-accessible
```

### 3. Create IAM Role for Lambda

Create a file `lambda-trust-policy.json`:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Create a file `lambda-permissions.json`:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::nfl-predictive-data",
        "arn:aws:s3:::nfl-predictive-data/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "ec2:CreateNetworkInterface",
        "ec2:DescribeNetworkInterfaces",
        "ec2:DeleteNetworkInterface",
        "ec2:AssignPrivateIpAddresses",
        "ec2:UnassignPrivateIpAddresses"
      ],
      "Resource": "*"
    }
  ]
}
```

Create the role:
```bash
# Create IAM role
aws iam create-role \
  --role-name NFLPredictiveLambdaRole \
  --assume-role-policy-document file://lambda-trust-policy.json

# Attach custom policy
aws iam put-role-policy \
  --role-name NFLPredictiveLambdaRole \
  --policy-name NFLLambdaPermissions \
  --policy-document file://lambda-permissions.json

# Attach AWS managed policy for VPC access
aws iam attach-role-policy \
  --role-name NFLPredictiveLambdaRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole
```

---

## Database Setup

### 1. Connect to RDS

```bash
# Get RDS endpoint
aws rds describe-db-instances \
  --db-instance-identifier nfl-predictive-db \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text

# Connect via psql (from a machine with access)
psql -h <RDS-ENDPOINT> -U admin -d postgres
```

### 2. Create Database Schema

```sql
-- Create database
CREATE DATABASE nfl_predictive;
\c nfl_predictive

-- Create games table
CREATE TABLE games (
    game_id VARCHAR(20) PRIMARY KEY,
    season INTEGER NOT NULL,
    game_type VARCHAR(10) NOT NULL,
    week INTEGER NOT NULL,
    gameday DATE,
    weekday VARCHAR(10),
    gametime VARCHAR(10),
    away_team VARCHAR(3) NOT NULL,
    away_score INTEGER,
    home_team VARCHAR(3) NOT NULL,
    home_score INTEGER,
    location VARCHAR(50),
    away_moneyline FLOAT,
    home_moneyline FLOAT,
    spread_line FLOAT,
    total_line FLOAT,
    div_game BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create team_rankings table
CREATE TABLE team_rankings (
    id SERIAL PRIMARY KEY,
    team_id VARCHAR(3) NOT NULL,
    season INTEGER NOT NULL,
    games_played INTEGER,
    wins INTEGER,
    losses INTEGER,
    ties INTEGER,
    win_rate FLOAT,
    total_points_scored INTEGER,
    total_points_allowed INTEGER,
    avg_points_scored FLOAT,
    avg_points_allowed FLOAT,
    point_differential INTEGER,
    avg_point_differential FLOAT,
    offensive_rank INTEGER,
    defensive_rank INTEGER,
    overall_rank INTEGER,
    home_games INTEGER,
    home_wins INTEGER,
    home_losses INTEGER,
    home_win_rate FLOAT,
    home_avg_points_scored FLOAT,
    home_avg_points_allowed FLOAT,
    away_games INTEGER,
    away_wins INTEGER,
    away_losses INTEGER,
    away_win_rate FLOAT,
    away_avg_points_scored FLOAT,
    away_avg_points_allowed FLOAT,
    div_games INTEGER,
    div_wins INTEGER,
    div_losses INTEGER,
    div_win_rate FLOAT,
    avg_spread_line FLOAT,
    avg_total_line FLOAT,
    times_favored INTEGER,
    times_underdog INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, season)
);

-- Create indexes
CREATE INDEX idx_games_season_week ON games(season, week);
CREATE INDEX idx_games_teams ON games(home_team, away_team);
CREATE INDEX idx_rankings_season ON team_rankings(season);
CREATE INDEX idx_rankings_team ON team_rankings(team_id);
CREATE INDEX idx_rankings_overall ON team_rankings(overall_rank);
```

---

## Lambda Deployment

### 1. Prepare Lambda Package

```bash
cd PredictiveDataModel

# Create deployment package directory
mkdir -p lambda_package

# Install dependencies to package directory
pip install -r requirements.txt -t lambda_package/

# Copy your Python files to package
cp *.py lambda_package/

# Create ZIP file
cd lambda_package
zip -r ../nfl-lambda-deployment.zip .
cd ..
```

### 2. Create Lambda Function

```bash
# Create Lambda function
aws lambda create-function \
  --function-name NFLPredictiveModel \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR-ACCOUNT-ID:role/NFLPredictiveLambdaRole \
  --handler Lambda_function.lambda_handler \
  --zip-file fileb://nfl-lambda-deployment.zip \
  --timeout 900 \
  --memory-size 1024 \
  --vpc-config SubnetIds=subnet-xxxxx,subnet-yyyyy,SecurityGroupIds=sg-xxxxx \
  --environment Variables="{DB_HOST=your-rds-endpoint.rds.amazonaws.com,DB_NAME=nfl_predictive,DB_USER=admin,DB_PASSWORD=YourSecurePassword123!,DB_PORT=5432}"
```

### 3. Configure S3 Trigger

```bash
# Add permission for S3 to invoke Lambda
aws lambda add-permission \
  --function-name NFLPredictiveModel \
  --statement-id s3-trigger-permission \
  --action lambda:InvokeFunction \
  --principal s3.amazonaws.com \
  --source-arn arn:aws:s3:::nfl-predictive-data

# Create S3 event notification
aws s3api put-bucket-notification-configuration \
  --bucket nfl-predictive-data \
  --notification-configuration file://s3-notification.json
```

Create `s3-notification.json`:
```json
{
  "LambdaFunctionConfigurations": [
    {
      "Id": "NFLDataUploadTrigger",
      "LambdaFunctionArn": "arn:aws:lambda:us-east-1:YOUR-ACCOUNT-ID:function:NFLPredictiveModel",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {
          "FilterRules": [
            {
              "Name": "suffix",
              "Value": ".txt"
            }
          ]
        }
      }
    }
  ]
}
```

---

## Environment Variables

Set these environment variables in Lambda Configuration:

| Variable | Description | Example |
|----------|-------------|---------|
| `DB_HOST` | RDS endpoint | `nfl-db.xxxxx.us-east-1.rds.amazonaws.com` |
| `DB_NAME` | Database name | `nfl_predictive` |
| `DB_USER` | Database user | `admin` |
| `DB_PASSWORD` | Database password | `YourSecurePassword123!` |
| `DB_PORT` | PostgreSQL port | `5432` |

**Security Best Practice**: Use AWS Secrets Manager or Parameter Store instead of environment variables:

```bash
# Store password in Secrets Manager
aws secretsmanager create-secret \
  --name nfl-db-password \
  --secret-string "YourSecurePassword123!"

# Update Lambda to retrieve from Secrets Manager (modify code)
```

---

## Testing

### 1. Upload Test File

```bash
# Upload a test file to S3
aws s3 cp your-nfl-data.txt s3://nfl-predictive-data/test/
```

### 2. Monitor CloudWatch Logs

```bash
# View recent logs
aws logs tail /aws/lambda/NFLPredictiveModel --follow
```

### 3. Manual Test

Create `test-event.json`:
```json
{
  "Records": [
    {
      "s3": {
        "bucket": {
          "name": "nfl-predictive-data"
        },
        "object": {
          "key": "test/your-nfl-data.txt"
        }
      }
    }
  ]
}
```

Test the function:
```bash
aws lambda invoke \
  --function-name NFLPredictiveModel \
  --payload file://test-event.json \
  --cli-binary-format raw-in-base64-out \
  response.json

# View response
cat response.json
```

---

## Troubleshooting

### Common Issues

#### 1. Timeout Errors
**Problem**: Lambda times out before completion
**Solution**: Increase timeout (max 15 minutes):
```bash
aws lambda update-function-configuration \
  --function-name NFLPredictiveModel \
  --timeout 900
```

#### 2. Memory Errors
**Problem**: Lambda runs out of memory
**Solution**: Increase memory allocation:
```bash
aws lambda update-function-configuration \
  --function-name NFLPredictiveModel \
  --memory-size 2048
```

#### 3. Database Connection Errors
**Problem**: Cannot connect to RDS
**Solution**: 
- Verify security group allows Lambda's security group on port 5432
- Ensure Lambda is in same VPC as RDS
- Check VPC subnet routing

#### 4. Import Errors
**Problem**: `ModuleNotFoundError`
**Solution**: Ensure all dependencies are in the Lambda package:
```bash
pip install --upgrade -r requirements.txt -t lambda_package/
```

#### 5. psycopg2 Issues
**Problem**: Binary incompatibility with Lambda runtime
**Solution**: Use `psycopg2-binary` or compile for Amazon Linux 2023

### Viewing Logs

```bash
# View all log streams
aws logs describe-log-streams \
  --log-group-name /aws/lambda/NFLPredictiveModel

# Filter for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/NFLPredictiveModel \
  --filter-pattern "ERROR"
```

---

## Update Lambda Code

After making changes:

```bash
# Recreate deployment package
cd PredictiveDataModel
cd lambda_package
zip -r ../nfl-lambda-deployment.zip .
cd ..

# Update Lambda function
aws lambda update-function-code \
  --function-name NFLPredictiveModel \
  --zip-file fileb://nfl-lambda-deployment.zip
```

---

## Cost Optimization

1. **Right-size memory**: Start with 1024 MB, adjust based on CloudWatch metrics
2. **Use RDS Proxy**: For connection pooling if needed
3. **Enable S3 Intelligent-Tiering**: For cost-effective storage
4. **Set CloudWatch log retention**: Default is indefinite
   ```bash
   aws logs put-retention-policy \
     --log-group-name /aws/lambda/NFLPredictiveModel \
     --retention-in-days 7
   ```

---

## Security Checklist

- [ ] Database password stored in Secrets Manager
- [ ] Lambda in private subnets with NAT Gateway for internet access
- [ ] RDS not publicly accessible
- [ ] S3 bucket has encryption enabled
- [ ] IAM role follows least privilege principle
- [ ] CloudWatch logs encrypted
- [ ] Security group rules restricted to minimum necessary

---

## Monitoring & Alerts

### Set up CloudWatch Alarms

```bash
# Create alarm for Lambda errors
aws cloudwatch put-metric-alarm \
  --alarm-name nfl-lambda-errors \
  --alarm-description "Alert when Lambda has errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=FunctionName,Value=NFLPredictiveModel
```

---

## Support & Maintenance

### Regular Maintenance Tasks
1. Review CloudWatch logs weekly
2. Monitor RDS performance metrics
3. Update dependencies monthly
4. Review and optimize Lambda memory/timeout settings
5. Backup RDS database regularly (automated with RDS)

### Useful AWS CLI Commands

```bash
# Check Lambda configuration
aws lambda get-function-configuration --function-name NFLPredictiveModel

# List recent invocations
aws lambda list-invocations --function-name NFLPredictiveModel

# Get CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=NFLPredictiveModel \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Average
```

---

## Additional Resources

- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [Amazon RDS PostgreSQL Guide](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_PostgreSQL.html)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [psycopg2 Documentation](https://www.psycopg.org/docs/)

---

**Last Updated**: October 18, 2025


