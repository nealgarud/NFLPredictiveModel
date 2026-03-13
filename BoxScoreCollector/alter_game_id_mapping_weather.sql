-- alter_game_id_mapping_weather.sql
-- Adds weather context columns to game_id_mapping.
-- Safe to run multiple times (IF NOT EXISTS).

ALTER TABLE game_id_mapping
    ADD COLUMN IF NOT EXISTS weather_temp        INTEGER,      -- °F at kickoff (NULL = dome)
    ADD COLUMN IF NOT EXISTS weather_wind_speed  INTEGER,      -- mph (NULL = dome)
    ADD COLUMN IF NOT EXISTS weather_condition   VARCHAR(100), -- "Sunny", "Rain", "Snow", etc.
    ADD COLUMN IF NOT EXISTS is_dome             BOOLEAN;      -- TRUE if no weather data returned
