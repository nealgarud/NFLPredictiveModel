-- =====================================================
-- Offensive Line PFF Ratings Table Schema
-- Pro Football Focus Statistics for Offensive Linemen
-- =====================================================

-- Drop table if exists (use with caution in production)
-- DROP TABLE IF EXISTS oline_pff_ratings;

CREATE TABLE IF NOT EXISTS oline_pff_ratings (
    -- Primary Key
    id SERIAL PRIMARY KEY,
    
    -- Player Identification
    player VARCHAR(255) NOT NULL,
    player_id VARCHAR(100),
    position VARCHAR(10),                -- C, LG, RG, LT, RT, TE
    team_name VARCHAR(10),
    season INTEGER NOT NULL,
    franchise_id INTEGER,
    
    -- Game Participation
    player_game_count INTEGER,
    
    -- Snap Counts by Position
    snap_counts_offense INTEGER,
    snap_counts_block INTEGER,
    snap_counts_pass_play INTEGER,
    snap_counts_pass_block INTEGER,
    snap_counts_run_block INTEGER,
    snap_counts_ce INTEGER,              -- Center snaps
    snap_counts_lg INTEGER,              -- Left Guard snaps
    snap_counts_rg INTEGER,              -- Right Guard snaps
    snap_counts_lt INTEGER,              -- Left Tackle snaps
    snap_counts_rt INTEGER,              -- Right Tackle snaps
    snap_counts_te INTEGER,              -- Tight End snaps (inline blocking)
    
    -- Blocking Performance Metrics
    block_percent DECIMAL(6,2),
    pass_block_percent DECIMAL(6,2),
    non_spike_pass_block INTEGER,
    non_spike_pass_block_percentage DECIMAL(6,2),
    
    -- Pass Protection Stats
    pressures_allowed INTEGER,
    sacks_allowed INTEGER,
    hits_allowed INTEGER,
    hurries_allowed INTEGER,
    pbe INTEGER,                         -- Pass Blocking Efficiency
    
    -- PFF Grades (0-100 scale)
    grades_offense DECIMAL(6,2),
    grades_pass_block DECIMAL(6,2),
    grades_run_block DECIMAL(6,2),
    
    -- Penalties
    penalties INTEGER,
    declined_penalties INTEGER,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT oline_pff_ratings_unique UNIQUE (player, team_name, season)
);

-- =====================================================
-- Indexes for Performance
-- =====================================================

-- Index for common queries by player
CREATE INDEX IF NOT EXISTS idx_oline_pff_player ON oline_pff_ratings(player);

-- Index for queries by team and season
CREATE INDEX IF NOT EXISTS idx_oline_pff_team_season ON oline_pff_ratings(team_name, season);

-- Index for queries by season
CREATE INDEX IF NOT EXISTS idx_oline_pff_season ON oline_pff_ratings(season);

-- Index for sorting by grades
CREATE INDEX IF NOT EXISTS idx_oline_pff_grades_offense ON oline_pff_ratings(grades_offense DESC);
CREATE INDEX IF NOT EXISTS idx_oline_pff_grades_pass_block ON oline_pff_ratings(grades_pass_block DESC);
CREATE INDEX IF NOT EXISTS idx_oline_pff_grades_run_block ON oline_pff_ratings(grades_run_block DESC);

-- Index for player_id lookups
CREATE INDEX IF NOT EXISTS idx_oline_pff_player_id ON oline_pff_ratings(player_id);

-- Index for position-based queries
CREATE INDEX IF NOT EXISTS idx_oline_pff_position ON oline_pff_ratings(position);

-- =====================================================
-- Comments
-- =====================================================

COMMENT ON TABLE oline_pff_ratings IS 'Pro Football Focus ratings and statistics for Offensive Linemen';
COMMENT ON COLUMN oline_pff_ratings.player IS 'Player full name';
COMMENT ON COLUMN oline_pff_ratings.team_name IS 'Normalized 3-letter team abbreviation';
COMMENT ON COLUMN oline_pff_ratings.season IS 'NFL season year';
COMMENT ON COLUMN oline_pff_ratings.position IS 'OL position: C, LG, RG, LT, RT, or TE';
COMMENT ON COLUMN oline_pff_ratings.grades_offense IS 'Overall PFF offensive grade (0-100)';
COMMENT ON COLUMN oline_pff_ratings.grades_pass_block IS 'PFF pass blocking grade (0-100)';
COMMENT ON COLUMN oline_pff_ratings.grades_run_block IS 'PFF run blocking grade (0-100)';
COMMENT ON COLUMN oline_pff_ratings.pressures_allowed IS 'Total pressures allowed (sacks + hits + hurries)';
COMMENT ON COLUMN oline_pff_ratings.pbe IS 'Pass Blocking Efficiency rating';

-- =====================================================
-- Sample Queries
-- =====================================================

/*
-- Top OL by overall grade (2024 season)
SELECT player, team_name, position, grades_offense, grades_pass_block, grades_run_block
FROM oline_pff_ratings
WHERE season = 2024 AND snap_counts_offense >= 200
ORDER BY grades_offense DESC
LIMIT 20;

-- Best pass blockers
SELECT player, team_name, position, grades_pass_block, pressures_allowed, sacks_allowed
FROM oline_pff_ratings
WHERE season = 2024 AND snap_counts_pass_block >= 200
ORDER BY grades_pass_block DESC
LIMIT 15;

-- Best run blockers
SELECT player, team_name, position, grades_run_block, snap_counts_run_block
FROM oline_pff_ratings
WHERE season = 2024 AND snap_counts_run_block >= 150
ORDER BY grades_run_block DESC
LIMIT 15;

-- Top tackles (LT/RT combined)
SELECT player, team_name, position, grades_pass_block, sacks_allowed, pressures_allowed
FROM oline_pff_ratings
WHERE season = 2024 
  AND position IN ('LT', 'RT')
  AND snap_counts_offense >= 300
ORDER BY grades_pass_block DESC
LIMIT 10;

-- Compare positions by average grade
SELECT position,
       COUNT(*) as player_count,
       AVG(grades_offense) as avg_grade,
       AVG(grades_pass_block) as avg_pass_block,
       AVG(grades_run_block) as avg_run_block
FROM oline_pff_ratings
WHERE season = 2024 AND snap_counts_offense >= 200
GROUP BY position
ORDER BY avg_grade DESC;

-- Players with fewest pressures allowed (min 400 snaps)
SELECT player, team_name, position, pressures_allowed, snap_counts_pass_block,
       ROUND((pressures_allowed::DECIMAL / NULLIF(snap_counts_pass_block, 0)) * 100, 2) as pressure_rate
FROM oline_pff_ratings
WHERE season = 2024 AND snap_counts_pass_block >= 400
ORDER BY pressure_rate ASC
LIMIT 20;

-- Check for duplicate entries (should return 0 rows)
SELECT player, team_name, season, COUNT(*)
FROM oline_pff_ratings
GROUP BY player, team_name, season
HAVING COUNT(*) > 1;
*/
