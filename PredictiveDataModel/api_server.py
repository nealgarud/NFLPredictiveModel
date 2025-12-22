"""
FastAPI Backend for NFL Spread Prediction Service
Provides REST API endpoints for the chatbot to query predictions
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import uvicorn

from SpreadPredictionCalculator import SpreadPredictionCalculator

app = FastAPI(
    title="NFL Spread Prediction API",
    description="AI-powered NFL spread coverage predictions using historical ATS data",
    version="1.0.0"
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize prediction calculator
calculator = SpreadPredictionCalculator()


class PredictionRequest(BaseModel):
    """Request model for spread predictions"""
    team_a: str = Field(..., description="First team abbreviation (e.g., 'GB')", min_length=2, max_length=3)
    team_b: str = Field(..., description="Second team abbreviation (e.g., 'PIT')", min_length=2, max_length=3)
    spread: float = Field(..., description="Point spread for team_a (negative means favored)")
    team_a_home: bool = Field(..., description="True if team_a is playing at home")
    seasons: Optional[List[int]] = Field(default=[2024, 2025], description="Seasons to include in analysis")
    
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
    """Response model for predictions"""
    success: bool
    data: Optional[dict]
    error: Optional[str]


@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "NFL Spread Prediction API",
        "version": "1.0.0"
    }


@app.get("/health")
def health_check():
    """Detailed health check"""
    try:
        # Test database connection
        conn = calculator.db.get_connection()
        conn.run("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "database": db_status,
        "calculator": "initialized"
    }


@app.post("/predict", response_model=PredictionResponse)
def predict_spread(request: PredictionRequest):
    """
    Predict which team will cover the spread
    
    **Example Request:**
    ```json
    {
        "team_a": "GB",
        "team_b": "PIT",
        "spread": -2.5,
        "team_a_home": false,
        "seasons": [2024, 2025]
    }
    ```
    
    **Returns:** Prediction with probabilities and breakdown
    """
    try:
        # Validate team codes
        if request.team_a.upper() == request.team_b.upper():
            raise HTTPException(
                status_code=400, 
                detail="team_a and team_b must be different teams"
            )
        
        # Get prediction
        prediction = calculator.predict_spread_coverage(
            team_a=request.team_a.upper(),
            team_b=request.team_b.upper(),
            spread=request.spread,
            team_a_home=request.team_a_home,
            seasons=request.seasons
        )
        
        return PredictionResponse(
            success=True,
            data=prediction,
            error=None
        )
        
    except Exception as e:
        return PredictionResponse(
            success=False,
            data=None,
            error=str(e)
        )


@app.get("/teams")
def get_teams():
    """Get list of all NFL teams"""
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
    return {"teams": teams}


if __name__ == "__main__":
    # Run the API server
    uvicorn.run(app, host="0.0.0.0", port=8000)

