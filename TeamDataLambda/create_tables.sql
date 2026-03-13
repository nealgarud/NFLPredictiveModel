-- ============================================================
-- PFF Team Grades Tables
-- Run this once in Supabase SQL Editor before first Lambda invocation
--
-- Source: PFF team export CSV
--   team, season, record, pf, pa, overall, offense, passing,
--   pass_block, receiving, run, run_block, defense, run_defense,
--   tackling, pass_rush, coverage, special_teams
-- ============================================================

-- -----------------------------------------------------------
-- 1. OFFENSIVE TABLE
--    Covers everything the offense does:
--      team record, points scored, and all offensive unit grades
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS pff_team_offense (
    team            VARCHAR(10)  NOT NULL,
    season          SMALLINT     NOT NULL,

    -- Team record (parsed from "W - L" string)
    wins            SMALLINT,
    losses          SMALLINT,
    ties            SMALLINT     DEFAULT 0,

    -- Scoring
    points_for      SMALLINT,

    -- PFF grades (0–100 scale)
    overall_grade   NUMERIC(5,1),
    offense_grade   NUMERIC(5,1),
    passing_grade   NUMERIC(5,1),
    pass_block_grade  NUMERIC(5,1),
    receiving_grade NUMERIC(5,1),
    run_grade       NUMERIC(5,1),
    run_block_grade NUMERIC(5,1),

    -- Metadata
    created_at      TIMESTAMPTZ  DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  DEFAULT NOW(),

    PRIMARY KEY (team, season)
);

-- -----------------------------------------------------------
-- 2. DEFENSIVE TABLE
--    Covers everything the defense does:
--      points allowed and all defensive unit grades
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS pff_team_defense (
    team            VARCHAR(10)  NOT NULL,
    season          SMALLINT     NOT NULL,

    -- Scoring
    points_against  SMALLINT,

    -- PFF grades (0–100 scale)
    defense_grade       NUMERIC(5,1),
    run_defense_grade   NUMERIC(5,1),
    tackling_grade      NUMERIC(5,1),
    pass_rush_grade     NUMERIC(5,1),
    coverage_grade      NUMERIC(5,1),

    -- Metadata
    created_at      TIMESTAMPTZ  DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  DEFAULT NOW(),

    PRIMARY KEY (team, season)
);

-- -----------------------------------------------------------
-- 3. SPECIAL TEAMS TABLE
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS pff_team_special_teams (
    team                    VARCHAR(10)  NOT NULL,
    season                  SMALLINT     NOT NULL,

    special_teams_grade     NUMERIC(5,1),

    -- Metadata
    created_at      TIMESTAMPTZ  DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  DEFAULT NOW(),

    PRIMARY KEY (team, season)
);

-- -----------------------------------------------------------
-- Indexes for common join patterns
-- (team_id in games/team_rankings = team here)
-- -----------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_pff_offense_season  ON pff_team_offense (season);
CREATE INDEX IF NOT EXISTS idx_pff_defense_season  ON pff_team_defense (season);
CREATE INDEX IF NOT EXISTS idx_pff_st_season       ON pff_team_special_teams (season);

-- -----------------------------------------------------------
-- Triggers: auto-update updated_at on upsert
-- -----------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_pff_offense_updated_at  ON pff_team_offense;
DROP TRIGGER IF EXISTS trg_pff_defense_updated_at  ON pff_team_defense;
DROP TRIGGER IF EXISTS trg_pff_st_updated_at       ON pff_team_special_teams;

CREATE TRIGGER trg_pff_offense_updated_at
    BEFORE UPDATE ON pff_team_offense
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_pff_defense_updated_at
    BEFORE UPDATE ON pff_team_defense
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_pff_st_updated_at
    BEFORE UPDATE ON pff_team_special_teams
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
