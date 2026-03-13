-- alter_game_id_mapping.sql
-- Adds game script (quarter scoring) and actual impact / performance surprise columns.
-- Run once in Supabase SQL Editor AFTER create_player_game_stats.sql.

-- ── Game script: quarter-by-quarter scoring ──────────────────────────────────
ALTER TABLE game_id_mapping
    ADD COLUMN IF NOT EXISTS home_q1_points       INTEGER,
    ADD COLUMN IF NOT EXISTS away_q1_points       INTEGER,
    ADD COLUMN IF NOT EXISTS home_q2_points       INTEGER,
    ADD COLUMN IF NOT EXISTS away_q2_points       INTEGER,
    ADD COLUMN IF NOT EXISTS home_q3_points       INTEGER,
    ADD COLUMN IF NOT EXISTS away_q3_points       INTEGER,
    ADD COLUMN IF NOT EXISTS home_q4_points       INTEGER,
    ADD COLUMN IF NOT EXISTS away_q4_points       INTEGER,
    ADD COLUMN IF NOT EXISTS home_led_at_half     BOOLEAN,
    ADD COLUMN IF NOT EXISTS halftime_margin      INTEGER,   -- home - away at half
    ADD COLUMN IF NOT EXISTS largest_lead_home    INTEGER,
    ADD COLUMN IF NOT EXISTS largest_lead_away    INTEGER,
    ADD COLUMN IF NOT EXISTS lead_changes         INTEGER;

-- ── Actual game impact (post-game, from box scores) ──────────────────────────
ALTER TABLE game_id_mapping
    ADD COLUMN IF NOT EXISTS home_actual_game_impact   DECIMAL(10,4),
    ADD COLUMN IF NOT EXISTS away_actual_game_impact   DECIMAL(10,4),
    ADD COLUMN IF NOT EXISTS home_performance_surprise DECIMAL(10,4),  -- actual - expected
    ADD COLUMN IF NOT EXISTS away_performance_surprise DECIMAL(10,4),
    ADD COLUMN IF NOT EXISTS performance_surprise_diff DECIMAL(10,4),  -- home - away surprise
    ADD COLUMN IF NOT EXISTS box_score_collected_at    TIMESTAMP;
