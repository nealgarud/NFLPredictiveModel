-- =====================================================
-- WR PFF Ratings Table Schema
-- Wide Receiver Pro Football Focus Statistics
-- =====================================================

-- Drop table if exists (use with caution in production)
-- DROP TABLE IF EXISTS wr_pff_ratings;

CREATE TABLE IF NOT EXISTS wr_pff_ratings (
    -- Primary Key
    id SERIAL PRIMARY KEY,
    
    -- Player Identification
    player VARCHAR(255) NOT NULL,
    player_id VARCHAR(100),
    position VARCHAR(10),
    team_name VARCHAR(10),
    season INTEGER NOT NULL,
    franchise_id INTEGER,
    
    -- Game Participation
    player_game_count INTEGER,
    
    -- Target & Reception Statistics
    targets INTEGER,
    receptions INTEGER,
    yards INTEGER,
    touchdowns INTEGER,
    longest INTEGER,
    first_downs INTEGER,
    
    -- Reception Efficiency
    caught_percent DECIMAL(6,2),           -- Catch percentage
    yards_per_reception DECIMAL(6,2),
    yards_after_catch INTEGER,
    yards_after_catch_per_reception DECIMAL(6,2),
    avg_depth_of_target DECIMAL(6,2),
    
    -- Route Running
    routes INTEGER,
    route_rate DECIMAL(6,2),
    yprr DECIMAL(6,2),                     -- Yards per route run
    
    -- Contested Catches
    contested_targets INTEGER,
    contested_receptions INTEGER,
    contested_catch_rate DECIMAL(6,2),
    
    -- Drops
    drops INTEGER,
    drop_rate DECIMAL(6,2),
    
    -- Alignment Splits
    wide_snaps INTEGER,
    wide_rate DECIMAL(6,2),
    slot_snaps INTEGER,
    slot_rate DECIMAL(6,2),
    inline_snaps INTEGER,
    inline_rate DECIMAL(6,2),
    
    -- Pass Blocking
    pass_plays INTEGER,
    pass_blocks INTEGER,
    pass_block_rate DECIMAL(6,2),
    
    -- Advanced Metrics
    avoided_tackles INTEGER,
    targeted_qb_rating DECIMAL(6,2),
    interceptions INTEGER,                  -- INTs caused when targeted
    
    -- PFF Grades (0-100 scale)
    grades_offense DECIMAL(6,2),
    grades_pass_route DECIMAL(6,2),
    grades_pass_block DECIMAL(6,2),
    grades_hands_drop DECIMAL(6,2),
    grades_hands_fumble DECIMAL(6,2),
    
    -- Negative Plays
    fumbles INTEGER,
    penalties INTEGER,
    declined_penalties INTEGER,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT wr_pff_ratings_unique UNIQUE (player, team_name, season)
);

-- =====================================================
-- Indexes for Performance
-- =====================================================

-- Index for common queries by player
CREATE INDEX IF NOT EXISTS idx_wr_pff_player ON wr_pff_ratings(player);

-- Index for queries by team and season
CREATE INDEX IF NOT EXISTS idx_wr_pff_team_season ON wr_pff_ratings(team_name, season);

-- Index for queries by season
CREATE INDEX IF NOT EXISTS idx_wr_pff_season ON wr_pff_ratings(season);

-- Index for sorting by grades
CREATE INDEX IF NOT EXISTS idx_wr_pff_grades_offense ON wr_pff_ratings(grades_offense DESC);

-- Index for player_id lookups
CREATE INDEX IF NOT EXISTS idx_wr_pff_player_id ON wr_pff_ratings(player_id);

-- Index for sorting by yards
CREATE INDEX IF NOT EXISTS idx_wr_pff_yards ON wr_pff_ratings(yards DESC);

-- Index for sorting by receptions
CREATE INDEX IF NOT EXISTS idx_wr_pff_receptions ON wr_pff_ratings(receptions DESC);

-- =====================================================
-- Comments
-- =====================================================

COMMENT ON TABLE wr_pff_ratings IS 'Pro Football Focus ratings and statistics for Wide Receivers';
COMMENT ON COLUMN wr_pff_ratings.player IS 'Player full name';
COMMENT ON COLUMN wr_pff_ratings.team_name IS 'Normalized 3-letter team abbreviation';
COMMENT ON COLUMN wr_pff_ratings.season IS 'NFL season year';
COMMENT ON COLUMN wr_pff_ratings.grades_offense IS 'Overall PFF offensive grade (0-100)';
COMMENT ON COLUMN wr_pff_ratings.yprr IS 'Yards per route run - key efficiency metric';
COMMENT ON COLUMN wr_pff_ratings.contested_catch_rate IS 'Success rate on contested catches';
COMMENT ON COLUMN wr_pff_ratings.avg_depth_of_target IS 'Average depth of target (aDOT)';

-- =====================================================
-- Sample Queries
-- =====================================================

/*
-- Top WRs by overall offensive grade (2024 season)
SELECT player, team_name, grades_offense, receptions, yards, touchdowns, yprr
FROM wr_pff_ratings
WHERE season = 2024 AND targets >= 30
ORDER BY grades_offense DESC
LIMIT 20;

-- WRs with best yards per route run
SELECT player, team_name, season, yprr, routes, yards, receptions
FROM wr_pff_ratings
WHERE season = 2024 AND routes >= 200
ORDER BY yprr DESC
LIMIT 15;

-- Best contested catch receivers
SELECT player, team_name, contested_catch_rate, contested_receptions, contested_targets
FROM wr_pff_ratings
WHERE season = 2024 AND contested_targets >= 10
ORDER BY contested_catch_rate DESC
LIMIT 10;

-- Deep threat receivers (high aDOT)
SELECT player, team_name, avg_depth_of_target, yards, touchdowns, yards_per_reception
FROM wr_pff_ratings
WHERE season = 2024 AND targets >= 40
ORDER BY avg_depth_of_target DESC
LIMIT 15;

-- Most reliable (low drop rate)
SELECT player, team_name, drop_rate, drops, targets, receptions, caught_percent
FROM wr_pff_ratings
WHERE season = 2024 AND targets >= 50
ORDER BY drop_rate ASC
LIMIT 10;

-- Check for duplicate entries (should return 0 rows)
SELECT player, team_name, season, COUNT(*)
FROM wr_pff_ratings
GROUP BY player, team_name, season
HAVING COUNT(*) > 1;
*/
