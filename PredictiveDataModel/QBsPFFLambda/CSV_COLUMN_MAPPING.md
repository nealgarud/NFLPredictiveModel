# CSV Column Mapping Reference

Table and CSV columns now match 1:1. CSV columns:

| CSV Column | DB Column |
|------------|-----------|
| player | player |
| player_id | player_id |
| position | position |
| team_name | team (normalized) |
| player_game_count | player_game_count |
| accuracy_percent | accuracy_percent |
| aimed_passes | aimed_passes |
| attempts | attempts |
| avg_depth_of_target | avg_depth_of_target |
| avg_time_to_throw | avg_time_to_throw |
| bats | bats |
| big_time_throws | big_time_throws |
| btt_rate | btt_rate |
| completion_percent | completion_percent |
| completions | completions |
| declined_penalties | declined_penalties |
| def_gen_pressures | def_gen_pressures |
| drop_rate | drop_rate |
| dropbacks | dropbacks |
| drops | drops |
| first_downs | first_downs |
| franchise_id | franchise_id |
| grades_hands_fumble | grades_hands_fumble |
| grades_offense | grades_offense |
| grades_pass | grades_pass |
| grades_run | grades_run |
| hit_as_threw | hit_as_threw |
| interceptions | interceptions |
| passing_snaps | passing_snaps |
| penalties | penalties |
| pressure_to_sack_rate | pressure_to_sack_rate |
| qb_rating | qb_rating |
| sack_percent | sack_percent |
| sacks | sacks |
| scrambles | scrambles |
| spikes | spikes |
| thrown_aways | thrown_aways |
| touchdowns | touchdowns |
| turnover_worthy_plays | turnover_worthy_plays |
| twp_rate | twp_rate |
| yards | yards |
| ypa | ypa |

**Note:** `season` comes from the Lambda event, not the CSV.

