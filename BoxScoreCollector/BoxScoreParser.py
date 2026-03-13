"""
BoxScoreParser

Parses Sportradar /games/{id}/statistics.json into structured dicts for
player_game_stats insertion and game script data.

Confirmed API structure (v7):
  resp['statistics']['home']          — team stats object
  resp['statistics']['home']['rushing']['players']  — player list
  resp['summary']['home']['points']   — final score
  resp['summary']['scoring']          — quarter-by-quarter (same response)

Quarter scores are extracted from the statistics.json response directly;
a separate summary.json call is not required.
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def parse_game_statistics(
    stats_response: Dict[str, Any],
    game_id: str,
    season: int,
    week: int,
) -> List[Dict[str, Any]]:
    """
    Parse /games/{id}/statistics.json.
    Returns one merged stat dict per player across all categories.
    """
    sportradar_game_id = stats_response.get('id', '')
    players: Dict[str, Dict] = {}

    # Scores live under summary, not statistics
    summary = stats_response.get('summary', {})
    home_pts = _int(summary.get('home', {}), 'points')
    away_pts = _int(summary.get('away', {}), 'points')

    stats_root = stats_response.get('statistics', {})

    for side in ('home', 'away'):
        team_stats = stats_root.get(side, {})
        team = team_stats.get('alias') or team_stats.get('market', '')
        team_pts = home_pts if side == 'home' else away_pts
        opp_pts  = away_pts if side == 'home' else home_pts
        result   = 'W' if team_pts > opp_pts else ('L' if team_pts < opp_pts else 'T')

        ctx = dict(
            game_id=game_id,
            sportradar_game_id=sportradar_game_id,
            team=team,
            season=season,
            week=week,
            team_points_scored=team_pts,
            team_points_allowed=opp_pts,
            game_result=result,
        )

        _parse_rushing(team_stats.get('rushing', {}), players, ctx)
        _parse_passing(team_stats.get('passing', {}), players, ctx)
        _parse_receiving(team_stats.get('receiving', {}), players, ctx)
        _parse_defense(team_stats.get('defense', {}), players, ctx)
        _parse_field_goals(team_stats.get('field_goals', {}), players, ctx)
        _parse_kick_returns(team_stats.get('kick_returns', {}), players, ctx)
        _parse_punt_returns(team_stats.get('punt_returns', {}), players, ctx)

    logger.info(f"Parsed {len(players)} players from {game_id}")
    return list(players.values())


def parse_quarter_scores(summary_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse /games/{id}/summary.json for quarter-by-quarter scoring.
    Handles both flat (scoring at root) and nested (game.scoring) structures.
    """
    result = {
        'home_q1': 0, 'home_q2': 0, 'home_q3': 0, 'home_q4': 0,
        'away_q1': 0, 'away_q2': 0, 'away_q3': 0, 'away_q4': 0,
        'home_led_at_half': None,
        'halftime_margin': None,
    }

    # summary.json can nest under 'game' key or be flat
    data    = summary_response.get('game', summary_response)
    scoring = data.get('scoring', [])

    for period in scoring:
        qnum = period.get('number') or period.get('period_number') or period.get('period', 0)
        try:
            qnum = int(qnum)
        except (TypeError, ValueError):
            continue
        if 1 <= qnum <= 4:
            result[f'home_q{qnum}'] = _int(period, 'home_points')
            result[f'away_q{qnum}'] = _int(period, 'away_points')

    home_half = result['home_q1'] + result['home_q2']
    away_half = result['away_q1'] + result['away_q2']
    result['home_led_at_half'] = home_half > away_half
    result['halftime_margin']  = home_half - away_half
    return result


def parse_weather(summary_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse weather conditions from /games/{id}/summary.json.
    Dome games return no weather object — is_dome is set True in that case.

    Sportradar weather structure:
      { "weather": { "condition": "Sunny", "temp": 72,
                     "humidity": 54, "wind": { "speed": 8 } } }
    """
    data    = summary_response.get('game', summary_response)
    weather = data.get('weather')

    if not weather:
        return {
            'weather_temp':       None,
            'weather_wind_speed': None,
            'weather_condition':  None,
            'is_dome':            True,
        }

    wind_speed = None
    wind = weather.get('wind')
    if isinstance(wind, dict):
        wind_speed = wind.get('speed')
        if wind_speed is not None:
            try:
                wind_speed = int(float(wind_speed))
            except (TypeError, ValueError):
                wind_speed = None
    elif wind is not None:
        try:
            wind_speed = int(float(wind))
        except (TypeError, ValueError):
            pass

    temp = weather.get('temp')
    if temp is not None:
        try:
            temp = int(float(temp))
        except (TypeError, ValueError):
            temp = None

    return {
        'weather_temp':       temp,
        'weather_wind_speed': wind_speed,
        'weather_condition':  weather.get('condition'),
        'is_dome':            False,
    }


# ── Private helpers ──────────────────────────────────────────────────────────

def _blank(pid: str, name: str, pos: str, ctx: Dict) -> Dict:
    return {
        'game_id': ctx['game_id'],
        'sportradar_game_id': ctx['sportradar_game_id'],
        'player_id': pid,
        'player_name': name,
        'team': ctx['team'],
        'position': pos,
        'season': ctx['season'],
        'week': ctx['week'],
        'team_points_scored': ctx['team_points_scored'],
        'team_points_allowed': ctx['team_points_allowed'],
        'game_result': ctx['game_result'],
        # Rushing
        'rush_attempts': 0, 'rush_yards': 0, 'rush_touchdowns': 0,
        'rush_first_downs': 0, 'rush_yards_after_contact': 0,
        'rush_broken_tackles': 0, 'rush_tlost': 0, 'scrambles': 0,
        # Passing
        'pass_attempts': 0, 'pass_completions': 0, 'pass_yards': 0,
        'pass_touchdowns': 0, 'pass_interceptions': 0, 'pass_air_yards': 0,
        'pass_on_target': 0, 'pass_poorly_thrown': 0,
        'sacks_taken': 0, 'sack_yards': 0, 'avg_pocket_time': None,
        'times_blitzed': 0, 'times_hurried': 0,
        # Receiving
        'targets': 0, 'receptions': 0, 'receiving_yards': 0,
        'receiving_touchdowns': 0, 'yards_after_catch': 0, 'drops': 0,
        # Defense
        'tackles': 0, 'ast_tackles': 0, 'missed_tackles': 0,
        'def_sacks': 0.0, 'def_sack_yards': 0, 'qb_hits': 0,
        'hurries': 0, 'knockdowns': 0, 'passes_defended': 0,
        'interceptions': 0, 'int_yards': 0, 'int_touchdowns': 0,
        'def_targets': 0, 'def_completions_allowed': 0, 'tackles_for_loss': 0,
        # Special Teams
        'fg_attempts': 0, 'fg_made': 0, 'fg_longest': 0,
        'xp_attempts': 0, 'xp_made': 0,
        'kick_return_yards': 0, 'punt_return_yards': 0,
    }


def _get(players: Dict, p: Dict, ctx: Dict) -> Dict:
    pid = p.get('id', '')
    if not pid:
        return {}
    if pid not in players:
        players[pid] = _blank(pid, p.get('name', ''), p.get('position', ''), ctx)
    return players[pid]


def _parse_rushing(rushing: Dict, players: Dict, ctx: Dict):
    for p in rushing.get('players', []):
        row = _get(players, p, ctx)
        if not row:
            continue
        row['rush_attempts']            += _int(p, 'attempts')
        row['rush_yards']               += _int(p, 'yards')
        row['rush_touchdowns']          += _int(p, 'touchdowns')
        row['rush_first_downs']         += _int(p, 'first_downs')
        row['rush_yards_after_contact'] += _int(p, 'yards_after_contact')
        row['rush_broken_tackles']      += _int(p, 'broken_tackles')
        row['rush_tlost']               += _int(p, 'tlost')
        row['scrambles']                += _int(p, 'scrambles')


def _parse_passing(passing: Dict, players: Dict, ctx: Dict):
    for p in passing.get('players', []):
        row = _get(players, p, ctx)
        if not row:
            continue
        row['pass_attempts']     += _int(p, 'attempts')
        row['pass_completions']  += _int(p, 'completions')
        row['pass_yards']        += _int(p, 'yards')
        row['pass_touchdowns']   += _int(p, 'touchdowns')
        row['pass_interceptions']+= _int(p, 'interceptions')
        row['pass_air_yards']    += _int(p, 'air_yards')
        row['pass_on_target']    += _int(p, 'on_target_throws')
        row['pass_poorly_thrown']+= _int(p, 'poor_throws')
        row['sacks_taken']       += _int(p, 'sacks')
        row['sack_yards']        += abs(_int(p, 'sack_yards'))
        row['times_blitzed']     += _int(p, 'blitzes')
        row['times_hurried']     += _int(p, 'hurries')
        if p.get('avg_pocket_time'):
            try:
                pt   = float(p['avg_pocket_time'])
                prev = row['avg_pocket_time']
                row['avg_pocket_time'] = pt if prev is None else (prev + pt) / 2
            except (TypeError, ValueError):
                pass


def _parse_receiving(receiving: Dict, players: Dict, ctx: Dict):
    for p in receiving.get('players', []):
        row = _get(players, p, ctx)
        if not row:
            continue
        row['targets']              += _int(p, 'targets')
        row['receptions']           += _int(p, 'receptions')
        row['receiving_yards']      += _int(p, 'yards')
        row['receiving_touchdowns'] += _int(p, 'touchdowns')
        row['yards_after_catch']    += _int(p, 'yards_after_catch')
        row['drops']                += _int(p, 'dropped_passes')


def _parse_defense(defense: Dict, players: Dict, ctx: Dict):
    for p in defense.get('players', []):
        row = _get(players, p, ctx)
        if not row:
            continue
        row['tackles']                 += _int(p, 'tackles')
        row['ast_tackles']             += _int(p, 'assists')        # 'assists' not 'ast_tackles'
        row['missed_tackles']          += _int(p, 'missed_tackles')
        row['def_sacks']               += _float(p, 'sacks')
        row['def_sack_yards']          += abs(_int(p, 'sack_yards'))
        row['qb_hits']                 += _int(p, 'qb_hits')
        row['hurries']                 += _int(p, 'hurries')
        row['knockdowns']              += _int(p, 'knockdowns')
        row['passes_defended']         += _int(p, 'passes_defended')
        row['interceptions']           += _int(p, 'interceptions')
        row['def_targets']             += _int(p, 'def_targets')
        row['def_completions_allowed'] += _int(p, 'def_comps')      # 'def_comps' not 'def_comp'
        row['tackles_for_loss']        += _int(p, 'tloss')          # INTEGER column; fractional API values rounded down


def _parse_field_goals(fg: Dict, players: Dict, ctx: Dict):
    for p in fg.get('players', []):
        row = _get(players, p, ctx)
        if not row:
            continue
        row['fg_attempts'] += _int(p, 'attempts')
        row['fg_made']     += _int(p, 'made')
        row['fg_longest']   = max(row['fg_longest'], _int(p, 'longest'))


def _parse_kick_returns(kr: Dict, players: Dict, ctx: Dict):
    for p in kr.get('players', []):
        row = _get(players, p, ctx)
        if row:
            row['kick_return_yards'] += _int(p, 'yards')


def _parse_punt_returns(pr: Dict, players: Dict, ctx: Dict):
    for p in pr.get('players', []):
        row = _get(players, p, ctx)
        if row:
            row['punt_return_yards'] += _int(p, 'yards')


def _int(d: Any, key: str) -> int:
    """Handles int, float, and string-encoded floats like '1.0' from JSON."""
    try:
        return int(float(d.get(key) or 0))
    except (TypeError, ValueError, AttributeError):
        return 0


def _float(d: Any, key: str) -> float:
    try:
        return float(d.get(key) or 0.0)
    except (TypeError, ValueError, AttributeError):
        return 0.0
