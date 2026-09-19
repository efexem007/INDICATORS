"""Reproducible shadow replay, data audit, event/FP/FN/segment/benchmark exports.

Usage: python research_report.py logs/run_... --fetch-history
Network data is public historical candles only; raw snapshots are never rewritten.
"""
import argparse
import bisect
import collections
import csv
import hashlib
import json
from pathlib import Path
import statistics

import tracker_v2 as tv
import shadow_research as sh


def read_jsonl(paths):
    """A killed writer leaves its last row half written; that is an interrupted write,
    not corruption. Only the final line of the newest file may be dropped this way, it
    is reported as a truncated tail, and every other bad line still stops the run."""
    rows, errors, truncated = [], [], []
    for path in paths:
        text = path.read_text(encoding='utf-8')
        lines = text.split('\n')
        tail_open = bool(lines) and lines[-1] != '' and path == paths[-1]
        if lines and lines[-1] == '':
            lines.pop()
        for line_no, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                if tail_open and line_no == len(lines):
                    truncated.append(f'{path.name}:{line_no}')
                else:
                    errors.append(f'{path.name}:{line_no}')
    return rows, errors, truncated


def dump_csv(path, rows):
    columns = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=columns or ['no_events'])
        w.writeheader()
        w.writerows(rows)


def med(values):
    values = [v for v in values if v is not None]
    return round(statistics.median(values), 4) if values else None


def history(symbol, interval, start, end, cache, fetch):
    step = 60_000 if interval == '1m' else 3_600_000
    start = start // step * step
    name = cache / f'{symbol}_{interval}_{start}_{end}.json'
    if name.exists():
        return json.loads(name.read_text(encoding='utf-8'))
    if not fetch:
        return []
    bars, cursor = [], start
    while cursor < end:
        data = tv.http_get_json(f'{tv.BINANCE_FAPI}/fapi/v1/klines?symbol={symbol}&interval={interval}&startTime={cursor}&endTime={end}&limit=1000')
        if not data:
            break
        bars.extend([int(k[0]), *map(float, k[1:5])] for k in data)
        nxt = int(data[-1][0]) + step
        if nxt <= cursor:
            raise ValueError('non-progressing historical response')
        cursor = nxt
        if len(data) < 1000:
            break
    name.write_text(json.dumps(bars), encoding='utf-8')
    return bars


def candles(bars):
    return {'time': [b[0] / 1000 for b in bars], 'open': [b[1] for b in bars], 'low': [b[3] for b in bars], 'close': [b[4] for b in bars]}


def segment(s):
    rank = s.get('coin_rank')
    cap = 'UNKNOWN' if not rank else 'TOP20' if rank <= 20 else 'TOP100' if rank <= 100 else 'OUTSIDE100'
    if s.get('coin_class') == 'OUTSIDE100':
        cap = 'OUTSIDE100'
    return {'cap': cap, 'regime': s.get('str_15m_regime', 'UNKNOWN'),
            'rvol': 'UNKNOWN' if sh.number(s, 'realf_rvol') is None else 'HIGH' if s['realf_rvol'] >= 1 else 'LOW',
            'htf': s.get('shadow_htf_context', 'UNKNOWN'), 'pump': s.get('shadow_H7_context', 'UNKNOWN')}


def warnings(s, hypothesis=None):
    reasons = []
    short = hypothesis in ('H4', 'H5')
    if short:
        if sh.gt(s, 'unpriced_d3', 0): reasons.append('gap_expanding')
        if sh.gt(s, 'cvd_5m', 0): reasons.append('cvd5_positive')
        if sh.lt(s, 'fat_1m', 30): reasons.append('fatigue_rested')
    else:
        if sh.lt(s, 'unpriced_d3', 0): reasons.append('gap_contracting')
        if sh.lt(s, 'cvd_5m', 0): reasons.append('cvd5_negative')
        if sh.gt(s, 'fat_1m', 83): reasons.append('fatigue_extreme')
    if sh.gt(s, 'return_24h', 20): reasons.append('pump_24h')
    if not sh.ob_valid(s): reasons.append('orderbook_unusable')
    elif short and sh.gt(s, 'orderbook_imbalance', 0): reasons.append('orderbook_buy_pressure')
    elif not short and sh.lt(s, 'orderbook_imbalance', 0): reasons.append('orderbook_sell_pressure')
    if sh.lt(s, 'realf_beta_r2', .45): reasons.append('r2_low')
    return '|'.join(reasons) or 'no_predefined_warning'


def analyze(run, fetch=False, cost_bps=10):
    run = Path(run)
    output = run / 'research_shadow_v1'
    cache = output / 'historical_cache'
    paths = sorted(run.glob('snapshots_*.jsonl')) or [run / 'snapshots.jsonl']
    raw, parse_errors, truncated_tail = read_jsonl(paths)
    raw.sort(key=lambda s: (s['captured_at_ms'], s['snapshot_id']))
    unique = {s['snapshot_id']: s for s in raw}
    snapshots = sorted(unique.values(), key=lambda s: (s['captured_at_ms'], s['snapshot_id']))
    if not snapshots:
        raise ValueError('No snapshots')
    if parse_errors:
        raise ValueError(f'Bozuk snapshot satırları var: {parse_errors[:5]}; önce veri bütünlüğünü düzeltin.')
    tv.validate_snapshot_inventory(str(run), len(snapshots))
    output.mkdir(exist_ok=True)
    cache.mkdir(exist_ok=True)
    outcome_rows, outcome_errors, outcome_tail = (read_jsonl([run / 'outcomes.jsonl'])
                                                  if (run / 'outcomes.jsonl').exists() else ([], [], []))
    outcomes = {o['snapshot_id']: o for o in outcome_rows if o.get('outcome_complete') and o['snapshot_id'] in unique}
    symbols = sorted({s['symbol'] for s in snapshots if s.get('provider') == 'BINANCE'})
    start = min(s['kline_asof_ms'] for s in snapshots)
    end = max(s['kline_asof_ms'] for s in snapshots)
    minutes, hours, network_errors = {}, {}, {}
    for symbol in sorted(set(symbols) | {'BTCUSDT', 'ETHUSDT'}):
        print(f'  History: {symbol}', flush=True)
        try:
            minutes[symbol] = history(symbol, '1m', start - 61 * 60_000, end + 62 * 60_000, cache, fetch)
            if symbol in symbols:
                hours[symbol] = history(symbol, '1h', start - 169 * 3_600_000, end, cache, fetch)
        except Exception as e:
            network_errors[symbol] = f'{type(e).__name__}: {e}'
    minute_indexes = {symbol: {b[0]: b for b in bars} for symbol, bars in minutes.items()}
    minute_times = {symbol: [b[0] for b in bars] for symbol, bars in minutes.items()}
    tracker = sh.ShadowTracker()
    replay, events, last_independent, gaps = [], [], {}, []
    previous = {}
    cutoff = start + int((end - start) * .7)
    benchmark_cache = {}

    def benchmark(symbols_for_basket, t0, horizon):
        values = []
        for symbol in symbols_for_basket:
            idx = minute_indexes.get(symbol, {})
            entry = idx.get(t0 // 60_000 * 60_000)
            exit_ms = (t0 + horizon * 60_000 + 30_000) // 60_000 * 60_000 - 60_000
            exit_bar = idx.get(exit_ms)
            if entry and exit_bar and entry[1] > 0:
                values.append((exit_bar[4] / entry[1] - 1) * 100)
        return (sum(values) / len(values), len(values)) if values else (None, 0)

    for original in snapshots:
        s = dict(original)
        symbol, t0 = s['symbol'], s['kline_asof_ms']
        prior = previous.get(symbol)
        if prior and s['captured_at_ms'] - prior > sh.GAP_MS:
            gaps.append({'symbol': symbol, 'start_ms': prior, 'end_ms': s['captured_at_ms'], 'reason': 'observation_gap'})
        previous[symbol] = s['captured_at_ms']
        if not s.get('h7_features_ready'):
            bars = minutes.get(symbol, [])
            stop = bisect.bisect_right(minute_times.get(symbol, []), t0 - 60_000)
            s.update(sh.extension_features(candles(bars[max(0, stop-60):stop]), candles(hours.get(symbol, [])), s['price'], t0, s.get('str_1m_atr_pct')))
            s['extension_reconstructed'] = True
        s.update(tracker.update(s))
        s.update(outcomes.get(s['snapshot_id'], {}))
        s['split'] = 'TRAIN' if t0 + 60 * 60_000 < cutoff else 'HOLDOUT' if t0 >= cutoff else 'PURGED'
        for h in tv.HORIZONS_MIN:
            # One common time grid per minute avoids repeated basket work.
            cache_key = (symbol, t0 // 60_000, int(t0 % 60_000 >= 30_000), h)
            if cache_key not in benchmark_cache:
                basket = [sym for sym in symbols if sym != symbol]
                value, n = benchmark(basket, t0, h)
                liquid, liquid_n = benchmark(('BTCUSDT', 'ETHUSDT'), t0, h)
                benchmark_cache[cache_key] = (value if n == len(basket) and n else None, n,
                                             liquid if liquid_n == 2 else None)
            value, n, liquid = benchmark_cache[cache_key]
            s[f'market_ret_{h}m'], s[f'market_n_{h}m'], s[f'btc_eth_ret_{h}m'] = value, n, liquid
            actual = s.get(f'fwd_ret_{h}m')
            s[f'excess_ret_{h}m'] = actual - value if actual is not None and value is not None else None
        replay.append(s)
        for hyp in sh.HYPOTHESES:
            selected = s[f'shadow_{hyp}_trigger'] or (hyp == 'H6' and s[f'shadow_{hyp}_new_event'])
            if not selected or t0 - last_independent.get((symbol, hyp), -10**20) < sh.EVENT_MS:
                continue
            last_independent[symbol, hyp] = t0
            direction = -1 if hyp in ('H4', 'H5') else 1
            e = {'snapshot_id': s['snapshot_id'], 'symbol': symbol, 'hypothesis': hyp,
                 'event_group_id': s[f'shadow_{hyp}_event_group_id'], 't0_ms': t0, 'split': s['split'],
                 'outcome_complete': bool(s.get('outcome_complete')), 'warnings': warnings(s, hyp), **segment(s)}
            for horizon in tv.HORIZONS_MIN:
                ret, excess = s.get(f'fwd_ret_{horizon}m'), s.get(f'excess_ret_{horizon}m')
                e[f'directional_{horizon}m'] = direction * ret if ret is not None else None
                e[f'net_{horizon}m'] = direction * ret - cost_bps / 100 if ret is not None else None
                e[f'excess_{horizon}m'] = direction * excess if excess is not None else None
            for horizon in tv.EXCURSION_MIN:
                e[f'mfe_{horizon}m'] = s.get(f'mfe_{horizon}m') if direction == 1 else (-s[f'mae_{horizon}m'] if s.get(f'mae_{horizon}m') is not None else None)
                e[f'mae_{horizon}m'] = s.get(f'mae_{horizon}m') if direction == 1 else (-s[f'mfe_{horizon}m'] if s.get(f'mfe_{horizon}m') is not None else None)
            events.append(e)
    meta = json.loads((run / 'run_meta.json').read_text(encoding='utf-8')) if (run / 'run_meta.json').exists() else {}
    last_update = meta.get('stopped_at_ms') or meta.get('updated_at_ms', end)
    for symbol, last in previous.items():
        if last_update - last > sh.GAP_MS:
            gaps.append({'symbol': symbol, 'start_ms': last, 'end_ms': last_update, 'reason': 'trailing_no_observations'})

    # False negatives: outcomes select cases; input features/explanations remain pre-outcome.
    false_negative, last_miss, recent_triggers = [], {}, {}
    for s in replay:
        symbol, now = s['symbol'], s['captured_at_ms']
        if any(s[f'shadow_{h}_trigger'] for h in ('H1', 'H2', 'H3')) or s['shadow_H3_reaccel_trigger']:
            recent_triggers[symbol] = now
        large = sh.gt(s, 'fwd_ret_20m', 1) or sh.gt(s, 'fwd_ret_60m', 2)
        missed = now - recent_triggers.get(symbol, -10**20) > 20 * 60_000
        if large and missed and now - last_miss.get(symbol, -10**20) >= sh.EVENT_MS:
            last_miss[symbol] = now
            false_negative.append({'snapshot_id': s['snapshot_id'], 'symbol': symbol, 't0_ms': s['kline_asof_ms'],
                                   'return_20m': s.get('fwd_ret_20m'), 'return_60m': s.get('fwd_ret_60m'),
                                   'quality': s['shadow_quality_veto'], 'warnings': warnings(s),
                                   **{h: s[f'shadow_{h}_blocked_reason'] if h not in ('H6', 'H7') else s[f'shadow_{h}_stage'] for h in sh.HYPOTHESES},
                                   **{h+'_missing_conditions': s[f'shadow_{h}_missing_conditions'] for h in sh.HYPOTHESES}})
    false_positive = [e for e in events if e['hypothesis'] not in ('H6', 'H7') and e['net_5m'] is not None and e['net_5m'] <= 0]
    filters = []
    for hyp in ('H1', 'H2', 'H3', 'H4', 'H5'):
        for split in ('ALL', 'TRAIN', 'HOLDOUT'):
            group = [e for e in events if e['hypothesis'] == hyp and e['net_5m'] is not None and (split == 'ALL' or e['split'] == split)]
            tags = sorted({tag for e in group for tag in e['warnings'].split('|') if tag != 'no_predefined_warning'})
            for tag in tags:
                removed = [e for e in group if tag in e['warnings'].split('|')]
                retained = [e for e in group if tag not in e['warnings'].split('|')]
                filters.append({'hypothesis': hyp, 'split': split, 'candidate_veto': tag, 'original_n': len(group),
                                'failures_removed': sum(e['net_5m'] <= 0 for e in removed),
                                'winners_removed': sum(e['net_5m'] > 0 for e in removed), 'retained_n': len(retained),
                                'original_net5_median': med(e['net_5m'] for e in group),
                                'retained_net5_median': med(e['net_5m'] for e in retained)})
    summaries = []
    for hyp in sh.HYPOTHESES:
        group = [e for e in events if e['hypothesis'] == hyp]
        for split in ('ALL', 'TRAIN', 'HOLDOUT'):
            selected = [e for e in group if split == 'ALL' or e['split'] == split]
            row = {'hypothesis': hyp, 'split': split, 'events': len(selected), 'complete': sum(e['outcome_complete'] for e in selected)}
            for horizon in (5, 20, 60):
                for name in ('directional', 'net', 'excess'):
                    row[f'{name}_{horizon}m_median'] = med(e[f'{name}_{horizon}m'] for e in selected)
            summaries.append(row)
    segments = []
    for hyp in sh.HYPOTHESES:
        group = [e for e in events if e['hypothesis'] == hyp]
        for dimension in ('cap', 'regime', 'rvol', 'htf', 'pump'):
            for value in sorted({str(e[dimension]) for e in group}):
                sub = [e for e in group if str(e[dimension]) == value]
                segments.append({'hypothesis': hyp, 'dimension': dimension, 'value': value, 'n': len(sub),
                                 'status': 'INSUFFICIENT' if len(sub) < 30 else 'SINGLE_RUN_ONLY',
                                 'net_20m_median': med(e['net_20m'] for e in sub), 'excess_20m_median': med(e['excess_20m'] for e in sub)})
    conversions = {}
    for s in replay:
        group = s['shadow_H6_event_group_id']
        if not group: continue
        record = conversions.setdefault(group, {'reset_group_id': group, 'symbol': s['symbol'],
                                               'reset_start_ms': s['shadow_H6_event_start_ms']})
        record['last_observed_ms'] = s['captured_at_ms']
        for target in ('H1', 'H2'):
            sid = s[f'shadow_H6_to_{target}_snapshot_id']
            if sid:
                record[target+'_snapshot_id'] = sid
                record[target+'_delay_sec'] = s[f'shadow_H6_to_{target}_delay_sec']
                record[target+'_timing'] = 'CONCURRENT' if record[target+'_delay_sec'] == 0 else 'LATER'
                for h in (5, 20, 60): record[target+f'_return_{h}m'] = outcomes.get(sid, {}).get(f'fwd_ret_{h}m')
    for record in conversions.values():
        record['full_window_observed'] = record['last_observed_ms'] - record['reset_start_ms'] >= sh.EVENT_MS - sh.GAP_MS
        for target in ('H1', 'H2'):
            record[target+'_censored'] = not record['full_window_observed'] and not record.get(target+'_snapshot_id')
    timing = {}
    alignment = []
    for s in replay:
        if s['shadow_alignment_changed']:
            alignment.append({'snapshot_id': s['snapshot_id'], 'symbol': s['symbol'], 'observed_ms': s['captured_at_ms'],
                              'previous_pattern': s['shadow_alignment_previous'], 'pattern': s['shadow_alignment_pattern'],
                              'quality_veto': s['shadow_quality_veto'],
                              **{f'return_{h}m': s.get(f'fwd_ret_{h}m') for h in (5, 20, 60)}})
        for hyp in ('H1', 'H2', 'H3', 'H4', 'H5'):
            prefix = f'shadow_{hyp}_'
            sid = s[prefix+'trigger_snapshot_id']
            if not sid:
                continue
            key = (hyp, sid)
            row = timing.setdefault(key, {'hypothesis': hyp, 'trigger_snapshot_id': sid, 'symbol': s['symbol']})
            row['last_observed_ms'] = s['captured_at_ms']
            row['full_60m_observed'] = s[prefix+'trigger_age_sec'] >= 3600
            row.update({k[len(prefix):]: v for k, v in s.items() if k.startswith(prefix) and
                        any(part in k for part in ('observed_', 'first_delay_sec', 'first_return_pct',
                                                   'setup_to_trigger', 'post_trigger_followthrough', 'confirmation_5m', 'event_group_id'))})
    funnel = {h: {stage: sum(bool(s[f'shadow_{h}_{stage}']) for s in replay) for stage in ('raw_candidate', 'setup', 'armed', 'trigger')} for h in sh.HYPOTHESES}
    audit = {'schema': sh.VERSION, 'snapshots': len(raw), 'unique': len(unique), 'duplicates': len(raw) - len(unique),
             'parse_errors': parse_errors, 'truncated_tail': truncated_tail + outcome_tail, 'outcome_parse_errors': outcome_errors, 'complete_outcomes': len(outcomes),
             'missing_outcomes': len(unique) - len(outcomes), 'cycle_errors': meta.get('cycle_errors'),
             'ob_null': sum(s.get('orderbook_imbalance') is None for s in raw), 'ob_stale': sum(bool(s.get('ob_stale')) for s in raw),
             'sync_errors': sum(bool(s.get('sync_error')) for s in raw), 'quality_vetoed': sum(bool(s['shadow_quality_veto']) for s in replay),
             'extension_ready': sum(bool(s.get('h7_features_ready')) for s in replay), 'history_errors': network_errors,
             'funnel_snapshot_counts': funnel, 'cost_bps_roundtrip': cost_bps, 'holdout_start_ms': cutoff,
             'false_positive_count': len(false_positive), 'false_negative_count': len(false_negative),
             'snapshot_hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
             'research_code_hashes': {p: hashlib.sha256(Path(__file__).with_name(p).read_bytes()).hexdigest() for p in ('shadow_research.py', 'research_report.py')},
             'history_hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(cache.glob('*.json'))}}
    (output / 'audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    for name, rows in (('events', events), ('false_positives', false_positive), ('false_negatives', false_negative),
                       ('segments', segments), ('summary', summaries), ('conversions', list(conversions.values())), ('excluded_intervals', gaps),
                       ('filter_candidates', filters), ('entry_exit_timing', list(timing.values())),
                       ('alignment_transitions', alignment)):
        dump_csv(output / f'{name}.csv', rows)
    scalar_rows = [{k: v for k, v in s.items() if not isinstance(v, (list, dict))} for s in replay]
    dump_csv(output / 'replay_with_outcomes.csv', scalar_rows)
    lines = ['# Shadow araştırma denetimi', '', f"Run: `{run.name}` · kurallar: `{sh.VERSION}` · yalnız araştırma.", '',
             f"Snapshot {len(raw)}; benzersiz {len(unique)}; complete outcome {len(outcomes)}; eksik {len(unique)-len(outcomes)}.",
             f"Bozuk JSONL {len(parse_errors)}; outcome parse hatası {len(outcome_errors)}; kalite nedeniyle veto {audit['quality_vetoed']}.",
             f"Orderbook null {audit['ob_null']}; stale {audit['ob_stale']}; sync hata {audit['sync_errors']}; cycle_errors {meta.get('cycle_errors')}.",
             f"H7 geçmiş mumlarla yeniden hesaplanabilen: {audit['extension_ready']}/{len(replay)}. Tarihsel veri hataları: {len(network_errors)}.", '',
             '## Yöntem ve sınırlar', '',
             '- Ham snapshotlar korunur; replay ayrı dosyadır. Eski rapordaki elle operationalize edilmiş varyantlar ile shadow-v1 aynı deney değildir.',
             '- Olaylar aynı coin/hipotez için en az 60 dakika aralıklı seçilir. Coinler arası piyasa bağımlılığı devam eder; bağımsızlık kanıtı değildir.',
             '- TRAIN ilk %70 zaman; HOLDOUT son %30 zaman. TRAIN sonuçları holdout başlangıcına taşarsa PURGED. Aynı gün holdout yeni gün/OOS kanıtı değildir.',
             f'- Net getiri için toplam {cost_bps} bps komisyon+slippage varsayımı; gerçekleşen işlem maliyeti değildir. Brüt, net ve excess ayrı sütunlardır.',
             '- Benchmark: izlenen coinlerin kendisi hariç eşit ağırlıklı sepeti; tüm piyasa endeksi değildir. Sepetin tamamı yoksa null. BTC/ETH eşit ağırlıklı referans da replay içinde.',
             '- Benchmark giriş fiyatı t0 dakikasının açılışıdır; snapshot fiyatıyla 0–60 sn zaman farkı vardır. Çıkışlar aynı ufuk kapanışına hizalıdır; sonuçlar yaklaşık excess returndür.',
             '- H7 getirileri geçmiş saatlik açılışa göre (hedefte <60 dk yuvarlama); local base son 60 kapalı 1m mumun dibidir. Gelecek mumlar özelliklere girmez.',
             '- Orderbook kullanılan varyantlarda shadow_ob_valid zorunludur. Temel aşamalar orderbook gerektirmez.',
             '- H6 tarayıcı, H7 context filtresidir; ikisi de giriş tetiği üretmez. H6 olay getirileri varsayımsal long izleme sonucudur.',
             '- Shadow-v1 akış tetik varyantı mevcut 3m CVD dönüş/eğim + 1m delta kullanır. Ayrı shadow_cvd_turn_1m gerçek ardışık 1m yön dönüşünü kaydeder; iki alan karıştırılmaz.',
             '- +2h/+4h opsiyonel ve bu sürümde yok. Veri olmayan kesintiler doldurulmuş gözlem sayılmaz.', '',
             '## Giriş / takip / çıkış araştırma verisi', '',
             'entry_exit_timing.csv tetik başına setup→trigger gecikmesi, gözlenen MFE/MAE, geri verilen kazanç, 1–60m takip ve ilk karşıt yapı/akış/gap/protected-level olayını içerir. Bunlar otomatik çıkış talimatı değildir.',
             'alignment_transitions.csv Structure (1m/5m/15m/1h/4h), REALF gap ve gerçek flow yönlerinin birleşimi değiştiğinde önceki/yeni durumu kaydeder. Fatigue yön oyu olarak kullanılmaz; kendi context alanlarında kalır.',
             'Gözlenen MFE/MAE snapshot fiyatlarından ölçülür; gerçek ara-dakika tepe/dip değildir. Tam 60m gözlenememiş olaylar ayrıca işaretlidir. Sonradan görülen tepe bir giriş/çıkış sinyali olarak kullanılmaz.', '',
             '## Aşama sayıları (snapshot sayısı)', '', '| H | Raw | Setup | Armed | Trigger |', '|---|---:|---:|---:|---:|']
    for hyp, counts in funnel.items(): lines.append('| '+hyp+' | '+' | '.join(str(v) for v in counts.values())+' |')
    lines += ['', '## Olay sonuçları', '', '| H | Olay | Net 5m medyan % | Net 20m medyan % | Excess 20m medyan % |', '|---|---:|---:|---:|---:|']
    for r in summaries:
        if r['split'] == 'ALL': lines.append(f"| {r['hypothesis']} | {r['events']} | {r['net_5m_median']} | {r['net_20m_median']} | {r['excess_20m_median']} |")
    lines += ['', '## False positive: gerçek olay dökümü', '',
              f'{len(false_positive)} tetikte 5m net getiri ≤0. Bu yalnız 5m tanımıdır; 20m/60m başarısızlığı anlamına gelmez. Tüm olaylar false_positives.csv dosyasında.', '',
              '| Snapshot | H | Net 5m % | Tetik öncesi uyarı / test edilecek filtre |', '|---|---|---:|---|']
    for e in false_positive[:15]: lines.append(f"| {e['snapshot_id']} | {e['hypothesis']} | {e['net_5m']:.4f} | {e['warnings'].replace('|', ', ')} |")
    lines += ['', 'Bu uyarılar filtre adayıdır. Başarılı olayları da eleyebilir; iyileştirme kanıtı sayılmaz. filter_candidates.csv her adayın kaç kaybeden ve kazanan olayı eleyeceğini TRAIN/HOLDOUT ayrı gösterir.', '',
              '## False negative: kaçırılan hareketler', '',
              f'{len(false_negative)} olay: +20m >%1 veya +60m >%2; gözlem anından önceki 20 dakikada H1/H2/H3 long tetiği yok. Aynı coin 60 dk tekilleştirilir.', '',
              '| Snapshot | 20m % | 60m % | H1/H2/H3 engeli |', '|---|---:|---:|---|']
    for e in false_negative[:15]: lines.append(f"| {e['snapshot_id']} | {e['return_20m']} | {e['return_60m']} | {e['H1']}/{e['H2']}/{e['H3']} |")
    lines += ['', 'Eksik/bozuk veri de kaçırılan hareket nedenidir; kalite alanı ayrı tutulur. H4/H5 short modelleri yukarı hareket yakalama hedefi taşımaz.', '',
              '## H6 dönüşümleri', '', f'İzlenen reset grubu: {len(conversions)}. Dönüşüm penceresi 60 dakika; kesinti >3 dk olursa durum sıfırlanır.']
    for target in ('H1', 'H2'):
        converted = [r for r in conversions.values() if r.get(target+'_snapshot_id')]
        concurrent = sum(r.get(target+'_timing') == 'CONCURRENT' for r in converted)
        censored = sum(r[target+'_censored'] for r in conversions.values())
        lines.append(f"- H6 → {target}: gözlenen {len(converted)}/{len(conversions)}; aynı anda zaten setup olan {concurrent}, sonradan dönüşen {len(converted)-concurrent}; gecikme medyanı {med(r[target+'_delay_sec'] for r in converted)} sn. Sonucu gözlenemeden takip kesilen {censored}; bunlar başarısız dönüşüm sayılmaz. Dönüşüm sonrası outcome conversions.csv içindedir.")
    lines += ['', '## Segmentler ve indikatör geliştirme kararı', '',
              'TOP20/TOP100/OUTSIDE100 (kayıt defterindeki statik sıra), rejim, RVOL, HTF, pump bağlamı segments.csv içinde; <30 olay INSUFFICIENT. Sıralar canlı market-cap sırası değildir.',
              'Fatigue, Structure, REALF ve CVD formülleri korunur. Reset süresi, gap büyümesi, R² tier, retest/reacceleration, follow-through ve confirmation delay replay içinde ölçülür.',
              'H1/H2/H4/H5 eşikleri bu deneyle production kuralına çevrilmez. H3 retest modeli ayrı shadow adaydır. Yeni H8 ilan edilmez.',
              '30/50/100 olay ve farklı gün/rejim verisi toplanmadan güç yüzdeleri yükseltilmez. Tarihsel raporlar yeni sonuçlarla sessizce değiştirilmez.',
              'Sonraki veri: farklı günler, holdout günleri, gerçek maliyetler ve H5 setup→armed kaybı. Best setup sıralaması için mevcut sample tek başına yeterli değildir.', '']
    (output / 'RAPOR.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({k:v for k,v in audit.items() if k not in ('snapshot_hashes', 'funnel_snapshot_counts', 'history_hashes', 'research_code_hashes')}, ensure_ascii=False), flush=True)
    print(f'Report: {output / "RAPOR.md"}', flush=True)
    return audit


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('run')
    p.add_argument('--fetch-history', action='store_true')
    p.add_argument('--cost-bps', type=float, default=10)
    args = p.parse_args()
    if args.cost_bps < 0: p.error('cost must be nonnegative')
    analyze(args.run, args.fetch_history, args.cost_bps)
