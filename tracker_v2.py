"""
tracker_v2.py — Canlı Takip Logger v2 telemetri katmanı
=======================================================
live_tracker.py bu modülü import eder. Burası SKOR ÜRETMEZ (REALF / Fatigue /
Structure motorları live_tracker.py'dedir); yalnızca ölçer ve kaydeder:

  • Binance aggTrades havuzunu BOŞLUKSUZ tutar: aggTradeId sürekliliği +
    fromId ile geri doldurma. Sayfa sınırı aşılırsa boşluk zaman aralığı
    olarak kaydedilir; her pencerenin GERÇEK kapsaması buradan ölçülür.
  • 1m / 5m / 15m akış pencereleri, 1 dakika önceye göre delta, dakika adımlı
    CVD eğimi, büyük işlem (burst) sayımı ve FLOW_CONFIDENCE (shadow metrik).
  • Orderbook özeti (spread, dengesizlik, microprice sapması).
  • Her çalıştırmayı logs/run_<id>/ altına console.txt + snapshots.jsonl +
    snapshots.csv + outcomes.jsonl olarak yazar.
  • Sonuç değerlendirici: forward return + MFE/MAE (canlı ve sonradan).

Alan sözlüğü ve tanımlar: LOGGER_V2_ALANLAR.md
Kendi kendine test:      python tracker_v2.py selftest
"""
import bisect
import csv
import hashlib
import io
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime

TRACKER_VERSION = "v2"
DATASET_SCHEMA = 2

# Her snapshot'ta bulunması ZORUNLU alanlar (eksik/None ise kayıt hatalı sayılır).
REQUIRED_SNAPSHOT_FIELDS = ('dataset_schema', 'tracker_version', 'structure_version', 'realf_engine',
                            'fatigue_version', 'run_id', 'code_fingerprint', 'snapshot_id', 'symbol',
                            'captured_at_ms', 'kline_asof_ms', 'price')
OB_STALE_MS = 5_000          # bu yaştan eski orderbook "stale" sayılır ve karar verisi değildir


def missing_required(flat):
    """Zorunlu alanlardan eksik/None olanlar (boş liste = kayıt geçerli)."""
    return [k for k in REQUIRED_SNAPSHOT_FIELDS if flat.get(k) is None]
FLOW_CONFIDENCE_VERSION = "fc-v1"
OUTCOME_VERSION = "oc-v1"

BINANCE_FAPI = "https://fapi.binance.com"


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _finite(v):
    """NaN / inf değerleri JSON/CSV'ye None olarak geçir."""
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


def _r(v, nd):
    """None-güvenli yuvarlama."""
    if v is None:
        return None
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return round(v, nd)


# ═══════════════════════════════════════════════════════════════════════
# 1. HTTP + AĞIRLIK KORUMASI (Binance IP limiti tüm uygulamalarla ortak)
# ═══════════════════════════════════════════════════════════════════════

WEIGHT_LIMIT_1M = 2400
WEIGHT_SOFT_LIMIT = 1500   # üstünde ek geri doldurma sayfası açılmaz (boşluk kaydedilir)
WEIGHT_HARD_LIMIT = 2100   # üstünde işlem senkronu bu tur atlanır


class HttpBackoff(Exception):
    """418/429 sonrası bekleme süresi dolmadan ağ çağrısı yapılmaz."""


class RateGuard:
    def __init__(self):
        self._lock = threading.Lock()
        self.used_weight_1m = 0
        self.used_weight_at_ms = 0
        self.max_used_weight_1m = 0
        self.backoff_until_ms = 0
        self.requests = 0
        self.http_errors = 0
        self.backoff_events = 0

    def note_headers(self, headers):
        if headers is None:
            return
        raw = headers.get('X-MBX-USED-WEIGHT-1M') or headers.get('x-mbx-used-weight-1m')
        if raw is None:
            return
        try:
            w = int(raw)
        except ValueError:
            return
        with self._lock:
            self.used_weight_1m = w
            self.used_weight_at_ms = int(time.time() * 1000)
            self.max_used_weight_1m = max(self.max_used_weight_1m, w)

    def current_weight(self):
        """Son okunan ağırlık; okuma önceki dakikadansa sayaç sıfırlanmış sayılır."""
        with self._lock:
            now_ms = int(time.time() * 1000)
            if now_ms // 60000 != self.used_weight_at_ms // 60000:
                return 0
            return self.used_weight_1m

    def soft_exceeded(self):
        return self.current_weight() >= WEIGHT_SOFT_LIMIT

    def hard_exceeded(self):
        return self.current_weight() >= WEIGHT_HARD_LIMIT

    def in_backoff(self):
        return int(time.time() * 1000) < self.backoff_until_ms

    def set_backoff(self, seconds):
        with self._lock:
            self.backoff_until_ms = max(self.backoff_until_ms, int(time.time() * 1000) + int(seconds * 1000))
            self.backoff_events += 1


RATE = RateGuard()


def http_get_json(url, timeout=10.0):
    if RATE.in_backoff():
        raise HttpBackoff(f"rate-limit beklemesi sürüyor ({(RATE.backoff_until_ms - int(time.time() * 1000)) // 1000} sn)")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    RATE.requests += 1
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            RATE.note_headers(resp.headers)
            return json.loads(body.decode('utf-8'))
    except urllib.error.HTTPError as e:
        RATE.http_errors += 1
        RATE.note_headers(e.headers)
        if e.code in (418, 429):
            try:
                retry = int(e.headers.get('Retry-After') or 60)
            except (TypeError, ValueError):
                retry = 60
            RATE.set_backoff(retry)
            print(f"  🚨 [RATE LIMIT] HTTP {e.code} — {retry} sn tüm Binance çağrıları durduruldu.")
            raise HttpBackoff(f"HTTP {e.code}, Retry-After={retry}s")
        raise


class ExchangeClock:
    """Yerel saat ile Binance sunucu saati farkı. Tüm pencereler borsa saatiyle hesaplanır."""

    def __init__(self, refresh_sec=600):
        self.offset_ms = 0
        self.rtt_ms = None
        self.synced_at = 0.0
        self.ok = False
        self.last_error = None
        self.refresh_sec = refresh_sec

    def refresh(self, force=False):
        # Başarısız senkron (ör. WARP kapalıyken başlatma) 30 sn'de bir yeniden denenir.
        interval = self.refresh_sec if self.ok else 30
        if not force and time.time() - self.synced_at < interval:
            return
        self.synced_at = time.time()
        try:
            t0 = int(time.time() * 1000)
            data = http_get_json(f"{BINANCE_FAPI}/fapi/v1/time", timeout=5)
            t1 = int(time.time() * 1000)
            self.offset_ms = int(data['serverTime']) - (t0 + t1) // 2
            self.rtt_ms = t1 - t0
            self.ok = True
            self.last_error = None
        except Exception as e:
            self.ok = False
            self.last_error = f"{type(e).__name__}: {e}"

    def now_ms(self):
        return int(time.time() * 1000) + self.offset_ms


CLOCK = ExchangeClock()


def network_hint(error_text):
    """Binance bağlantı hatası için kullanıcıya anlaşılır ipucu (yoksa None)."""
    if not error_text:
        return None
    t = str(error_text)
    if 'WRONG_VERSION_NUMBER' in t or 'SEC_E_INVALID_TOKEN' in t or 'UNEXPECTED_EOF' in t:
        return ("Bağlı olduğunuz ağ Binance'i engelliyor (ör. GSBWIFI / yurt / kurum Wi-Fi filtresi bağlantıyı engel sayfasına "
                "yönlendiriyor). Cloudflare WARP / VPN'i açın ya da telefon hotspot'u gibi başka bir ağa geçin — "
                "takip her turda yeniden dener, kapatmanıza gerek yok.")
    if 'getaddrinfo' in t or 'Name or service not known' in t or 'timed out' in t:
        return "Binance'e ulaşılamıyor (DNS / zaman aşımı). İnternet ve WARP / VPN bağlantısını kontrol edin; takip yeniden dener."
    return None


# ═══════════════════════════════════════════════════════════════════════
# 2. İŞLEM HAVUZU — boşluk takipli (sembol başına izole)
# ═══════════════════════════════════════════════════════════════════════

POOL_RETENTION_MS = 17 * 60_000
AGG_PAGE_LIMIT = 1000


class TradePool:
    """Bir sembolün son 17 dakikalık aggTrade havuzu + kapsama defteri.

    Kapsama defteri:
      coverage_start_ms : bu andan önce veri yok (başlangıç)
      known_until_ms    : bu ana kadar tüm işlemler havuzda (son başarılı senkron)
      gaps              : (başlangıç, bitiş) — arası bilinmiyor (sayfa sınırı / id sıçraması)
    """

    def __init__(self, provider, market, symbol):
        self.provider = provider.upper()
        self.market = market.upper()
        self.symbol = symbol.upper()
        self.trades = deque()           # (T_ms, agg_id, price, qty, usd, is_buy, n_trades)
        self.last_id = None
        self.last_T = None
        self.last_price = 0.0
        self.coverage_start_ms = None
        self.known_until_ms = None
        self.gaps = deque()
        self.integrity_errors = 0
        self.gap_events = 0
        self.gap_ms_total = 0
        self.resets = 0
        self.last_sync = {}
        self.last_verify_ms = 0          # sessiz coinde id sıfırlanması kontrolü
        self._keys = deque()             # MEXC: sıralı kimlik tekrar koruması
        self._keyset = set()

    # ── alım ──
    def _accept(self, T, agg_id, price, qty, is_buy, n_trades, ref_price):
        if price <= 0 or qty <= 0:
            return False
        if ref_price and ref_price > 0 and abs(price - ref_price) / ref_price > 0.40:
            self.integrity_errors += 1
            print(f"⚠️ [DATA INTEGRITY ERROR]: {self.symbol} için anormal fiyat reddedildi! Ref={ref_price}, Gelen={price}")
            return False
        usd = price * qty
        self.trades.append((T, agg_id, price, qty, usd, is_buy, n_trades))
        self.last_T = T if self.last_T is None else max(self.last_T, T)
        self.last_price = price
        return True

    def ingest_binance(self, items, incoming_symbol, ref_price=0.0):
        if incoming_symbol.upper() != self.symbol:
            self.integrity_errors += 1
            print(f"⚠️ [DATA INTEGRITY ERROR]: Sembol uyuşmazlığı reddedildi! Hedef={self.symbol}, Gelen={incoming_symbol}")
            return 0
        accepted = 0
        for t in sorted(items, key=lambda x: int(x['a'])):
            aid = int(t['a'])
            if self.last_id is not None and aid <= self.last_id:
                continue
            n_tr = int(t.get('l', 0)) - int(t.get('f', 0)) + 1 if 'l' in t and 'f' in t else 1
            if self._accept(int(t['T']), aid, float(t['p']), float(t['q']), not bool(t.get('m', False)), max(1, n_tr), ref_price):
                accepted += 1
            self.last_id = aid
        return accepted

    def ingest_keyed(self, rows, ref_price=0.0):
        """Sıralı kimliği olmayan sağlayıcılar (MEXC): rows = (T, key, price, qty, is_buy)."""
        accepted = 0
        for T, key, price, qty, is_buy in sorted(rows, key=lambda r: r[0]):
            if key in self._keyset:
                continue
            self._keyset.add(key)
            self._keys.append(key)
            if len(self._keys) > 20000:
                self._keyset.discard(self._keys.popleft())
            if self._accept(T, None, price, qty, is_buy, 1, ref_price):
                accepted += 1
        return accepted

    # ── kapsama ──
    def mark_gap(self, start_ms, end_ms):
        if start_ms is None or end_ms is None or end_ms <= start_ms:
            return
        self.gaps.append((int(start_ms), int(end_ms)))
        self.gap_events += 1
        self.gap_ms_total += int(end_ms - start_ms)

    def reset(self, now_ms):
        self.trades.clear()
        self.gaps.clear()
        self.last_id = None
        self.last_T = None
        self.last_price = 0.0
        self.coverage_start_ms = None
        self.known_until_ms = None
        self._keys.clear()
        self._keyset.clear()
        self.resets += 1

    def prune(self, now_ms):
        cutoff = now_ms - POOL_RETENTION_MS
        while self.trades and self.trades[0][0] < cutoff:
            self.trades.popleft()
        while self.gaps and self.gaps[0][1] < cutoff:
            self.gaps.popleft()

    def uncovered_ms(self, lo, hi):
        """[lo, hi) aralığında verisi bilinmeyen milisaniye."""
        span = hi - lo
        if span <= 0:
            return 0
        if self.coverage_start_ms is None or self.known_until_ms is None:
            return span
        un = 0
        if lo < self.coverage_start_ms:
            un += min(hi, self.coverage_start_ms) - lo
        if hi > self.known_until_ms:
            un += hi - max(lo, self.known_until_ms)
        a = max(lo, self.coverage_start_ms)
        b = min(hi, self.known_until_ms)
        if b > a:
            for gs, ge in self.gaps:
                ov = min(b, ge) - max(a, gs)
                if ov > 0:
                    un += ov
        return int(min(span, max(0, un)))


def sync_binance_pool(pool, clock, ref_price=0.0, max_pages=5):
    """Havuzu borsayla eşitle. Dönüş: senkron özeti (sayfa, mod, boşluk, hata).

    known_until_ms, cevabı dönen İSTEĞİN BAŞLADIĞI an olarak alınır (muhafazakâr):
    o ana kadarki tüm işlemler havuzdadır."""
    info = {'pages': 0, 'fetched': 0, 'mode': '', 'gap_ms': 0, 'error': None}
    sym = pool.symbol
    base = f"{BINANCE_FAPI}/fapi/v1/aggTrades?symbol={sym}"
    try:
        if RATE.hard_exceeded():
            info['mode'] = 'weight_skip'
            return info
        if pool.last_id is None:
            req_at = clock.now_ms()
            data = http_get_json(f"{base}&limit={AGG_PAGE_LIMIT}")
            info['pages'] = 1
            info['fetched'] = len(data)
            info['mode'] = 'bootstrap'
            pool.ingest_binance(data, sym, ref_price)
            if data:
                first_T = int(data[0]['T'])
                pool.coverage_start_ms = first_T + 1 if len(data) >= AGG_PAGE_LIMIT else first_T
            else:
                pool.coverage_start_ms = req_at
            pool.known_until_ms = req_at
            return info

        caught_up = False
        while info['pages'] < max_pages:
            if info['pages'] > 0 and RATE.soft_exceeded():
                info['mode'] = 'weight_guard'
                break
            req_at = clock.now_ms()
            data = http_get_json(f"{base}&fromId={pool.last_id + 1}&limit={AGG_PAGE_LIMIT}")
            info['pages'] += 1
            info['fetched'] += len(data)
            pool.ingest_binance(data, sym, ref_price)
            if len(data) < AGG_PAGE_LIMIT:
                pool.known_until_ms = req_at
                caught_up = True
                break
            pool.known_until_ms = int(data[-1]['T']) - 1
        if caught_up:
            info['mode'] = info['mode'] or 'continuous'
            # Uzun süre işlem gelmeyen coinde id sıfırlanmasını (yeniden listeleme) 10 dakikada bir doğrula.
            quiet = pool.last_T is None or pool.known_until_ms - pool.last_T > 600_000
            if info['fetched'] == 0 and quiet and pool.known_until_ms - pool.last_verify_ms > 600_000:
                pool.last_verify_ms = pool.known_until_ms
                req_at = clock.now_ms()
                latest = http_get_json(f"{base}&limit=10")
                info['pages'] += 1
                if latest and int(latest[-1]['a']) < pool.last_id:
                    pool.reset(req_at)
                    info['mode'] = 'id_reset'
                    pool.coverage_start_ms = req_at
                    pool.known_until_ms = req_at
                    pool.last_id = int(latest[-1]['a'])
            return info

        # Sayfa sınırı: en yeniye atla, aradaki süreyi boşluk olarak kaydet.
        req_at = clock.now_ms()
        data = http_get_json(f"{base}&limit={AGG_PAGE_LIMIT}")
        info['pages'] += 1
        info['fetched'] += len(data)
        info['mode'] = 'jump' if info['mode'] != 'weight_guard' else 'weight_guard_jump'
        if data:
            first_id = int(data[0]['a'])
            newest_id = int(data[-1]['a'])
            if newest_id < pool.last_id:
                pool.reset(req_at)
                info['mode'] = 'id_reset'
                pool.ingest_binance(data, sym, ref_price)
                pool.coverage_start_ms = int(data[0]['T']) + 1
            else:
                if first_id > pool.last_id + 1:
                    gap_start = pool.known_until_ms
                    gap_end = int(data[0]['T']) + 1      # aynı ms'deki daha küçük id'li işlemler de eksik olabilir
                    pool.mark_gap(gap_start, gap_end)
                    info['gap_ms'] = max(0, gap_end - gap_start) if gap_start is not None else 0
                pool.ingest_binance(data, sym, ref_price)
        pool.known_until_ms = req_at
        return info
    except Exception as e:
        info['error'] = f"{type(e).__name__}: {e}"
        return info
    finally:
        pool.prune(clock.now_ms())
        pool.last_sync = info


def sync_mexc_pool(pool, clock, ref_price=0.0):
    """MEXC deals: sıralı id yok → zaman tabanlı boşluk tahmini (dolu 100'lük parti eskiyle birleşmiyorsa boşluk)."""
    info = {'pages': 1, 'fetched': 0, 'mode': 'mexc', 'gap_ms': 0, 'error': None}
    try:
        asof = clock.now_ms()
        payload = http_get_json(f"https://contract.mexc.com/api/v1/contract/deals/{pool.symbol}?limit=100", timeout=5)
        deals = payload.get('data', []) if isinstance(payload, dict) else []
        rows = []
        for d in deals:
            T = int(d.get('t', 0))
            key = str(d.get('i') or f"{T}_{d.get('p')}_{d.get('v')}_{d.get('T')}")
            rows.append((T, key, float(d.get('p', 0)), float(d.get('v', 0)), d.get('T') == 1))
        info['fetched'] = len(rows)
        if rows:
            first_T = min(r[0] for r in rows)
            if pool.coverage_start_ms is None:
                pool.coverage_start_ms = first_T
            elif len(rows) >= 100 and pool.last_T is not None and first_T > pool.last_T:
                pool.mark_gap(pool.last_T, first_T)
                info['gap_ms'] = first_T - pool.last_T
        elif pool.coverage_start_ms is None:
            pool.coverage_start_ms = asof
        pool.ingest_keyed(rows, ref_price)
        pool.known_until_ms = asof
    except Exception as e:
        info['error'] = f"{type(e).__name__}: {e}"
    finally:
        pool.prune(clock.now_ms())
        pool.last_sync = info
    return info


# ═══════════════════════════════════════════════════════════════════════
# 3. AKIŞ PENCERELERİ, DELTA / EĞİM, BÜYÜK İŞLEM, FLOW CONFIDENCE
# ═══════════════════════════════════════════════════════════════════════

FLOW_WINDOWS = (('1m', 1), ('5m', 5), ('15m', 15))
N_BUCKETS = 16                 # 15m pencere + "1 dakika önceki" 15m pencere
DELTA_MIN_COVERAGE = 0.95      # bunun altında delta/eğim None
WINDOW_COMPLETE_MIN = 0.999    # `1m_complete` / `5m_complete` / `15m_complete` bayrağı için asgari kapsama
TURN_DEADBAND = 0.02           # normalize eğim işaret değişimi için ölü bölge

FC_WEIGHTS = (('count', 0.40), ('notional', 0.30), ('coverage', 0.20), ('freshness', 0.10))
FC_COUNT_HALF = 50.0           # n_eff = 50 → sayı faktörü 0.50


def flow_confidence(n_eff, notional, coverage_ratio, last_trade_age_ms, window_sec):
    """SHADOW metrik (skora girmez). Ağırlıklı geometrik ortalama, 0-100.

    count     = n_eff / (n_eff + 50)            n_eff = (Σusd)² / Σusd²  (hacim-konsantrasyon düzeltmeli işlem sayısı)
    notional  = clamp((log10($) - 2) / 4)       $100 → 0 · $10k → 0.5 · $1M+ → 1
    coverage  = pencerenin veriyle dolu oranı
    freshness = clamp(1 - son_işlem_yaşı / pencere)
    """
    f = {
        'count': (n_eff / (n_eff + FC_COUNT_HALF)) if n_eff and n_eff > 0 else 0.0,
        'notional': _clamp((math.log10(notional) - 2.0) / 4.0, 0.0, 1.0) if notional and notional > 0 else 0.0,
        'coverage': _clamp(coverage_ratio or 0.0, 0.0, 1.0),
        'freshness': _clamp(1.0 - last_trade_age_ms / (window_sec * 1000.0), 0.0, 1.0) if last_trade_age_ms is not None else 0.0,
    }
    if min(f.values()) <= 0.0:
        score = 0.0
    else:
        score = 100.0 * math.exp(sum(w * math.log(f[k]) for k, w in FC_WEIGHTS))
    return round(score, 1), {k: round(v, 3) for k, v in f.items()}


def _ols_slope(ys):
    n = len(ys)
    if n < 2:
        return None
    xm = (n - 1) / 2.0
    ym = sum(ys) / n
    den = sum((i - xm) ** 2 for i in range(n))
    return sum((i - xm) * (y - ym) for i, y in enumerate(ys)) / den if den else None


def _direction(cvd_pct):
    if cvd_pct is None:
        return None
    return 'UP' if cvd_pct > 3.0 else ('DOWN' if cvd_pct < -3.0 else 'FLAT')


def compute_flow_features(pool, asof_ms, whale_usd):
    """Havuzdan, asof_ms'de biten pencere özellikleri (borsa saati)."""
    nb = N_BUCKETS
    b_buy = [0.0] * nb
    b_sell = [0.0] * nb
    b_agg = [0] * nb
    b_tr = [0] * nb
    b_sq = [0.0] * nb
    lb_c = [0] * nb
    lb_v = [0.0] * nb
    ls_c = [0] * nb
    ls_v = [0.0] * nb
    horizon = asof_ms - nb * 60_000
    last_whale = None

    burst = None  # [T, is_buy, usd, qty]

    def close_burst(bu):
        nonlocal last_whale
        T, is_buy, usd, qty = bu
        if usd < whale_usd:
            return
        last_whale = {'time_ms': T, 'side': 'BUY' if is_buy else 'SELL', 'usd': usd, 'price': usd / qty if qty > 0 else None}
        if T > horizon and T <= asof_ms:
            k = int((asof_ms - T) // 60_000)
            if 0 <= k < nb:
                if is_buy:
                    lb_c[k] += 1
                    lb_v[k] += usd
                else:
                    ls_c[k] += 1
                    ls_v[k] += usd

    for (T, _aid, _p, qty, usd, is_buy, ntr) in pool.trades:
        if T > asof_ms:
            continue
        if burst is not None and (T != burst[0] or is_buy != burst[1]):
            close_burst(burst)
            burst = None
        if burst is None:
            burst = [T, is_buy, 0.0, 0.0]
        burst[2] += usd
        burst[3] += qty
        if T <= horizon:
            continue
        k = int((asof_ms - T) // 60_000)
        if k >= nb:
            continue
        if is_buy:
            b_buy[k] += usd
        else:
            b_sell[k] += usd
        b_agg[k] += 1
        b_tr[k] += ntr
        b_sq[k] += usd * usd
    if burst is not None:
        close_burst(burst)

    unc = [pool.uncovered_ms(asof_ms - (k + 1) * 60_000, asof_ms - k * 60_000) for k in range(nb)]
    last_age = (asof_ms - pool.last_T) if pool.last_T is not None else None

    def win(k0, length):
        ks = range(k0, k0 + length)
        buy = sum(b_buy[k] for k in ks)
        sell = sum(b_sell[k] for k in ks)
        tot = buy + sell
        sq = sum(b_sq[k] for k in ks)
        uncovered = sum(unc[k] for k in ks)
        span_ms = length * 60_000
        cvd = buy - sell
        return {
            'buy': buy, 'sell': sell, 'tot': tot, 'cvd': cvd,
            'cvd_pct': (cvd / tot * 100.0) if tot > 0 else None,
            'buyer_ratio': (buy / tot * 100.0) if tot > 0 else None,
            'agg': sum(b_agg[k] for k in ks), 'trades': sum(b_tr[k] for k in ks),
            'n_eff': (tot * tot / sq) if sq > 0 else 0.0,
            'cov_sec': (span_ms - uncovered) / 1000.0,
            'cov_ratio': (span_ms - uncovered) / span_ms,
            'lbc': sum(lb_c[k] for k in ks), 'lbv': sum(lb_v[k] for k in ks),
            'lsc': sum(ls_c[k] for k in ks), 'lsv': sum(ls_v[k] for k in ks),
        }

    out = {'last_trade_age_ms': last_age, 'pool_trades': len(pool.trades)}
    wins = {}
    for label, length in FLOW_WINDOWS:
        w = win(0, length)
        wins[label] = w
        fc, parts = flow_confidence(w['n_eff'], w['tot'], w['cov_ratio'], last_age, length * 60)
        score = 50.0 + 45.0 * math.tanh((w['cvd_pct'] or 0.0) / 22.0)
        out.update({
            f'flow_{label}_buy_usd': round(w['buy'], 2),
            f'flow_{label}_sell_usd': round(w['sell'], 2),
            f'cvd_{label}': round(w['cvd'], 2),
            f'cvd_{label}_pct': _r(w['cvd_pct'], 2),
            f'buyer_ratio_{label}': _r(w['buyer_ratio'], 2),
            f'flow_{label}_score': round(_clamp(score, 0.0, 100.0), 1),
            f'flow_{label}_direction': _direction(w['cvd_pct']),
            f'trade_count_{label}': w['trades'],
            f'agg_count_{label}': w['agg'],
            f'notional_{label}': round(w['tot'], 2),
            f'n_eff_{label}': round(w['n_eff'], 1),
            f'window_coverage_sec_{label}': round(w['cov_sec'], 1),
            f'window_coverage_ratio_{label}': round(w['cov_ratio'], 4),
            f'{label}_complete': w['cov_ratio'] >= WINDOW_COMPLETE_MIN,   # KISMİ pencere karar/alarm verisi değildir
            f'large_buy_count_{label}': w['lbc'],
            f'large_buy_value_{label}': round(w['lbv'], 2),
            f'large_sell_count_{label}': w['lsc'],
            f'large_sell_value_{label}': round(w['lsv'], 2),
            f'whale_net_notional_{label}': round(w['lbv'] - w['lsv'], 2),
            f'flow_confidence_{label}': fc,
            f'fc_{label}_count': parts['count'],
            f'fc_{label}_notional': parts['notional'],
            f'fc_{label}_coverage': parts['coverage'],
            f'fc_{label}_freshness': parts['freshness'],
        })

    # ── 1 dakika önceki aynı pencerelere göre delta ──
    prev = {label: win(1, length) for label, length in FLOW_WINDOWS}
    delta_cov = min(min(wins[l]['cov_ratio'], prev[l]['cov_ratio']) for l, _ in FLOW_WINDOWS)
    for label, _ in FLOW_WINDOWS:
        ok = min(wins[label]['cov_ratio'], prev[label]['cov_ratio']) >= DELTA_MIN_COVERAGE
        out[f'cvd_{label}_delta'] = round(wins[label]['cvd'] - prev[label]['cvd'], 2) if ok else None
    for label in ('1m', '5m'):
        ok = min(wins[label]['cov_ratio'], prev[label]['cov_ratio']) >= DELTA_MIN_COVERAGE
        a, b = wins[label]['buyer_ratio'], prev[label]['buyer_ratio']
        out[f'buyer_ratio_delta_{label}'] = round(a - b, 2) if ok and a is not None and b is not None else None
    out['flow_delta_coverage_ratio'] = round(delta_cov, 4)

    # ── dakika adımlı kümülatif CVD eğimi ($/dk ve hacme normalize) ──
    def slope(k_newest, n):
        ks_old_to_new = list(range(k_newest + n - 1, k_newest - 1, -1))
        cov = 1.0 - sum(unc[k] for k in ks_old_to_new) / (n * 60_000.0)
        if cov < DELTA_MIN_COVERAGE:
            return None, None
        ys = [0.0]
        cum = 0.0
        vol = 0.0
        for k in ks_old_to_new:
            cum += b_buy[k] - b_sell[k]
            vol += b_buy[k] + b_sell[k]
            ys.append(cum)
        s = _ols_slope(ys)
        norm = (s / (vol / n)) if (s is not None and vol > 0) else None
        return s, norm

    s3, n3 = slope(0, 3)
    s5, n5 = slope(0, 5)
    sp3, np3 = slope(3, 3)
    out.update({
        'cvd_slope_3m': _r(s3, 2), 'cvd_slope_3m_norm': _r(n3, 4),
        'cvd_slope_5m': _r(s5, 2), 'cvd_slope_5m_norm': _r(n5, 4),
        'cvd_slope_prev_3m_norm': _r(np3, 4),
    })
    if n3 is None or np3 is None:
        out['cvd_turn_3m'] = None
    elif np3 <= -TURN_DEADBAND and n3 >= TURN_DEADBAND:
        out['cvd_turn_3m'] = 'UP'
    elif np3 >= TURN_DEADBAND and n3 <= -TURN_DEADBAND:
        out['cvd_turn_3m'] = 'DOWN'
    else:
        out['cvd_turn_3m'] = 'NONE'

    lw = last_whale
    out.update({
        'last_whale_time_ms': lw['time_ms'] if lw else None,
        'last_whale_side': lw['side'] if lw else None,
        'last_whale_usd': round(lw['usd'], 2) if lw else None,
        'last_whale_price': lw['price'] if lw else None,
    })
    return out


KLINE_SETTLE_MS = 10_000   # Binance REST mumu kapanıştan sonraki ilk saniyelerde henüz tamamlanmamış olabilir (canlı ölçüm: 1-3 sn'de %13-45 eksik)


def pool_kline_check(pool, candles_1m, asof_ms, kline_asof_ms=None):
    """Oturmuş son KAPANMIŞ 1m barda havuz toplamı ile Binance kline toplamını karşılaştır (tamlık kanıtı).
    Bar, mumlar çekilmeden en az KLINE_SETTLE_MS önce kapanmış olmalı; yoksa bir önceki bar kullanılır."""
    res = {'kcheck_bar_open': None, 'kcheck_status': 'no_bar', 'pool_vs_kline_notional_ratio': None,
           'pool_vs_kline_trades_ratio': None, 'pool_vs_kline_taker_buy_ratio': None}
    times = candles_1m.get('time') or []
    limit = min(asof_ms, (kline_asof_ms if kline_asof_ms is not None else asof_ms) - KLINE_SETTLE_MS)
    idx = None
    for i in range(len(times) - 1, -1, -1):
        if times[i] * 1000 + 60_000 <= limit:
            idx = i
            break
    if idx is None:
        return res
    open_ms = times[idx] * 1000
    close_ms = open_ms + 60_000
    res['kcheck_bar_open'] = open_ms
    if pool.coverage_start_ms is None or pool.uncovered_ms(open_ms, close_ms) > 0:
        res['kcheck_status'] = 'pool_incomplete'
        return res
    usd = buy = 0.0
    trades = 0
    for (T, _a, _p, _q, u, is_buy, ntr) in pool.trades:
        if open_ms <= T < close_ms:
            usd += u
            trades += ntr
            if is_buy:
                buy += u
    amount = candles_1m['amount'][idx]
    k_trades = (candles_1m.get('trades') or [None] * len(times))[idx]
    k_buy = (candles_1m.get('taker_buy') or [None] * len(times))[idx]
    res['kcheck_status'] = 'ok'
    res['pool_vs_kline_notional_ratio'] = round(usd / amount, 4) if amount else None
    res['pool_vs_kline_trades_ratio'] = round(trades / k_trades, 4) if k_trades else None
    res['pool_vs_kline_taker_buy_ratio'] = round(buy / k_buy, 4) if k_buy else None
    return res


# ═══════════════════════════════════════════════════════════════════════
# 4. ORDERBOOK
# ═══════════════════════════════════════════════════════════════════════

OB_KEYS = ('ob_best_bid', 'ob_best_ask', 'spread_bps', 'microprice_deviation_bps', 'orderbook_imbalance',
           'ob_imbalance_top5', 'ob_bid_notional_20', 'ob_ask_notional_20', 'ob_depth_span_bps',
           'ob_timestamp_ms', 'ob_age_ms', 'ob_stale', 'ob_error')


def orderbook_features(depth, now_ms):
    """Binance /fapi/v1/depth?limit=20 cevabından özet. depth=None ise boş alanlar."""
    out = {k: None for k in OB_KEYS}
    out['ob_stale'] = True                     # aksi kanıtlanana kadar bayat say
    if not depth:
        out['ob_error'] = 'no_data'
        return out
    try:
        bids = [(float(p), float(q)) for p, q in depth.get('bids', [])]
        asks = [(float(p), float(q)) for p, q in depth.get('asks', [])]
        if not bids or not asks:
            out['ob_error'] = 'empty_book'
            return out
        bb, bq = bids[0]
        ba, aq = asks[0]
        mid = (bb + ba) / 2.0
        micro = (bb * aq + ba * bq) / (bq + aq) if (bq + aq) > 0 else mid

        def notional(levels, n):
            return sum(p * q for p, q in levels[:n])

        b5, a5 = notional(bids, 5), notional(asks, 5)
        b20, a20 = notional(bids, 20), notional(asks, 20)
        span = max(asks[-1][0] - mid, mid - bids[-1][0])
        E = depth.get('E') or depth.get('T')
        age = (now_ms - int(E)) if E else None
        out.update({
            'ob_timestamp_ms': int(E) if E else None,
            'ob_age_ms': age,
            'ob_stale': (age is None) or age > OB_STALE_MS or age < -OB_STALE_MS,
            'ob_best_bid': bb, 'ob_best_ask': ba,
            'spread_bps': round((ba - bb) / mid * 1e4, 3),
            'microprice_deviation_bps': round((micro - mid) / mid * 1e4, 3),
            'orderbook_imbalance': round((b20 - a20) / (b20 + a20), 4) if (b20 + a20) > 0 else None,
            'ob_imbalance_top5': round((b5 - a5) / (b5 + a5), 4) if (b5 + a5) > 0 else None,
            'ob_bid_notional_20': round(b20, 2), 'ob_ask_notional_20': round(a20, 2),
            'ob_depth_span_bps': round(span / mid * 1e4, 2),
            'ob_error': None,
        })
    except Exception as e:
        out['ob_error'] = f"{type(e).__name__}: {e}"
    return out


# ═══════════════════════════════════════════════════════════════════════
# 5. BAR HİZALI İNDİKATÖR SERİLERİ (REALF / Fatigue / Unpriced delta)
# ═══════════════════════════════════════════════════════════════════════

def indicator_series_features(rows):
    """rows: get_recent_minute_history() çıktısı, eskiden yeniye, SON satır = canlı (açık) bar.
    "1m önce" = bir önceki barın KAPANIŞTAKİ değeri (kapalı mumlarla yeniden hesaplanmış)."""
    def series(key):
        return [r.get(key) for r in rows]

    def ago(vals, k):
        return vals[-1 - k] if len(vals) > k else None

    def diff(a, b):
        return round(a - b, 5) if a is not None and b is not None else None

    out = {}
    rv = series('realf')
    fv = series('fat')
    uv = series('inventory')
    now_r, now_f, now_u = ago(rv, 0), ago(fv, 0), ago(uv, 0)
    out.update({
        'realf_now': now_r, 'realf_1m_ago': ago(rv, 1), 'realf_3m_ago': ago(rv, 3), 'realf_5m_ago': ago(rv, 5),
        'realf_d1': _r(diff(now_r, ago(rv, 1)), 2), 'realf_d3': _r(diff(now_r, ago(rv, 3)), 2), 'realf_d5': _r(diff(now_r, ago(rv, 5)), 2),
        'unpriced_now': now_u,
        'unpriced_d1': diff(now_u, ago(uv, 1)), 'unpriced_d3': diff(now_u, ago(uv, 3)), 'unpriced_d5': diff(now_u, ago(uv, 5)),
        'fatigue_now': now_f, 'fatigue_1m_ago': ago(fv, 1), 'fatigue_3m_ago': ago(fv, 3), 'fatigue_5m_ago': ago(fv, 5),
        'fatigue_delta_1m': _r(diff(now_f, ago(fv, 1)), 2), 'fatigue_delta_3m': _r(diff(now_f, ago(fv, 3)), 2),
        'fatigue_delta_5m': _r(diff(now_f, ago(fv, 5)), 2),
    })
    series_out = {
        'realf_series': rv, 'fatigue_series': fv, 'unpriced_series': uv,
        'bar_time_series': series('open_ms'), 'bar_close_series': series('close'),
        'bar_notional_series': [_r(v, 2) for v in series('tot')], 'bar_taker_buy_series': [_r(v, 2) for v in series('tb')],
        'bar_cvd_series': [_r(v, 2) for v in series('cvd')], 'bar_trades_series': series('trades'),
    }
    return out, series_out


# ═══════════════════════════════════════════════════════════════════════
# 6. ÇALIŞTIRMA BAĞLAMI, KONSOL AYNASI, JSONL / CSV YAZICI
# ═══════════════════════════════════════════════════════════════════════

def code_fingerprint(paths):
    h = hashlib.sha256()
    for p in paths:
        try:
            with open(p, 'rb') as f:
                h.update(f.read())
        except OSError:
            h.update(b'<missing>')
    return h.hexdigest()[:16]


def git_commit(directory):
    """Klasör bir git deposuysa kısa commit; değilse None (o durumda code_fingerprint kodu tanımlar)."""
    try:
        r = subprocess.run(['git', '-C', directory, 'rev-parse', '--short', 'HEAD'],
                           capture_output=True, text=True, timeout=3)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


def make_snapshot_id(symbol, captured_ms):
    sym = symbol.upper().replace('.P', '')
    if sym.endswith('_USDT'):
        sym = sym[:-5]
    elif sym.endswith('USDT'):
        sym = sym[:-4]
    local = datetime.fromtimestamp(captured_ms / 1000.0)
    return f"{sym}_{local.strftime('%Y%m%d_%H%M%S')}_{captured_ms % 1000:03d}"


def _append_text(path, text, retries=4):
    """OneDrive kilitlerine karşı tekrar denemeli ekleme. Başarısızsa False (veri tamponda kalır)."""
    for attempt in range(retries):
        try:
            with open(path, 'a', encoding='utf-8', newline='') as f:
                f.write(text)
            return True
        except OSError:
            time.sleep(0.25 * (attempt + 1))
    return False


MAX_PENDING_BYTES = 64 * 1024 * 1024   # disk yazılamazsa bellekte en fazla bu kadar tutulur (uzun çalışma koruması)


def hour_key(ms):
    """Saatlik dosya parçası anahtarı (yerel saat): 20260917_18"""
    return datetime.fromtimestamp(ms / 1000.0).strftime('%Y%m%d_%H')


class _HourlyBuffer:
    """Saat anahtarına göre sıralı bekleyen metin; yazılamayanlar tutulur, üst sınırda en eskisi atılır."""

    def __init__(self):
        self.chunks = []        # [[key, [texts], bytes]]
        self.size = 0
        self.dropped_bytes = 0

    def add(self, key, text):
        if self.chunks and self.chunks[-1][0] == key:
            self.chunks[-1][1].append(text)
            self.chunks[-1][2] += len(text)
        else:
            self.chunks.append([key, [text], len(text)])
        self.size += len(text)
        while self.size > MAX_PENDING_BYTES and len(self.chunks) > 1:
            _k, _t, n = self.chunks.pop(0)
            self.size -= n
            self.dropped_bytes += n
        if self.size > MAX_PENDING_BYTES and self.chunks:
            texts = self.chunks[0][1]
            while self.size > MAX_PENDING_BYTES and len(texts) > 1:
                n = len(texts.pop(1))          # ilk metin (CSV başlığı olabilir) korunur
                self.chunks[0][2] -= n
                self.size -= n
                self.dropped_bytes += n

    def flush(self, path_for_key):
        """Başarısız olursa False döner ve kalanı sırasıyla tutar."""
        while self.chunks:
            key, texts, n = self.chunks[0]
            if not _append_text(path_for_key(key), ''.join(texts)):
                return False
            self.chunks.pop(0)
            self.size -= n
        return True


class ConsoleSink:
    """Konsola basılan her şeyin dosya kopyası: console_YYYYMMDD_HH.txt (saatlik parçalar).
    Windows konsolu yalnız son ~9001 satırı tutar; bu dosyalar çalışmanın TAMAMINI tutar."""

    def __init__(self, run_dir, now=None):
        self.run_dir = run_dir
        self._now = now or (lambda: int(time.time() * 1000))
        self._buf = _HourlyBuffer()
        self._lock = threading.Lock()
        self.write_failures = 0

    def path_for(self, key):
        return os.path.join(self.run_dir, f"console_{key}.txt")

    def add(self, s):
        with self._lock:
            self._buf.add(hour_key(self._now()), s)
            big = self._buf.size > 1_000_000
        if big:
            self.flush()

    def flush(self):
        with self._lock:
            if self._buf.chunks and not self._buf.flush(self.path_for):
                self.write_failures += 1

    @property
    def dropped_bytes(self):
        return self._buf.dropped_bytes


class TeeStream:
    def __init__(self, stream, sink):
        self._stream = stream
        self._sink = sink

    def write(self, s):
        self._sink.add(s)
        try:
            return self._stream.write(s)
        except Exception:
            return len(s)

    def flush(self):
        try:
            self._stream.flush()
        finally:
            self._sink.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


class RunContext:
    def __init__(self, base_dir, script_dir, argv, settings):
        self.started_ms = int(time.time() * 1000)
        self.run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.run_dir = os.path.join(base_dir, f"run_{self.run_id}")
        os.makedirs(self.run_dir, exist_ok=True)
        self.seq = 0
        self.code_fingerprint = code_fingerprint([os.path.join(script_dir, 'live_tracker.py'), os.path.join(script_dir, 'tracker_v2.py')])
        self.git_commit = git_commit(script_dir)
        self.meta = {
            'run_id': self.run_id, 'started_at_ms': self.started_ms, 'argv': argv,
            'python': sys.version.split()[0], 'tracker_version': TRACKER_VERSION, 'dataset_schema': DATASET_SCHEMA,
            'code_fingerprint': self.code_fingerprint, 'git_commit': self.git_commit, 'settings': settings,
            'files': {'console': 'console_YYYYMMDD_HH.txt (saatlik)', 'snapshots_jsonl': 'snapshots_YYYYMMDD_HH.jsonl (saatlik)',
                      'snapshots_csv': 'snapshots_YYYYMMDD_HH.csv (saatlik, her parçada başlık)', 'outcomes_jsonl': 'outcomes.jsonl',
                      'merged_csv': 'snapshots_with_outcomes_YYYYMMDD.csv (günlük, SONUCLARI_HESAPLA.bat üretir)'},
        }
        self.write_meta()

    def next_seq(self):
        self.seq += 1
        return self.seq

    def write_meta(self, **extra):
        self.meta.update(extra)
        path = os.path.join(self.run_dir, 'run_meta.json')
        for attempt in range(4):
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(self.meta, f, ensure_ascii=False, indent=2)
                return True
            except OSError:
                time.sleep(0.25 * (attempt + 1))
        return False


def _clean_json(v):
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, (list, tuple)):
        return [_clean_json(x) for x in v]
    return v


def _json_line(record):
    return json.dumps({k: _clean_json(v) for k, v in record.items()}, ensure_ascii=False, separators=(',', ':'), default=str) + '\n'


def _csv_cell(v):
    v = _finite(v)
    return '' if v is None else v


class SnapshotWriter:
    """Saatlik parçalar (snapshot'ın yakalandığı yerel saate göre):
         snapshots_YYYYMMDD_HH.jsonl  tam kayıt: skalerler + seriler
         snapshots_YYYYMMDD_HH.csv    yalnız skalerler; sütunlar çalışma boyunca sabit, her parçada başlık var
       Tek dosya: outcomes.jsonl (küçük; ~0,5 KB / snapshot)."""

    def __init__(self, run_dir):
        self.run_dir = run_dir
        self.outcomes_path = os.path.join(run_dir, 'outcomes.jsonl')
        self.csv_fields = None
        self._csv_field_set = set()
        self._csv_parts_started = set()
        self._jsonl = _HourlyBuffer()
        self._csv = _HourlyBuffer()
        self._out = _HourlyBuffer()
        self.snapshots = 0
        self.outcomes = 0
        self.write_failures = 0
        self.invalid_snapshots = 0
        self._warned_extra = False
        self._warned_required = False

    def jsonl_path(self, key):
        return os.path.join(self.run_dir, f"snapshots_{key}.jsonl")

    def csv_path(self, key):
        return os.path.join(self.run_dir, f"snapshots_{key}.csv")

    def add_snapshot(self, flat, series):
        missing = missing_required(flat)
        if missing:
            self.invalid_snapshots += 1
            if not self._warned_required:
                self._warned_required = True
                print(f"  🚨 ZORUNLU ALAN EKSİK (snapshot yazıldı ama required_fields_missing ile işaretlendi): {missing}")
        key = hour_key(flat.get('captured_at_ms') or int(time.time() * 1000))
        full = dict(flat)
        full.update(series)
        self._jsonl.add(key, _json_line(full))
        if self.csv_fields is None:
            self.csv_fields = list(flat.keys())
            self._csv_field_set = set(self.csv_fields)
        if key not in self._csv_parts_started:
            self._csv_parts_started.add(key)
            if not os.path.exists(self.csv_path(key)):
                self._csv.add(key, self._csv_line(self.csv_fields))
        extra = [k for k in flat if k not in self._csv_field_set]
        if extra and not self._warned_extra:
            self._warned_extra = True
            print(f"  ⚠️ CSV başlığında olmayan alan(lar) yalnız JSONL'e yazıldı: {extra[:5]}")
        self._csv.add(key, self._csv_line([_csv_cell(flat.get(k)) for k in self.csv_fields]))
        self.snapshots += 1

    @staticmethod
    def _csv_line(cells):
        buf = io.StringIO()
        csv.writer(buf, lineterminator='\n').writerow(cells)
        return buf.getvalue()

    def add_outcome(self, rec):
        self._out.add('outcomes', _json_line(rec))
        self.outcomes += 1

    def flush(self):
        for buf, path_for in ((self._jsonl, self.jsonl_path), (self._csv, self.csv_path), (self._out, lambda _k: self.outcomes_path)):
            if buf.chunks and not buf.flush(path_for):
                self.write_failures += 1

    @property
    def dropped_bytes(self):
        return self._jsonl.dropped_bytes + self._csv.dropped_bytes + self._out.dropped_bytes


# ═══════════════════════════════════════════════════════════════════════
# 7. SONUÇ DEĞERLENDİRİCİ (forward return · MFE · MAE)
# ═══════════════════════════════════════════════════════════════════════

HORIZONS_MIN = (1, 3, 5, 10, 20, 30, 60)
EXCURSION_MIN = (5, 10, 20, 30, 60)


def bars_from_candles(candles, now_ms):
    """live_tracker mum sözlüğü → yalnız KAPANMIŞ barlar: [(open_ms, open, high, low, close)]"""
    out = []
    t, o, h, l, c = candles['time'], candles['open'], candles['high'], candles['low'], candles['close']
    for i in range(len(t)):
        open_ms = int(t[i]) * 1000
        if open_ms + 60_000 <= now_ms:
            out.append((open_ms, o[i], h[i], l[i], c[i]))
    return out


def evaluate_outcome(entry_price, t0_ms, bars, now_ms):
    """Tanımlar (LOGGER_V2_ALANLAR.md):
      fwd_ret_Hm : t0+H dakikaya EN YAKIN 1m bar kapanışının entry'ye göre % getirisi (±30 sn çözünürlük).
      mfe_Hm/mae_Hm : t0 → o çıkış kapanışı arasındaki en yüksek/en düşük fiyatın % sapması.
                      Yol = entry + yakalama barının KAPANIŞI + sonraki barların high/low'u
                      (yakalama barının high/low'u t0'dan önceyi içerebileceği için kullanılmaz).
    Olgunlaşmamışsa (60m çıkış barı kapanmadıysa) None döner."""
    if not entry_price or entry_price <= 0:
        return None
    by_open = {b[0]: b for b in bars}
    cap_open = (t0_ms // 60_000) * 60_000
    exits = {H: ((t0_ms + H * 60_000 + 30_000) // 60_000) * 60_000 for H in HORIZONS_MIN}
    if exits[max(HORIZONS_MIN)] > now_ms:
        return None
    res = {}
    complete = True
    for H in HORIZONS_MIN:
        bar = by_open.get(exits[H] - 60_000)
        if bar is None:
            res[f'fwd_ret_{H}m'] = None
            complete = False
        else:
            res[f'fwd_ret_{H}m'] = round((bar[4] - entry_price) / entry_price * 100.0, 4)
    for H in EXCURSION_MIN:
        close_ms = exits[H]
        hi = lo = entry_price
        missing = False
        cap_bar = by_open.get(cap_open)
        if cap_bar is not None and cap_open + 60_000 <= close_ms:
            hi = max(hi, cap_bar[4])
            lo = min(lo, cap_bar[4])
        elif cap_bar is None:
            missing = True
        o = cap_open + 60_000
        while o + 60_000 <= close_ms:
            b = by_open.get(o)
            if b is None:
                missing = True
            else:
                hi = max(hi, b[2])
                lo = min(lo, b[3])
            o += 60_000
        if missing:
            complete = False
            res[f'mfe_{H}m'] = res[f'mae_{H}m'] = None
        else:
            res[f'mfe_{H}m'] = round((hi - entry_price) / entry_price * 100.0, 4)
            res[f'mae_{H}m'] = round((lo - entry_price) / entry_price * 100.0, 4)
    res['outcome_complete'] = complete
    return res


class LiveOutcomeTracker:
    def __init__(self, writer, run_id):
        self.writer = writer
        self.run_id = run_id
        self.pending = {}

    def register(self, symbol, snapshot_id, t0_ms, entry_price):
        self.pending.setdefault(symbol, deque()).append((snapshot_id, t0_ms, entry_price))

    def evaluate(self, symbol, candles_1m, now_ms):
        q = self.pending.get(symbol)
        if not q:
            return 0
        written = 0
        bars = None
        while q:
            sid, t0, entry = q[0]
            if ((t0 + max(HORIZONS_MIN) * 60_000 + 30_000) // 60_000) * 60_000 > now_ms:
                break
            if bars is None:
                bars = bars_from_candles(candles_1m, now_ms)
            res = evaluate_outcome(entry, t0, bars, now_ms)
            q.popleft()
            if res is None:
                continue
            rec = {'snapshot_id': sid, 'symbol': symbol, 'run_id': self.run_id, 't0_ms': t0, 'entry_price': entry,
                   'OUTCOME_VERSION': OUTCOME_VERSION, 'evaluated_at_ms': now_ms, 'source': 'live'}
            rec.update(res)
            self.writer.add_outcome(rec)
            written += 1
        return written


def _fetch_binance_1m_range(symbol, start_ms, end_ms):
    bars = []
    cursor = start_ms
    while cursor < end_ms:
        data = http_get_json(f"{BINANCE_FAPI}/fapi/v1/klines?symbol={symbol}&interval=1m&startTime={cursor}&endTime={end_ms}&limit=1000")
        if not data:
            break
        for k in data:
            bars.append((int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4])))
        nxt = int(data[-1][0]) + 60_000
        if nxt <= cursor:
            break
        cursor = nxt
        if len(data) < 1000:
            break
    return bars


def resolve_run_dir(base_dir, which):
    if which and which != 'latest':
        return which if os.path.isabs(which) or os.path.isdir(which) else os.path.join(base_dir, which)
    runs = sorted(d for d in os.listdir(base_dir) if d.startswith('run_') and os.path.isdir(os.path.join(base_dir, d))) if os.path.isdir(base_dir) else []
    return os.path.join(base_dir, runs[-1]) if runs else None


SNAPSHOT_PART_RE = re.compile(r'^snapshots_(\d{8})_(\d{2})\.csv$')


def run_is_live(run_dir, stale_ms=10 * 60_000):
    """run_meta.json'a göre takip hâlâ yazıyor mu (düzgün durdurulmadıysa son güncelleme 10 dk'dan yeni mi)."""
    try:
        with open(os.path.join(run_dir, 'run_meta.json'), encoding='utf-8') as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return False
    if meta.get('stopped_at_ms'):
        return False
    last = meta.get('updated_at_ms') or meta.get('started_at_ms') or 0
    return int(time.time() * 1000) - int(last) < stale_ms


def snapshot_csv_parts(run_dir):
    """Saatlik CSV parçaları [(gün, yol)] sıralı. Eski tek dosya düzeni (snapshots.csv) → [('', yol)]."""
    parts = []
    for name in sorted(os.listdir(run_dir)):
        m = SNAPSHOT_PART_RE.match(name)
        if m:
            parts.append((m.group(1), os.path.join(run_dir, name)))
    legacy = os.path.join(run_dir, 'snapshots.csv')
    if not parts and os.path.exists(legacy):
        parts.append(('', legacy))
    return parts


def _read_snapshot_index(parts):
    """Sonuç hesabı için gereken alanlar. Yazılmakta olan son satır (eksik sütun) atlanır."""
    snaps = []
    for _day, path in parts:
        with open(path, encoding='utf-8', newline='') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header or 'snapshot_id' not in header:
                continue
            idx = {k: header.index(k) for k in ('snapshot_id', 'symbol', 'provider', 'run_id', 'kline_asof_ms', 'captured_at_ms', 'price') if k in header}
            for row in reader:
                if len(row) != len(header):
                    continue

                def g(k):
                    i = idx.get(k)
                    return row[i] if i is not None and row[i] != '' else None
                try:
                    t0 = int(float(g('kline_asof_ms') or g('captured_at_ms')))
                    price = float(g('price'))
                except (TypeError, ValueError):
                    continue
                snaps.append({'snapshot_id': g('snapshot_id'), 'symbol': g('symbol'), 'provider': g('provider'),
                              'run_id': g('run_id'), 't0': t0, 'price': price})
    return snaps


def offline_evaluate(run_dir, now_ms=None, fetch_bars=None, verbose=True):
    """Çalışma bittikten sonra (veya SÜRERKEN) eksik sonuçları Binance 1m mumlarıyla hesaplar,
    outcomes.jsonl'e ekler ve günlük snapshots_with_outcomes_YYYYMMDD.csv dosyalarını yeniden üretir.
    Tekrar çalıştırmak güvenlidir."""
    fetch_bars = fetch_bars or _fetch_binance_1m_range
    now_ms = now_ms or CLOCK.now_ms()
    out_path = os.path.join(run_dir, 'outcomes.jsonl')
    parts = snapshot_csv_parts(run_dir)
    if not parts:
        raise FileNotFoundError(os.path.join(run_dir, 'snapshots_YYYYMMDD_HH.csv'))
    snaps = _read_snapshot_index(parts)
    # Takip hâlâ çalışıyorsa son sonuçları canlı değerlendirici yazacak; çift kayıt olmasın diye 6 dk pay bırakılır.
    live_run = run_is_live(run_dir)
    extra_ms = 6 * 60_000 if live_run else 0

    done = {}
    if os.path.exists(out_path):
        with open(out_path, encoding='utf-8') as f:
            for line in f:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get('outcome_complete'):
                    done[r['snapshot_id']] = r

    todo = {}
    immature = 0
    for s in snaps:
        if s['snapshot_id'] in done:
            continue
        t0 = s['t0']
        if ((t0 + max(HORIZONS_MIN) * 60_000 + 30_000) // 60_000) * 60_000 + extra_ms > now_ms:
            immature += 1
            continue
        todo.setdefault((s.get('provider') or 'BINANCE', s['symbol']), []).append((s, t0))

    new_records = []
    skipped = 0
    missing_bars = 0
    for (provider, symbol), items in todo.items():
        if provider != 'BINANCE':
            skipped += len(items)
            continue
        start = (min(t0 for _, t0 in items) // 60_000) * 60_000 - 60_000
        end = max(t0 for _, t0 in items) + (max(HORIZONS_MIN) + 2) * 60_000
        try:
            bars = [b for b in fetch_bars(symbol, start, min(end, now_ms)) if b[0] + 60_000 <= now_ms]
        except Exception as e:
            if verbose:
                print(f"  ⚠️ {symbol} mumları alınamadı: {e}")
            skipped += len(items)
            continue
        for s, t0 in items:
            res = evaluate_outcome(s['price'], t0, bars, now_ms)
            if res is None:
                continue
            if not res['outcome_complete']:
                missing_bars += 1          # eksik mum → yazılmaz, sonraki çalıştırmada tekrar denenir
                continue
            rec = {'snapshot_id': s['snapshot_id'], 'symbol': symbol, 'run_id': s.get('run_id'), 't0_ms': t0,
                   'entry_price': s['price'], 'OUTCOME_VERSION': OUTCOME_VERSION, 'evaluated_at_ms': now_ms, 'source': 'offline'}
            rec.update(res)
            new_records.append(rec)
            done[s['snapshot_id']] = rec

    if new_records and not _append_text(out_path, ''.join(_json_line(r) for r in new_records)):
        raise OSError(f"{out_path} yazılamadı (dosya kilitli olabilir) — tekrar çalıştırın")

    merged = write_merged_csv(run_dir, done, parts)
    if verbose:
        if live_run:
            print("  ℹ️ Takip hâlâ çalışıyor: son ~66 dakikanın sonuçlarını takip programı kendisi yazacak; tabloyu sonra yeniden üretebilirsiniz.")
        print(f"  ✅ Sonuç değerlendirme: {len(snaps)} snapshot | tamamlanan {len(done)} | bu çalıştırmada yazılan {len(new_records)} | "
              f"henüz olgunlaşmamış {immature} | eksik mum {missing_bars} | atlanan {skipped}")
        for path in merged:
            print(f"     Birleşik tablo: {path}")
    return {'snapshots': len(snaps), 'complete': len(done), 'written': len(new_records), 'immature': immature,
            'missing_bars': missing_bars, 'skipped': skipped, 'merged_files': merged}


OUTCOME_COLUMNS = ([f'fwd_ret_{h}m' for h in HORIZONS_MIN] +
                   [c for h in EXCURSION_MIN for c in (f'mfe_{h}m', f'mae_{h}m')] + ['outcome_complete', 'OUTCOME_VERSION'])


def write_merged_csv(run_dir, outcomes_by_id, parts=None):
    """Gün başına tek birleşik tablo: saatlik CSV parçaları + sonuç sütunları → snapshots_with_outcomes_YYYYMMDD.csv
    (eski tek dosya düzeninde snapshots_with_outcomes.csv). Dosya Excel'de açıksa .tmp olarak bırakılır."""
    parts = parts if parts is not None else snapshot_csv_parts(run_dir)
    by_day = {}
    for day, path in parts:
        by_day.setdefault(day, []).append(path)
    outputs = []
    for day, paths in sorted(by_day.items()):
        dst = os.path.join(run_dir, f"snapshots_with_outcomes_{day}.csv" if day else 'snapshots_with_outcomes.csv')
        tmp = dst + '.tmp'
        base_header = None
        sid_idx = None
        with open(tmp, 'w', encoding='utf-8', newline='') as f_out:
            writer = csv.writer(f_out, lineterminator='\n')
            for path in paths:
                with open(path, encoding='utf-8', newline='') as f_in:
                    reader = csv.reader(f_in)
                    header = next(reader, None)
                    if not header or 'snapshot_id' not in header:
                        continue
                    if base_header is None:
                        base_header = header
                        sid_idx = header.index('snapshot_id')
                        writer.writerow(header + OUTCOME_COLUMNS)
                    remap = None if header == base_header else [header.index(c) if c in header else None for c in base_header]
                    for row in reader:
                        if len(row) != len(header):
                            continue
                        if remap is not None:
                            row = [row[i] if i is not None else '' for i in remap]
                        o = outcomes_by_id.get(row[sid_idx], {})
                        writer.writerow(row + ['' if o.get(c) is None else o.get(c) for c in OUTCOME_COLUMNS])
        for attempt in range(4):
            try:
                os.replace(tmp, dst)
                outputs.append(dst)
                break
            except OSError:
                time.sleep(0.5 * (attempt + 1))
        else:
            print(f"  ⚠️ {dst} güncellenemedi (dosya açık olabilir) — yeni tablo: {tmp}")
            outputs.append(tmp)
    return outputs


# ═══════════════════════════════════════════════════════════════════════
# 8. KENDİ KENDİNE TEST (ağ gerektirmez)
# ═══════════════════════════════════════════════════════════════════════

def selftest():
    import tempfile
    fails = []

    def check(name, cond, detail=''):
        print(f"  {'✓' if cond else '✗'} {name}" + (f" — {detail}" if detail and not cond else ''))
        if not cond:
            fails.append(name)

    # 0) gerçek saat nesnesi ve ağ ipucu (canlı döngünün kullandığı yüzey)
    check('CLOCK.now_ms çalışıyor', callable(getattr(CLOCK, 'now_ms', None)) and abs(CLOCK.now_ms() - CLOCK.offset_ms - time.time() * 1000) < 5000)
    check('WARP ipucu (TLS engeli)', 'WARP' in (network_hint('<urlopen error [SSL: WRONG_VERSION_NUMBER] wrong version number>') or ''))
    check('ipucu yok (alakasız hata)', network_hint('KeyError: price') is None)

    # 1) kapsama defteri
    p = TradePool('BINANCE', 'FUTURES', 'TESTUSDT')
    p.coverage_start_ms, p.known_until_ms = 100_000, 1_000_000
    p.mark_gap(400_000, 460_000)
    check('uncovered: tam kapsama', p.uncovered_ms(200_000, 300_000) == 0)
    check('uncovered: başlangıç öncesi', p.uncovered_ms(40_000, 160_000) == 60_000)
    check('uncovered: boşluk', p.uncovered_ms(380_000, 480_000) == 60_000)
    check('uncovered: senkron sonrası', p.uncovered_ms(990_000, 1_050_000) == 50_000)

    # 2) pencere / delta / eğim — bilinen akış
    asof = 10_000_000
    p = TradePool('BINANCE', 'FUTURES', 'TESTUSDT')
    aid = 0
    for k in range(15, -1, -1):          # her dakikada 10 işlem; dakika k'da alış payı artıyor
        for j in range(10):
            aid += 1
            T = asof - k * 60_000 - 59_000 + j * 5_000
            is_buy = j < (10 - k // 2)
            p.ingest_binance([{'a': aid, 'T': T, 'p': '100', 'q': '1', 'm': not is_buy, 'f': aid, 'l': aid}], 'TESTUSDT')
    p.coverage_start_ms, p.known_until_ms = asof - 20 * 60_000, asof
    ff = compute_flow_features(p, asof, whale_usd=1e9)
    check('1m işlem sayısı', ff['trade_count_1m'] == 10, str(ff['trade_count_1m']))
    check('15m kapsama tam', ff['window_coverage_ratio_15m'] == 1.0)
    check('1m alıcı oranı 100', ff['buyer_ratio_1m'] == 100.0, str(ff['buyer_ratio_1m']))
    check('cvd_1m_delta tanımlı', ff['cvd_1m_delta'] is not None)
    check('cvd eğimi pozitif', (ff['cvd_slope_3m'] or 0) > 0, str(ff['cvd_slope_3m']))
    p.mark_gap(asof - 150_000, asof - 90_000)
    ff2 = compute_flow_features(p, asof, whale_usd=1e9)
    check('boşluklu pencerede delta None', ff2['cvd_1m_delta'] is None and ff2['window_coverage_ratio_5m'] < 1.0)

    # 3) flow confidence — GPT örnekleri
    fa, _ = flow_confidence(4, 310.0, 1.0, 10_000, 60)
    fb, _ = flow_confidence(1800, 4_800_000.0, 1.0, 100, 60)
    check('FC ince akış düşük', fa < 25, str(fa))
    check('FC kalın akış yüksek', fb > 90, str(fb))
    check('FC kapsama 0 → 0', flow_confidence(500, 1e6, 0.0, 100, 60)[0] == 0.0)

    # 4) burst / büyük işlem
    p = TradePool('BINANCE', 'FUTURES', 'TESTUSDT')
    T = asof - 30_000
    p.ingest_binance([{'a': 1, 'T': T, 'p': '100', 'q': '30', 'm': False},
                      {'a': 2, 'T': T, 'p': '101', 'q': '30', 'm': False},
                      {'a': 3, 'T': T + 5, 'p': '101', 'q': '1', 'm': True}], 'TESTUSDT')
    p.coverage_start_ms, p.known_until_ms = asof - 20 * 60_000, asof
    ff = compute_flow_features(p, asof, whale_usd=5000.0)
    check('aynı ms+yön burst tek büyük alış', ff['large_buy_count_1m'] == 1 and ff['large_buy_value_1m'] == 6030.0, str(ff['large_buy_value_1m']))

    # 4b) kline kontrolü taze (henüz oturmamış) barı kullanmamalı
    p = TradePool('BINANCE', 'FUTURES', 'TESTUSDT')
    bar0 = (asof // 60_000) * 60_000 - 120_000          # iki bar önce açılan (kapalı) bar
    p.ingest_binance([{'a': 1, 'T': bar0 + 1000, 'p': '10', 'q': '5', 'm': False},
                      {'a': 2, 'T': bar0 + 61_000, 'p': '10', 'q': '7', 'm': True}], 'TESTUSDT')
    p.coverage_start_ms, p.known_until_ms = bar0 - 60_000, asof
    candles = {'time': [bar0 // 1000, bar0 // 1000 + 60, bar0 // 1000 + 120], 'amount': [50.0, 70.0, 0.0],
               'trades': [1, 1, 0], 'taker_buy': [50.0, 0.0, 0.0]}
    fresh = pool_kline_check(p, candles, asof, kline_asof_ms=bar0 + 120_000 + 2_000)   # ikinci bar 2 sn önce kapandı
    check('kline kontrolü taze barı atlar', fresh['kcheck_bar_open'] == bar0 and fresh['pool_vs_kline_notional_ratio'] == 1.0, str(fresh))
    settled = pool_kline_check(p, candles, asof, kline_asof_ms=bar0 + 120_000 + 15_000)
    check('kline kontrolü oturmuş son barı kullanır', settled['kcheck_bar_open'] == bar0 + 60_000 and settled['pool_vs_kline_notional_ratio'] == 1.0, str(settled))

    # 5) senkron: devam, sayfa sınırı → boşluk, id sıfırlanması
    class FakeClock:
        def now_ms(self):
            return 50_000_000

    state = {'next': 1, 'T0': 49_000_000}

    def make(a):
        return {'a': a, 'T': state['T0'] + a, 'p': '10', 'q': '1', 'm': a % 2 == 0, 'f': a, 'l': a}

    def fake_http(url, timeout=10.0):
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(url).query)
        last = state['next'] - 1
        limit = int(q.get('limit', ['500'])[0])
        if 'fromId' in q:
            start = int(q['fromId'][0])
            return [make(a) for a in range(start, min(last, start + limit - 1) + 1)]
        return [make(a) for a in range(max(1, last - limit + 1), last + 1)]

    real_http = globals()['http_get_json']
    globals()['http_get_json'] = fake_http
    try:
        p = TradePool('BINANCE', 'FUTURES', 'TESTUSDT')
        state['next'] = 1501
        info = sync_binance_pool(p, FakeClock(), max_pages=2)
        check('bootstrap son 1000', info['mode'] == 'bootstrap' and p.last_id == 1500 and len(p.trades) == 1000)
        state['next'] = 2801
        info = sync_binance_pool(p, FakeClock(), max_pages=2)
        check('devam senkronu boşluksuz', info['mode'] == 'continuous' and p.last_id == 2800 and p.gap_events == 0, str(info))
        state['next'] = 9001
        info = sync_binance_pool(p, FakeClock(), max_pages=2)
        check('sayfa sınırında atla + boşluk', info['mode'] == 'jump' and p.gap_events == 1 and p.last_id == 9000, str(info))
        state['next'] = 101
        info = sync_binance_pool(p, FakeClock(), max_pages=2)
        check('id sıfırlanması → havuz reset', info['mode'] == 'id_reset' and p.resets == 1, str(info))
    finally:
        globals()['http_get_json'] = real_http

    # 6) sonuç değerlendirici — bilinen yol
    base = 1_700_000_000_000 - (1_700_000_000_000 % 60_000)
    bars = []
    for i in range(80):
        c = 100.0 + i * 0.1
        bars.append((base + i * 60_000, c - 0.05, c + 0.2, c - 0.3, c))
    t0 = base + 10_000            # yakalama barının 10. saniyesi, entry 100.0
    res = evaluate_outcome(100.0, t0, bars, base + 80 * 60_000)
    check('fwd_ret_1m = ilk bar kapanışı (±30sn)', res and res['fwd_ret_1m'] == 0.0, str(res and res['fwd_ret_1m']))
    check('fwd_ret_5m', res and res['fwd_ret_5m'] == round((100.4 - 100) / 100 * 100, 4), str(res and res['fwd_ret_5m']))
    check('mfe_5m yakalama barı high hariç', res and res['mfe_5m'] == round((100.4 + 0.2 - 100) / 100 * 100, 4), str(res and res['mfe_5m']))
    check('mae_5m ≤ 0', res and res['mae_5m'] <= 0.0)
    check('olgunlaşmamış → None', evaluate_outcome(100.0, t0, bars, t0 + 30 * 60_000) is None)
    t1 = base + 50_000            # 50. saniye → 1m çıkışı bir sonraki bar
    res1 = evaluate_outcome(100.0, t1, bars, base + 80 * 60_000)
    check('fwd_ret_1m (50. sn) sonraki bar', res1 and res1['fwd_ret_1m'] == round((100.1 - 100) / 100 * 100, 4), str(res1 and res1['fwd_ret_1m']))

    # 7) yazıcı (saatlik parçalar) + çevrimdışı günlük birleşik tablo
    with tempfile.TemporaryDirectory() as tmp:
        w = SnapshotWriter(tmp)
        times = [t0, t0 + 60_000, t0 + 120_000, t0 + 2 * 3_600_000, t0 + 24 * 3_600_000]   # aynı saat ×3, +2 saat, +1 gün
        req = {'dataset_schema': DATASET_SCHEMA, 'tracker_version': TRACKER_VERSION, 'structure_version': 'v1.2',
               'realf_engine': 'REALF_PY_V4_2_DERIVED', 'fatigue_version': 'ZPTDIFAT_PY_V1_4_DERIVED', 'code_fingerprint': 'test'}
        for i, ts in enumerate(times):
            flat = {'snapshot_id': f'TST_{i}', 'symbol': 'TESTUSDT', 'provider': 'BINANCE', 'run_id': 'x',
                    'kline_asof_ms': ts, 'captured_at_ms': ts, 'price': 100.0, 'x': float('nan'), 'none': None, **req}
            w.add_snapshot(flat, {'realf_series': [1, 2, 3]})
            if i == 1:
                w.flush()                                  # aynı saatin parçasına sonradan ekleme başlık tekrarlamamalı
        w.flush()
        k0, k1, k2 = hour_key(times[0]), hour_key(times[3]), hour_key(times[4])
        with open(os.path.join(tmp, f'snapshots_{k0}.csv'), encoding='utf-8') as f:
            lines = f.read().splitlines()
        check('saatlik CSV: tek başlık + 3 satır', len(lines) == 4 and lines[0].startswith('snapshot_id') and not lines[3].startswith('snapshot_id'))
        check('ayrı saat/gün parçaları başlıklı', all(open(os.path.join(tmp, f'snapshots_{k}.csv'), encoding='utf-8').readline().startswith('snapshot_id') for k in (k1, k2)))
        with open(os.path.join(tmp, f'snapshots_{k0}.jsonl'), encoding='utf-8') as f:
            parsed = [json.loads(x) for x in f]
        check('JSONL geçerli, NaN → null', len(parsed) == 3 and parsed[0]['x'] is None and parsed[0]['realf_series'] == [1, 2, 3])
        summary = offline_evaluate(tmp, now_ms=base + 80 * 60_000, fetch_bars=lambda s, a, b: bars, verbose=False)
        check('çevrimdışı değerlendirme 3 tamam + 2 olgunlaşmamış', summary['complete'] == 3 and summary['immature'] == 2, str(summary))
        summary2 = offline_evaluate(tmp, now_ms=base + 80 * 60_000, fetch_bars=lambda s, a, b: bars, verbose=False)
        check('tekrar çalıştırma yazmaz', summary2['written'] == 0, str(summary2))
        merged_files = sorted(os.path.basename(p) for p in summary2['merged_files'])
        check('gün başına birleşik tablo', merged_files == sorted({f'snapshots_with_outcomes_{k0[:8]}.csv', f'snapshots_with_outcomes_{k2[:8]}.csv'}), str(merged_files))
        with open(os.path.join(tmp, f'snapshots_with_outcomes_{k0[:8]}.csv'), encoding='utf-8') as f:
            merged = list(csv.DictReader(f))
        check('birleşik tabloda fwd_ret_5m dolu', len(merged) == (4 if k1[:8] == k0[:8] else 3) and merged[0]['fwd_ret_5m'] != '')

        sink_now = [times[0]]
        sink = ConsoleSink(tmp, now=lambda: sink_now[0])
        sink.add('a\n')
        sink_now[0] = times[3]
        sink.add('b\n')
        sink.flush()
        check('konsol saatlik parçalar', open(os.path.join(tmp, f'console_{k0}.txt'), encoding='utf-8').read() == 'a\n'
              and open(os.path.join(tmp, f'console_{k1}.txt'), encoding='utf-8').read() == 'b\n')
        check('geçerli kayıtlarda zorunlu alan hatası yok', w.invalid_snapshots == 0, str(w.invalid_snapshots))

    # 8) GELECEK SIZINTISI (leakage) · zorunlu alanlar · orderbook bayatlığı
    p = TradePool('BINANCE', 'FUTURES', 'TESTUSDT')
    p.ingest_binance([{'a': 1, 'T': asof - 30_000, 'p': '10', 'q': '1', 'm': False},
                      {'a': 2, 'T': asof + 15_000, 'p': '10', 'q': '99', 'm': False}], 'TESTUSDT')   # gelecekteki işlem
    p.coverage_start_ms, p.known_until_ms = asof - 20 * 60_000, asof
    ff_leak = compute_flow_features(p, asof, whale_usd=1e9)
    check('gelecekteki işlem pencereye girmiyor', ff_leak['notional_1m'] == 10.0 and ff_leak['trade_count_1m'] == 1,
          f"{ff_leak['notional_1m']}/{ff_leak['trade_count_1m']}")

    now_cut = base + 80 * 60_000
    future_bars = bars + [(bars[-1][0] + (i + 1) * 60_000, 500.0, 900.0, 100.0, 800.0) for i in range(30)]
    res_now = evaluate_outcome(100.0, t0, [b for b in bars if b[0] + 60_000 <= now_cut], now_cut)
    res_future = evaluate_outcome(100.0, t0, future_bars, now_cut)
    check('sonuç hesabı now_ms sonrası barları kullanmıyor', res_now == res_future, f"{res_now} vs {res_future}")
    check('olgunlaşmadan sonuç yok (60 dk)', evaluate_outcome(100.0, t0, future_bars, t0 + 59 * 60_000) is None)

    with tempfile.TemporaryDirectory() as tmp2:
        w2 = SnapshotWriter(tmp2)
        good = {k: 1 for k in REQUIRED_SNAPSHOT_FIELDS}
        good['captured_at_ms'] = t0
        w2.add_snapshot(good, {})
        bad = dict(good)
        bad['structure_version'] = None
        w2.add_snapshot(bad, {})
        w2.flush()
        check('zorunlu alan eksikse sayaç artar', w2.invalid_snapshots == 1 and missing_required(bad) == ['structure_version'],
              f"{w2.invalid_snapshots}/{missing_required(bad)}")

    ob_fresh = orderbook_features({'E': asof - 200, 'bids': [['10', '1']], 'asks': [['10.1', '1']]}, asof)
    ob_old = orderbook_features({'E': asof - 30_000, 'bids': [['10', '1']], 'asks': [['10.1', '1']]}, asof)
    ob_none = orderbook_features(None, asof)
    check('orderbook zaman damgası + bayatlık bayrağı',
          ob_fresh['ob_stale'] is False and ob_fresh['ob_timestamp_ms'] == asof - 200 and ob_fresh['ob_age_ms'] == 200
          and ob_old['ob_stale'] is True and ob_none['ob_stale'] is True, f"{ob_fresh['ob_stale']}/{ob_old['ob_stale']}")

    hb = _HourlyBuffer()
    big = 'x' * (MAX_PENDING_BYTES // 3)
    for k in ('h1', 'h2', 'h3', 'h4', 'h5'):
        hb.add(k, big)
    check('yazılamayan tampon sınırlı', hb.size <= MAX_PENDING_BYTES and hb.dropped_bytes > 0 and hb.chunks[-1][0] == 'h5')

    print(f"\n  SONUÇ: {'TÜMÜ GEÇTİ' if not fails else str(len(fails)) + ' HATA: ' + ', '.join(fails)}")
    return not fails


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'selftest'
    if cmd == 'selftest':
        sys.exit(0 if selftest() else 1)
    elif cmd == 'outcomes':
        here = os.path.dirname(os.path.abspath(__file__))
        target = resolve_run_dir(os.path.join(here, 'logs'), sys.argv[2] if len(sys.argv) > 2 else 'latest')
        if not target:
            print("  logs/ altında run_ klasörü bulunamadı.")
            sys.exit(1)
        CLOCK.refresh(force=True)
        print(f"  Değerlendirilen çalışma: {target}")
        offline_evaluate(target)
    else:
        print("Kullanım: python tracker_v2.py [selftest | outcomes [run_klasörü|latest]]")
