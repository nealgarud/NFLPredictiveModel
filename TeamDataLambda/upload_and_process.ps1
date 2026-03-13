# upload_and_process.ps1
#
# 1. Uploads local PFF team grade CSVs to S3 (team_data_nfl bucket)
# 2. Invokes TeamDataLambda to process each season into Supabase
#
# Usage:
#   .\upload_and_process.ps1
#   .\upload_and_process.ps1 -Seasons 2024          # single season
#   .\upload_and_process.ps1 -UploadOnly             # skip Lambda invoke
#   .\upload_and_process.ps1 -InvokeOnly             # skip S3 upload (already uploaded)
#
# Prerequisites:
#   - AWS CLI configured (aws configure)
#   - TeamDataLambda deployed to AWS Lambda
#   - Local CSV files named <season>_team_grades.csv in $LocalDataDir
#     e.g.  2022_team_grades.csv
#           2023_team_grades.csv
#           2024_team_grades.csv

param(
    [string[]] $Seasons     = @("2022", "2023", "2024"),
    [string]   $LocalDataDir = "$PSScriptRoot\data",
    [string]   $S3Bucket    = "team_data_nfl",
    [string]   $LambdaName  = "TeamDataLambda",
    [switch]   $UploadOnly,
    [switch]   $InvokeOnly
)

$ErrorActionPreference = "Stop"

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host " NFL Team Data — Upload & Process" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "Bucket  : $S3Bucket"
Write-Host "Lambda  : $LambdaName"
Write-Host "Seasons : $($Seasons -join ', ')"
Write-Host ""

# -------------------------------------------------------------------
# STEP 1: Upload CSVs to S3
# -------------------------------------------------------------------
if (-not $InvokeOnly) {
    Write-Host "STEP 1: Uploading CSVs to S3..." -ForegroundColor Yellow

    if (-not (Test-Path $LocalDataDir)) {
        Write-Host "  ERROR: Local data directory not found: $LocalDataDir" -ForegroundColor Red
        Write-Host "  Create the folder and place your CSVs there:"
        Write-Host "    $LocalDataDir\2022_team_grades.csv"
        Write-Host "    $LocalDataDir\2023_team_grades.csv"
        Write-Host "    $LocalDataDir\2024_team_grades.csv"
        exit 1
    }

    foreach ($season in $Seasons) {
        $localFile = Join-Path $LocalDataDir "${season}_team_grades.csv"
        $s3Key     = "${season}/team_grades.csv"

        if (-not (Test-Path $localFile)) {
            Write-Host "  SKIP  $season — file not found: $localFile" -ForegroundColor Yellow
            continue
        }

        Write-Host "  Uploading $localFile -> s3://$S3Bucket/$s3Key"
        aws s3 cp $localFile "s3://$S3Bucket/$s3Key"
        Write-Host "  OK" -ForegroundColor Green
    }

    Write-Host ""
}

# -------------------------------------------------------------------
# STEP 2: Invoke Lambda for all seasons at once
# -------------------------------------------------------------------
if (-not $UploadOnly) {
    Write-Host "STEP 2: Invoking $LambdaName..." -ForegroundColor Yellow

    $seasonsArray = $Seasons | ForEach-Object { [int]$_ }
    $payload = @{
        bucket  = $S3Bucket
        seasons = $seasonsArray
    } | ConvertTo-Json -Compress

    $responseFile = "$env:TEMP\team_data_lambda_response.json"

    aws lambda invoke `
        --function-name $LambdaName `
        --payload $payload `
        --cli-binary-format raw-in-base64-out `
        $responseFile

    $response = Get-Content $responseFile | ConvertFrom-Json
    Write-Host ""
    Write-Host "Lambda response:" -ForegroundColor Cyan
    $response | ConvertTo-Json -Depth 5 | Write-Host

    if ($response.statusCode -eq 200) {
        Write-Host ""
        Write-Host "SUCCESS — all seasons processed." -ForegroundColor Green

        $body = $response.body | ConvertFrom-Json
        foreach ($result in $body.results) {
            Write-Host ("  Season {0}: offense={1} defense={2} special_teams={3}" -f `
                $result.season, $result.offense_rows, $result.defense_rows, $result.special_teams_rows)
        }
    } else {
        Write-Host "Lambda returned non-200 status: $($response.statusCode)" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
