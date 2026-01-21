# PowerShell Script - Lambda Package WITHOUT dependencies (using Layer)
# Creates lightweight ZIP - dependencies go in Lambda Layer

Write-Host "================================" -ForegroundColor Cyan
Write-Host "PlayerImpactCalculator Lambda Package (Layer Version)" -ForegroundColor Cyan
Write-Host "Dependencies will be in Lambda Layer - ZIP will be MUCH smaller!" -ForegroundColor Yellow
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Clean up old package
if (Test-Path "lambda_package") {
    Write-Host "Cleaning up old package directory..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force lambda_package
}

if (Test-Path "playerimpact-lambda-light.zip") {
    Write-Host "Removing old ZIP file..." -ForegroundColor Yellow
    Remove-Item -Force playerimpact-lambda-light.zip
}

# Create fresh directory
Write-Host "Creating package directory..." -ForegroundColor Green
New-Item -ItemType Directory lambda_package | Out-Null

# Copy ONLY Python modules (NO dependencies)
Write-Host "Copying Python modules (code only)..." -ForegroundColor Green
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

# Copy PlayerImpactFeature
Write-Host "Copying PlayerImpactFeature..." -ForegroundColor Green
if (Test-Path "PredictionAPILambda\PlayerImpactFeature.py") {
    Copy-Item "PredictionAPILambda\PlayerImpactFeature.py" lambda_package\
    Write-Host "  [OK] PlayerImpactFeature.py" -ForegroundColor Gray
}

# Create lightweight ZIP (NO heavy dependencies)
Write-Host ""
Write-Host "Creating lightweight ZIP file..." -ForegroundColor Green
Write-Host "(Dependencies will be in Lambda Layer)" -ForegroundColor Yellow
Compress-Archive -Path lambda_package\* -DestinationPath playerimpact-lambda-light.zip -Force

# Get file size
$zipSize = (Get-Item playerimpact-lambda-light.zip).Length / 1KB
$zipSizeFormatted = [math]::Round($zipSize, 2)

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "[SUCCESS] Lightweight package created!" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Package: playerimpact-lambda-light.zip" -ForegroundColor White
Write-Host "Size: $zipSizeFormatted KB (lightweight!)" -ForegroundColor Green
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Cyan
Write-Host "1. Create Lambda Layer with dependencies (pandas, numpy, etc.)" -ForegroundColor White
Write-Host "   See: create_lambda_layer.ps1" -ForegroundColor Gray
Write-Host "2. Upload this lightweight ZIP to Lambda" -ForegroundColor White
Write-Host "3. Attach the Layer to your Lambda function" -ForegroundColor White
Write-Host ""
Write-Host "Benefits:" -ForegroundColor Yellow
Write-Host "- Faster uploads (smaller file)" -ForegroundColor Gray
Write-Host "- Faster deployments" -ForegroundColor Gray
Write-Host "- Reuse layer across multiple functions" -ForegroundColor Gray
Write-Host ""

# Cleanup
$cleanup = Read-Host "Delete lambda_package folder? (y/n)"
if ($cleanup -eq "y" -or $cleanup -eq "Y") {
    Remove-Item -Recurse -Force lambda_package
    Write-Host "[OK] Cleaned up" -ForegroundColor Green
}

Write-Host ""
Write-Host "Done! Now create the Lambda Layer with dependencies." -ForegroundColor Green
Write-Host "Run: .\create_lambda_layer.ps1" -ForegroundColor Cyan

