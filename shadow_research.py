"""Versioned research telemetry only. Never called by production indicators/alerts.

Thresholds here operationalize qualitative hypotheses; they are NOT validated rules.
All state is per run/symbol, causal, and discarded across observation gaps >3 min.
"""
import math

VERSION = 'shadow-v1'
HYPOTHESES = tuple(f'H{i}' for i in range(1, 8))
GAP_MS = 180_000
EVENT_MS = 60 * 60_000


def number(s, key):
    v = s.get(key)
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def gt(s, key, threshold):
    v = number(s, key)
    return v is not None and v > threshold


def lt(s, key, threshold):
    v = number(s, key)
    return v is not None and v < threshold


def between(s, key, low, high):
    v = number(s, key)
    return v is not None and low <= v <= high


def extension_features(candles, hourly, price, asof_ms, atr_pct):
    """Returns use a past hourly OPEN (target rounded down), never an unfinished close.
    Local base = lowest low of last 60 contiguous CLOSED 1m candles.
    ATR extension = distance from that base / confirmed 1m ATR (supplied as %).
    Missing/discontinuous history produces null, not a fabricated return.
    """
    out = {}
    history = {} if not hourly else {int(t * 1000): o for t, o in zip(hourly['time'], hourly['open']) if t * 1000 <= asof_ms}
    for label, hours in (('24h', 24), ('3d', 72), ('7d', 168)):
        target = asof_ms - hours * 3_600_000
        anchor = target // 3_600_000 * 3_600_000
        base = history.get(anchor)
        out[f'return_{label}'] = round((price / base - 1) * 100, 6) if base and price > 0 else None
        out[f'return_{label}_anchor_ms'] = anchor if base else None
        out[f'return_{label}_rounding_sec'] = (target - anchor) / 1000 if base else None
    closed = [(int(t * 1000), low) for t, low in zip(candles['time'], candles['low']) if t * 1000 + 60_000 <= asof_ms][-60:]
    valid = (len(closed) == 60 and closed[-1][0] + 60_000 == asof_ms // 60_000 * 60_000
             and all(b[0] - a[0] == 60_000 for a, b in zip(closed, closed[1:])))
    base = min(v for _, v in closed) if valid else None
    closes = [(int(t * 1000), c) for t, c in zip(candles['time'], candles.get('close', [])) if t * 1000 + 60_000 <= asof_ms]
    atr_price = closes[-1][1] if closes else None
    atr = atr_price * atr_pct / 100 if atr_pct and atr_price and atr_price > 0 else None
    out.update(local_base_price=base, local_base_window_min=60,
               local_base_return=round((price / base - 1) * 100, 6) if base else None,
               atr_extension=round((price - base) / atr, 6) if base and atr else None,
               extension_source='past_hourly_open_and_closed_1m', extension_version='extension-v1')
    out['h7_features_ready'] = all(out.get(k) is not None for k in ('return_24h', 'return_3d', 'return_7d', 'local_base_return', 'atr_extension'))
    return out


def quality(s):
    reasons = []
    if not all(s.get(f'{w}_complete') is True for w in ('1m', '5m', '15m')):
        reasons.append('partial_flow')
    if s.get('sync_error') or s.get('pool_contamination_reset'):
        reasons.append('sync_error')
    if s.get('required_fields_missing'):
        reasons.append('required_fields_missing')
    if s.get('clock_synced') is not True:
        reasons.append('clock_unsynced')
    if number(s, 'bar_progress_sec') is None or not 0 <= s['bar_progress_sec'] <= 90:
        reasons.append('stale_kline')
    if number(s, 'captured_at_ms') is not None and number(s, 'kline_asof_ms') is not None and not 0 <= s['captured_at_ms'] - s['kline_asof_ms'] <= 90_000:
        reasons.append('price_flow_time_mismatch')
    if s.get('kline_gaps_300', 0):
        reasons.append('kline_gaps')
    return reasons


def ob_valid(s):
    return (s.get('ob_stale') is False and not s.get('ob_error') and not s.get('sync_error')
            and between(s, 'ob_age_ms', 0, 5000) and number(s, 'orderbook_imbalance') is not None)


def state(s, tf, direction):
    return s.get(f'str_{tf}_ready') is True and s.get(f'str_{tf}_state') in (
        ('BULL', 'TR-UP') if direction == 'UP' else ('BEAR', 'TR-DN'))


def event(s, tf, direction, max_age=3):
    return (s.get(f'str_{tf}_ready') is True
            and s.get(f'str_{tf}_event') in (f'BOS {direction}', f'CHOCH {direction}')
            and between(s, f'str_{tf}_event_age', 0, max_age))


class ShadowTracker:
    def __init__(self):
        self.symbols = {}

    def update(self, s):
        now = s['captured_at_ms']
        key = (s.get('run_id'), s['symbol'])
        mem = self.symbols.setdefault(key, {'last': now, 'events': {}, 'latches': {}})
        gap = now - mem['last'] > GAP_MS or now < mem['last']
        if gap:
            mem = {'last': now, 'events': {}, 'latches': {}}
            self.symbols[key] = mem
        mem['last'] = now
        out = {'shadow_version': VERSION, 'shadow_gap_reset': gap,
               'shadow_quality_veto': '|'.join(quality(s)), 'shadow_ob_valid': ob_valid(s)}
        valid = not out['shadow_quality_veto']
        bull = any(state(s, tf, 'UP') for tf in ('15m', '1h', '4h'))
        bear = any(state(s, tf, 'DN') for tf in ('15m', '1h'))
        up = s.get('cvd_turn_3m') == 'UP' or (gt(s, 'cvd_slope_3m_norm', 0) and gt(s, 'cvd_1m_delta', 0))
        down = s.get('cvd_turn_3m') == 'DOWN' or (lt(s, 'cvd_slope_3m_norm', 0) and lt(s, 'cvd_1m_delta', 0))
        # Separate exact one-minute direction research from the inherited 3m proxy variant.
        current_br = number(s, 'buyer_ratio_1m')
        delta_br = number(s, 'buyer_ratio_delta_1m')
        one = (2 * current_br - 100) / 100 if current_br is not None else None
        prev_one = (2 * (current_br - delta_br) - 100) / 100 if current_br is not None and delta_br is not None else None
        turn = None if one is None or prev_one is None or not valid else ('UP' if prev_one <= -.02 and one >= .02 else 'DOWN' if prev_one >= .02 and one <= -.02 else 'NONE')
        out.update(shadow_cvd_slope_1m_norm=one if valid else None,
                   shadow_cvd_slope_prev_1m_norm=prev_one if valid else None,
                   shadow_cvd_turn_1m=turn, shadow_trigger_flow_source='3m_turn_or_slope_plus_1m_delta')
        for tf in ('1m', '3m', '5m', '15m', '1h', '4h'):
            age = number(s, f'str_{tf}_event_age')
            out[f'shadow_str_{tf}_freshness'] = 'UNKNOWN' if age is None else 'FRESH_0_3' if age <= 3 else 'RECENT_4_10' if age <= 10 else 'OLD'
        rising5 = gt(s, 'cvd_5m_delta', 0)
        u = number(s, 'realf_unpriced_flow')
        reset = all(lt(s, f'fat_{tf}', 30) and s.get(f'fat_{tf}_ready') is True for tf in ('1m', '3m', '5m'))
        deep = reset and lt(s, 'fat_15m', 35) and s.get('fat_15m_ready') is True
        out.update(shadow_reset_type='DEEP_RESET' if deep else 'RESET' if reset else 'NONE',
                   shadow_htf_context='MIXED' if bull and bear else 'BULL' if bull else 'BEAR' if bear else 'OTHER',
                   shadow_gap_direction='EXPANDING' if gt(s, 'unpriced_d3', 0) else 'CONTRACTING' if lt(s, 'unpriced_d3', 0) else 'UNKNOWN',
                   shadow_unpriced_bucket='STRONG_GAP' if u is not None and u > .01 else 'GAP' if u is not None and u > .005 else 'SMALL' if u is not None and u > 0 else 'NONPOSITIVE' if u is not None else 'UNKNOWN',
                   shadow_r2_tier='HIGH' if gt(s, 'realf_beta_r2', .45) else 'MID' if gt(s, 'realf_beta_r2', .35) else 'LOW_OR_MISSING',
                   shadow_fatigue_recovery_per_min=number(s, 'fatigue_delta_1m'))
        if reset:
            mem.setdefault('reset_start', now)
        else:
            mem.pop('reset_start', None)
        out['shadow_reset_duration_sec'] = (now - mem['reset_start']) / 1000 if reset else None

        # Latches preserve the temporal "exhaustion THEN unwind" and "bounce THEN fail" sequence.
        if valid and gt(s, 'fat_1m', 83) and s.get('fat_1m_ready') is True:
            mem['latches']['exhaustion'] = now
        bounce = valid and bear and gt(s, 'fatigue_delta_3m', 0) and gt(s, 'chg_1m_pct', 0)
        if bounce:
            mem['latches']['bounce'] = now
        exhausted = now - mem['latches'].get('exhaustion', -10**20) <= 15 * 60_000
        bounced = now - mem['latches'].get('bounce', -10**20) <= 15 * 60_000

        # raw, setup, armed, trigger-condition. All are research definitions v1.
        raw1 = any(lt(s, f'fat_{tf}', 35) for tf in ('3m', '5m'))
        setup1 = raw1 and bull and between(s, 'realf_score', 35, 55)
        armed1 = setup1 and u is not None and u >= 0
        raw2 = u is not None and u > 0
        setup2 = raw2 and gt(s, 'realf_unpriced_flow', .005) and lt(s, 'realf_score', 50) and gt(s, 'realf_beta_r2', .45) and gt(s, 'realf_component_agreement', .5)
        armed2 = setup2 and lt(s, 'fat_1m', 83) and not event(s, '5m', 'DN')
        raw3 = any(s.get(f'str_{tf}_event') == 'BOS UP' and event(s, tf, 'UP') for tf in ('5m', '15m'))
        setup3 = any(s.get(f'str_{tf}_event') == 'BOS UP' and event(s, tf, 'UP') and gt(s, f'str_{tf}_event_strength', 30) and gt(s, f'str_{tf}_conf', 60) for tf in ('5m', '15m'))
        armed3 = setup3 and lt(s, 'fat_1m', 72) and between(s, 'realf_score', 40, 60)
        setup4 = exhausted and (gt(s, 'realf_score', 58) or lt(s, 'realf_unpriced_flow', 0))
        armed4 = setup4 and lt(s, 'fatigue_delta_1m', 0) and lt(s, 'cvd_1m_delta', 0)
        setup5 = bear and bounced
        armed5 = setup5 and u is not None and u <= .005 and lt(s, 'cvd_5m', 0)
        stages = {
            'H1': (raw1, setup1, armed1, armed1 and (up or event(s, '1m', 'UP')) and rising5),
            'H2': (raw2, setup2, armed2, armed2 and up and rising5 and gt(s, 'buyer_ratio_delta_1m', 0)),
            'H3': (raw3, setup3, armed3, armed3 and gt(s, 'cvd_1m', 0) and gt(s, 'cvd_5m', 0) and gt(s, 'buyer_ratio_1m', 50)),
            'H4': (exhausted, setup4, armed4, armed4 and down and any(event(s, tf, 'DN') for tf in ('3m', '5m'))),
            'H5': (bear, setup5, armed5, armed5 and now > mem['latches'].get('bounce', now) and down and any(state(s, tf, 'DN') for tf in ('1m', '3m'))),
            'H6': (any(lt(s, f'fat_{tf}', 30) for tf in ('1m', '3m', '5m')), reset, False, False),
            'H7': (lt(s, 'fat_1m', 30), lt(s, 'fat_1m', 30) and bool(s.get('h7_features_ready')), False, False),
        }
        components = {
            'H1': {'fatigue_3m_or_5m_lt35': raw1, 'htf_bull': bull, 'realf_35_55': between(s, 'realf_score', 35, 55),
                   'unpriced_nonnegative': u is not None and u >= 0, 'flow_up_or_structure_up': up or event(s, '1m', 'UP'), 'cvd5_delta_positive': rising5},
            'H2': {'unpriced_gt005': gt(s, 'realf_unpriced_flow', .005), 'realf_lt50': lt(s, 'realf_score', 50),
                   'r2_gt045': gt(s, 'realf_beta_r2', .45), 'agreement_gt05': gt(s, 'realf_component_agreement', .5),
                   'fatigue_lt83': lt(s, 'fat_1m', 83), 'no_fresh_bear5': not event(s, '5m', 'DN'),
                   'flow_up': up, 'cvd5_delta_positive': rising5, 'buyer_ratio_rising': gt(s, 'buyer_ratio_delta_1m', 0)},
            'H3': {'fresh_strong_confident_bos': setup3, 'fatigue_lt72': lt(s, 'fat_1m', 72),
                   'realf_40_60': between(s, 'realf_score', 40, 60), 'cvd1_positive': gt(s, 'cvd_1m', 0),
                   'cvd5_positive': gt(s, 'cvd_5m', 0), 'buyer_ratio_gt50': gt(s, 'buyer_ratio_1m', 50)},
            'H4': {'recent_exhaustion': exhausted, 'price_ahead': gt(s, 'realf_score', 58) or lt(s, 'realf_unpriced_flow', 0),
                   'fatigue_falling': lt(s, 'fatigue_delta_1m', 0), 'cvd1_delta_negative': lt(s, 'cvd_1m_delta', 0),
                   'flow_down': down, 'fresh_bear3_or5': any(event(s, tf, 'DN') for tf in ('3m', '5m'))},
            'H5': {'htf_bear': bear, 'recent_bounce': bounced, 'no_strong_positive_gap': u is not None and u <= .005,
                   'cvd5_negative': lt(s, 'cvd_5m', 0), 'flow_down': down, 'ltf_bear': any(state(s, tf, 'DN') for tf in ('1m', '3m'))},
            'H6': {'reset_1m3m5m': reset}, 'H7': {'fatigue_lt30': lt(s, 'fat_1m', 30), 'extension_history': bool(s.get('h7_features_ready'))},
        }
        requirements = {'H1': ('1m', '3m', '5m'), 'H2': ('1m', '5m'), 'H3': ('1m', '5m', '15m'), 'H4': ('1m', '3m', '5m'), 'H5': ('1m', '3m', '5m'), 'H6': ('1m', '3m', '5m'), 'H7': ('1m',)}
        for h, (raw, setup, armed, trigger) in stages.items():
            ready = all(s.get(f'fat_{tf}_ready') is True for tf in requirements[h])
            if h in ('H1', 'H2', 'H3', 'H4', 'H5'):
                ready = ready and s.get('realf_ready') is True
            eligible = valid and ready
            setup, armed, trigger = bool(setup and eligible), bool(armed and eligible), bool(trigger and eligible)
            ev = mem['events'].get(h)
            expires = max(ev['start'] + EVENT_MS, (ev['trigger_ms'] + EVENT_MS + 90_000) if ev['trigger_ms'] is not None else 0) if ev else 0
            new = False
            if setup and (ev is None or now > expires):
                ev = {'id': f"{s.get('run_id')}/{s['symbol']}/{h}/{now}", 'start': now, 'trigger_ms': None, 'price': None, 'follow': {}}
                mem['events'][h] = ev
                new = True
            if ev and now > expires and not setup:
                ev = None
                mem['events'].pop(h, None)
            pulse = bool(trigger and ev and ev['trigger_ms'] is None)
            if pulse:
                protected_type = 'HIGH' if h in ('H4', 'H5') else 'LOW'
                protected = number(s, 'str_1m_protected_level') if s.get('str_1m_protected_type') == protected_type else None
                ev.update(trigger_ms=now, price=s['price'], snapshot_id=s['snapshot_id'],
                          protected=protected, peak=0., trough=0., peak_ms=now, trough_ms=now, exit_candidates={})
            age = (now - ev['trigger_ms']) / 1000 if ev and ev['trigger_ms'] is not None else None
            prefix = f'shadow_{h}_'
            out.update({prefix+'hypothesis_id': h, prefix+'raw_candidate': bool(raw), prefix+'setup': setup,
                        prefix+'armed': armed, prefix+'trigger': pulse, prefix+'trigger_condition': trigger,
                        prefix+'event_group_id': ev['id'] if ev else None, prefix+'new_event': new,
                        prefix+'event_start_ms': ev['start'] if ev else None,
                        prefix+'trigger_age_sec': age, prefix+'eligible': eligible,
                        prefix+'blocked_reason': 'quality' if not valid else 'warmup' if not ready else 'setup' if not setup else 'armed' if not armed else 'trigger' if not trigger else 'already_triggered_group' if not pulse else '',
                        prefix+'missing_conditions': '|'.join(k for k, satisfied in components[h].items() if not satisfied),
                        prefix+'stage': 'TRIGGER' if pulse else 'ARMED' if armed else 'SETUP' if setup else 'RAW' if raw else 'NONE'})
            direction = -1 if h in ('H4', 'H5') else 1
            for minute in (1, 3, 5, 10, 20, 30, 60):
                if age is not None and age >= minute * 60 and minute not in ev['follow']:
                    ev['follow'][minute] = (direction * (s['price'] / ev['price'] - 1) * 100 if age <= minute * 60 + 90 and valid else None)
                out[prefix+f'post_trigger_followthrough_{minute}m'] = ev['follow'].get(minute) if ev else None
            out[prefix+'post_trigger_followthrough'] = out[prefix+'post_trigger_followthrough_5m']
            if age is not None and 'confirm5' not in ev and valid and direction * (number(s, 'cvd_5m') or 0) > 0:
                ev['confirm5'] = age
            out[prefix+'confirmation_5m_delay_sec'] = ev.get('confirm5') if ev else None
            out[prefix+'trigger_snapshot_id'] = ev.get('snapshot_id') if ev else None
            self._timing(s, ev, out, prefix, direction, valid)
        f5 = out['shadow_H4_post_trigger_followthrough_5m']
        out['shadow_H4_DECAY_5M'] = f5 <= 0 if f5 is not None else None
        out['shadow_H7_context'] = ('UNKNOWN' if not s.get('h7_features_ready') else 'PUMP' if gt(s, 'return_24h', 20) else 'NORMAL' if lt(s, 'return_24h', 5) else 'MID')

        # H6 conversions retain the reset id and link to the conversion snapshot's outcome.
        reset_ev = mem['events'].get('H6')
        for target in ('H1', 'H2'):
            cv = reset_ev.get(target) if reset_ev else None
            if reset_ev and not cv and out[f'shadow_{target}_setup']:
                cv = {'snapshot_id': s['snapshot_id'], 'delay_sec': (now - reset_ev['start']) / 1000}
                reset_ev[target] = cv
            out[f'shadow_H6_to_{target}_snapshot_id'] = cv['snapshot_id'] if cv else None
            out[f'shadow_H6_to_{target}_delay_sec'] = cv['delay_sec'] if cv else None

        self._breakout(s, mem, out, valid, up)
        self._alignment(s, mem, out, valid)
        return out

    @staticmethod
    def _timing(s, ev, out, prefix, direction, valid):
        """Observed paths and first causal exit candidates, never retrospective ideal exits."""
        active = ev is not None and ev['trigger_ms'] is not None
        now = s['captured_at_ms']
        ret = direction * (s['price'] / ev['price'] - 1) * 100 if active and valid else None
        opposite = 'UP' if direction < 0 else 'DN'
        if ret is not None:
            if ret > ev['peak']:
                ev['peak'], ev['peak_ms'] = ret, now
            if ret < ev['trough']:
                ev['trough'], ev['trough_ms'] = ret, now
        out.update({prefix+'setup_to_trigger_sec': (ev['trigger_ms'] - ev['start']) / 1000 if active else None,
                    prefix+'observed_return_pct': ret,
                    prefix+'observed_mfe_pct': ev['peak'] if active else None,
                    prefix+'observed_mae_pct': ev['trough'] if active else None,
                    prefix+'observed_giveback_pct': ev['peak'] - ret if ret is not None else None,
                    prefix+'observed_peak_delay_sec': (ev['peak_ms'] - ev['trigger_ms']) / 1000 if active else None,
                    prefix+'observed_trough_delay_sec': (ev['trough_ms'] - ev['trigger_ms']) / 1000 if active else None})
        flow = number(s, 'cvd_5m')
        gap = number(s, 'realf_unpriced_flow')
        level = ev.get('protected') if active else None
        candidates = {'structure_opposes': event(s, '1m', opposite),
                      'flow5_opposes': flow is not None and direction * flow < 0,
                      'gap_opposes': gap is not None and direction * gap < 0,
                      'protected_level_broken': level is not None and direction * (s['price'] - level) < 0}
        for name, present in candidates.items():
            seen = ev['exit_candidates'].get(name) if active else None
            if active and valid and now > ev['trigger_ms'] and present and seen is None:
                seen = {'ms': now, 'return_pct': ret, 'snapshot_id': s['snapshot_id']}
                ev['exit_candidates'][name] = seen
            out[prefix+name+'_now'] = bool(active and valid and present)
            out[prefix+name+'_first_delay_sec'] = (seen['ms'] - ev['trigger_ms']) / 1000 if seen else None
            out[prefix+name+'_first_return_pct'] = seen['return_pct'] if seen else None
            out[prefix+name+'_snapshot_id'] = seen['snapshot_id'] if seen else None

    @staticmethod
    def _alignment(s, mem, out, valid):
        def sign(value):
            return 'UNKNOWN' if value is None else 'UP' if value > 0 else 'DOWN' if value < 0 else 'FLAT'
        fields = {}
        for tf in ('1m', '5m', '15m', '1h', '4h'):
            fields['structure_'+tf] = ('UP' if state(s, tf, 'UP') else 'DOWN' if state(s, tf, 'DN') else
                                      'NEUTRAL' if s.get(f'str_{tf}_ready') else 'UNKNOWN')
        fields['realf_gap'] = sign(number(s, 'realf_unpriced_flow')) if s.get('realf_ready') else 'UNKNOWN'
        for tf in ('1m', '5m', '15m'):
            fields['flow_'+tf] = sign(number(s, 'cvd_'+tf)) if valid else 'UNKNOWN'
        pattern = '|'.join(f'{k}={v}' for k, v in fields.items())
        prior = mem.get('alignment')
        changed = prior is not None and prior['pattern'] != pattern
        if prior is None or changed:
            mem['alignment'] = {'pattern': pattern, 'since': s['captured_at_ms']}
        for name, value in fields.items():
            out['shadow_alignment_'+name] = value
        out.update(shadow_alignment_pattern=pattern, shadow_alignment_changed=changed,
                   shadow_alignment_duration_sec=(s['captured_at_ms'] - mem['alignment']['since']) / 1000,
                   shadow_alignment_previous=prior['pattern'] if changed else None)

    def _breakout(self, s, mem, out, valid, up):
        now = s['captured_at_ms']
        # Track a confirmed BOS event by source timestamp; repeated snapshots do not restart it.
        for tf in ('5m', '15m'):
            ts = number(s, f'str_{tf}_event_time_ms')
            identity = (tf, ts)
            if valid and s.get(f'str_{tf}_event') == 'BOS UP' and event(s, tf, 'UP') and ts is not None and identity != mem.get('last_bos'):
                prior = mem.get('breakout')
                if prior is None or ts > prior['event_ms']:
                    mem['last_bos'] = identity
                    mem['breakout'] = {'event_ms': ts, 'seen_ms': now, 'price': s['price'], 'low': s['price'],
                                       'protected': s.get(f'str_{tf}_protected_level'), 'retest': None, 'reaccel': None, 'invalid': False}
        b = mem.get('breakout')
        if b and now - b['seen_ms'] > 30 * 60_000:
            mem.pop('breakout', None)
            b = None
        if b and valid:
            b['low'] = min(b['low'], s['price'])
            delay = (now - b['seen_ms']) / 1000
            if (b['protected'] is not None and s['price'] < b['protected']) or event(s, '1m', 'DN'):
                b['invalid'] = True
            if valid and 120 <= delay <= 600 and s['price'] < b['price'] and b['retest'] is None:
                b['retest'] = now
            if (b['protected'] is not None and s.get('realf_ready') is True and s.get('fat_1m_ready') is True
                    and b['retest'] is not None and now > b['retest'] and b['reaccel'] is None and not b['invalid']
                    and between(s, 'realf_score', 40, 60) and lt(s, 'fat_1m', 72) and up
                    and (gt(s, 'cvd_5m', 0) or gt(s, 'cvd_5m_delta', 0))):
                b['reaccel'] = now
        out.update(shadow_H3_breakout_timestamp_ms=b['event_ms'] if b else None,
                   shadow_H3_breakout_observed_ms=b['seen_ms'] if b else None,
                   shadow_H3_retest_timestamp_ms=b['retest'] if b else None,
                   shadow_H3_retest_depth_pct=(b['price'] - b['low']) / b['price'] * 100 if b else None,
                   shadow_H3_protected_level_survived=not b['invalid'] if b and b['protected'] is not None else None,
                   shadow_H3_reacceleration_delay_sec=(b['reaccel'] - b['seen_ms']) / 1000 if b and b['reaccel'] else None,
                   shadow_H3_reaccel_trigger=bool(b and b['reaccel'] == now))
