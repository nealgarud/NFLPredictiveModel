import pandas as pd
from typing import Dict, Any

class AggregateCalculator:
    """Calculate aggregate team statistics from game data"""
    
    @staticmethod
    def calculate_team_stats(games_df: pd.DataFrame, season: int) -> pd.DataFrame:
        """
        Calculate all team statistics for a season
        
        Args:
            games_df: DataFrame with game data
            season: Season to calculate for
            
        Returns:
            DataFrame with team statistics
        """
        # Filter to season
        season_games = games_df[games_df['season'] == season].copy()
        
        # Create team game records (home + away)
        home_games = season_games.copy()
        home_games['team'] = home_games['home_team']
        home_games['is_home'] = True
        home_games['points_scored'] = home_games['home_score']
        home_games['points_allowed'] = home_games['away_score']
        home_games['won'] = home_games['home_score'] > home_games['away_score']
        home_games['tied'] = home_games['home_score'] == home_games['away_score']
        
        away_games = season_games.copy()
        away_games['team'] = away_games['away_team']
        away_games['is_home'] = False
        away_games['points_scored'] = away_games['away_score']
        away_games['points_allowed'] = away_games['home_score']
        away_games['won'] = away_games['away_score'] > away_games['home_score']
        away_games['tied'] = away_games['away_score'] == away_games['home_score']
        
        # Combine
        all_games = pd.concat([home_games, away_games], ignore_index=True)
        
        # Calculate aggregates
        stats = all_games.groupby('team').agg({
            'game_id': 'count',  # games_played
            'won': 'sum',  # wins
            'tied': 'sum',  # ties
            'points_scored': ['sum', 'mean'],
            'points_allowed': ['sum', 'mean'],
            'div_game': 'sum'  # div_games
        }).reset_index()
        
        # Flatten column names
        stats.columns = [
            'team_id', 'games_played', 'wins', 'ties',
            'total_points_scored', 'avg_points_scored',
            'total_points_allowed', 'avg_points_allowed',
            'div_games'
        ]
        
        # Calculate derived fields
        stats['losses'] = stats['games_played'] - stats['wins'] - stats['ties']
        stats['win_rate'] = (stats['wins'] + 0.5 * stats['ties']) / stats['games_played']
        stats['point_differential'] = stats['total_points_scored'] - stats['total_points_allowed']
        stats['avg_point_differential'] = stats['avg_points_scored'] - stats['avg_points_allowed']
        
        # Home/Away splits
        home_stats = AggregateCalculator._calculate_home_away_stats(all_games, True)
        away_stats = AggregateCalculator._calculate_home_away_stats(all_games, False)
        
        # Merge
        stats = stats.merge(home_stats, on='team_id', how='left')
        stats = stats.merge(away_stats, on='team_id', how='left')
        
        # Divisional stats
        div_stats = AggregateCalculator._calculate_divisional_stats(all_games)
        stats = stats.merge(div_stats, on='team_id', how='left')
        
        stats['season'] = season
        
        return stats
    
    @staticmethod
    def _calculate_home_away_stats(all_games: pd.DataFrame, is_home: bool) -> pd.DataFrame:
        """Calculate home or away specific stats"""
        prefix = 'home' if is_home else 'away'
        filtered = all_games[all_games['is_home'] == is_home].copy()
        
        stats = filtered.groupby('team').agg({
            'game_id': 'count',
            'won': 'sum',
            'points_scored': 'mean',
            'points_allowed': 'mean'
        }).reset_index()
        
        stats.columns = [
            'team_id',
            f'{prefix}_games',
            f'{prefix}_wins',
            f'{prefix}_avg_points_scored',
            f'{prefix}_avg_points_allowed'
        ]
        
        stats[f'{prefix}_losses'] = stats[f'{prefix}_games'] - stats[f'{prefix}_wins']
        stats[f'{prefix}_win_rate'] = stats[f'{prefix}_wins'] / stats[f'{prefix}_games']
        
        return stats
    
    @staticmethod
    def _calculate_divisional_stats(all_games: pd.DataFrame) -> pd.DataFrame:
        """Calculate divisional game stats"""
        div_games = all_games[all_games['div_game'] == True].copy()
        
        stats = div_games.groupby('team').agg({
            'game_id': 'count',
            'won': 'sum'
        }).reset_index()
        
        stats.columns = ['team_id', 'div_games_count', 'div_wins']
        stats['div_losses'] = stats['div_games_count'] - stats['div_wins']
        stats['div_win_rate'] = stats['div_wins'] / stats['div_games_count']
        
        return stats