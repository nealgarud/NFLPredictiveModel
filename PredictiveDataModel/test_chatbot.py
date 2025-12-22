"""
Test script for NFL Prediction Chatbot
Run this to verify everything works before deployment
"""
import os
import sys
import json
import requests
from SpreadPredictionCalculator import SpreadPredictionCalculator


def test_prediction_calculator():
    """Test the core prediction engine"""
    print("\n" + "="*60)
    print("TEST 1: Prediction Calculator")
    print("="*60)
    
    try:
        calc = SpreadPredictionCalculator()
        print("✅ Calculator initialized")
        
        # Test prediction: GB @ PIT, GB -2.5
        print("\nTesting: GB @ PIT (GB -2.5)")
        result = calc.predict_spread_coverage(
            team_a="GB",
            team_b="PIT",
            spread=-2.5,
            team_a_home=False,
            seasons=[2024, 2025]
        )
        
        print(f"\n📊 Results:")
        print(f"   Matchup: {result['matchup']}")
        print(f"   Spread: {result['spread_line']}")
        print(f"   Favored: {result['favored_team']}")
        print(f"   Underdog: {result['underdog_team']}")
        print(f"\n🎯 Prediction:")
        print(f"   Recommended Bet: {result['prediction']['recommended_bet']}")
        print(f"   Confidence: {result['prediction']['confidence']*100:.1f}%")
        print(f"   {result['favored_team']} Cover Prob: {result['prediction']['favored_cover_probability']*100:.1f}%")
        print(f"   {result['underdog_team']} Cover Prob: {result['prediction']['underdog_cover_probability']*100:.1f}%")
        
        print(f"\n📈 Breakdown:")
        print(f"   Situational ATS: {result['breakdown']['situational_ats']['situation']}")
        print(f"     • {result['favored_team']}: {result['breakdown']['situational_ats']['favored_rate']*100:.1f}% ({result['breakdown']['situational_ats']['favored_record']})")
        print(f"     • {result['underdog_team']}: {result['breakdown']['situational_ats']['underdog_rate']*100:.1f}% ({result['breakdown']['situational_ats']['underdog_record']})")
        
        print(f"\n   Overall ATS:")
        print(f"     • {result['favored_team']}: {result['breakdown']['overall_ats']['favored_rate']*100:.1f}% ({result['breakdown']['overall_ats']['favored_record']})")
        print(f"     • {result['underdog_team']}: {result['breakdown']['overall_ats']['underdog_rate']*100:.1f}% ({result['breakdown']['overall_ats']['underdog_record']})")
        
        print(f"\n   Home/Away Performance:")
        print(f"     • {result['favored_team']}: {result['breakdown']['home_away']['favored_rate']*100:.1f}% win rate")
        print(f"     • {result['underdog_team']}: {result['breakdown']['home_away']['underdog_rate']*100:.1f}% win rate")
        
        print("\n✅ TEST PASSED: Prediction Calculator working!")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_server():
    """Test the FastAPI server (must be running on localhost:8000)"""
    print("\n" + "="*60)
    print("TEST 2: API Server")
    print("="*60)
    
    base_url = "http://localhost:8000"
    
    # Test 1: Health check
    print("\nTest 2.1: Health Check")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        response.raise_for_status()
        print(f"✅ Health check passed: {response.json()['status']}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        print("   Make sure API server is running: python api_server.py")
        return False
    
    # Test 2: Get teams
    print("\nTest 2.2: Get Teams")
    try:
        response = requests.get(f"{base_url}/teams", timeout=5)
        response.raise_for_status()
        teams = response.json()['teams']
        print(f"✅ Retrieved {len(teams)} teams")
    except Exception as e:
        print(f"❌ Get teams failed: {e}")
        return False
    
    # Test 3: Prediction endpoint
    print("\nTest 2.3: Prediction Endpoint")
    try:
        payload = {
            "team_a": "GB",
            "team_b": "PIT",
            "spread": -2.5,
            "team_a_home": False,
            "seasons": [2024, 2025]
        }
        response = requests.post(f"{base_url}/predict", json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result['success']:
            data = result['data']
            print(f"✅ Prediction successful!")
            print(f"   Recommended: {data['prediction']['recommended_bet']} ({data['prediction']['confidence']*100:.1f}% confidence)")
        else:
            print(f"❌ Prediction failed: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Prediction endpoint failed: {e}")
        return False
    
    print("\n✅ TEST PASSED: API Server working!")
    return True


def test_chatbot():
    """Test the OpenAI chatbot (requires OPENAI_API_KEY)"""
    print("\n" + "="*60)
    print("TEST 3: OpenAI Chatbot")
    print("="*60)
    
    if not os.getenv('OPENAI_API_KEY'):
        print("⚠️  SKIPPED: OPENAI_API_KEY not set")
        print("   Set it with: $env:OPENAI_API_KEY = 'sk-...'")
        return None
    
    try:
        from chatbot import NFLPredictionChatbot
        
        print("\nInitializing chatbot...")
        chatbot = NFLPredictionChatbot(api_base_url="http://localhost:8000")
        print("✅ Chatbot initialized")
        
        # Test query
        print("\nTest Query: 'Who covers GB @ PIT with Packers -2.5?'")
        response = chatbot.chat("Who covers GB @ PIT with Packers -2.5?")
        print(f"\n🤖 Response:\n{response}\n")
        
        print("✅ TEST PASSED: Chatbot working!")
        return True
        
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🏈 NFL PREDICTION CHATBOT - TEST SUITE")
    print("="*60)
    
    results = {
        'calculator': False,
        'api': False,
        'chatbot': None
    }
    
    # Test 1: Prediction Calculator (no dependencies)
    results['calculator'] = test_prediction_calculator()
    
    # Test 2: API Server (requires server running)
    results['api'] = test_api_server()
    
    # Test 3: Chatbot (requires OpenAI key + server running)
    if results['api']:
        results['chatbot'] = test_chatbot()
    else:
        print("\n⚠️  Skipping chatbot test (API server not available)")
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Prediction Calculator: {'✅ PASS' if results['calculator'] else '❌ FAIL'}")
    print(f"API Server: {'✅ PASS' if results['api'] else '❌ FAIL'}")
    
    if results['chatbot'] is None:
        print(f"OpenAI Chatbot: ⚠️  SKIPPED")
    else:
        print(f"OpenAI Chatbot: {'✅ PASS' if results['chatbot'] else '❌ FAIL'}")
    
    # Overall
    all_passed = results['calculator'] and results['api'] and (results['chatbot'] in [True, None])
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED! Ready for deployment.")
    else:
        print("\n⚠️  Some tests failed. Fix issues before deploying.")
        sys.exit(1)


if __name__ == "__main__":
    main()

