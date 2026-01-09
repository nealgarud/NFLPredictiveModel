"""
PlayerImpactCalculator Module

Calculates player-level impact on game outcomes by combining:
- Position mapping (PositionMapper) - Maps NFL positions to Boyd's system
- Madden ratings (MaddenRatingMapper) - Player quality assessment
- Player weights (PlayerWeightAssigner) - Importance scores
- Injury impact (InjuryImpactCalculator) - Game-day roster analysis
- Game processing (GameProcessor) - Orchestrates full pipeline

Main entry point: GameProcessor
"""

from .PositionMapper import PositionMapper
from .MaddenRatingMapper import MaddenRatingMapper
from .PlayerWeightAssigner import PlayerWeightAssigner
from .InjuryImpactCalculator import InjuryImpactCalculator

__version__ = "0.1.0"
__all__ = [
    'PositionMapper',
    'MaddenRatingMapper', 
    'PlayerWeightAssigner',
    'InjuryImpactCalculator'
]

