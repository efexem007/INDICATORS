"""Ledger tests: a round must add evidence, never repeat or invent it."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

import research_ledger as rl


def spec(events=10, all_n=10, train=(-0.1, 10), holdout=(-0.1, 5), clusters=None, peak=30.0):
    """One variant's cell values: (excess, n) per split, same for both horizons.

    Clusters default to n, so a test that says 30 means 30 independent observations.
    """
    cells = {'events': events, 'all': (0.0, all_n), 'train': train, 'holdout': holdout, 'peak': peak}
    cells['clusters'] = clusters or {'all': all_n, 'train': train[1], 'holdout': holdout[1]}
    return cells


class Run:
    """A fake lab output folder: only what the ledger actually reads."""

    def __init__(self, root, name='run_20260918_112149', version='hypothesis-candidates-v2.2',
                 replay='sha-1', missing=0, censored=0, rows=6100, decision_h=20, drift=(), code='c1'):
        self.path = Path(root) / 'logs' / name
        self.lab = self.path / 'hypothesis_lab_v21'
        self.lab.mkdir(parents=True, exist_ok=True)
        self.version, self.replay, self.missing, self.censored, self.rows = version, replay, missing, censored, rows
        self.decision_h, self.drift, self.code = decision_h, list(drift), code

    def write(self, variants):
        with (self.lab / 'entry_summary.csv').open('w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['variant', 'split', 'horizon', 'events', 'n', 'clusters', 'decision',
                             'median', 'mean', 'hit_pct', 'excess_median', 'status'])
            for variant, s in variants.items():
                for horizon in rl.DECISION_HORIZONS:
                    for split in ('ALL', 'TRAIN', 'HOLDOUT'):
                        excess, n = s[split.lower()]
                        writer.writerow([variant, split, horizon, s['events'], n, s['clusters'][split.lower()],
                                         horizon == self.decision_h, 0.12, 0.1, 50.0,
                                         '' if excess is None else excess, 'SINGLE_RUN_EXPLORATORY'])
        with (self.lab / 'character.csv').open('w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['variant', 'split', 'shaped', 'peak_delay_min_median', 'rule_horizon',
                             'mfe_median', 'mae_median', 'giveback_median', 'mae_delay_min_median',
                             'flow_opposes_min_median', 'hit_pct_at_decision'])
            for variant, s in variants.items():
                writer.writerow([variant, 'ALL', s['events'], s['peak'], self.decision_h,
                                 1.0, -0.3, 0.25, 12, 6, 64.0])
        with (self.lab / 'exit_summary.csv').open('w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['variant', 'split', 'horizon', 'policy', 'n', 'censored'])
            writer.writerow(['H1_BASE', 'ALL', 20, 'FLOW_STRUCTURE', 100 - self.censored, self.censored])
        (self.lab / 'audit.json').write_text(json.dumps(
            {'version': self.version, 'replay_sha256': self.replay, 'rows': self.rows,
             'missing_outcomes': self.missing, 'cost_bps_roundtrip': 10, 'horizon_drift': self.drift,
             'code_hashes': {'hypothesis_lab.py': self.code},
             'candidate_menu': {v: v for v in variants}}), encoding='utf-8')
        return self.path


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ledger = self.root / 'DEFTER'
        self.addCleanup(self.tmp.cleanup)

    def state(self):
        return json.loads((self.ledger / 'ledger.json').read_text(encoding='utf-8'))

    def test_first_round_records_every_variant_and_writes_both_books(self):
        run = Run(self.root).write({'H1_BASE': spec(), 'H6_RESET': spec()})
        result = rl.record(run, self.ledger)
        self.assertEqual(result['status'], 'RECORDED')
        self.assertEqual(result['round'], 1)
        state = self.state()
        self.assertEqual(set(state['hypotheses']), {'H1_BASE', 'H6_RESET'})
        self.assertEqual(state['hypotheses']['H6_RESET']['status'], 'TARAYICI')
        self.assertTrue((self.ledger / 'HIPOTEZ_DEFTERI.md').exists())
        self.assertTrue((self.ledger / 'EKSIKLER.md').exists())
        self.assertIn('H1_BASE', (self.ledger / 'HIPOTEZ_DEFTERI.md').read_text(encoding='utf-8'))

    def test_same_run_same_fingerprint_adds_no_round(self):
        run = Run(self.root).write({'H1_BASE': spec()})
        rl.record(run, self.ledger)
        again = rl.record(run, self.ledger)
        self.assertEqual(again['status'], 'NO_NEW_EVIDENCE')
        self.assertEqual(len(self.state()['rounds']), 1)

    def test_new_menu_on_the_same_evidence_revises_the_round(self):
        run = Run(self.root)
        rl.record(run.write({'H1_BASE': spec()}), self.ledger)
        run.version = 'hypothesis-candidates-v2.3'
        result = rl.record(run.write({'H1_BASE': spec(), 'H1_SLOW_SETUP': spec(events=4)}), self.ledger)
        self.assertEqual(result['round'], 1)                     # same data: one round, revised
        self.assertEqual(len(self.state()['rounds']), 1)
        self.assertEqual(self.state()['rounds'][0]['revisions'], 1)
        self.assertEqual(self.state()['hypotheses']['H1_SLOW_SETUP']['first_round'], 1)
        self.assertEqual(len(self.state()['hypotheses']['H1_BASE']['history']), 1)

    def test_more_outcomes_on_the_same_run_open_a_round(self):
        run = Run(self.root, replay='sha-1')
        rl.record(run.write({'H1_BASE': spec()}), self.ledger)
        run.replay = 'sha-2'
        self.assertEqual(rl.record(run.write({'H1_BASE': spec()}), self.ledger)['round'], 2)

    def test_zero_trigger_opens_a_gap_that_closes_when_the_trigger_appears(self):
        run = Run(self.root, name='run_20260918_112149')
        rl.record(run.write({'H4_BASE': spec(events=0, all_n=0, train=(None, 0), holdout=(None, 0))}), self.ledger)
        self.assertEqual(self.state()['hypotheses']['H4_BASE']['status'], 'VERI_YOK')
        gap = next(g for g in self.state()['gaps'] if g['key'] == 'auto:no-trigger:H4_BASE')
        self.assertEqual(gap['state'], 'ACIK')

        later = Run(self.root, name='run_20260919_090000', replay='sha-9')
        result = rl.record(later.write({'H4_BASE': spec(events=12)}), self.ledger)
        closed = next(g for g in self.state()['gaps'] if g['key'] == 'auto:no-trigger:H4_BASE')
        self.assertEqual(closed['state'], 'KAPANDI')
        self.assertEqual(closed['closed_round'], 2)
        self.assertIn(closed['id'], result['gaps_closed'])
        self.assertEqual(self.state()['hypotheses']['H4_BASE']['status'], 'YETERSIZ')

    def test_candidate_needs_positive_excess_in_both_splits_and_a_thick_holdout(self):
        thin = Run(self.root).write({'H1_BASE': spec(events=90, all_n=90, train=(0.2, 60), holdout=(0.3, 29))})
        rl.record(thin, self.ledger)
        self.assertEqual(self.state()['hypotheses']['H1_BASE']['status'], 'IZLENIYOR')

        run = Run(self.root, name='run_20260919_090000', replay='sha-9')
        rl.record(run.write({'H1_BASE': spec(events=90, all_n=90, train=(0.2, 60), holdout=(0.3, 30))}), self.ledger)
        self.assertEqual(self.state()['hypotheses']['H1_BASE']['status'], 'ADAY')

    def test_one_split_positive_is_not_a_candidate(self):
        run = Run(self.root).write({'H1_BASE': spec(events=90, all_n=90, train=(-0.2, 60), holdout=(0.3, 40))})
        rl.record(run, self.ledger)
        self.assertEqual(self.state()['hypotheses']['H1_BASE']['status'], 'IZLENIYOR')

    def test_elimination_needs_two_consecutive_negative_rounds(self):
        first = Run(self.root).write({'H2_BASE': spec(events=40, all_n=40, train=(-0.2, 30), holdout=(-0.3, 10))})
        rl.record(first, self.ledger)
        self.assertEqual(self.state()['hypotheses']['H2_BASE']['status'], 'IZLENIYOR')
        second = Run(self.root, name='run_20260919_090000', replay='sha-9')
        rl.record(second.write({'H2_BASE': spec(events=40, all_n=40, train=(-0.1, 30), holdout=(-0.2, 12))}),
                  self.ledger)
        self.assertEqual(self.state()['hypotheses']['H2_BASE']['status'], 'ELENDI')

    def test_a_tiny_sample_is_never_eliminated(self):
        small = spec(events=4, all_n=4, train=(-0.9, 3), holdout=(-0.9, 1))
        rl.record(Run(self.root).write({'H3_SLOW_SETUP': small}), self.ledger)
        rl.record(Run(self.root, name='run_20260919_090000', replay='sha-9').write({'H3_SLOW_SETUP': small}),
                  self.ledger)
        self.assertEqual(self.state()['hypotheses']['H3_SLOW_SETUP']['status'], 'YETERSIZ')

    def test_status_change_is_listed_once_with_its_reason(self):
        rl.record(Run(self.root).write({'H1_BASE': spec(events=0, all_n=0, train=(None, 0), holdout=(None, 0))}),
                  self.ledger)
        steady = spec(events=12, all_n=12, train=(0.1, 9), holdout=(0.2, 3))
        result = rl.record(Run(self.root, name='run_20260919_090000', replay='sha-9')
                           .write({'H1_BASE': steady}), self.ledger)
        self.assertEqual([c['variant'] for c in result['status_changes']], ['H1_BASE'])
        self.assertEqual(result['status_changes'][0]['from'], 'VERI_YOK')
        third = rl.record(Run(self.root, name='run_20260920_090000', replay='sha-10')
                          .write({'H1_BASE': steady}), self.ledger)
        self.assertEqual(third['status_changes'], [])

    def test_gap_metric_keeps_its_trend(self):
        rl.record(Run(self.root, missing=327).write({'H1_BASE': spec()}), self.ledger)
        rl.record(Run(self.root, name='run_20260919_090000', replay='sha-9', missing=40)
                  .write({'H1_BASE': spec()}), self.ledger)
        gap = next(g for g in self.state()['gaps'] if g['key'] == 'auto:missing-outcomes')
        self.assertEqual([m['value'] for m in gap['metric']], [327, 40])
        rl.record(Run(self.root, name='run_20260920_090000', replay='sha-10', missing=0)
                  .write({'H1_BASE': spec()}), self.ledger)
        gap = next(g for g in self.state()['gaps'] if g['key'] == 'auto:missing-outcomes')
        self.assertEqual(gap['state'], 'KAPANDI')
        self.assertIn('327 (tur 1) → 40 (tur 2)', (self.ledger / 'EKSIKLER.md').read_text(encoding='utf-8'))

    def test_second_day_closes_the_single_day_gap(self):
        rl.record(Run(self.root).write({'H1_BASE': spec()}), self.ledger)
        self.assertTrue(any(g['key'] == 'auto:single-day' and g['state'] == 'ACIK' for g in self.state()['gaps']))
        result = rl.record(Run(self.root, name='run_20260919_090000', replay='sha-9').write({'H1_BASE': spec()}),
                           self.ledger)
        self.assertEqual(result['distinct_days'], 2)
        self.assertTrue(any(g['key'] == 'auto:single-day' and g['state'] == 'KAPANDI' for g in self.state()['gaps']))

    def test_manual_gaps_are_seeded_once_and_survive_rounds(self):
        rl.record(Run(self.root).write({'H1_BASE': spec()}), self.ledger)
        rl.record(Run(self.root, name='run_20260919_090000', replay='sha-9').write({'H1_BASE': spec()}), self.ledger)
        manual = [g for g in self.state()['gaps'] if g['source'] == 'manual']
        self.assertEqual(len(manual), len(rl.SEED_GAPS))
        self.assertTrue(all(g['state'] == 'ACIK' for g in manual))

    def test_manual_gap_closes_only_with_evidence(self):
        rl.record(Run(self.root).write({'H1_BASE': spec()}), self.ledger)
        opened = rl.add_gap(self.ledger, 'Gerçek Binance duman testi', 'WARP kapalıyken erişim yok', 'Testin geçmesi')
        with self.assertRaises(ValueError):
            rl.close_gap(self.ledger, opened['id'], '')
        rl.close_gap(self.ledger, opened['id'], 'WARP açıkken 221 pencere hatasız.')
        with self.assertRaises(ValueError):
            rl.close_gap(self.ledger, opened['id'], 'ikinci kez')
        gap = next(g for g in self.state()['gaps'] if g['id'] == opened['id'])
        self.assertEqual(gap['state'], 'KAPANDI')
        self.assertIn('221 pencere', (self.ledger / 'EKSIKLER.md').read_text(encoding='utf-8'))

    def test_unknown_gap_id_is_rejected(self):
        rl.record(Run(self.root).write({'H1_BASE': spec()}), self.ledger)
        with self.assertRaises(ValueError):
            rl.close_gap(self.ledger, 'E-9999', 'kanıt')

    def test_variant_dropped_from_the_menu_is_kept_as_evidence(self):
        rl.record(Run(self.root).write({'H1_BASE': spec(), 'H2_GAP_EXPANDS': spec()}), self.ledger)
        result = rl.record(Run(self.root, name='run_20260919_090000', replay='sha-9').write({'H1_BASE': spec()}),
                           self.ledger)
        self.assertEqual(result['retired'], ['H2_GAP_EXPANDS'])
        entry = self.state()['hypotheses']['H2_GAP_EXPANDS']
        self.assertEqual(entry['retired_round'], 2)
        self.assertEqual(len(entry['history']), 1)
        self.assertIn('Menüden çıktı', (self.ledger / 'HIPOTEZ_DEFTERI.md').read_text(encoding='utf-8'))

    def test_censored_exit_share_opens_and_closes_its_own_gap(self):
        rl.record(Run(self.root, censored=60).write({'H1_BASE': spec()}), self.ledger)
        self.assertTrue(any(g['key'] == 'auto:censored-exits' for g in self.state()['gaps']))
        rl.record(Run(self.root, name='run_20260919_090000', replay='sha-9', censored=5).write({'H1_BASE': spec()}),
                  self.ledger)
        gap = next(g for g in self.state()['gaps'] if g['key'] == 'auto:censored-exits')
        self.assertEqual(gap['state'], 'KAPANDI')

    def test_foreign_schema_is_refused(self):
        self.ledger.mkdir(parents=True)
        (self.ledger / 'ledger.json').write_text('{"schema": "başka-defter"}', encoding='utf-8')
        with self.assertRaises(ValueError):
            rl.record(Run(self.root).write({'H1_BASE': spec()}), self.ledger)

    def test_newest_run_needs_a_lab_output(self):
        (self.root / 'logs' / 'run_20260918_000000').mkdir(parents=True)
        with self.assertRaises(ValueError):
            rl.newest_run(self.root / 'logs')
        Run(self.root, name='run_20260918_112149').write({'H1_BASE': spec()})
        self.assertEqual(rl.newest_run(self.root / 'logs').name, 'run_20260918_112149')

    def test_delta_columns_report_growth_against_the_previous_round(self):
        rl.record(Run(self.root).write({'H1_BASE': spec(events=10, holdout=(-0.1, 5))}), self.ledger)
        rl.record(Run(self.root, name='run_20260919_090000', replay='sha-9')
                  .write({'H1_BASE': spec(events=18, all_n=18, holdout=(-0.1, 9))}), self.ledger)
        row = next(line for line in (self.ledger / 'HIPOTEZ_DEFTERI.md').read_text(encoding='utf-8').splitlines()
                   if line.startswith('| H1_BASE |'))
        self.assertIn('| +8 |', row)
        self.assertIn('| +4 |', row)

    def test_clusters_not_raw_events_decide_the_status(self):
        crowded = spec(events=40, all_n=40, train=(0.2, 30), holdout=(0.3, 10),
                       clusters={'all': 6, 'train': 5, 'holdout': 2})
        rl.record(Run(self.root).write({'H1_BASE': crowded}), self.ledger)
        entry = self.state()['hypotheses']['H1_BASE']
        self.assertEqual(entry['status'], 'YETERSIZ')
        self.assertIn('küme', entry['history'][-1]['reason'])

    def test_decision_horizon_cell_is_the_one_that_judges(self):
        run = Run(self.root, decision_h=60)
        run.write({'H1_BASE': spec(events=90, all_n=90, train=(0.2, 60), holdout=(0.3, 31))})
        rows = list(csv.DictReader((run.lab / 'entry_summary.csv').open(encoding='utf-8')))
        self.assertTrue(any(r['decision'] == 'True' and r['horizon'] == '60' for r in rows))
        rl.record(run.path, self.ledger)
        entry = self.state()['hypotheses']['H1_BASE']
        self.assertEqual(entry['status'], 'ADAY')
        self.assertIn('60m', entry['history'][-1]['reason'])
        self.assertEqual(entry['history'][-1]['measure']['decision_horizon'], 60)

    def test_character_is_carried_and_rendered(self):
        rl.record(Run(self.root).write({'H3_RETEST': spec(peak=42.0)}), self.ledger)
        character = self.state()['hypotheses']['H3_RETEST']['history'][-1]['measure']['character']
        self.assertEqual(character['peak_delay_min_median'], 42.0)
        self.assertEqual(character['giveback_median'], 0.25)
        row = next(line for line in (self.ledger / 'HIPOTEZ_DEFTERI.md').read_text(encoding='utf-8').splitlines()
                   if line.startswith('| H3_RETEST |'))
        self.assertIn('| 42 |', row)
        self.assertIn('| 64 |', row)

    def test_horizon_drift_opens_and_closes_its_gap(self):
        drift = [{'variant': 'H8_IGNITION', 'measured_peak_min': 58, 'rule_horizon': 60, 'frozen_horizon': 20}]
        rl.record(Run(self.root, drift=drift).write({'H8_IGNITION': spec()}), self.ledger)
        gap = next(g for g in self.state()['gaps'] if g['key'] == 'auto:horizon-drift')
        self.assertEqual(gap['metric'][0]['value'], 1)
        rl.record(Run(self.root, name='run_20260919_090000', replay='sha-9').write({'H8_IGNITION': spec()}),
                  self.ledger)
        self.assertEqual(next(g for g in self.state()['gaps'] if g['key'] == 'auto:horizon-drift')['state'], 'KAPANDI')

    def test_three_flat_rounds_open_a_stagnation_gap(self):
        flat = spec(events=12, all_n=12, train=(0.1, 9), holdout=(0.2, 3))
        result = None
        for name, sha in (('run_20260918_112149', 'a'), ('run_20260919_090000', 'b'), ('run_20260920_090000', 'c')):
            result = rl.record(Run(self.root, name=name, replay=sha).write({'H1_BASE': flat}), self.ledger)
        gap = next(g for g in self.state()['gaps'] if g['key'] == 'auto:stagnant:H1_BASE')
        self.assertEqual(gap['opened_round'], 3)
        self.assertIn(gap['id'], result['gaps_opened'])

    def test_growing_evidence_is_not_stagnation(self):
        for name, sha, holdout_n in (('run_20260918_112149', 'a', 3), ('run_20260919_090000', 'b', 5),
                                     ('run_20260920_090000', 'c', 9)):
            rl.record(Run(self.root, name=name, replay=sha)
                      .write({'H1_BASE': spec(events=12, all_n=12, train=(0.1, 9), holdout=(0.2, holdout_n))}),
                      self.ledger)
        self.assertFalse(any(g['key'] == 'auto:stagnant:H1_BASE' for g in self.state()['gaps']))

    def test_manual_is_written_with_success_and_risk_per_hypothesis(self):
        rl.record(Run(self.root).write({'H3_RETEST': spec(events=27, peak=42.0), 'H6_RESET': spec()}), self.ledger)
        manual = (self.ledger / 'KULLANIM_KILAVUZU.md').read_text(encoding='utf-8')
        self.assertIn('H3_RETEST', manual)
        self.assertIn('%64', manual)          # hit rate at the decision horizon
        self.assertIn('42 dk', manual)        # time to the strongest move
        self.assertIn('3.3', manual)          # reward/risk from MFE 1.00 vs MAE -0.30
        self.assertIn('H6_RESET', manual)     # scanners are listed as context, not as entries

    def test_remeasuring_one_run_revises_it_and_cannot_eliminate(self):
        negative = spec(events=40, all_n=40, train=(-0.2, 30), holdout=(-0.3, 10))
        rl.record(Run(self.root, code='c1').write({'H2_BASE': negative}), self.ledger)
        second = rl.record(Run(self.root, code='c2').write({'H2_BASE': negative}), self.ledger)
        self.assertEqual(second['round'], 1)                       # new code, same data: revision
        self.assertEqual(self.state()['hypotheses']['H2_BASE']['status'], 'IZLENIYOR')  # same data, no verdict
        rl.record(Run(self.root, name='run_20260919_090000', replay='sha-9').write({'H2_BASE': negative}),
                  self.ledger)
        self.assertEqual(self.state()['hypotheses']['H2_BASE']['status'], 'ELENDI')

    def test_revision_does_not_stack_gaps_or_seed_twice(self):
        run = Run(self.root, missing=10)
        rl.record(run.write({'H4_BASE': spec(events=0, all_n=0, train=(None, 0), holdout=(None, 0))}), self.ledger)
        first = [g['id'] for g in self.state()['gaps']]
        run.code = 'c2'
        rl.record(run.write({'H4_BASE': spec(events=0, all_n=0, train=(None, 0), holdout=(None, 0))}), self.ledger)
        state = self.state()
        self.assertEqual(len(state['gaps']), len(first))                       # no duplicates
        self.assertEqual(len([g for g in state['gaps'] if g['source'] == 'manual']), len(rl.SEED_GAPS))
        missing = next(g for g in state['gaps'] if g['key'] == 'auto:missing-outcomes')
        self.assertEqual([m['round'] for m in missing['metric']], [1])          # one metric per round


if __name__ == '__main__':
    unittest.main(verbosity=2)
