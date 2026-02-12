"""
Local Testing Script for QB PFF Lambda
Run this to test the Lambda function locally before deploying
"""

import os
import json
import sys
from lambda_function import lambda_handler

# Set environment variables (replace with your actual values)
os.environ['DB_HOST'] = 'your-project.supabase.co'
os.environ['DB_PORT'] = '5432'
os.environ['DB_NAME'] = 'postgres'
os.environ['DB_USER'] = 'postgres'
os.environ['DB_PASSWORD'] = 'your-password-here'

def test_single_season():
    """Test processing a single season"""
    print("=" * 60)
    print("TEST 1: Single Season Processing")
    print("=" * 60)
    
    event = {
        "bucket": "neal-nitya-qb-bucket",
        "season": 2022,
        "s3_prefix": "QBs/"
    }
    
    print(f"\nEvent: {json.dumps(event, indent=2)}\n")
    
    try:
        result = lambda_handler(event, None)
        print("\n✓ Test completed successfully!")
        print(f"\nResponse:")
        print(json.dumps(json.loads(result['body']), indent=2))
        return True
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multiple_seasons():
    """Test processing multiple seasons"""
    print("\n" + "=" * 60)
    print("TEST 2: Multiple Seasons Processing")
    print("=" * 60)
    
    event = {
        "bucket": "neal-nitya-qb-bucket",
        "seasons": [
            {"season": 2022, "s3_prefix": "QBs/"},
            {"season": 2023, "s3_prefix": "QBs/"},
            {"season": 2024, "s3_prefix": "QBs/"}
        ]
    }
    
    print(f"\nEvent: {json.dumps(event, indent=2)}\n")
    
    try:
        result = lambda_handler(event, None)
        print("\n✓ Test completed successfully!")
        print(f"\nResponse:")
        print(json.dumps(json.loads(result['body']), indent=2))
        return True
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_s3_connection():
    """Test S3 connection and file listing"""
    print("\n" + "=" * 60)
    print("TEST 3: S3 Connection Test")
    print("=" * 60)
    
    from S3FileReader import S3FileReader
    
    try:
        reader = S3FileReader(bucket_name="neal-nitya-qb-bucket")
        files = reader.list_files_in_folder("QBs/")
        
        print(f"\n✓ S3 connection successful!")
        print(f"Found {len(files)} files in QBs/ folder:")
        for file in files[:10]:  # Show first 10
            print(f"  - {file}")
        if len(files) > 10:
            print(f"  ... and {len(files) - 10} more files")
        
        return True
    except Exception as e:
        print(f"\n✗ S3 connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_connection():
    """Test database connection"""
    print("\n" + "=" * 60)
    print("TEST 4: Database Connection Test")
    print("=" * 60)
    
    from DatabaseUtils import DatabaseUtils
    
    try:
        db = DatabaseUtils()
        db.connect()
        print("\n✓ Database connection successful!")
        db.close()
        return True
    except Exception as e:
        print(f"\n✗ Database connection failed: {e}")
        print("\nMake sure you've set the environment variables:")
        print("  DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("QB PFF Lambda - Local Testing")
    print("=" * 60)
    print("\n⚠ Make sure to update environment variables in this file!")
    print("⚠ Make sure AWS credentials are configured (for S3 access)")
    print("\n")
    
    # Run tests
    results = []
    
    # Test 1: Database connection
    results.append(("Database Connection", test_database_connection()))
    
    # Test 2: S3 connection
    results.append(("S3 Connection", test_s3_connection()))
    
    # Test 3: Single season (only if DB and S3 work)
    if results[0][1] and results[1][1]:
        results.append(("Single Season Processing", test_single_season()))
        # Test 4: Multiple seasons (optional)
        # results.append(("Multiple Seasons Processing", test_multiple_seasons()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(result[1] for result in results)
    if all_passed:
        print("\n✓ All tests passed! Ready to deploy.")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed. Fix issues before deploying.")
        sys.exit(1)

