"""
Local test script for the prediction API
Tests without needing to upload to Lambda
"""
import os
import json

# Set environment variables (use your Supabase credentials)
os.environ['SUPABASE_DB_HOST'] = 'aws-1-us-east-2.pooler.supabase.com'
os.environ['SUPABASE_DB_PORT'] = '5432'
os.environ['SUPABASE_DB_USER'] = 'postgres.bodckgmwvhzythotvfgp'
os.environ['SUPABASE_DB_NAME'] = 'postgres'
os.environ['SUPABASE_DB_PASSWORD'] = 'QtL0eNHRxeqva7Je'

# Import the handler
from api_handler_simple import lambda_handler

def test_health():
    """Test health endpoint"""
    print("\n=== Testing /health ===")
    event = {
        'rawPath': '/health',
        'requestContext': {
            'http': {
                'method': 'GET'
            }
        }
    }
    response = lambda_handler(event, None)
    print(f"Status: {response['statusCode']}")
    print(f"Body: {response['body']}")
    return response

def test_teams():
    """Test teams endpoint"""
    print("\n=== Testing /teams ===")
    event = {
        'rawPath': '/teams',
        'requestContext': {
            'http': {
                'method': 'GET'
            }
        }
    }
    response = lambda_handler(event, None)
    print(f"Status: {response['statusCode']}")
    body = json.loads(response['body'])
    print(f"Teams count: {body.get('count', 0)}")
    return response

def test_predict():
    """Test prediction endpoint"""
    print("\n=== Testing /predict ===")
    
    test_request = {
        "team_a": "GB",
        "team_b": "PIT",
        "spread": -2.5,
        "team_a_home": False,
        "seasons": [2024, 2025]
    }
    
    event = {
        'rawPath': '/predict',
        'requestContext': {
            'http': {
                'method': 'POST'
            }
        },
        'body': json.dumps(test_request)
    }
    
    print(f"Request: {test_request}")
    response = lambda_handler(event, None)
    print(f"Status: {response['statusCode']}")
    
    body = json.loads(response['body'])
    if body.get('success'):
        print("\n✅ PREDICTION SUCCESS!")
        print(json.dumps(body['data'], indent=2))
    else:
        print(f"\n❌ ERROR: {body.get('error')}")
    
    return response

if __name__ == "__main__":
    print("🧪 Testing NFL Prediction API Locally")
    print("=" * 50)
    
    try:
        # Test health
        health_response = test_health()
        
        # Test teams
        teams_response = test_teams()
        
        # Test prediction
        predict_response = test_predict()
        
        print("\n" + "=" * 50)
        print("✅ All tests completed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

