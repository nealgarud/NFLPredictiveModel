# deploy.ps1
# Prerequisites: AWS CLI configured, Docker Desktop running
# Run from NFLPredictiveModel/ folder

$AWS_ACCOUNT_ID = "838319850663"
$AWS_REGION     = "us-east-1"
$S3_BUCKET      = "nfl-predictive-model-artifacts"
$ECR_REPO_NAME  = "xgboost-prediction-lambda"
$XGBOOST_LAMBDA = "XGBoostPredictionLambda"
$BEDROCK_LAMBDA = "BedrockChatLambda"

$ErrorActionPreference = "Stop"

Write-Host "`n=== STEP 1: Upload model artifacts to S3 ===" -ForegroundColor Cyan
aws s3 cp "ML-Training/models/nfl_spread_model_latest.json" "s3://$S3_BUCKET/models/nfl_spread_model_latest.json"
aws s3 cp "ML-Training/models/feature_names.json" "s3://$S3_BUCKET/models/feature_names.json"
Write-Host "Model artifacts uploaded." -ForegroundColor Green

Write-Host "`n=== STEP 2: Create ECR repository (skip if exists) ===" -ForegroundColor Cyan
$repoExists = $false
try {
    aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION | Out-Null
    if ($LASTEXITCODE -eq 0) { $repoExists = $true }
} catch { $repoExists = $false }

if (-not $repoExists) {
    aws ecr create-repository --repository-name $ECR_REPO_NAME --region $AWS_REGION
    Write-Host "ECR repo created: $ECR_REPO_NAME" -ForegroundColor Green
} else {
    Write-Host "ECR repo already exists, skipping." -ForegroundColor Yellow
}

Write-Host "`n=== STEP 3: Authenticate Docker with ECR ===" -ForegroundColor Cyan
$ECR_URI = "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URI
Write-Host "Docker authenticated with ECR." -ForegroundColor Green

Write-Host "`n=== STEP 4: Build Docker image ===" -ForegroundColor Cyan
$IMAGE_TAG = "$ECR_URI/$ECR_REPO_NAME`:latest"
docker build --provenance=false -t $IMAGE_TAG "XGBoostPredictionLambda/"
Write-Host "Image built: $IMAGE_TAG" -ForegroundColor Green

Write-Host "`n=== STEP 5: Push image to ECR ===" -ForegroundColor Cyan
docker push $IMAGE_TAG
Write-Host "Image pushed to ECR." -ForegroundColor Green

Write-Host "`n=== STEP 6: Update XGBoostPredictionLambda ===" -ForegroundColor Cyan
$ROLE_ARN = "arn:aws:iam::838319850663:role/service-role/XGBoostPredictionLambda-role-3xb1zgyi"

$lambdaJson = ""
try {
    $lambdaJson = aws lambda get-function --function-name $XGBOOST_LAMBDA --region $AWS_REGION 2>&1 | Out-String
} catch { $lambdaJson = "ResourceNotFoundException" }

if ($lambdaJson -match "ResourceNotFoundException") {
    Write-Host "Lambda not found - creating as Image type..." -ForegroundColor Yellow
    aws lambda create-function --function-name $XGBOOST_LAMBDA --package-type Image --code "ImageUri=$IMAGE_TAG" --role $ROLE_ARN --timeout 30 --memory-size 512 --region $AWS_REGION
} elseif ($lambdaJson -match '"PackageType":\s*"Zip"') {
    Write-Host "Lambda is Zip type - deleting and recreating as Image type..." -ForegroundColor Yellow
    aws lambda delete-function --function-name $XGBOOST_LAMBDA --region $AWS_REGION
    Start-Sleep -Seconds 5
    aws lambda create-function --function-name $XGBOOST_LAMBDA --package-type Image --code "ImageUri=$IMAGE_TAG" --role $ROLE_ARN --timeout 30 --memory-size 512 --region $AWS_REGION
} else {
    aws lambda update-function-code --function-name $XGBOOST_LAMBDA --image-uri $IMAGE_TAG --region $AWS_REGION
}
Write-Host "XGBoostPredictionLambda updated." -ForegroundColor Green

Write-Host "`n=== STEP 7: Deploy BedrockChatLambda as zip ===" -ForegroundColor Cyan
Compress-Archive -Force -Path "BedrockChatLambda/lambda_function.py" -DestinationPath "BedrockChatLambda/deployment.zip"
aws lambda update-function-code --function-name $BEDROCK_LAMBDA --zip-file fileb://BedrockChatLambda/deployment.zip --region $AWS_REGION
Write-Host "BedrockChatLambda updated." -ForegroundColor Green

Write-Host "`n=== ALL DONE ===" -ForegroundColor Green
Write-Host "XGBoostPredictionLambda -> ECR container image"
Write-Host "BedrockChatLambda       -> zip deployment"
Write-Host ""
Write-Host "Next: set environment variables on both Lambdas in the AWS console"
Write-Host "  XGBoostPredictionLambda: S3_BUCKET, SUPABASE_DB_HOST, SUPABASE_DB_PASSWORD, SUPABASE_DB_NAME, SUPABASE_DB_USER, SUPABASE_DB_PORT"
Write-Host "  BedrockChatLambda: XGBOOST_LAMBDA_NAME=$XGBOOST_LAMBDA, BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0"
