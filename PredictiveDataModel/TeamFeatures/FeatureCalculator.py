"""
FeatureCalculator.py
Computes ALL team-level features from the games table in one pass.

One row per team per season (full season totals):
  1. Home / away win rate + home advantage
  2. Division vs non-division record + div advantage
  3. Prime time record (TNF / SNF / MNF)
  4. Record vs strong / mid / weak opponents
  5. Close game ATS performance (spread <= 3)
  6. After-loss ATS performance
  7. After-bye-week ATS performance
"""

import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

GAME_COLUMNS = [
    'game_id', 'season', 'week', 'gameday',
    'home_team', 'away_team', 'home_score', 'away_score',
    'spread_line', 'div_game'
]

STRONG_THRESHOLD = 10 / 17   # ~0.588
WEAK_THRESHOLD = 7 / 17      # ~0.412


class FeatureCalculator:
    """Compute all team features from raw game rows."""

    def compute_all(self, raw_rows: list, seasons: List[int]) -> List[Dict[str, Any]]:
        """
        Main entry point.  Takes raw DB rows, returns a list of dicts
        (one per team-season) ready for upsert.
        """
        games_df = pd.DataFrame(raw_rows, columns=GAME_COLUMNS)
        games_df['gameday'] = pd.to_datetime(games_df['gameday'])
        games_df['home_score'] = pd.to_numeric(games_df['home_score'], errors='coerce')
        games_df['away_score'] = pd.to_numeric(games_df['away_score'], errors='coerce')
        games_df['spread_line'] = pd.to_numeric(games_df['spread_line'], errors='coerce')
        games_df['div_game'] = games_df['div_game'].fillna(False).astype(bool)

        logger.info(f"Computing features for {len(games_df)} games across seasons {seasons}")

        all_games = self._build_team_perspective(games_df)
        team_strength = self._compute_season_strength(all_games)
        all_games = self._enrich_opponent_strength(all_games, team_strength)
        all_games = self._compute_ats_columns(all_games, games_df)
        all_games = self._compute_bye_week_flag(all_games)

        results = self._aggregate_season_totals(all_games, seasons)
        logger.info(f"Produced {len(results)} team-season feature rows")
        return results

    # ------------------------------------------------------------------
    # Step 1: Build unified team-perspective DataFrame
    # ------------------------------------------------------------------
    def _build_team_perspective(self, df: pd.DataFrame) -> pd.DataFrame:
        home = df.copy()
        home['team'] = home['home_team']
        home['opponent'] = home['away_team']
        home['won'] = (home['home_score'] > home['away_score']).astype(int)
        home['is_home'] = 1
        home['points_scored'] = home['home_score']
        home['points_allowed'] = home['away_score']

        away = df.copy()
        away['team'] = away['away_team']
        away['opponent'] = away['home_team']
        away['won'] = (away['away_score'] > away['home_score']).astype(int)
        away['is_home'] = 0
        away['points_scored'] = away['away_score']
        away['points_allowed'] = away['home_score']

        combined = pd.concat([home, away], ignore_index=True)
        combined = combined.sort_values(['team', 'season', 'gameday']).reset_index(drop=True)
        logger.info(f"Built team perspective: {len(combined)} rows")
        return combined

    # ------------------------------------------------------------------
    # Step 2: Season-level team strength (for opponent classification)
    # ------------------------------------------------------------------
    def _compute_season_strength(self, all_games: pd.DataFrame) -> pd.DataFrame:
        strength = (
            all_games
            .groupby(['team', 'season'])['won']
            .agg(['sum', 'count'])
            .reset_index()
        )
        strength.columns = ['team', 'season', 'wins', 'games']
        strength['win_rate'] = strength['wins'] / strength['games']
        strength['strength'] = np.where(
            strength['win_rate'] >= STRONG_THRESHOLD, 'strong',
            np.where(strength['win_rate'] <= WEAK_THRESHOLD, 'weak', 'mid')
        )
        return strength

    def _enrich_opponent_strength(self, all_games: pd.DataFrame, strength: pd.DataFrame) -> pd.DataFrame:
        opp_strength = strength[['team', 'season', 'strength']].rename(
            columns={'team': 'opponent', 'strength': 'opp_strength'}
        )
        merged = all_games.merge(opp_strength, on=['opponent', 'season'], how='left')
        merged['opp_strength'] = merged['opp_strength'].fillna('mid')
        return merged

    # ------------------------------------------------------------------
    # Step 3: Rolling window columns (shifted to avoid leakage)
    # ------------------------------------------------------------------
    def _compute_rolling_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        df['rolling_form_5g'] = (
            df.groupby('team')['won']
            .transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
        )
        df['rolling_form_5g'] = df['rolling_form_5g'].fillna(0.5)
        return df

    # ------------------------------------------------------------------
    # Step 4: ATS columns
    # ------------------------------------------------------------------
    def _compute_ats_columns(self, all_games: pd.DataFrame, games_df: pd.DataFrame) -> pd.DataFrame:
        margin = all_games['points_scored'] - all_games['points_allowed']
        team_spread = np.where(
            all_games['is_home'] == 1,
            all_games['spread_line'],
            -all_games['spread_line']
        )
        all_games['ats_covered'] = np.where(
            all_games['spread_line'].isna(), np.nan,
            np.where(margin > team_spread, 1, 0)
        )
        all_games['is_close_game'] = np.where(
            all_games['spread_line'].isna(), False,
            np.abs(all_games['spread_line']) <= 3
        )

        all_games['rolling_ats_10g'] = (
            all_games.groupby('team')['ats_covered']
            .transform(lambda x: x.shift(1).rolling(10, min_periods=1).mean())
        )
        all_games['rolling_ats_10g'] = all_games['rolling_ats_10g'].fillna(0.5)

        # Prime time flag
        all_games['day_of_week'] = all_games['gameday'].dt.day_name()
        all_games['hour'] = all_games['gameday'].dt.hour
        all_games['is_prime_time'] = (
            (all_games['day_of_week'] == 'Thursday') |
            (all_games['day_of_week'] == 'Monday') |
            ((all_games['day_of_week'] == 'Sunday') & (all_games['hour'] >= 20))
        ).astype(int)

        # Previous game result (for after-loss calc)
        all_games['prev_won'] = all_games.groupby('team')['won'].shift(1)

        return all_games

    # ------------------------------------------------------------------
    # Step 5: Bye week detection
    # ------------------------------------------------------------------
    def _compute_bye_week_flag(self, df: pd.DataFrame) -> pd.DataFrame:
        df['prev_gameday'] = df.groupby('team')['gameday'].shift(1)
        df['rest_days'] = (df['gameday'] - df['prev_gameday']).dt.days
        df['after_bye'] = np.where(df['rest_days'] >= 14, 1, 0)
        return df

    # ------------------------------------------------------------------
    # Step 6: Aggregate full-season totals per team
    # ------------------------------------------------------------------
    def _aggregate_season_totals(self, df: pd.DataFrame, seasons: List[int]) -> List[Dict[str, Any]]:
        results = []

        for season in seasons:
            season_df = df[df['season'] == season].copy()
            teams = season_df['team'].unique()

            for team in sorted(teams):
                tdf = season_df[season_df['team'] == team]
                gp = len(tdf)
                if gp == 0:
                    continue

                home_g = tdf[tdf['is_home'] == 1]
                away_g = tdf[tdf['is_home'] == 0]
                hw, hg = int(home_g['won'].sum()), len(home_g)
                aw, ag = int(away_g['won'].sum()), len(away_g)
                hwr = hw / hg if hg > 0 else 0.5
                awr = aw / ag if ag > 0 else 0.5

                div_g = tdf[tdf['div_game'] == True]
                ndiv_g = tdf[tdf['div_game'] == False]
                dw, dg = int(div_g['won'].sum()), len(div_g)
                ndw, ndg = int(ndiv_g['won'].sum()), len(ndiv_g)
                dwr = dw / dg if dg > 0 else 0.5
                ndwr = ndw / ndg if ndg > 0 else 0.5

                pt = tdf[tdf['is_prime_time'] == 1]
                ptw, ptg = int(pt['won'].sum()), len(pt)
                ptwr = ptw / ptg if ptg > 0 else 0.5

                vs_s = tdf[tdf['opp_strength'] == 'strong']
                vs_m = tdf[tdf['opp_strength'] == 'mid']
                vs_w = tdf[tdf['opp_strength'] == 'weak']
                vsw_s, vsg_s = int(vs_s['won'].sum()), len(vs_s)
                vsw_m, vsg_m = int(vs_m['won'].sum()), len(vs_m)
                vsw_w, vsg_w = int(vs_w['won'].sum()), len(vs_w)

                close = tdf[(tdf['is_close_game'] == True) & (tdf['ats_covered'].notna())]
                cg_covers = int(close['ats_covered'].sum()) if len(close) > 0 else 0
                cg_total = len(close)

                after_loss = tdf[(tdf['prev_won'] == 0) & (tdf['ats_covered'].notna())]
                al_covers = int(after_loss['ats_covered'].sum()) if len(after_loss) > 0 else 0
                al_total = len(after_loss)

                after_bye = tdf[(tdf['after_bye'] == 1) & (tdf['ats_covered'].notna())]
                ab_covers = int(after_bye['ats_covered'].sum()) if len(after_bye) > 0 else 0
                ab_total = len(after_bye)

                results.append({
                    'team_id': team,
                    'season': int(season),
                    'games_played': gp,
                    'home_wins': hw, 'home_games': hg,
                    'home_win_rate': round(hwr, 4),
                    'away_wins': aw, 'away_games': ag,
                    'away_win_rate': round(awr, 4),
                    'home_advantage': round(hwr - awr, 4),
                    'div_wins': dw, 'div_games': dg,
                    'div_win_rate': round(dwr, 4),
                    'non_div_wins': ndw, 'non_div_games': ndg,
                    'non_div_win_rate': round(ndwr, 4),
                    'div_advantage': round(dwr - ndwr, 4),
                    'prime_time_wins': ptw, 'prime_time_games': ptg,
                    'prime_time_win_rate': round(ptwr, 4),
                    'vs_strong_wins': vsw_s, 'vs_strong_games': vsg_s,
                    'vs_strong_win_rate': round(vsw_s / vsg_s, 4) if vsg_s > 0 else 0.5,
                    'vs_mid_wins': vsw_m, 'vs_mid_games': vsg_m,
                    'vs_mid_win_rate': round(vsw_m / vsg_m, 4) if vsg_m > 0 else 0.5,
                    'vs_weak_wins': vsw_w, 'vs_weak_games': vsg_w,
                    'vs_weak_win_rate': round(vsw_w / vsg_w, 4) if vsg_w > 0 else 0.5,
                    'close_game_ats_covers': cg_covers,
                    'close_game_ats_total': cg_total,
                    'close_game_ats_rate': round(cg_covers / cg_total, 4) if cg_total > 0 else 0.5,
                    'after_loss_ats_covers': al_covers,
                    'after_loss_ats_total': al_total,
                    'after_loss_ats_rate': round(al_covers / al_total, 4) if al_total > 0 else 0.5,
                    'after_bye_ats_covers': ab_covers,
                    'after_bye_ats_total': ab_total,
                    'after_bye_ats_rate': round(ab_covers / ab_total, 4) if ab_total > 0 else 0.5,
                })

        return results
