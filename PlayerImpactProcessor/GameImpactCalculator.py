"""
GameImpactCalculator — PlayerImpactProcessor
============================================

Formula:
    actual_impact = pff_grade × position_weight × performance_multiplier

- pff_grade           : season-level PFF grade (0-100) fetched from DB
- position_weight     : positional importance weight (QB=3.0, EDGE=1.8, ...)
- performance_multiplier: how well the player performed in THIS game vs baseline
                          >1.0 = outperformed baseline, <1.0 = underperformed
                          capped to [0.40, 1.60]

Enhancements over BoxScoreCollector:
  - calc_team_impacts accepts nflverse_data for enhanced multipliers on all positions
  - Two-pass OL processing: QB/RB processed first to build team OL context
  - Position group breakdowns: offense_impact, defense_impact, ol_impact
  - Per-player multiplier_components dict stored for JSONB enrichment
  - Returns 4-tuple: (actual, expected, position_groups, player_details)
"""
import logging
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# League-average fallbacks
_QB = {'comp_pct': 0.65, 'ypa': 7.0, 'td_int_ratio': 1.5, 'sack_rate': 0.065}
_RB = {'ypc': 4.3, 'yac_per': 2.1, 'bt_rate': 0.08}
_RB_NV = {
    'epa_per_carry':    0.0,
    'receiving_yards':  15.0,
    'fd_rate':          0.20,
}
_WR = {'catch_rate': 0.65, 'ypr': 11.0, 'yac_rate': 0.45, 'drop_rate': 0.04}
_WR_NV = {
    'epa_per_target': 0.0,
    'wopr':           0.30,
    'target_share':   0.20,
    'fd_rate':        0.50,
}
_OL_NV = {
    'sack_rate':        0.065,
    'team_ypc':         4.3,
    'team_rush_epa_pc': 0.0,
    'ol_penalties':     1.5,
    'pressure_rate':    0.30,
}

POSITION_WEIGHTS = {
    'QB':   3.0,
    'RB':   1.5, 'HB': 1.5, 'FB': 0.5,
    'WR':   1.2, 'TE': 1.0,
    'LT':   1.0, 'RT': 0.8, 'LG': 0.6, 'RG': 0.6, 'C': 0.6,
    'DE':   1.8, 'DT': 1.0, 'NT': 0.8, 'EDGE': 1.8,
    'LB':   1.2, 'ILB': 1.2, 'OLB': 1.3, 'MLB': 1.2,
    'CB':   1.4, 'S':  1.2, 'FS':  1.2, 'SS':  1.2, 'DB': 1.0,
    'DL':   1.0, 'SAF': 1.2,
}

_DEFAULT_GRADE  = 65.0
_MULTIPLIER_CAP = (0.40, 1.60)

# Position group membership sets
_QB_POS     = {'QB'}
_RB_POS     = {'RB', 'HB', 'FB'}
_SKILL_POS  = {'WR', 'TE'}
_OL_POS     = {'LT', 'RT', 'LG', 'RG', 'C', 'OL', 'G', 'T'}
_FRONT7_POS = {'DE', 'DT', 'NT', 'EDGE', 'LB', 'ILB', 'OLB', 'MLB', 'DL'}
_SEC_POS    = {'CB', 'S', 'FS', 'SS', 'DB', 'SAF'}
_DEF_POS    = _FRONT7_POS | _SEC_POS


# ── Position-specific multiplier calculators ─────────────────────────────────
# (unchanged from BoxScoreCollector/GameImpactCalculator.py)

def calc_qb_multiplier_enhanced(
    p: Dict,
    b: Optional[Dict] = None,
    nv_game: Optional[Dict] = None,
    nv_base: Optional[Dict] = None,
) -> Optional[float]:
    atts = p['pass_attempts']
    if atts < 5:
        return None

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

    comp_pct  = p['pass_completions'] / atts
    ypa       = p['pass_yards'] / atts
    td_int    = (p['pass_touchdowns'] + 1) / (p['pass_interceptions'] + 1)
    dropbacks = atts + p['sacks_taken']
    sack_rate = p['sacks_taken'] / dropbacks if dropbacks > 0 else 0.0
    rush_yards = float(p.get('rush_yards') or 0.0)

    if nv_game is None or nv_base is None:
        m = (
            (comp_pct / max(comp_pct_base, 0.01)) * 0.30 +
            (ypa      / max(ypa_base,      0.10)) * 0.35 +
            (td_int   / max(td_int_base,   0.10)) * 0.25 +
            (1 - max(0, sack_rate - sack_rate_base) * 5) * 0.10
        )
        m += p.get('scrambles', 0) * 0.01
        return _cap(m)

    # nflverse-enhanced path
    game_cpoe = float(nv_game.get('cpoe') or 0.0)
    base_cpoe = float(nv_base.get('cpoe') or 0.0)
    if base_cpoe == 0 and game_cpoe == 0:
        cpoe_component = comp_pct / max(comp_pct_base, 0.01)
    else:
        cpoe_component = 1.0 + (game_cpoe - base_cpoe) / 10.0
    cpoe_component = max(0.5, min(1.5, cpoe_component))

    air_yards_game = float(nv_game.get('passing_air_yards') or 0.0)
    air_yards_base = float(nv_base.get('passing_air_yards') or 0.0)
    atts_base_nv   = float(nv_base.get('attempts') or 0.0)
    game_adot = air_yards_game / atts if atts > 0 else 0.0
    base_adot = air_yards_base / atts_base_nv if atts_base_nv > 0 else 8.0
    ypa_ratio  = ypa       / max(ypa_base, 0.10)
    adot_ratio = game_adot / max(base_adot, 0.10)
    explosiveness = ypa_ratio * 0.6 + adot_ratio * 0.4

    td_int_component = td_int / max(td_int_base, 0.10)

    pass_epa_game = float(nv_game.get('passing_epa') or 0.0)
    pass_epa_base = float(nv_base.get('passing_epa') or 0.0)
    sacks_game_nv = float(nv_game.get('sacks') or p['sacks_taken'] or 0)
    sacks_base_nv = float(nv_base.get('sacks') or 0)
    plays_game = atts + sacks_game_nv
    plays_base = (nv_base.get('attempts') or 0) + sacks_base_nv
    if plays_game > 0 and plays_base > 0:
        game_epa_pp = pass_epa_game / plays_game
        base_epa_pp = pass_epa_base / plays_base
        epa_component = 1.0 + (game_epa_pp - base_epa_pp) / 0.3
        epa_component = max(0.5, min(1.5, epa_component))
    else:
        epa_component = 1.0

    sack_component = 1.0 - max(0.0, (sack_rate - sack_rate_base) * 5.0)
    sack_component = max(0.5, min(1.5, sack_component))

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


def calc_rb_multiplier_enhanced(
    p: Dict,
    b: Optional[Dict] = None,
    nv_game: Optional[Dict] = None,
    nv_base: Optional[Dict] = None,
) -> Optional[float]:
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

    avg_atts     = float(b.get('avg_rush_attempts') or 0) if b else 0
    bt_rate_base = (bt_base_raw / avg_atts) if avg_atts > 0 else _RB['bt_rate']

    ypc     = p['rush_yards'] / atts
    yac_per = (p['rush_yards_after_contact'] / atts) if p.get('rush_yards_after_contact', 0) > 0 else yac_base
    bt_rate = p.get('rush_broken_tackles', 0) / atts

    if nv_game is None or nv_base is None:
        rush_m = (
            (ypc     / max(ypc_base,     0.1)) * 0.45 +
            (yac_per / max(yac_base,     0.1)) * 0.35 +
            (1 + (bt_rate - bt_rate_base) * 3) * 0.20
        )
        rush_m -= p.get('rush_tlost', 0) * 0.02
        recv_bonus = (p.get('receptions', 0) * 0.01) + (p.get('receiving_touchdowns', 0) * 0.05)
        return _cap(rush_m * 0.80 + recv_bonus)

    ypc_component = ypc / max(ypc_base, 0.1)
    yac_component = yac_per / max(yac_base, 0.1)
    bt_component  = 1.0 + (bt_rate - bt_rate_base) * 3.0

    game_carries  = float(nv_game.get('carries') or atts)
    game_rush_epa = float(nv_game.get('rushing_epa') or 0.0)
    base_carries  = float(nv_base.get('carries') or 0.0)
    base_rush_epa = float(nv_base.get('rushing_epa') or 0.0)
    game_epa_pc   = game_rush_epa / game_carries if game_carries > 0 else 0.0
    base_epa_pc   = (base_rush_epa / base_carries) if base_carries > 0 else _RB_NV['epa_per_carry']
    epa_component = 1.0 + (game_epa_pc - base_epa_pc) / 0.2
    epa_component = max(0.5, min(1.5, epa_component))

    game_recv_yds  = float(nv_game.get('receiving_yards') or p.get('receiving_yards') or 0.0)
    game_recv_tds  = int(nv_game.get('receiving_tds')     or p.get('receiving_touchdowns') or 0)
    base_recv_yds  = float(nv_base.get('avg_receiving_yards') or _RB_NV['receiving_yards'])
    recv_component = game_recv_yds / max(base_recv_yds, 10.0)
    recv_component = max(0.3, min(2.0, recv_component))
    recv_component += game_recv_tds * 0.05

    game_fds     = float(nv_game.get('rushing_first_downs') or 0.0)
    base_fds_sum = float(nv_base.get('rushing_first_downs') or 0.0)
    game_fd_rate = game_fds / game_carries    if game_carries > 0 else 0.0
    base_fd_rate = (base_fds_sum / base_carries) if base_carries > 0 else _RB_NV['fd_rate']
    fd_component = game_fd_rate / max(base_fd_rate, 0.05)
    fd_component = max(0.5, min(2.0, fd_component))

    fumbles_lost = (
        int(nv_game.get('rushing_fumbles_lost')   or 0) +
        int(nv_game.get('receiving_fumbles_lost') or 0)
    )
    fumble_component = max(0.4, 1.0 - fumbles_lost * 0.15)

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


def calc_wr_te_multiplier_enhanced(
    p: Dict,
    b: Optional[Dict] = None,
    nv_game: Optional[Dict] = None,
    nv_base: Optional[Dict] = None,
) -> Optional[float]:
    targets = p.get('targets', 0)
    if targets < 2:
        return None

    catch_rate_base = (b.get('avg_catch_rate') or 0) if b else 0
    ypr_base        = (b.get('avg_ypr')        or 0) if b else 0
    avg_yac_yards  = float(b.get('avg_yac')             or 0) if b else 0
    avg_recv_yards = float(b.get('avg_receiving_yards') or 0) if b else 0
    avg_drops      = float(b.get('avg_drops')           or 0) if b else 0
    avg_targets_b  = float(b.get('avg_targets')         or 0) if b else 0

    if not catch_rate_base:
        catch_rate_base = _WR['catch_rate']
    if not ypr_base:
        ypr_base = _WR['ypr']

    yac_rate_base  = (avg_yac_yards  / avg_recv_yards) if avg_recv_yards > 0 else _WR['yac_rate']
    drop_rate_base = (avg_drops      / avg_targets_b)  if avg_targets_b  > 0 else _WR['drop_rate']

    recs       = p.get('receptions', 0)
    recv_yards = p.get('receiving_yards', 0)
    catch_rate = recs / targets
    ypr        = (recv_yards / recs) if recs > 0 else 0.0
    yac_rate   = (p.get('yards_after_catch', 0) / recv_yards) if recv_yards > 0 else yac_rate_base
    drop_rate  = p.get('drops', 0) / targets

    if nv_game is None or nv_base is None:
        m = (
            (catch_rate / max(catch_rate_base, 0.01)) * 0.40 +
            (ypr        / max(ypr_base,        0.10)) * 0.30 +
            (yac_rate   / max(yac_rate_base,   0.01)) * 0.20 +
            (1 - drop_rate / max(drop_rate_base, 0.01)) * 0.10
        )
        m += p.get('receiving_touchdowns', 0) * 0.05
        return _cap(m)

    catch_component = catch_rate / max(catch_rate_base, 0.01)
    ypr_component   = ypr / max(ypr_base, 0.10)
    yac_component   = yac_rate / max(yac_rate_base, 0.01)

    game_recv_epa  = float(nv_game.get('receiving_epa') or 0.0)
    game_tgts_nv   = float(nv_game.get('targets')       or targets)
    base_recv_epa  = float(nv_base.get('receiving_epa') or 0.0)
    base_tgts_nv   = float(nv_base.get('targets')       or 0.0)
    game_epa_pt = game_recv_epa / game_tgts_nv if game_tgts_nv > 0 else 0.0
    base_epa_pt = (base_recv_epa / base_tgts_nv) if base_tgts_nv > 0 else _WR_NV['epa_per_target']
    epa_component = 1.0 + (game_epa_pt - base_epa_pt) / 0.25
    epa_component = max(0.5, min(1.5, epa_component))

    game_wopr = float(nv_game.get('wopr') or nv_game.get('target_share') or 0.0)
    base_wopr = float(nv_base.get('wopr') or nv_base.get('target_share') or 0.0)
    if base_wopr == 0:
        base_wopr = _WR_NV['wopr']
    wopr_component = game_wopr / max(base_wopr, 0.01)
    wopr_component = max(0.3, min(2.0, wopr_component))

    fumbles_lost   = int(nv_game.get('receiving_fumbles_lost') or 0)
    drop_component = 1.0 - (drop_rate / max(drop_rate_base, 0.01)) * 0.70
    drop_component -= fumbles_lost * 0.20
    ball_security  = max(0.3, min(1.5, drop_component))

    game_fds     = float(nv_game.get('receiving_first_downs') or 0.0)
    base_fds     = float(nv_base.get('receiving_first_downs') or 0.0)
    base_recs_nv = float(nv_base.get('receptions')            or 0.0)
    game_fd_rate = game_fds / recs           if recs > 0         else 0.0
    base_fd_rate = (base_fds / base_recs_nv) if base_recs_nv > 0 else _WR_NV['fd_rate']
    fd_component  = game_fd_rate / max(base_fd_rate, 0.05)
    fd_component += p.get('receiving_touchdowns', 0) * 0.05
    fd_component  = max(0.3, min(2.0, fd_component))

    m = (
        catch_component * 0.20 +
        ypr_component   * 0.15 +
        yac_component   * 0.10 +
        epa_component   * 0.20 +
        wopr_component  * 0.15 +
        ball_security   * 0.10 +
        fd_component    * 0.10
    )
    return _cap(m)


def calc_ol_multiplier(
    p: Dict,
    b: Optional[Dict] = None,
    nv_game: Optional[Dict] = None,
    nv_base: Optional[Dict] = None,
) -> Optional[float]:
    if nv_game is None or nv_base is None:
        return 1.0

    sacks     = float(nv_game.get('team_sacks_suffered') or 0.0)
    pass_atts = float(nv_game.get('team_pass_attempts')  or 0.0)
    dropbacks = pass_atts + sacks
    game_sack_rate = sacks / dropbacks if dropbacks > 0 else 0.0
    base_sack_rate = float(nv_base.get('base_sack_rate') or _OL_NV['sack_rate'])
    pass_prot = 1.0 - (game_sack_rate - base_sack_rate) * 8.0
    pass_prot = max(0.5, min(1.5, pass_prot))

    rush_yds = float(nv_game.get('team_rushing_yards') or 0.0)
    carries  = float(nv_game.get('team_carries')       or 0.0)
    game_ypc      = rush_yds / carries if carries > 0 else 0.0
    base_team_ypc = float(nv_base.get('base_team_ypc') or _OL_NV['team_ypc'])
    run_block = game_ypc / max(base_team_ypc, 0.10)
    run_block = max(0.5, min(1.5, run_block))

    game_rush_epa = float(nv_game.get('team_rushing_epa') or 0.0)
    base_rush_epa = float(nv_base.get('base_team_rush_epa') or 0.0)
    base_carries  = float(nv_base.get('base_carries') or carries or 1.0)
    game_epa_pc = game_rush_epa / carries       if carries      > 0 else 0.0
    base_epa_pc = base_rush_epa / base_carries  if base_carries > 0 else _OL_NV['team_rush_epa_pc']
    epa_component = 1.0 + (game_epa_pc - base_epa_pc) / 0.15
    epa_component = max(0.5, min(1.5, epa_component))

    game_penalties = float(nv_game.get('team_ol_penalties') or 0.0)
    base_penalties = float(nv_base.get('base_ol_penalties') or _OL_NV['ol_penalties'])
    penalty_component = 1.0 - (game_penalties - base_penalties) * 0.08
    penalty_component = max(0.5, min(1.3, penalty_component))

    hurries     = float(nv_game.get('team_hurries')    or 0.0)
    knockdowns  = float(nv_game.get('team_knockdowns') or 0.0)
    base_pressure_rate = float(nv_base.get('base_pressure_rate') or _OL_NV['pressure_rate'])
    if dropbacks > 0 and (hurries > 0 or knockdowns > 0):
        game_pressure_rate = (hurries + knockdowns) / dropbacks
        pressure_component = 1.0 - (game_pressure_rate - base_pressure_rate) * 3.0
        pressure_component = max(0.5, min(1.3, pressure_component))
    else:
        pressure_component = 1.0

    m = (
        pass_prot          * 0.40 +
        run_block          * 0.25 +
        epa_component      * 0.15 +
        penalty_component  * 0.10 +
        pressure_component * 0.10
    )
    return _cap(m)


def calc_front7_multiplier(
    p: Dict,
    b: Optional[Dict] = None,
    nv_game: Optional[Dict] = None,
    nv_base: Optional[Dict] = None,
) -> Optional[float]:
    total_activity = (
        float(p['tackles'])          + float(p['ast_tackles']) +
        float(p['def_sacks'])        + float(p['qb_hits'])     + float(p['hurries']) +
        float(p['tackles_for_loss']) + float(p['passes_defended']) + float(p['interceptions'])
    )
    if total_activity < 1:
        return None

    game_pressure = (
        float(p['def_sacks']) * 3.0 +
        float(p['qb_hits'])   * 1.5 +
        float(p['hurries'])   * 0.75
    )
    avg_pressure = 0.0
    if b:
        avg_pressure = (
            float(b.get('avg_def_sacks') or 0) * 3.0 +
            float(b.get('avg_qb_hits')   or 0) * 1.5 +
            float(b.get('avg_hurries')   or 0) * 0.75
        )
    pressure_denom = max(avg_pressure, 2.0)
    pressure_m = 1.0 + (game_pressure - avg_pressure) / pressure_denom
    pressure_m = max(0.5, min(1.8, pressure_m))

    run_stop = (
        float(p['tackles'])          +
        float(p['ast_tackles']) * 0.5 +
        float(p['tackles_for_loss']) * 2.0
    )
    avg_run_stop = max(float(b.get('avg_tackles') or 3.0) if b else 3.0, 0.5)
    run_m = 1.0 + (run_stop - avg_run_stop) * 0.08
    run_m = max(0.5, min(1.8, run_m))

    tackle_quality_m = 1.0 - float(p['missed_tackles']) * 0.15
    tackle_quality_m = max(0.5, min(1.2, tackle_quality_m))

    to_score = (
        float(p['interceptions'])             * 1.5 +
        float(p.get('def_fumbles_forced', 0)) * 1.0
    )
    avg_to = 0.0
    if b:
        avg_to = (
            float(b.get('avg_interceptions')  or 0) * 1.5 +
            float(b.get('avg_fumbles_forced') or 0) * 1.0
        )
    turnover_m = 1.0 + (to_score - avg_to) * 0.30
    turnover_m = max(0.7, min(1.8, turnover_m))

    coverage_m = 1.0
    if float(p.get('def_targets', 0)) > 0:
        allow_rate = float(p['def_completions_allowed']) / float(p['def_targets'])
        avg_allow  = 0.65
        if b and float(b.get('avg_def_targets') or 0) > 0:
            avg_allow = float(b.get('avg_def_comp_allowed') or 0) / float(b['avg_def_targets'])
        coverage_m = 1.0 + (avg_allow - allow_rate) * 0.8
    coverage_m += float(p['passes_defended']) * 0.04 + float(p['interceptions']) * 0.05
    coverage_m = max(0.6, min(1.5, coverage_m))

    m = (
        pressure_m       * 0.35 +
        run_m            * 0.25 +
        tackle_quality_m * 0.15 +
        turnover_m       * 0.15 +
        coverage_m       * 0.10
    )
    return _cap(m)


def calc_secondary_multiplier(
    p: Dict,
    b: Optional[Dict] = None,
    nv_game: Optional[Dict] = None,
    nv_base: Optional[Dict] = None,
) -> Optional[float]:
    total_activity = (
        float(p['tackles'])         + float(p['ast_tackles']) +
        float(p['passes_defended']) + float(p['interceptions']) +
        float(p['def_sacks'])       + float(p['qb_hits'])
    )
    if total_activity < 1:
        return None

    coverage_m = 1.0
    if float(p.get('def_targets', 0)) > 0:
        allow_rate = float(p['def_completions_allowed']) / float(p['def_targets'])
        avg_allow  = 0.60
        if b and float(b.get('avg_def_targets') or 0) > 0:
            avg_allow = float(b.get('avg_def_comp_allowed') or 0) / float(b['avg_def_targets'])
        coverage_m = 1.0 + (avg_allow - allow_rate) * 1.5
    coverage_m += float(p['passes_defended']) * 0.07 + float(p['interceptions']) * 0.15
    coverage_m = max(0.4, min(2.0, coverage_m))

    play_score = (
        float(p['passes_defended'])            * 0.5  +
        float(p['interceptions'])              * 1.5  +
        float(p.get('def_fumbles_forced', 0))  * 1.0
    )
    avg_play = 0.0
    if b:
        avg_play = (
            float(b.get('avg_passes_defended') or 0) * 0.5  +
            float(b.get('avg_interceptions')   or 0) * 1.5  +
            float(b.get('avg_fumbles_forced')  or 0) * 1.0
        )
    play_baseline = max(avg_play, 0.5)
    play_m = 1.0 + (play_score - avg_play) / play_baseline * 0.5
    play_m = max(0.5, min(2.5, play_m))

    avg_tackles  = float(b.get('avg_tackles') or 4.0) if b else 4.0
    tackle_score = (
        float(p['tackles'])          +
        float(p['ast_tackles']) * 0.5 -
        float(p['missed_tackles']) * 1.5
    )
    tackle_m = 1.0 + (tackle_score - avg_tackles) * 0.05
    tackle_m = max(0.5, min(1.5, tackle_m))

    to_score = (
        float(p['interceptions'])             * 2.0 +
        float(p.get('def_fumbles_forced', 0)) * 1.0
    )
    avg_to = 0.0
    if b:
        avg_to = (
            float(b.get('avg_interceptions')  or 0) * 2.0 +
            float(b.get('avg_fumbles_forced') or 0) * 1.0
        )
    turnover_m = 1.0 + (to_score - avg_to) * 0.25
    turnover_m = max(0.7, min(2.0, turnover_m))

    pressure = (
        float(p['def_sacks']) * 3.0 +
        float(p['qb_hits'])   * 1.0 +
        float(p['hurries'])   * 0.5
    )
    avg_pressure = 0.0
    if b:
        avg_pressure = (
            float(b.get('avg_def_sacks') or 0) * 3.0 +
            float(b.get('avg_qb_hits')   or 0) * 1.0 +
            float(b.get('avg_hurries')   or 0) * 0.5
        )
    pressure_denom = max(avg_pressure, 1.0)
    pressure_m = 1.0 + (pressure - avg_pressure) / pressure_denom * 0.4
    pressure_m = max(0.8, min(1.3, pressure_m))

    m = (
        coverage_m * 0.35 +
        play_m     * 0.25 +
        tackle_m   * 0.20 +
        turnover_m * 0.15 +
        pressure_m * 0.05
    )
    return _cap(m)


def calc_performance_multiplier(
    p: Dict,
    b: Optional[Dict] = None,
    nv_game: Optional[Dict] = None,
    nv_base: Optional[Dict] = None,
) -> Optional[float]:
    pos = (p.get('position') or '').upper()
    if pos == 'QB':
        return calc_qb_multiplier_enhanced(p, b, nv_game, nv_base)
    if pos in ('RB', 'HB', 'FB'):
        return calc_rb_multiplier_enhanced(p, b, nv_game, nv_base)
    if pos in ('WR', 'TE'):
        return calc_wr_te_multiplier_enhanced(p, b, nv_game, nv_base)
    if pos in ('LT', 'RT', 'LG', 'RG', 'C', 'OL', 'G', 'T'):
        return calc_ol_multiplier(p, b, nv_game, nv_base)
    if pos in ('DE', 'DT', 'NT', 'EDGE', 'LB', 'ILB', 'OLB', 'MLB', 'DL'):
        return calc_front7_multiplier(p, b, nv_game, nv_base)
    if pos in ('CB', 'S', 'FS', 'SS', 'DB', 'SAF'):
        return calc_secondary_multiplier(p, b, nv_game, nv_base)
    return None


# ── Multiplier with components (for JSONB enrichment) ────────────────────────

def calc_performance_multiplier_with_components(
    p: Dict,
    b: Optional[Dict] = None,
    nv_game: Optional[Dict] = None,
    nv_base: Optional[Dict] = None,
) -> Tuple[Optional[float], Dict[str, Any]]:
    """
    Calls calc_performance_multiplier and assembles a components dict capturing
    the key inputs used, suitable for storage in the multiplier_components JSONB.
    Returns (multiplier, components_dict).
    """
    pos        = (p.get('position') or '').upper()
    multiplier = calc_performance_multiplier(p, b, nv_game, nv_base)

    if multiplier is None:
        return None, {}

    path = 'nflverse_enhanced' if (nv_game is not None and nv_base is not None) else 'box_score_fallback'
    components: Dict[str, Any] = {
        'path':  path,
        'final': round(multiplier, 4),
    }

    if pos == 'QB':
        atts = p.get('pass_attempts', 0)
        if atts >= 5:
            components['pass_attempts']  = atts
            components['comp_pct']       = round(p.get('pass_completions', 0) / max(atts, 1), 4)
            components['ypa']            = round(p.get('pass_yards', 0) / max(atts, 1), 2)
            components['sacks_taken']    = p.get('sacks_taken', 0)
            if nv_game:
                components['cpoe']           = round(float(nv_game.get('cpoe') or 0), 4)
                components['passing_epa']    = round(float(nv_game.get('passing_epa') or 0), 3)
                components['passing_air_yards'] = nv_game.get('passing_air_yards')

    elif pos in ('RB', 'HB', 'FB'):
        atts = p.get('rush_attempts', 0)
        if atts >= 3:
            components['rush_attempts']  = atts
            components['rush_yards']     = p.get('rush_yards', 0)
            components['ypc']            = round(p.get('rush_yards', 0) / max(atts, 1), 2)
            if nv_game:
                components['rushing_epa']        = round(float(nv_game.get('rushing_epa') or 0), 3)
                components['rushing_first_downs'] = nv_game.get('rushing_first_downs')
                components['receiving_yards_nv']  = nv_game.get('receiving_yards')
                components['fumbles_lost']        = (
                    int(nv_game.get('rushing_fumbles_lost') or 0) +
                    int(nv_game.get('receiving_fumbles_lost') or 0)
                )

    elif pos in ('WR', 'TE'):
        tgts = p.get('targets', 0)
        if tgts >= 2:
            components['targets']     = tgts
            components['receptions']  = p.get('receptions', 0)
            components['recv_yards']  = p.get('receiving_yards', 0)
            if nv_game:
                components['receiving_epa']  = round(float(nv_game.get('receiving_epa') or 0), 3)
                components['wopr']           = round(float(nv_game.get('wopr') or 0), 4)
                components['target_share']   = round(float(nv_game.get('target_share') or 0), 4)
                components['recv_fumb_lost'] = int(nv_game.get('receiving_fumbles_lost') or 0)

    elif pos in _OL_POS:
        if nv_game:
            components['team_sacks_suffered'] = float(nv_game.get('team_sacks_suffered') or 0)
            components['team_pass_attempts']  = float(nv_game.get('team_pass_attempts') or 0)
            components['team_carries']        = float(nv_game.get('team_carries') or 0)
            components['team_rushing_epa']    = round(float(nv_game.get('team_rushing_epa') or 0), 3)
            components['ol_team_proxy']       = True

    elif pos in _FRONT7_POS:
        components['tackles']       = p.get('tackles', 0)
        components['def_sacks']     = float(p.get('def_sacks', 0))
        components['qb_hits']       = p.get('qb_hits', 0)
        components['hurries']       = p.get('hurries', 0)
        components['tfl']           = p.get('tackles_for_loss', 0)
        components['interceptions'] = p.get('interceptions', 0)

    elif pos in _SEC_POS:
        components['tackles']        = p.get('tackles', 0)
        components['passes_defended'] = p.get('passes_defended', 0)
        components['interceptions']  = p.get('interceptions', 0)
        if p.get('def_targets', 0) > 0:
            components['allow_rate'] = round(
                p.get('def_completions_allowed', 0) / max(p.get('def_targets', 1), 1), 4
            )

    return multiplier, components


# ── Team-level aggregation ─────────────────────────────────────────────────────

def calc_team_impacts(
    players: List[Dict],
    team: str,
    player_baselines: Optional[Dict[str, Dict]] = None,
    nflverse_data: Optional[Dict[str, Dict]] = None,
) -> Tuple[float, float, Dict[str, float], List[Dict]]:
    """
    Enhanced team impact calculation with nflverse enrichment.

    Parameters
    ----------
    players          : all player dicts from BoxScoreParser (both teams)
    team             : team abbreviation to aggregate (e.g. 'KC', 'BUF')
    player_baselines : {player_id: baseline_dict} from player_season_stats
    nflverse_data    : {player_id: {'nv_game': dict, 'nv_base': dict}}
                       from NflverseReader.  Pass None/empty for box-score-only mode.

    Returns
    -------
    (actual_impact, expected_impact, position_groups, player_details)

    position_groups:
        {'offense_impact': float, 'defense_impact': float, 'ol_impact': float}

    player_details:
        list of per-player dicts including multiplier_components for JSONB storage

    Side effects: mutates each player dict to set
        p['performance_multiplier'], p['actual_impact_score'], p['multiplier_components']

    Two-pass OL processing:
        Pass 1 — compute QB/RB/Skill/Defense multipliers; collect QB+RB context.
        Assemble team_ol_context from that QB/RB context.
        Pass 2 — compute OL multipliers using the assembled team context.
    """
    team_players = [p for p in players if (p.get('team') or '').upper() == team.upper()]
    baselines    = player_baselines or {}
    nflverse     = nflverse_data or {}

    # ── PASS 1: QB, RB, Skill, Defense ───────────────────────────────────────
    team_qb_ctx: Dict[str, Any] = {}   # collected from starting QB row
    team_rb_rushing_yards = 0.0
    team_rb_carries       = 0.0
    team_rb_rushing_epa   = 0.0

    for p in team_players:
        pos = (p.get('position') or '').upper()
        if pos in _OL_POS:
            continue  # handled in pass 2

        pid    = p.get('player_id', '')
        b      = baselines.get(pid)
        nv     = nflverse.get(pid, {})
        nv_game = nv.get('nv_game')
        nv_base = nv.get('nv_base')

        multiplier, components = calc_performance_multiplier_with_components(
            p, b, nv_game, nv_base
        )
        if multiplier is None:
            multiplier = 1.0
            components = {}

        weight    = POSITION_WEIGHTS.get(pos, 0.5)
        pff_grade = float(p.get('pff_grade') or _DEFAULT_GRADE)

        p['performance_multiplier'] = round(multiplier, 3)
        p['actual_impact_score']    = round(pff_grade * weight * multiplier, 2)
        p['multiplier_components']  = components
        p['nflverse_enriched']      = (nv_game is not None)

        # Collect context for OL team proxy
        if pos in _QB_POS:
            team_qb_ctx = {
                'sacks_taken':   p.get('sacks_taken', 0),
                'pass_attempts': p.get('pass_attempts', 0),
                'times_hurried': p.get('times_hurried', 0),
                'knockdowns':    p.get('knockdowns', 0),
                'nv_base':       nv_base or {},
            }

        if pos in _RB_POS:
            team_rb_rushing_yards += float(p.get('rush_yards', 0))
            team_rb_carries       += float(p.get('rush_attempts', 0))
            if nv_game:
                team_rb_rushing_epa += float(nv_game.get('rushing_epa') or 0)

    # ── Assemble OL team context from QB/RB data ─────────────────────────────
    qb_nv_base    = team_qb_ctx.get('nv_base', {})
    qb_base_atts  = float(qb_nv_base.get('attempts') or 0)
    qb_base_sacks = float(qb_nv_base.get('sacks')    or 0)
    base_sack_rate = (
        qb_base_sacks / (qb_base_atts + qb_base_sacks)
        if (qb_base_atts + qb_base_sacks) > 0
        else _OL_NV['sack_rate']
    )

    # Build base YPC from player_baselines for team RBs
    rb_players     = [p for p in team_players if (p.get('position') or '').upper() in _RB_POS]
    base_rb_yards  = 0.0
    base_rb_carries = 0.0
    base_rb_rush_epa = 0.0

    for rb in rb_players:
        rb_pid = rb.get('player_id', '')
        rb_b   = baselines.get(rb_pid)
        if rb_b:
            base_rb_yards   += float(rb_b.get('avg_rush_yards')    or 0)
            base_rb_carries += float(rb_b.get('avg_rush_attempts') or 0)
        rb_nv      = nflverse.get(rb_pid, {})
        rb_nv_base = rb_nv.get('nv_base')
        if rb_nv_base:
            base_rb_rush_epa += float(rb_nv_base.get('rushing_epa') or 0)
            if base_rb_carries == 0:
                base_rb_carries = float(rb_nv_base.get('carries') or 0)

    base_team_ypc = (
        base_rb_yards / base_rb_carries
        if base_rb_carries > 0
        else _OL_NV['team_ypc']
    )

    ol_nv_game = {
        'team_sacks_suffered': team_qb_ctx.get('sacks_taken',   0),
        'team_pass_attempts':  team_qb_ctx.get('pass_attempts', 0),
        'team_rushing_yards':  team_rb_rushing_yards,
        'team_carries':        team_rb_carries,
        'team_rushing_epa':    team_rb_rushing_epa,
        'team_hurries':        team_qb_ctx.get('times_hurried', 0),
        'team_knockdowns':     team_qb_ctx.get('knockdowns',    0),
        'team_ol_penalties':   0.0,  # Sportradar optional; not currently parsed
    }
    ol_nv_base = {
        'base_sack_rate':      base_sack_rate,
        'base_team_ypc':       base_team_ypc,
        'base_team_rush_epa':  base_rb_rush_epa,
        'base_carries':        base_rb_carries if base_rb_carries > 0 else 1.0,
        'base_ol_penalties':   _OL_NV['ol_penalties'],
        'base_pressure_rate':  _OL_NV['pressure_rate'],
    }

    # Use None/None (returns 1.0) if we couldn't assemble any QB context at all
    ol_game_arg = ol_nv_game if team_qb_ctx else None
    ol_base_arg = ol_nv_base if team_qb_ctx else None

    # ── PASS 2: OL ───────────────────────────────────────────────────────────
    for p in team_players:
        pos = (p.get('position') or '').upper()
        if pos not in _OL_POS:
            continue

        pid = p.get('player_id', '')
        b   = baselines.get(pid)

        multiplier, components = calc_performance_multiplier_with_components(
            p, b, ol_game_arg, ol_base_arg
        )
        if multiplier is None:
            multiplier = 1.0
            components = {}

        weight    = POSITION_WEIGHTS.get(pos, 0.5)
        pff_grade = float(p.get('pff_grade') or _DEFAULT_GRADE)

        p['performance_multiplier'] = round(multiplier, 3)
        p['actual_impact_score']    = round(pff_grade * weight * multiplier, 2)
        p['multiplier_components']  = components
        p['nflverse_enriched']      = (ol_game_arg is not None)

    # ── Aggregate: totals + position groups ──────────────────────────────────
    total_actual   = 0.0
    total_expected = 0.0
    total_weight   = 0.0

    off_actual = 0.0;  off_weight = 0.0
    def_actual = 0.0;  def_weight = 0.0
    ol_actual  = 0.0;  ol_weight  = 0.0

    player_details: List[Dict] = []

    for p in team_players:
        pos       = (p.get('position') or '').upper()
        weight    = POSITION_WEIGHTS.get(pos, 0.5)
        pff_grade = float(p.get('pff_grade') or _DEFAULT_GRADE)
        multiplier = p.get('performance_multiplier', 1.0)

        expected_score = pff_grade * weight
        actual_score   = pff_grade * weight * multiplier

        total_expected += expected_score
        total_actual   += actual_score
        total_weight   += weight

        if pos in _QB_POS | _RB_POS | _SKILL_POS:
            off_actual += actual_score
            off_weight += weight
        elif pos in _OL_POS:
            ol_actual += actual_score
            ol_weight += weight
        elif pos in _DEF_POS:
            def_actual += actual_score
            def_weight += weight

        player_details.append({
            'player_id':              p.get('player_id', ''),
            'player_name':            p.get('player_name', ''),
            'position':               pos,
            'pff_grade':              round(pff_grade, 1),
            'weight':                 weight,
            'performance_multiplier': multiplier,
            'actual_impact_score':    p.get('actual_impact_score', 0.0),
            'nflverse_enriched':      p.get('nflverse_enriched', False),
            'multiplier_components':  p.get('multiplier_components', {}),
        })

    if total_weight == 0:
        logger.warning("No scorable players for %s", team)
        return 0.0, 0.0, {}, []

    actual   = round(total_actual   / total_weight, 4)
    expected = round(total_expected / total_weight, 4)

    position_groups = {
        'offense_impact': round(off_actual / off_weight, 4) if off_weight > 0 else 0.0,
        'defense_impact': round(def_actual / def_weight, 4) if def_weight > 0 else 0.0,
        'ol_impact':      round(ol_actual  / ol_weight,  4) if ol_weight  > 0 else 0.0,
    }

    nflverse_enriched_count = sum(1 for d in player_details if d.get('nflverse_enriched'))
    logger.info(
        "%s actual=%.2f expected=%.2f surprise=%+.2f "
        "(%d players, weight=%.1f, nflverse=%d/%d)",
        team, actual, expected, actual - expected,
        len(team_players), total_weight,
        nflverse_enriched_count, len(team_players),
    )
    return actual, expected, position_groups, player_details


def calc_performance_surprise(actual: float, expected: float) -> float:
    return round(actual - expected, 4)


def _cap(v: float) -> float:
    return max(_MULTIPLIER_CAP[0], min(_MULTIPLIER_CAP[1], v))
