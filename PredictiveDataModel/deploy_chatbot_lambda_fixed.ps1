# Deploy Chatbot Lambda Package (Linux Compatible)
# This script creates a deployment package with Lambda-compatible binaries

Write-Host "`nNFL Chatbot Lambda Deployment Script (Linux Compatible)" -ForegroundColor Cyan
Write-Host "============================================================"

# Step 1: Clean up old deployment folder
Write-Host "`nStep 1: Preparing deployment folder..." -ForegroundColor Yellow
if (Test-Path "chatbot_lambda") {
    Remove-Item -Recurse -Force chatbot_lambda
    Write-Host "   Cleaned up old deployment folder"
}
New-Item -ItemType Directory -Path chatbot_lambda | Out-Null
Write-Host "   Created chatbot_lambda folder"

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
        Write-Host "   Copied $file"
    } else {
        Write-Host "   Missing: $file" -ForegroundColor Red
        exit 1
    }
}

# Step 3: Install dependencies for Lambda (Linux)
Write-Host "`nStep 3: Installing Lambda-compatible dependencies..." -ForegroundColor Yellow
Write-Host "   Using --platform manylinux2014_x86_64 for Linux compatibility" -ForegroundColor Gray

# Create requirements.txt for Lambda
$requirements = "fastapi==0.104.1`npydantic==2.5.0`nmangum==0.17.0`npg8000==1.30.3"
Set-Content -Path "chatbot_lambda/requirements.txt" -Value $requirements
Write-Host "   Created requirements.txt"

# Install dependencies with Linux platform
Push-Location chatbot_lambda
try {
    # Install for Linux platform
    Write-Host "   Installing packages (this may take 2-3 minutes)..." -ForegroundColor Gray
    pip install -r requirements.txt `
        --platform manylinux2014_x86_64 `
        --target . `
        --implementation cp `
        --python-version 3.11 `
        --only-binary=:all: `
        --upgrade `
        --quiet 2>&1 | Out-Null
    Write-Host "   Installed Python dependencies for Linux"
} catch {
    Write-Host "   Warning: Some packages may have compatibility notes" -ForegroundColor Yellow
}
Pop-Location

# Step 4: Clean up unnecessary files (reduce size)
Write-Host "`nStep 4: Cleaning up unnecessary files..." -ForegroundColor Yellow
$cleanupPatterns = @("*.pyc", "__pycache__", "*.dist-info", "tests", "*.egg-info", "*.whl")
foreach ($pattern in $cleanupPatterns) {
    Get-ChildItem -Path chatbot_lambda -Recurse -Include $pattern -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host "   Removed unnecessary files"

# Step 5: Create deployment ZIP
Write-Host "`nStep 5: Creating deployment package..." -ForegroundColor Yellow
if (Test-Path "chatbot-api-lambda-linux.zip") {
    Remove-Item "chatbot-api-lambda-linux.zip" -Force
}

Push-Location chatbot_lambda
try {
    Compress-Archive -Path * -DestinationPath ..\chatbot-api-lambda-linux.zip -Force
    Write-Host "   Created chatbot-api-lambda-linux.zip"
} catch {
    Write-Host "   Failed to create ZIP file" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location

# Step 6: Get file size
$zipFile = Get-Item "chatbot-api-lambda-linux.zip"
$sizeMB = [math]::Round($zipFile.Length / 1MB, 2)

Write-Host "`nDeployment package ready!" -ForegroundColor Green
Write-Host "============================================================"
Write-Host "File: chatbot-api-lambda-linux.zip" -ForegroundColor Cyan
Write-Host "Size: $sizeMB MB" -ForegroundColor Cyan
Write-Host "Platform: Linux (manylinux2014_x86_64)" -ForegroundColor Cyan

if ($sizeMB -gt 50) {
    Write-Host "`nWarning: File is larger than 50 MB" -ForegroundColor Yellow
    Write-Host "   You'll need to upload via S3" -ForegroundColor Yellow
} else {
    Write-Host "`nFile size is under 50 MB - you can upload directly!" -ForegroundColor Green
}

Write-Host "`nNext Steps:" -ForegroundColor Cyan
Write-Host "1. Go to Lambda Console: ChatbotPredictionAPI"
Write-Host "2. Upload: chatbot-api-lambda-linux.zip"
Write-Host "3. Wait for upload to complete"
Write-Host "4. Test with: /health endpoint"

Write-Host "`nReady to deploy!`n" -ForegroundColor Green















