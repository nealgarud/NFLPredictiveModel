# Deploy Simple Chatbot Lambda (No FastAPI)
# Uses the chatbot_final version with direct Lambda handler

Write-Host "`nNFL Chatbot Lambda Deployment (Simple Version)" -ForegroundColor Cyan
Write-Host "============================================================"

# Configuration
$LAMBDA_FUNCTION_NAME = "ChatbotPredictiveAPI"
$SOURCE_DIR = "chatbot_final"
$ZIP_FILE = "chatbot-deployment.zip"

# Step 1: Check if source directory exists
Write-Host "`nStep 1: Checking source directory..." -ForegroundColor Yellow
if (-not (Test-Path $SOURCE_DIR)) {
    Write-Host "   ❌ Source directory '$SOURCE_DIR' not found!" -ForegroundColor Red
    exit 1
}
Write-Host "   ✅ Source directory found"

# Step 2: Create ZIP file
Write-Host "`nStep 2: Creating deployment package..." -ForegroundColor Yellow
if (Test-Path $ZIP_FILE) {
    Remove-Item $ZIP_FILE -Force
    Write-Host "   ✅ Removed old ZIP file"
}

Push-Location $SOURCE_DIR
try {
    Compress-Archive -Path * -DestinationPath "..\$ZIP_FILE" -Force
    Write-Host "   ✅ Created $ZIP_FILE"
} catch {
    Write-Host "   ❌ Failed to create ZIP file" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location

# Step 3: Get file size
$zipFile = Get-Item $ZIP_FILE
$sizeMB = [math]::Round($zipFile.Length / 1MB, 2)

Write-Host "`nPackage Information:" -ForegroundColor Cyan
Write-Host "   File: $ZIP_FILE"
Write-Host "   Size: $sizeMB MB"

# Step 4: Deploy to Lambda
Write-Host "`nStep 3: Deploying to AWS Lambda..." -ForegroundColor Yellow
Write-Host "   Function: $LAMBDA_FUNCTION_NAME"

try {
    # Update Lambda function code
    aws lambda update-function-code `
        --function-name $LAMBDA_FUNCTION_NAME `
        --zip-file "fileb://$ZIP_FILE" `
        --no-cli-pager
    
    Write-Host "   ✅ Lambda function updated successfully!" -ForegroundColor Green
    
    # Wait for update to complete
    Write-Host "`nStep 4: Waiting for deployment to complete..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
    
    # Get function info
    $functionInfo = aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --query 'Configuration.[LastModified,State,LastUpdateStatus]' --output text
    Write-Host "   ✅ Deployment complete!"
    Write-Host "   Status: $functionInfo"
    
} catch {
    Write-Host "   ❌ Deployment failed!" -ForegroundColor Red
    Write-Host "   Error: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "✅ DEPLOYMENT SUCCESSFUL!" -ForegroundColor Green
Write-Host "============================================================"

Write-Host "`nNext Steps:" -ForegroundColor Cyan
Write-Host "1. Test the Lambda function in AWS Console"
Write-Host "2. Use this test event:"
Write-Host @"
{
  "rawPath": "/predict",
  "requestContext": {
    "http": {
      "method": "POST"
    }
  },
  "body": "{\"team_a\": \"NE\", \"team_b\": \"NYJ\", \"spread\": -5.5, \"team_a_home\": true, \"seasons\": [2024, 2025]}"
}
"@ -ForegroundColor Gray

Write-Host "`n3. Or test via API Gateway:"
Write-Host "   https://bck79rw0nf.execute-api.us-east-1.amazonaws.com/Deployment/predict" -ForegroundColor Gray

Write-Host "`nReady to test!`n" -ForegroundColor Green



