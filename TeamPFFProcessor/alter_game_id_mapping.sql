-- =====================================================================
-- Add Team PFF Matchup Columns to game_id_mapping
-- Run ONCE in Supabase SQL Editor before running team_pff_processor.py
--
-- All columns are nullable (DEFAULT NULL) so existing rows are
-- unaffected. team_pff_processor.py will UPDATE rows with values.
-- 2022 games will remain NULL (no 2021 PFF data) → fillna(0) at training.
-- =====================================================================

-- -------------------------------------------------------------------
-- 1. Raw PFF grades per team (16 columns)
--    Source: pff_team_offense + pff_team_defense + pff_team_special_teams
--    Previous season's grades (g.season - 1) to prevent leakage.
-- -------------------------------------------------------------------
ALTER TABLE game_id_mapping
    ADD COLUMN IF NOT EXISTS home_pff_offense       NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS away_pff_offense       NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS home_pff_defense       NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS away_pff_defense       NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS home_pff_run           NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS away_pff_run           NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS home_pff_passing       NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS away_pff_passing       NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS home_pff_run_defense   NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS away_pff_run_defense   NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS home_pff_coverage      NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS away_pff_coverage      NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS home_pff_pass_rush     NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS away_pff_pass_rush     NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS home_pff_special_teams NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS away_pff_special_teams NUMERIC(5,2);

-- -------------------------------------------------------------------
-- 2. Season rankings 1-32 per grade category (12 columns)
--    Rank 1 = best grade (highest), Rank 32 = worst.
--    Computed per season from previous season PFF data.
-- -------------------------------------------------------------------
ALTER TABLE game_id_mapping
    ADD COLUMN IF NOT EXISTS home_run_offense_rank   SMALLINT,
    ADD COLUMN IF NOT EXISTS away_run_offense_rank   SMALLINT,
    ADD COLUMN IF NOT EXISTS home_pass_offense_rank  SMALLINT,
    ADD COLUMN IF NOT EXISTS away_pass_offense_rank  SMALLINT,
    ADD COLUMN IF NOT EXISTS home_run_defense_rank   SMALLINT,
    ADD COLUMN IF NOT EXISTS away_run_defense_rank   SMALLINT,
    ADD COLUMN IF NOT EXISTS home_pass_defense_rank  SMALLINT,
    ADD COLUMN IF NOT EXISTS away_pass_defense_rank  SMALLINT,
    ADD COLUMN IF NOT EXISTS home_pass_rush_rank     SMALLINT,
    ADD COLUMN IF NOT EXISTS away_pass_rush_rank     SMALLINT,
    ADD COLUMN IF NOT EXISTS home_special_teams_rank SMALLINT,
    ADD COLUMN IF NOT EXISTS away_special_teams_rank SMALLINT;

-- -------------------------------------------------------------------
-- 3. Matchup differential features (6 columns)
--    Net advantage formulas (positive = home team advantage):
--
--    run:        (home_run - away_run_def) - (away_run - home_run_def)
--    pass:       (home_pass - away_cov)    - (away_pass - home_cov)
--    trench:     (home_pass_rush - away_pass_block) - (away_pass_rush - home_pass_block)
--    overall:    (home_offense - away_defense) - (away_offense - home_defense)
--    st:         home_special_teams - away_special_teams
--    overall_diff: home_overall_grade - away_overall_grade
-- -------------------------------------------------------------------
ALTER TABLE game_id_mapping
    ADD COLUMN IF NOT EXISTS matchup_run_off_vs_run_def       NUMERIC(7,3),
    ADD COLUMN IF NOT EXISTS matchup_pass_off_vs_coverage     NUMERIC(7,3),
    ADD COLUMN IF NOT EXISTS matchup_pass_rush_vs_pass_block  NUMERIC(7,3),
    ADD COLUMN IF NOT EXISTS matchup_overall_off_vs_def       NUMERIC(7,3),
    ADD COLUMN IF NOT EXISTS matchup_special_teams            NUMERIC(7,3),
    ADD COLUMN IF NOT EXISTS pff_overall_diff                 NUMERIC(7,3);

-- -------------------------------------------------------------------
-- 4. Rank advantage features (4 columns)
--    Positive = home team advantage (lower rank = better, so
--    away_rank - home_rank > 0 means home is ranked better)
-- -------------------------------------------------------------------
ALTER TABLE game_id_mapping
    ADD COLUMN IF NOT EXISTS rank_adv_run_game        SMALLINT,
    ADD COLUMN IF NOT EXISTS rank_adv_pass_game       SMALLINT,
    ADD COLUMN IF NOT EXISTS rank_adv_rush_pressure   SMALLINT,
    ADD COLUMN IF NOT EXISTS rank_adv_special_teams   SMALLINT;

-- -------------------------------------------------------------------
-- Indexes for common filter/join patterns
-- -------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_gim_home_pff_offense
    ON game_id_mapping (home_pff_offense)
    WHERE home_pff_offense IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_gim_matchup_overall
    ON game_id_mapping (matchup_overall_off_vs_def)
    WHERE matchup_overall_off_vs_def IS NOT NULL;
