# NFL Predictive Model 🏈

A serverless AWS Lambda-based system for processing NFL game data, calculating team statistics, and generating rankings.

## 🚀 Quick Start

This project processes NFL game data from S3, stores it in PostgreSQL (RDS), and calculates comprehensive team rankings including offensive, defensive, and overall performance metrics.

## 📋 Features

- **Automated Data Processing**: Triggered by S3 file uploads
- **Comprehensive Statistics**: Calculates 30+ team metrics including:
  - Win/Loss records (overall, home, away, divisional)
  - Offensive and defensive rankings
  - Point differentials and averages
  - Betting line analysis
- **Duplicate Prevention**: Intelligent upsert logic prevents data duplication
- **Scalable Architecture**: Serverless design handles varying workloads
- **Full Logging**: CloudWatch integration for debugging and monitoring

## 📁 Project Structure

```
PredictiveDataModel/
├── Lambda_function.py              # Main Lambda handler
├── data_orchestrator_pipeline.py   # Pipeline orchestrator
├── S3Handler.py                    # S3 operations
├── DatabaseConnection.py           # Database connection manager
├── GameRepository.py               # Games table operations
├── TeamRankingsRepository.py       # Rankings table operations
├── DuplicateHandler.py             # Upsert logic
├── TextFileParser.py               # Input file parser
├── AggregateCalculator.py          # Team statistics calculator
├── BettingAnalyzer.py              # Betting metrics analyzer
├── RankingsCalculator.py           # Rankings calculator
├── requirements.txt                # Python dependencies
├── DEPLOYMENT.md                   # Complete deployment guide
└── ISSUES_FIXED.md                 # Issues resolved and improvements
```

## 🔧 Technology Stack

- **Runtime**: Python 3.11
- **Compute**: AWS Lambda
- **Storage**: Amazon S3
- **Database**: Amazon RDS (PostgreSQL 15)
- **Logging**: CloudWatch Logs
- **Libraries**: pandas, psycopg2, boto3

## 📖 Documentation

- **[DEPLOYMENT.md](PredictiveDataModel/DEPLOYMENT.md)** - Complete AWS deployment guide with step-by-step instructions
- **[ISSUES_FIXED.md](PredictiveDataModel/ISSUES_FIXED.md)** - Detailed list of all fixes and improvements

## 🏗️ Architecture

```
S3 Bucket (NFL Data) → Lambda Function → RDS PostgreSQL
                            ↓
                    CloudWatch Logs
```

1. Upload `.txt` file with NFL game data to S3
2. S3 triggers Lambda function
3. Lambda processes data and calculates rankings
4. Results stored in RDS PostgreSQL
5. All activity logged to CloudWatch

## 🚦 Prerequisites

- AWS Account with appropriate permissions
- AWS CLI configured
- PostgreSQL client (for database setup)
- Python 3.11+

## 📦 Quick Deployment

See [DEPLOYMENT.md](PredictiveDataModel/DEPLOYMENT.md) for full instructions.

```bash
# 1. Install dependencies
cd PredictiveDataModel
pip install -r requirements.txt

# 2. Create deployment package
mkdir lambda_package
pip install -r requirements.txt -t lambda_package/
cp *.py lambda_package/
cd lambda_package && zip -r ../deployment.zip . && cd ..

# 3. Deploy to Lambda (see DEPLOYMENT.md for full AWS setup)
aws lambda create-function \
  --function-name NFLPredictiveModel \
  --runtime python3.11 \
  --handler Lambda_function.lambda_handler \
  --zip-file fileb://deployment.zip \
  [... see DEPLOYMENT.md for complete command]
```

## 🔐 Environment Variables

Required Lambda environment variables:

```bash
DB_HOST=your-rds-endpoint.rds.amazonaws.com
DB_NAME=nfl_predictive
DB_USER=admin
DB_PASSWORD=your-secure-password
DB_PORT=5432
```

## 📊 Database Schema

### Tables
- **games**: Stores all NFL game data with betting lines
- **team_rankings**: Stores calculated team statistics and rankings

See [DEPLOYMENT.md](PredictiveDataModel/DEPLOYMENT.md) for complete schema.

## 🧪 Testing

```bash
# Upload test file to S3
aws s3 cp test-data.txt s3://your-bucket/

# Monitor logs
aws logs tail /aws/lambda/NFLPredictiveModel --follow

# Manual invoke
aws lambda invoke \
  --function-name NFLPredictiveModel \
  --payload file://test-event.json \
  response.json
```

## 📈 Monitoring

All execution logs are sent to CloudWatch Logs:
- INFO: Processing steps and progress
- ERROR: Errors with full stack traces
- WARNING: Connection issues and retries

## 🔍 Troubleshooting

Common issues and solutions are documented in [DEPLOYMENT.md](PredictiveDataModel/DEPLOYMENT.md#troubleshooting).

Quick checks:
1. Verify Lambda has VPC access to RDS
2. Check security group rules (port 5432)
3. Confirm environment variables are set
4. Review CloudWatch logs for errors

## 🛠️ Recent Fixes

All critical errors have been resolved:
- ✅ Fixed invalid imports in S3Handler.py
- ✅ Completed incomplete code in DatabaseConnection.py
- ✅ Fixed truncated return in Lambda_function.py
- ✅ Corrected all import paths for flat directory structure
- ✅ Replaced all print statements with proper logging

See [ISSUES_FIXED.md](PredictiveDataModel/ISSUES_FIXED.md) for complete details.

## 🎯 Future Enhancements

- [ ] Implement batch database operations
- [ ] Add RDS Proxy for connection pooling
- [ ] Create CloudWatch dashboard
- [ ] Add automated testing suite
- [ ] Implement caching layer
- [ ] Add data validation and quality checks

## 📝 License

This project is for educational and analytical purposes.

## 👥 Contributing

1. Review code and provide feedback
2. Test with your own NFL data
3. Suggest improvements or report issues

---

**Status**: ✅ Production Ready  
**Last Updated**: October 18, 2025  
**AWS Lambda Compatible**: Yes

BOYS LET US COOK 🔥
