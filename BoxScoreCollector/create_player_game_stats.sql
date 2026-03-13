-- create_player_game_stats.sql
-- Run once in Supabase SQL Editor before using BoxScoreCollector Lambda.

CREATE TABLE IF NOT EXISTS player_game_stats (
    id SERIAL PRIMARY KEY,
    game_id VARCHAR(30) NOT NULL,
    sportradar_game_id VARCHAR(100),
    player_id VARCHAR(100) NOT NULL,
    player_name VARCHAR(255),
    team VARCHAR(10) NOT NULL,
    position VARCHAR(10),
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,

    -- Rushing
    rush_attempts INTEGER DEFAULT 0,
    rush_yards INTEGER DEFAULT 0,
    rush_touchdowns INTEGER DEFAULT 0,
    rush_first_downs INTEGER DEFAULT 0,
    rush_yards_after_contact INTEGER DEFAULT 0,
    rush_broken_tackles INTEGER DEFAULT 0,
    rush_tlost INTEGER DEFAULT 0,
    scrambles INTEGER DEFAULT 0,

    -- Passing
    pass_attempts INTEGER DEFAULT 0,
    pass_completions INTEGER DEFAULT 0,
    pass_yards INTEGER DEFAULT 0,
    pass_touchdowns INTEGER DEFAULT 0,
    pass_interceptions INTEGER DEFAULT 0,
    pass_air_yards INTEGER DEFAULT 0,
    pass_on_target INTEGER DEFAULT 0,
    pass_poorly_thrown INTEGER DEFAULT 0,
    sacks_taken INTEGER DEFAULT 0,
    sack_yards INTEGER DEFAULT 0,
    avg_pocket_time DECIMAL(5,3),
    times_blitzed INTEGER DEFAULT 0,
    times_hurried INTEGER DEFAULT 0,

    -- Receiving
    targets INTEGER DEFAULT 0,
    receptions INTEGER DEFAULT 0,
    receiving_yards INTEGER DEFAULT 0,
    receiving_touchdowns INTEGER DEFAULT 0,
    yards_after_catch INTEGER DEFAULT 0,
    drops INTEGER DEFAULT 0,

    -- Defense
    tackles INTEGER DEFAULT 0,
    ast_tackles INTEGER DEFAULT 0,
    missed_tackles INTEGER DEFAULT 0,
    def_sacks DECIMAL(4,1) DEFAULT 0,
    def_sack_yards INTEGER DEFAULT 0,
    qb_hits INTEGER DEFAULT 0,
    hurries INTEGER DEFAULT 0,
    knockdowns INTEGER DEFAULT 0,
    passes_defended INTEGER DEFAULT 0,
    interceptions INTEGER DEFAULT 0,
    int_yards INTEGER DEFAULT 0,
    int_touchdowns INTEGER DEFAULT 0,
    def_targets INTEGER DEFAULT 0,
    def_completions_allowed INTEGER DEFAULT 0,
    tackles_for_loss INTEGER DEFAULT 0,

    -- Special Teams
    fg_attempts INTEGER DEFAULT 0,
    fg_made INTEGER DEFAULT 0,
    fg_longest INTEGER DEFAULT 0,
    xp_attempts INTEGER DEFAULT 0,
    xp_made INTEGER DEFAULT 0,
    kick_return_yards INTEGER DEFAULT 0,
    punt_return_yards INTEGER DEFAULT 0,

    -- Game Context
    team_points_scored INTEGER,
    team_points_allowed INTEGER,
    game_result VARCHAR(5),

    -- Computed impact score (filled by GameImpactCalculator)
    actual_impact_score DECIMAL(6,2),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(game_id, player_id)
);

-- Trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_player_game_stats_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = CURRENT_TIMESTAMP; RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_pgs_updated_at ON player_game_stats;
CREATE TRIGGER trg_pgs_updated_at
    BEFORE UPDATE ON player_game_stats
    FOR EACH ROW EXECUTE FUNCTION update_player_game_stats_updated_at();

-- Indexes
CREATE INDEX IF NOT EXISTS idx_pgs_game        ON player_game_stats(game_id);
CREATE INDEX IF NOT EXISTS idx_pgs_player      ON player_game_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_pgs_team_season ON player_game_stats(team, season);
CREATE INDEX IF NOT EXISTS idx_pgs_player_season ON player_game_stats(player_id, season);
