# PowerShell Script to Create PlayerImpactCalculator Lambda Deployment Package
# For Windows users

Write-Host "================================" -ForegroundColor Cyan
Write-Host "PlayerImpactCalculator Lambda Package Creator" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Clean up old package
if (Test-Path "lambda_package") {
    Write-Host "Cleaning up old package directory..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force lambda_package
}

if (Test-Path "playerimpact-lambda.zip") {
    Write-Host "Removing old ZIP file..." -ForegroundColor Yellow
    Remove-Item -Force playerimpact-lambda.zip
}

# Create fresh directory
Write-Host "Creating package directory..." -ForegroundColor Green
New-Item -ItemType Directory lambda_package | Out-Null

# Copy Python modules from PlayerImpactCalculator
Write-Host "Copying PlayerImpactCalculator modules..." -ForegroundColor Green
$modules = @(
    "PlayerImpactCalculator\S3DataLoader.py",
    "PlayerImpactCalculator\PositionMapper.py",
    "PlayerImpactCalculator\PlayerWeightAssigner.py",
    "PlayerImpactCalculator\MaddenRatingMapper.py",
    "PlayerImpactCalculator\InjuryImpactCalculator.py",
    "PlayerImpactCalculator\SportradarClient.py",
    "PlayerImpactCalculator\SupabaseStorage.py",
    "PlayerImpactCalculator\game_processor.py",
    "PlayerImpactCalculator\__init__.py"
)

foreach ($module in $modules) {
    if (Test-Path $module) {
        Copy-Item $module lambda_package\
        Write-Host "  [OK] $module" -ForegroundColor Gray
    } else {
        Write-Host "  [FAIL] $module (not found)" -ForegroundColor Red
    }
}

# Copy PlayerImpactFeature from PredictionAPILambda
Write-Host "Copying PlayerImpactFeature..." -ForegroundColor Green
if (Test-Path "PredictionAPILambda\PlayerImpactFeature.py") {
    Copy-Item "PredictionAPILambda\PlayerImpactFeature.py" lambda_package\
    Write-Host "  [OK] PlayerImpactFeature.py" -ForegroundColor Gray
} else {
    Write-Host "  [FAIL] PlayerImpactFeature.py (not found)" -ForegroundColor Red
}

# Install Python dependencies
Write-Host ""
Write-Host "Installing Python dependencies..." -ForegroundColor Green
Write-Host "(This may take a few minutes)" -ForegroundColor Yellow

$dependencies = @(
    "requests",
    "boto3",
    "pandas",
    "numpy",
    "pg8000"
)

foreach ($dep in $dependencies) {
    Write-Host "  Installing $dep..." -ForegroundColor Gray
    pip install --target lambda_package --quiet $dep
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] $dep installed" -ForegroundColor Gray
    } else {
        Write-Host "  [FAIL] $dep failed to install" -ForegroundColor Red
    }
}

# Create ZIP file
Write-Host ""
Write-Host "Creating ZIP file..." -ForegroundColor Green
Compress-Archive -Path lambda_package\* -DestinationPath playerimpact-lambda.zip -Force

# Get file size
$zipSize = (Get-Item playerimpact-lambda.zip).Length / 1MB
$zipSizeFormatted = [math]::Round($zipSize, 2)

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "[SUCCESS] Lambda package created successfully!" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Package: playerimpact-lambda.zip" -ForegroundColor White
Write-Host "Size: $zipSizeFormatted MB" -ForegroundColor White
Write-Host ""

# Check if size is too large for direct upload
if ($zipSize -gt 50) {
    Write-Host "WARNING: Package is larger than 50MB" -ForegroundColor Yellow
    Write-Host "You must upload to S3 first, then deploy to Lambda from S3" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor Cyan
    Write-Host "  aws s3 cp playerimpact-lambda.zip s3://sportsdatacollection/lambda-packages/" -ForegroundColor Gray
    Write-Host "  aws lambda update-function-code --function-name PlayerImpactProcessor --s3-bucket sportsdatacollection --s3-key lambda-packages/playerimpact-lambda.zip" -ForegroundColor Gray
} else {
    Write-Host "Package size is OK for direct Lambda upload" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Go to AWS Lambda console" -ForegroundColor Gray
    Write-Host "2. Create or select your function" -ForegroundColor Gray
    Write-Host "3. Upload playerimpact-lambda.zip" -ForegroundColor Gray
    Write-Host "4. Set environment variables (see LAMBDA_DEPLOYMENT.md)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Cleanup:" -ForegroundColor Cyan
Write-Host "The lambda_package folder can be deleted if desired" -ForegroundColor Gray
Write-Host ""

# Optional: Clean up package directory
$cleanup = Read-Host "Delete lambda_package folder? (y/n)"
if ($cleanup -eq "y" -or $cleanup -eq "Y") {
    Remove-Item -Recurse -Force lambda_package
    Write-Host "[OK] Cleaned up lambda_package folder" -ForegroundColor Green
}

Write-Host ""
Write-Host "Done! Package ready for deployment." -ForegroundColor Green
