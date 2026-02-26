-- =====================================================
-- RB PFF Ratings Table Schema
-- Running Back Pro Football Focus Statistics
-- =====================================================

-- Drop table if exists (use with caution in production)
-- DROP TABLE IF EXISTS rb_pff_ratings;

CREATE TABLE IF NOT EXISTS rb_pff_ratings (
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
    
    -- Rushing Statistics
    attempts INTEGER,
    yards INTEGER,
    run_plays INTEGER,
    ypa DECIMAL(6,2),                    -- Yards per attempt
    longest INTEGER,
    first_downs INTEGER,
    touchdowns INTEGER,
    
    -- Advanced Rushing Metrics
    avoided_tackles INTEGER,
    breakaway_attempts INTEGER,
    breakaway_percent DECIMAL(6,2),
    breakaway_yards INTEGER,
    designed_yards INTEGER,
    explosive INTEGER,
    gap_attempts INTEGER,
    scramble_yards INTEGER,
    scrambles INTEGER,
    zone_attempts INTEGER,
    
    -- Yards After Contact
    yards_after_contact INTEGER,
    yco_attempt DECIMAL(6,2),            -- YAC per attempt
    
    -- Receiving Statistics
    targets INTEGER,
    receptions INTEGER,
    rec_yards INTEGER,
    routes INTEGER,
    drops INTEGER,
    yprr DECIMAL(6,2),                   -- Yards per route run
    
    -- Combined Metrics
    total_touches INTEGER,
    
    -- Elusiveness Metrics
    elu_recv_mtf DECIMAL(6,2),           -- Elusive receiving missed tackles forced
    elu_rush_mtf DECIMAL(6,2),           -- Elusive rushing missed tackles forced
    elu_yco DECIMAL(6,2),                -- Elusive yards after contact
    elusive_rating DECIMAL(6,2),
    
    -- PFF Grades (0-100 scale)
    grades_offense DECIMAL(6,2),
    grades_run DECIMAL(6,2),
    grades_pass DECIMAL(6,2),
    grades_pass_block DECIMAL(6,2),
    grades_pass_route DECIMAL(6,2),
    grades_run_block DECIMAL(6,2),
    grades_hands_fumble DECIMAL(6,2),
    grades_offense_penalty DECIMAL(6,2),
    
    -- Negative Plays
    fumbles INTEGER,
    penalties INTEGER,
    declined_penalties INTEGER,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT rb_pff_ratings_unique UNIQUE (player, team_name, season)
);

-- =====================================================
-- Indexes for Performance
-- =====================================================

-- Index for common queries by player
CREATE INDEX IF NOT EXISTS idx_rb_pff_player ON rb_pff_ratings(player);

-- Index for queries by team and season
CREATE INDEX IF NOT EXISTS idx_rb_pff_team_season ON rb_pff_ratings(team_name, season);

-- Index for queries by season
CREATE INDEX IF NOT EXISTS idx_rb_pff_season ON rb_pff_ratings(season);

-- Index for sorting by grades
CREATE INDEX IF NOT EXISTS idx_rb_pff_grades_offense ON rb_pff_ratings(grades_offense DESC);

-- Index for player_id lookups
CREATE INDEX IF NOT EXISTS idx_rb_pff_player_id ON rb_pff_ratings(player_id);

-- =====================================================
-- Comments
-- =====================================================

COMMENT ON TABLE rb_pff_ratings IS 'Pro Football Focus ratings and statistics for Running Backs';
COMMENT ON COLUMN rb_pff_ratings.player IS 'Player full name';
COMMENT ON COLUMN rb_pff_ratings.team_name IS 'Normalized 3-letter team abbreviation';
COMMENT ON COLUMN rb_pff_ratings.season IS 'NFL season year';
COMMENT ON COLUMN rb_pff_ratings.grades_offense IS 'Overall PFF offensive grade (0-100)';
COMMENT ON COLUMN rb_pff_ratings.elusive_rating IS 'PFF elusive rating measuring ability to avoid tackles';
COMMENT ON COLUMN rb_pff_ratings.yards_after_contact IS 'Total yards gained after contact';
COMMENT ON COLUMN rb_pff_ratings.avoided_tackles IS 'Number of tackles avoided/broken';

-- =====================================================
-- Sample Queries
-- =====================================================

/*
-- Top RBs by overall offensive grade (2024 season)
SELECT player, team_name, grades_offense, attempts, yards, touchdowns
FROM rb_pff_ratings
WHERE season = 2024 AND attempts >= 50
ORDER BY grades_offense DESC
LIMIT 20;

-- RBs with best elusive rating
SELECT player, team_name, season, elusive_rating, avoided_tackles, yards_after_contact
FROM rb_pff_ratings
WHERE season = 2024 AND attempts >= 100
ORDER BY elusive_rating DESC
LIMIT 10;

-- Most productive receiving backs
SELECT player, team_name, receptions, rec_yards, yprr, grades_pass_route
FROM rb_pff_ratings
WHERE season = 2024 AND targets >= 20
ORDER BY rec_yards DESC
LIMIT 15;

-- Check for duplicate entries (should return 0 rows)
SELECT player, team_name, season, COUNT(*)
FROM rb_pff_ratings
GROUP BY player, team_name, season
HAVING COUNT(*) > 1;
*/
