# PowerShell Script - Create Lambda Layer with Python Dependencies
# This layer contains: pandas, numpy, boto3, requests, pg8000

Write-Host "================================" -ForegroundColor Cyan
Write-Host "Lambda Layer Creator - Python 3.11 Dependencies" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Clean up
if (Test-Path "layer_package") {
    Write-Host "Cleaning up old layer directory..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force layer_package
}

if (Test-Path "python-dependencies-layer.zip") {
    Write-Host "Removing old layer ZIP..." -ForegroundColor Yellow
    Remove-Item -Force python-dependencies-layer.zip
}

# Create layer structure
# Lambda expects: python/lib/python3.11/site-packages/
Write-Host "Creating layer directory structure..." -ForegroundColor Green
New-Item -ItemType Directory -Path "layer_package\python" | Out-Null

# Install dependencies to layer
Write-Host ""
Write-Host "Installing Python dependencies to layer..." -ForegroundColor Green
Write-Host "(This will take several minutes - pandas and numpy are large)" -ForegroundColor Yellow
Write-Host ""

$dependencies = @(
    "pandas",
    "numpy", 
    "boto3",
    "botocore",
    "requests",
    "pg8000",
    "python-dateutil",
    "pytz"
)

foreach ($dep in $dependencies) {
    Write-Host "Installing $dep..." -ForegroundColor Cyan
    pip install --target layer_package\python --platform manylinux2014_x86_64 --only-binary=:all: $dep
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] $dep" -ForegroundColor Green
    } else {
        Write-Host "  [WARNING] $dep - trying alternative install" -ForegroundColor Yellow
        pip install --target layer_package\python $dep
    }
}

# Create ZIP for layer
Write-Host ""
Write-Host "Creating layer ZIP file..." -ForegroundColor Green
Write-Host "(This may take a minute - compressing large files)" -ForegroundColor Yellow
Compress-Archive -Path layer_package\* -DestinationPath python-dependencies-layer.zip -Force

# Get size
$layerSize = (Get-Item python-dependencies-layer.zip).Length / 1MB
$layerSizeFormatted = [math]::Round($layerSize, 2)

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "[SUCCESS] Lambda Layer created!" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Layer ZIP: python-dependencies-layer.zip" -ForegroundColor White
Write-Host "Size: $layerSizeFormatted MB" -ForegroundColor White
Write-Host ""

if ($layerSize -gt 250) {
    Write-Host "WARNING: Layer is close to 250MB limit" -ForegroundColor Red
    Write-Host "Consider removing unused dependencies" -ForegroundColor Yellow
}

Write-Host "DEPLOYMENT STEPS:" -ForegroundColor Cyan
Write-Host ""
Write-Host "Option 1 - AWS Console:" -ForegroundColor Yellow
Write-Host "1. Go to Lambda > Layers > Create Layer" -ForegroundColor Gray
Write-Host "2. Name: PlayerImpactDependencies" -ForegroundColor Gray
Write-Host "3. Upload python-dependencies-layer.zip" -ForegroundColor Gray
Write-Host "4. Compatible runtimes: Python 3.11" -ForegroundColor Gray
Write-Host "5. Create layer" -ForegroundColor Gray
Write-Host ""
Write-Host "Option 2 - AWS CLI:" -ForegroundColor Yellow
Write-Host 'aws lambda publish-layer-version \' -ForegroundColor Gray
Write-Host '  --layer-name PlayerImpactDependencies \' -ForegroundColor Gray
Write-Host '  --description "Python dependencies for PlayerImpact" \' -ForegroundColor Gray
Write-Host '  --zip-file fileb://python-dependencies-layer.zip \' -ForegroundColor Gray
Write-Host '  --compatible-runtimes python3.11' -ForegroundColor Gray
Write-Host ""
Write-Host "Then attach layer to your Lambda function:" -ForegroundColor Cyan
Write-Host "- Lambda > Configuration > Layers > Add Layer" -ForegroundColor Gray
Write-Host "- Select Custom Layer > PlayerImpactDependencies" -ForegroundColor Gray
Write-Host ""

# Cleanup
$cleanup = Read-Host "Delete layer_package folder? (y/n)"
if ($cleanup -eq "y" -or $cleanup -eq "Y") {
    Remove-Item -Recurse -Force layer_package
    Write-Host "[OK] Cleaned up" -ForegroundColor Green
}

Write-Host ""
Write-Host "Done! Layer ready for Lambda deployment." -ForegroundColor Green

