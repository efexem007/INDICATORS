"""Round ledger: how each hypothesis and each known gap moved in the newest run.

One review round records exactly one run's lab table. Nothing is rescanned and no
threshold is searched, so a status change here means evidence arrived, not that a
knob was turned. Re-recording a run whose replay fingerprint and menu version are
unchanged adds no round; a new menu or new outcomes on the same run does add one,
and cumulative counts then use that run's latest round only.

Gaps are carried, not retold: an automatic gap closes when its condition stops
being observed, a manual gap only when a person records the closing evidence.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

SCHEMA = 'research-ledger-v1'
DECISION_HORIZONS = (20, 60)
ENOUGH = 30          # the lab's own INSUFFICIENT bound; not tuned here
ELIMINATION_MIN = 10  # never eliminate a variant on a handful of events
SCANNER = ('H6', 'H7')

# Evidence a person has to bring; no code can observe these, so they stay open
# until someone records how they were met. Seeded once, on the first round.
SEED_GAPS = [
    ('Farklı gün ve düşen/sıkışan rejim verisi',
     'H4 ve H5 short hipotezleri yükselen rejimde yargılanamaz.',
     'En az bir düşen rejim çalışmasının deftere girmesi'),
    ('Gerçek maliyet ve funding',
     'Lab sabit 10 bps varsayıyor; gerçekleşmiş maliyet değil.',
     'Gerçekleşmiş komisyon/slippage/funding ölçümünün deftere girmesi'),
    ('H4 tanımının gözlenebilirliği',
     'Armed anı ile taze 3m/5m DN olayı bu veride saatlerce ayrık.',
     'Başka günlerde de bağ yoksa H4 tanımı gözlenemez sayılmalı'),
    ('H2/H3 için 30-60 dk ufkunun ayrı olay tanımı',
     'Kenar uzun ufukta göründü; olay tanımı hâlâ kısa ufka göre.',
     'Uzun ufuk için ayrı tanımın yazılıp ölçülmesi'),
]


def now_iso(now=None):
    return (now or datetime.now(timezone.utc)).strftime('%Y-%m-%dT%H:%M:%SZ')


def number(value):
    if value in (None, '', 'None'):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read_rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def best_plan(plans, variant, minimum=8):
    """Best paired plan for this candidate; the baseline wins when nothing beats it."""
    rows = [r for r in plans if r['variant'] == variant and r['split'] == 'ALL'
            and int(r['paired_n'] or 0) >= minimum and number(r['paired_vs_baseline_median']) is not None]
    if not rows:
        return None
    best = max(rows, key=lambda r: number(r['paired_vs_baseline_median']))
    return {'entry': best['entry_policy'], 'exit': best['exit_policy'],
            'gain': number(best['paired_vs_baseline_median']), 'pairs': int(best['paired_n'] or 0),
            'fill_pct': number(best['fill_pct']), 'hit_pct': number(best['hit_pct']),
            'exit_min': number(best['exit_delay_min_median'])}


def cell_values(cells, horizon):
    per = {}
    for split in ('ALL', 'TRAIN', 'HOLDOUT'):
        cell = cells.get((split, horizon))
        per[split.lower()] = {'n': int(cell['n']) if cell else 0,
                              'clusters': int(cell['clusters']) if cell and cell.get('clusters') else 0,
                              'excess': number(cell['excess_median']) if cell else None,
                              'net': number(cell['median']) if cell else None}
    return per


def measure(rows, variant, character=None, plans=None, coin_rows=None):
    """One variant's evidence in this round, read from the lab's own tables.

    Evidence is carried twice: raw events and 10 minute clusters. Events inside one
    cluster move together, so the cluster count is what the decision rules use.
    """
    cells = {(r['split'], int(r['horizon'])): r for r in rows if r['variant'] == variant}
    first = cells.get(('ALL', DECISION_HORIZONS[0]))
    decision = next((int(r['horizon']) for r in rows
                     if r['variant'] == variant and str(r.get('decision')).lower() == 'true'), None)
    out = {'events': int(first['events']) if first else 0,
           'clusters': int(first['clusters']) if first and first.get('clusters') else 0,
           'decision_horizon': decision, 'horizons': {}}
    for horizon in DECISION_HORIZONS:
        out['horizons'][str(horizon)] = cell_values(cells, horizon)
    # the decision horizon is one of the stored horizons; it is not copied a second time
    if plans:
        out['plan'] = best_plan(plans, variant)
    if coin_rows:
        out['coin_classes'] = [{'class': r['coin_class'], 'events': int(r['events'] or 0),
                                'filled': int(r['filled'] or 0), 'net': number(r['net_median']),
                                'hit': number(r['hit_pct']), 'symbols': int(r['symbols'] or 0)}
                               for r in coin_rows if r['variant'] == variant and int(r['filled'] or 0) >= 3]
    if character:
        row = next((c for c in character if c['variant'] == variant and c['split'] == 'ALL'), None)
        if row:
            out['character'] = {k: number(row.get(k)) for k in
                                ('peak_delay_min_median', 'rule_horizon', 'mfe_median', 'mae_median',
                                 'giveback_median', 'mae_delay_min_median', 'flow_opposes_min_median',
                                 'hit_pct_at_decision', 'shaped')}
    return out


def decision_cell(m):
    """The horizon this hypothesis is judged at; older rounds only carry 20m."""
    horizons = m['horizons']
    return (horizons.get('decision') or horizons.get(str(m.get('decision_horizon')))
            or horizons[str(DECISION_HORIZONS[0])])


def _all_negative(m):
    """Non-positive in both splits on a real sample, at the horizon it is judged at."""
    if m['events'] < ELIMINATION_MIN:
        return False
    per = decision_cell(m)
    seen = False
    for split in ('train', 'holdout'):
        excess = per[split]['excess']
        if excess is None:
            continue
        seen = True
        if excess > 0:
            return False
    return seen


def evidence(per, split):
    """Clusters when the lab reports them, raw n for rounds recorded before that."""
    return per[split].get('clusters') or 0 if per[split].get('clusters') else per[split]['n']


def classify(variant, current, history, evidence_id=None):
    """Fixed ladder. Order matters: no sample beats a missing sample.

    Elimination needs two rounds of DIFFERENT evidence: re-measuring one run with new
    code opens a round, but it is the same data and must not count as confirmation.
    """
    if variant.startswith(SCANNER):
        return 'TARAYICI', 'Tarama/bağlam katmanı; işlem tetiği olarak ölçülmez.'
    if current['events'] == 0:
        return 'VERI_YOK', 'Bu tanımla tetik gözlenmedi; eşik gevşetilmedi.'
    per = decision_cell(current)
    horizon = current.get('decision_horizon') or DECISION_HORIZONS[0]
    if (evidence(per, 'holdout') >= ENOUGH and (per['train']['excess'] or 0) > 0
            and (per['holdout']['excess'] or 0) > 0):
        return 'ADAY', f'{horizon}m excess iki bölümde de pozitif ve holdout kümesi {ENOUGH}+.'
    previous = history[-1] if history else None
    if (_all_negative(current) and previous and _all_negative(previous['measure'])
            and previous.get('evidence_id') not in (None, evidence_id)):
        return 'ELENDI', f'Farklı iki kanıt turunda {horizon}m excess pozitif değil.'
    if evidence(per, 'all') < ENOUGH:
        return 'YETERSIZ', f'Bağımsız kanıt {ENOUGH} kümenin altında; yön iddiası taşımaz.'
    return 'IZLENIYOR', f'Kanıt yeterli ama holdout {ENOUGH} kümeye ulaşmadı.'


def blank_state():
    return {'schema': SCHEMA, 'rounds': [], 'hypotheses': {}, 'gaps': [], 'next_gap': 1}


def load(ledger_root):
    path = Path(ledger_root) / 'ledger.json'
    if not path.exists():
        return blank_state()
    state = json.loads(path.read_text(encoding='utf-8'))
    if state.get('schema') != SCHEMA:
        raise ValueError(f'Tanınmayan defter sürümü: {state.get("schema")}')
    return state


def save(ledger_root, state):
    ledger_root = Path(ledger_root)
    ledger_root.mkdir(parents=True, exist_ok=True)
    (ledger_root / 'ledger.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    if state['rounds']:
        (ledger_root / 'HIPOTEZ_DEFTERI.md').write_text(render_hypotheses(state), encoding='utf-8')
        (ledger_root / 'EKSIKLER.md').write_text(render_gaps(state), encoding='utf-8')
        (ledger_root / 'KULLANIM_KILAVUZU.md').write_text(render_manual(state), encoding='utf-8')


def rewind_gaps(state, round_no):
    """Undo one round's gap effects so a revision does not stack on its own first pass."""
    state['gaps'] = [g for g in state['gaps'] if not (g['opened_round'] == round_no and g['source'] == 'auto')]
    for gap in state['gaps']:
        if gap['closed_round'] == round_no and (gap['key'] or '').startswith('auto:'):
            gap.update(state='ACIK', closed_round=None, evidence=None)
        gap['metric'] = [m for m in gap['metric'] if m['round'] != round_no]


def open_gap(state, key, title, detail, close_when, round_no, source, metric=None):
    gap = {'id': f'E-{state["next_gap"]:04d}', 'key': key, 'title': title, 'detail': detail,
           'close_when': close_when, 'source': source, 'opened_round': round_no,
           'state': 'ACIK', 'metric': [], 'closed_round': None, 'evidence': None}
    if metric is not None:
        gap['metric'].append({'round': round_no, 'value': metric})
    state['gaps'].append(gap)
    state['next_gap'] += 1
    return gap


def auto_conditions(variants, current, audit, exit_rows, distinct_days, history):
    """Conditions a machine can both observe and later see disappear."""
    found = {}
    for variant in variants:
        if variant.startswith(SCANNER):
            continue
        if current[variant]['events'] == 0:
            found[f'auto:no-trigger:{variant}'] = {
                'title': f'{variant}: bu tanımla tetik yok',
                'detail': 'Koşul kümesi bu veride hiç birlikte gerçekleşmedi.',
                'close_when': 'Aynı tanımla en az bir tetik gözlenmesi', 'metric': 0}
    best_holdout = max([evidence(decision_cell(current[v]), 'holdout')
                        for v in variants if not v.startswith(SCANNER)] or [0])
    if best_holdout < ENOUGH:
        found['auto:holdout-evidence'] = {
            'title': f'Hiçbir adayda {ENOUGH}+ bağımsız holdout kümesi yok',
            'detail': 'Aynı 10 dakikalık kovadaki olaylar birlikte hareket ettiği için ayrı kanıt sayılmaz.',
            'close_when': f'Bir adayın holdout küme sayısının {ENOUGH} olması', 'metric': best_holdout}
    drift = audit.get('horizon_drift') or []
    if drift:
        names = ', '.join(d['variant'] for d in drift[:4]) + ('…' if len(drift) > 4 else '')
        found['auto:horizon-drift'] = {
            'title': 'Ölçülen tepe zamanı dondurulmuş karar ufkuyla uyuşmuyor',
            'detail': f'Kural (medyan tepeyi içeren en küçük ufuk) başka ufuk veriyor: {names}.',
            'close_when': 'Ufukların ölçülen tepe zamanıyla uyumlu hâle gelmesi', 'metric': len(drift)}
    missing = int(audit.get('missing_outcomes') or 0)
    if missing:
        found['auto:missing-outcomes'] = {
            'title': 'Sonucu tamamlanmamış snapshot var',
            'detail': 'Ufku dolmuş kayıtlar SONUCLARI_HESAPLA.bat ile kapatılabilir.',
            'close_when': 'Tamamlanmamış sonuç sayısının 0 olması', 'metric': missing}
    if distinct_days < 2:
        found['auto:single-day'] = {
            'title': 'Tek güne dayanan kanıt',
            'detail': 'Gün içi holdout, farklı gün OOS yerine geçmez.',
            'close_when': 'Deftere en az iki farklı günün girmesi', 'metric': distinct_days}
    for variant in variants:
        if variant.startswith(SCANNER):
            continue
        recent = history.get(variant, {}).get('history', [])[-3:]  # current round is already in it
        if len(recent) < 3 or not all(r['measure'].get('clusters') for r in recent):
            continue  # rounds counted on different bases are not a trend, they are a unit change
        grown = [evidence(decision_cell(r['measure']), 'holdout') for r in recent]
        if len({r['status'] for r in recent}) == 1 and grown[0] and grown[-1] <= grown[0]:
            found[f'auto:stagnant:{variant}'] = {
                'title': f'{variant}: üç turdur ne durum ne kanıt değişiyor',
                'detail': 'Aynı tanımla beklemek kanıt üretmiyor; tanım ya toplama değişmeli.',
                'close_when': 'Holdout kümesinin büyümesi veya tanımın değişmesi', 'metric': grown[-1]}
    counted = [(int(r['n'] or 0), int(r['censored'] or 0)) for r in exit_rows if r.get('split') == 'ALL']
    total = sum(n + c for n, c in counted)
    if total:
        share = round(100 * sum(c for _, c in counted) / total, 1)
        if share > 20:
            found['auto:censored-exits'] = {
                'title': 'Çıkış karşılaştırmalarının büyük kısmı sansürlü',
                'detail': 'Tam indikatör penceresi olmayan olaylar eşleştirilemiyor.',
                'close_when': 'Sansürlü payın %20 altına inmesi', 'metric': share}
    return found


def sync_gaps(state, found, round_no):
    """Open what is new, keep measuring what stays, close what is gone."""
    opened, closed, carried = [], [], []
    by_key = {g['key']: g for g in state['gaps'] if g['key'] and g['state'] == 'ACIK'}
    for key, item in sorted(found.items()):
        gap = by_key.get(key)
        if gap is None:
            opened.append(open_gap(state, key, item['title'], item['detail'], item['close_when'],
                                   round_no, 'auto', item['metric']))
        else:
            gap['metric'].append({'round': round_no, 'value': item['metric']})
            carried.append(gap)
    for key, gap in by_key.items():
        if key.startswith('auto:') and key not in found:
            gap.update(state='KAPANDI', closed_round=round_no, evidence='Koşul bu turda gözlenmedi.')
            closed.append(gap)
    return opened, closed, carried


def record(run, ledger_root, note=None, now=None):
    run, ledger_root = Path(run), Path(ledger_root)
    lab = run / 'hypothesis_lab_v21'
    audit = json.loads((lab / 'audit.json').read_text(encoding='utf-8'))
    rows = read_rows(lab / 'entry_summary.csv')
    exit_path = lab / 'exit_summary.csv'
    exit_rows = read_rows(exit_path) if exit_path.exists() else []
    char_path = lab / 'character.csv'
    character = read_rows(char_path) if char_path.exists() else []
    plan_path = lab / 'plan_summary.csv'
    plans = read_rows(plan_path) if plan_path.exists() else []
    class_path = lab / 'coin_class_summary.csv'
    coin_rows = read_rows(class_path) if class_path.exists() else []
    variants = list(audit['candidate_menu'])
    state = load(ledger_root)

    # The defter's own classification code is part of what produced these numbers, so a
    # change in it revises the round instead of silently restating an older verdict.
    code = json.dumps(dict(audit.get('code_hashes') or {},
                           research_ledger=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
                      sort_keys=True)
    evidence_id = f"{run.name}:{audit['replay_sha256'][:12]}"  # same data, however often it is re-measured
    same = [r for r in state['rounds'] if r['run'] == run.name
            and r['replay_sha256'] == audit['replay_sha256']
            and r['menu_version'] == audit['version']
            and r.get('code') == code]
    if same:
        return {'status': 'NO_NEW_EVIDENCE', 'round': same[-1]['round'], 'run': run.name,
                'message': 'Bu run aynı menü ve aynı replay ile zaten kayıtlı; tur açılmadı.'}

    # Same evidence measured again (new menu or new code) revises its round instead of
    # opening one: the defter stays one round per distinct evidence, without losing the
    # new measurement.
    last_round = state['rounds'][-1] if state['rounds'] else None
    revising = bool(last_round) and f"{last_round['run']}:{last_round['replay_sha256'][:12]}" == evidence_id
    round_no = last_round['round'] if revising else len(state['rounds']) + 1
    if revising:
        rewind_gaps(state, round_no)
    current = {v: measure(rows, v, character, plans, coin_rows) for v in variants}
    days = {r['run'][4:12] for r in state['rounds']} | {run.name[4:12]}
    record_row = {'round': round_no, 'run': run.name, 'recorded_at': now_iso(now),
                  'menu_version': audit['version'], 'replay_sha256': audit['replay_sha256'], 'code': code,
                  'rows': audit.get('rows'), 'missing_outcomes': audit.get('missing_outcomes'),
                  'cost_bps_roundtrip': audit.get('cost_bps_roundtrip'), 'note': note,
                  'revisions': (last_round.get('revisions', 0) + 1) if revising else 0}
    if revising:
        state['rounds'][-1] = record_row
    else:
        state['rounds'].append(record_row)

    changes = []
    for variant in variants:
        entry = state['hypotheses'].setdefault(
            variant, {'first_round': round_no, 'status': None, 'history': [], 'status_history': []})
        entry['description'] = (audit.get('candidate_menu') or {}).get(variant, entry.get('description', ''))
        entry['indicators'] = (audit.get('indicators') or {}).get(variant.split('_')[0]) or entry.get('indicators')
        history = entry['history']
        if revising and history and history[-1]['round'] == round_no:
            history.pop()  # the revised measurement replaces the one it corrects
            entry['status_history'] = [h for h in entry['status_history'] if h['round'] != round_no]
        before = history[-1]['status'] if history else None
        status, reason = classify(variant, current[variant], history, evidence_id)
        history.append({'round': round_no, 'run': run.name, 'evidence_id': evidence_id,
                        'measure': current[variant], 'status': status, 'reason': reason})
        entry['last_round'] = round_no
        if status != before:
            entry['status_history'].append({'round': round_no, 'from': before, 'to': status, 'reason': reason})
            changes.append({'variant': variant, 'from': before, 'to': status, 'reason': reason})
        entry['status'] = status
    dropped = [v for v in state['hypotheses'] if v not in variants]
    for variant in dropped:  # a variant leaving the menu stays as evidence, it is not deleted
        state['hypotheses'][variant].setdefault('retired_round', round_no)

    if round_no == 1 and not any(g['source'] == 'manual' for g in state['gaps']):
        for title, detail, close_when in SEED_GAPS:
            open_gap(state, None, title, detail, close_when, round_no, 'manual')
    found = auto_conditions(variants, current, audit, exit_rows, len(days), state['hypotheses'])
    opened, closed, _ = sync_gaps(state, found, round_no)

    save(ledger_root, state)
    return {'status': 'RECORDED', 'round': round_no, 'run': run.name, 'menu_version': audit['version'],
            'variants': len(variants), 'status_changes': changes, 'retired': dropped,
            'gaps_opened': [g['id'] for g in opened], 'gaps_closed': [g['id'] for g in closed],
            'gaps_open_total': sum(g['state'] == 'ACIK' for g in state['gaps']),
            'distinct_days': len(days), 'ledger': str(ledger_root)}


def fmt(value, digits=4):
    return '—' if value is None else (f'{value:+.{digits}f}' if isinstance(value, float) else str(value))


def delta(current, previous):
    return '—' if previous is None else f'{current - previous:+d}'


def render_hypotheses(state):
    rounds = state['rounds']
    last = rounds[-1]
    days = sorted({r['run'][4:12] for r in rounds})
    runs = {r['run'] for r in rounds}
    lines = ['# Hipotez defteri', '',
             f'Şema: `{SCHEMA}` · tur: {last["round"]} · farklı run: {len(runs)} · farklı gün: {len(days)}', '',
             f'Son tur: **{last["run"]}** · menü `{last["menu_version"]}` · {last["recorded_at"]} · '
             f'{last.get("rows")} satır, {last.get("missing_outcomes")} sonuçsuz.', '',
             'Durum kuralları sabittir; hiçbir eşik aranmaz. Bir durumun değişmesi kanıtın değiştiği anlamına gelir.',
             'Hiçbir satır işlem kuralı değildir.', '',
             '## Bu turda durumu değişen', '']
    changes = [item for item in state['hypotheses'].items()
               if item[1]['status_history'] and item[1]['status_history'][-1]['round'] == last['round']]
    if changes:
        for variant, entry in changes:
            step = entry['status_history'][-1]
            lines.append(f'- **{variant}**: {step["from"] or "yeni"} → **{step["to"]}** — {step["reason"]}')
    else:
        lines.append('- Durum değişikliği yok.')
    lines += ['', '## Durum tablosu', '',
              'Kanıt kümede sayılır (10 dk kovası); excess karar ufkunda okunur. Karakter sütunları '
              'hipotezin işlem davranışıdır: en güçlü hareket ne zaman geliyor, ne kadarı geri veriliyor.', '',
              '| Aday | Durum | Ufuk | Olay | Küme | Δ küme | HO küme | Δ HO | excess TR/HO | '
              'Tepe dk | MFE % | Geri verme % | İsabet % | Gerekçe |',
              '|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|']
    for variant, entry in state['hypotheses'].items():
        history = entry['history']
        if not history:
            continue
        current = history[-1]
        if current['round'] != last['round']:
            lines.append(f'| {variant} | {entry["status"]} (tur {current["round"]}) | — | — | — | — | — | — | — | '
                         '— | — | — | — | Menüden çıktı; kanıt olarak duruyor |')
            continue
        m = current['measure']
        previous = next((h['measure'] for h in reversed(history[:-1])), None)
        cell = decision_cell(m)
        before = decision_cell(previous) if previous else None
        ch = m.get('character') or {}
        def c(key, digits=2):
            value = ch.get(key)
            return '—' if value is None else f'{value:.{digits}f}'
        lines.append(
            f'| {variant} | {entry["status"]} | {m.get("decision_horizon") or "—"}m | {m["events"]} | '
            f'{evidence(cell, "all")} | {delta(evidence(cell, "all"), evidence(before, "all") if before else None)} | '
            f'{evidence(cell, "holdout")} | '
            f'{delta(evidence(cell, "holdout"), evidence(before, "holdout") if before else None)} | '
            f'{fmt(cell["train"]["excess"])} / {fmt(cell["holdout"]["excess"])} | '
            f'{c("peak_delay_min_median", 0)} | {c("mfe_median")} | {c("giveback_median")} | '
            f'{c("hit_pct_at_decision", 0)} | {current["reason"]} |')
    lines += ['', '## Turlar', '', '| Tur | Run | Menü | Satır | Sonuçsuz | Kayıt |', '|---:|---|---|---:|---:|---|']
    for r in rounds:
        lines.append(f'| {r["round"]} | {r["run"]} | {r["menu_version"]} | {r.get("rows")} | '
                     f'{r.get("missing_outcomes")} | {r["recorded_at"]} |')
    lines += ['', 'Durumlar: VERI_YOK · YETERSIZ (<30 olay) · IZLENIYOR (30+ olay, holdout ince) · '
              f'ADAY (iki bölümde excess>0 ve holdout {ENOUGH}+) · ELENDI (iki tur üst üste her ufukta negatif) · '
              'TARAYICI (işlem tetiği değil).', '']
    return '\n'.join(lines)


def trend(gap):
    """An improvement is only visible if the measurement stays with the gap."""
    if not gap['metric']:
        return '—'
    first, latest = gap['metric'][0], gap['metric'][-1]
    if first is latest:
        return f'{first["value"]} (tur {first["round"]})'
    return f'{first["value"]} (tur {first["round"]}) → {latest["value"]} (tur {latest["round"]})'


def render_gaps(state):
    last = state['rounds'][-1]['round'] if state['rounds'] else 0
    live = [g for g in state['gaps'] if g['state'] == 'ACIK']
    done = [g for g in state['gaps'] if g['state'] != 'ACIK']
    opened_now = [g for g in live if g['opened_round'] == last]
    closed_now = [g for g in done if g['closed_round'] == last]
    lines = ['# Eksikler defteri', '',
             f'Tur {last}. Eksikler kapanana kadar taşınır; ölçüsü olan her turda yeniden ölçülür.', '',
             f'Açık: **{len(live)}** · bu turda açılan: {len(opened_now)} · bu turda kapanan: {len(closed_now)} · '
             f'toplam kapanan: {len(done)}', '', '## Açık', '',
             '| No | Konu | Açıldığı tur | Ölçü (ilk → son) | Kapanma koşulu | Kaynak |',
             '|---|---|---:|---|---|---|']
    for gap in live:
        lines.append(f'| {gap["id"]} | {gap["title"]} | {gap["opened_round"]} | {trend(gap)} | '
                     f'{gap["close_when"]} | {gap["source"]} |')
    if not live:
        lines.append('| — | Açık eksik yok | — | — | — | — |')
    lines += ['', '## Kapanmış', '', '| No | Konu | Açık | Ölçü (ilk → son) | Kanıt |', '|---|---|---|---|---|']
    for gap in done:
        lines.append(f'| {gap["id"]} | {gap["title"]} | tur {gap["opened_round"]}–{gap["closed_round"]} | '
                     f'{trend(gap)} | {gap["evidence"]} |')
    if not done:
        lines.append('| — | Henüz kapanan yok | — | — | — |')
    lines += ['', 'Otomatik eksik, koşulu kaybolduğunda kendiliğinden kapanır. Elle açılan eksik yalnız '
              '`--gap-close` ile, kanıt yazılarak kapanır.', '']
    return '\n'.join(lines)


def ratio(reward, risk):
    """Reward over risk from the same observations; no assumed stop distance."""
    if reward is None or not risk:
        return None
    return round(reward / abs(risk), 1)


def render_manual(state):
    """Per-hypothesis usage guide, rebuilt from measurement every round.

    It is a description of observed behaviour, not permission to trade: a candidate
    that has not reached ADAY says so in its own section.
    """
    last = state['rounds'][-1]
    lines = ['# Hipotez kullanım kılavuzu', '',
             f'Tur {last["round"]} · {last["run"]} · menü `{last["menu_version"]}` · {last["recorded_at"]}', '',
             'Bu kılavuz her turda ölçümden yeniden üretilir; hipotez geliştikçe kendisi de gelişir.',
             'Sayılar **gözlenen davranıştır**, kâr vaadi değildir. Maliyet varsayımı toplam '
             f'{last.get("cost_bps_roundtrip")} bps; gerçekleşmiş komisyon/funding değildir.', '',
             '**Kanıt seviyesi nasıl okunur:** kanıt 10 dakikalık kümede sayılır, ham olayda değil — aynı kovadaki '
             f'olaylar birlikte hareket eder. Bir aday ancak karar ufkunda TRAIN ve HOLDOUT excess pozitifken ve '
             f'holdout {ENOUGH}+ kümeye ulaştığında ADAY olur. Uzun süren bir kayıt çok küme, kısa kayıt az küme '
             'ekler; kısa kayıt tek başına karar değiştirmez, yalnız kanıta eklenir.', '']
    live = [(v, e) for v, e in state['hypotheses'].items()
            if e['history'] and e['history'][-1]['round'] == last['round']]
    ranked = sorted(live, key=lambda item: (item[1]['status'] != 'ADAY', item[1]['status'] != 'IZLENIYOR',
                                            -(item[1]['history'][-1]['measure'].get('clusters') or 0)))
    for variant, entry in ranked:
        m = entry['history'][-1]['measure']
        if variant.startswith(SCANNER) or not m['events']:
            continue
        cell, ch = decision_cell(m), (m.get('character') or {})
        horizon = m.get('decision_horizon') or DECISION_HORIZONS[0]
        rr = ratio(ch.get('mfe_median'), ch.get('mae_median'))
        def g(key, digits=2, suffix=''):
            value = ch.get(key)
            return '—' if value is None else f'{value:.{digits}f}{suffix}'
        lines += [f'## {variant} — {entry["status"]}', '',
                  f'*{entry.get("description", "")}*', '',
                  f'- **Karar ufku:** {horizon} dk (ölçülen medyan tepe {g("peak_delay_min_median", 0)} dk)',
                  f'- **En güçlü hareket:** medyan {g("peak_delay_min_median", 0)} dakikada; '
                  f'tipik MFE %{g("mfe_median")}, tipik MAE %{g("mae_median")}'
                  + (f' → ödül/risk **{rr}**' if rr else ''),
                  f'- **Geri verme:** tepeden ufuk sonuna medyan %{g("giveback_median")}; '
                  f'en kötü an medyan {g("mae_delay_min_median", 0)}. dakikada',
                  f'- **İlk karşıt akış sinyali:** medyan {g("flow_opposes_min_median", 0)}. dakikada — '
                  'tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)',
                  f'- **Başarı oranı (karar ufkunda, maliyet sonrası):** %{g("hit_pct_at_decision", 0)} · '
                  f'net medyan {fmt(cell["all"]["net"])} · excess TRAIN {fmt(cell["train"]["excess"])} / '
                  f'HOLDOUT {fmt(cell["holdout"]["excess"])}',
                  f'- **Kanıt:** {m["events"]} olay / {evidence(cell, "all")} küme; holdout '
                  f'{evidence(cell, "holdout")} küme. {entry["history"][-1]["reason"]}', '']
        if entry.get('indicators'):
            lines += ['**Belirteç bütünü** (tetik anında okunan alanlar):', '']
            lines += [f'  - {item}' for item in entry['indicators']] + ['']
        plan = m.get('plan')
        if plan:
            if plan['gain'] and plan['gain'] > 0:
                lines += [f'**Plan:** `{plan["entry"]}` + `{plan["exit"]}` — aynı olaylarda taban plana göre '
                          f'**{plan["gain"]:+.3f}** (eşleşme {plan["pairs"]}), dolum %{plan["fill_pct"]}, '
                          f'isabet %{plan["hit_pct"]}, çıkış ~{plan["exit_min"]:.0f}. dakika.', '']
            else:
                lines += [f'**Plan:** taban plan (`AT_TRIGGER` + `HOLD_HORIZON`) bu adayda en iyisi; denenen '
                          f'erken çıkışların hiçbiri {plan["pairs"]} eşleşmede onu geçmedi.', '']
        buckets = sorted(m.get('coin_classes') or [], key=lambda c: -(c['net'] or 0))
        if buckets:
            good = ', '.join(f'{c["class"]} (net {c["net"]:+.2f}, isabet %{c["hit"]:.0f}, {c["filled"]} dolum)'
                             for c in buckets[:2])
            worst = buckets[-1]
            lines += [f'**Hangi coinlerde:** en iyi → {good}.',
                      f'En kötü → {worst["class"]} (net {worst["net"]:+.2f}, isabet %{worst["hit"]:.0f}, '
                      f'{worst["filled"]} dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.', '']
    scanners = [(v, e) for v, e in live if v.startswith(SCANNER)]
    if scanners:
        lines += ['## Bağlam katmanı (işlem tetiği değil)', '']
        for variant, entry in scanners:
            m = entry['history'][-1]['measure']
            lines.append(f'- **{variant}** — {entry.get("description", "")} · {m["events"]} olay / '
                         f'{m.get("clusters") or 0} küme. Yön kararı için kullanılmaz; '
                         'diğer hipotezlerin bağlamını okumak için izlenir.')
        lines.append('')
    lines += ['## Bu kılavuzun sınırları', '',
              '- Hiçbir bölüm işlem izni değildir; ADAY olmayan bir hipotez için sayılar yalnız davranış tarifidir.',
              '- Tek gün içi holdout, farklı gün OOS değildir; rejim değişince karakter de değişebilir.',
              '- MFE/MAE gözlenen snapshot fiyatlarıdır, bar içi uçlar değildir: gerçek stop bunlardan daha erken '
              'tetiklenebilir.',
              '- Ödül/risk oranı gözlenen MFE ve MAE medyanlarının oranıdır; varsayılan bir stop mesafesi değildir.', '']
    return '\n'.join(lines)

def add_gap(ledger_root, title, detail, close_when):
    state = load(ledger_root)
    round_no = state['rounds'][-1]['round'] if state['rounds'] else 0
    gap = open_gap(state, None, title, detail or '', close_when or 'Elle kapatılır', round_no, 'manual')
    save(ledger_root, state)
    return {'status': 'OPENED', 'id': gap['id'], 'title': title}


def close_gap(ledger_root, gap_id, evidence):
    state = load(ledger_root)
    gap = next((g for g in state['gaps'] if g['id'] == gap_id), None)
    if gap is None:
        raise ValueError(f'Eksik bulunamadı: {gap_id}')
    if gap['state'] != 'ACIK':
        raise ValueError(f'{gap_id} zaten kapanmış (tur {gap["closed_round"]}).')
    if not evidence:
        raise ValueError('Kapatma kanıtı yazılmalı.')
    gap.update(state='KAPANDI', closed_round=state['rounds'][-1]['round'] if state['rounds'] else 0,
               evidence=evidence)
    save(ledger_root, state)
    return {'status': 'CLOSED', 'id': gap_id, 'evidence': evidence}


def newest_run(log_root):
    runs = [p for p in sorted(Path(log_root).glob('run_*'))
            if (p / 'hypothesis_lab_v21' / 'audit.json').exists()]
    if not runs:
        raise ValueError('Lab çıktısı olan run yok; önce hypothesis_lab.py çalıştırılmalı.')
    return runs[-1]


def report(result):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, OSError):
        pass
    text = json.dumps(result, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'backslashreplace').decode('ascii'))


if __name__ == '__main__':
    here = Path(__file__).parent
    ap = argparse.ArgumentParser(description='Hipotez ve eksik defteri; yalnız en yeni run.')
    ap.add_argument('--run', help='Varsayılan: lab çıktısı olan en yeni run')
    ap.add_argument('--log-dir', default=str(here / 'logs'))
    ap.add_argument('--ledger-dir', default=str(here / 'ARASTIRMA' / 'DEFTER'))
    ap.add_argument('--note')
    ap.add_argument('--gap-add', metavar='BASLIK')
    ap.add_argument('--gap-detail', default='')
    ap.add_argument('--gap-close-when', default='')
    ap.add_argument('--gap-close', metavar='E-0001')
    ap.add_argument('--evidence', default='')
    args = ap.parse_args()
    if args.gap_add:
        report(add_gap(args.ledger_dir, args.gap_add, args.gap_detail, args.gap_close_when))
    elif args.gap_close:
        report(close_gap(args.ledger_dir, args.gap_close, args.evidence))
    else:
        report(record(args.run or newest_run(args.log_dir), args.ledger_dir, args.note))
