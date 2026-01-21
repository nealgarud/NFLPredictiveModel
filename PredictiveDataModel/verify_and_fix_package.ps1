# Verify and fix Lambda package structure
# This ensures PlayerImpactFeature.py is at the root of the ZIP

Write-Host "Verifying Lambda package structure..." -ForegroundColor Cyan
Write-Host ""

# Check if ZIP exists
if (-not (Test-Path "playerimpact-lambda-light.zip")) {
    Write-Host "[ERROR] playerimpact-lambda-light.zip not found!" -ForegroundColor Red
    Write-Host "Run: .\create_lambda_package_with_layer.ps1 first" -ForegroundColor Yellow
    exit 1
}

# Extract and check structure
Write-Host "Extracting ZIP to verify structure..." -ForegroundColor Green
if (Test-Path "temp_verify") {
    Remove-Item -Recurse -Force temp_verify
}
Expand-Archive -Path playerimpact-lambda-light.zip -DestinationPath temp_verify

# Check for PlayerImpactFeature.py at root
Write-Host ""
Write-Host "Checking file structure:" -ForegroundColor Cyan
$files = Get-ChildItem -Path temp_verify -File -Name
foreach ($file in $files) {
    if ($file -eq "PlayerImpactFeature.py") {
        Write-Host "[OK] $file" -ForegroundColor Green
    } else {
        Write-Host "     $file" -ForegroundColor Gray
    }
}

if (-not ($files -contains "PlayerImpactFeature.py")) {
    Write-Host ""
    Write-Host "[ERROR] PlayerImpactFeature.py NOT found at ZIP root!" -ForegroundColor Red
    Write-Host "This is why Lambda can't import it." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Fix: Recreating package with correct structure..." -ForegroundColor Cyan
    
    # Clean up and recreate
    Remove-Item -Recurse -Force temp_verify
    
    # Create correct package
    if (Test-Path "lambda_package") {
        Remove-Item -Recurse -Force lambda_package
    }
    New-Item -ItemType Directory lambda_package | Out-Null
    
    # Copy PlayerImpactCalculator modules
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
        }
    }
    
    # CRITICAL: Copy PlayerImpactFeature to root
    if (Test-Path "PredictionAPILambda\PlayerImpactFeature.py") {
        Copy-Item "PredictionAPILambda\PlayerImpactFeature.py" lambda_package\
        Write-Host "[OK] Copied PlayerImpactFeature.py to package root" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Source file not found: PredictionAPILambda\PlayerImpactFeature.py" -ForegroundColor Red
        exit 1
    }
    
    # Create new ZIP
    if (Test-Path "playerimpact-lambda-light.zip") {
        Remove-Item playerimpact-lambda-light.zip
    }
    Compress-Archive -Path lambda_package\* -DestinationPath playerimpact-lambda-light.zip
    
    Write-Host "[SUCCESS] Fixed package created: playerimpact-lambda-light.zip" -ForegroundColor Green
    
} else {
    Write-Host ""
    Write-Host "[OK] Package structure is correct!" -ForegroundColor Green
    Write-Host "PlayerImpactFeature.py is at ZIP root" -ForegroundColor Gray
}

# Cleanup
Remove-Item -Recurse -Force temp_verify

Write-Host ""
Write-Host "Expected ZIP structure:" -ForegroundColor Cyan
Write-Host "playerimpact-lambda-light.zip" -ForegroundColor White
Write-Host "├── PlayerImpactFeature.py          <-- MUST be at root!" -ForegroundColor Yellow
Write-Host "├── S3DataLoader.py" -ForegroundColor Gray
Write-Host "├── PositionMapper.py" -ForegroundColor Gray
Write-Host "├── PlayerWeightAssigner.py" -ForegroundColor Gray
Write-Host "└── ... (other modules)" -ForegroundColor Gray
Write-Host ""
Write-Host "Now upload playerimpact-lambda-light.zip to Lambda" -ForegroundColor Green

