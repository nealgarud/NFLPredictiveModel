-- alter_player_game_stats.sql
-- Adds computed columns if the table was created before they were added.
-- Safe to run on an already-complete table (IF NOT EXISTS).

ALTER TABLE player_game_stats
    ADD COLUMN IF NOT EXISTS actual_impact_score   DECIMAL(6,2),
    ADD COLUMN IF NOT EXISTS pff_grade             DECIMAL(5,1),
    ADD COLUMN IF NOT EXISTS performance_multiplier DECIMAL(5,3);
