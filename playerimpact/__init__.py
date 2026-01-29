"""
PlayerImpactCalculator Module - NOW WITH REAL DATA!

Calculates player-level impact on game outcomes by combining:
- Sportradar API (SportradarClient) - Live NFL data
- S3 Data Loading (S3DataLoader) - Historical games and Madden ratings
- Position mapping (PositionMapper) - Maps NFL positions to Boyd's system
- Madden ratings (MaddenRatingMapper) - Player quality assessment
- Player weights (PlayerWeightAssigner) - Importance scores
- Injury impact (InjuryImpactCalculator) - Game-day roster analysis
- Game processing (GameProcessor) - Orchestrates full pipeline
- Supabase storage (SupabaseStorage) - Database persistence

Main entry point: GameProcessor
"""

from .SportradarClient import SportradarClient
from .S3DataLoader import S3DataLoader
from .PositionMapper import PositionMapper
from .MaddenRatingMapper import MaddenRatingMapper
from .PlayerWeightAssigner import PlayerWeightAssigner
from .InjuryImpactCalculator import InjuryImpactCalculator
from .game_processor import GameProcessor
from .SupabaseStorage import SupabaseStorage

__version__ = "1.0.0"  # Version bump for real data integration!
__all__ = [
    'SportradarClient',
    'S3DataLoader',
    'PositionMapper',
    'MaddenRatingMapper', 
    'PlayerWeightAssigner',
    'InjuryImpactCalculator',
    'GameProcessor',
    'SupabaseStorage'
]

