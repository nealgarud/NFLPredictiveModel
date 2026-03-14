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


-- =============================================================================
-- nflverse_wr_stats
-- Per-game advanced WR/TE metrics from nflverse (receiving EPA, WOPR,
-- target share, first downs, ball security).
-- NOTE: yards_after_catch and drops stay sourced from Sportradar.
-- =============================================================================
CREATE TABLE IF NOT EXISTS nflverse_wr_stats (
    id SERIAL PRIMARY KEY,

    -- Identifiers
    player_id       VARCHAR(50),
    player_name     VARCHAR(100),
    position        VARCHAR(5),
    team            VARCHAR(5),
    season          INTEGER NOT NULL,
    week            INTEGER NOT NULL,

    -- Receiving stats
    receptions                  INTEGER,
    targets                     INTEGER,
    receiving_yards             INTEGER,
    receiving_tds               INTEGER,
    receiving_air_yards         INTEGER,
    receiving_yards_after_catch INTEGER,
    receiving_first_downs       INTEGER,
    receiving_epa               DECIMAL(8,3),
    receiving_fumbles           INTEGER,
    receiving_fumbles_lost      INTEGER,
    receiving_2pt_conversions   INTEGER,

    -- Opportunity metrics
    target_share    DECIMAL(5,4),   -- share of team targets
    air_yards_share DECIMAL(5,4),   -- share of team air yards
    wopr            DECIMAL(5,4),   -- Weighted Opportunity Rating
    racr            DECIMAL(6,4),   -- Receiver Air Conversion Ratio

    -- Calculated fields (derived on ingest)
    catch_rate      DECIMAL(5,4),   -- receptions / targets
    ypr             DECIMAL(6,2),   -- receiving_yards / receptions
    epa_per_target  DECIMAL(6,4),   -- receiving_epa / targets
    fd_rate         DECIMAL(5,4),   -- receiving_first_downs / receptions

    -- Metadata
    opponent        VARCHAR(5),
    game_id         VARCHAR(50),
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),

    UNIQUE(player_id, season, week)
);

CREATE INDEX IF NOT EXISTS idx_nflverse_wr_team_season   ON nflverse_wr_stats(team, season);
CREATE INDEX IF NOT EXISTS idx_nflverse_wr_player_season ON nflverse_wr_stats(player_id, season);
CREATE INDEX IF NOT EXISTS idx_nflverse_wr_game          ON nflverse_wr_stats(game_id);
CREATE INDEX IF NOT EXISTS idx_nflverse_wr_week          ON nflverse_wr_stats(season, week);
CREATE INDEX IF NOT EXISTS idx_nflverse_wr_position      ON nflverse_wr_stats(position, season);
