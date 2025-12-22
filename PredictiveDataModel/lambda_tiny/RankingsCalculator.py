import pandas as pd

class RankingsCalculator:
    """Calculate offensive, defensive, and overall rankings"""
    
    @staticmethod
    def calculate_rankings(stats_df: pd.DataFrame) -> pd.DataFrame:
        """
        Add ranking columns to team stats
        
        Args:
            stats_df: DataFrame with team statistics
            
        Returns:
            DataFrame with added rank columns
        """
        # Offensive rank (highest points scored = rank 1)
        stats_df['offensive_rank'] = stats_df['avg_points_scored'].rank(
            ascending=False, method='min'
        ).astype(int)
        
        # Defensive rank (lowest points allowed = rank 1)
        stats_df['defensive_rank'] = stats_df['avg_points_allowed'].rank(
            ascending=True, method='min'
        ).astype(int)
        
        # Overall rank (combination of win rate and point differential)
        # Normalize both to 0-1 scale
        stats_df['win_rate_norm'] = (
            (stats_df['win_rate'] - stats_df['win_rate'].min()) / 
            (stats_df['win_rate'].max() - stats_df['win_rate'].min())
        )
        
        stats_df['point_diff_norm'] = (
            (stats_df['point_differential'] - stats_df['point_differential'].min()) / 
            (stats_df['point_differential'].max() - stats_df['point_differential'].min())
        )
        
        # Overall score (70% win rate, 30% point differential)
        stats_df['overall_score'] = (
            0.7 * stats_df['win_rate_norm'] + 
            0.3 * stats_df['point_diff_norm']
        )
        
        stats_df['overall_rank'] = stats_df['overall_score'].rank(
            ascending=False, method='min'
        ).astype(int)
        
        # Drop temporary columns
        stats_df = stats_df.drop(['win_rate_norm', 'point_diff_norm', 'overall_score'], axis=1)
        
        return stats_df