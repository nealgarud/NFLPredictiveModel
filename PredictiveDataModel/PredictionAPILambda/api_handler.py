"""
AWS Lambda handler for Chatbot Prediction API
This wraps the FastAPI app to work with Lambda + API Gateway
"""
from mangum import Mangum
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import os
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Import your prediction calculator
try:
    from SpreadPredictionCalculator import SpreadPredictionCalculator
    logger.info("✅ SpreadPredictionCalculator imported successfully")
except Exception as e:
    logger.error(f"❌ Failed to import SpreadPredictionCalculator: {e}")
    SpreadPredictionCalculator = None

# Create FastAPI app
app = FastAPI(
    title="NFL Prediction API",
    description="AI-powered NFL spread coverage predictions",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize predictor (YOUR EQUATION)
predictor = None
try:
    predictor = SpreadPredictionCalculator()
    logger.info("✅ Predictor initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize predictor: {e}")


class PredictionRequest(BaseModel):
    """Request format from OpenAI chatbot"""
    team_a: str
    team_b: str
    spread: float
    team_a_home: bool
    seasons: Optional[List[int]] = [2024, 2025]
    
    class Config:
        json_schema_extra = {
            "example": {
                "team_a": "GB",
                "team_b": "PIT",
                "spread": -2.5,
                "team_a_home": False,
                "seasons": [2024, 2025]
            }
        }


class PredictionResponse(BaseModel):
    """Response format"""
    success: bool
    data: Optional[dict]
    error: Optional[str]


@app.get("/")
def root():
    """Health check"""
    return {
        "status": "healthy",
        "service": "NFL Chatbot Prediction API",
        "version": "1.0.0",
        "endpoints": {
            "health": "GET /health",
            "teams": "GET /teams",
            "predict": "POST /predict"
        }
    }


@app.get("/health")
def health():
    """Detailed health check"""
    try:
        # Test database connection
        if predictor:
            conn = predictor.db.get_connection()
            conn.run("SELECT 1")
            db_status = "connected"
        else:
            db_status = "predictor not initialized"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "database": db_status,
        "predictor": "initialized" if predictor else "failed",
        "environment": {
            "python_version": "3.11",
            "has_supabase_host": bool(os.getenv('SUPABASE_DB_HOST')),
            "has_supabase_password": bool(os.getenv('SUPABASE_DB_PASSWORD'))
        }
    }


@app.get("/teams")
def get_teams():
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
    return {"teams": teams, "count": len(teams)}


@app.post("/predict", response_model=PredictionResponse)
def predict_spread(request: PredictionRequest):
    """
    Predict which team covers the spread
    THIS IS WHERE YOUR EQUATION RUNS
    
    Your 40/30/30 weighted formula:
    - 40% Situational ATS (spread range + home/away)
    - 30% Overall ATS (season performance)
    - 30% Home/Away splits
    """
    try:
        if not predictor:
            logger.error("Predictor not initialized")
            raise HTTPException(
                status_code=503,
                detail="Predictor not initialized - check environment variables"
            )
        
        logger.info(f"Prediction request: {request.team_a} vs {request.team_b}, spread: {request.spread}")
        
        # Call YOUR prediction equation
        prediction = predictor.predict_spread_coverage(
            team_a=request.team_a.upper(),
            team_b=request.team_b.upper(),
            spread=request.spread,
            team_a_home=request.team_a_home,
            seasons=request.seasons
        )
        
        logger.info(f"Prediction result: {prediction['prediction']['recommended_bet']} with {prediction['prediction']['confidence']*100:.1f}% confidence")
        
        return PredictionResponse(
            success=True,
            data=prediction,
            error=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prediction failed: {str(e)}", exc_info=True)
        return PredictionResponse(
            success=False,
            data=None,
            error=f"Prediction failed: {str(e)}"
        )


# Lambda handler (required for AWS Lambda)
# This adapts FastAPI to work with Lambda + API Gateway
handler = Mangum(app, lifespan="off")


# For local testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

