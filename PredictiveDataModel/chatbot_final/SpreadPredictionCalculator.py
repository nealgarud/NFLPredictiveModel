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
    
    # Minimum games threshold for situational data
    MIN_SITUATIONAL_GAMES = 3      # Need at least 3 games combined to use situational data
    
    # Key NFL scoring margins (based on common scoring patterns)
    # These are the most frequent margins of victory in NFL
    KEY_NUMBERS = {
        3: 0.1552,   # Field goal - 15.52% of games
        7: 0.1018,   # Touchdown - 10.18% of games
        10: 0.0688,  # FG + TD - 6.88% of games
        6: 0.0701,   # TD no PAT - 7.01% of games
        4: 0.0543,   # FG + Safety or TD-2pt miss - 5.43% of games
        14: 0.0432,  # Two TDs - 4.32% of games
        17: 0.0289,  # TD + FG + TD - 2.89% of games
    }
    
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
        
        # Check if we have enough situational data
        total_situational_games = situational_ats.get('total_games', 0)
        data_quality_factor = min(1.0, total_situational_games / 10.0)  # Scale 0-1 based on games (10+ = full quality)
        
        print(f"\n📊 Data Quality:")
        print(f"   Situational games: {total_situational_games}")
        print(f"   Data quality factor: {data_quality_factor:.2f}")
        
        # START FROM BASELINE: Spreads should generally be 50/50 (that's how Vegas sets them)
        # Then adjust based on team intelligence, but don't let it dominate
        baseline_prob = 0.50
        
        # Calculate team intelligence factors for FAVORED team
        if total_situational_games < self.MIN_SITUATIONAL_GAMES:
            # Not enough situational data - use only overall ATS and home/away
            print(f"⚠️  Insufficient situational data - using Overall ATS + Home/Away only")
            
            favored_intelligence = (
                0.5 * overall_ats['favored_normalized'] +
                0.5 * home_away_perf['favored_normalized']
            )
        else:
            # Use all three factors
            favored_intelligence = (
            self.SITUATIONAL_ATS_WEIGHT * situational_ats['favored_normalized'] +
            self.OVERALL_ATS_WEIGHT * overall_ats['favored_normalized'] +
            self.HOME_AWAY_WEIGHT * home_away_perf['favored_normalized']
        )
        
        # Calculate team intelligence factors for UNDERDOG team (from their perspective)
        # Use underdog's historical performance when they were underdogs
        if total_situational_games < self.MIN_SITUATIONAL_GAMES:
            underdog_intelligence = (
                0.5 * overall_ats['underdog_normalized'] +
                0.5 * home_away_perf['underdog_normalized']
            )
        else:
            # Use underdog's situational ATS (when they were underdogs in this spread range)
            underdog_intelligence = (
                self.SITUATIONAL_ATS_WEIGHT * situational_ats['underdog_normalized'] +
                self.OVERALL_ATS_WEIGHT * overall_ats['underdog_normalized'] +
                self.HOME_AWAY_WEIGHT * home_away_perf['underdog_normalized']
            )
        
        # Apply team intelligence as an ADJUSTMENT to baseline for BOTH teams
        # Larger spreads often indicate mismatches (strong team vs weak), so team intelligence matters MORE
        base_adjustment_factor = 0.4  # Base ±20% adjustment with perfect data
        if spread_abs > 6:
            adjustment_factor = base_adjustment_factor * 1.2  # ±24% for large spreads
        else:
            adjustment_factor = base_adjustment_factor
        
        favored_adjustment = (favored_intelligence - 0.5) * adjustment_factor * data_quality_factor
        underdog_adjustment = (underdog_intelligence - 0.5) * adjustment_factor * data_quality_factor
        
        base_favored_prob = baseline_prob + favored_adjustment
        base_underdog_prob = baseline_prob + underdog_adjustment
        
        print(f"\n🎯 Probability Calculation (From Each Team's Perspective):")
        print(f"  Baseline (Vegas efficiency): {baseline_prob:.3f}")
        print(f"\n  FAVORED ({favored_team}):")
        print(f"    Team intelligence: {favored_intelligence:.3f}")
        print(f"    Team adjustment: {favored_adjustment:+.3f}")
        print(f"    Base probability: {base_favored_prob:.3f}")
        print(f"      - Situational ATS: {situational_ats['favored_normalized']:.3f}")
        print(f"      - Overall ATS: {overall_ats['favored_normalized']:.3f}")
        print(f"      - Home/Away: {home_away_perf['favored_normalized']:.3f}")
        print(f"\n  UNDERDOG ({underdog_team}):")
        print(f"    Team intelligence: {underdog_intelligence:.3f}")
        print(f"    Team adjustment: {underdog_adjustment:+.3f}")
        print(f"    Base probability: {base_underdog_prob:.3f}")
        print(f"      - Situational ATS: {situational_ats['underdog_normalized']:.3f}")
        print(f"      - Overall ATS: {overall_ats['underdog_normalized']:.3f}")
        print(f"      - Home/Away: {home_away_perf['underdog_normalized']:.3f}")
        
        # Calculate key number impact
        key_impact = self._calculate_key_number_impact(spread_abs)
        
        # Apply key number adjustment (gentle - key numbers matter but don't override team intelligence)
        if key_impact > 0:
            key_adjustment = -(key_impact * 0.15)  # 15% of key probability as penalty
            print(f"  Key number penalty: {key_adjustment:.3f} (crossing key numbers)")
        else:
            key_adjustment = 0.0
        
        # Apply VERY GENTLE spread difficulty adjustment
        # The logic: Larger spreads are harder to cover, BUT they also indicate better teams
        # So we apply a minimal penalty that doesn't override team intelligence
        if spread_abs <= 3:
            spread_penalty = spread_abs * 0.005  # 0.5% per point - very gentle
        elif spread_abs <= 7:
            spread_penalty = 0.015 + (spread_abs - 3) * 0.008  # ~0.5-1.5% total
        else:
            spread_penalty = 0.047 + (spread_abs - 7) * 0.01  # ~1.5-3% for large spreads
        
        print(f"  Spread penalty: -{spread_penalty:.3f} (minimal - team intelligence dominates)")
        
        # Combine all adjustments
        total_adjustment = team_adjustment + key_adjustment - spread_penalty
        favored_prob = baseline_prob + total_adjustment
        
        # Clamp to reasonable bounds (wider range to allow team intelligence to shine)
        favored_prob = max(0.30, min(0.70, favored_prob))
        
        print(f"  Final adjusted probability: {favored_prob:.3f}")
        
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
    
    def _calculate_key_number_impact(self, spread: float) -> float:
        """
        Calculate probability adjustment based on key NFL scoring numbers
        Returns the cumulative probability of landing ON a key number
        
        Key numbers represent common margins of victory (3, 7, 10, etc.)
        Spreads near these values have different covering probabilities
        """
        # Check if spread is exactly on a half-point near a key number
        # e.g., -2.5, -3.5 (around 3), -6.5, -7.5 (around 7)
        
        total_key_impact = 0.0
        
        # For each key number, see if the spread crosses it
        for key, probability in self.KEY_NUMBERS.items():
            # Check if spread is within 0.5 of the key number
            # e.g., -2.5 to -3.5 crosses the key number 3
            lower_half = key - 0.5
            upper_half = key + 0.5
            
            if lower_half <= spread <= upper_half:
                # We're right on a key number zone
                # The probability represents the "value" of that number
                total_key_impact += probability
                print(f"  Key number impact: Spread {spread} near key {key} → +{probability:.4f}")
        
        return total_key_impact
    
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
            min_spread = int(float(parts[0]))
            max_spread = int(float(parts[1]))
        
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
                AND ABS(spread_line) BETWEEN :min_spread AND :max_spread
                AND spread_line < 0
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
                AND ABS(spread_line) BETWEEN :min_spread AND :max_spread
                AND spread_line < 0
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
        
        # Calculate rates (pg8000 returns list of tuples)
        # Handle None values from database (when no matching rows)
        fav_total = favored_data[0][0] if favored_data and len(favored_data) > 0 and favored_data[0][0] is not None else 0
        fav_wins = favored_data[0][1] if favored_data and len(favored_data) > 0 and favored_data[0][1] is not None else 0
        fav_rate = fav_wins / fav_total if fav_total > 0 else 0.5
        
        und_total = underdog_data[0][0] if underdog_data and len(underdog_data) > 0 and underdog_data[0][0] is not None else 0
        und_wins = underdog_data[0][1] if underdog_data and len(underdog_data) > 0 and underdog_data[0][1] is not None else 0
        und_rate = und_wins / und_total if und_total > 0 else 0.5
        
        # Debug logging
        print(f"\n📈 Situational ATS Analysis:")
        print(f"  Spread range: {spread_range} ({min_spread}-{max_spread} points)")
        print(f"  Favored ({favored} {favored_location}): {fav_wins}/{fav_total} = {fav_rate:.1%} cover rate")
        print(f"    → Query: When {favored} was a {spread_range} point {favored_location} favorite, how often did they cover?")
        print(f"  Underdog ({underdog} {underdog_location}): {und_wins}/{und_total} = {und_rate:.1%} cover rate")
        print(f"    → Query: When {underdog} was a {spread_range} point {underdog_location} underdog, how often did they cover?")
        
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
            'situation': f"{favored} {favored_location.title()} Favorite {spread_range}, {underdog} {underdog_location.title()} Underdog {spread_range}",
            'total_games': fav_total + und_total  # Add total games for threshold check
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
        # pg8000 returns list of tuples, need to specify column names
        df = pd.DataFrame(data, columns=['team_id', 'season', 'games_played', 'ats_wins', 'ats_losses', 'ats_cover_rate'])
        
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
        total_rate = float(fav_rate) + float(und_rate)
        fav_normalized = float(fav_rate) / total_rate if total_rate > 0 else 0.5
        und_normalized = float(und_rate) / total_rate if total_rate > 0 else 0.5
        
        fav_wins = int(fav_df['ats_wins'].sum()) if not fav_df.empty else 0
        fav_losses = int(fav_df['ats_losses'].sum()) if not fav_df.empty else 0
        und_wins = int(und_df['ats_wins'].sum()) if not und_df.empty else 0
        und_losses = int(und_df['ats_losses'].sum()) if not und_df.empty else 0
        
        return {
            'favored_rate': round(float(fav_rate), 3),
            'favored_record': f"{fav_wins}-{fav_losses}",
            'underdog_rate': round(float(und_rate), 3),
            'underdog_record': f"{und_wins}-{und_losses}",
            'favored_normalized': float(fav_normalized),
            'underdog_normalized': float(und_normalized)
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
        # pg8000 returns list of tuples, need to specify column names
        df = pd.DataFrame(data, columns=['team_id', 'season', 'home_games', 'home_wins', 'away_games', 'away_wins', 'home_win_rate', 'away_win_rate'])
        
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
        total_rate = float(fav_rate) + float(und_rate)
        fav_normalized = float(fav_rate) / total_rate if total_rate > 0 else 0.5
        und_normalized = float(und_rate) / total_rate if total_rate > 0 else 0.5
        
        return {
            'favored_rate': round(float(fav_rate), 3),
            'underdog_rate': round(float(und_rate), 3),
            'favored_normalized': float(fav_normalized),
            'underdog_normalized': float(und_normalized),
            'location': 'Home' if favored_home else 'Away'
        }

