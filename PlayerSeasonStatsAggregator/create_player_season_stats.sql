-- create_player_season_stats.sql
-- Run once in Supabase SQL Editor before deploying PlayerSeasonStatsAggregator.
-- Stores rolling season averages per player — used by BoxScoreCollector
-- as player-specific baselines for performance_surprise calculation.

CREATE TABLE IF NOT EXISTS player_season_stats (
    player_id               VARCHAR(100) NOT NULL,
    player_name             VARCHAR(150),
    team                    VARCHAR(10),
    position                VARCHAR(20),
    season                  INT NOT NULL,
    through_week            INT NOT NULL,
    games_played            INT NOT NULL DEFAULT 0,

    -- Passing
    avg_pass_attempts       NUMERIC(6,2) DEFAULT 0,
    avg_pass_completions    NUMERIC(6,2) DEFAULT 0,
    avg_pass_yards          NUMERIC(7,2) DEFAULT 0,
    avg_pass_touchdowns     NUMERIC(5,2) DEFAULT 0,
    avg_pass_interceptions  NUMERIC(5,2) DEFAULT 0,
    avg_comp_pct            NUMERIC(5,4) DEFAULT 0,  -- SUM(comp)/SUM(att) — season-level ratio
    avg_ypa                 NUMERIC(5,2) DEFAULT 0,  -- SUM(yards)/SUM(att)
    avg_sacks_taken         NUMERIC(5,2) DEFAULT 0,

    -- Rushing
    avg_rush_attempts       NUMERIC(6,2) DEFAULT 0,
    avg_rush_yards          NUMERIC(7,2) DEFAULT 0,
    avg_rush_ypc            NUMERIC(5,2) DEFAULT 0,  -- SUM(yards)/SUM(att)
    avg_rush_yac            NUMERIC(6,2) DEFAULT 0,
    avg_rush_broken_tackles NUMERIC(5,2) DEFAULT 0,
    avg_rush_tlost          NUMERIC(5,2) DEFAULT 0,
    avg_scrambles           NUMERIC(5,2) DEFAULT 0,

    -- Receiving
    avg_targets             NUMERIC(6,2) DEFAULT 0,
    avg_receptions          NUMERIC(6,2) DEFAULT 0,
    avg_receiving_yards     NUMERIC(7,2) DEFAULT 0,
    avg_receiving_tds       NUMERIC(5,2) DEFAULT 0,
    avg_catch_rate          NUMERIC(5,4) DEFAULT 0,  -- SUM(rec)/SUM(targets)
    avg_ypr                 NUMERIC(5,2) DEFAULT 0,  -- SUM(yards)/SUM(rec)
    avg_yac                 NUMERIC(6,2) DEFAULT 0,
    avg_drops               NUMERIC(5,2) DEFAULT 0,

    -- Defense
    avg_tackles             NUMERIC(6,2) DEFAULT 0,
    avg_ast_tackles         NUMERIC(5,2) DEFAULT 0,
    avg_missed_tackles      NUMERIC(5,2) DEFAULT 0,
    avg_def_sacks           NUMERIC(5,2) DEFAULT 0,
    avg_qb_hits             NUMERIC(5,2) DEFAULT 0,
    avg_hurries             NUMERIC(5,2) DEFAULT 0,
    avg_passes_defended     NUMERIC(5,2) DEFAULT 0,
    avg_interceptions       NUMERIC(5,2) DEFAULT 0,
    avg_def_targets         NUMERIC(5,2) DEFAULT 0,
    avg_def_comp_allowed    NUMERIC(5,2) DEFAULT 0,
    avg_tackles_for_loss    NUMERIC(5,2) DEFAULT 0,

    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (player_id, season)
);

CREATE INDEX IF NOT EXISTS idx_player_season_stats_lookup
    ON player_season_stats(player_id, season);
