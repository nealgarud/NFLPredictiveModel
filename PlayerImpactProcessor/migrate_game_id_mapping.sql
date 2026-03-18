-- =============================================================================
-- PlayerImpactProcessor migration
-- =============================================================================
-- Run this once against Supabase before deploying PlayerImpactProcessor.
-- Adds position-group impact columns and enriched player-details JSONB to
-- game_id_mapping, and adds multiplier_components + nflverse_enriched to
-- player_game_stats.
--
-- Safe to run multiple times (all use ADD COLUMN IF NOT EXISTS).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- game_id_mapping — position-group impacts + player_details JSONB
-- -----------------------------------------------------------------------------
ALTER TABLE game_id_mapping
    ADD COLUMN IF NOT EXISTS home_offense_impact     NUMERIC(8,4),
    ADD COLUMN IF NOT EXISTS home_defense_impact     NUMERIC(8,4),
    ADD COLUMN IF NOT EXISTS home_ol_impact          NUMERIC(8,4),
    ADD COLUMN IF NOT EXISTS away_offense_impact     NUMERIC(8,4),
    ADD COLUMN IF NOT EXISTS away_defense_impact     NUMERIC(8,4),
    ADD COLUMN IF NOT EXISTS away_ol_impact          NUMERIC(8,4),
    ADD COLUMN IF NOT EXISTS home_player_details     JSONB,
    ADD COLUMN IF NOT EXISTS away_player_details     JSONB,
    ADD COLUMN IF NOT EXISTS impact_processor_version VARCHAR(50);

-- Index the JSONB for future ML feature extraction queries
CREATE INDEX IF NOT EXISTS idx_gim_home_player_details
    ON game_id_mapping USING GIN (home_player_details);
CREATE INDEX IF NOT EXISTS idx_gim_away_player_details
    ON game_id_mapping USING GIN (away_player_details);

-- Index the position-group columns for training set queries
CREATE INDEX IF NOT EXISTS idx_gim_home_offense ON game_id_mapping (home_offense_impact);
CREATE INDEX IF NOT EXISTS idx_gim_away_offense ON game_id_mapping (away_offense_impact);

-- -----------------------------------------------------------------------------
-- player_game_stats — multiplier_components JSONB + nflverse_enriched flag
-- -----------------------------------------------------------------------------
ALTER TABLE player_game_stats
    ADD COLUMN IF NOT EXISTS multiplier_components JSONB,
    ADD COLUMN IF NOT EXISTS nflverse_enriched     BOOLEAN DEFAULT FALSE;

-- Index for querying nflverse-enriched rows specifically
CREATE INDEX IF NOT EXISTS idx_pgs_nflverse_enriched
    ON player_game_stats (nflverse_enriched)
    WHERE nflverse_enriched = TRUE;

-- GIN index on multiplier_components for component-level queries
CREATE INDEX IF NOT EXISTS idx_pgs_multiplier_components
    ON player_game_stats USING GIN (multiplier_components);
