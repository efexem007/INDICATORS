"""Compare a small frozen candidate menu and causal next-observation exits.

Uses research_report's replay CSV as a typed machine table, not as edited input.
No thresholds are searched or optimized. Outputs are descriptive research only.

Three things are measured beyond raw returns, because raw event counts and a
fixed 20 minute window were both misleading:
  * trade character - when the strongest move arrives, how much is given back and
    when the first opposing signal shows up, per candidate;
  * time clusters - events that share a 10 minute bucket move together, so the
    evidence is counted in buckets as well as in raw events;
  * quality veto cost - what the data-quality veto suppressed, measured instead of
    assumed.
"""
import argparse
import bisect
import collections
import csv
import hashlib
import json
from pathlib import Path
import statistics

import hypothesis_candidates as hc
import shadow_research as sh
import trade_plan as tp
from research_report import dump_csv, med

# Cross-coin co-movement: events inside one bucket are not independent evidence.
CLUSTER_MS = 10 * 60_000


def typed(value):
    if value == '': return None
    if value == 'True': return True
    if value == 'False': return False
    try: return json.loads(value)
    except (ValueError, TypeError): return value


def summarize(rows, key):
    values = [r[key] for r in rows if r.get(key) is not None]
    return {'n': len(values), 'median': med(values), 'mean': round(statistics.mean(values), 4) if values else None,
            'hit_pct': round(100 * sum(v > 0 for v in values) / len(values), 1) if values else None}


def clusters(rows):
    """Independent-ish observations: distinct 10 minute buckets, not raw events."""
    return len({r['t0_ms'] // CLUSTER_MS for r in rows})


def share(values, limit):
    return round(100 * sum(v <= limit for v in values) / len(values), 1) if values else None


def observed_shape(entry, following, horizon, cost_bps):
    """Where the move peaks, where it hurts, and when the first opposing signal is.

    Same censoring rule as the exit table: a gap, a quality veto or a short
    indicator window means the event is not shaped, never silently truncated.
    """
    t0 = entry['captured_at_ms']
    direction = -1 if entry['variant'].startswith(('H4', 'H5')) else 1
    end = t0 + horizon * 60_000
    last, peak, trough, current = t0, 0., 0., 0.
    peak_delay = trough_delay = 0.
    opposing = {'flow_structure': None, 'atr_giveback': None}
    full = False
    for s in following:
        now = s['captured_at_ms']
        if now > end + 90_000: break
        if now - last > sh.GAP_MS or sh.quality(s): return None
        last = now
        current = direction * (s['price'] / entry['price'] - 1) * 100
        delay = (now - t0) / 1000
        if current > peak: peak, peak_delay = current, delay
        if current < trough: trough, trough_delay = current, delay
        for policy, key in (('FLOW_STRUCTURE', 'flow_structure'), ('ATR_GIVEBACK', 'atr_giveback')):
            if opposing[key] is None and delay >= 60 and hc.exit_condition(
                    policy, s, direction, peak, current, entry.get('str_1m_atr_pct')):
                opposing[key] = delay
        if now >= end:
            full = True
            break
    if not full: return None
    return {'mfe_pct': round(peak, 4), 'mae_pct': round(trough, 4),
            'peak_delay_sec': peak_delay, 'trough_delay_sec': trough_delay,
            'end_pct': round(current - cost_bps / 100, 4), 'giveback_pct': round(peak - current, 4),
            'flow_opposes_sec': opposing['flow_structure'], 'atr_giveback_sec': opposing['atr_giveback']}


def observed_exit_path(entry, following, horizon, policy, cost_bps):
    """Paired full-window comparisons. No indicators after observation cutoff.
    Signal at t is filled at next valid snapshot, including when its price worsens.
    No indicator coverage to horizon -> censored, even when price outcome exists.
    """
    t0 = entry['captured_at_ms']
    direction = -1 if entry['variant'].startswith(('H4', 'H5')) else 1
    end = t0 + horizon * 60_000
    last, peak, pending, result = t0, 0., None, None
    full = False
    for s in following:
        now = s['captured_at_ms']
        if now > end + 90_000: break
        if now - last > sh.GAP_MS or sh.quality(s): return None
        last = now
        ret = direction * (s['price'] / entry['price'] - 1) * 100
        if pending is not None and result is None:
            result = {'exit_snapshot_id': s['snapshot_id'], 'signal_snapshot_id': pending,
                      'delay_sec': (now - t0) / 1000, 'net_pct': ret - cost_bps / 100}
        peak = max(peak, ret)
        if now >= end:
            full = True
            break
        if result is None and pending is None and now - t0 >= 60_000 and hc.exit_condition(policy, s, direction, peak, ret, entry.get('str_1m_atr_pct')):
            pending = s['snapshot_id']
    if not full: return None
    fixed = entry.get(f'fwd_ret_{horizon}m')
    if fixed is None: return None
    fixed_net = direction * fixed - cost_bps / 100
    if result is None:
        result = {'exit_snapshot_id': None, 'signal_snapshot_id': None, 'delay_sec': horizon*60, 'net_pct': fixed_net}
    result.update(fixed_net_pct=fixed_net, improvement_pct=result['net_pct']-fixed_net)
    return result


def entry_row(s, variant, cost_bps):
    direction = -1 if variant.startswith(('H4', 'H5')) else 1
    row = {'variant': variant, 'snapshot_id': s['snapshot_id'], 'symbol': s['symbol'],
           't0_ms': s['captured_at_ms'], 'split': s['split'], 'decision_horizon': hc.decision_horizon(variant),
           'complete': bool(s.get('outcome_complete')), 'pump': s.get('shadow_H7_context'),
           'alignment': s.get('shadow_alignment_pattern'), 'warnings': s.get('shadow_quality_veto')}
    for h in hc.OUTCOME_HORIZONS:
        ret, excess = s.get(f'fwd_ret_{h}m'), s.get(f'excess_ret_{h}m')
        row[f'net_{h}m'] = direction * ret - cost_bps/100 if ret is not None else None
        row[f'excess_{h}m'] = direction * excess if excess is not None else None
    return row


def character_rows(entries, variant, split):
    """One candidate's trade character; only fully observed windows are shaped."""
    group = [r for r in entries if r['variant'] == variant and (split == 'ALL' or r['split'] == split)]
    shaped = [r for r in group if r.get('peak_delay_sec') is not None]
    peaks = [r['peak_delay_sec']/60 for r in shaped]
    decision = hc.decision_horizon(variant)
    at_horizon = [r[f'net_{decision}m'] for r in group if r.get(f'net_{decision}m') is not None]
    measured_peak = med(peaks)
    return {'variant': variant, 'split': split, 'events': len(group), 'clusters': clusters(group),
            'shaped': len(shaped), 'decision_horizon': decision,
            'peak_delay_min_median': measured_peak,
            'rule_horizon': hc.horizon_rule(measured_peak),
            'peak_within_10m_pct': share(peaks, 10), 'peak_within_20m_pct': share(peaks, 20),
            'peak_within_30m_pct': share(peaks, 30),
            'mfe_median': med(r['mfe_pct'] for r in shaped), 'mae_median': med(r['mae_pct'] for r in shaped),
            'giveback_median': med(r['giveback_pct'] for r in shaped),
            'mae_delay_min_median': med(r['trough_delay_sec']/60 for r in shaped),
            'flow_opposes_min_median': med(r['flow_opposes_sec']/60 for r in shaped if r['flow_opposes_sec'] is not None),
            'net_at_decision_median': med(at_horizon),
            'hit_pct_at_decision': round(100*sum(v > 0 for v in at_horizon)/len(at_horizon), 1) if at_horizon else None}


def evaluate(run, cost_bps=10):
    run = Path(run)
    replay_path = run/'research_shadow_v1'/'replay_with_outcomes.csv'
    with replay_path.open(encoding='utf-8-sig', newline='') as f:
        rows = [{k:typed(v) for k,v in r.items()} for r in csv.DictReader(f)]
    rows.sort(key=lambda s:s['captured_at_ms'])
    by_symbol = collections.defaultdict(list)
    for s in rows: by_symbol[s['symbol']].append(s)
    times = {symbol:[s['captured_at_ms'] for s in group] for symbol,group in by_symbol.items()}
    tracker, entries, exits = hc.CandidateTracker(), [], []
    veto_tracker, vetoed, triggered = hc.CandidateTracker(), [], []
    for s in rows:
        labels = tracker.update(s)
        if s.get('shadow_quality_veto'):  # what the veto suppressed, measured not assumed
            suppressed = veto_tracker.update_masks(s, hc.candidate_masks(s, ignore_quality=True))
            for variant in hc.VARIANTS:
                if suppressed[variant]:
                    vetoed.append(dict(entry_row(s, variant, cost_bps), veto=s.get('shadow_quality_veto')))
        for variant in hc.VARIANTS:
            if not labels[f'research_{variant}_event']: continue
            entry = dict(s, variant=variant)
            row = entry_row(s, variant, cost_bps)
            entries.append(row)
            triggered.append(entry)
            if variant.startswith('H6'): continue
            ix = bisect.bisect_right(times[s['symbol']], s['captured_at_ms'])
            following = by_symbol[s['symbol']][ix:]
            shape = observed_shape(entry, following, 60, cost_bps)
            if shape: row.update(shape)
            for horizon in (20,60):
                for policy in ('FLOW_STRUCTURE','ATR_GIVEBACK'):
                    result = observed_exit_path(entry, following, horizon, policy, cost_bps)
                    exits.append({'variant':variant, 'snapshot_id':s['snapshot_id'], 'symbol':s['symbol'],
                                  'split':s['split'], 'horizon':horizon, 'policy':policy, 'censored': result is None,
                                  **(result or {})})
    summary, exit_summary, segments, character = [], [], [], []
    for variant in hc.VARIANTS:
        for split in ('ALL','TRAIN','HOLDOUT'):
            group = [r for r in entries if r['variant']==variant and (split=='ALL' or r['split']==split)]
            for h in hc.OUTCOME_HORIZONS:
                stats = summarize(group,f'net_{h}m')
                summary.append({'variant':variant,'split':split,'horizon':h,'events':len(group),
                                'clusters':clusters(group),'decision':h == hc.decision_horizon(variant), **stats,
                                'excess_median':med(r[f'excess_{h}m'] for r in group),
                                'status':'INSUFFICIENT' if stats['n']<30 else 'SINGLE_RUN_EXPLORATORY'})
            character.append(character_rows(entries, variant, split))
            for h in (20,60):
                for policy in ('FLOW_STRUCTURE','ATR_GIVEBACK'):
                    group = [r for r in exits if r['variant']==variant and r['horizon']==h and r['policy']==policy and (split=='ALL' or r['split']==split)]
                    valid = [r for r in group if not r['censored']]
                    exit_summary.append({'variant':variant,'split':split,'horizon':h,'policy':policy,
                                         'n':len(valid),'censored':len(group)-len(valid),
                                         'dynamic_median':med(r['net_pct'] for r in valid),
                                         'fixed_median':med(r['fixed_net_pct'] for r in valid),
                                         'paired_improvement_median':med(r['improvement_pct'] for r in valid)})
        for pump in sorted({str(r['pump']) for r in entries if r['variant']==variant}):
            group=[r for r in entries if r['variant']==variant and str(r['pump'])==pump]
            segments.append({'variant':variant,'pump':pump,**summarize(group,'net_20m')})
    veto_summary = []
    for variant in hc.VARIANTS:
        group = [r for r in vetoed if r['variant']==variant]
        if not group: continue
        decision = hc.decision_horizon(variant)
        veto_summary.append({'variant':variant,'suppressed_events':len(group),
                             'with_outcome':sum(r.get(f'net_{decision}m') is not None for r in group),
                             'horizon':decision, **summarize(group, f'net_{decision}m'),
                             'excess_median':med(r[f'excess_{decision}m'] for r in group)})
    plan_events, plan_summary, class_summary, classes, atr_cut = tp.build(
        rows, by_symbol, times, triggered, character, cost_bps)
    by_class = {c['symbol']: c['class'] for c in classes}
    for row in entries:
        row['coin_class'] = by_class.get(row['symbol'])
    folder=run/'hypothesis_lab_v21'
    folder.mkdir(exist_ok=True)
    for name,data in [('entries',entries),('entry_summary',summary),('exit_events',exits),('exit_summary',exit_summary),
                      ('pump_segments',segments),('character',character),('veto_suppressed',vetoed),('veto_cost',veto_summary),
                      ('plan_events',plan_events),('plan_summary',plan_summary),('coin_class_summary',class_summary),
                      ('coin_classes',classes)]:
        dump_csv(folder/f'{name}.csv',data)
    (folder/'PLAN.md').write_text(tp.render_plan(plan_summary, class_summary, classes, atr_cut),encoding='utf-8')
    drift = [c for c in character if c['split']=='ALL' and c['rule_horizon'] is not None
             and c['rule_horizon'] != c['decision_horizon']]
    audit={'version':hc.VERSION,'cost_bps_roundtrip':cost_bps,'candidate_menu':hc.VARIANTS,
           'replay_sha256':hashlib.sha256(replay_path.read_bytes()).hexdigest(),
           'code_hashes':{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ('hypothesis_candidates.py','hypothesis_lab.py')},
           'rows':len(rows),'missing_outcomes':sum(not s.get('outcome_complete') for s in rows),
           'cluster_ms':CLUSTER_MS,'decision_horizons':hc.DECISION_HORIZON,'indicators':hc.INDICATORS,
           'entry_policies':tp.ENTRY_POLICIES,'exit_policies':tp.EXIT_POLICIES,
           'frozen_peak_minutes':hc.MEASURED_PEAK_MIN,
           'horizon_drift':[{'variant':c['variant'],'measured_peak_min':c['peak_delay_min_median'],
                             'rule_horizon':c['rule_horizon'],'frozen_horizon':c['decision_horizon']} for c in drift],
           'ignition_thresholds':{'realf_rvol':hc.IGNITION_RVOL,'buyer_ratio_1m':hc.IGNITION_BUYER_PCT,
                                  'quiet_atr_pct':hc.QUIET_ATR_PCT},
           'veto_suppressed_events':len(vetoed),
           'limits':['single run, no independent day OOS','60m spacing does not remove cross-coin dependence',
                     'baseline menu fixed, no threshold optimization','next snapshot execution approximate',
                     'giveback uses observed prices, not intrabar extrema','no automatic promotion',
                     'decision horizon follows measured peak timing, it is not searched',
                     'H8 thresholds are this run own distribution quantiles, outcome blind but in-sample']}
    (folder/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'KARAKTER.md').write_text(render_character(character, drift),encoding='utf-8')
    lines=['# H1–H8 aday karşılaştırması','','Sürüm: '+hc.VERSION+'. Tamamı araştırma; otomatik üretim değişikliği yok.','',
           'Karar ufku hipotez başına, ölçülen tepe zamanından türer (bkz. KARAKTER.md); aranmaz.','',
           '| Aday | Karar ufku | Olay | Küme | Net (karar) % | Excess (karar) % | Holdout olay | Holdout küme | Holdout excess % |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for variant in hc.VARIANTS:
        decision = hc.decision_horizon(variant)
        a=next(r for r in summary if r['variant']==variant and r['split']=='ALL' and r['horizon']==decision)
        b=next(r for r in summary if r['variant']==variant and r['split']=='HOLDOUT' and r['horizon']==decision)
        lines.append(f"| {variant} | {decision}m | {a['events']} | {a['clusters']} | {a['median']} | "
                     f"{a['excess_median']} | {b['events']} | {b['clusters']} | {b['excess_median']} |")
    lines+=['','## Sınırlar','',
            'İlk %70 zaman eğitim; son %30 doğrulama; 60m sonuç taşması eğitimden temizlenir. Tek gün içi doğrulama, farklı gün OOS değildir.',
            'Eksik sonuçlar sıfır sayılmaz. 60m aralıklı ilk koşul gözlemi kullanılır; ana raporun setup-grubu tetiğinden farklı örnekleme olabilir.',
            'Maliyet varsayımı toplam 10 bps (komisyon+slippage); gerçekleşmiş maliyet/funding değildir. H6 getirileri yalnız scanner izleme sonucudur.',
            'Exit tabloları sadece tam indicator takip penceresi olan aynı olayları eşler. Sinyal anındaki fiyatla anında dolum kabul edilmez; sonraki snapshot kullanılır.',
            'İki çıkış adayı: (1) 1m CVD ters + 5m CVD/yapı ters; (2) en az 1 ATR ilerledikten sonra 1 ATR geri verme. İkinci eşik girişteki ATR ile sabittir.',
            "Karar sütunu excess'tir: yükselen piyasada net getiri sepetle birlikte artar; tek başına üstünlük kanıtı değildir.",
            f'Küme sütunu {CLUSTER_MS//60000} dakikalık kovalardır: aynı kovadaki olaylar birlikte hareket eder, bağımsız kanıt sayılmaz.',
            'H8 eşikleri bu runın kendi dağılım yüzdelikleridir (getiriye bakılmadan seçildi, ama örneklem içidir).',
            '30+ holdout kümesi ve farklı gün/rejim kanıtı olmadan hiçbir aday doğrulanmış işlem kuralına yükseltilmez.','']
    (folder/'KARSILASTIRMA.md').write_text('\n'.join(lines),encoding='utf-8')
    print('\n'.join(lines[:len(hc.VARIANTS)+8]),flush=True)
    return summary,exit_summary,character


def render_character(character, drift):
    lines=['# Aday işlem karakteri','',
           'Her satır: en güçlü hareket ne zaman geliyor, ne kadarı geri veriliyor, ilk karşıt sinyal nerede.',
           'Yalnız tam 60 dakika gözlenen olaylar şekillendirilir; eksik pencere sansürlüdür, sıfır sayılmaz.','',
           '| Aday | Olay | Şekilli | Tepe (dk, medyan) | ≤10dk | ≤20dk | ≤30dk | MFE % | MAE % | Geri verme % | '
           'MAE zamanı (dk) | İlk karşıt akış (dk) | Karar ufku | Kural ufku | İsabet % |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in character:
        if row['split'] != 'ALL' or not row['shaped']:
            continue
        def f(v, digits=2):
            return '—' if v is None else f'{v:.{digits}f}'
        lines.append(f"| {row['variant']} | {row['events']} | {row['shaped']} | {f(row['peak_delay_min_median'],0)} | "
                     f"{f(row['peak_within_10m_pct'],0)} | {f(row['peak_within_20m_pct'],0)} | {f(row['peak_within_30m_pct'],0)} | "
                     f"{f(row['mfe_median'])} | {f(row['mae_median'])} | {f(row['giveback_median'])} | "
                     f"{f(row['mae_delay_min_median'],0)} | {f(row['flow_opposes_min_median'],0)} | "
                     f"{row['decision_horizon']}m | {row['rule_horizon'] or '—'} | {f(row['hit_pct_at_decision'],0)} |")
    lines += ['', '## Karar ufku sapması', '']
    if drift:
        lines.append('Ölçülen tepe zamanı dondurulmuş ufkun dışına çıkan adaylar (defter bunu eksik olarak açar):')
        lines.append('')
        for row in drift:
            lines.append(f"- **{row['variant']}**: ölçülen tepe {row['peak_delay_min_median']:.0f} dk → kural {row['rule_horizon']}m, "
                         f"dondurulmuş {row['decision_horizon']}m")
    else:
        lines.append('Sapma yok: ölçülen tepe zamanları dondurulmuş karar ufuklarıyla uyumlu.')
    lines += ['', 'Kural: medyan tepeyi İÇEREN en küçük mevcut ufuk. Ufuk getiriye göre değil, tepe zamanına göre seçilir.',
              'MFE/MAE gözlenen snapshot fiyatlarıdır, bar içi uçlar değildir; maliyet yalnız net sütunlarına uygulanır.','']
    return '\n'.join(lines)


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('run')
    ap.add_argument('--cost-bps',type=float,default=10)
    args=ap.parse_args()
    if args.cost_bps<0:ap.error('cost must be nonnegative')
    evaluate(args.run,args.cost_bps)
