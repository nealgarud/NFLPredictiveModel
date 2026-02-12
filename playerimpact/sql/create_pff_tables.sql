-- ============================================================================
-- PFF GRADE TABLES FOR PLAYER IMPACT CALCULATION
-- Replaces Madden ratings with Pro Football Focus grades
-- ============================================================================

-- ============================================================================
-- 1. WR/TE GRADES TABLE (Wide Receivers & Tight Ends)
-- ============================================================================
CREATE TABLE IF NOT EXISTS pff_wr_grades (
    id SERIAL PRIMARY KEY,
    player VARCHAR(255) NOT NULL,
    player_id VARCHAR(50),
    position VARCHAR(10),
    team_name VARCHAR(10),
    player_game_count INTEGER,
    franchise_id INTEGER,
    
    -- PFF Grade Columns (PRIMARY METRIC)
    grades_offense DECIMAL(5,2),           -- Overall offensive grade (60-99 range)
    grades_hands_drop DECIMAL(5,2),        -- Hands/Drop grade
    grades_hands_fumble DECIMAL(5,2),      -- Fumble prevention grade
    grades_pass_block DECIMAL(5,2),        -- Pass blocking grade (for TE)
    grades_pass_route DECIMAL(5,2),        -- Route running grade
    
    -- Reception Stats
    receptions INTEGER,
    targets INTEGER,
    yards INTEGER,
    touchdowns INTEGER,
    yards_per_reception DECIMAL(5,2),
    yards_after_catch INTEGER,
    yards_after_catch_per_reception DECIMAL(5,2),
    yprr DECIMAL(5,2),                     -- Yards per route run
    
    -- Advanced Metrics
    avg_depth_of_target DECIMAL(5,2),
    avoided_tackles INTEGER,
    caught_percent DECIMAL(5,2),
    contested_catch_rate DECIMAL(5,2),
    contested_receptions INTEGER,
    contested_targets INTEGER,
    drop_rate DECIMAL(5,2),
    drops INTEGER,
    first_downs INTEGER,
    fumbles INTEGER,
    interceptions INTEGER,
    longest INTEGER,
    targeted_qb_rating DECIMAL(5,2),
    
    -- Route/Snap Distribution
    inline_rate DECIMAL(5,2),
    inline_snaps INTEGER,
    slot_rate DECIMAL(5,2),
    slot_snaps INTEGER,
    wide_rate DECIMAL(5,2),
    wide_snaps INTEGER,
    route_rate DECIMAL(5,2),
    routes INTEGER,
    
    -- Blocking (for TE)
    pass_block_rate DECIMAL(5,2),
    pass_blocks INTEGER,
    pass_plays INTEGER,
    
    -- Other
    penalties INTEGER,
    declined_penalties INTEGER,
    
    -- Metadata
    season INTEGER DEFAULT 2024,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_pff_wr_player ON pff_wr_grades(player);
CREATE INDEX IF NOT EXISTS idx_pff_wr_team ON pff_wr_grades(team_name);
CREATE INDEX IF NOT EXISTS idx_pff_wr_player_team ON pff_wr_grades(player, team_name);


-- ============================================================================
-- 2. RB GRADES TABLE (Running Backs)
-- ============================================================================
CREATE TABLE IF NOT EXISTS pff_rb_grades (
    id SERIAL PRIMARY KEY,
    player VARCHAR(255) NOT NULL,
    player_id VARCHAR(50),
    position VARCHAR(10),
    team_name VARCHAR(10),
    player_game_count INTEGER,
    franchise_id INTEGER,
    
    -- PFF Grade Columns
    grades_offense DECIMAL(5,2),           -- Overall offensive grade
    grades_hands_drop DECIMAL(5,2),        -- Hands/Drop grade
    grades_hands_fumble DECIMAL(5,2),      -- Fumble prevention
    grades_pass_block DECIMAL(5,2),        -- Pass blocking grade
    grades_pass_route DECIMAL(5,2),        -- Receiving grade
    
    -- Receiving Stats (RBs catch passes too)
    receptions INTEGER,
    targets INTEGER,
    yards INTEGER,                         -- Receiving yards
    touchdowns INTEGER,
    yards_per_reception DECIMAL(5,2),
    yards_after_catch INTEGER,
    yards_after_catch_per_reception DECIMAL(5,2),
    yprr DECIMAL(5,2),
    
    -- Advanced Metrics
    avg_depth_of_target DECIMAL(5,2),
    avoided_tackles INTEGER,
    caught_percent DECIMAL(5,2),
    contested_catch_rate DECIMAL(5,2),
    contested_receptions INTEGER,
    contested_targets INTEGER,
    drop_rate DECIMAL(5,2),
    drops INTEGER,
    first_downs INTEGER,
    fumbles INTEGER,
    interceptions INTEGER,
    longest INTEGER,
    targeted_qb_rating DECIMAL(5,2),
    
    -- Route/Snap Distribution
    inline_rate DECIMAL(5,2),
    inline_snaps INTEGER,
    slot_rate DECIMAL(5,2),
    slot_snaps INTEGER,
    wide_rate DECIMAL(5,2),
    wide_snaps INTEGER,
    route_rate DECIMAL(5,2),
    routes INTEGER,
    
    -- Blocking
    pass_block_rate DECIMAL(5,2),
    pass_blocks INTEGER,
    pass_plays INTEGER,
    
    -- Other
    penalties INTEGER,
    declined_penalties INTEGER,
    
    -- Metadata
    season INTEGER DEFAULT 2024,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pff_rb_player ON pff_rb_grades(player);
CREATE INDEX IF NOT EXISTS idx_pff_rb_team ON pff_rb_grades(team_name);
CREATE INDEX IF NOT EXISTS idx_pff_rb_player_team ON pff_rb_grades(player, team_name);


-- ============================================================================
-- 3. QB GRADES TABLE (Quarterbacks)
-- ============================================================================
CREATE TABLE IF NOT EXISTS pff_qb_grades (
    id SERIAL PRIMARY KEY,
    player VARCHAR(255) NOT NULL,
    player_id VARCHAR(50),
    position VARCHAR(10),
    team_name VARCHAR(10),
    player_game_count INTEGER,
    
    -- PFF Grade Columns
    grades_offense DECIMAL(5,2),           -- Overall offensive grade
    grades_pass DECIMAL(5,2),              -- Passing grade
    grades_run DECIMAL(5,2),               -- Rushing grade (QB runs)
    
    -- Stats
    pass_attempts INTEGER,
    completions INTEGER,
    passing_yards INTEGER,
    passing_touchdowns INTEGER,
    interceptions INTEGER,
    
    -- Metadata
    season INTEGER DEFAULT 2024,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pff_qb_player ON pff_qb_grades(player);
CREATE INDEX IF NOT EXISTS idx_pff_qb_team ON pff_qb_grades(team_name);
CREATE INDEX IF NOT EXISTS idx_pff_qb_player_team ON pff_qb_grades(player, team_name);


-- ============================================================================
-- 4. OFFENSIVE LINE GRADES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS pff_ol_grades (
    id SERIAL PRIMARY KEY,
    player VARCHAR(255) NOT NULL,
    player_id VARCHAR(50),
    position VARCHAR(10),                  -- LT, LG, C, RG, RT
    team_name VARCHAR(10),
    player_game_count INTEGER,
    
    -- PFF Grade Columns
    grades_offense DECIMAL(5,2),           -- Overall OL grade
    grades_pass_block DECIMAL(5,2),        -- Pass blocking grade
    grades_run_block DECIMAL(5,2),         -- Run blocking grade
    
    -- Stats
    snaps INTEGER,
    sacks_allowed INTEGER,
    penalties INTEGER,
    
    -- Metadata
    season INTEGER DEFAULT 2024,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pff_ol_player ON pff_ol_grades(player);
CREATE INDEX IF NOT EXISTS idx_pff_ol_team ON pff_ol_grades(team_name);
CREATE INDEX IF NOT EXISTS idx_pff_ol_player_team ON pff_ol_grades(player, team_name);


-- ============================================================================
-- 5. DEFENSE GRADES TABLE (All defensive positions)
-- ============================================================================
CREATE TABLE IF NOT EXISTS pff_def_grades (
    id SERIAL PRIMARY KEY,
    player VARCHAR(255) NOT NULL,
    player_id VARCHAR(50),
    position VARCHAR(10),                  -- EDGE, DT, LB, CB, S, etc.
    team_name VARCHAR(10),
    player_game_count INTEGER,
    
    -- PFF Grade Columns
    grades_defense DECIMAL(5,2),           -- Overall defensive grade (PRIMARY)
    grades_pass_rush DECIMAL(5,2),         -- Pass rush grade
    grades_run_defense DECIMAL(5,2),       -- Run defense grade
    grades_coverage DECIMAL(5,2),          -- Coverage grade
    grades_tackling DECIMAL(5,2),          -- Tackling grade
    
    -- Stats
    tackles INTEGER,
    sacks DECIMAL(4,1),
    interceptions INTEGER,
    passes_defended INTEGER,
    
    -- Metadata
    season INTEGER DEFAULT 2024,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pff_def_player ON pff_def_grades(player);
CREATE INDEX IF NOT EXISTS idx_pff_def_team ON pff_def_grades(team_name);
CREATE INDEX IF NOT EXISTS idx_pff_def_player_team ON pff_def_grades(player, team_name);


-- ============================================================================
-- DROP OLD MADDEN TABLE (AFTER CONFIRMING DATA MIGRATION)
-- ============================================================================
-- Uncomment when ready to fully transition:
-- DROP TABLE IF EXISTS player_ratings CASCADE;


-- ============================================================================
-- GRANT PERMISSIONS (adjust based on your Supabase setup)
-- ============================================================================
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;

