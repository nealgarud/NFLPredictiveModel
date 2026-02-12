# Madden to PFF Migration Summary

**Date**: February 6, 2026  
**Status**: Phase 1 Complete - All Madden files deleted

## Overview

This migration replaces Madden ratings with Pro Football Focus (PFF) grades as the primary data source for player impact calculations.

## Phase 1: Cleanup ✅

### Files Deleted

#### Madden ETL Lambda (entire folder)
- `madden-etl/lambda_function.py`
- `madden-etl/madden-etl-debug.zip`
- `madden-etl/madden-etl-fixed.zip`
- `madden-etl/README.md`
- `madden-etl/requirements.txt`

#### Madden Rating Mappers
- `playerimpact/MaddenRatingMapper.py`
- `PredictiveDataModel/PlayerImpactCalculator/MaddenRatingMapper.py`
- `PredictiveDataModel/SupervisedLearningDataCollector/test_madden_mapper.py`

#### S3 Data Loaders (Madden-specific)
- `playerimpact/S3DataLoader.py`
- `PredictiveDataModel/PlayerImpactCalculator/S3DataLoader.py`

#### Old Lambda Versions
- `playerimpact/lambda_function_old.py.bak`
- `playerimpact/lambda_function_s3_backup.py`
- `playerimpact/lambda_function_supabase.py`
- `playerimpact/lambda_function_v2.py`

#### Test/Example Files
- `playerimpact/example_usage.py`
- `playerimpact/test_integration.py`
- `playerimpact/process_weekly_games.py`
- `PredictiveDataModel/PlayerImpactCalculator/example_usage.py`
- `PredictiveDataModel/PlayerImpactCalculator/test_integration.py`
- `PredictiveDataModel/PlayerImpactCalculator/process_weekly_games.py`

#### Old Deployment Packages
- `playerimpact/playerimpact-with-injury-tracking.zip`
- `playerimpact/playerimpact-with-weights.zip`
- `PredictiveDataModel/playerimpact-lambda-light.zip`
- `PredictiveDataModel/playerimpact-lambda.zip`

### Total Files Deleted: 24 files + 1 folder

---

## Phase 2: PFF Implementation (Next Steps)

### New Components Created
- ✅ `playerimpact/sql/create_pff_tables.sql` - Database schema for PFF grades
- ✅ `pff-etl-lambdas/base_pff_etl.py` - Common ETL utilities
- ✅ `playerimpact/PFFGradeClient.py` - PFF data fetching interface

### S3 Structure for PFF Data
```
s3://your-bucket/pff-grades/
├── QB/
│   ├── QB_2024.csv
│   ├── QB_2025.csv
├── RB/
│   ├── RB_2024.csv
│   ├── RB_2025.csv
├── WR/
│   ├── WR_2024.csv
│   ├── WR_2025.csv
├── OL/
│   ├── OL_2024.csv
│   ├── OL_2025.csv
└── DEF/
    ├── DEF_2024.csv
    ├── DEF_2025.csv
```

### Database Tables
- `pff_wr_grades` - Wide Receivers & Tight Ends
- `pff_rb_grades` - Running Backs
- `pff_qb_grades` - Quarterbacks
- `pff_ol_grades` - Offensive Line
- `pff_def_grades` - Defense

### Pending Tasks
1. Build position-specific ETL Lambdas (QB, RB, WR, OL, DEF)
2. Update `lambda_function.py` to use PFF grades
3. Update `ImpactCalculator.py` to use PFF grades
4. Create deployment documentation

---

## Key Changes

### Data Source Migration
- **Before**: Madden overall rating (0-99 scale)
- **After**: PFF grades_offense/grades_defense (60-99 scale)

### Architecture
- **Before**: Single Madden ETL Lambda → S3 → Lambda function
- **After**: Multiple position-specific PFF ETL Lambdas → Supabase → Lambda function

### Benefits
1. **More accurate**: PFF grades based on actual game film analysis
2. **Position-specific**: Different metrics for different positions
3. **Better granularity**: Separate grades for different skills (pass_route, run_block, coverage, etc.)
4. **Industry standard**: PFF is the gold standard for player evaluation

---

## Git Status

All Madden-related files have been deleted and staged for commit:
```bash
git add -A
# 24 files deleted
# 1 folder removed (madden-etl/)
```

Ready to commit when Phase 2 implementation is complete.

