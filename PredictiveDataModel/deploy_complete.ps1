# Complete Lambda Package - All Dependencies Included
# Uses Docker to build Linux-compatible binaries

Write-Host "`nBuilding Complete Lambda Package..." -ForegroundColor Cyan
Write-Host "============================================================"

# Check if Docker is available
$dockerAvailable = $null -ne (Get-Command docker -ErrorAction SilentlyContinue)

if (-not $dockerAvailable) {
    Write-Host "`nDocker not found. Using alternative method..." -ForegroundColor Yellow
    
    # Alternative: Download pre-built Lambda-compatible packages
    Write-Host "`nDownloading Lambda-compatible packages from PyPI..." -ForegroundColor Yellow
    
    # Clean up
    if (Test-Path "chatbot_complete") { Remove-Item -Recurse -Force chatbot_complete }
    New-Item -ItemType Directory -Path chatbot_complete | Out-Null
    
    # Copy core files
    Copy-Item api_handler.py chatbot_complete/
    Copy-Item SpreadPredictionCalculator.py chatbot_complete/
    Copy-Item DatabaseConnection.py chatbot_complete/
    Write-Host "Core files copied"
    
    # Install with specific platform
    Push-Location chatbot_complete
    
    # Install packages one by one with explicit platform
    Write-Host "Installing fastapi..."
    pip install fastapi==0.104.1 --platform manylinux2014_x86_64 --target . --only-binary=:all: --python-version 311 --implementation cp --quiet 2>&1 | Out-Null
    
    Write-Host "Installing pydantic..."
    pip install "pydantic==2.5.0" --platform manylinux2014_x86_64 --target . --only-binary=:all: --python-version 311 --implementation cp --quiet 2>&1 | Out-Null
    
    Write-Host "Installing mangum..."
    pip install mangum==0.17.0 --platform manylinux2014_x86_64 --target . --only-binary=:all: --python-version 311 --implementation cp --quiet 2>&1 | Out-Null
    
    Write-Host "Installing pg8000..."
    pip install pg8000==1.30.3 --target . --quiet 2>&1 | Out-Null
    
    Pop-Location
    
} else {
    Write-Host "`nUsing Docker to build Lambda-compatible package..." -ForegroundColor Green
    
    # Use Docker with Amazon Linux 2
    if (Test-Path "chatbot_complete") { Remove-Item -Recurse -Force chatbot_complete }
    New-Item -ItemType Directory -Path chatbot_complete | Out-Null
    
    # Copy core files
    Copy-Item api_handler.py chatbot_complete/
    Copy-Item SpreadPredictionCalculator.py chatbot_complete/
    Copy-Item DatabaseConnection.py chatbot_complete/
    
    # Create requirements file
    @"
fastapi==0.104.1
pydantic==2.5.0
mangum==0.17.0
pg8000==1.30.3
"@ | Set-Content chatbot_complete/requirements.txt
    
    # Build using Docker
    docker run --rm -v "${PWD}/chatbot_complete:/var/task" public.ecr.aws/lambda/python:3.11 pip install -r /var/task/requirements.txt -t /var/task/
}

# Clean up
Write-Host "Cleaning up unnecessary files..."
Get-ChildItem -Path chatbot_complete -Recurse -Include "*.pyc","__pycache__","*.dist-info","tests","*.egg-info" -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# Create ZIP
Write-Host "Creating deployment package..."
if (Test-Path "chatbot-complete.zip") { Remove-Item "chatbot-complete.zip" -Force }
Compress-Archive -Path chatbot_complete\* -DestinationPath chatbot-complete.zip -Force

$size = [math]::Round((Get-Item chatbot-complete.zip).Length / 1MB, 2)

Write-Host "`nPackage created: chatbot-complete.zip" -ForegroundColor Green
Write-Host "Size: $size MB" -ForegroundColor Cyan

if ($size -gt 50) {
    Write-Host "`nFile is larger than 50 MB - upload via S3:" -ForegroundColor Yellow
    Write-Host "1. Upload chatbot-complete.zip to your S3 bucket"
    Write-Host "2. In Lambda, use 'Upload from S3' option"
} else {
    Write-Host "`nFile is under 50 MB - can upload directly to Lambda!" -ForegroundColor Green
}

Write-Host "`nReady to deploy!`n" -ForegroundColor Green















