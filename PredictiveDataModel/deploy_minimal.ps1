# Minimal Lambda Package - Just Core Files + Pure Python Dependencies

Write-Host "`nCreating Minimal Lambda Package..." -ForegroundColor Cyan

# Clean up
if (Test-Path "chatbot_minimal") { Remove-Item -Recurse -Force chatbot_minimal }
New-Item -ItemType Directory -Path chatbot_minimal | Out-Null

# Copy core files
Copy-Item api_handler.py chatbot_minimal/
Copy-Item SpreadPredictionCalculator.py chatbot_minimal/
Copy-Item DatabaseConnection.py chatbot_minimal/

# Install ONLY pure Python packages (no binary dependencies)
Push-Location chatbot_minimal

# Just pg8000 (pure Python PostgreSQL driver)
pip install pg8000==1.30.3 -t . --quiet

# Clean up
Get-ChildItem -Recurse -Include "*.pyc","__pycache__","*.dist-info" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Pop-Location

# Create ZIP
Compress-Archive -Path chatbot_minimal\* -DestinationPath chatbot-minimal.zip -Force

$size = [math]::Round((Get-Item chatbot-minimal.zip).Length / 1MB, 2)
Write-Host "`nCreated: chatbot-minimal.zip ($size MB)" -ForegroundColor Green
Write-Host "Note: You'll need to add Lambda layers for FastAPI/Pydantic" -ForegroundColor Yellow















