import pandas as pd

class BettingAnalyzer:
    """Analyze betting odds and spreads"""
    
    @staticmethod
    def calculate_betting_metrics(games_df: pd.DataFrame, season: int) -> pd.DataFrame:
        """
        Calculate betting-related metrics for teams
        
        Args:
            games_df: DataFrame with game data including betting lines
            season: Season to analyze
            
        Returns:
            DataFrame with betting metrics per team
        """
        season_games = games_df[games_df['season'] == season].copy()
        
        # Determine who was favored for each game
        home_favored = season_games.copy()
        home_favored['team'] = home_favored['home_team']
        home_favored['spread'] = home_favored['spread_line']
        home_favored['is_favored'] = home_favored['spread_line'] < 0
        home_favored['total'] = home_favored['total_line']
        
        away_favored = season_games.copy()
        away_favored['team'] = away_favored['away_team']
        away_favored['spread'] = -1 * away_favored['spread_line']  # Flip spread for away team
        away_favored['is_favored'] = away_favored['spread_line'] > 0
        away_favored['total'] = away_favored['total_line']
        
        all_betting = pd.concat([home_favored, away_favored], ignore_index=True)
        
        # Calculate metrics
        betting_stats = all_betting.groupby('team').agg({
            'spread': 'mean',
            'total': 'mean',
            'is_favored': 'sum'
        }).reset_index()
        
        betting_stats.columns = ['team_id', 'avg_spread_line', 'avg_total_line', 'times_favored']
        
        # Calculate times underdog
        game_counts = all_betting.groupby('team').size().reset_index(name='total_games')
        betting_stats = betting_stats.merge(game_counts, on='team_id')
        betting_stats['times_underdog'] = betting_stats['total_games'] - betting_stats['times_favored']
        betting_stats = betting_stats.drop('total_games', axis=1)
        
        betting_stats['season'] = season
        
        return betting_stats