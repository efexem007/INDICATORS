"""
Live Tracker v2 — Telemetry, Delta, Flow Confidence, JSONL/CSV, Outcome Evaluator
==================================================================================
Bu modül live_tracker.py'nin MEVCUT yapısını bozmadan ek analitik katmanlar ekler.
Doğrudan live_tracker.py tarafından import edilir.
"""
import json
import csv
import math
import os
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════
# SÜRÜM DAMGALARI
# ═══════════════════════════════════════════════════════════════════════
REALF_VERSION = "v4.2"
FATIGUE_VERSION = "ZPTDIFAT-v1"
STRUCTURE_VERSION = "v1.1"
TRACKER_VERSION = "v2.0"

def _clamp(x, lo, hi):
    return max(lo, min(hi, x))

# ═══════════════════════════════════════════════════════════════════════
# 1. SNAPSHOT IDENTITY
# ═══════════════════════════════════════════════════════════════════════
def make_snapshot_id(symbol: str) -> str:
    """AKE_20260917_113800_341 formatında benzersiz snapshot ID."""
    now = datetime.now(timezone.utc)
    sym = symbol.upper().replace('USDT', '').replace('_', '')[:8]
    return f"{sym}_{now.strftime('%Y%m%d_%H%M%S')}_{now.strftime('%f')[:3]}"


def make_snapshot_meta(symbol: str, candles_1m: dict) -> dict:
    """Snapshot kimlik ve mum zamanlaması bilgisi."""
    now_ms = int(time.time() * 1000)
    times = candles_1m.get('time', [])
    last_bar_time = times[-1] if times else 0
    bar_close_time = last_bar_time + 60  # 1m bar = 60 seconds

    return {
        'snapshot_id': make_snapshot_id(symbol),
        'captured_at_ms': now_ms,
        'bar_open_time': last_bar_time,
        'bar_close_time': bar_close_time,
        'is_bar_closed': (now_ms // 1000) >= bar_close_time,
        'REALF_VERSION': REALF_VERSION,
        'FATIGUE_VERSION': FATIGUE_VERSION,
        'STRUCTURE_VERSION': STRUCTURE_VERSION,
        'TRACKER_VERSION': TRACKER_VERSION,
    }


# ═══════════════════════════════════════════════════════════════════════
# 2. FLOW CONFIDENCE
# ═══════════════════════════════════════════════════════════════════════
def compute_flow_confidence(window_stats: dict) -> dict:
    """Order-flow penceresi için güvenilirlik skoru hesapla.

    İnput: get_window_stats() çıktısı
    Output: flow_confidence + bileşenler
    """
    tc = window_stats.get('trade_count', 0)
    notional = window_stats.get('total_usd', 0.0)

    # Window coverage: trade listesinden timestamp aralığına bakarak
    # gerçek kapsama süresini tahmin ediyoruz
    trades_raw = window_stats.get('_trades_raw', [])
    if trades_raw and len(trades_raw) >= 2:
        first_ts = trades_raw[0][0]
        last_ts = trades_raw[-1][0]
        coverage_sec = max(0, (last_ts - first_ts) / 1000.0)
    else:
        coverage_sec = 0.0

    # Last trade age
    if trades_raw:
        last_trade_ts = trades_raw[-1][0]
        last_trade_age_ms = max(0, int(time.time() * 1000) - last_trade_ts)
    else:
        last_trade_age_ms = 999999

    # Flow Confidence = sqrt(count_factor * notional_factor * freshness_factor) * 100
    count_factor = _clamp(tc / 50.0, 0.0, 1.0)
    notional_factor = _clamp(math.log10(notional + 1) / 5.0, 0.0, 1.0)
    freshness_factor = _clamp(1.0 - last_trade_age_ms / 120000.0, 0.0, 1.0)

    confidence = min(100.0, math.sqrt(count_factor * notional_factor * freshness_factor) * 100.0)

    return {
        'trade_count': tc,
        'total_notional': round(notional, 2),
        'window_coverage_sec': round(coverage_sec, 1),
        'last_trade_age_ms': last_trade_age_ms,
        'flow_confidence': round(confidence, 1),
        'fc_count_factor': round(count_factor, 3),
        'fc_notional_factor': round(notional_factor, 3),
        'fc_freshness_factor': round(freshness_factor, 3),
    }


# ═══════════════════════════════════════════════════════════════════════
# 3. DELTA / SLOPE TRACKER
# ═══════════════════════════════════════════════════════════════════════
class SnapshotHistory:
    """Her sembol için son N snapshot değerlerini saklar ve delta/slope hesaplar."""

    def __init__(self, max_snapshots: int = 10):
        self._history = {}   # symbol -> deque of dict
        self._max = max_snapshots

    def record(self, symbol: str, values: dict):
        """Yeni snapshot değerleri kaydet."""
        sym = symbol.upper()
        if sym not in self._history:
            self._history[sym] = deque(maxlen=self._max)
        self._history[sym].append({
            'ts': time.time(),
            **values,
        })

    def get_history(self, symbol: str) -> list:
        sym = symbol.upper()
        return list(self._history.get(sym, []))

    def compute_deltas(self, symbol: str, current_values: dict) -> dict:
        """REALF, Fatigue, CVD için delta ve slope hesapla."""
        hist = self.get_history(symbol)
        result = {}

        # REALF deltas
        realf_now = current_values.get('realf_score', 50.0)
        result['realf_now'] = round(realf_now, 1)
        for offset, label in [(1, '1m_ago'), (3, '3m_ago'), (5, '5m_ago')]:
            idx = len(hist) - offset
            if idx >= 0:
                val = hist[idx].get('realf_score', realf_now)
                result[f'realf_{label}'] = round(val, 1)
                result[f'realf_d{offset}'] = round(realf_now - val, 1)
            else:
                result[f'realf_{label}'] = None
                result[f'realf_d{offset}'] = None

        # Unpriced Flow deltas
        unpriced_now = current_values.get('unpriced_flow', 0.0)
        result['unpriced_now'] = round(unpriced_now, 5)
        for offset, label in [(1, 'd1'), (3, 'd3'), (5, 'd5')]:
            idx = len(hist) - offset
            if idx >= 0:
                val = hist[idx].get('unpriced_flow', 0.0)
                result[f'unpriced_{label}'] = round(unpriced_now - val, 5)
            else:
                result[f'unpriced_{label}'] = None

        # Fatigue deltas
        fat_now = current_values.get('fatigue_1m', 50.0)
        result['fatigue_now'] = round(fat_now, 1)
        for offset, label in [(1, '1m_ago'), (3, '3m_ago'), (5, '5m_ago')]:
            idx = len(hist) - offset
            if idx >= 0:
                val = hist[idx].get('fatigue_1m', fat_now)
                result[f'fatigue_{label}'] = round(val, 1)
                result[f'fatigue_d{offset}'] = round(fat_now - val, 1)
            else:
                result[f'fatigue_{label}'] = None
                result[f'fatigue_d{offset}'] = None

        # CVD deltas
        for window in ['1m', '5m', '15m']:
            cvd_key = f'cvd_{window}'
            br_key = f'buyer_ratio_{window}'
            cvd_now = current_values.get(cvd_key, 0.0)
            br_now = current_values.get(br_key, 50.0)
            result[f'{cvd_key}_now'] = round(cvd_now, 1)

            if hist:
                prev = hist[-1]
                result[f'{cvd_key}_delta'] = round(cvd_now - prev.get(cvd_key, cvd_now), 1)
                result[f'{br_key}_delta'] = round(br_now - prev.get(br_key, br_now), 1)
            else:
                result[f'{cvd_key}_delta'] = None
                result[f'{br_key}_delta'] = None

        # CVD slopes (linear regression over last N snapshots)
        for window_n, label in [(3, '3m'), (5, '5m')]:
            cvd_vals = []
            for h in hist[-(window_n):]:
                cvd_vals.append(h.get('cvd_1m', 0.0))
            cvd_vals.append(current_values.get('cvd_1m', 0.0))

            if len(cvd_vals) >= 2:
                n = len(cvd_vals)
                x_mean = (n - 1) / 2.0
                y_mean = sum(cvd_vals) / n
                num = sum((i - x_mean) * (cvd_vals[i] - y_mean) for i in range(n))
                den = sum((i - x_mean) ** 2 for i in range(n))
                slope = num / den if den > 0 else 0.0
                result[f'cvd_slope_{label}'] = round(slope, 2)
            else:
                result[f'cvd_slope_{label}'] = None

        return result

    def format_trend_line(self, symbol: str, key: str, current_val: float, n: int = 5) -> str:
        """21 → 24 → 28 → 35 → 44 (Δ +23) formatında trend çizgisi."""
        hist = self.get_history(symbol)
        vals = []
        for h in hist[-(n - 1):]:
            v = h.get(key)
            if v is not None:
                vals.append(round(v, 1))
        vals.append(round(current_val, 1))

        if len(vals) < 2:
            return f"{current_val:.1f} (yeni)"

        trend_str = " → ".join(str(v) for v in vals)
        delta = vals[-1] - vals[0]
        return f"{trend_str} (Δ {delta:+.1f})"


# ═══════════════════════════════════════════════════════════════════════
# 4. JSONL / CSV WRITER
# ═══════════════════════════════════════════════════════════════════════
class SnapshotWriter:
    """JSONL ve CSV dosyalarına snapshot yazar. Günlük rotasyon."""

    def __init__(self, base_dir: str = "logs"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._csv_headers_written = set()

    def _today_tag(self) -> str:
        return datetime.now().strftime('%Y%m%d')

    def write_snapshot(self, flat_record: dict):
        """Snapshot'ı JSONL ve CSV'ye yazar."""
        tag = self._today_tag()

        # JSONL
        jsonl_path = self.base_dir / f"snapshots_{tag}.jsonl"
        with open(jsonl_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(flat_record, ensure_ascii=False, default=str) + '\n')

        # CSV
        csv_path = self.base_dir / f"snapshots_{tag}.csv"
        file_exists = csv_path.exists()

        # Ensure all values are serializable
        clean_record = {}
        for k, v in flat_record.items():
            if isinstance(v, (dict, list)):
                clean_record[k] = json.dumps(v, ensure_ascii=False, default=str)
            else:
                clean_record[k] = v

        csv_key = str(csv_path)
        if csv_key not in self._csv_headers_written and not file_exists:
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=list(clean_record.keys()))
                writer.writeheader()
                writer.writerow(clean_record)
            self._csv_headers_written.add(csv_key)
        else:
            # Append — handle potential new columns gracefully
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    existing_headers = next(reader, [])
            except Exception:
                existing_headers = []

            # If we have new columns, rewrite isn't practical — just append
            with open(csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=existing_headers or list(clean_record.keys()),
                                       extrasaction='ignore')
                writer.writerow(clean_record)

    def write_outcome(self, outcome_record: dict):
        """Outcome evaluator sonuçlarını ayrı JSONL'ye yazar."""
        tag = self._today_tag()
        path = self.base_dir / f"outcomes_{tag}.jsonl"
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(outcome_record, ensure_ascii=False, default=str) + '\n')


# ═══════════════════════════════════════════════════════════════════════
# 5. OUTCOME EVALUATOR
# ═══════════════════════════════════════════════════════════════════════
class OutcomeEvaluator:
    """Snapshot'ların forward return ve MFE/MAE'sini hesaplar.

    Her snapshot kaydedilir. Belirli süreler geçtiğinde kline verisinden
    forward return, MFE (max favorable excursion), MAE (max adverse excursion)
    hesaplanır ve outcomes JSONL'ye yazılır.
    """

    HORIZONS = [1, 3, 5, 10, 20, 30, 60]  # dakika
    MFE_MAE_HORIZONS = [5, 10, 20]  # dakika

    def __init__(self, writer: SnapshotWriter):
        self._pending = deque(maxlen=5000)  # (snapshot_id, symbol, entry_price, ts_sec, evaluated_horizons)
        self._writer = writer

    def register(self, snapshot_id: str, symbol: str, price: float):
        self._pending.append({
            'snapshot_id': snapshot_id,
            'symbol': symbol,
            'entry_price': price,
            'ts_sec': time.time(),
            'results': {},
            'done_horizons': set(),
        })

    def evaluate(self, symbol: str, candles_1m: dict):
        """Mevcut kline verisine göre olgunlaşmış snapshot'ları değerlendir."""
        now = time.time()
        closes = candles_1m.get('close', [])
        highs = candles_1m.get('high', [])
        lows = candles_1m.get('low', [])
        times = candles_1m.get('time', [])

        if not closes or not times:
            return

        completed = []
        for entry in self._pending:
            if entry['symbol'].upper() != symbol.upper():
                continue

            age_sec = now - entry['ts_sec']
            age_min = age_sec / 60.0
            entry_price = entry['entry_price']

            if entry_price <= 0:
                continue

            # Forward returns
            for horizon in self.HORIZONS:
                if horizon in entry['done_horizons']:
                    continue
                if age_min >= horizon + 0.5:  # half-minute buffer
                    # Find the bar that's `horizon` minutes after entry
                    target_time = entry['ts_sec'] + (horizon * 60)
                    best_idx = None
                    for i, t in enumerate(times):
                        if t >= target_time:
                            best_idx = i
                            break
                    if best_idx is not None and best_idx < len(closes):
                        fwd_ret = (closes[best_idx] - entry_price) / entry_price * 100.0
                        entry['results'][f'fwd_ret_{horizon}m'] = round(fwd_ret, 4)
                        entry['done_horizons'].add(horizon)

            # MFE / MAE
            for horizon in self.MFE_MAE_HORIZONS:
                mfe_key = f'mfe_{horizon}m'
                mae_key = f'mae_{horizon}m'
                if mfe_key in entry['results']:
                    continue
                if age_min >= horizon + 0.5:
                    start_time = entry['ts_sec']
                    end_time = start_time + (horizon * 60)
                    window_highs = []
                    window_lows = []
                    for i, t in enumerate(times):
                        if start_time <= t <= end_time:
                            window_highs.append(highs[i])
                            window_lows.append(lows[i])

                    if window_highs and window_lows:
                        max_high = max(window_highs)
                        min_low = min(window_lows)
                        mfe = (max_high - entry_price) / entry_price * 100.0
                        mae = (min_low - entry_price) / entry_price * 100.0
                        entry['results'][mfe_key] = round(mfe, 4)
                        entry['results'][mae_key] = round(mae, 4)

            # Check if fully evaluated
            all_done = all(h in entry['done_horizons'] for h in self.HORIZONS)
            all_mfe = all(f'mfe_{h}m' in entry['results'] for h in self.MFE_MAE_HORIZONS)
            if all_done and all_mfe:
                completed.append(entry)

        # Write completed outcomes
        for entry in completed:
            outcome = {
                'snapshot_id': entry['snapshot_id'],
                'symbol': entry['symbol'],
                'entry_price': entry['entry_price'],
                'entry_ts': entry['ts_sec'],
                **entry['results'],
            }
            self._writer.write_outcome(outcome)
            try:
                self._pending.remove(entry)
            except ValueError:
                pass


# ═══════════════════════════════════════════════════════════════════════
# 6. STRUCTURE ENRICHMENT HELPER
# ═══════════════════════════════════════════════════════════════════════
def enrich_structure(struct_result: dict, candles: dict, atrLen: int = 14) -> dict:
    """calc_structure sonucuna ek alanlar ekler (protected level, EQH/EQL mesafe, vb.)

    Not: calc_structure'ın kendisi bu alanları HESAPLAMIYORSA dışarıdan ekleyemeyiz.
    Bu fonksiyon, calc_structure'ın RETURN DEĞERİNE ek alanlar eklendiğini varsayar.
    Eğer calc_structure güncellenmediyse, varsayılan boş değerler döner.
    """
    enriched = dict(struct_result)

    # Ensure all expected enrichment fields exist with defaults
    defaults = {
        'int_seq': struct_result.get('int_seq', 'N/A'),
        'event_age': struct_result.get('event_age'),
        'event_strength': struct_result.get('event_strength'),
        'protected_level': struct_result.get('protected_level'),
        'protected_type': struct_result.get('protected_type', 'N/A'),
        'protected_distance_atr': struct_result.get('protected_distance_atr'),
        'nearest_eqh': struct_result.get('nearest_eqh'),
        'nearest_eql': struct_result.get('nearest_eql'),
        'eqh_distance_atr': struct_result.get('eqh_distance_atr'),
        'eql_distance_atr': struct_result.get('eql_distance_atr'),
        'last_liq_event': struct_result.get('last_liq_event', 'NONE'),
        'liq_event_age': struct_result.get('liq_event_age'),
        'sweep_event': struct_result.get('sweep_event', False),
    }

    for k, v in defaults.items():
        if k not in enriched:
            enriched[k] = v

    return enriched


# ═══════════════════════════════════════════════════════════════════════
# 7. FLAT RECORD BUILDER
# ═══════════════════════════════════════════════════════════════════════
def build_flat_record(
    symbol: str,
    meta: dict,
    price: float,
    chg_1m: float,
    realf: dict,
    fatigue_mtf: dict,       # {tf_label: fatigue_dict}
    structure_mtf: dict,     # {tf_label: structure_dict}
    cvd_windows: dict,       # {'1m': stats, '5m': stats, '15m': stats}
    flow_conf: dict,         # {'1m': fc_dict, '5m': ..., '15m': ...}
    deltas: dict,
    coin_info: dict,
) -> dict:
    """Tüm verileri düz bir dict'e sıkıştırır (JSONL/CSV için)."""
    rec = {}

    # Identity
    rec.update(meta)
    rec['symbol'] = symbol
    rec['price'] = price
    rec['chg_1m_pct'] = round(chg_1m, 4)
    rec['coin_class'] = coin_info.get('class', 'UNKNOWN')
    rec['coin_rank'] = coin_info.get('rank', 0)

    # REALF
    for k, v in realf.items():
        rec[f'realf_{k}'] = v

    # Fatigue per TF
    for tf, fat in fatigue_mtf.items():
        rec[f'fatigue_{tf}'] = fat.get('fat', 50.0)
        rec[f'fatigue_{tf}_state'] = fat.get('state', 'WARMUP')
        rec[f'fatigue_{tf}_abs'] = fat.get('abs', 50.0)
        rec[f'fatigue_{tf}_rank'] = fat.get('rank', 50.0)

    # Structure per TF
    for tf, st in structure_mtf.items():
        rec[f'str_{tf}_score'] = st.get('score', 50.0)
        rec[f'str_{tf}_state'] = st.get('state', 'RANGE')
        rec[f'str_{tf}_event'] = st.get('event', 'NONE')
        rec[f'str_{tf}_regime'] = st.get('regime', 'RANGE')
        rec[f'str_{tf}_conf'] = st.get('conf', 0.0)
        rec[f'str_{tf}_ext_seq'] = st.get('ext_seq', 'WARMUP')
        rec[f'str_{tf}_int_seq'] = st.get('int_seq', 'N/A')
        rec[f'str_{tf}_event_age'] = st.get('event_age')
        rec[f'str_{tf}_event_strength'] = st.get('event_strength')
        rec[f'str_{tf}_protected'] = st.get('protected_level')
        rec[f'str_{tf}_prot_type'] = st.get('protected_type', 'N/A')
        rec[f'str_{tf}_prot_dist_atr'] = st.get('protected_distance_atr')

    # CVD windows
    for window, stats in cvd_windows.items():
        rec[f'cvd_{window}_usd'] = round(stats.get('cvd_usd', 0.0), 2)
        rec[f'cvd_{window}_pct'] = round(stats.get('cvd_pct', 0.0), 2)
        rec[f'buyer_ratio_{window}'] = round(stats.get('buy_ratio', 50.0), 2)
        rec[f'cvd_{window}_score'] = stats.get('score', 50.0)
        rec[f'cvd_{window}_direction'] = stats.get('direction', 'FLAT')
        rec[f'cvd_{window}_trade_count'] = stats.get('trade_count', 0)

    # Flow confidence
    for window, fc in flow_conf.items():
        for k, v in fc.items():
            rec[f'fc_{window}_{k}'] = v

    # Deltas
    rec.update(deltas)

    return rec


# ═══════════════════════════════════════════════════════════════════════
# 8. CONSOLE DISPLAY HELPERS (new sections)
# ═══════════════════════════════════════════════════════════════════════
def print_delta_section(snapshot_hist: SnapshotHistory, symbol: str, current_values: dict, deltas: dict):
    """[6] DELTA TRACKER bölümünü yazdırır."""
    sub_border = "-" * 78

    print("  [6] DELTA TRACKER (Değişim Eğilimleri):")

    # REALF trend
    realf_trend = snapshot_hist.format_trend_line(symbol, 'realf_score', current_values.get('realf_score', 50.0))
    print(f"    • REALF       : {realf_trend}")

    # Fatigue trend
    fat_trend = snapshot_hist.format_trend_line(symbol, 'fatigue_1m', current_values.get('fatigue_1m', 50.0))
    print(f"    • FATIGUE 1m  : {fat_trend}")

    # Unpriced flow
    unp_trend = snapshot_hist.format_trend_line(symbol, 'unpriced_flow', current_values.get('unpriced_flow', 0.0), n=5)
    print(f"    • UNPRICED    : {unp_trend}")

    # CVD slopes
    slope_3 = deltas.get('cvd_slope_3m')
    slope_5 = deltas.get('cvd_slope_5m')
    slope_3_str = f"{slope_3:+.2f}" if slope_3 is not None else "N/A"
    slope_5_str = f"{slope_5:+.2f}" if slope_5 is not None else "N/A"
    slope_emoji = "📈" if (slope_3 or 0) > 0.5 else ("📉" if (slope_3 or 0) < -0.5 else "➡️")
    print(f"    • CVD SLOPE   : 3m: {slope_3_str} | 5m: {slope_5_str} {slope_emoji}")

    print(sub_border)


def print_flow_confidence_section(flow_conf: dict):
    """[7] FLOW CONFIDENCE bölümünü yazdırır."""
    sub_border = "-" * 78

    print("  [7] FLOW CONFIDENCE (Akış Güvenilirliği):")
    print("    PENCERE | İŞLEM | HACİM ($)    | KAPSAM  | BAYATLIK | GÜVENİLİRLİK")

    for window in ['1m', '5m', '15m']:
        fc = flow_conf.get(window, {})
        tc = fc.get('trade_count', 0)
        notional = fc.get('total_notional', 0.0)
        coverage = fc.get('window_coverage_sec', 0.0)
        age_ms = fc.get('last_trade_age_ms', 999999)
        conf = fc.get('flow_confidence', 0.0)

        age_str = f"{age_ms/1000:.0f}s" if age_ms < 120000 else "BAYAT"
        conf_emoji = "🟢" if conf >= 60 else ("🟡" if conf >= 30 else "🔴")
        notional_str = f"${notional:>12,.0f}" if notional < 1e9 else f"${notional/1e6:>9,.1f}M"

        print(f"    {window:>7s} | {tc:>5d} | {notional_str} | {coverage:>5.0f}s | {age_str:>8s} | {conf_emoji} {conf:>5.1f}/100")

    print(sub_border)
