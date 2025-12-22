# Deploy Chatbot Lambda Package
# This script creates a deployment package for AWS Lambda

Write-Host "`nNFL Chatbot Lambda Deployment Script" -ForegroundColor Cyan
Write-Host "============================================================"

# Step 1: Clean up old deployment folder
Write-Host "`nStep 1: Preparing deployment folder..." -ForegroundColor Yellow
if (Test-Path "chatbot_lambda") {
    Remove-Item -Recurse -Force chatbot_lambda
    Write-Host "   ✅ Cleaned up old deployment folder"
}
New-Item -ItemType Directory -Path chatbot_lambda | Out-Null
Write-Host "   ✅ Created chatbot_lambda folder"

# Step 2: Copy core files
Write-Host "`nStep 2: Copying core files..." -ForegroundColor Yellow
$coreFiles = @(
    "api_handler.py",
    "SpreadPredictionCalculator.py",
    "DatabaseConnection.py"
)

foreach ($file in $coreFiles) {
    if (Test-Path $file) {
        Copy-Item $file chatbot_lambda/
        Write-Host "   ✅ Copied $file"
    } else {
        Write-Host "   ❌ Missing: $file" -ForegroundColor Red
        exit 1
    }
}

# Step 3: Install dependencies
Write-Host "`nStep 3: Installing dependencies..." -ForegroundColor Yellow
Write-Host "   (This may take 1-2 minutes...)" -ForegroundColor Gray

# Create requirements.txt for Lambda
$requirements = "fastapi==0.104.1`npydantic==2.5.0`nmangum==0.17.0`npg8000==1.30.3"

Set-Content -Path "chatbot_lambda/requirements.txt" -Value $requirements
Write-Host "   ✅ Created requirements.txt"

# Install dependencies to chatbot_lambda folder
Push-Location chatbot_lambda
try {
    pip install -r requirements.txt -t . --upgrade --quiet 2>&1 | Out-Null
    Write-Host "   ✅ Installed Python dependencies"
} catch {
    Write-Host "   ⚠️  Some packages may have warnings (this is usually okay)" -ForegroundColor Yellow
}
Pop-Location

# Step 4: Clean up unnecessary files (reduce size)
Write-Host "`nStep 4: Cleaning up unnecessary files..." -ForegroundColor Yellow
$cleanupPatterns = @("*.pyc", "__pycache__", "*.dist-info", "tests", "*.egg-info")
foreach ($pattern in $cleanupPatterns) {
    Get-ChildItem -Path chatbot_lambda -Recurse -Include $pattern -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host "   ✅ Removed unnecessary files"

# Step 5: Create deployment ZIP
Write-Host "`nStep 5: Creating deployment package..." -ForegroundColor Yellow
if (Test-Path "chatbot-api-lambda.zip") {
    Remove-Item "chatbot-api-lambda.zip" -Force
}

Push-Location chatbot_lambda
try {
    Compress-Archive -Path * -DestinationPath ..\chatbot-api-lambda.zip -Force
    Write-Host "   ✅ Created chatbot-api-lambda.zip"
} catch {
    Write-Host "   ❌ Failed to create ZIP file" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location

# Step 6: Get file size
$zipFile = Get-Item "chatbot-api-lambda.zip"
$sizeMB = [math]::Round($zipFile.Length / 1MB, 2)

Write-Host "`nDeployment package ready!" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "File: chatbot-api-lambda.zip" -ForegroundColor Cyan
Write-Host "Size: $sizeMB MB" -ForegroundColor Cyan

if ($sizeMB -gt 50) {
    Write-Host "`n⚠️  Warning: File is larger than 50 MB" -ForegroundColor Yellow
    Write-Host "   You'll need to upload via S3 instead of direct upload" -ForegroundColor Yellow
    Write-Host "   See: https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-package.html"
} else {
    Write-Host "`n✅ File size is under 50 MB - you can upload directly to Lambda!" -ForegroundColor Green
}

Write-Host "`nNext Steps:" -ForegroundColor Cyan
Write-Host "1. Go to AWS Lambda Console: https://console.aws.amazon.com/lambda"
Write-Host "2. Create new function: ChatbotPredictionAPI"
Write-Host "3. Runtime: Python 3.11"
Write-Host "4. Upload: chatbot-api-lambda.zip"
Write-Host "5. Set handler: api_handler.handler"
Write-Host "6. Add environment variables (Supabase credentials)"
Write-Host "7. Test with /health endpoint"

Write-Host "`nReady to deploy!`n" -ForegroundColor Green

