"""
AWS Lambda handler for Chatbot Prediction API (Simplified)
Works with AWS SDK Pandas Layer - no FastAPI needed
"""
import json
import os
from typing import Dict, Any

# Import your prediction calculator
try:
    from SpreadPredictionCalculator import SpreadPredictionCalculator
    predictor = SpreadPredictionCalculator()
    print("✅ Predictor initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize predictor: {e}")
    predictor = None


def lambda_handler(event, context):
    """
    Direct Lambda handler (no FastAPI/Mangum needed)
    """
    try:
        # Parse the request
        path = event.get('rawPath', event.get('path', '/'))
        method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')
        
        # Remove stage from path if present
        if path.startswith('/Deployment'):
            path = path[len('/Deployment'):]
        
        print(f"Request: {method} {path}")
        
        # Handle OPTIONS preflight request for CORS
        if method == 'OPTIONS':
            return response(200, {"message": "OK"})
        
        # Route to handlers
        if path == '/' or path == '':
            return response(200, {
                "status": "healthy",
                "service": "NFL Chatbot Prediction API",
                "version": "1.0.0"
            })
        
        elif path == '/health':
            return handle_health()
        
        elif path == '/teams':
            return handle_teams()
        
        elif path == '/predict' and method == 'POST':
            body = json.loads(event.get('body', '{}'))
            return handle_predict(body)
        
        else:
            return response(404, {"error": "Not Found"})
    
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return response(500, {"error": str(e)})


def handle_health():
    """Health check endpoint"""
    try:
        if predictor:
            conn = predictor.db.get_connection()
            conn.run("SELECT 1")
            db_status = "connected"
        else:
            db_status = "predictor not initialized"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return response(200, {
        "status": "healthy",
        "database": db_status,
        "predictor": "initialized" if predictor else "failed"
    })


def handle_teams():
    """List all NFL teams"""
    teams = [
        {"abbr": "ARI", "name": "Cardinals", "city": "Arizona"},
        {"abbr": "ATL", "name": "Falcons", "city": "Atlanta"},
        {"abbr": "BAL", "name": "Ravens", "city": "Baltimore"},
        {"abbr": "BUF", "name": "Bills", "city": "Buffalo"},
        {"abbr": "CAR", "name": "Panthers", "city": "Carolina"},
        {"abbr": "CHI", "name": "Bears", "city": "Chicago"},
        {"abbr": "CIN", "name": "Bengals", "city": "Cincinnati"},
        {"abbr": "CLE", "name": "Browns", "city": "Cleveland"},
        {"abbr": "DAL", "name": "Cowboys", "city": "Dallas"},
        {"abbr": "DEN", "name": "Broncos", "city": "Denver"},
        {"abbr": "DET", "name": "Lions", "city": "Detroit"},
        {"abbr": "GB", "name": "Packers", "city": "Green Bay"},
        {"abbr": "HOU", "name": "Texans", "city": "Houston"},
        {"abbr": "IND", "name": "Colts", "city": "Indianapolis"},
        {"abbr": "JAX", "name": "Jaguars", "city": "Jacksonville"},
        {"abbr": "KC", "name": "Chiefs", "city": "Kansas City"},
        {"abbr": "LAC", "name": "Chargers", "city": "Los Angeles"},
        {"abbr": "LAR", "name": "Rams", "city": "Los Angeles"},
        {"abbr": "LV", "name": "Raiders", "city": "Las Vegas"},
        {"abbr": "MIA", "name": "Dolphins", "city": "Miami"},
        {"abbr": "MIN", "name": "Vikings", "city": "Minnesota"},
        {"abbr": "NE", "name": "Patriots", "city": "New England"},
        {"abbr": "NO", "name": "Saints", "city": "New Orleans"},
        {"abbr": "NYG", "name": "Giants", "city": "New York"},
        {"abbr": "NYJ", "name": "Jets", "city": "New York"},
        {"abbr": "PHI", "name": "Eagles", "city": "Philadelphia"},
        {"abbr": "PIT", "name": "Steelers", "city": "Pittsburgh"},
        {"abbr": "SEA", "name": "Seahawks", "city": "Seattle"},
        {"abbr": "SF", "name": "49ers", "city": "San Francisco"},
        {"abbr": "TB", "name": "Buccaneers", "city": "Tampa Bay"},
        {"abbr": "TEN", "name": "Titans", "city": "Tennessee"},
        {"abbr": "WAS", "name": "Commanders", "city": "Washington"}
    ]
    return response(200, {"teams": teams, "count": len(teams)})


def handle_predict(body: Dict[str, Any]):
    """Handle prediction request"""
    try:
        if not predictor:
            return response(503, {
                "success": False,
                "error": "Predictor not initialized"
            })
        
        # Extract parameters
        team_a = body.get('team_a', '').upper()
        team_b = body.get('team_b', '').upper()
        spread = float(body.get('spread', 0))
        team_a_home = body.get('team_a_home', False)
        seasons = body.get('seasons', [2024, 2025])
        
        # Validate
        if not team_a or not team_b:
            return response(400, {
                "success": False,
                "error": "team_a and team_b are required"
            })
        
        # Get prediction
        prediction = predictor.predict_spread_coverage(
            team_a=team_a,
            team_b=team_b,
            spread=spread,
            team_a_home=team_a_home,
            seasons=seasons
        )
        
        return response(200, {
            "success": True,
            "data": prediction,
            "error": None
        })
        
    except Exception as e:
        print(f"Prediction error: {str(e)}")
        import traceback
        traceback.print_exc()
        return response(500, {
            "success": False,
            "data": None,
            "error": str(e)
        })


def response(status_code: int, body: Dict[str, Any]):
    """Create API Gateway response"""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        },
        "body": json.dumps(body)
    }

