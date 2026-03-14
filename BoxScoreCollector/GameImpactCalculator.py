"""
GameImpactCalculator

Formula:
    actual_impact = pff_grade × position_weight × performance_multiplier

- pff_grade           : season-level PFF grade (0-100) fetched from DB
- position_weight     : positional importance weight (QB=3.0, EDGE=1.8, ...)
- performance_multiplier: how well the player performed in THIS game vs baseline
                          >1.0 = outperformed baseline, <1.0 = underperformed
                          capped to [0.40, 1.60]

Baseline priority per player:
  1. Player's own rolling season averages (from player_season_stats, games >= 3)
  2. Player's prior-season full-year averages (pre-season prior)
  3. 1.0 neutral multiplier (rookies / players with no history)

Team actual impact = weighted average of individual actual_impact scores.
Performance surprise = team_actual_impact - team_expected_impact.
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# League-average fallbacks used ONLY when no player baseline exists (rookies, etc.)
_QB = {'comp_pct': 0.65, 'ypa': 7.0, 'td_int_ratio': 1.5, 'sack_rate': 0.065}
_RB = {'ypc': 4.3, 'yac_per': 2.1, 'bt_rate': 0.08}
_RB_NV = {
    'epa_per_carry':    0.0,   # league-avg rushing EPA/carry ≈ 0
    'receiving_yards':  15.0,  # avg RB receiving yards/game
    'fd_rate':          0.20,  # ~20% of carries result in first downs
}
_WR = {'catch_rate': 0.65, 'ypr': 11.0, 'yac_rate': 0.45, 'drop_rate': 0.04}

POSITION_WEIGHTS = {
    'QB':   3.0,
    'RB':   1.5, 'HB': 1.5, 'FB': 0.5,
    'WR':   1.2, 'TE': 1.0,
    'LT':   1.0, 'RT': 0.8, 'LG': 0.6, 'RG': 0.6, 'C': 0.6,
    'DE':   1.8, 'DT': 1.0, 'NT': 0.8, 'EDGE': 1.8,
    'LB':   1.2, 'ILB': 1.2, 'OLB': 1.3, 'MLB': 1.2,
    'CB':   1.4, 'S':  1.2, 'FS':  1.2, 'SS':  1.2, 'DB': 1.0,
}

_DEFAULT_GRADE   = 65.0
_MULTIPLIER_CAP  = (0.40, 1.60)


# ── Position-specific multiplier calculators ─────────────────────────────────

def calc_qb_multiplier_enhanced(
    p: Dict,
    b: Optional[Dict] = None,
    nv_game: Optional[Dict] = None,
    nv_base: Optional[Dict] = None,
) -> Optional[float]:
    """
    Enhanced QB multiplier.

    - If nflverse data (nv_game, nv_base) is provided, uses CPOE, EPA, aDOT and
      rushing value on top of the existing box-score baselines.
    - If nflverse data is missing, falls back to the existing 4-component
      box-score-only formula (accuracy, YPA, TD/INT, sack avoidance +
      small scramble bonus).
    """
    atts = p['pass_attempts']
    if atts < 5:
        return None

    # ── Baselines from player_season_stats (current behavior) ────────────────
    comp_pct_base = (b.get('avg_comp_pct') or 0) if b else 0
    ypa_base      = (b.get('avg_ypa')      or 0) if b else 0
    if not comp_pct_base:
        comp_pct_base = _QB['comp_pct']
    if not ypa_base:
        ypa_base = _QB['ypa']

    if b:
        avg_tds  = float(b.get('avg_pass_touchdowns')    or 0)
        avg_ints = float(b.get('avg_pass_interceptions') or 0)
        td_int_base = (avg_tds + 1) / (avg_ints + 1)

        avg_atts  = float(b.get('avg_pass_attempts') or 0)
        avg_sacks = float(b.get('avg_sacks_taken')   or 0)
        sack_rate_base = (avg_sacks / (avg_atts + avg_sacks)) if avg_atts > 0 else _QB['sack_rate']

        base_rush_yards = float(b.get('avg_rush_yards') or 0)
    else:
        td_int_base     = _QB['td_int_ratio']
        sack_rate_base  = _QB['sack_rate']
        base_rush_yards = 0.0

    # ── Game box-score stats (always available) ──────────────────────────────
    comp_pct  = p['pass_completions'] / atts
    ypa       = p['pass_yards'] / atts
    td_int    = (p['pass_touchdowns'] + 1) / (p['pass_interceptions'] + 1)
    dropbacks = atts + p['sacks_taken']
    sack_rate = p['sacks_taken'] / dropbacks if dropbacks > 0 else 0.0
    rush_yards = float(p.get('rush_yards') or 0.0)

    # ── Fallback path: no nflverse data, keep current behavior ───────────────
    if nv_game is None or nv_base is None:
        m = (
            (comp_pct / max(comp_pct_base, 0.01)) * 0.30 +
            (ypa      / max(ypa_base,      0.10)) * 0.35 +
            (td_int   / max(td_int_base,   0.10)) * 0.25 +
            (1 - max(0, sack_rate - sack_rate_base) * 5) * 0.10
        )
        m += p.get('scrambles', 0) * 0.01
        return _cap(m)

    # =======================================================================
    # nflverse-enhanced path
    # =======================================================================

    # COMPONENT 1 — Accuracy over expected (CPOE)
    game_cpoe = float(nv_game.get('cpoe') or 0.0)
    base_cpoe = float(nv_base.get('cpoe') or 0.0)
    if base_cpoe == 0 and game_cpoe == 0:
        cpoe_component = comp_pct / max(comp_pct_base, 0.01)
    else:
        cpoe_component = 1.0 + (game_cpoe - base_cpoe) / 10.0  # 10 pts CPOE ≈ +1.0
    cpoe_component = max(0.5, min(1.5, cpoe_component))

    # COMPONENT 2 — Explosiveness (YPA + aDOT)
    air_yards_game = float(nv_game.get('passing_air_yards') or 0.0)
    air_yards_base = float(nv_base.get('passing_air_yards') or 0.0)
    atts_base_nv   = float(nv_base.get('attempts') or 0.0)

    game_adot = air_yards_game / atts if atts > 0 else 0.0
    base_adot = air_yards_base / atts_base_nv if atts_base_nv > 0 else 8.0

    ypa_ratio  = ypa       / max(ypa_base, 0.10)
    adot_ratio = game_adot / max(base_adot, 0.10)
    explosiveness = ypa_ratio * 0.6 + adot_ratio * 0.4

    # COMPONENT 3 — Scoring efficiency (TD/INT)
    td_int_component = td_int / max(td_int_base, 0.10)

    # COMPONENT 4 — EPA efficiency
    pass_epa_game = float(nv_game.get('passing_epa') or 0.0)
    pass_epa_base = float(nv_base.get('passing_epa') or 0.0)
    sacks_game_nv = float(nv_game.get('sacks') or p['sacks_taken'] or 0)
    sacks_base_nv = float(nv_base.get('sacks') or 0)

    plays_game = atts + sacks_game_nv
    plays_base = (nv_base.get('attempts') or 0) + sacks_base_nv

    if plays_game > 0 and plays_base > 0:
        game_epa_pp = pass_epa_game / plays_game
        base_epa_pp = pass_epa_base / plays_base
        epa_component = 1.0 + (game_epa_pp - base_epa_pp) / 0.3  # 0.3 EPA/play ≈ +1.0
        epa_component = max(0.5, min(1.5, epa_component))
    else:
        epa_component = 1.0

    # COMPONENT 5 — Sack avoidance
    sack_component = 1.0 - max(0.0, (sack_rate - sack_rate_base) * 5.0)
    sack_component = max(0.5, min(1.5, sack_component))

    # COMPONENT 6 — Rushing value
    base_rush_yards_for_ratio = max(base_rush_yards, 10.0)
    rush_yards_ratio = rush_yards / base_rush_yards_for_ratio
    rush_component = max(0.5, min(2.0, rush_yards_ratio))

    m = (
        cpoe_component   * 0.20 +
        explosiveness    * 0.20 +
        td_int_component * 0.15 +
        epa_component    * 0.20 +
        sack_component   * 0.10 +
        rush_component   * 0.15
    )

    return _cap(m)


def calc_rb_multiplier(p: Dict, b: Optional[Dict] = None) -> Optional[float]:
    atts = p['rush_attempts']
    if atts < 3:
        return None

    ypc_base    = (b.get('avg_rush_ypc') or 0) if b else 0
    yac_base    = (b.get('avg_rush_yac') or 0) if b else 0
    bt_base_raw = (b.get('avg_rush_broken_tackles') or 0) if b else 0

    if not ypc_base:
        ypc_base = _RB['ypc']
    if not yac_base:
        yac_base = _RB['yac_per']

    avg_atts = float(b.get('avg_rush_attempts') or 0) if b else 0
    bt_rate_base = (bt_base_raw / avg_atts) if avg_atts > 0 else _RB['bt_rate']

    ypc     = p['rush_yards'] / atts
    yac_per = (p['rush_yards_after_contact'] / atts) if p['rush_yards_after_contact'] > 0 else yac_base
    bt_rate = p['rush_broken_tackles'] / atts

    rush_m = (
        (ypc     / max(ypc_base,     0.1)) * 0.45 +
        (yac_per / max(yac_base,     0.1)) * 0.35 +
        (1 + (bt_rate - bt_rate_base) * 3) * 0.20
    )
    rush_m -= p['rush_tlost'] * 0.02
    recv_bonus = (p['receptions'] * 0.01) + (p['receiving_touchdowns'] * 0.05)
    return _cap(rush_m * 0.80 + recv_bonus)


def calc_rb_multiplier_enhanced(
    p: Dict,
    b: Optional[Dict] = None,
    nv_game: Optional[Dict] = None,
    nv_base: Optional[Dict] = None,
) -> Optional[float]:
    """
    Enhanced RB multiplier (7 components).

    Sportradar box-score fields (always available via BoxScoreParser):
      p['rush_attempts'], p['rush_yards'], p['rush_yards_after_contact'],
      p['rush_broken_tackles'], p['rush_tlost'], p['receptions'],
      p['receiving_yards'], p['receiving_touchdowns']

    nflverse game fields (nv_game):
      rushing_epa, rushing_first_downs, carries,
      receiving_yards, receiving_tds, receiving_epa,
      rushing_fumbles_lost, receiving_fumbles_lost

    nflverse baseline fields (nv_base — rolling prior-week sums):
      carries, rushing_yards, rushing_epa, rushing_first_downs,
      avg_receiving_yards, rushing_fumbles_lost, receiving_fumbles_lost

    When nv_game/nv_base are both None, degrades cleanly to the original
    3-component box-score formula + flat receiving bonus.
    """
    atts = p['rush_attempts']
    if atts < 3:
        return None

    # ── Sportradar baselines ──────────────────────────────────────────────────
    ypc_base    = (b.get('avg_rush_ypc') or 0) if b else 0
    yac_base    = (b.get('avg_rush_yac') or 0) if b else 0
    bt_base_raw = (b.get('avg_rush_broken_tackles') or 0) if b else 0

    if not ypc_base:
        ypc_base = _RB['ypc']
    if not yac_base:
        yac_base = _RB['yac_per']

    avg_atts     = float(b.get('avg_rush_attempts') or 0) if b else 0
    bt_rate_base = (bt_base_raw / avg_atts) if avg_atts > 0 else _RB['bt_rate']

    # ── Sportradar game stats ─────────────────────────────────────────────────
    ypc     = p['rush_yards'] / atts
    yac_per = (p['rush_yards_after_contact'] / atts) if p.get('rush_yards_after_contact', 0) > 0 else yac_base
    bt_rate = p.get('rush_broken_tackles', 0) / atts

    # ── Fallback: no nflverse data — original 3-component formula ────────────
    if nv_game is None or nv_base is None:
        rush_m = (
            (ypc     / max(ypc_base,     0.1)) * 0.45 +
            (yac_per / max(yac_base,     0.1)) * 0.35 +
            (1 + (bt_rate - bt_rate_base) * 3) * 0.20
        )
        rush_m -= p.get('rush_tlost', 0) * 0.02
        recv_bonus = (p.get('receptions', 0) * 0.01) + (p.get('receiving_touchdowns', 0) * 0.05)
        return _cap(rush_m * 0.80 + recv_bonus)

    # =========================================================================
    # nflverse-enhanced path (7 components)
    # =========================================================================

    # COMPONENT 1 — YPC / rushing efficiency (weight: 0.25)  [Sportradar]
    ypc_component = ypc / max(ypc_base, 0.1)

    # COMPONENT 2 — Yards after contact per carry (weight: 0.15)  [Sportradar]
    yac_component = yac_per / max(yac_base, 0.1)

    # COMPONENT 3 — Broken tackle rate (weight: 0.10)  [Sportradar]
    bt_component = 1.0 + (bt_rate - bt_rate_base) * 3.0

    # COMPONENT 4 — Rushing EPA per carry (weight: 0.20)  [nflverse]
    game_carries  = float(nv_game.get('carries') or atts)
    game_rush_epa = float(nv_game.get('rushing_epa') or 0.0)

    base_carries  = float(nv_base.get('carries') or 0.0)
    base_rush_epa = float(nv_base.get('rushing_epa') or 0.0)

    game_epa_pc = game_rush_epa / game_carries if game_carries > 0 else 0.0
    base_epa_pc = (base_rush_epa / base_carries) if base_carries > 0 else _RB_NV['epa_per_carry']

    epa_component = 1.0 + (game_epa_pc - base_epa_pc) / 0.2   # 0.2 EPA/carry ≈ +1.0
    epa_component = max(0.5, min(1.5, epa_component))

    # COMPONENT 5 — Receiving value (weight: 0.15)  [nflverse]
    game_recv_yds  = float(nv_game.get('receiving_yards') or p.get('receiving_yards') or 0.0)
    game_recv_tds  = int(nv_game.get('receiving_tds')     or p.get('receiving_touchdowns') or 0)
    base_recv_yds  = float(nv_base.get('avg_receiving_yards') or _RB_NV['receiving_yards'])

    recv_component = game_recv_yds / max(base_recv_yds, 10.0)
    recv_component = max(0.3, min(2.0, recv_component))
    recv_component += game_recv_tds * 0.05

    # COMPONENT 6 — First down rate (weight: 0.10)  [nflverse]
    game_fds       = float(nv_game.get('rushing_first_downs') or 0.0)
    base_fds_sum   = float(nv_base.get('rushing_first_downs') or 0.0)

    game_fd_rate   = game_fds / game_carries    if game_carries > 0 else 0.0
    base_fd_rate   = (base_fds_sum / base_carries) if base_carries > 0 else _RB_NV['fd_rate']

    fd_component = game_fd_rate / max(base_fd_rate, 0.05)
    fd_component = max(0.5, min(2.0, fd_component))

    # COMPONENT 7 — Ball security (weight: 0.05)  [nflverse]
    fumbles_lost   = (
        int(nv_game.get('rushing_fumbles_lost')   or 0) +
        int(nv_game.get('receiving_fumbles_lost') or 0)
    )
    fumble_component = max(0.4, 1.0 - fumbles_lost * 0.15)

    # ── Negative adjustment: tackles for loss (Sportradar) ───────────────────
    tlost_penalty = p.get('rush_tlost', 0) * 0.02

    m = (
        ypc_component    * 0.25 +
        yac_component    * 0.15 +
        bt_component     * 0.10 +
        epa_component    * 0.20 +
        recv_component   * 0.15 +
        fd_component     * 0.10 +
        fumble_component * 0.05
    ) - tlost_penalty

    return _cap(m)


def calc_wr_te_multiplier(p: Dict, b: Optional[Dict] = None) -> Optional[float]:
    targets = p['targets']
    if targets < 2:
        return None

    catch_rate_base = (b.get('avg_catch_rate') or 0) if b else 0
    ypr_base        = (b.get('avg_ypr')        or 0) if b else 0

    avg_yac_yards    = float(b.get('avg_yac')              or 0) if b else 0
    avg_recv_yards   = float(b.get('avg_receiving_yards')  or 0) if b else 0
    avg_drops        = float(b.get('avg_drops')            or 0) if b else 0
    avg_targets      = float(b.get('avg_targets')          or 0) if b else 0

    if not catch_rate_base:
        catch_rate_base = _WR['catch_rate']
    if not ypr_base:
        ypr_base = _WR['ypr']

    yac_rate_base = (avg_yac_yards / avg_recv_yards) if avg_recv_yards > 0 else _WR['yac_rate']
    drop_rate_base = (avg_drops / avg_targets) if avg_targets > 0 else _WR['drop_rate']

    catch_rate = p['receptions'] / targets
    ypr        = (p['receiving_yards'] / p['receptions']) if p['receptions'] > 0 else 0.0
    yac_rate   = (p['yards_after_catch'] / p['receiving_yards']) if p['receiving_yards'] > 0 else yac_rate_base
    drop_rate  = p['drops'] / targets

    m = (
        (catch_rate / max(catch_rate_base, 0.01))                    * 0.40 +
        (ypr        / max(ypr_base,        0.10))                    * 0.30 +
        (yac_rate   / max(yac_rate_base,   0.01))                    * 0.20 +
        (1 - drop_rate / max(drop_rate_base, 0.01))                  * 0.10
    )
    m += p['receiving_touchdowns'] * 0.05
    return _cap(m)


def calc_def_multiplier(p: Dict, b: Optional[Dict] = None) -> Optional[float]:
    total_activity = (
        p['tackles'] + p['ast_tackles'] +
        float(p['def_sacks']) + p['qb_hits'] + p['hurries'] +
        p['passes_defended'] + p['interceptions']
    )
    if total_activity < 1:
        return None

    # Pressure component — compare to player's own avg pressure production
    pressure = float(p['def_sacks']) * 3 + p['qb_hits'] * 1 + p['hurries'] * 0.5
    avg_pressure = 0.0
    if b:
        avg_pressure = (
            float(b.get('avg_def_sacks') or 0) * 3 +
            float(b.get('avg_qb_hits')   or 0) * 1 +
            float(b.get('avg_hurries')   or 0) * 0.5
        )
    pressure_baseline = max(avg_pressure, 1.0)
    pressure_m = pressure / pressure_baseline

    # Coverage component
    coverage_m = 1.0
    if p['def_targets'] > 0:
        allow_rate = p['def_completions_allowed'] / p['def_targets']
        if b and (b.get('avg_def_targets') or 0) > 0:
            avg_allow = float(b.get('avg_def_comp_allowed') or 0) / float(b['avg_def_targets'])
        else:
            avg_allow = 0.65  # league avg
        coverage_m = 1.0 + (avg_allow - allow_rate) * 0.8
    coverage_m += p['passes_defended'] * 0.04 + p['interceptions'] * 0.10

    # Tackling component — compare to player's own avg tackle count
    avg_tackles = float(b.get('avg_tackles') or 4.0) if b else 4.0
    tackle_score = p['tackles'] + p['ast_tackles'] * 0.5 - p['missed_tackles'] * 1.5
    tackle_m = 1.0 + (tackle_score - avg_tackles) * 0.04
    tackle_m += p['tackles_for_loss'] * 0.05

    m = pressure_m * 0.35 + coverage_m * 0.35 + tackle_m * 0.30
    return _cap(m)


def calc_performance_multiplier(
    p: Dict,
    b: Optional[Dict] = None,
    nv_game: Optional[Dict] = None,
    nv_base: Optional[Dict] = None,
) -> Optional[float]:
    """
    Route to the correct position multiplier.

    nv_game / nv_base are nflverse per-game and rolling-baseline dicts.
    Pass None for both to use the original box-score-only formulas.
    """
    pos = (p.get('position') or '').upper()
    if pos == 'QB':
        return calc_qb_multiplier_enhanced(p, b, nv_game, nv_base)
    if pos in ('RB', 'HB', 'FB'):
        return calc_rb_multiplier_enhanced(p, b, nv_game, nv_base)
    if pos in ('WR', 'TE'):
        return calc_wr_te_multiplier(p, b)
    if pos in ('DE', 'DT', 'NT', 'EDGE', 'LB', 'ILB', 'OLB', 'MLB',
               'CB', 'S', 'FS', 'SS', 'DB'):
        return calc_def_multiplier(p, b)
    return None


# ── Team-level aggregation ────────────────────────────────────────────────────

def calc_team_impacts(
    players: List[Dict],
    team: str,
    player_baselines: Optional[Dict[str, Dict]] = None,
) -> tuple:
    """
    Returns (actual_impact, expected_impact) for the team.

    player_baselines: {player_id: baseline_dict} from player_season_stats.
                      Pass None to use league-average fallbacks for all players.

    expected = Σ(pff_grade × weight × 1.0)  / Σ(weight)   ← multiplier=1.0
    actual   = Σ(pff_grade × weight × mult)  / Σ(weight)
    surprise = actual - expected
    """
    team_players   = [p for p in players if (p.get('team') or '').upper() == team.upper()]
    total_actual   = 0.0
    total_expected = 0.0
    total_weight   = 0.0

    baselines = player_baselines or {}

    for p in team_players:
        pos    = (p.get('position') or '').upper()
        weight = POSITION_WEIGHTS.get(pos, 0.5)

        pff_grade  = float(p.get('pff_grade') or _DEFAULT_GRADE)
        b          = baselines.get(p.get('player_id', ''))
        multiplier = calc_performance_multiplier(p, b)
        if multiplier is None:
            multiplier = 1.0

        expected_score = pff_grade * weight
        actual_score   = pff_grade * weight * multiplier

        total_expected += expected_score
        total_actual   += actual_score
        total_weight   += weight

        p['performance_multiplier'] = round(multiplier, 3)
        p['actual_impact_score']    = round(actual_score, 2)

    if total_weight == 0:
        logger.warning(f"No scorable players for {team}")
        return 0.0, 0.0

    actual   = round(total_actual   / total_weight, 4)
    expected = round(total_expected / total_weight, 4)

    logger.info(
        f"{team} actual={actual:.2f}  expected={expected:.2f}  "
        f"surprise={actual - expected:+.2f}  "
        f"({len(team_players)} players, weight={total_weight:.1f}, "
        f"baselines={sum(1 for p in team_players if p.get('player_id', '') in baselines)} player-specific)"
    )
    return actual, expected


def calc_performance_surprise(actual: float, expected: float) -> float:
    return round(actual - expected, 4)


def _cap(v: float) -> float:
    return max(_MULTIPLIER_CAP[0], min(_MULTIPLIER_CAP[1], v))
