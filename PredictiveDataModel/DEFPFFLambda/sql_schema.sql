-- =====================================================
-- Defense PFF Ratings Table Schema
-- Pro Football Focus Statistics for Defensive Players
-- =====================================================

-- Drop table if exists (use with caution in production)
-- DROP TABLE IF EXISTS defense_pff_ratings;

CREATE TABLE IF NOT EXISTS defense_pff_ratings (
    -- Primary Key
    id SERIAL PRIMARY KEY,
    
    -- Player Identification
    player VARCHAR(255) NOT NULL,
    player_id VARCHAR(100),
    position VARCHAR(10),                -- DT, DE, LB, CB, S, etc.
    team_name VARCHAR(10),
    season INTEGER NOT NULL,
    franchise_id INTEGER,
    
    -- Game Participation
    player_game_count INTEGER,
    
    -- Snap Counts by Alignment
    snap_counts_defense INTEGER,
    snap_counts_box INTEGER,
    snap_counts_corner INTEGER,
    snap_counts_coverage INTEGER,
    snap_counts_dl INTEGER,              -- Defensive Line total
    snap_counts_dl_a_gap INTEGER,        -- DL A-gap alignment
    snap_counts_dl_b_gap INTEGER,        -- DL B-gap alignment
    snap_counts_dl_outside_t INTEGER,    -- DL outside tackle
    snap_counts_dl_over_t INTEGER,       -- DL over tackle
    snap_counts_fs INTEGER,              -- Free Safety
    snap_counts_offball INTEGER,         -- Off-ball linebacker
    snap_counts_pass_rush INTEGER,
    snap_counts_run_defense INTEGER,
    snap_counts_slot INTEGER,
    
    -- Tackling Stats
    tackles INTEGER,
    assists INTEGER,
    tackles_for_loss DECIMAL(6,2),
    missed_tackles INTEGER,
    missed_tackle_rate DECIMAL(6,2),
    stops INTEGER,                       -- Run stops
    
    -- Pass Rush Stats
    sacks DECIMAL(6,2),
    hits INTEGER,                        -- QB hits
    hurries INTEGER,
    total_pressures INTEGER,
    batted_passes INTEGER,
    
    -- Coverage Stats
    targets INTEGER,
    receptions INTEGER,
    yards INTEGER,
    yards_after_catch INTEGER,
    yards_per_reception DECIMAL(6,2),
    catch_rate DECIMAL(6,2),
    qb_rating_against DECIMAL(6,2),
    pass_break_ups INTEGER,
    interceptions INTEGER,
    interception_touchdowns INTEGER,
    longest INTEGER,
    
    -- Turnovers Created
    forced_fumbles INTEGER,
    fumble_recoveries INTEGER,
    fumble_recovery_touchdowns INTEGER,
    
    -- PFF Grades (0-100 scale)
    grades_defense DECIMAL(6,2),
    grades_run_defense DECIMAL(6,2),
    grades_tackle DECIMAL(6,2),
    grades_pass_rush_defense DECIMAL(6,2),
    grades_coverage_defense DECIMAL(6,2),
    grades_defense_penalty DECIMAL(6,2),
    
    -- Scoring & Special
    touchdowns INTEGER,
    safeties INTEGER,
    
    -- Penalties
    penalties INTEGER,
    declined_penalties INTEGER,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT defense_pff_ratings_unique UNIQUE (player, team_name, season)
);

-- =====================================================
-- Indexes for Performance
-- =====================================================

-- Index for common queries by player
CREATE INDEX IF NOT EXISTS idx_def_pff_player ON defense_pff_ratings(player);

-- Index for queries by team and season
CREATE INDEX IF NOT EXISTS idx_def_pff_team_season ON defense_pff_ratings(team_name, season);

-- Index for queries by season
CREATE INDEX IF NOT EXISTS idx_def_pff_season ON defense_pff_ratings(season);

-- Index for sorting by grades
CREATE INDEX IF NOT EXISTS idx_def_pff_grades_defense ON defense_pff_ratings(grades_defense DESC);
CREATE INDEX IF NOT EXISTS idx_def_pff_grades_pass_rush ON defense_pff_ratings(grades_pass_rush_defense DESC);
CREATE INDEX IF NOT EXISTS idx_def_pff_grades_coverage ON defense_pff_ratings(grades_coverage_defense DESC);

-- Index for player_id lookups
CREATE INDEX IF NOT EXISTS idx_def_pff_player_id ON defense_pff_ratings(player_id);

-- Index for position-based queries
CREATE INDEX IF NOT EXISTS idx_def_pff_position ON defense_pff_ratings(position);

-- Index for stat leaders
CREATE INDEX IF NOT EXISTS idx_def_pff_sacks ON defense_pff_ratings(sacks DESC);
CREATE INDEX IF NOT EXISTS idx_def_pff_tackles ON defense_pff_ratings(tackles DESC);
CREATE INDEX IF NOT EXISTS idx_def_pff_interceptions ON defense_pff_ratings(interceptions DESC);

-- =====================================================
-- Comments
-- =====================================================

COMMENT ON TABLE defense_pff_ratings IS 'Pro Football Focus ratings and statistics for Defensive Players';
COMMENT ON COLUMN defense_pff_ratings.player IS 'Player full name';
COMMENT ON COLUMN defense_pff_ratings.team_name IS 'Normalized 3-letter team abbreviation';
COMMENT ON COLUMN defense_pff_ratings.season IS 'NFL season year';
COMMENT ON COLUMN defense_pff_ratings.position IS 'Defensive position: DT, DE, LB, CB, S, etc.';
COMMENT ON COLUMN defense_pff_ratings.grades_defense IS 'Overall PFF defensive grade (0-100)';
COMMENT ON COLUMN defense_pff_ratings.total_pressures IS 'Total QB pressures (sacks + hits + hurries)';
COMMENT ON COLUMN defense_pff_ratings.stops IS 'Run stops - tackles that constitute a failure for the offense';

-- =====================================================
-- Sample Queries
-- =====================================================

/*
-- Top defenders by overall grade (2024 season)
SELECT player, team_name, position, grades_defense, tackles, sacks, interceptions
FROM defense_pff_ratings
WHERE season = 2024 AND snap_counts_defense >= 200
ORDER BY grades_defense DESC
LIMIT 20;

-- Best pass rushers
SELECT player, team_name, position, grades_pass_rush_defense, sacks, hits, hurries, total_pressures
FROM defense_pff_ratings
WHERE season = 2024 AND snap_counts_pass_rush >= 150
ORDER BY grades_pass_rush_defense DESC
LIMIT 15;

-- Best coverage defenders
SELECT player, team_name, position, grades_coverage_defense, targets, receptions, 
       interceptions, pass_break_ups, qb_rating_against
FROM defense_pff_ratings
WHERE season = 2024 AND snap_counts_coverage >= 200
ORDER BY grades_coverage_defense DESC
LIMIT 15;

-- Top tacklers
SELECT player, team_name, position, tackles, assists, missed_tackles, missed_tackle_rate,
       tackles_for_loss, stops
FROM defense_pff_ratings
WHERE season = 2024 AND snap_counts_defense >= 300
ORDER BY tackles DESC
LIMIT 20;

-- Most impactful playmakers (turnovers)
SELECT player, team_name, position, interceptions, forced_fumbles, fumble_recoveries,
       sacks, pass_break_ups
FROM defense_pff_ratings
WHERE season = 2024 AND snap_counts_defense >= 250
ORDER BY (interceptions + forced_fumbles + fumble_recoveries) DESC
LIMIT 15;

-- Position group averages
SELECT position,
       COUNT(*) as player_count,
       AVG(grades_defense) as avg_grade,
       AVG(tackles) as avg_tackles,
       AVG(sacks) as avg_sacks
FROM defense_pff_ratings
WHERE season = 2024 AND snap_counts_defense >= 200
GROUP BY position
ORDER BY avg_grade DESC;

-- Check for duplicate entries (should return 0 rows)
SELECT player, team_name, season, COUNT(*)
FROM defense_pff_ratings
GROUP BY player, team_name, season
HAVING COUNT(*) > 1;
*/
