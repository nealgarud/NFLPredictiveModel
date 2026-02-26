-- =====================================================
-- Add Player Impact Columns to game_id_mapping Table
-- Run this ONCE to add PFF impact columns
-- =====================================================

-- Add home team impact columns
ALTER TABLE game_id_mapping 
ADD COLUMN IF NOT EXISTS home_total_impact DECIMAL(10,4),
ADD COLUMN IF NOT EXISTS home_active_players INTEGER,
ADD COLUMN IF NOT EXISTS home_tier_1_count INTEGER,
ADD COLUMN IF NOT EXISTS home_tier_2_count INTEGER,
ADD COLUMN IF NOT EXISTS home_tier_3_count INTEGER,
ADD COLUMN IF NOT EXISTS home_tier_4_count INTEGER,
ADD COLUMN IF NOT EXISTS home_tier_5_count INTEGER,
ADD COLUMN IF NOT EXISTS home_qb1_active BOOLEAN,
ADD COLUMN IF NOT EXISTS home_rb1_active BOOLEAN,
ADD COLUMN IF NOT EXISTS home_wr1_active BOOLEAN,
ADD COLUMN IF NOT EXISTS home_edge1_active BOOLEAN,
ADD COLUMN IF NOT EXISTS home_cb1_active BOOLEAN,
ADD COLUMN IF NOT EXISTS home_lt_active BOOLEAN,
ADD COLUMN IF NOT EXISTS home_s1_active BOOLEAN;

-- Add away team impact columns
ALTER TABLE game_id_mapping 
ADD COLUMN IF NOT EXISTS away_total_impact DECIMAL(10,4),
ADD COLUMN IF NOT EXISTS away_active_players INTEGER,
ADD COLUMN IF NOT EXISTS away_tier_1_count INTEGER,
ADD COLUMN IF NOT EXISTS away_tier_2_count INTEGER,
ADD COLUMN IF NOT EXISTS away_tier_3_count INTEGER,
ADD COLUMN IF NOT EXISTS away_tier_4_count INTEGER,
ADD COLUMN IF NOT EXISTS away_tier_5_count INTEGER,
ADD COLUMN IF NOT EXISTS away_qb1_active BOOLEAN,
ADD COLUMN IF NOT EXISTS away_rb1_active BOOLEAN,
ADD COLUMN IF NOT EXISTS away_wr1_active BOOLEAN,
ADD COLUMN IF NOT EXISTS away_edge1_active BOOLEAN,
ADD COLUMN IF NOT EXISTS away_cb1_active BOOLEAN,
ADD COLUMN IF NOT EXISTS away_lt_active BOOLEAN,
ADD COLUMN IF NOT EXISTS away_s1_active BOOLEAN;

-- Add impact differential and metadata
ALTER TABLE game_id_mapping
ADD COLUMN IF NOT EXISTS impact_differential DECIMAL(10,4),  -- home_total_impact - away_total_impact
ADD COLUMN IF NOT EXISTS impact_calculated_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS home_player_details JSONB,  -- Detailed player breakdown for home team
ADD COLUMN IF NOT EXISTS away_player_details JSONB;  -- Detailed player breakdown for away team

-- Create indexes for impact queries
CREATE INDEX IF NOT EXISTS idx_game_mapping_impact_diff 
ON game_id_mapping(impact_differential DESC);

CREATE INDEX IF NOT EXISTS idx_game_mapping_season_week_impact 
ON game_id_mapping(season, week) 
WHERE home_total_impact IS NOT NULL;

-- Comments
COMMENT ON COLUMN game_id_mapping.home_total_impact IS 'Sum of weighted PFF grades for home team active players';
COMMENT ON COLUMN game_id_mapping.away_total_impact IS 'Sum of weighted PFF grades for away team active players';
COMMENT ON COLUMN game_id_mapping.impact_differential IS 'home_total_impact - away_total_impact (positive = home advantage)';
COMMENT ON COLUMN game_id_mapping.home_qb1_active IS 'TRUE if home team starting QB was active';
COMMENT ON COLUMN game_id_mapping.home_player_details IS 'JSONB array of home team players with individual impact scores';
COMMENT ON COLUMN game_id_mapping.away_player_details IS 'JSONB array of away team players with individual impact scores';