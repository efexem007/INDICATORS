"""Incremental research inbox: latest run's new rows + pending outcome updates.

No archive scan and no threshold optimization. SQLite offsets are committed only
after a durable batch export. Prior reports remain evidence; batches await review.

A processed source that disappears or changes stops the run instead of shrinking
the evidence silently. Missing outcomes are split: ripe ones are a real gap that
SONUCLARI_HESAPLA.bat can close, immature ones only need time.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time
import uuid

# tracker_v2 declares an outcome mature at t0 + 60m + 30s, plus a 6 minute grace
# period while its own run is still writing. The same bound is used here so that a
# still-missing outcome is only called a gap when it could already be computed.
OUTCOME_HORIZON_MS = 60 * 60_000 + 30_000
LIVE_RUN_GRACE_MS = 6 * 60_000


def block_hash(f, start, length):
    f.seek(start)
    return hashlib.sha256(f.read(length)).hexdigest()


def ripe_before_ms(log_root, run_name, now_ms):
    """Snapshots captured at or before this are old enough to have an outcome."""
    meta_path = Path(log_root)/run_name/'run_meta.json'
    stopped = False
    if meta_path.exists():
        try:
            stopped = bool(json.loads(meta_path.read_text(encoding='utf-8')).get('stopped_at_ms'))
        except ValueError:
            stopped = False
    return now_ms - OUTCOME_HORIZON_MS - (0 if stopped else LIVE_RUN_GRACE_MS)


def read_appended(db, path):
    key = str(path.resolve())
    saved = db.execute('SELECT offset,head,tail FROM sources WHERE path=?', (key,)).fetchone()
    offset, head, tail = saved if saved else (0, None, None)
    with path.open('rb') as f:
        if path.stat().st_size < offset:
            raise ValueError(f'İşlenmiş kaynak kısalmış: {path.name}; önceki inceleme geçerliliğini kontrol edin.')
        span = min(offset, 4096)
        if offset and (block_hash(f, 0, span) != head or block_hash(f, offset-span, span) != tail):
            raise ValueError(f'İşlenmiş kaynak değiştirilmiş: {path.name}; otomatik olarak yeniden analiz edilmedi.')
        f.seek(offset)
        records = []
        while True:
            line = f.readline()
            if not line or not line.endswith(b'\n'):
                break  # a writer's partial final row is retried on the next invocation
            try:
                record = json.loads(line)
            except ValueError as e:
                raise ValueError(f'Bozuk yeni JSONL satırı: {path.name}, byte {offset}') from e
            records.append(record)
            offset = f.tell()
        span = min(offset, 4096)
        db.execute('INSERT OR REPLACE INTO sources VALUES (?,?,?,?)',
                   (key, offset, block_hash(f, 0, span), block_hash(f, offset-span, span)))
    return records


def collect(log_root, state_root, baseline=False, now_ms=None):
    log_root, state_root = Path(log_root), Path(state_root)
    runs = sorted(p for p in log_root.glob('run_*') if p.is_dir())
    if not runs:
        raise ValueError('Yeni run bulunamadı.')
    latest = runs[-1]
    paths = sorted(latest.glob('snapshots_*.jsonl'))
    if not paths and (latest/'snapshots.jsonl').exists(): paths = [latest/'snapshots.jsonl']
    if not paths: raise ValueError('En yeni run içinde snapshot yok.')
    if baseline:
        audit_path = latest/'research_shadow_v1'/'audit.json'
        if not audit_path.exists(): raise ValueError('Başlangıç işareti için önce bu runın inceleme audit.json dosyası gerekir.')
        audit = json.loads(audit_path.read_text(encoding='utf-8'))
        for path in paths:
            if audit['snapshot_hashes'].get(path.name) != hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError('Baseline raporundan sonra kaynak değişmiş; yeni kayıtları incelenmiş sayamam.')
    state_root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(state_root/'checkpoint.sqlite')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS sources(path TEXT PRIMARY KEY, offset INTEGER, head TEXT, tail TEXT);
        CREATE TABLE IF NOT EXISTS snapshots(run TEXT, id TEXT, raw TEXT, complete INTEGER DEFAULT 0,
                                             captured_at_ms INTEGER, PRIMARY KEY(run,id));
        CREATE TABLE IF NOT EXISTS outcomes(run TEXT, id TEXT, payload TEXT, PRIMARY KEY(run,id));
        CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY, path TEXT, status TEXT, created_at TEXT);
    ''')
    if 'captured_at_ms' not in {row[1] for row in db.execute('PRAGMA table_info(snapshots)')}:
        db.execute('ALTER TABLE snapshots ADD COLUMN captured_at_ms INTEGER')
    db.commit()
    fresh, completed, issues = [], [], []
    try:
        db.execute('BEGIN IMMEDIATE')
        known_paths = [Path(row[0]) for row in db.execute('SELECT path FROM sources')]
        vanished = sorted(str(p) for p in known_paths if not p.exists())
        if vanished:
            raise ValueError('İşlenmiş kaynaklardan biri artık yok; eksik set tam sayılmadı: '
                             + ', '.join(vanished))
        for path in paths:
            for s in read_appended(db, path):
                if not isinstance(s, dict) or not s.get('snapshot_id'):
                    raise ValueError(f'Geçersiz snapshot: {path.name}')
                payload = json.dumps(s, ensure_ascii=False, separators=(',', ':'))
                captured = s.get('captured_at_ms') if isinstance(s.get('captured_at_ms'), (int, float)) else None
                inserted = db.execute('INSERT OR IGNORE INTO snapshots(run,id,raw,captured_at_ms) VALUES (?,?,?,?)',
                                      (latest.name, s['snapshot_id'], payload, captured)).rowcount
                if inserted: fresh.append(s)
        meta_path = latest/'run_meta.json'
        if meta_path.exists():
            expected = json.loads(meta_path.read_text(encoding='utf-8')).get('snapshots', 0)
            actual = db.execute('SELECT COUNT(*) FROM snapshots WHERE run=?', (latest.name,)).fetchone()[0]
            if expected > actual:
                raise ValueError(f'En yeni run kaynakları eksik: beklenen {expected}, okunan {actual}.')
        pending_runs = {r[0] for r in db.execute('SELECT DISTINCT run FROM snapshots WHERE complete=0')}
        for run_name in sorted(pending_runs | {latest.name}):
            path = log_root/run_name/'outcomes.jsonl'
            if not path.exists():
                issues.append(f'{run_name}: outcome dosyası henüz yok')
                continue
            for o in read_appended(db, path):
                if o.get('outcome_complete') is not True: continue
                sid = o['snapshot_id']
                item = db.execute('SELECT raw,complete FROM snapshots WHERE run=? AND id=?', (run_name,sid)).fetchone()
                if item is None: continue
                payload = json.dumps(o, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
                previous = db.execute('SELECT payload FROM outcomes WHERE run=? AND id=?', (run_name,sid)).fetchone()
                if previous and previous[0] == payload: continue
                db.execute('INSERT OR REPLACE INTO outcomes VALUES (?,?,?)', (run_name,sid,payload))
                db.execute('UPDATE snapshots SET complete=1,raw=NULL WHERE run=? AND id=?', (run_name,sid))
                completed.append({'run':run_name,'snapshot_id':sid,'snapshot':json.loads(item[0]) if item[0] else None,
                                  'outcome':o,'revision':bool(previous)})
        now_ms = int(time.time()*1000) if now_ms is None else now_ms
        per_run = db.execute('SELECT run,COUNT(*) FROM snapshots WHERE complete=0 GROUP BY run').fetchall()
        pending = sum(count for _, count in per_run)
        ripe = sum(db.execute('SELECT COUNT(*) FROM snapshots WHERE run=? AND complete=0 AND '
                              'captured_at_ms IS NOT NULL AND captured_at_ms<=?',
                              (run_name, ripe_before_ms(log_root, run_name, now_ms))).fetchone()[0]
                   for run_name, _ in per_run)
        if ripe:
            issues.append(f'{ripe} snapshot ufku dolduğu hâlde sonuçsuz; SONUCLARI_HESAPLA.bat tamamlayabilir.')
        counts = {'pending_outcomes': pending, 'ripe_missing_outcomes': ripe, 'immature_outcomes': pending-ripe}
        batch_path = None
        if (fresh or completed) and not baseline:
            batch_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
            batch_path = state_root/'batches'/batch_id
            batch_path.mkdir(parents=True)
            for name, rows in [('new_snapshots',fresh), ('completed_outcomes',completed)]:
                with (batch_path/(name+'.jsonl')).open('w',encoding='utf-8') as f:
                    for row in rows: f.write(json.dumps(row,ensure_ascii=False)+'\n')
            summary = {'latest_run':latest.name,'new_snapshots':len(fresh),'new_or_revised_outcomes':len(completed),
                       **counts,'issues':issues,'status':'AWAITING_REVIEW',
                       'scope':'Only appended latest-run snapshots and newly completed pending outcomes. No archive rescan.'}
            (batch_path/'manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
            db.execute('INSERT INTO batches VALUES (?,?,?,?)', (batch_id,str(batch_path),'AWAITING_REVIEW',datetime.now(timezone.utc).isoformat()))
        if baseline:
            baseline_note = {'run':latest.name,'review':'research_shadow_v1 + hypothesis_lab_v21',
                             'snapshots_marked':len(fresh),'outcomes_marked':len(completed),**counts}
            (state_root/'baseline.json').write_text(json.dumps(baseline_note,ensure_ascii=False,indent=2),encoding='utf-8')
        db.commit()
        waiting = [{'id':r[0],'path':r[1]} for r in db.execute("SELECT id,path FROM batches WHERE status='AWAITING_REVIEW' ORDER BY created_at")]
        result = {'latest_run':latest.name,'new_snapshots':len(fresh),'new_or_revised_outcomes':len(completed),
                  **counts,'batch_path':str(batch_path) if batch_path else None,
                  'awaiting_review':waiting,'baseline':baseline,'issues':issues}
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def mark_reviewed(state_root, batch_id, report_path):
    report_path = Path(report_path).resolve()
    if not report_path.is_file(): raise ValueError('İnceleme raporu mevcut olmalı.')
    db = sqlite3.connect(Path(state_root)/'checkpoint.sqlite')
    try:  # sqlite3's context manager commits but never closes; the handle must not leak
        with db:
            row = db.execute('SELECT path FROM batches WHERE id=?', (batch_id,)).fetchone()
            if row is None: raise ValueError('Batch bulunamadı.')
            path = Path(row[0])/'review.json'
            path.write_text(json.dumps({'report':str(report_path),'sha256':hashlib.sha256(report_path.read_bytes()).hexdigest()},indent=2),encoding='utf-8')
            db.execute("UPDATE batches SET status='REVIEWED' WHERE id=?", (batch_id,))
    finally:
        db.close()


def report(result):
    """Console output is a view, never part of collect's contract.

    A Windows console without UTF-8 must not turn a committed batch into a
    'kaynak kontrolu basarisiz' message: the offsets have already advanced, so a
    crash here would tell the user nothing was read while the next pass skips
    those rows.
    """
    try: sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, OSError): pass
    text = json.dumps(result, ensure_ascii=False, indent=2)
    try: print(text)
    except UnicodeEncodeError: print(text.encode('ascii', 'backslashreplace').decode('ascii'))


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--log-dir',default=str(Path(__file__).parent/'logs'))
    ap.add_argument('--state-dir',default=str(Path(__file__).parent/'ARASTIRMA'/'YENI_VERI_TAKIBI'))
    ap.add_argument('--baseline-latest',action='store_true')
    ap.add_argument('--reviewed',metavar='BATCH_ID')
    ap.add_argument('--report')
    args=ap.parse_args()
    if args.reviewed:
        if not args.report:ap.error('--reviewed requires --report')
        mark_reviewed(args.state_dir,args.reviewed,args.report)
    else:
        report(collect(args.log_dir,args.state_dir,args.baseline_latest))
