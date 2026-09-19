"""Entry and exit plans per hypothesis, measured on the same events.

Every policy here is written down before it is measured and none of its numbers are
searched: a pullback is 0.25%, a confirmation is 3 minutes, a stall is 10 minutes
without a new favourable extreme. They exist because the observed shape said so -
the peak arrives around 30-42 minutes for the long families while the first opposing
flow signal arrives around minute 6, and coins here tend to rise and then go flat.

Fills are causal: a signal at t is filled at a later snapshot, never at t's own price,
and an event whose window is broken by a gap or a quality veto is censored, not zero.

Coins are not interchangeable, so every plan is also cut by coin class: size from the
run's own notional terciles, volatility from its own ATR median.
"""
import collections

import hypothesis_candidates as hc
import shadow_research as sh
from research_report import med

PULLBACK_PCT = 0.25      # how deep a retrace the patient entry waits for
PULLBACK_WINDOW_SEC = 600
CONFIRM_SEC = 180        # a late entry only fills if the move is still in its favour
STALL_MIN = 10           # no new favourable extreme for this long -> the move went flat
FOLLOW_MAX_MIN = 60

ENTRY_POLICIES = {
    'AT_TRIGGER': 'Tetikten sonraki ilk gözlemde dolum',
    f'PULLBACK_{int(PULLBACK_PCT * 100)}': f'Tetik fiyatından %{PULLBACK_PCT} geri çekilme beklenir '
                                           f'(en çok {PULLBACK_WINDOW_SEC // 60} dk), gelmezse işlem yok',
    'CONFIRM_3M': f'{CONFIRM_SEC // 60} dakika sonra fiyat hâlâ tetik lehineyse dolum, değilse işlem yok',
}
EXIT_POLICIES = {
    'HOLD_HORIZON': 'Karar ufkuna kadar tut',
    'PEAK_TIME': 'Ailenin ölçülen medyan tepe dakikasında çık',
    f'STALL_{STALL_MIN}M': f'{STALL_MIN} dakikadır yeni lehte uç yoksa çık (yükselip düzleşme)',
    'FLOW_STRUCTURE': 'İlk karşıt akış/yapı sinyalinde çık',
    'ATR_GIVEBACK': '1 ATR ilerledikten sonra 1 ATR geri verince çık',
}
BASELINE = ('AT_TRIGGER', 'HOLD_HORIZON')


def direction_of(variant):
    return -1 if variant.startswith(('H4', 'H5')) else 1


def coin_classes(rows):
    """Size and volatility classes from this run's own symbols, not from outside data."""
    per = collections.defaultdict(lambda: {'notional': [], 'atr': []})
    for s in rows:
        if isinstance(s.get('notional_5m'), (int, float)):
            per[s['symbol']]['notional'].append(s['notional_5m'])
        if isinstance(s.get('str_1m_atr_pct'), (int, float)):
            per[s['symbol']]['atr'].append(s['str_1m_atr_pct'])
    stats = {symbol: {'notional': med(v['notional']), 'atr': med(v['atr'])} for symbol, v in per.items()}
    sized = sorted((v['notional'] or 0, symbol) for symbol, v in stats.items())  # 5 dk gercek $ hacmi
    third = max(1, len(sized) // 3)
    size_label = {}
    for index, (_, symbol) in enumerate(sized):
        size_label[symbol] = 'KUCUK' if index < third else ('ORTA' if index < 2 * third else 'BUYUK')
    atr_values = sorted(v['atr'] for v in stats.values() if v['atr'] is not None)
    cut = atr_values[len(atr_values) // 2] if atr_values else 0
    out = {}
    for symbol, values in stats.items():
        volatility = 'OYNAK' if (values['atr'] or 0) > cut else 'SAKIN'
        out[symbol] = {'symbol': symbol, 'size': size_label[symbol], 'volatility': volatility,
                       'class': f'{size_label[symbol]}/{volatility}',
                       'median_notional_usd_5m': values['notional'], 'median_atr_pct': values['atr']}
    return out, cut


def fill(entry, following, policy, direction):
    """Where this plan actually gets in. None means the plan skipped the event."""
    trigger_price, t0 = entry['price'], entry['captured_at_ms']
    last = t0
    for s in following:
        now = s['captured_at_ms']
        if now - last > sh.GAP_MS or sh.quality(s):
            return None
        last = now
        delay, move = (now - t0) / 1000, direction * (s['price'] / trigger_price - 1) * 100
        if policy == 'AT_TRIGGER':
            return s, delay
        if policy.startswith('PULLBACK'):
            if delay > PULLBACK_WINDOW_SEC:
                return None
            if move <= -PULLBACK_PCT:
                return s, delay
        elif policy == 'CONFIRM_3M':
            if delay >= CONFIRM_SEC:
                return (s, delay) if move > 0 else None
    return None


def plan_path(entry, following, entry_policy, exit_policy, horizon, peak_min, cost_bps):
    """One event under one plan: fill, then exit, then the net result after cost."""
    direction = direction_of(entry['variant'])
    filled = fill(entry, following, entry_policy, direction)
    if filled is None:
        return {'filled': False}
    fill_snapshot, fill_delay = filled
    start, fill_price = fill_snapshot['captured_at_ms'], fill_snapshot['price']
    end = start + horizon * 60_000
    rest = [s for s in following if s['captured_at_ms'] > start]
    last, peak, peak_at, pending = start, 0., start, None
    for s in rest:
        now = s['captured_at_ms']
        if now > end + 90_000:
            break
        if now - last > sh.GAP_MS or sh.quality(s):
            return None
        last = now
        ret = direction * (s['price'] / fill_price - 1) * 100
        delay = (now - start) / 1000
        if pending is not None:  # a signal at the previous snapshot fills here
            return {'filled': True, 'net_pct': ret - cost_bps / 100, 'exit_delay_sec': delay,
                    'fill_delay_sec': fill_delay, 'reason': pending}
        if ret > peak:
            peak, peak_at = ret, now
        if now >= end:
            return {'filled': True, 'net_pct': ret - cost_bps / 100, 'exit_delay_sec': delay,
                    'fill_delay_sec': fill_delay, 'reason': 'HORIZON'}
        if exit_policy == 'PEAK_TIME' and peak_min and delay >= peak_min * 60:
            return {'filled': True, 'net_pct': ret - cost_bps / 100, 'exit_delay_sec': delay,
                    'fill_delay_sec': fill_delay, 'reason': 'PEAK_TIME'}
        if exit_policy.startswith('STALL') and now - peak_at >= STALL_MIN * 60_000:
            return {'filled': True, 'net_pct': ret - cost_bps / 100, 'exit_delay_sec': delay,
                    'fill_delay_sec': fill_delay, 'reason': 'STALL'}
        if exit_policy in ('FLOW_STRUCTURE', 'ATR_GIVEBACK') and delay >= 60 and hc.exit_condition(
                exit_policy, s, direction, peak, ret, entry.get('str_1m_atr_pct')):
            pending = exit_policy
    return None


def build(rows, by_symbol, times, events, character, cost_bps):
    """Grid of entry x exit per candidate, plus the coin-class cut of the base plan."""
    import bisect
    classes, atr_cut = coin_classes(rows)
    peak_by_variant = {c['variant']: c['peak_delay_min_median'] for c in character if c['split'] == 'ALL'}
    plan_events, per_event = [], collections.defaultdict(dict)
    for entry in events:
        variant = entry['variant']
        if variant.startswith(hc.SCANNER if hasattr(hc, 'SCANNER') else ('H6', 'H7')):
            continue
        symbol = entry['symbol']
        index = bisect.bisect_right(times[symbol], entry['captured_at_ms'])
        following = by_symbol[symbol][index:]
        horizon = hc.decision_horizon(variant)
        peak_min = peak_by_variant.get(variant)
        for entry_policy in ENTRY_POLICIES:
            for exit_policy in EXIT_POLICIES:
                result = plan_path(entry, following, entry_policy, exit_policy, horizon, peak_min, cost_bps)
                row = {'variant': variant, 'snapshot_id': entry['snapshot_id'], 'symbol': symbol,
                       'coin_class': classes.get(symbol, {}).get('class'), 'split': entry['split'],
                       'entry_policy': entry_policy, 'exit_policy': exit_policy, 'horizon': horizon,
                       'censored': result is None, **(result or {})}
                plan_events.append(row)
                if result and result.get('filled'):
                    per_event[(variant, entry['snapshot_id'])][(entry_policy, exit_policy)] = result['net_pct']
    summary = []
    for variant in sorted({r['variant'] for r in plan_events}):
        for split in ('ALL', 'TRAIN', 'HOLDOUT'):
            for entry_policy in ENTRY_POLICIES:
                for exit_policy in EXIT_POLICIES:
                    group = [r for r in plan_events if r['variant'] == variant and r['entry_policy'] == entry_policy
                             and r['exit_policy'] == exit_policy and (split == 'ALL' or r['split'] == split)]
                    if not group:
                        continue
                    done = [r for r in group if r.get('filled') and not r['censored']]
                    nets = [r['net_pct'] for r in done]
                    paired = [nets_by[(entry_policy, exit_policy)] - nets_by[BASELINE]
                              for key, nets_by in per_event.items() if key[0] == variant
                              and BASELINE in nets_by and (entry_policy, exit_policy) in nets_by
                              and (split == 'ALL' or any(r['split'] == split and r['snapshot_id'] == key[1]
                                                         for r in group))]
                    summary.append({'variant': variant, 'split': split, 'entry_policy': entry_policy,
                                    'exit_policy': exit_policy, 'events': len(group), 'filled': len(done),
                                    'fill_pct': round(100 * len(done) / len(group), 1) if group else None,
                                    'net_median': med(nets),
                                    'hit_pct': round(100 * sum(v > 0 for v in nets) / len(nets), 1) if nets else None,
                                    'exit_delay_min_median': med(r['exit_delay_sec'] / 60 for r in done),
                                    'paired_vs_baseline_median': med(paired), 'paired_n': len(paired)})
    class_summary = []
    for variant in sorted({r['variant'] for r in plan_events}):
        for label in sorted({c['class'] for c in classes.values()}):
            group = [r for r in plan_events if r['variant'] == variant and r['coin_class'] == label
                     and r['entry_policy'] == BASELINE[0] and r['exit_policy'] == BASELINE[1]]
            done = [r for r in group if r.get('filled') and not r['censored']]
            if not group:
                continue
            nets = [r['net_pct'] for r in done]
            class_summary.append({'variant': variant, 'coin_class': label, 'events': len(group),
                                  'filled': len(done), 'net_median': med(nets),
                                  'hit_pct': round(100 * sum(v > 0 for v in nets) / len(nets), 1) if nets else None,
                                  'symbols': len({r['symbol'] for r in group})})
    return plan_events, summary, class_summary, list(classes.values()), atr_cut


def best_plan(summary, variant, split='ALL', minimum=8):
    """The plan with the best paired improvement, only when enough pairs back it."""
    rows = [r for r in summary if r['variant'] == variant and r['split'] == split
            and r['paired_n'] >= minimum and r['paired_vs_baseline_median'] is not None]
    return max(rows, key=lambda r: r['paired_vs_baseline_median']) if rows else None


def render_plan(summary, class_summary, classes, atr_cut):
    lines = ['# Giriş / çıkış planı ve coin sınıfı', '',
             'Politikalar ölçümden önce yazıldı ve hiçbir sayısı aranmadı: geri çekilme %0.25, teyit 3 dk, '
             f'durgunluk {STALL_MIN} dk. Dolum her zaman sinyalden SONRAKİ gözlemde olur.', '',
             '## Politikalar', '']
    for name, text in list(ENTRY_POLICIES.items()) + list(EXIT_POLICIES.items()):
        lines.append(f'- **{name}** — {text}')
    lines += ['', '## Aday başına en iyi eşleşmiş plan', '',
              'Eşleşmiş fark: aynı olayda plan ile taban planın (AT_TRIGGER + HOLD_HORIZON) net farkı. '
              'En az 8 eşleşme istenir; altındaki satırlar rapor edilmez.', '',
              '| Aday | Plan | Eşleşme | Taban farkı (medyan) | Dolum % | İsabet % | Çıkış dk |',
              '|---|---|---:|---:|---:|---:|---:|']
    for variant in sorted({r['variant'] for r in summary}):
        best = best_plan(summary, variant)
        base = next((r for r in summary if r['variant'] == variant and r['split'] == 'ALL'
                     and (r['entry_policy'], r['exit_policy']) == BASELINE), None)
        if not best or not base:
            continue
        mark = '' if best['paired_vs_baseline_median'] > 0 else ' (taban daha iyi)'
        plan = f"{best['entry_policy']} + {best['exit_policy']}"
        lines.append(f"| {variant} | {plan}{mark} | {best['paired_n']} | "
                     f"{best['paired_vs_baseline_median']:+.3f} | {best['fill_pct']} | {best['hit_pct']} | "
                     f"{best['exit_delay_min_median']} |")
    lines += ['', '## Coin sınıfları', '',
              f'Büyüklük bu runın kendi 5 dakikalık $ hacmi üçlüklerinden, oynaklık kendi ATR medyanından '
              f'(%{atr_cut:.3f}) türer; dışarıdan piyasa değeri kullanılmaz.', '',
              '| Coin | Sınıf | Medyan 5m hacim $ | Medyan 1m ATR % |', '|---|---|---:|---:|']
    for row in sorted(classes, key=lambda c: -(c['median_notional_usd_5m'] or 0)):
        lines.append(f"| {row['symbol']} | {row['class']} | {row['median_notional_usd_5m']:,.0f} | {row['median_atr_pct']} |")
    lines += ['', '## Aday x coin sınıfı (taban plan)', '',
              'Aynı hipotez her coinde aynı şeyi yapmıyor; satırlar taban planla ölçüldü.', '',
              '| Aday | Sınıf | Coin | Olay | Dolum | Net medyan % | İsabet % |', '|---|---|---:|---:|---:|---:|---:|']
    for row in class_summary:
        if not row['filled']:
            continue
        lines.append(f"| {row['variant']} | {row['coin_class']} | {row['symbols']} | {row['events']} | "
                     f"{row['filled']} | {row['net_median']} | {row['hit_pct']} |")
    lines += ['', 'Sınırlar: tek gün, tek rejim; sınıf başına örneklem küçük. Dolum gözlenen snapshot fiyatıdır, '
              'gerçek emir defteri değildir. Bu tablo işlem kuralı değil, plan karşılaştırmasıdır.', '']
    return '\n'.join(lines)
