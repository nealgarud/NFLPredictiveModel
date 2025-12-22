# Create deployment ZIP for manual upload to Lambda

Write-Host "`nCreating Lambda deployment package..." -ForegroundColor Cyan
Write-Host "============================================================"

$SOURCE_DIR = "chatbot_final"
$ZIP_FILE = "chatbot-deployment.zip"

# Step 1: Check source directory
Write-Host "`nStep 1: Checking source directory..." -ForegroundColor Yellow
if (-not (Test-Path $SOURCE_DIR)) {
    Write-Host "   ❌ Source directory '$SOURCE_DIR' not found!" -ForegroundColor Red
    exit 1
}
Write-Host "   ✅ Source directory found"

# Step 2: Create ZIP
Write-Host "`nStep 2: Creating ZIP file..." -ForegroundColor Yellow
if (Test-Path $ZIP_FILE) {
    Remove-Item $ZIP_FILE -Force
}

Push-Location $SOURCE_DIR
Compress-Archive -Path * -DestinationPath "..\$ZIP_FILE" -Force
Pop-Location

$zipFile = Get-Item $ZIP_FILE
$sizeMB = [math]::Round($zipFile.Length / 1MB, 2)

Write-Host "   ✅ Created $ZIP_FILE ($sizeMB MB)"

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "✅ DEPLOYMENT PACKAGE READY!" -ForegroundColor Green
Write-Host "============================================================"

Write-Host "`nManual Deployment Steps:" -ForegroundColor Cyan
Write-Host "1. Go to: https://console.aws.amazon.com/lambda"
Write-Host "2. Find your function: ChatbotPredictiveAPI"
Write-Host "3. Click 'Upload from' → '.zip file'"
Write-Host "4. Select: $ZIP_FILE"
Write-Host "5. Click 'Save'"
Write-Host "6. Wait for deployment to complete"
Write-Host "7. Test with the prediction!"

Write-Host "`nFile location:" -ForegroundColor Yellow
Write-Host "   $(Get-Location)\$ZIP_FILE"

Write-Host "`n"

