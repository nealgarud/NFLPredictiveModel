# Lambda Layer Deployment - Lightweight & Fast! 🚀

Deploy PlayerImpactCalculator using Lambda Layers for much smaller package size.

## Why Use Lambda Layers?

**Without Layer:**
- ZIP size: ~150-200 MB (pandas + numpy are huge)
- Slow uploads
- Each function has duplicate dependencies

**With Layer:**
- Function ZIP: ~100 KB (just your code!)
- Layer ZIP: ~150 MB (shared dependencies)
- Fast deploys, reusable layer

---

## Quick Start - 2 Steps

### Step 1: Create Function Package (Lightweight)

```powershell
cd "C:\Users\nealg\Nfl Predictive Model\NFLPredictiveModel\PredictiveDataModel"
.\create_lambda_package_with_layer.ps1
```

**Output:** `playerimpact-lambda-light.zip` (~100 KB)

### Step 2: Create Lambda Layer (One Time)

```powershell
.\create_lambda_layer.ps1
```

**Output:** `python-dependencies-layer.zip` (~150 MB)

---

## Deployment Instructions

### A. Deploy Lambda Layer (One Time Only)

#### AWS Console:
1. Go to **Lambda** → **Layers** → **Create layer**
2. **Name:** `PlayerImpactDependencies`
3. **Description:** `Python 3.11 dependencies for NFL predictions (pandas, numpy, boto3)`
4. **Upload:** `python-dependencies-layer.zip`
5. **Compatible runtimes:** `Python 3.11`
6. Click **Create**

#### AWS CLI:
```bash
aws lambda publish-layer-version \
  --layer-name PlayerImpactDependencies \
  --description "Python dependencies for PlayerImpact" \
  --zip-file fileb://python-dependencies-layer.zip \
  --compatible-runtimes python3.11 \
  --region us-east-1
```

**Note the Layer ARN** from output - you'll need it!

---

### B. Deploy Lambda Function

#### AWS Console:
1. Go to **Lambda** → **Create function**
2. **Function name:** `PlayerImpactProcessor`
3. **Runtime:** `Python 3.11`
4. **Architecture:** `x86_64`
5. Create function

6. **Upload code:**
   - Code tab → Upload from → .zip file
   - Select `playerimpact-lambda-light.zip`
   - Save

7. **Attach Layer:**
   - Configuration → Layers → Add a layer
   - Choose **Custom layers**
   - Select `PlayerImpactDependencies`
   - Select latest version
   - Add

8. **Configure:**
   - Memory: 512 MB (enough for pandas)
   - Timeout: 300 seconds (5 min)
   - Handler: `PlayerImpactFeature.lambda_handler`

9. **Environment variables:**
   ```
   SPORTRADAR_API_KEY=bJWOnSi5MAUjzTVHr8gVELZIugdi1IHkVXUMT0Xm
   (Optional: Supabase vars if using DB)
   ```

10. **IAM Role** - Add S3 permissions:
    ```json
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::sportsdatacollection",
        "arn:aws:s3:::sportsdatacollection/*"
      ]
    }
    ```

#### AWS CLI:
```bash
# Create function
aws lambda create-function \
  --function-name PlayerImpactProcessor \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/lambda-s3-role \
  --handler PlayerImpactFeature.lambda_handler \
  --zip-file fileb://playerimpact-lambda-light.zip \
  --timeout 300 \
  --memory-size 512

# Attach layer (use ARN from layer creation)
aws lambda update-function-configuration \
  --function-name PlayerImpactProcessor \
  --layers arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:layer:PlayerImpactDependencies:1
```

---

## Testing

### Test Event:
```json
{
  "team_a": "KC",
  "team_b": "GB", 
  "season": 2025
}
```

### Expected Response:
```json
{
  "statusCode": 200,
  "body": {
    "success": true,
    "data": {
      "team_a_total_impact": 18.45,
      "team_b_total_impact": 16.23,
      "normalized_differential": 0.111,
      "advantage": "team_a"
    }
  }
}
```

---

## Updating Your Code

When you change Python code (not dependencies):

1. **Update only function code:**
   ```powershell
   .\create_lambda_package_with_layer.ps1
   ```

2. **Upload light ZIP** (fast!)
   - AWS Console: Upload `playerimpact-lambda-light.zip`
   - Or CLI:
     ```bash
     aws lambda update-function-code \
       --function-name PlayerImpactProcessor \
       --zip-file fileb://playerimpact-lambda-light.zip
     ```

**No need to re-upload layer!** Layer is reused.

---

## Updating Dependencies

If you need to add/update Python packages:

1. **Recreate layer:**
   ```powershell
   .\create_lambda_layer.ps1
   ```

2. **Publish new layer version:**
   ```bash
   aws lambda publish-layer-version \
     --layer-name PlayerImpactDependencies \
     --zip-file fileb://python-dependencies-layer.zip \
     --compatible-runtimes python3.11
   ```

3. **Update function to use new layer version:**
   - Console: Layers → Edit → Select new version
   - CLI:
     ```bash
     aws lambda update-function-configuration \
       --function-name PlayerImpactProcessor \
       --layers arn:aws:lambda:REGION:ACCOUNT:layer:PlayerImpactDependencies:2
     ```

---

## Layer Contents

**Layer includes:**
- pandas (data processing)
- numpy (numerical operations)
- boto3 (AWS SDK for S3)
- botocore
- requests (HTTP for Sportradar API)
- pg8000 (Supabase/PostgreSQL)
- python-dateutil
- pytz (timezone support)

**Function code includes:**
- S3DataLoader
- PositionMapper
- PlayerWeightAssigner
- MaddenRatingMapper
- InjuryImpactCalculator
- SportradarClient
- SupabaseStorage
- PlayerImpactFeature

---

## File Sizes Comparison

| Approach | Function ZIP | Layer ZIP | Total | Upload Time |
|----------|-------------|-----------|-------|-------------|
| **Without Layer** | 150-200 MB | - | 150-200 MB | ~5-10 min |
| **With Layer** | ~100 KB | ~150 MB | ~150 MB | ~30 sec (code updates) |

**Benefits:**
- ✅ 99.9% smaller code uploads
- ✅ Faster iterations
- ✅ Reuse layer across functions
- ✅ No dependency conflicts

---

## Troubleshooting

### "Module not found" error
- **Issue:** Layer not attached or wrong Python version
- **Fix:** Verify layer is attached and using Python 3.11

### "Unable to import pandas"
- **Issue:** Layer architecture mismatch (ARM vs x86)
- **Fix:** Ensure both function and layer use `x86_64`

### Layer too large (>250 MB)
- **Issue:** Uncompressed size limit
- **Fix:** Remove unused dependencies or split into multiple layers

### Import path errors
- **Issue:** Layer structure incorrect
- **Fix:** Ensure layer has `python/` folder at root

---

## AWS CLI Quick Reference

```bash
# List layers
aws lambda list-layers

# Get layer versions
aws lambda list-layer-versions --layer-name PlayerImpactDependencies

# Delete old layer version
aws lambda delete-layer-version \
  --layer-name PlayerImpactDependencies \
  --version-number 1

# List functions using layer
aws lambda list-functions --query "Functions[?Layers[?contains(Arn, 'PlayerImpactDependencies')]]"
```

---

## Best Practices

1. **Version your layers** - Keep old versions for rollback
2. **Test locally first** - Use virtual env with same packages
3. **Monitor size** - Keep layers under 200 MB uncompressed
4. **Reuse layers** - Attach same layer to multiple functions
5. **Document dependencies** - Track what's in each layer version

---

## Next Steps

1. ✅ Run `create_lambda_layer.ps1` (one time)
2. ✅ Deploy layer to AWS
3. ✅ Run `create_lambda_package_with_layer.ps1`
4. ✅ Deploy lightweight function
5. ✅ Attach layer to function
6. ✅ Test with sample teams

**You're now deploying with Lambda Layers! Much faster iterations.** 🎯

