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
    SITUATIONAL_ATS_WEIGHT = 0.35  # 35% - Most predictive
    OVERALL_ATS_WEIGHT = 0.25      # 25% - Historical consistency
    HOME_AWAY_WEIGHT = 0.25         # 25% - Location performance
    RECENT_FORM_WEIGHT = 0.15      # 15% - Recent momentum
    
    def __init__(self):
        """Initialize with database connection"""
        self.db = DatabaseConnection()
        
    def predict_spread_coverage(
        self, 
        team_a: str, 
        team_b: str, 
        spread: float,
        team_a_home: bool,
        seasons: list = [2024, 2025],
        current_season: Optional[int] = None,
        current_week: Optional[int] = None
    ) -> Dict:
        """
        Predict which team will cover the spread
        
        Args:
            team_a: Favored team abbreviation (e.g., 'GB')
            team_b: Underdog team abbreviation (e.g., 'PIT')
            spread: Point spread (positive for team_a favored, e.g., -2.5)
            team_a_home: True if team_a is home, False if away
            seasons: List of seasons to include (default: [2024, 2025])
            current_season: Season of game being predicted (optional, for form calculation)
            current_week: Week of game being predicted (optional, for form calculation)
            
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
        
        # Calculate recent form for both teams
        favored_form = self._calc_recent_form(
            favored_team, current_season, current_week, seasons
        )
        
        underdog_form = self._calc_recent_form(
            underdog_team, current_season, current_week, seasons
        )
        
        # Calculate divisional performance
        divisional_data = self._calc_divisional_performance(
            favored_team, underdog_team, seasons
        )
        
        # Calculate opponent strength
        opponent_strength = self._calc_opponent_strength(
            favored_team, underdog_team, seasons
        )
        
        # Weighted probability calculation
        favored_prob = (
            self.SITUATIONAL_ATS_WEIGHT * situational_ats['favored_normalized'] +
            self.OVERALL_ATS_WEIGHT * overall_ats['favored_normalized'] +
            self.HOME_AWAY_WEIGHT * home_away_perf['favored_normalized'] +
            self.RECENT_FORM_WEIGHT * favored_form['form_rate']
        )
        
        # Apply adjustments
        divisional_adjustment = divisional_data.get('adjustment', 0.0) if divisional_data.get('is_divisional', False) else 0.0
        opponent_adjustment = opponent_strength.get('adjustment', 0.0)
        
        favored_prob = favored_prob + divisional_adjustment + opponent_adjustment
        favored_prob = max(0.0, min(1.0, favored_prob))  # Clamp between 0 and 1
        
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
                'home_away': home_away_perf,
                'recent_form': {
                    'favored': favored_form,
                    'underdog': underdog_form
                },
                'divisional': divisional_data,
                'opponent_strength': opponent_strength
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
                AND spread_line BETWEEN -:max_spread AND -:min_spread
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
                AND spread_line BETWEEN -:max_spread AND -:min_spread
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

    def _calc_recent_form(
        self,
        team: str,
        current_season: Optional[int],
        current_week: Optional[int],
        seasons: list
    ) -> Dict:
        """
        Calculate team's recent form (win rate in last 5 games)
        
        Args:
            team: Team abbreviation (e.g., 'KC')
            current_season: Season of game being predicted (optional)
            current_week: Week of game being predicted (optional)
            seasons: List of seasons to query (e.g., [2024, 2025])
        
        Returns:
            Dictionary with form_rate, games_count, wins, losses
        """
        conn = self.db.get_connection()
        
        # Build query with optional current game exclusion
        if current_season is not None and current_week is not None:
            query = """
            SELECT 
                season,
                week,
                gameday,
                home_team,
                away_team,
                home_score,
                away_score,
                CASE 
                    WHEN home_team = :team AND home_score > away_score THEN 1
                    WHEN away_team = :team AND away_score > home_score THEN 1
                    ELSE 0
                END as won
            FROM games
            WHERE (home_team = :team OR away_team = :team)
                AND season = ANY(:seasons)
                AND game_type = 'REG'
                AND home_score IS NOT NULL
                AND (
                    season < :current_season 
                    OR (season = :current_season AND week < :current_week)
                )
            ORDER BY season DESC, week DESC, gameday DESC
            LIMIT 5
            """
            data = conn.run(query, team=team, seasons=seasons, current_season=current_season, current_week=current_week)
        else:
            # If no current_season/week provided, just get last 5 games
            query = """
            SELECT 
                season,
                week,
                gameday,
                home_team,
                away_team,
                home_score,
                away_score,
                CASE 
                    WHEN home_team = :team AND home_score > away_score THEN 1
                    WHEN away_team = :team AND away_score > home_score THEN 1
                    ELSE 0
                END as won
            FROM games
            WHERE (home_team = :team OR away_team = :team)
                AND season = ANY(:seasons)
                AND game_type = 'REG'
                AND home_score IS NOT NULL
            ORDER BY season DESC, week DESC, gameday DESC
            LIMIT 5
            """
            data = conn.run(query, team=team, seasons=seasons)
        
        # Convert to DataFrame
        df = pd.DataFrame(data, columns=['season', 'week', 'gameday', 'home_team', 'away_team', 'home_score', 'away_score', 'won'])
        
        # Handle empty result
        if df.empty:
            return {
                'form_rate': 0.5,
                'games_count': 0,
                'wins': 0,
                'losses': 0
            }
        
        # Aggregate (no groupby needed - all rows are for same team)
        games_count = len(df)
        wins = int(df['won'].sum())
        losses = games_count - wins
        win_rate = wins / games_count if games_count > 0 else 0.5
        
        return {
            'form_rate': round(win_rate, 3),
            'games_count': games_count,
            'wins': wins,
            'losses': losses
        }

    def _calc_divisional_performance(
        self,
        favored: str,
        underdog: str,
        seasons: list
    ) -> Dict:
        """
        Calculate ATS performance in division vs non-division games
        
        Args:
            favored: Favored team abbreviation
            underdog: Underdog team abbreviation
            seasons: List of seasons to query
            
        Returns:
            Dictionary with divisional ATS, non-divisional ATS, is_divisional flag, and adjustment
        """
        conn = self.db.get_connection()
        
        # Check if this is a divisional matchup
        check_divisional_query = """
        SELECT div_game
        FROM games
        WHERE ((home_team = :team1 AND away_team = :team2)
               OR (home_team = :team2 AND away_team = :team1))
            AND season = ANY(:seasons)
            AND game_type = 'REG'
        LIMIT 1
        """
        
        div_check = conn.run(check_divisional_query, team1=favored, team2=underdog, seasons=seasons)
        # pg8000 returns list of tuples, access first element of first tuple
        is_divisional = div_check[0][0] if div_check and len(div_check) > 0 and div_check[0][0] is not None else False
        
        # Query all games for favored team, split by divisional status
        query = """
        SELECT 
            div_game,
            CASE 
                WHEN (home_team = :team AND spread_line > 0 AND (home_score - away_score) > spread_line)
                     OR (away_team = :team AND spread_line < 0 AND (away_score - home_score) > ABS(spread_line))
                THEN 1
                WHEN (home_team = :team AND spread_line > 0 AND (home_score - away_score) <= spread_line)
                     OR (away_team = :team AND spread_line < 0 AND (away_score - home_score) <= ABS(spread_line))
                THEN 0
                ELSE NULL
            END as ats_covered
        FROM games
        WHERE (home_team = :team OR away_team = :team)
            AND season = ANY(:seasons)
            AND game_type = 'REG'
            AND home_score IS NOT NULL
            AND spread_line IS NOT NULL
        """
        
        data = conn.run(query, team=favored, seasons=seasons)
        df = pd.DataFrame(data, columns=['div_game', 'ats_covered'])
        
        if df.empty:
            return {
                'is_divisional': bool(is_divisional),
                'divisional_ats': 0.5,
                'non_divisional_ats': 0.5,
                'divisional_games': 0,
                'non_divisional_games': 0,
                'adjustment': 0.0
            }
        
        # Filter out NULL ATS results
        df = df[df['ats_covered'].notna()]
        
        # Split by divisional status
        div_games = df[df['div_game'] == True]
        non_div_games = df[df['div_game'] == False]
        
        # Calculate ATS rates
        div_ats = div_games['ats_covered'].mean() if len(div_games) > 0 else 0.5
        non_div_ats = non_div_games['ats_covered'].mean() if len(non_div_games) > 0 else 0.5
        
        # Calculate adjustment: Underdogs cover more in division games
        # If divisional game: +2-3% for underdog, -1-2% for favorite
        if is_divisional:
            # Underdog gets boost, favorite gets penalty
            adjustment = -0.015  # -1.5% for favorite in division game
        else:
            adjustment = 0.0
        
        return {
            'is_divisional': bool(is_divisional),
            'divisional_ats': round(float(div_ats), 3),
            'non_divisional_ats': round(float(non_div_ats), 3),
            'divisional_games': len(div_games),
            'non_divisional_games': len(non_div_games),
            'adjustment': round(adjustment, 3)
        }

    def _calc_opponent_strength(
        self,
        team: str,
        opponent: str,
        seasons: list
    ) -> Dict:
        """
        Classify opponent strength and calculate team's ATS performance vs that tier
        
        Args:
            team: Team abbreviation (favored team)
            opponent: Opponent abbreviation (underdog team)
            seasons: List of seasons to query
            
        Returns:
            Dictionary with opponent_tier, ats_vs_tier, and adjustment
        """
        conn = self.db.get_connection()
        
        # Step 1: Calculate opponent's win rate to classify strength
        opponent_win_rate_query = """
        SELECT 
            COUNT(*) as total_games,
            SUM(CASE 
                WHEN home_team = :team AND home_score > away_score THEN 1
                WHEN away_team = :team AND away_score > home_score THEN 1
                ELSE 0
            END) as wins
        FROM games
        WHERE (home_team = :team OR away_team = :team)
            AND season = ANY(:seasons)
            AND game_type = 'REG'
            AND home_score IS NOT NULL
        """
        
        opp_data = conn.run(opponent_win_rate_query, team=opponent, seasons=seasons)
        opp_total = opp_data[0][0] if opp_data and len(opp_data) > 0 and opp_data[0][0] is not None else 0
        opp_wins = opp_data[0][1] if opp_data and len(opp_data) > 0 and opp_data[0][1] is not None else 0
        opp_win_rate = opp_wins / opp_total if opp_total > 0 else 0.5
        
        # Classify opponent strength
        if opp_win_rate > (10/17):  # > 0.588
            opponent_tier = 'Strong'
        elif opp_win_rate < (7/17):  # < 0.412
            opponent_tier = 'Weak'
        else:
            opponent_tier = 'Mediocre'
        
        # Step 2: Get all games for the team and identify opponents
        team_games_query = """
        SELECT 
            CASE 
                WHEN home_team = :team THEN away_team
                ELSE home_team
            END as opponent,
            CASE 
                WHEN (home_team = :team AND spread_line > 0 AND (home_score - away_score) > spread_line)
                     OR (away_team = :team AND spread_line < 0 AND (away_score - home_score) > ABS(spread_line))
                THEN 1
                WHEN (home_team = :team AND spread_line > 0 AND (home_score - away_score) <= spread_line)
                     OR (away_team = :team AND spread_line < 0 AND (away_score - home_score) <= ABS(spread_line))
                THEN 0
                ELSE NULL
            END as ats_covered
        FROM games
        WHERE (home_team = :team OR away_team = :team)
            AND season = ANY(:seasons)
            AND game_type = 'REG'
            AND home_score IS NOT NULL
            AND spread_line IS NOT NULL
        """
        
        team_games_data = conn.run(team_games_query, team=team, seasons=seasons)
        team_games_df = pd.DataFrame(team_games_data, columns=['opponent', 'ats_covered'])
        team_games_df = team_games_df[team_games_df['ats_covered'].notna()]
        
        if team_games_df.empty:
            return {
                'opponent_tier': opponent_tier,
                'ats_vs_tier': 0.5,
                'games_vs_tier': 0,
                'adjustment': 0.0
            }
        
        # Step 3: Calculate opponent win rates for classification
        # For each unique opponent in team's games, calculate their win rate
        unique_opponents = team_games_df['opponent'].unique()
        opponent_win_rates = {}
        
        for opp in unique_opponents:
            opp_win_query = """
            SELECT 
                COUNT(*) as total_games,
                SUM(CASE 
                    WHEN home_team = :opp AND home_score > away_score THEN 1
                    WHEN away_team = :opp AND away_score > home_score THEN 1
                    ELSE 0
                END) as wins
            FROM games
            WHERE (home_team = :opp OR away_team = :opp)
                AND season = ANY(:seasons)
                AND game_type = 'REG'
                AND home_score IS NOT NULL
            """
            opp_win_data = conn.run(opp_win_query, opp=opp, seasons=seasons)
            opp_total_games = opp_win_data[0][0] if opp_win_data and len(opp_win_data) > 0 and opp_win_data[0][0] is not None else 0
            opp_wins_count = opp_win_data[0][1] if opp_win_data and len(opp_win_data) > 0 and opp_win_data[0][1] is not None else 0
            opp_win_rate = opp_wins_count / opp_total_games if opp_total_games > 0 else 0.5
            opponent_win_rates[opp] = opp_win_rate
        
        # Classify each opponent
        team_games_df['opponent_tier'] = team_games_df['opponent'].map(
            lambda opp: 'Strong' if opponent_win_rates.get(opp, 0.5) > (10/17)
            else 'Weak' if opponent_win_rates.get(opp, 0.5) < (7/17)
            else 'Mediocre'
        )
        
        # Step 4: Calculate ATS rate vs the current opponent's tier
        tier_games = team_games_df[team_games_df['opponent_tier'] == opponent_tier]
        ats_vs_tier = tier_games['ats_covered'].mean() if len(tier_games) > 0 else 0.5
        
        # Step 5: Calculate adjustment
        # If facing strong opponent: reduce favored probability by 2-3%
        # If facing weak opponent: increase favored probability by 1-2%
        if opponent_tier == 'Strong':
            adjustment = -0.025  # -2.5% for facing strong opponent
        elif opponent_tier == 'Weak':
            adjustment = 0.015  # +1.5% for facing weak opponent
        else:
            adjustment = 0.0  # No adjustment for mediocre
        
        return {
            'opponent_tier': opponent_tier,
            'opponent_win_rate': round(opp_win_rate, 3),
            'ats_vs_tier': round(float(ats_vs_tier), 3),
            'games_vs_tier': len(tier_games),
            'adjustment': round(adjustment, 3)
        }

    def _calc_after_loss_performance(
        self,
        team: str,
        current_season: Optional[int],
        current_week: Optional[int],
        seasons: list
    ) -> Dict:
        """
        Calculate ATS performance in games following a loss vs following a win
        
        Args:
            team: Team abbreviation
            current_season: Season of game being predicted (optional)
            current_week: Week of game being predicted (optional)
            seasons: List of seasons to query
            
        Returns:
            Dictionary with ats_after_loss, ats_after_win, coming_off_loss flag, and adjustment
        """
        conn = self.db.get_connection()
        
        # Query 1: Check if team lost their previous game
        check_previous_loss_query = """
        SELECT 
            CASE 
                WHEN (home_team = :team AND home_score < away_score)
                     OR (away_team = :team AND away_score < home_score)
                THEN 1  -- Lost
                ELSE 0   -- Won or tied
            END as lost_previous_game
        FROM games
        WHERE (home_team = :team OR away_team = :team)
            AND season = ANY(:seasons)
            AND game_type = 'REG'
            AND home_score IS NOT NULL
            AND (
                (:current_season IS NULL OR season < :current_season) 
                OR (:current_season IS NOT NULL AND season = :current_season AND (:current_week IS NULL OR week < :current_week))
            )
        ORDER BY season DESC, week DESC, gameday DESC
        LIMIT 1
        """
        
        prev_loss_check = conn.run(
            check_previous_loss_query, 
            team=team, 
            seasons=seasons,
            current_season=current_season,
            current_week=current_week
        )
        # pg8000 returns list of tuples
        coming_off_loss = prev_loss_check[0][0] == 1 if prev_loss_check and len(prev_loss_check) > 0 else False
        
        # Query 2: Get all games with previous game result flag
        # This query gets games ordered chronologically with win/loss result
        team_games_query = """
        SELECT 
            season,
            week,
            gameday,
            CASE 
                WHEN (home_team = :team AND home_score > away_score)
                     OR (away_team = :team AND away_score > home_score)
                THEN 1  -- Won
                WHEN (home_team = :team AND home_score < away_score)
                     OR (away_team = :team AND away_score < home_score)
                THEN 0  -- Lost
                ELSE 0.5  -- Tied
            END as game_result,
            CASE 
                WHEN (home_team = :team AND spread_line > 0 AND (home_score - away_score) > spread_line)
                     OR (away_team = :team AND spread_line < 0 AND (away_score - home_score) > ABS(spread_line))
                THEN 1
                WHEN (home_team = :team AND spread_line > 0 AND (home_score - away_score) <= spread_line)
                     OR (away_team = :team AND spread_line < 0 AND (away_score - home_score) <= ABS(spread_line))
                THEN 0
                ELSE NULL
            END as ats_covered
        FROM games
        WHERE (home_team = :team OR away_team = :team)
            AND season = ANY(:seasons)
            AND game_type = 'REG'
            AND home_score IS NOT NULL
            AND spread_line IS NOT NULL
        ORDER BY season ASC, week ASC, gameday ASC
        """
        
        data = conn.run(team_games_query, team=team, seasons=seasons)
        # Convert to DataFrame with column names
        df = pd.DataFrame(data, columns=['season', 'week', 'gameday', 'game_result', 'ats_covered'])
        
        # YOUR PANDAS CODE HERE:
        # 1. Filter out NULL ats_covered values
        # 2. Create a column indicating if previous game was a loss
        #    (Hint: Use .shift(1) to look at previous row's game_result)
        # 3. Split into "after loss" vs "after win" games
        # 4. Calculate mean ATS rate for each group
        # 5. Count games in each group
        
        # Calculate adjustment based on performance difference
        # If team performs worse after loss: negative adjustment
        # If team performs better after loss (bounce-back): positive adjustment
        if coming_off_loss:
            # adjustment = (ats_after_loss - ats_after_win) * some_factor
            adjustment = 0.0  # Replace with your calculated adjustment
        else:
            adjustment = 0.0
        
        return {
            'coming_off_loss': bool(coming_off_loss),
            'ats_after_loss': 0.5,  # Replace with your calculated value
            'ats_after_win': 0.5,  # Replace with your calculated value
            'games_after_loss': 0,  # Replace with your calculated value
            'games_after_win': 0,  # Replace with your calculated value
            'adjustment': round(adjustment, 3)
        }


        