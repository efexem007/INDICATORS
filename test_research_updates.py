"""Probe tests for research_updates.py (incremental research inbox)."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import research_updates as ru


def snap(i, run='run_20260918_112149'):
    return {'snapshot_id': f'S{i}', 'symbol': 'TESTUSDT', 'run_id': run,
            'captured_at_ms': 1_789_730_000_000 + i * 60_000, 'price': 100 + i}


def outcome(i, complete=True, ret=0.5):
    return {'snapshot_id': f'S{i}', 'outcome_complete': complete, 'ret_20m_pct': ret}


def write_jsonl(path, rows, mode='w'):
    with path.open(mode, encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


class Fixture:
    def __init__(self, tmp, run='run_20260918_112149', n=5, meta=True):
        self.root = Path(tmp)
        self.logs = self.root / 'logs'
        self.state = self.root / 'state'
        self.run = self.logs / run
        self.run.mkdir(parents=True)
        self.snapshots = self.run / 'snapshots_20260918_11.jsonl'
        write_jsonl(self.snapshots, [snap(i) for i in range(n)])
        if meta:
            (self.run / 'run_meta.json').write_text(json.dumps({'snapshots': n}), encoding='utf-8')

    def outcomes(self, ids, complete=True, mode='w', ret=0.5):
        path = self.run / 'outcomes.jsonl'
        write_jsonl(path, [outcome(i, complete, ret) for i in ids], mode)
        return path

    def collect(self, baseline=False):
        return ru.collect(self.logs, self.state, baseline)

    def collect_at(self, now_ms):
        return ru.collect(self.logs, self.state, False, now_ms)


class IncrementalInboxTests(unittest.TestCase):
    def test_first_pass_collects_rows_and_creates_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.outcomes(range(3))
            r = fx.collect()
            self.assertEqual(r['new_snapshots'], 5)
            self.assertEqual(r['new_or_revised_outcomes'], 3)
            self.assertEqual(r['pending_outcomes'], 2)
            batch = Path(r['batch_path'])
            self.assertTrue((batch / 'manifest.json').exists())
            rows = (batch / 'new_snapshots.jsonl').read_text(encoding='utf-8').splitlines()
            self.assertEqual(len(rows), 5)

    def test_second_pass_only_reports_appended_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.outcomes(range(3))
            fx.collect()
            write_jsonl(fx.snapshots, [snap(i) for i in range(5, 8)], mode='a')
            (fx.run / 'run_meta.json').write_text(json.dumps({'snapshots': 8}), encoding='utf-8')
            fx.outcomes(range(3, 6), mode='a')
            r = fx.collect()
            self.assertEqual(r['new_snapshots'], 3)
            self.assertEqual(r['new_or_revised_outcomes'], 3)

    def test_nothing_new_creates_no_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.outcomes(range(5))
            fx.collect()
            r = fx.collect()
            self.assertEqual(r['new_snapshots'], 0)
            self.assertEqual(r['new_or_revised_outcomes'], 0)
            self.assertIsNone(r['batch_path'])

    def test_tampered_prefix_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.collect()
            rows = [snap(i) for i in range(5)]
            rows[0]['price'] = 999
            write_jsonl(fx.snapshots, rows)
            with self.assertRaisesRegex(ValueError, 'değiştirilmiş'):
                fx.collect()

    def test_truncated_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.collect()
            write_jsonl(fx.snapshots, [snap(i) for i in range(2)])
            with self.assertRaisesRegex(ValueError, 'kısalmış'):
                fx.collect()

    def test_vanished_snapshot_part_of_latest_run_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.collect()
            fx.snapshots.unlink()
            extra = fx.run / 'snapshots_20260918_12.jsonl'
            write_jsonl(extra, [snap(9)])
            with self.assertRaises(ValueError):
                fx.collect()

    def test_vanished_outcomes_source_is_rejected(self):
        """A previously processed outcomes.jsonl that disappears must not be silent."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            path = fx.outcomes(range(3))
            fx.collect()
            path.unlink()
            with self.assertRaises(ValueError):
                fx.collect()

    def test_vanished_source_of_older_run_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp, run='run_20260918_010000')
            fx.outcomes(range(3))
            fx.collect()
            newer = fx.logs / 'run_20260918_112149'
            newer.mkdir()
            write_jsonl(newer / 'snapshots_20260918_11.jsonl', [snap(7)])
            (newer / 'run_meta.json').write_text(json.dumps({'snapshots': 1}), encoding='utf-8')
            fx.snapshots.unlink()
            with self.assertRaises(ValueError):
                ru.collect(fx.logs, fx.state, False)

    def test_short_run_meta_count_blocks_partial_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            (fx.run / 'run_meta.json').write_text(json.dumps({'snapshots': 50}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'eksik'):
                fx.collect()
            db = sqlite3.connect(fx.state / 'checkpoint.sqlite')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0], 0)
            db.close()

    def test_partial_final_line_is_retried_next_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp, n=3)
            with fx.snapshots.open('a', encoding='utf-8') as f:
                f.write(json.dumps(snap(3))[:20])
            r = fx.collect()
            self.assertEqual(r['new_snapshots'], 3)
            with fx.snapshots.open('w', encoding='utf-8') as f:
                for i in range(4):
                    f.write(json.dumps(snap(i)) + '\n')
            (fx.run / 'run_meta.json').write_text(json.dumps({'snapshots': 4}), encoding='utf-8')
            r = fx.collect()
            self.assertEqual(r['new_snapshots'], 1)

    def test_incomplete_outcomes_stay_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp, n=3)
            fx.outcomes(range(3), complete=False)
            r = fx.collect()
            self.assertEqual(r['new_or_revised_outcomes'], 0)
            self.assertEqual(r['pending_outcomes'], 3)

    def test_revised_outcome_is_reported_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp, n=3)
            fx.outcomes(range(3))
            fx.collect()
            fx.outcomes(range(3), mode='a', ret=1.75)
            r = fx.collect()
            self.assertEqual(r['new_or_revised_outcomes'], 3)
            batch = Path(r['batch_path'])
            rows = [json.loads(l) for l in (batch / 'completed_outcomes.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertTrue(all(row['revision'] for row in rows))

    def test_baseline_requires_matching_audit_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            audit_dir = fx.run / 'research_shadow_v1'
            audit_dir.mkdir()
            (audit_dir / 'audit.json').write_text(json.dumps(
                {'snapshot_hashes': {'snapshots_20260918_11.jsonl': 'deadbeef'}}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Baseline'):
                fx.collect(baseline=True)

    def test_baseline_marks_reviewed_rows_without_batch(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp)
            fx.outcomes(range(5))
            audit_dir = fx.run / 'research_shadow_v1'
            audit_dir.mkdir()
            digest = hashlib.sha256(fx.snapshots.read_bytes()).hexdigest()
            (audit_dir / 'audit.json').write_text(json.dumps(
                {'snapshot_hashes': {'snapshots_20260918_11.jsonl': digest}}), encoding='utf-8')
            r = fx.collect(baseline=True)
            self.assertIsNone(r['batch_path'])
            self.assertTrue((fx.state / 'baseline.json').exists())
            write_jsonl(fx.snapshots, [snap(9)], mode='a')
            (fx.run / 'run_meta.json').write_text(json.dumps({'snapshots': 6}), encoding='utf-8')
            r2 = fx.collect()
            self.assertEqual(r2['new_snapshots'], 1)

    def test_ripe_gap_is_separated_from_immature_wait(self):
        """A stopped run's overdue snapshot is an actionable gap, not a wait."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp, n=3)
            (fx.run / 'run_meta.json').write_text(
                json.dumps({'snapshots': 3, 'stopped_at_ms': snap(2)['captured_at_ms']}), encoding='utf-8')
            young = snap(2)['captured_at_ms'] + 10 * 60_000
            r = fx.collect_at(young)
            self.assertEqual(r['pending_outcomes'], 3)
            self.assertEqual(r['ripe_missing_outcomes'], 0)
            self.assertEqual(r['immature_outcomes'], 3)
            self.assertFalse([i for i in r['issues'] if 'SONUCLARI_HESAPLA' in i])
            old = snap(2)['captured_at_ms'] + 120 * 60_000
            r2 = fx.collect_at(old)
            self.assertEqual(r2['ripe_missing_outcomes'], 3)
            self.assertEqual(r2['immature_outcomes'], 0)
            self.assertTrue([i for i in r2['issues'] if 'SONUCLARI_HESAPLA' in i])

    def test_live_run_gets_grace_before_a_gap_is_declared(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp, n=1)
            just_past_horizon = snap(0)['captured_at_ms'] + 63 * 60_000
            self.assertEqual(fx.collect_at(just_past_horizon)['ripe_missing_outcomes'], 0)
            (fx.run / 'run_meta.json').write_text(
                json.dumps({'snapshots': 1, 'stopped_at_ms': snap(0)['captured_at_ms']}), encoding='utf-8')
            self.assertEqual(fx.collect_at(just_past_horizon)['ripe_missing_outcomes'], 1)

    def test_completed_outcomes_clear_the_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp, n=3)
            (fx.run / 'run_meta.json').write_text(
                json.dumps({'snapshots': 3, 'stopped_at_ms': snap(2)['captured_at_ms']}), encoding='utf-8')
            old = snap(2)['captured_at_ms'] + 120 * 60_000
            self.assertEqual(fx.collect_at(old)['ripe_missing_outcomes'], 3)
            fx.outcomes(range(3))
            r = fx.collect_at(old)
            self.assertEqual(r['ripe_missing_outcomes'], 0)
            self.assertEqual(r['pending_outcomes'], 0)

    def test_mark_reviewed_records_report_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(tmp, n=2)
            r = fx.collect()
            batch_id = r['awaiting_review'][0]['id']
            report = fx.root / 'RAPOR.md'
            report.write_text('inceleme', encoding='utf-8')
            ru.mark_reviewed(fx.state, batch_id, report)
            db = sqlite3.connect(fx.state / 'checkpoint.sqlite')
            self.assertEqual(db.execute('SELECT status FROM batches WHERE id=?', (batch_id,)).fetchone()[0], 'REVIEWED')
            db.close()
            self.assertTrue((Path(r['batch_path']) / 'review.json').exists())
            r2 = fx.collect()
            self.assertEqual(r2['awaiting_review'], [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
