import pandas as pd
import numpy as np

class BettingAnalyzer:
    """Analyze betting odds and spreads including ATS (Against The Spread) performance"""
    
    @staticmethod
    def calculate_betting_metrics(games_df: pd.DataFrame, season: int) -> pd.DataFrame:
        """
        Calculate betting-related metrics for teams including ATS performance
        
        Args:
            games_df: DataFrame with game data including betting lines
            season: Season to analyze
            
        Returns:
            DataFrame with betting metrics per team
        """
        season_games = games_df[games_df['season'] == season].copy()
        
        # Filter out games without betting lines or scores
        season_games = season_games[
            season_games['spread_line'].notna() & 
            season_games['home_score'].notna() & 
            season_games['away_score'].notna()
        ].copy()
        
        if len(season_games) == 0:
            # Return empty DataFrame with expected columns if no data
            return pd.DataFrame(columns=[
                'team_id', 'avg_spread_line', 'avg_total_line', 'times_favored', 
                'times_underdog', 'ats_wins', 'ats_losses', 'ats_pushes', 
                'ats_cover_rate', 'avg_spread_margin', 'season'
            ])
        
        # Calculate actual margins
        season_games['actual_margin'] = season_games['home_score'] - season_games['away_score']
        
        # Process home team betting data
        home_betting = season_games.copy()
        home_betting['team'] = home_betting['home_team']
        home_betting['spread'] = home_betting['spread_line']
        home_betting['is_favored'] = home_betting['spread_line'] < 0
        home_betting['total'] = home_betting['total_line']
        home_betting['points_scored'] = home_betting['home_score']
        home_betting['points_allowed'] = home_betting['away_score']
        home_betting['margin'] = home_betting['actual_margin']
        
        # ATS calculation for home team
        # Home team covers if: actual_margin + spread_line > 0
        home_betting['spread_margin'] = home_betting['actual_margin'] + home_betting['spread_line']
        home_betting['ats_result'] = np.where(
            home_betting['spread_margin'] > 0, 'win',
            np.where(home_betting['spread_margin'] < 0, 'loss', 'push')
        )
        
        # Process away team betting data
        away_betting = season_games.copy()
        away_betting['team'] = away_betting['away_team']
        away_betting['spread'] = -1 * away_betting['spread_line']  # Flip spread for away team
        away_betting['is_favored'] = away_betting['spread_line'] > 0
        away_betting['total'] = away_betting['total_line']
        away_betting['points_scored'] = away_betting['away_score']
        away_betting['points_allowed'] = away_betting['home_score']
        away_betting['margin'] = -1 * away_betting['actual_margin']
        
        # ATS calculation for away team
        # Away team covers if: -actual_margin + (-spread_line) > 0
        away_betting['spread_margin'] = -away_betting['actual_margin'] - away_betting['spread_line']
        away_betting['ats_result'] = np.where(
            away_betting['spread_margin'] > 0, 'win',
            np.where(away_betting['spread_margin'] < 0, 'loss', 'push')
        )
        
        # Combine home and away data
        all_betting = pd.concat([home_betting, away_betting], ignore_index=True)
        
        # Calculate basic betting metrics
        betting_stats = all_betting.groupby('team').agg({
            'spread': 'mean',
            'total': 'mean',
            'is_favored': 'sum'
        }).reset_index()
        
        betting_stats.columns = ['team_id', 'avg_spread_line', 'avg_total_line', 'times_favored']
        
        # Calculate times underdog
        game_counts = all_betting.groupby('team').size().reset_index(name='total_games')
        betting_stats = betting_stats.merge(game_counts, left_on='team_id', right_on='team')
        betting_stats['times_underdog'] = betting_stats['total_games'] - betting_stats['times_favored']
        
        # Calculate ATS metrics
        ats_stats = all_betting.groupby('team').agg({
            'ats_result': lambda x: (x == 'win').sum(),
            'spread_margin': 'mean'
        }).reset_index()
        ats_stats.columns = ['team_id', 'ats_wins', 'avg_spread_margin']
        
        ats_losses = all_betting[all_betting['ats_result'] == 'loss'].groupby('team').size().reset_index(name='ats_losses')
        ats_pushes = all_betting[all_betting['ats_result'] == 'push'].groupby('team').size().reset_index(name='ats_pushes')
        
        # Merge ATS stats
        betting_stats = betting_stats.merge(ats_stats, on='team_id', how='left')
        betting_stats = betting_stats.merge(ats_losses, left_on='team_id', right_on='team', how='left')
        betting_stats = betting_stats.merge(ats_pushes, left_on='team_id', right_on='team', how='left')
        
        # Fill NaN values for teams with no losses or pushes
        betting_stats['ats_losses'] = betting_stats['ats_losses'].fillna(0).astype(int)
        betting_stats['ats_pushes'] = betting_stats['ats_pushes'].fillna(0).astype(int)
        
        # Calculate ATS cover rate (excluding pushes)
        betting_stats['ats_cover_rate'] = betting_stats.apply(
            lambda row: row['ats_wins'] / (row['ats_wins'] + row['ats_losses']) 
            if (row['ats_wins'] + row['ats_losses']) > 0 else 0,
            axis=1
        )
        
        # Clean up extra columns
        betting_stats = betting_stats.drop(['total_games', 'team'], axis=1, errors='ignore')
        
        betting_stats['season'] = season
        
        return betting_stats