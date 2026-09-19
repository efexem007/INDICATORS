import copy
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import tracker_v2 as tv
import shadow_research as sh
from research_report import candles


def snapshot(now=1_800_000_000_000, **updates):
    s = dict(run_id='test', symbol='TESTUSDT', snapshot_id=str(now), captured_at_ms=now,
             kline_asof_ms=now, price=100, clock_synced=True, bar_progress_sec=10,
             realf_ready=True, realf_score=45, realf_unpriced_flow=.008,
             realf_beta_r2=.6, realf_component_agreement=.8, cvd_slope_3m_norm=.1,
             cvd_1m_delta=100, cvd_5m_delta=100, buyer_ratio_delta_1m=2,
             fatigue_delta_1m=-2, fatigue_delta_3m=-3, chg_1m_pct=-.1,
             cvd_1m=100, cvd_5m=100, buyer_ratio_1m=60)
    for tf in ('1m', '3m', '5m', '15m', '1h', '4h'):
        s.update({f'fat_{tf}': 25, f'fat_{tf}_ready': True,
                  f'str_{tf}_ready': True, f'str_{tf}_state': 'BULL', f'str_{tf}_event': 'NONE'})
    for tf in ('1m', '5m', '15m'): s[tf+'_complete'] = True
    s.update(updates)
    return s


def advance(s, **updates):
    result = dict(s, **updates)
    result['kline_asof_ms'] = result['captured_at_ms']
    result['snapshot_id'] = str(result['captured_at_ms'])
    return result


class ResearchTests(unittest.TestCase):
    def test_quality_blocks_all_entries_and_ob_variants(self):
        for change in ({'5m_complete': False}, {'sync_error': 'DNS'}, {'clock_synced': False}, {'bar_progress_sec': 200}):
            out = sh.ShadowTracker().update(snapshot(**change))
            self.assertTrue(out['shadow_quality_veto'])
            self.assertFalse(any(out[f'shadow_H{i}_trigger'] for i in range(1, 8)))
        good = snapshot(ob_stale=False, ob_age_ms=100, orderbook_imbalance=.2)
        self.assertTrue(sh.ob_valid(good))
        for key, value in [('ob_stale', True), ('ob_age_ms', -1), ('orderbook_imbalance', None), ('sync_error', 'DNS')]:
            self.assertFalse(sh.ob_valid(dict(good, **{key: value})))

    def test_once_per_group_and_isolation(self):
        tracker = sh.ShadowTracker()
        s = snapshot()
        first = tracker.update(s)
        self.assertTrue(first['shadow_H2_trigger'])
        second = tracker.update(advance(s, captured_at_ms=s['captured_at_ms']+60_000))
        self.assertFalse(second['shadow_H2_trigger'])
        self.assertEqual(first['shadow_H2_event_group_id'], second['shadow_H2_event_group_id'])
        self.assertTrue(tracker.update(dict(s, symbol='OTHERUSDT'))['shadow_H2_trigger'])
        self.assertTrue(tracker.update(dict(s, run_id='other'))['shadow_H2_trigger'])

    def test_gap_erases_latches(self):
        tracker = sh.ShadowTracker()
        s = snapshot(fat_1m=90)
        tracker.update(s)
        later = tracker.update(advance(s, captured_at_ms=s['captured_at_ms']+240_000, fat_1m=70))
        self.assertTrue(later['shadow_gap_reset'])
        self.assertFalse(later['shadow_H4_setup'])

    def test_h4_unwinds_after_extreme_not_only_while_extreme(self):
        tracker = sh.ShadowTracker()
        s = snapshot(fat_1m=90)
        tracker.update(s)
        later = advance(s, captured_at_ms=s['captured_at_ms']+60_000, fat_1m=75,
                     realf_score=65, cvd_slope_3m_norm=-.1, cvd_1m_delta=-10,
                     str_3m_event='CHOCH DN', str_3m_event_age=0)
        out = tracker.update(later)
        self.assertTrue(out['shadow_H4_trigger'])
        for i in range(1, 6):
            out = tracker.update(advance(later, captured_at_ms=later['captured_at_ms']+i*60_000, price=101))
        self.assertTrue(out['shadow_H4_DECAY_5M'])

    def test_scanners_never_trade_and_conversion_links(self):
        s = snapshot()
        out = sh.ShadowTracker().update(s)
        self.assertTrue(out['shadow_H6_setup'])
        self.assertFalse(out['shadow_H6_trigger'])
        self.assertFalse(out['shadow_H7_trigger'])
        self.assertEqual(out['shadow_H6_to_H2_snapshot_id'], s['snapshot_id'])

    def test_h5_bounce_then_failure(self):
        tracker = sh.ShadowTracker()
        s = snapshot(str_15m_state='BEAR', realf_unpriced_flow=0,
                     fatigue_delta_3m=3, chg_1m_pct=.1, cvd_5m=-100)
        self.assertTrue(tracker.update(s)['shadow_H5_armed'])
        out = tracker.update(advance(s, captured_at_ms=s['captured_at_ms']+60_000,
                                  cvd_slope_3m_norm=-.1, cvd_1m_delta=-100, str_1m_state='BEAR',
                                  chg_1m_pct=-.1, fatigue_delta_3m=-2))
        self.assertTrue(out['shadow_H5_trigger'])

    def test_h3_retest_then_reacceleration(self):
        tracker = sh.ShadowTracker()
        s = snapshot(str_5m_event='BOS UP', str_5m_event_age=0,
                     str_5m_event_time_ms=1_799_999_700_000, str_5m_protected_level=95,
                     str_5m_event_strength=50, str_5m_conf=80)
        tracker.update(s)
        s2 = advance(s, captured_at_ms=s['captured_at_ms']+120_000, price=99)
        out = tracker.update(s2)
        self.assertIsNotNone(out['shadow_H3_retest_timestamp_ms'])
        self.assertFalse(out['shadow_H3_reaccel_trigger'])
        out = tracker.update(advance(s2, captured_at_ms=s2['captured_at_ms']+60_000, price=100))
        self.assertTrue(out['shadow_H3_reaccel_trigger'])
        self.assertEqual(out['shadow_H3_reacceleration_delay_sec'], 180)

    def test_history_has_no_future_leak_and_missing_is_null(self):
        now = 1_800_000_000_000 // 3_600_000 * 3_600_000 + 30_000
        bars = [[now//60_000*60_000 - i*60_000, 100, 102, 98, 100] for i in range(60, 0, -1)]
        hourly = [[(now//3_600_000-i)*3_600_000, 50, 999, 1, 999] for i in range(168, -1, -1)]
        a = sh.extension_features(candles(bars), candles(hourly), 100, now, 1)
        b = sh.extension_features(candles(bars+[[now+60_000, 1, 1e9, 0, 1]]), candles(hourly+[[now+3_600_000, 1, 1e9, 0, 1]]), 100, now, 1)
        self.assertEqual(a, b)
        self.assertEqual(a['return_7d'], 100)
        self.assertEqual(a['atr_extension'], 2)
        self.assertTrue(a['h7_features_ready'])
        missing = sh.extension_features(candles(bars[1:]), None, 100, now, 1)
        self.assertIsNone(missing['local_base_return'])
        self.assertIsNone(missing['return_7d'])

    def test_input_is_not_mutated_and_schema_is_stable(self):
        s = snapshot()
        saved = copy.deepcopy(s)
        t = sh.ShadowTracker()
        first = t.update(s)
        self.assertEqual(saved, s)
        later = t.update(advance(s, captured_at_ms=s['captured_at_ms']+60_000, fat_1m=90))
        self.assertEqual(set(first), set(later))

    def test_live_outcome_retries_missing_bars_without_partial_record(self):
        base = 1_800_000_000_000 // 60_000 * 60_000
        bars = [[base+i*60_000, 100, 101, 99, 100+i*.01] for i in range(70)]
        c = {'time':[b[0]/1000 for b in bars], 'open':[b[1] for b in bars], 'high':[b[2] for b in bars], 'low':[b[3] for b in bars], 'close':[b[4] for b in bars]}
        with tempfile.TemporaryDirectory() as directory:
            writer = tv.SnapshotWriter(directory)
            tracker = tv.LiveOutcomeTracker(writer, 'test')
            tracker.register('TEST', 'one', base+10_000, 100)
            incomplete = {key: values[:10]+values[11:] for key, values in c.items()}
            self.assertEqual(tracker.evaluate('TEST', incomplete, base+70*60_000), 0)
            self.assertEqual(len(tracker.pending['TEST']), 1)
            self.assertEqual(writer.outcomes, 0)
            self.assertEqual(tracker.evaluate('TEST', c, base+70*60_000), 1)
            self.assertEqual(len(tracker.pending['TEST']), 0)
            self.assertEqual(tracker.evaluate('TEST', c, base+70*60_000), 0)

    def test_missing_gap_does_not_get_stuck_behind_immature_entry(self):
        base = 1_800_000_000_000 // 60_000 * 60_000
        bars = [[base+i*60_000, 100, 101, 99, 100] for i in range(80)]
        c = dict(time=[b[0]/1000 for b in bars], open=[b[1] for b in bars], high=[b[2] for b in bars], low=[b[3] for b in bars], close=[b[4] for b in bars])
        with tempfile.TemporaryDirectory() as directory:
            tracker = tv.LiveOutcomeTracker(tv.SnapshotWriter(directory), 'test')
            tracker.register('TEST', 'old', base+10_000, 100)
            tracker.register('TEST', 'young', base+30*60_000, 100)
            bad = {k:v[:10]+v[11:] for k,v in c.items()}
            tracker.evaluate('TEST', bad, base+70*60_000)
            self.assertEqual(tracker.evaluate('TEST', c, base+70*60_000), 1)
            self.assertEqual(tracker.pending['TEST'][0][0], 'young')

    def test_timing_tracks_giveback_and_preserves_first_exit_candidate(self):
        t = sh.ShadowTracker()
        s = snapshot(str_1m_protected_type='LOW', str_1m_protected_level=99)
        initial = t.update(s)
        self.assertIsNone(initial['shadow_H2_flow5_opposes_first_delay_sec'])
        t.update(advance(s, captured_at_ms=s['captured_at_ms']+60_000, price=102))
        out = t.update(advance(s, captured_at_ms=s['captured_at_ms']+120_000, price=101, cvd_5m=-10))
        self.assertAlmostEqual(out['shadow_H2_observed_giveback_pct'], 1)
        self.assertEqual(out['shadow_H2_flow5_opposes_first_delay_sec'], 120)
        for minute in range(3, 61):
            out = t.update(advance(s, captured_at_ms=s['captured_at_ms']+minute*60_000, price=100, cvd_5m=-10))
        self.assertEqual(out['shadow_H2_flow5_opposes_first_delay_sec'], 120)
        self.assertEqual(out['shadow_H2_post_trigger_followthrough_60m'], 0)
        self.assertEqual(out['shadow_H2_event_group_id'], initial['shadow_H2_event_group_id'])

    def test_missing_h5_gap_cannot_arm(self):
        out = sh.ShadowTracker().update(snapshot(str_15m_state='BEAR', realf_unpriced_flow=None,
                                                 fatigue_delta_3m=3, chg_1m_pct=.1, cvd_5m=-100))
        self.assertTrue(out['shadow_H5_setup'])
        self.assertFalse(out['shadow_H5_armed'])

    def test_source_loss_stops_before_overwriting_reports(self):
        from research_report import analyze
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p/'run_meta.json').write_text(json.dumps({'snapshots': 100}))
            (p/'snapshots_20260918_01.jsonl').write_text(json.dumps(snapshot())+'\n')
            with self.assertRaisesRegex(ValueError, 'Kaynak snapshot eksik'):
                analyze(p)
            self.assertFalse((p/'research_shadow_v1').exists())
            with self.assertRaisesRegex(ValueError, 'Kaynak snapshot eksik'):
                tv.offline_evaluate(str(p), fetch_bars=lambda *args: self.fail('must not fetch'))
            self.assertFalse((p/'outcomes.jsonl').exists())

    def test_jsonl_is_authoritative_and_merged_without_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p/'snapshots_20260918_01.jsonl').write_text(json.dumps(snapshot())+'\n')
            result = tv.offline_evaluate(str(p), now_ms=snapshot()['captured_at_ms'], verbose=False)
            self.assertEqual(result['snapshots'], 1)
            self.assertEqual(result['immature'], 1)
            self.assertTrue(Path(result['merged_files'][0]).exists())

    def test_report_pipeline_synthetic_without_network(self):
        from research_report import analyze
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            s = snapshot(provider='BINANCE')
            rows = [advance(s, captured_at_ms=s['captured_at_ms']+i*60_000) for i in range(4)]
            (p/'snapshots_20260918_01.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with contextlib.redirect_stdout(io.StringIO()):
                result = analyze(p)
            self.assertEqual(result['unique'], 4)
            self.assertTrue((p/'research_shadow_v1'/'RAPOR.md').exists())

    def test_killed_writer_tail_is_dropped_but_real_corruption_still_stops(self):
        """A run stopped mid-write leaves half a row; that is not corrupt data."""
        from research_report import analyze
        s = snapshot(provider='BINANCE')
        rows = [advance(s, captured_at_ms=s['captured_at_ms']+i*60_000) for i in range(4)]
        body = ''.join(json.dumps(r)+'\n' for r in rows)
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p/'snapshots_20260918_01.jsonl').write_text(body + json.dumps(rows[0])[:120])  # no newline
            with contextlib.redirect_stdout(io.StringIO()):
                result = analyze(p)
            self.assertEqual(result['unique'], 4)
            audit = json.loads((p/'research_shadow_v1'/'audit.json').read_text(encoding='utf-8'))
            self.assertEqual(audit['truncated_tail'], ['snapshots_20260918_01.jsonl:5'])
            self.assertEqual(audit['parse_errors'], [])
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            broken = body.replace(json.dumps(rows[1]), json.dumps(rows[1])[:150])  # middle row cut
            (p/'snapshots_20260918_01.jsonl').write_text(broken)
            with self.assertRaises(ValueError), contextlib.redirect_stdout(io.StringIO()):
                analyze(p)


if __name__ == '__main__':
    unittest.main()
