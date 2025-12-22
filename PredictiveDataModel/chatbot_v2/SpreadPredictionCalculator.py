"""
NFL Spread Prediction Calculator
Uses weighted factors: Situational ATS, Overall ATS, Home/Away Performance
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from DatabaseConnection import DatabaseConnection


class SpreadPredictionCalculator:
    """Predict spread coverage using historical ATS and performance data"""
    
    # Factor weights (must sum to 1.0)
    SITUATIONAL_ATS_WEIGHT = 0.40  # 40% - Most predictive
    OVERALL_ATS_WEIGHT = 0.30      # 30% - Historical consistency
    HOME_AWAY_WEIGHT = 0.30        # 30% - Location performance
    
    def __init__(self):
        """Initialize with database connection"""
        self.db = DatabaseConnection()
        
    def predict_spread_coverage(
        self, 
        team_a: str, 
        team_b: str, 
        spread: float,
        team_a_home: bool,
        seasons: list = [2024, 2025]
    ) -> Dict:
        """
        Predict which team will cover the spread
        
        Args:
            team_a: Favored team abbreviation (e.g., 'GB')
            team_b: Underdog team abbreviation (e.g., 'PIT')
            spread: Point spread (positive for team_a favored, e.g., -2.5)
            team_a_home: True if team_a is home, False if away
            seasons: List of seasons to include (default: [2024, 2025])
            
        Returns:
            Dictionary with prediction results
        """
        # Determine roles
        if spread < 0:
            favored_team = team_a
            underdog_team = team_b
            favored_home = team_a_home
        else:
            favored_team = team_b
            underdog_team = team_a
            favored_home = not team_a_home
            
        spread_abs = abs(spread)
        spread_range = self._get_spread_range(spread_abs)
        
        # Calculate each factor
        situational_ats = self._calc_situational_ats(
            favored_team, underdog_team, favored_home, spread_range, seasons
        )
        
        overall_ats = self._calc_overall_ats(
            favored_team, underdog_team, seasons
        )
        
        home_away_perf = self._calc_home_away_performance(
            favored_team, underdog_team, favored_home, seasons
        )
        
        # Weighted probability calculation
        favored_prob = (
            self.SITUATIONAL_ATS_WEIGHT * situational_ats['favored_normalized'] +
            self.OVERALL_ATS_WEIGHT * overall_ats['favored_normalized'] +
            self.HOME_AWAY_WEIGHT * home_away_perf['favored_normalized']
        )
        
        underdog_prob = 1 - favored_prob
        
        # Build response
        return {
            'matchup': f"{team_a} @ {team_b}" if not team_a_home else f"{team_b} @ {team_a}",
            'spread_line': f"{team_a} {spread:+.1f}",
            'favored_team': favored_team,
            'underdog_team': underdog_team,
            'prediction': {
                'favored_cover_probability': round(favored_prob, 3),
                'underdog_cover_probability': round(underdog_prob, 3),
                'recommended_bet': favored_team if favored_prob > 0.5 else underdog_team,
                'confidence': round(max(favored_prob, underdog_prob), 3),
                'edge': round(abs(favored_prob - 0.5), 3)
            },
            'breakdown': {
                'situational_ats': situational_ats,
                'overall_ats': overall_ats,
                'home_away': home_away_perf
            }
        }
    
    def _get_spread_range(self, spread: float) -> str:
        """Categorize spread into range (e.g., 2-4, 4-7)"""
        if spread <= 2:
            return "0-2"
        elif spread <= 4:
            return "2-4"
        elif spread <= 7:
            return "4-7"
        elif spread <= 10:
            return "7-10"
        else:
            return "10+"
    
    def _calc_situational_ats(
        self, 
        favored: str, 
        underdog: str, 
        favored_home: bool,
        spread_range: str,
        seasons: list
    ) -> Dict:
        """Calculate situational ATS performance"""
        conn = self.db.get_connection()
        
        # Parse spread range
        if spread_range == "10+":
            min_spread, max_spread = 10, 100
        else:
            parts = spread_range.split('-')
            min_spread = float(parts[0])
            max_spread = float(parts[1])
        
        # Favored team query
        favored_location = "home" if favored_home else "away"
        if favored_location == "home":
            favored_query = """
            SELECT 
                COUNT(*) as total_games,
                SUM(CASE 
                    WHEN spread_line > 0 AND (home_score - away_score) > spread_line THEN 1
                    ELSE 0 
                END) as ats_wins
            FROM games
            WHERE season = ANY(:seasons)
                AND home_team = :team
                AND spread_line BETWEEN :min_spread AND :max_spread
                AND game_type = 'REG'
                AND home_score IS NOT NULL
            """
        else:
            favored_query = """
            SELECT 
                COUNT(*) as total_games,
                SUM(CASE 
                    WHEN spread_line < 0 AND (away_score - home_score) > ABS(spread_line) THEN 1
                    ELSE 0 
                END) as ats_wins
            FROM games
            WHERE season = ANY(:seasons)
                AND away_team = :team
                AND spread_line BETWEEN (:min_spread * -1) AND (:max_spread * -1)
                AND game_type = 'REG'
                AND home_score IS NOT NULL
            """
        
        favored_data = conn.run(
            favored_query,
            seasons=seasons,
            team=favored,
            min_spread=min_spread,
            max_spread=max_spread
        )
        
        # Underdog team query
        underdog_location = "away" if favored_home else "home"
        if underdog_location == "home":
            underdog_query = """
            SELECT 
                COUNT(*) as total_games,
                SUM(CASE 
                    WHEN spread_line < 0 AND (home_score - away_score) > spread_line THEN 1
                    ELSE 0 
                END) as ats_wins
            FROM games
            WHERE season = ANY(:seasons)
                AND home_team = :team
                AND spread_line BETWEEN (:min_spread * -1) AND (:max_spread * -1)
                AND game_type = 'REG'
                AND home_score IS NOT NULL
            """
        else:
            underdog_query = """
            SELECT 
                COUNT(*) as total_games,
                SUM(CASE 
                    WHEN spread_line > 0 AND (away_score - home_score) > -spread_line THEN 1
                    ELSE 0 
                END) as ats_wins
            FROM games
            WHERE season = ANY(:seasons)
                AND away_team = :team
                AND spread_line BETWEEN :min_spread AND :max_spread
                AND game_type = 'REG'
                AND home_score IS NOT NULL
            """
        
        underdog_data = conn.run(
            underdog_query,
            seasons=seasons,
            team=underdog,
            min_spread=min_spread,
            max_spread=max_spread
        )
        
        # Calculate rates
        fav_total = favored_data[0]['total_games'] if favored_data else 0
        fav_wins = favored_data[0]['ats_wins'] if favored_data else 0
        fav_rate = fav_wins / fav_total if fav_total > 0 else 0.5
        
        und_total = underdog_data[0]['total_games'] if underdog_data else 0
        und_wins = underdog_data[0]['ats_wins'] if underdog_data else 0
        und_rate = und_wins / und_total if und_total > 0 else 0.5
        
        # Normalize
        total_rate = fav_rate + und_rate
        fav_normalized = fav_rate / total_rate if total_rate > 0 else 0.5
        und_normalized = und_rate / total_rate if total_rate > 0 else 0.5
        
        return {
            'favored_rate': round(fav_rate, 3),
            'favored_record': f"{fav_wins}-{fav_total - fav_wins}",
            'underdog_rate': round(und_rate, 3),
            'underdog_record': f"{und_wins}-{und_total - und_wins}",
            'favored_normalized': fav_normalized,
            'underdog_normalized': und_normalized,
            'situation': f"{favored} {favored_location.title()} Favorite {spread_range}, {underdog} {underdog_location.title()} Underdog {spread_range}"
        }
    
    def _calc_overall_ats(self, favored: str, underdog: str, seasons: list) -> Dict:
        """Calculate overall ATS performance across all seasons"""
        conn = self.db.get_connection()
        
        query = """
        SELECT 
            team_id,
            season,
            games_played,
            ats_wins,
            ats_losses,
            ats_cover_rate
        FROM team_rankings
        WHERE team_id IN (:fav, :und)
            AND season = ANY(:seasons)
        ORDER BY team_id, season
        """
        
        data = conn.run(query, fav=favored, und=underdog, seasons=seasons)
        df = pd.DataFrame(data)
        
        if df.empty:
            return {
                'favored_rate': 0.5,
                'underdog_rate': 0.5,
                'favored_normalized': 0.5,
                'underdog_normalized': 0.5,
                'favored_record': 'N/A',
                'underdog_record': 'N/A'
            }
        
        # Weighted average by games played
        fav_df = df[df['team_id'] == favored]
        und_df = df[df['team_id'] == underdog]
        
        fav_rate = (
            (fav_df['ats_cover_rate'] * fav_df['games_played']).sum() / 
            fav_df['games_played'].sum()
        ) if not fav_df.empty else 0.5
        
        und_rate = (
            (und_df['ats_cover_rate'] * und_df['games_played']).sum() / 
            und_df['games_played'].sum()
        ) if not und_df.empty else 0.5
        
        # Normalize
        total_rate = fav_rate + und_rate
        fav_normalized = fav_rate / total_rate if total_rate > 0 else 0.5
        und_normalized = und_rate / total_rate if total_rate > 0 else 0.5
        
        fav_wins = int(fav_df['ats_wins'].sum()) if not fav_df.empty else 0
        fav_losses = int(fav_df['ats_losses'].sum()) if not fav_df.empty else 0
        und_wins = int(und_df['ats_wins'].sum()) if not und_df.empty else 0
        und_losses = int(und_df['ats_losses'].sum()) if not und_df.empty else 0
        
        return {
            'favored_rate': round(float(fav_rate), 3),
            'favored_record': f"{fav_wins}-{fav_losses}",
            'underdog_rate': round(float(und_rate), 3),
            'underdog_record': f"{und_wins}-{und_losses}",
            'favored_normalized': fav_normalized,
            'underdog_normalized': und_normalized
        }
    
    def _calc_home_away_performance(
        self, 
        favored: str, 
        underdog: str, 
        favored_home: bool,
        seasons: list
    ) -> Dict:
        """Calculate home/away win rate performance"""
        conn = self.db.get_connection()
        
        query = """
        SELECT 
            team_id,
            season,
            home_games,
            home_wins,
            away_games,
            away_wins,
            home_win_rate,
            away_win_rate
        FROM team_rankings
        WHERE team_id IN (:fav, :und)
            AND season = ANY(:seasons)
        ORDER BY team_id, season
        """
        
        data = conn.run(query, fav=favored, und=underdog, seasons=seasons)
        df = pd.DataFrame(data)
        
        if df.empty:
            return {
                'favored_rate': 0.5,
                'underdog_rate': 0.5,
                'favored_normalized': 0.5,
                'underdog_normalized': 0.5
            }
        
        fav_df = df[df['team_id'] == favored]
        und_df = df[df['team_id'] == underdog]
        
        # Get appropriate rate based on location
        if favored_home:
            fav_rate = (
                (fav_df['home_win_rate'] * fav_df['home_games']).sum() / 
                fav_df['home_games'].sum()
            ) if not fav_df.empty and fav_df['home_games'].sum() > 0 else 0.5
            
            und_rate = (
                (und_df['away_win_rate'] * und_df['away_games']).sum() / 
                und_df['away_games'].sum()
            ) if not und_df.empty and und_df['away_games'].sum() > 0 else 0.5
        else:
            fav_rate = (
                (fav_df['away_win_rate'] * fav_df['away_games']).sum() / 
                fav_df['away_games'].sum()
            ) if not fav_df.empty and fav_df['away_games'].sum() > 0 else 0.5
            
            und_rate = (
                (und_df['home_win_rate'] * und_df['home_games']).sum() / 
                und_df['home_games'].sum()
            ) if not und_df.empty and und_df['home_games'].sum() > 0 else 0.5
        
        # Normalize
        total_rate = fav_rate + und_rate
        fav_normalized = fav_rate / total_rate if total_rate > 0 else 0.5
        und_normalized = und_rate / total_rate if total_rate > 0 else 0.5
        
        return {
            'favored_rate': round(float(fav_rate), 3),
            'underdog_rate': round(float(und_rate), 3),
            'favored_normalized': fav_normalized,
            'underdog_normalized': und_normalized,
            'location': 'Home' if favored_home else 'Away'
        }

