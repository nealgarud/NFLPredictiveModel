-- =============================================================================
-- nflverse_qb_stats
-- Per-game advanced QB metrics from nflverse (passing_cpoe, EPA, aDOT, etc.)
-- =============================================================================
CREATE TABLE IF NOT EXISTS nflverse_qb_stats (
    id SERIAL PRIMARY KEY,

    -- Identifiers
    player_id       VARCHAR(50),
    player_name     VARCHAR(100),
    team            VARCHAR(5),
    season          INTEGER NOT NULL,
    week            INTEGER NOT NULL,

    -- Passing stats
    completions             INTEGER,
    attempts                INTEGER,
    passing_yards           INTEGER,
    passing_tds             INTEGER,
    passing_interceptions   INTEGER,
    sacks_suffered          INTEGER,
    sack_yards_lost         INTEGER,
    passing_air_yards       INTEGER,
    passing_yards_after_catch INTEGER,
    passing_first_downs     INTEGER,
    passing_epa             DECIMAL(8,3),
    passing_cpoe            DECIMAL(8,4),
    pacr                    DECIMAL(6,4),

    -- Rushing stats (QBs rush too)
    carries                 INTEGER,
    rushing_yards           INTEGER,
    rushing_tds             INTEGER,
    rushing_epa             DECIMAL(8,3),
    rushing_first_downs     INTEGER,

    -- Calculated fields
    cpoe                    DECIMAL(8,4),   -- alias for passing_cpoe
    ypa                     DECIMAL(5,2),   -- passing_yards / attempts
    adot                    DECIMAL(5,2),   -- passing_air_yards / attempts
    epa_per_dropback        DECIMAL(6,4),   -- passing_epa / (attempts + sacks_suffered)

    -- Metadata
    opponent        VARCHAR(5),
    game_id         VARCHAR(50),
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),

    UNIQUE(player_id, season, week)
);

CREATE INDEX IF NOT EXISTS idx_nflverse_qb_team_season   ON nflverse_qb_stats(team, season);
CREATE INDEX IF NOT EXISTS idx_nflverse_qb_player_season ON nflverse_qb_stats(player_id, season);
CREATE INDEX IF NOT EXISTS idx_nflverse_qb_week          ON nflverse_qb_stats(season, week);


-- =============================================================================
-- nflverse_rb_stats
-- Per-game advanced RB metrics from nflverse (rushing EPA, receiving value,
-- first down rate, ball security, WOPR, target share)
-- NOTE: yards_after_contact and broken_tackles are NOT in nflverse.
--       Those stay sourced from Sportradar via BoxScoreParser.
-- =============================================================================
CREATE TABLE IF NOT EXISTS nflverse_rb_stats (
    id SERIAL PRIMARY KEY,

    -- Identifiers
    player_id       VARCHAR(50),
    player_name     VARCHAR(100),
    team            VARCHAR(5),
    season          INTEGER NOT NULL,
    week            INTEGER NOT NULL,

    -- Rushing stats
    carries                 INTEGER,
    rushing_yards           INTEGER,
    rushing_tds             INTEGER,
    rushing_fumbles         INTEGER,
    rushing_fumbles_lost    INTEGER,
    rushing_first_downs     INTEGER,
    rushing_epa             DECIMAL(8,3),

    -- Receiving stats (pass-catching value)
    receptions                  INTEGER,
    targets                     INTEGER,
    receiving_yards             INTEGER,
    receiving_tds               INTEGER,
    receiving_air_yards         INTEGER,
    receiving_yards_after_catch INTEGER,
    receiving_first_downs       INTEGER,
    receiving_epa               DECIMAL(8,3),
    receiving_fumbles_lost      INTEGER,
    target_share                DECIMAL(5,4),
    wopr                        DECIMAL(5,4),

    -- Calculated fields (derived on ingest)
    ypc             DECIMAL(5,2),    -- rushing_yards / carries
    epa_per_carry   DECIMAL(6,4),    -- rushing_epa / carries
    fd_rate         DECIMAL(5,4),    -- rushing_first_downs / carries
    total_epa       DECIMAL(8,3),    -- rushing_epa + receiving_epa
    total_yards     INTEGER,         -- rushing_yards + receiving_yards
    total_tds       INTEGER,         -- rushing_tds + receiving_tds

    -- Metadata
    opponent        VARCHAR(5),
    game_id         VARCHAR(50),
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),

    UNIQUE(player_id, season, week)
);

CREATE INDEX IF NOT EXISTS idx_nflverse_rb_team_season   ON nflverse_rb_stats(team, season);
CREATE INDEX IF NOT EXISTS idx_nflverse_rb_player_season ON nflverse_rb_stats(player_id, season);
CREATE INDEX IF NOT EXISTS idx_nflverse_rb_game          ON nflverse_rb_stats(game_id);
CREATE INDEX IF NOT EXISTS idx_nflverse_rb_week          ON nflverse_rb_stats(season, week);
