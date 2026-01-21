#!/bin/bash
# Bash Script to Create PlayerImpactCalculator Lambda Deployment Package
# For Linux/Mac users

echo "================================"
echo "PlayerImpactCalculator Lambda Package Creator"
echo "================================"
echo ""

# Clean up old package
if [ -d "lambda_package" ]; then
    echo "Cleaning up old package directory..."
    rm -rf lambda_package
fi

if [ -f "playerimpact-lambda.zip" ]; then
    echo "Removing old ZIP file..."
    rm -f playerimpact-lambda.zip
fi

# Create fresh directory
echo "Creating package directory..."
mkdir lambda_package

# Copy Python modules from PlayerImpactCalculator
echo "Copying PlayerImpactCalculator modules..."
modules=(
    "PlayerImpactCalculator/S3DataLoader.py"
    "PlayerImpactCalculator/PositionMapper.py"
    "PlayerImpactCalculator/PlayerWeightAssigner.py"
    "PlayerImpactCalculator/MaddenRatingMapper.py"
    "PlayerImpactCalculator/InjuryImpactCalculator.py"
    "PlayerImpactCalculator/SportradarClient.py"
    "PlayerImpactCalculator/SupabaseStorage.py"
    "PlayerImpactCalculator/game_processor.py"
    "PlayerImpactCalculator/__init__.py"
)

for module in "${modules[@]}"; do
    if [ -f "$module" ]; then
        cp "$module" lambda_package/
        echo "  ✓ $module"
    else
        echo "  ✗ $module (not found)"
    fi
done

# Copy PlayerImpactFeature from PredictionAPILambda
echo "Copying PlayerImpactFeature..."
if [ -f "PredictionAPILambda/PlayerImpactFeature.py" ]; then
    cp "PredictionAPILambda/PlayerImpactFeature.py" lambda_package/
    echo "  ✓ PlayerImpactFeature.py"
else
    echo "  ✗ PlayerImpactFeature.py (not found)"
fi

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
echo "(This may take a few minutes)"

dependencies=(
    "requests"
    "boto3"
    "pandas"
    "numpy"
    "pg8000"
)

for dep in "${dependencies[@]}"; do
    echo "  Installing $dep..."
    pip install --target lambda_package --quiet "$dep"
    if [ $? -eq 0 ]; then
        echo "  ✓ $dep installed"
    else
        echo "  ✗ $dep failed to install"
    fi
done

# Create ZIP file
echo ""
echo "Creating ZIP file..."
cd lambda_package
zip -r ../playerimpact-lambda.zip . -x "*.pyc" -x "__pycache__/*" -x "*.dist-info/*" > /dev/null
cd ..

# Get file size
zip_size=$(du -h playerimpact-lambda.zip | cut -f1)
zip_size_mb=$(du -m playerimpact-lambda.zip | cut -f1)

echo ""
echo "================================"
echo "✓ Lambda package created successfully!"
echo "================================"
echo ""
echo "Package: playerimpact-lambda.zip"
echo "Size: $zip_size"
echo ""

# Check if size is too large for direct upload
if [ "$zip_size_mb" -gt 50 ]; then
    echo "WARNING: Package is larger than 50MB"
    echo "You must upload to S3 first, then deploy to Lambda from S3"
    echo ""
    echo "Commands:"
    echo "  aws s3 cp playerimpact-lambda.zip s3://sportsdatacollection/lambda-packages/"
    echo "  aws lambda update-function-code --function-name PlayerImpactProcessor --s3-bucket sportsdatacollection --s3-key lambda-packages/playerimpact-lambda.zip"
else
    echo "Package size is OK for direct Lambda upload"
    echo ""
    echo "Next steps:"
    echo "1. Go to AWS Lambda console"
    echo "2. Create or select your function"
    echo "3. Upload playerimpact-lambda.zip"
    echo "4. Set environment variables (see LAMBDA_DEPLOYMENT.md)"
fi

echo ""
echo "Cleanup:"
echo "The lambda_package folder can be deleted if desired"
echo ""

# Optional: Clean up package directory
read -p "Delete lambda_package folder? (y/n) " cleanup
if [ "$cleanup" = "y" ] || [ "$cleanup" = "Y" ]; then
    rm -rf lambda_package
    echo "✓ Cleaned up lambda_package folder"
fi

echo ""
echo "Done! 🚀"

