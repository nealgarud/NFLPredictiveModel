"""
Simple prediction output - just the key metrics
"""
from SpreadPredictionCalculator import SpreadPredictionCalculator
import json


def main():
    calc = SpreadPredictionCalculator()
    
    result = calc.predict_spread_coverage(
        team_a="NE",
        team_b="NYJ",
        spread=-5.5,
        team_a_home=True,
        seasons=[2024, 2025]
    )
    
    # Extract only the key prediction metrics
    output = {
        "favored_cover_probability": result['prediction']['favored_cover_probability'],
        "underdog_cover_probability": result['prediction']['underdog_cover_probability'],
        "recommended_bet": result['prediction']['recommended_bet'],
        "confidence": result['prediction']['confidence']
    }
    
    print(json.dumps(output, indent=4))


if __name__ == "__main__":
    main()



