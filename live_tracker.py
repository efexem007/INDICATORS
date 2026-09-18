import argparse
import bisect
import concurrent.futures
import math
import os
import sys
import textwrap
import time
from datetime import datetime

import tracker_v2 as tv2

# Windows konsol UTF-8 ayarı
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SYMBOL_MEXC = 'LONGXIA_USDT'
SYMBOL_BYBIT = 'LONGXIAUSDT'

# ═══════════════════════════════════════════════════════════════════════
# MOTOR DAMGALARI (her snapshot'ta zorunlu alan) — bir formül değişirse damga
# değişir ki farklı sürümlerin verisi analizde karışmasın.
# Pine kaynakları ve farklar: LOGGER_V2_ALANLAR.md §9
# ═══════════════════════════════════════════════════════════════════════
STRUCTURE_VERSION = "v1.2"                    # STRUCTURE v1.2 Audited (plan/STRUCTURE_v1.1.pine çekirdeği + v1.2 multi-zone/WARM)
REALF_ENGINE = "REALF_PY_V4_2_DERIVED"        # Pine REALF v4.2'den TÜRETİLMİŞ Python motoru — birebir değil (farklar: LOGGER_V2_ALANLAR.md §9.1)
FATIGUE_VERSION = "ZPTDIFAT_PY_V1_4_DERIVED"  # ZP TDIALT + FATIGUE MTF v1.4 yorgunluk motorundan türetilmiş (farklar: §9.2)

# ═══════════════════════════════════════════════════════════════════════
# 0. COİN KAYIT DEFTERİ & SINIFLANDIRMA
# ═══════════════════════════════════════════════════════════════════════

COIN_REGISTRY = {
    # ─── MEVCUT 6 ───
    'BTCUSDT':      {'provider': 'BINANCE', 'class': 'MEVCUT',      'whale': 100000, 'rank': 1},
    'SOLUSDT':      {'provider': 'BINANCE', 'class': 'MEVCUT',      'whale': 25000,  'rank': 8},
    'SYNUSDT':      {'provider': 'BINANCE', 'class': 'MEVCUT',      'whale': 5000,   'rank': 0},
    'IOSTUSDT':     {'provider': 'BINANCE', 'class': 'MEVCUT',      'whale': 1500,   'rank': 0},
    'SAGAUSDT':     {'provider': 'BINANCE', 'class': 'MEVCUT',      'whale': 3000,   'rank': 0},
    'LONGXIA_USDT': {'provider': 'MEXC',    'class': 'MEVCUT',      'whale': 1000,   'rank': 0},
    # ─── İLK 100 (TEST GRUBU A) ───
    'ETHUSDT':      {'provider': 'BINANCE', 'class': 'TOP100',      'whale': 75000,  'rank': 2},
    'BNBUSDT':      {'provider': 'BINANCE', 'class': 'TOP100',      'whale': 25000,  'rank': 4},
    'XRPUSDT':      {'provider': 'BINANCE', 'class': 'TOP100',      'whale': 25000,  'rank': 5},
    'DOGEUSDT':     {'provider': 'BINANCE', 'class': 'TOP100',      'whale': 15000,  'rank': 12},
    'LINKUSDT':     {'provider': 'BINANCE', 'class': 'TOP100',      'whale': 10000,  'rank': 17},
    'ADAUSDT':      {'provider': 'BINANCE', 'class': 'TOP100',      'whale': 10000,  'rank': 19},
    'LTCUSDT':      {'provider': 'BINANCE', 'class': 'TOP100',      'whale': 10000,  'rank': 25},
    'AVAXUSDT':     {'provider': 'BINANCE', 'class': 'TOP100',      'whale': 5000,   'rank': 31},
    'SUIUSDT':      {'provider': 'BINANCE', 'class': 'TOP100',      'whale': 5000,   'rank': 35},
    'AKEUSDT':      {'provider': 'BINANCE', 'class': 'TOP100',      'whale': 2000,   'rank': 94},
    # ─── İLK 100 DIŞI (TEST GRUBU B) ───
    'PONSUSDT':     {'provider': 'BINANCE', 'class': 'OUTSIDE100',  'whale': 2000,   'rank': 112},
    'SKRUSDT':      {'provider': 'BINANCE', 'class': 'OUTSIDE100',  'whale': 500,    'rank': 227},
    'PROMUSDT':     {'provider': 'BINANCE', 'class': 'OUTSIDE100',  'whale': 1000,   'rank': 266},
    'UAIUSDT':      {'provider': 'BINANCE', 'class': 'OUTSIDE100',  'whale': 2000,   'rank': 296},
    'BULLAUSDT':    {'provider': 'BINANCE', 'class': 'OUTSIDE100',  'whale': 5000,   'rank': 339},
    'OGUSDT':       {'provider': 'BINANCE', 'class': 'OUTSIDE100',  'whale': 500,    'rank': 523},
    'ZORAUSDT':     {'provider': 'BINANCE', 'class': 'OUTSIDE100',  'whale': 500,    'rank': 612},
    'TNSRUSDT':     {'provider': 'BINANCE', 'class': 'OUTSIDE100',  'whale': 200,    'rank': 738},
    'VELVETUSDT':   {'provider': 'BINANCE', 'class': 'OUTSIDE100',  'whale': 200,    'rank': 761},
    'ZKCUSDT':      {'provider': 'BINANCE', 'class': 'OUTSIDE100',  'whale': 200,    'rank': 1142},
}

def get_coin_info(symbol_key):
    return COIN_REGISTRY.get(symbol_key.upper(), {
        'provider': 'BINANCE', 'class': 'UNKNOWN', 'whale': 1000, 'rank': 0
    })

def get_whale_threshold(symbol_key):
    return get_coin_info(symbol_key).get('whale', 1000)

def verify_contracts(coin_list):
    binance_coins = [c for c in coin_list if get_coin_info(c)['provider'] == 'BINANCE']
    if not binance_coins:
        return coin_list

    try:
        data = tv2.http_get_json(f"{tv2.BINANCE_FAPI}/fapi/v1/exchangeInfo", timeout=15)
        active = {s['symbol'] for s in data['symbols'] if s['status'] == 'TRADING'}

        verified = []
        for coin in coin_list:
            info = get_coin_info(coin)
            if info['provider'] == 'MEXC':
                verified.append(coin)
                continue
            clean = coin.upper().replace('_', '')
            if clean in active:
                verified.append(coin)
            else:
                print(f"  ⚠️ {coin} Binance Futures'ta AKTİF DEĞİL — listeden çıkarıldı!")
        return verified
    except Exception as e:
        print(f"  ⚠️ exchangeInfo doğrulaması başarısız ({e}) — tüm coinler kabul edildi.")
        return coin_list

# ═══════════════════════════════════════════════════════════════════════
# 1. GERÇEK ALIM / SATIM & CVD TAKİP MOTORU (Per-Symbol Isolated)
#    Havuz + boşluk takibi tracker_v2.TradePool'da.
# ═══════════════════════════════════════════════════════════════════════

class RealtimeOrderFlowManager:
    """(provider, market, symbol) başına izole işlem havuzu."""

    def __init__(self):
        self._pools = {}

    def get_pool(self, provider: str, market: str, symbol: str) -> tv2.TradePool:
        key = (provider.upper(), market.upper(), symbol.upper())
        if key not in self._pools:
            self._pools[key] = tv2.TradePool(provider, market, symbol)
        return self._pools[key]

    def pools(self):
        return list(self._pools.values())

flow_manager = RealtimeOrderFlowManager()

# ═══════════════════════════════════════════════════════════════════════
# 2. VERİ ÇEKME FONKSİYONLARI (KLINES, TRADES, ORDERBOOK - STRICT ISOLATION)
# ═══════════════════════════════════════════════════════════════════════

MTF_TFS = (('1m', 1, '1m'), ('3m', 3, '3m'), ('5m', 5, '5m'), ('15m', 15, '15m'), ('1h', 60, '1h'), ('4h', 240, '4h'))
KLINE_LIMIT_1M = 500
HTF_KLINE_LIMIT = 499      # Binance ağırlığı: limit [100, 500) → 2

def fetch_candles_mexc(symbol=SYMBOL_MEXC, interval='Min1'):
    d = tv2.http_get_json(f"https://contract.mexc.com/api/v1/contract/kline/{symbol}?interval={interval}")
    if not d.get('success'):
        raise Exception(f"MEXC error: {d}")
    data = d['data']
    return {
        'time': data['time'],
        'open': data['open'],
        'high': data['high'],
        'low': data['low'],
        'close': data['close'],
        'vol': data['vol'],
        'amount': data.get('amount', [v * c for v, c in zip(data['vol'], data['close'])])
    }

def fetch_candles_binance(symbol='SYNUSDT', interval='1m', limit=KLINE_LIMIT_1M):
    raw = tv2.http_get_json(f"{tv2.BINANCE_FAPI}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}")
    return {
        'time': [int(k[0]) // 1000 for k in raw],
        'open': [float(k[1]) for k in raw],
        'high': [float(k[2]) for k in raw],
        'low': [float(k[3]) for k in raw],
        'close': [float(k[4]) for k in raw],
        'vol': [float(k[5]) for k in raw],
        'amount': [float(k[7]) for k in raw],
        'trades': [int(k[8]) for k in raw],
        'taker_buy': [float(k[10]) for k in raw]
    }

def fetch_orderbook_binance(symbol, limit=20):
    return tv2.http_get_json(f"{tv2.BINANCE_FAPI}/fapi/v1/depth?symbol={symbol}&limit={limit}", timeout=5)

def fetch_live_trades(provider: str, market: str, symbol: str, reference_price: float = 0.0, max_pages: int = 5):
    """Havuzu borsayla eşitler (Binance: aggTradeId sürekliliği + fromId geri doldurma)."""
    pool = flow_manager.get_pool(provider, market, symbol)
    if provider.upper() == 'MEXC':
        return tv2.sync_mexc_pool(pool, tv2.CLOCK, reference_price)
    return tv2.sync_binance_pool(pool, tv2.CLOCK, reference_price, max_pages=max_pages)

# ═══════════════════════════════════════════════════════════════════════
# 3. İNDİKATÖR FORMÜLLERİ: ZPTDIFAT (yorgunluk) · REALF (türetilmiş) · STRUCTURE v1.2
# ═══════════════════════════════════════════════════════════════════════

def resample_candles(c1m, tf_min):
    if tf_min == 1:
        return c1m
    tf_sec = tf_min * 60
    n = len(c1m['time'])
    groups = {}
    for i in range(n):
        t = c1m['time'][i]
        bucket = (t // tf_sec) * tf_sec
        if bucket not in groups:
            groups[bucket] = {
                'time': bucket,
                'open': c1m['open'][i],
                'high': c1m['high'][i],
                'low': c1m['low'][i],
                'close': c1m['close'][i],
                'vol': c1m['vol'][i],
                'amount': c1m['amount'][i]
            }
        else:
            g = groups[bucket]
            g['high'] = max(g['high'], c1m['high'][i])
            g['low'] = min(g['low'], c1m['low'][i])
            g['close'] = c1m['close'][i]
            g['vol'] += c1m['vol'][i]
            g['amount'] += c1m['amount'][i]

    sorted_buckets = sorted(groups.keys())
    return {
        'time': [groups[b]['time'] for b in sorted_buckets],
        'open': [groups[b]['open'] for b in sorted_buckets],
        'high': [groups[b]['high'] for b in sorted_buckets],
        'low': [groups[b]['low'] for b in sorted_buckets],
        'close': [groups[b]['close'] for b in sorted_buckets],
        'vol': [groups[b]['vol'] for b in sorted_buckets],
        'amount': [groups[b]['amount'] for b in sorted_buckets],
    }

def calc_rsi(series, period=14):
    n = len(series)
    res = [50.0] * n
    if n <= period:
        return res
    gains = [max(series[i] - series[i-1], 0) for i in range(1, n)]
    losses = [max(series[i-1] - series[i], 0) for i in range(1, n)]
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    for i in range(period, n):
        chg = series[i] - series[i-1]
        g = max(chg, 0)
        l = max(-chg, 0)
        ag = (ag * (period - 1) + g) / period
        al = (al * (period - 1) + l) / period
        res[i] = 100.0 if al == 0 else 100.0 - (100.0 / (1.0 + (ag / al)))
    return res

FATIGUE_RANK_WIN = 300

def calc_fatigue(candles, rank_win=FATIGUE_RANK_WIN):
    closes = candles['close']
    n = len(closes)
    if n < 30:
        return {'fat': 50.0, 'state': 'WARMUP', 'abs': 50.0, 'rank': 50.0, 'bars': n, 'ready': False, 'rank_window': 0}

    rsi14 = calc_rsi(closes, 14)
    srsi_raw = [0.0] * n
    for i in range(14, n):
        win = rsi14[i-13:i+1]
        mn, mx = min(win), max(win)
        srsi_raw[i] = 0.0 if mx == mn else (rsi14[i] - mn) / (mx - mn) * 100.0

    stoch_k = [0.0] * n
    for i in range(16, n):
        stoch_k[i] = sum(srsi_raw[i-2:i+1]) / 3.0

    pb_sc = [50.0] * n
    for i in range(20, n):
        win = closes[i-19:i+1]
        basis = sum(win) / 20.0
        var = sum((x - basis)**2 for x in win) / 20.0
        sd = math.sqrt(var)
        rng = 4.0 * sd
        if rng > 0:
            pb_raw = (closes[i] - (basis - 2.0 * sd)) / rng
            pb_sc[i] = max(-25.0, min(125.0, 100.0 * pb_raw))

    abs_fat = [0.0] * n
    for i in range(20, n):
        r_c = max(0.0, min(100.0, rsi14[i]))
        k_c = max(0.0, min(100.0, stoch_k[i]))
        p_c = pb_sc[i]
        abs_fat[i] = max(0.0, min(100.0, 0.35 * r_c + 0.20 * k_c + 0.45 * p_c))

    actual_win = min(rank_win, n - 20)
    rank_fat = [50.0] * n
    start_r = max(20, n - actual_win)
    # Kayan pencere sıralı listede tutulur (O(n log w)); sonuç tam tarama ile birebir aynıdır.
    lo = max(0, start_r - actual_win + 1)
    window = sorted(abs_fat[lo:start_r])
    for i in range(start_r, n):
        x = abs_fat[i]
        bisect.insort(window, x)
        new_lo = max(0, i - actual_win + 1)
        while lo < new_lo:
            del window[bisect.bisect_left(window, abs_fat[lo])]
            lo += 1
        less = bisect.bisect_left(window, x)
        eq = bisect.bisect_right(window, x) - less
        rank_fat[i] = (less + (eq + 1) / 2.0) / len(window) * 100.0

    fat_val = abs_fat[start_r]
    for i in range(start_r, n):
        ada = 0.70 * abs_fat[i] + 0.30 * rank_fat[i]
        fat_val = 0.30 * ada + 0.70 * fat_val

    if fat_val >= 83.0:
        state = "ASIRI"
    elif fat_val >= 72.0:
        state = "YORGUN"
    elif fat_val >= 30.0:
        state = "NORMAL"
    else:
        state = "DINLENMIS"

    return {
        'fat': round(fat_val, 2),
        'state': state,
        'abs': round(abs_fat[-1], 2),
        'rank': round(rank_fat[-1], 2),
        'bars': n,
        'ready': (n - 20) >= rank_win,     # Pine: 300 barlık rank penceresi dolu
        'rank_window': actual_win
    }

REALF_READY_BARS = 420   # Pine REALF tablosu: "WARMUP x/420"

def calc_realf(candles):
    closes = candles['close']
    highs = candles['high']
    lows = candles['low']
    amounts = candles['amount']
    n = len(closes)

    if n < 30:
        return {
            'score': 50.0, 'state': 'WARMUP', 'whale': 'YOK',
            'impact_score': 50.0, 'memory_score': 50.0, 'momentum_score': 50.0, 'activity_score': 50.0,
            'inventory': 0.0, 'fast_price': 0.0, 'fast_flow': 0.0,
            'beta': 0.0, 'beta_r2': 0.0, 'rvol': 1.0, 'percentile': 50.0, 'persistence': 50.0, 'net_pct': 0.0,
            'ready': False, 'bars': n, 'component_spread': None, 'component_agreement': None,
            'implied_price': None, 'implied_gap_pct': None
        }

    impactK = 2.0
    memoryHalfLife = 30.0

    ret = [0.0] * n
    for i in range(1, n):
        ret[i] = math.log(closes[i] / closes[i-1]) if closes[i-1] > 0 else 0.0

    flow = [0.0] * n
    pressures = [0.0] * n
    signed_notional = [0.0] * n
    for i in range(n):
        rng = highs[i] - lows[i]
        p = max(-1.0, min(1.0, (2.0 * closes[i] - highs[i] - lows[i]) / rng)) if rng > 0 else 0.0
        pressures[i] = p
        signed_notional[i] = p * amounts[i]
        v_win = amounts[max(0, i-19):i+1]
        v_base = sum(v_win) / len(v_win) if v_win else 1.0
        rvol_i = amounts[i] / v_base if v_base > 0 else 1.0
        flow[i] = p * min(math.log(1.0 + rvol_i), 3.0)

    win_len = min(100, n)
    sub_ret = ret[-win_len:]
    sub_flow = flow[-win_len:]
    meanR = sum(sub_ret) / win_len
    meanF = sum(sub_flow) / win_len
    meanRF = sum(ret[i] * flow[i] for i in range(n-win_len, n)) / win_len
    meanF2 = sum(flow[i]**2 for i in range(n-win_len, n)) / win_len
    meanR2 = sum(ret[i]**2 for i in range(n-win_len, n)) / win_len
    varF = max(meanF2 - meanF**2, 0.0)
    varR = max(meanR2 - meanR**2, 0.0)
    cov = meanRF - meanR * meanF
    betaRaw = cov / varF if varF > 1e-12 else 0.0
    fitR2 = (cov**2) / (varF * varR) if varF > 1e-12 and varR > 1e-16 else 0.0
    fitTrust = math.sqrt(fitR2) if betaRaw > 0 else 0.0

    priceScale = max(math.sqrt(meanR2), 1e-5)
    flowScale = max(math.sqrt(meanF2), 0.35)
    fallbackBeta = priceScale / flowScale
    calibration = fitTrust * max(betaRaw, 0.0) + (1.0 - fitTrust) * fallbackBeta
    potentialStep = [calibration * f for f in flow]

    actual5 = sum(ret[-5:])
    potential5 = sum(potentialStep[-5:])
    actual20 = sum(ret[-min(20, n):])
    potential20 = sum(potentialStep[-min(20, n):])
    actual100 = sum(ret[-min(100, n):])
    potential100 = sum(potentialStep[-min(100, n):])

    gap5 = (actual5 - potential5) / (priceScale * math.sqrt(5.0) * impactK)
    gap20 = (actual20 - potential20) / (priceScale * math.sqrt(20.0) * impactK)
    gap100 = (actual100 - potential100) / (priceScale * 10.0 * impactK)
    impactGap = 0.45 * math.tanh(gap5) + 0.35 * math.tanh(gap20) + 0.20 * math.tanh(gap100)
    impactScore = max(0.0, min(100.0, 50.0 + 49.0 * impactGap))

    decay = math.exp(math.log(0.5) / memoryHalfLife)
    inventory = 0.0
    for i in range(max(0, n-150), n):
        inventory = decay * inventory + potentialStep[i] - ret[i]

    net20 = sum(signed_notional[-min(20, n):])
    tot20 = sum(amounts[-min(20, n):])
    net_pct = (100.0 * net20 / tot20) if tot20 > 0 else 0.0
    pos_count = sum(1 for s in signed_notional[-min(20, n):] if s > 0)
    neg_count = sum(1 for s in signed_notional[-min(20, n):] if s < 0)
    persistence = (pos_count / 20.0) if net20 > 0 else ((neg_count / 20.0) if net20 < 0 else 0.0)
    persistFactor = 0.35 + 0.65 * persistence

    memoryGap = -inventory / (priceScale * math.sqrt(1.0 / (1.0 - decay)) * impactK)
    memoryScore = max(0.0, min(100.0, 50.0 + 49.0 * math.tanh(memoryGap) * persistFactor))

    fastPrice = actual5 / (priceScale * math.sqrt(5.0))
    fastFlow = potential5 / (priceScale * math.sqrt(5.0))
    fastGap = (actual5 - potential5) / (priceScale * math.sqrt(5.0) * impactK)
    mediumGap = (actual20 - potential20) / (priceScale * math.sqrt(20.0) * impactK)
    momentumGap = 0.65 * math.tanh(fastGap) + 0.35 * math.tanh(mediumGap)
    momentumScore = max(0.0, min(100.0, 50.0 + 49.0 * momentumGap * persistFactor))

    win_notional = amounts[-min(n, 300):]
    curr_notional = amounts[-1]
    percentile = (sum(1 for a in win_notional if a <= curr_notional) / len(win_notional)) * 100.0
    vol_win = amounts[-min(20, n):]
    v_base = sum(vol_win) / len(vol_win) if vol_win else 1.0
    rvol_val = curr_notional / v_base if v_base > 0 else 1.0
    activityConfidence = math.sqrt(min(max(rvol_val / 2.0, 0.0), 1.0) * min(max(percentile / 100.0, 0.0), 1.0))
    core = (0.45 * impactScore + 0.25 * memoryScore + 0.20 * momentumScore) / 0.90
    activityScore = max(0.0, min(100.0, 50.0 + (core - 50.0) * activityConfidence))

    final_score = 0.45 * impactScore + 0.25 * memoryScore + 0.20 * momentumScore + 0.10 * activityScore
    final_score = max(0.0, min(100.0, final_score))

    if final_score >= 70.0:
        state = "STRONG AHEAD"
    elif final_score >= 58.0:
        state = "PRICE AHEAD"
    elif final_score <= 30.0:
        state = "STRONG LAG"
    elif final_score <= 42.0:
        state = "PRICE LAG"
    else:
        state = "FAIR (DENGE)"

    whale_level = 0
    p90 = sorted(win_notional)[int(len(win_notional) * 0.90)]
    p97 = sorted(win_notional)[int(len(win_notional) * 0.97)]
    if curr_notional >= p97 and rvol_val >= 2.5:
        whale_level = 2
    elif curr_notional >= p90 and rvol_val >= 1.5:
        whale_level = 1

    whale_str = "YOK"
    if whale_level > 0:
        direction = "BUY" if pressures[-1] > 0 else "SELL"
        whale_str = f"WHALE {direction} L{whale_level}"

    # Teşhis (skora girmez): bileşen uyumu Pine "Component agreement" ile aynı formül;
    # flow-ima fiyatı = kapanış × exp(RemainingUnpricedFlow) — tahmin değil, envanterin fiyat karşılığı.
    total_dev = 0.45 * abs(impactScore - 50.0) + 0.25 * abs(memoryScore - 50.0) + 0.20 * abs(momentumScore - 50.0)
    agreement = max(0.0, min(1.0, abs(0.9 * (core - 50.0)) / total_dev)) if total_dev > 1e-6 else 1.0
    comps = (impactScore, memoryScore, momentumScore)
    inv_factor = math.exp(max(-5.0, min(5.0, inventory)))

    return {
        'score': round(final_score, 1),
        'state': state,
        'whale': whale_str,
        'impact_score': round(impactScore, 1),
        'memory_score': round(memoryScore, 1),
        'momentum_score': round(momentumScore, 1),
        'activity_score': round(activityScore, 1),
        'inventory': round(inventory, 5),
        'fast_price': round(fastPrice, 2),
        'fast_flow': round(fastFlow, 2),
        'beta': round(betaRaw, 5),
        'beta_r2': round(fitR2, 3),
        'rvol': round(rvol_val, 2),
        'percentile': round(percentile, 1),
        'persistence': round(persistence * 100.0, 1),
        'net_pct': round(net_pct, 1),
        'ready': n >= REALF_READY_BARS,
        'bars': n,
        'component_spread': round(max(comps) - min(comps), 1),
        'component_agreement': round(agreement, 3),
        'implied_price': closes[-1] * inv_factor,
        'implied_gap_pct': round((inv_factor - 1.0) * 100.0, 3)
    }

STRUCTURE_WARM = 'WARM'

def _structure_warmup(bars, confirmed):
    """v1.2: yeterli teyitli pivot yokken sahte RANGE/50 yerine WARM döner."""
    return {'score': None, 'state': STRUCTURE_WARM, 'event': None, 'ext_seq': 'WARMUP', 'int_seq': 'WARMUP',
            'regime': None, 'conf': None, 'ready': False, 'regime_ready': False, 'bars': bars, 'confirmed_bars': confirmed,
            'event_age': None, 'event_strength': None, 'event_time_ms': None,
            'protected_type': 'NONE', 'protected_level': None, 'protected_distance_atr': None,
            'nearest_eqh': None, 'eqh_distance_atr': None, 'eqh_touches': None,
            'nearest_eql': None, 'eql_distance_atr': None, 'eql_touches': None,
            'eqh_active': 0, 'eql_active': 0, 'liq_ref_high': None, 'liq_ref_low': None,
            'last_liq_event': 'NONE', 'liq_event_age': None, 'liq_event_level': None,
            'sweep_event': False, 'sweep_forming': False, 'atr': None, 'atr_pct': None}

def _eq_zone_touch(zones, price, tol, bar, max_active):
    """v1.2 multi-zone: tolerans içindeki aktif bölge yeni teyitli temas alır (sweep kilidi sıfırlanır),
    yoksa yeni bölge açılır; sınır dolduğunda en eski aktif bölge düşer. Bölge fiyatı = iki eşit pivotun ortalaması."""
    for z in zones:
        if abs(z['price'] - price) <= tol:
            z['price'] = price
            z['bar'] = bar
            z['touches'] += 1
            z['swept'] = False
            return
    if len(zones) >= max_active:
        zones.pop(0)
    zones.append({'price': price, 'bar': bar, 'touches': 2, 'swept': False})

def calc_structure(candles, is_bar_closed=False, intLen=2, extLen=4, atrLen=14, intPromMin=0.35, extPromMin=0.80,
                   eqTolAtr=0.12, breakBufferAtr=0.10, eventMemoryBars=40, adxLen=14, adxSmooth=14, trendAdx=22.0,
                   bbLen=20, bbMult=2.0, regLookback=200, squeezePct=20.0, expandAtrPct=70.0, expandBbwPct=60.0,
                   chaosAtrPct=90.0, expandEventBars=10, maxZonesPerSide=3):
    """STRUCTURE v1.2 Audited — Pine kaynağı: plan/STRUCTURE_v1.1.pine (çekirdek) + v1.2 denetim raporu
    (çok bölgeli EQH/EQL, bölge başına sweep kilidi, hazır değilken WARM).

    Pine `barstate.isconfirmed` karşılığı: pivot, state machine, kırılım, bölge ve sweep işlemleri YALNIZ
    kapanmış barlarda çalışır; canlı (açık) bar yalnız skor yaşlanmasında ve mesafe ölçümünde kullanılır.
    """
    closes = candles.get('close') or []
    n = len(closes)
    confirmed_n = n if is_bar_closed else n - 1          # işlenecek kapanmış bar sayısı
    if 'open' not in candles or confirmed_n < max(atrLen, extLen * 2) + 10:
        return _structure_warmup(n, max(0, confirmed_n))

    opens = candles['open']
    highs = candles['high']
    lows = candles['low']
    times = candles.get('time')
    last_conf = confirmed_n - 1
    cur = n - 1

    def clamp(x, lo, hi):
        return max(lo, min(hi, x))

    # ── ATR (Pine ta.atr = RMA(TR), ilk değer SMA ile tohumlanır) ──
    tr = [0.0] * n
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
    atr = [0.0] * n
    atr[0] = tr[0]
    for i in range(1, atrLen):
        atr[i] = sum(tr[:i+1]) / (i+1)
    for i in range(atrLen, n):
        atr[i] = (atr[i-1] * (atrLen - 1) + tr[i]) / atrLen

    atrp = [0.0] * n
    for i in range(n):
        atrp[i] = (atr[i] / closes[i] * 100.0) if closes[i] != 0 else 0.0

    def pct_rank_at(series, idx):
        """Pine ta.percentrank: son `regLookback` ÖNCEKİ değerin kaçı <= şimdiki. Yetersiz geçmişte None (na)."""
        if idx < regLookback:
            return None
        win = series[idx - regLookback:idx]
        curr = series[idx]
        return sum(1 for x in win if x <= curr) / regLookback * 100.0

    # Bollinger genişliği yalnız rejim için gerekli aralıkta hesaplanır (sonuç tam diziyle aynıdır).
    bbw = [0.0] * n
    for i in range(max(bbLen - 1, last_conf - regLookback), last_conf + 1):
        win = closes[i - bbLen + 1:i + 1]
        basis = sum(win) / bbLen
        dev = math.sqrt(sum((x - basis) ** 2 for x in win) / bbLen)
        bbw[i] = ((basis + bbMult * dev) - (basis - bbMult * dev)) / basis * 100.0 if basis != 0 else 0.0

    # ── DMI / ADX (Wilder) ──
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    for i in range(1, n):
        up_move = highs[i] - highs[i-1]
        down_move = lows[i-1] - lows[i]
        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move
    s_tr = [0.0] * n
    s_pdm = [0.0] * n
    s_mdm = [0.0] * n
    s_tr[adxLen-1] = sum(tr[:adxLen])
    s_pdm[adxLen-1] = sum(plus_dm[:adxLen])
    s_mdm[adxLen-1] = sum(minus_dm[:adxLen])
    for i in range(adxLen, n):
        s_tr[i] = s_tr[i-1] - (s_tr[i-1] / adxLen) + tr[i]
        s_pdm[i] = s_pdm[i-1] - (s_pdm[i-1] / adxLen) + plus_dm[i]
        s_mdm[i] = s_mdm[i-1] - (s_mdm[i-1] / adxLen) + minus_dm[i]
    dx = [0.0] * n
    for i in range(adxLen-1, n):
        di_plus = 100.0 * s_pdm[i] / s_tr[i] if s_tr[i] > 0 else 0.0
        di_minus = 100.0 * s_mdm[i] / s_tr[i] if s_tr[i] > 0 else 0.0
        di_sum = di_plus + di_minus
        dx[i] = 100.0 * abs(di_plus - di_minus) / di_sum if di_sum > 0 else 0.0
    adx = [0.0] * n
    if n > adxLen + adxSmooth - 1:
        seed_end = adxLen - 1 + adxSmooth
        adx[seed_end - 1] = sum(dx[adxLen-1:seed_end]) / adxSmooth
        for i in range(seed_end, n):
            adx[i] = (adx[i-1] * (adxSmooth - 1) + dx[i]) / adxSmooth

    def get_ph(idx, L, R):
        if idx - L < 0 or idx + R >= n:
            return False
        val = highs[idx]
        for i in range(idx - L, idx + R + 1):
            if i == idx:
                continue
            if highs[i] > val:
                return False
            if highs[i] == val and i > idx:
                return False
        return True

    def get_pl(idx, L, R):
        if idx - L < 0 or idx + R >= n:
            return False
        val = lows[idx]
        for i in range(idx - L, idx + R + 1):
            if i == idx:
                continue
            if lows[i] < val:
                return False
            if lows[i] == val and i > idx:
                return False
        return True

    extHigh0 = extHigh1 = extHighBar0 = extHighBar1 = None
    extLow0 = extLow1 = extLowBar0 = extLowBar1 = None
    extHighRel = extLowRel = 0
    extHighCount = extLowCount = 0
    extHighProm = extLowProm = None
    intHigh0 = intHigh1 = intHighBar0 = intHighBar1 = None
    intLow0 = intLow1 = intLowBar0 = intLowBar1 = None
    intHighRel = intLowRel = 0

    persistence = 0.0
    structureState = 0
    lastEventType = lastEventDir = 0
    lastEventBar = None
    lastEventStrength = None
    brokenUpRefBar = brokenDownRefBar = None
    protectedLowPrice = protectedLowBar = None
    protectedHighPrice = protectedHighBar = None

    eqhZones, eqlZones = [], []
    lastHighSweepRef = lastLowSweepRef = None
    liqEvent, liqBar, liqLevel = 'NONE', None, None

    for i in range(max(extLen, atrLen), confirmed_n):          # yalnız KAPANMIŞ barlar
        pb = i - extLen
        pb_int = i - intLen
        atrP = atr[pb]
        atrP_int = atr[pb_int]

        # ── Internal pivots (skora girmez; iç dizilim teşhisi) ──
        if get_ph(pb_int, intLen, intLen):
            phInt = highs[pb_int]
            opp = intLow0 if (intLow0 is not None and intLowBar0 is not None and intLowBar0 < pb_int) else (
                intLow1 if (intLow1 is not None and intLowBar1 is not None and intLowBar1 < pb_int) else None)
            prom = abs(phInt - opp) / atrP_int if (opp is not None and atrP_int > 0) else 999.0
            if prom >= intPromMin:
                intHigh1, intHighBar1 = intHigh0, intHighBar0
                intHigh0, intHighBar0 = phInt, pb_int
                tol = atrP_int * eqTolAtr
                intHighRel = 0 if intHigh1 is None else (1 if phInt > intHigh1 + tol else (-1 if phInt < intHigh1 - tol else 0))
        if get_pl(pb_int, intLen, intLen):
            plInt = lows[pb_int]
            opp = intHigh0 if (intHigh0 is not None and intHighBar0 is not None and intHighBar0 < pb_int) else (
                intHigh1 if (intHigh1 is not None and intHighBar1 is not None and intHighBar1 < pb_int) else None)
            prom = abs(plInt - opp) / atrP_int if (opp is not None and atrP_int > 0) else 999.0
            if prom >= intPromMin:
                intLow1, intLowBar1 = intLow0, intLowBar0
                intLow0, intLowBar0 = plInt, pb_int
                tol = atrP_int * eqTolAtr
                intLowRel = 0 if intLow1 is None else (1 if plInt > intLow1 + tol else (-1 if plInt < intLow1 - tol else 0))

        # ── External pivots (yapı motoru) ──
        if get_ph(pb, extLen, extLen):
            phExt = highs[pb]
            opp = extLow0 if (extLow0 is not None and extLowBar0 is not None and extLowBar0 < pb) else (
                extLow1 if (extLow1 is not None and extLowBar1 is not None and extLowBar1 < pb) else None)
            prom = abs(phExt - opp) / atrP if (opp is not None and atrP > 0) else None
            bootstrap = (extHighCount == 0 or opp is None)
            if bootstrap or (prom is not None and prom >= extPromMin):
                oldHigh = extHigh0
                extHigh1, extHighBar1 = extHigh0, extHighBar0
                extHigh0, extHighBar0 = phExt, pb
                extHighProm = prom
                extHighCount += 1
                tol = atrP * eqTolAtr
                moveDir = 0 if oldHigh is None else (1 if phExt > oldHigh + tol else (-1 if phExt < oldHigh - tol else 0))
                extHighRel = moveDir
                persistence = clamp(persistence * 0.70 + moveDir * 0.30, -1.0, 1.0)
                if extHigh1 is not None and abs(extHigh0 - extHigh1) <= tol:
                    _eq_zone_touch(eqhZones, (extHigh0 + extHigh1) / 2.0, tol, pb, maxZonesPerSide)

        if get_pl(pb, extLen, extLen):
            plExt = lows[pb]
            opp = extHigh0 if (extHigh0 is not None and extHighBar0 is not None and extHighBar0 < pb) else (
                extHigh1 if (extHigh1 is not None and extHighBar1 is not None and extHighBar1 < pb) else None)
            prom = abs(plExt - opp) / atrP if (opp is not None and atrP > 0) else None
            bootstrap = (extLowCount == 0 or opp is None)
            if bootstrap or (prom is not None and prom >= extPromMin):
                oldLow = extLow0
                extLow1, extLowBar1 = extLow0, extLowBar0
                extLow0, extLowBar0 = plExt, pb
                extLowProm = prom
                extLowCount += 1
                tol = atrP * eqTolAtr
                moveDir = 0 if oldLow is None else (1 if plExt > oldLow + tol else (-1 if plExt < oldLow - tol else 0))
                extLowRel = moveDir
                persistence = clamp(persistence * 0.70 + moveDir * 0.30, -1.0, 1.0)
                if extLow1 is not None and abs(extLow0 - extLow1) <= tol:
                    _eq_zone_touch(eqlZones, (extLow0 + extLow1) / 2.0, tol, pb, maxZonesPerSide)

        # ── Dizilim + ilk state tohumu ──
        extReady = None not in (extHigh0, extHigh1, extLow0, extLow1)
        seqBull = extReady and extHighRel == 1 and extLowRel == 1
        seqBear = extReady and extHighRel == -1 and extLowRel == -1
        partialBull = not seqBull and not seqBear and (extHighRel == 1 or extLowRel == 1)
        partialBear = not seqBull and not seqBear and (extHighRel == -1 or extLowRel == -1)
        if extReady and structureState == 0:
            if seqBull:
                structureState = 2
                protectedLowPrice, protectedLowBar = extLow0, extLowBar0
            elif seqBear:
                structureState = -2
                protectedHighPrice, protectedHighBar = extHigh0, extHighBar0
            else:
                structureState = 1 if partialBull else (-1 if partialBear else 0)

        # ── BOS / CHOCH (teyitli kapanışla) ──
        upBreakLevel = protectedHighPrice if (structureState == -2 and protectedHighPrice is not None) else extHigh0
        upBreakRefBar = protectedHighBar if (structureState == -2 and protectedHighBar is not None) else extHighBar0
        downBreakLevel = protectedLowPrice if (structureState == 2 and protectedLowPrice is not None) else extLow0
        downBreakRefBar = protectedLowBar if (structureState == 2 and protectedLowBar is not None) else extLowBar0
        buf = atr[i] * breakBufferAtr

        def break_strength(level, direction):
            rng = max(highs[i] - lows[i], 1e-10)
            bodyQ = abs(closes[i] - opens[i]) / rng
            closeLoc = (closes[i] - lows[i]) / rng if direction > 0 else (highs[i] - closes[i]) / rng
            disp = abs(closes[i] - level) / atr[i] if atr[i] > 0 else 0.0
            return clamp(100.0 * (0.45 * clamp(disp / 1.50, 0.0, 1.0) + 0.30 * bodyQ + 0.25 * closeLoc), 0.0, 100.0)

        if (upBreakLevel is not None and closes[i] > upBreakLevel + buf and closes[i-1] <= upBreakLevel + buf
                and (brokenUpRefBar is None or brokenUpRefBar != upBreakRefBar)):
            bs = break_strength(upBreakLevel, 1)
            if structureState == -2:
                structureState, lastEventType = 1, 2
                protectedLowPrice, protectedLowBar = extLow0, extLowBar0
            else:
                structureState, lastEventType = 2, 1
                protectedLowPrice, protectedLowBar = extLow0, extLowBar0
                protectedHighPrice = protectedHighBar = None
            lastEventDir, lastEventBar, lastEventStrength = 1, i, bs
            brokenUpRefBar = upBreakRefBar

        if (downBreakLevel is not None and closes[i] < downBreakLevel - buf and closes[i-1] >= downBreakLevel - buf
                and (brokenDownRefBar is None or brokenDownRefBar != downBreakRefBar)):
            bs = break_strength(downBreakLevel, -1)
            if structureState == 2:
                structureState, lastEventType = -1, 2
                protectedHighPrice, protectedHighBar = extHigh0, extHighBar0
            else:
                structureState, lastEventType = -2, 1
                protectedHighPrice, protectedHighBar = extHigh0, extHighBar0
                protectedLowPrice = protectedLowBar = None
            lastEventDir, lastEventBar, lastEventStrength = -1, i, bs
            brokenDownRefBar = downBreakRefBar

        # ── Likidite: bölge başına sweep kilidi, aktif bölge yoksa swing yedeği ──
        if eqhZones:
            for z in eqhZones:
                if not z['swept'] and highs[i] > z['price'] + buf and closes[i] < z['price']:
                    z['swept'] = True
                    liqEvent, liqBar, liqLevel = 'EQH_SWEEP', i, z['price']
            eqhZones[:] = [z for z in eqhZones if not closes[i] > z['price'] + buf]      # teyitli kabul → tüketildi
        elif extHigh0 is not None and highs[i] > extHigh0 + buf and closes[i] < extHigh0 and lastHighSweepRef != extHighBar0:
            lastHighSweepRef = extHighBar0
            liqEvent, liqBar, liqLevel = 'HIGH_SWEEP', i, extHigh0

        if eqlZones:
            for z in eqlZones:
                if not z['swept'] and lows[i] < z['price'] - buf and closes[i] > z['price']:
                    z['swept'] = True
                    liqEvent, liqBar, liqLevel = 'EQL_SWEEP', i, z['price']
            eqlZones[:] = [z for z in eqlZones if not closes[i] < z['price'] - buf]
        elif extLow0 is not None and lows[i] < extLow0 - buf and closes[i] > extLow0 and lastLowSweepRef != extLowBar0:
            lastLowSweepRef = extLowBar0
            liqEvent, liqBar, liqLevel = 'LOW_SWEEP', i, extLow0

    # ── Son durum (canlı bar yalnız yaşlanma ve mesafede kullanılır) ──
    extReady = None not in (extHigh0, extHigh1, extLow0, extLow1)
    intReady = None not in (intHigh0, intHigh1, intLow0, intLow1)
    seqBull = extReady and extHighRel == 1 and extLowRel == 1
    seqBear = extReady and extHighRel == -1 and extLowRel == -1
    partialBull = extReady and not seqBull and not seqBear and (extHighRel == 1 or extLowRel == 1)
    partialBear = extReady and not seqBull and not seqBear and (extHighRel == -1 or extLowRel == -1)

    def seq_text(hi_rel, lo_rel):
        if hi_rel == 1 and lo_rel == 1:
            return 'HH/HL'
        if hi_rel == -1 and lo_rel == -1:
            return 'LH/LL'
        if hi_rel == 1:
            return 'HH/MIX'
        if lo_rel == 1:
            return 'MIX/HL'
        if hi_rel == -1:
            return 'LH/MIX'
        if lo_rel == -1:
            return 'MIX/LL'
        return 'EQ/RANGE'

    currC = closes[cur]
    currAtr = atr[last_conf]
    atr_pct = round(atrp[last_conf], 4)

    if not extReady:                                    # v1.2: sahte RANGE/50 yok
        res = _structure_warmup(n, confirmed_n)
        res.update({'int_seq': seq_text(intHighRel, intLowRel) if intReady else 'WARMUP',
                    'regime_ready': last_conf >= regLookback, 'atr': currAtr, 'atr_pct': atr_pct})
        return res

    eventAge = (cur - lastEventBar) if lastEventBar is not None else 99999
    swingComp = 20.0 if seqBull else (-20.0 if seqBear else (8.0 if partialBull else (-8.0 if partialBear else 0.0)))
    eventDecay = clamp(1.0 - eventAge / eventMemoryBars, 0.0, 1.0) if lastEventBar is not None else 0.0
    eventBase = 15.0 if lastEventType == 1 else (10.0 if lastEventType == 2 else 0.0)
    breakQualityNorm = clamp((lastEventStrength - 30.0) / 70.0, 0.0, 1.0) if lastEventStrength is not None else 0.0
    structureScore = clamp(50.0 + swingComp + lastEventDir * eventBase * eventDecay
                           + lastEventDir * 10.0 * breakQualityNorm * eventDecay + persistence * 5.0, 0.0, 100.0)

    def confidence_at(age):
        pivotConf = 25.0 if extReady else (14.0 if (extHighCount >= 2 or extLowCount >= 2) else 5.0)
        promHigh = extHighProm if extHighProm is not None else extPromMin
        promLow = extLowProm if extLowProm is not None else extPromMin
        promAvg = (promHigh + promLow) / 2.0
        promConf = 25.0 * clamp(promAvg / max(extPromMin * 2.5, 0.01), 0.0, 1.0)
        seqConf = 25.0 if (seqBull or seqBear) else (16.0 if (partialBull or partialBear) else (10.0 if extReady else 5.0))
        dyn = 15.0 * abs(persistence) + (10.0 * (lastEventStrength / 100.0)
                                         if (lastEventStrength is not None and age <= eventMemoryBars) else 0.0)
        return clamp(pivotConf + promConf + seqConf + dyn, 0.0, 100.0)

    confidence = confidence_at(eventAge)

    # ── Rejim: Pine'da yalnız teyitli barda güncellenir ──
    age_conf = (last_conf - lastEventBar) if lastEventBar is not None else 99999
    atrRank = pct_rank_at(atrp, last_conf)
    bbwRank = pct_rank_at(bbw, last_conf)
    adxNow = adx[last_conf]
    conf_conf = confidence_at(age_conf)
    squeeze = atrRank is not None and bbwRank is not None and atrRank <= squeezePct and bbwRank <= squeezePct
    recentBull = lastEventType == 1 and lastEventDir == 1 and age_conf <= expandEventBars
    recentBear = lastEventType == 1 and lastEventDir == -1 and age_conf <= expandEventBars
    expansionUp = atrRank is not None and bbwRank is not None and atrRank >= expandAtrPct and bbwRank >= expandBbwPct and recentBull
    expansionDown = atrRank is not None and bbwRank is not None and atrRank >= expandAtrPct and bbwRank >= expandBbwPct and recentBear
    chaotic = atrRank is not None and atrRank >= chaosAtrPct and conf_conf < 45.0
    if squeeze:
        regime = 'SQZ'
    elif expansionUp:
        regime = 'EXP UP'
    elif expansionDown:
        regime = 'EXP DN'
    elif chaotic:
        regime = 'CHAOS'
    elif structureState == 1:
        regime = 'TR-UP'
    elif structureState == -1:
        regime = 'TR-DN'
    elif structureState == 2 and adxNow >= trendAdx:
        regime = 'TR UP'
    elif structureState == -2 and adxNow >= trendAdx:
        regime = 'TR DN'
    else:
        regime = 'RANGE'

    state_short = {2: 'BULL', 1: 'TR-UP', 0: 'RANGE', -1: 'TR-DN', -2: 'BEAR'}[structureState]
    event_name = ('BOS UP' if (lastEventType == 1 and lastEventDir == 1) else
                  'BOS DN' if (lastEventType == 1 and lastEventDir == -1) else
                  'CHOCH UP' if (lastEventType == 2 and lastEventDir == 1) else
                  'CHOCH DN' if (lastEventType == 2 and lastEventDir == -1) else 'NONE')

    if structureState in (1, 2) and protectedLowPrice is not None:
        protType, protLvl = 'LOW', protectedLowPrice
        protDist = (currC - protLvl) / currAtr if currAtr > 0 else None
    elif structureState in (-1, -2) and protectedHighPrice is not None:
        protType, protLvl = 'HIGH', protectedHighPrice
        protDist = (protLvl - currC) / currAtr if currAtr > 0 else None
    else:
        protType, protLvl, protDist = 'NONE', None, None

    above = [z for z in eqhZones if z['price'] >= currC]
    below = [z for z in eqlZones if z['price'] <= currC]
    zEqh = min(above, key=lambda z: z['price']) if above else None
    zEql = max(below, key=lambda z: z['price']) if below else None
    liqRefHigh = min((z['price'] for z in eqhZones), default=None) if eqhZones else extHigh0
    liqRefLow = max((z['price'] for z in eqlZones), default=None) if eqlZones else extLow0

    # Canlı barda oluşmakta olan (henüz teyitsiz) süpürme — yalnız bilgi, karar verisi değil
    sweep_forming = False
    if not is_bar_closed and n > 1:
        bufLive = atr[last_conf] * breakBufferAtr
        if liqRefHigh is not None and highs[cur] > liqRefHigh + bufLive and closes[cur] < liqRefHigh:
            sweep_forming = True
        if liqRefLow is not None and lows[cur] < liqRefLow - bufLive and closes[cur] > liqRefLow:
            sweep_forming = True

    def rnd(v, nd):
        return round(v, nd) if v is not None else None

    return {
        'score': round(structureScore, 1),
        'state': state_short,
        'event': event_name,
        'ext_seq': seq_text(extHighRel, extLowRel),
        'int_seq': seq_text(intHighRel, intLowRel) if intReady else 'WARMUP',
        'regime': regime,
        'conf': round(confidence, 1),
        'ready': True,
        'regime_ready': last_conf >= regLookback,
        'bars': n,
        'confirmed_bars': confirmed_n,
        'event_age': eventAge if lastEventBar is not None else None,
        'event_strength': rnd(lastEventStrength, 1),
        'event_time_ms': (times[lastEventBar] * 1000) if (times and lastEventBar is not None) else None,
        'protected_type': protType,
        'protected_level': protLvl,
        'protected_distance_atr': rnd(protDist, 2),
        'nearest_eqh': zEqh['price'] if zEqh else None,
        'eqh_distance_atr': rnd((zEqh['price'] - currC) / currAtr, 2) if (zEqh and currAtr > 0) else None,
        'eqh_touches': zEqh['touches'] if zEqh else None,
        'nearest_eql': zEql['price'] if zEql else None,
        'eql_distance_atr': rnd((currC - zEql['price']) / currAtr, 2) if (zEql and currAtr > 0) else None,
        'eql_touches': zEql['touches'] if zEql else None,
        'eqh_active': len(eqhZones),
        'eql_active': len(eqlZones),
        'liq_ref_high': liqRefHigh,
        'liq_ref_low': liqRefLow,
        'last_liq_event': liqEvent,
        'liq_event_age': (cur - liqBar) if liqBar is not None else None,
        'liq_event_level': liqLevel,
        'sweep_event': liqBar == last_conf,
        'sweep_forming': sweep_forming,
        'atr': currAtr,
        'atr_pct': atr_pct
    }

def get_recent_minute_history(candles, limit=6):
    closes = candles['close']
    opens = candles['open']
    highs = candles['high']
    lows = candles['low']
    amounts = candles['amount']
    times = candles['time']
    taker_buys = candles.get('taker_buy', None)
    trades = candles.get('trades', None)
    n = len(closes)

    rows = []
    start_idx = max(25, n - limit)
    for i in range(start_idx, n):
        t_str = datetime.fromtimestamp(times[i]).strftime('%H:%M')
        c = closes[i]
        chg = ((c - closes[i-1]) / closes[i-1] * 100.0) if i > 0 else 0.0
        tot = amounts[i]
        if taker_buys is not None:
            tb = taker_buys[i]
            ts = tot - tb
            cvd = tb - ts
        else:
            rng = highs[i] - lows[i]
            p = ((2.0 * c - highs[i] - lows[i]) / rng) if rng > 0 else 0.0
            cvd = p * tot
            tb = (tot + cvd) / 2.0
            ts = tot - tb
        cvd_pct = (cvd / tot * 100.0) if tot > 0 else 0.0

        sub_c = {'close': closes[:i+1]}
        sub_all = {
            'close': closes[:i+1], 'open': opens[:i+1],
            'high': highs[:i+1], 'low': lows[:i+1],
            'amount': amounts[:i+1], 'vol': candles['vol'][:i+1]
        }
        f_info = calc_fatigue(sub_c)
        r_info = calc_realf(sub_all)

        rows.append({
            'time': t_str, 'open_ms': times[i] * 1000, 'close': c, 'chg': chg,
            'tot': tot, 'tb': tb, 'ts': ts, 'cvd': cvd, 'cvd_pct': cvd_pct,
            'trades': trades[i] if trades is not None else None,
            'fat': f_info['fat'], 'fat_st': f_info['state'],
            'realf': r_info['score'], 'inventory': r_info['inventory']
        })
    return rows

def kline_quality(candles, window=300):
    """REALF veri kaynağı kalitesi: bar sayısı, zaman boşluğu, sıfır hacimli bar payı."""
    times = candles['time'][-window:]
    amounts = candles['amount'][-window:]
    gaps = sum(1 for i in range(1, len(times)) if times[i] - times[i-1] != 60)
    zero_share = (sum(1 for a in amounts if a <= 0) / len(amounts)) if amounts else 1.0
    bars_factor = min(1.0, len(candles['close']) / REALF_READY_BARS)
    gap_factor = max(0.0, 1.0 - gaps / max(1, len(times) - 1))
    return {
        'kline_gaps_300': gaps,
        'zero_volume_share_300': round(zero_share, 4),
        'realf_source_quality': round(100.0 * bars_factor * gap_factor * (1.0 - zero_share), 1)
    }

# ═══════════════════════════════════════════════════════════════════════
# 4. SNAPSHOT KAYDI (JSONL / CSV) — alan sözlüğü: LOGGER_V2_ALANLAR.md
# ═══════════════════════════════════════════════════════════════════════

class TrackerSession:
    def __init__(self, settings, run=None, writer=None, outcomes=None):
        self.settings = settings
        self.run = run
        self.writer = writer
        self.outcomes = outcomes
        self.seq = 0
        self.last_capture_ms = {}
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)
        self.cycle_errors = 0
        self.snapshots = 0

def _alerts(chg_1m, flow, realf, mtf_fat):
    """Alarm kuralları. KISMİ (eksik kapsamalı) akış penceresi ve BAYAT orderbook karar verisi DEĞİLDİR:
    akış alarmları yalnız `1m_complete` iken çalışır, orderbook hiçbir alarma girmez.
    Dönüş: (metin listesi, kod listesi, uyumsuzluk metni, atlanan alarm nedenleri)."""
    alerts, codes, skipped = [], [], []
    flow_ok = bool(flow.get('1m_complete'))
    if not flow_ok:
        skipped.append('flow_1m_incomplete')
    cvd_pct_1m = (flow['cvd_1m_pct'] if flow['cvd_1m_pct'] is not None else 0.0) if flow_ok else 0.0
    div_text = None
    if chg_1m < -0.3 and cvd_pct_1m > 5.0:
        div_text = "🔥 BOĞA UYUMSUZLUĞU (Bullish CVD Divergence): Fiyat düşüyor ama akıllı para ALIYOR!"
        codes.append('BULL_CVD_DIVERGENCE')
    elif chg_1m > 0.3 and cvd_pct_1m < -5.0:
        div_text = "🔥 AYI UYUMSUZLUĞU (Bearish CVD Divergence): Fiyat yükseliyor ama akıllı para SATIYOR!"
        codes.append('BEAR_CVD_DIVERGENCE')
    if div_text:
        alerts.append(div_text)
    if mtf_fat['1m']['state'] == 'ASIRI' or mtf_fat['5m']['state'] == 'ASIRI' or mtf_fat['15m']['state'] == 'ASIRI':
        alerts.append("🚨 [AŞIRI YORGUNLUK]: Üst periyotlarda FAT > 83 tepe/tükeniş alarmı!")
        codes.append('FATIGUE_EXTREME')
    if mtf_fat['1m']['state'] == 'DINLENMIS':
        alerts.append("💡 [1m DİNLENMİŞ]: 1 dakikalık yorgunluk tamamen sıfırlandı.")
        codes.append('FATIGUE_RESTED_1M')
    if realf['score'] < 30.0:
        alerts.append("🔵 [PRICE LAG]: Fiyat akışın çok gerisinde (Akümülasyon / Patlama potansiyeli)!")
        codes.append('REALF_PRICE_LAG')
    elif realf['score'] > 70.0:
        alerts.append("🔴 [PRICE AHEAD]: Fiyat hacmin çok önüne geçti (Düzeltme riski)!")
        codes.append('REALF_PRICE_AHEAD')
    br = flow['buyer_ratio_1m'] if flow_ok else None
    if br is not None and br >= 70.0 and flow['notional_1m'] > 2000.0:
        alerts.append("🟢 [AGRESİF ALICI]: 1 dakikalık işlemlerde %70+ ezici Taker Alıcı baskısı!")
        codes.append('AGGRESSIVE_BUYER')
    elif br is not None and br <= 30.0 and flow['notional_1m'] > 2000.0:
        alerts.append("🔴 [AGRESİF SATICI]: 1 dakikalık işlemlerde %70+ ezici Taker Satıcı baskısı!")
        codes.append('AGGRESSIVE_SELLER')
    return alerts, codes, div_text, skipped

def build_snapshot(session, ctx):
    """Tek düz kayıt (CSV sütunları) + seriler (yalnız JSONL)."""
    s = {}
    run = session.run
    captured = ctx['captured_at_ms']
    # ── ZORUNLU kimlik alanları (tv2.REQUIRED_SNAPSHOT_FIELDS) ──
    s['dataset_schema'] = tv2.DATASET_SCHEMA
    s['tracker_version'] = tv2.TRACKER_VERSION
    s['structure_version'] = STRUCTURE_VERSION
    s['realf_engine'] = REALF_ENGINE
    s['fatigue_version'] = FATIGUE_VERSION
    s['flow_confidence_version'] = tv2.FLOW_CONFIDENCE_VERSION
    s['mtf_source'] = session.settings['mtf']
    s['git_commit'] = run.git_commit if run else None
    s['code_fingerprint'] = run.code_fingerprint if run else tv2.code_fingerprint(
        [os.path.join(SCRIPT_DIR, 'live_tracker.py'), os.path.join(SCRIPT_DIR, 'tracker_v2.py')])
    s['run_id'] = run.run_id if run else 'no-files'
    s['seq'] = ctx['seq']
    s['snapshot_id'] = ctx['snapshot_id']
    s['symbol'] = ctx['symbol']
    s['provider'] = ctx['provider']
    s['market'] = ctx['market']
    info = get_coin_info(ctx['symbol'])
    s['coin_class'] = info['class']
    s['coin_rank'] = info['rank']
    s['whale_threshold_usd'] = info.get('whale', 1000)

    s['captured_at_ms'] = captured
    s['captured_at_local'] = datetime.fromtimestamp(captured / 1000.0).astimezone().isoformat(timespec='milliseconds')
    s['clock_offset_ms'] = tv2.CLOCK.offset_ms
    s['clock_synced'] = tv2.CLOCK.ok
    s['kline_asof_ms'] = ctx['kline_asof_ms']
    s['flow_asof_ms'] = ctx['pool'].known_until_ms
    prev = session.last_capture_ms.get(ctx['symbol'])
    s['prev_snapshot_age_sec'] = round((captured - prev) / 1000.0, 1) if prev else None

    candles = ctx['candles']
    bar_open = candles['time'][-1] * 1000
    s['bar_open_time'] = bar_open
    s['bar_close_time'] = bar_open + 60_000 - 1
    s['is_bar_closed'] = ctx['kline_asof_ms'] >= bar_open + 60_000
    s['bar_progress_sec'] = round((ctx['kline_asof_ms'] - bar_open) / 1000.0, 1)
    s['price'] = ctx['price']
    s['chg_1m_pct'] = round(ctx['chg_1m'], 4)

    realf = ctx['realf']
    s['realf_score'] = realf['score']
    s['realf_state'] = realf['state']
    s['realf_ready'] = realf['ready']
    s['realf_bars'] = realf['bars']
    for k in ('impact_score', 'memory_score', 'momentum_score', 'activity_score'):
        s[f"realf_{k.replace('_score', '')}"] = realf[k]
    s['realf_unpriced_flow'] = realf['inventory']
    for k in ('fast_price', 'fast_flow', 'beta', 'beta_r2', 'rvol', 'percentile', 'persistence', 'net_pct', 'whale',
              'component_spread', 'component_agreement', 'implied_price', 'implied_gap_pct'):
        s[f'realf_{k}'] = realf[k]
    s['realf_source'] = 'CLV_PROXY_1M' if ctx['provider'] == 'BINANCE' else 'CLV_PROXY_1M_MEXC'
    s.update(ctx['kline_quality'])

    s.update(ctx['indicator_deltas'])
    s['absolute_fatigue'] = ctx['mtf_fat']['1m']['abs']
    s['relative_rank'] = ctx['mtf_fat']['1m']['rank']

    for label, _m, _i in MTF_TFS:
        f = ctx['mtf_fat'][label]
        st = ctx['mtf_str'][label]
        meta = ctx['tf_meta'][label]
        s[f'tf_{label}_bars'] = meta['bars']
        s[f'tf_{label}_source'] = meta['source']
        s[f'fat_{label}'] = f['fat']
        s[f'fat_{label}_state'] = f['state']
        s[f'fat_{label}_abs'] = f['abs']
        s[f'fat_{label}_rank'] = f['rank']
        s[f'fat_{label}_ready'] = f['ready']
        s[f'fat_{label}_rank_window'] = f['rank_window']
        for key in ('score', 'state', 'event', 'ext_seq', 'int_seq', 'regime', 'conf', 'ready', 'regime_ready',
                    'confirmed_bars', 'event_age', 'event_strength', 'event_time_ms', 'protected_type', 'protected_level',
                    'protected_distance_atr', 'nearest_eqh', 'eqh_distance_atr', 'eqh_touches', 'nearest_eql',
                    'eql_distance_atr', 'eql_touches', 'eqh_active', 'eql_active', 'liq_ref_high', 'liq_ref_low',
                    'last_liq_event', 'liq_event_age', 'liq_event_level', 'sweep_event', 'sweep_forming', 'atr_pct'):
            s[f'str_{label}_{key}'] = st[key]

    s.update(ctx['flow'])
    s.update(ctx['kcheck'])
    sync = ctx['sync'] or {}
    pool = ctx['pool']
    s['sync_mode'] = sync.get('mode')
    s['sync_pages'] = sync.get('pages')
    s['sync_fetched'] = sync.get('fetched')
    s['sync_gap_ms'] = sync.get('gap_ms')
    s['sync_error'] = sync.get('error')
    s['pool_gap_events'] = pool.gap_events
    s['pool_gap_ms_total'] = pool.gap_ms_total
    s['pool_resets'] = pool.resets
    s['pool_integrity_errors'] = pool.integrity_errors
    s['pool_contamination_reset'] = ctx['contaminated']
    s['used_weight_1m'] = tv2.RATE.current_weight()
    s.update(ctx['ob'])
    s['alerts'] = '|'.join(ctx['alert_codes'])
    s['alerts_skipped'] = '|'.join(ctx['alerts_skipped'])          # kısmi pencere yüzünden çalıştırılmayan alarmlar
    s['required_fields_missing'] = '|'.join(tv2.missing_required(s))
    return s, ctx['series']

# ═══════════════════════════════════════════════════════════════════════
# 5. CANLI DASHBOARD & ALARM YAZDIRMA (insan okuması için TXT)
# ═══════════════════════════════════════════════════════════════════════

def _f(v, fmt, none='—'):
    if v is None:
        return none
    try:
        return format(v, fmt)
    except (TypeError, ValueError):
        return str(v)

def _px(p):
    if p is None:
        return '—'
    a = abs(p)
    return f"{p:.2f}" if a >= 1000 else (f"{p:.4f}" if a >= 1 else f"{p:.6f}")

def _usd_signed(v):
    return '—' if v is None else f"${v:+,.0f}"

def _age(ms):
    if ms is None:
        return '—'
    return f"{ms / 1000:.1f} sn" if ms < 120_000 else f"{ms / 60000:.0f} dk"

def _dir(d):
    return {'UP': 'UP 🟢', 'DOWN': 'DOWN 🔴', 'FLAT': 'FLAT ⚪'}.get(d, 'VERİ YOK ⚪')

def _series(vals, fmt):
    return ' → '.join(_f(v, fmt) for v in vals)

def print_live_dashboard(snap, series, ctx, display_sym):
    s = snap
    realf = ctx['realf']
    flow = ctx['flow']
    pool = ctx['pool']
    sync = ctx['sync'] or {}
    mtf_fat = ctx['mtf_fat']
    mtf_str = ctx['mtf_str']
    border = "=" * 78
    sub_border = "-" * 78
    cap_local = datetime.fromtimestamp(s['captured_at_ms'] / 1000.0)
    bar_local = datetime.fromtimestamp(s['bar_open_time'] / 1000.0)
    rank_tag = f"#{s['coin_rank']}" if s['coin_rank'] > 0 else ""

    print("\n" + border)
    print(f"  🔴 CANLI TAKİP: {display_sym} | {cap_local:%Y-%m-%d %H:%M:%S} | [{s['coin_class']}] {rank_tag}")
    print(f"  SNAPSHOT: {s['snapshot_id']} | sıra #{s['seq']} | Bar {bar_local:%H:%M} {'KAPANDI' if s['is_bar_closed'] else 'CANLI'} ({s['bar_progress_sec']:.0f}. sn)")
    print(f"  FİYAT: {s['price']:.6f}  |  1m DEĞİŞİM: {s['chg_1m_pct']:+.2f}%  |  RVOL: {realf['rvol']}x")
    print(border)

    print("  [1] GERÇEK ALIM-SATIM & CVD AKIŞI (Taker Order-Flow):")
    print(f"    • DOĞRULAMA         : FLOW SOURCE: {s['provider']} / {s['symbol']} / {s['market']}")
    print(f"    • PENCERE & EŞLEŞME : FLOW WINDOW: 1m | LAST TRADE SYMBOL: {s['symbol']}")
    print(f"    • İZOLE HAVUZ       : {len(pool.trades)} trade | Son fiyat: {pool.last_price:.6f} | Hata: {pool.integrity_errors}")
    if pool.integrity_errors > 0:
        print(f"    ⚠️ [VERİ İHLALİ KORUMASI]: {pool.integrity_errors} adet yabancı/hatalı trade engellendi!")
    cov = ' · '.join(f"{w} %{flow[f'window_coverage_ratio_{w}'] * 100:.0f}{'' if flow[f'{w}_complete'] else ' KISMİ'}" for w in ('1m', '5m', '15m'))
    extra = ''
    if sync.get('gap_ms'):
        extra += f" | ⚠️ boşluk {sync['gap_ms'] / 1000:.0f} sn"
    if sync.get('error'):
        extra += f" | ⚠️ {sync['error']}"
    print(f"    • SENKRON & KAPSAMA : {sync.get('pages', 0)} sayfa ({sync.get('mode') or '-'}) | kapsama {cov} | son işlem {_age(flow['last_trade_age_ms'])} önce | ağırlık {s['used_weight_1m']}/2400{extra}")
    print(f"    • 1 Dakikalık Akış  : Alış: ${flow['flow_1m_buy_usd']:,.1f} | Satış: ${flow['flow_1m_sell_usd']:,.1f} ({flow['trade_count_1m']} İşlem)")
    print(f"      Net CVD           : ${flow['cvd_1m']:+,.1f} ({_dir(flow['flow_1m_direction'])}) | Alıcı Oranı: %{_f(flow['buyer_ratio_1m'], '.1f')}")
    print(f"      Project Z Skoru   : {flow['flow_1m_score']:.1f} / 100")
    print(f"    • 5 Dakikalık Akış  : Net CVD: ${flow['cvd_5m']:+,.1f} | Alıcı: %{_f(flow['buyer_ratio_5m'], '.1f')} | CVD: {_dir(flow['flow_5m_direction'])}")
    print(f"    • 15 Dakikalık Akış : Net CVD: ${flow['cvd_15m']:+,.1f} | Alıcı: %{_f(flow['buyer_ratio_15m'], '.1f')}")
    if ctx['div_text']:
        print(f"    ⭐ {ctx['div_text']}")
    kc = ctx['kcheck']
    if kc['kcheck_status'] == 'ok':
        print(f"    • VERİ KONTROLÜ     : son kapanmış bar havuz/kline → hacim {_f(kc['pool_vs_kline_notional_ratio'], '.3f')} · işlem {_f(kc['pool_vs_kline_trades_ratio'], '.3f')} · alış {_f(kc['pool_vs_kline_taker_buy_ratio'], '.3f')}")
    else:
        print(f"    • VERİ KONTROLÜ     : son kapanmış bar için havuz eksik ({kc['kcheck_status']}) — ilk dakikalarda normal")

    print(sub_border)

    print("  [2] DAKİKALIK BİRİKİM & İNDİKATÖR GEÇMİŞİ (Son 6 Mum):")
    print("    SAAT  | FİYAT    | 1m BAR% | ALICI $  | SATICI $ | NET CVD $ | FATIGUE | DURUM   | REALF")
    for r in ctx['history_rows']:
        fat_tag = "🔴" if r['fat_st'] == "ASIRI" else "🟠" if r['fat_st'] == "YORGUN" else "🟢"
        print(f"    {r['time']} | {r['close']:.6f} | {r['chg']:+6.2f}% | ${r['tb']:7,.0f} | ${r['ts']:7,.0f} | ${r['cvd']:+8,.0f} | {r['fat']:5.1f} {fat_tag} | {r['fat_st']:7s} | {r['realf']:5.1f}")

    print(sub_border)

    print(f"  [3] ZPTDIFAT (Yorgunluk) & STRUCTURE {STRUCTURE_VERSION} (MTF Matrisi) — mum: {s['mtf_source']}:")
    print("    TF  | BAR | FATIGUE  | DURUM       || STR SCORE | STR DURUM | STR EVENT | REGIME     | CONF | HAZIR")
    for label, _m, _i in MTF_TFS:
        f_info = mtf_fat[label]
        s_info = mtf_str[label]
        color_tag = "🔴" if f_info['state'] == "ASIRI" else "🟠" if f_info['state'] == "YORGUN" else "🟢" if f_info['state'] == "NORMAL" else "🔵"
        st_state = s_info['state']
        st_tag = "⚪" if st_state == 'WARM' else ("🟢" if ("BULL" in st_state or "UP" in st_state) else ("🔴" if ("BEAR" in st_state or "DN" in st_state) else "⚪"))
        ready = f"F{'✓' if f_info['ready'] else '✗'} S{'✓' if s_info['ready'] else '✗'} R{'✓' if s_info['regime_ready'] else '✗'}"
        print(f"    {label:>3s} | {s[f'tf_{label}_bars']:>3} | {f_info['fat']:>8.1f} | {color_tag} {f_info['state']:<9s} || {_f(s_info['score'], '>9.1f'):>9s} | {st_tag} {st_state:<7s} | {(s_info['event'] or '—'):<9s} | {(s_info['regime'] or '—'):<10s} | {_f(s_info['conf'], '4.1f'):>4s} | {ready}")

    print(sub_border)

    print(f"  [4] REALF ({REALF_ENGINE}) — Fiyat & Akış Değerleme Dengesi & 12 Tanı Metriği:")
    r_tag = "⚠️" if "AHEAD" in realf['state'] or "LAG" in realf['state'] else "⚖️"
    print(f"    • GENEL SKOR      : {realf['score']} / 100 ({r_tag} {realf['state']})")
    print(f"    • 4 BİLEŞEN       : Impact: {realf['impact_score']:.1f} | Memory: {realf['memory_score']:.1f} | Momentum: {realf['momentum_score']:.1f} | Activity: {realf['activity_score']:.1f}")
    print(f"    • UNPRICED FLOW   : RemainingUnpricedFlow: {realf['inventory']:+.5f} log units")
    print(f"    • FAST IMPULSE    : FastPrice: {realf['fast_price']:+.2f} | FastFlow: {realf['fast_flow']:+.2f}")
    print(f"    • REGRESYON MODEL : Beta: {realf['beta']:.5f} | Beta R²: {realf['beta_r2']:.3f}")
    print(f"    • HACİM & AKIŞ    : Dollar RVOL: {realf['rvol']:.2f}x | Volume Percentile: %{realf['percentile']:.1f} | Persistence: %{realf['persistence']:.1f}")
    print(f"    • WHALE DURUMU    : {realf['whale']} (Son 20 Bar İmzalı Hacim Net: {realf['net_pct']:+0.1f}%)")
    print(f"    • BİLEŞEN UYUMU   : Spread: {_f(realf['component_spread'], '.1f')} | Agreement: {_f(realf['component_agreement'], '.2f')} | Hazır: {'EVET' if realf['ready'] else 'HAYIR'} ({realf['bars']} bar)")
    print(f"    • FLOW-İMA FİYAT  : {_px(realf['implied_price'])} ({_f(realf['implied_gap_pct'], '+.2f')}%) | Kaynak: {s['realf_source']} · kalite {_f(s['realf_source_quality'], '.0f')}/100")
    if flow['last_whale_usd']:
        lw_time = datetime.fromtimestamp(flow['last_whale_time_ms'] / 1000.0).strftime('%H:%M:%S')
        side = 'BUY 🟢' if flow['last_whale_side'] == 'BUY' else 'SELL 🔴'
        print(f"    • SON BÜYÜK EMİR  : [{lw_time}] {side} ${flow['last_whale_usd']:,.0f} @ {_px(flow['last_whale_price'])} ({s['symbol']})")

    print(sub_border)

    print("  [5] DELTA TRACKER (1m bara hizalı: 5 kapanmış bar → canlı bar):")
    print(f"    • REALF     : {_series(series['realf_series'], '.1f')} | Δ1 {_f(s['realf_d1'], '+.1f')} · Δ3 {_f(s['realf_d3'], '+.1f')} · Δ5 {_f(s['realf_d5'], '+.1f')}")
    print(f"    • FATIGUE   : {_series(series['fatigue_series'], '.1f')} | Δ1 {_f(s['fatigue_delta_1m'], '+.1f')} · Δ3 {_f(s['fatigue_delta_3m'], '+.1f')} · Δ5 {_f(s['fatigue_delta_5m'], '+.1f')} | abs {s['absolute_fatigue']:.1f} · rank {s['relative_rank']:.1f}")
    print(f"    • UNPRICED  : {_series(series['unpriced_series'], '+.4f')} | Δ1 {_f(s['unpriced_d1'], '+.5f')} · Δ3 {_f(s['unpriced_d3'], '+.5f')} · Δ5 {_f(s['unpriced_d5'], '+.5f')}")
    print(f"    • CVD Δ     : (canlı pencere − 1 dk önceki aynı pencere) 1m {_usd_signed(flow['cvd_1m_delta'])} · 5m {_usd_signed(flow['cvd_5m_delta'])} · 15m {_usd_signed(flow['cvd_15m_delta'])} | Alıcı% Δ 1m {_f(flow['buyer_ratio_delta_1m'], '+.1f')} · 5m {_f(flow['buyer_ratio_delta_5m'], '+.1f')}")
    print(f"    • CVD EĞİM  : 3dk {_usd_signed(flow['cvd_slope_3m'])}/dk (norm {_f(flow['cvd_slope_3m_norm'], '+.3f')}) · 5dk {_usd_signed(flow['cvd_slope_5m'])}/dk (norm {_f(flow['cvd_slope_5m_norm'], '+.3f')}) · önceki 3dk norm {_f(flow['cvd_slope_prev_3m_norm'], '+.3f')} → DÖNÜŞ: {flow['cvd_turn_3m'] or '—'}")

    print(sub_border)

    print("  [6] FLOW CONFIDENCE (shadow — hiçbir skora girmez) · TAM/KISMİ = karar-alarm uygunluğu:")
    print("    PENCERE | TAMLIK |  İŞLEM |  n_eff |        HACİM $ | KAPSAMA   | BÜYÜK ALIŞ (adet/$) | BÜYÜK SATIŞ (adet/$) | GÜVEN")
    for w in ('1m', '5m', '15m'):
        fc = flow[f'flow_confidence_{w}']
        emoji = "🟢" if fc >= 60 else ("🟡" if fc >= 30 else "🔴")
        complete = 'TAM   ' if flow[f'{w}_complete'] else 'KISMİ '
        print(f"    {w:>7s} | {complete} | {flow[f'trade_count_{w}']:>6d} | {flow[f'n_eff_{w}']:>6.1f} | ${flow[f'notional_{w}']:>13,.0f} | {flow[f'window_coverage_sec_{w}']:>4.0f}s %{flow[f'window_coverage_ratio_{w}'] * 100:>3.0f} | {flow[f'large_buy_count_{w}']:>3d} / ${flow[f'large_buy_value_{w}']:>12,.0f} | {flow[f'large_sell_count_{w}']:>3d} / ${flow[f'large_sell_value_{w}']:>13,.0f} | {emoji} {fc:5.1f}")

    print(sub_border)

    print(f"  [7] STRUCTURE {STRUCTURE_VERSION} DETAY (dizilim · son olay · korunan seviye · EQH/EQL bölgeleri · likidite; mesafeler ATR):")
    print("    TF  | EXT      | INT      | OLAY (yaş bar/güç)   | KORUNAN (mesafe)        | EQH ↑ (mesafe/temas) | EQL ↓ (mesafe/temas) | LİKİDİTE (yaş)")
    for label, _m, _i in MTF_TFS:
        si = mtf_str[label]
        ev = f"{si['event']} ({si['event_age']}b/{si['event_strength']:.0f})" if si['event_age'] is not None else ('WARM' if not si['ready'] else 'NONE')
        prot = f"{si['protected_type']} {_px(si['protected_level'])} ({_f(si['protected_distance_atr'], '+.2f')})" if si['protected_level'] is not None else 'NONE'
        eqh = f"{_px(si['nearest_eqh'])} ({_f(si['eqh_distance_atr'], '.2f')}/{si['eqh_touches']}×)" if si['nearest_eqh'] is not None else f"— ({si['eqh_active']} bölge)"
        eql = f"{_px(si['nearest_eql'])} ({_f(si['eql_distance_atr'], '.2f')}/{si['eql_touches']}×)" if si['nearest_eql'] is not None else f"— ({si['eql_active']} bölge)"
        liq = f"{si['last_liq_event']} ({si['liq_event_age']}b)" if si['liq_event_age'] is not None else 'NONE'
        if si['sweep_forming']:
            liq += ' +canlı?'
        print(f"    {label:>3s} | {si['ext_seq']:<8s} | {si['int_seq']:<8s} | {ev:<20s} | {prot:<23s} | {eqh:<20s} | {eql:<20s} | {liq}")

    print(sub_border)

    ob = ctx['ob']
    if ob.get('ob_error'):
        print(f"  [8] ORDERBOOK: veri yok ({ob['ob_error']}) — karar verisi değil")
    else:
        ob_time = datetime.fromtimestamp(ob['ob_timestamp_ms'] / 1000.0).strftime('%H:%M:%S.%f')[:-3] if ob['ob_timestamp_ms'] else '—'
        stale_tag = f"🚨 BAYAT ({_age(ob['ob_age_ms'])}) — karar verisi değil" if ob['ob_stale'] else f"yaş {_age(ob['ob_age_ms'])}"
        print(f"  [8] ORDERBOOK (ilk 20 kademe, {ob_time} · {stale_tag}): Spread {_f(ob['spread_bps'], '.2f')} bps | Dengesizlik top5 {_f(ob['ob_imbalance_top5'], '+.2f')} · top20 {_f(ob['orderbook_imbalance'], '+.2f')} | Microprice {_f(ob['microprice_deviation_bps'], '+.2f')} bps | Derinlik ±{_f(ob['ob_depth_span_bps'], '.1f')} bps | Alış ${ob['ob_bid_notional_20']:,.0f} · Satış ${ob['ob_ask_notional_20']:,.0f}")

    print(sub_border)

    if ctx['alerts']:
        print("  [9] ANLIK KRİTİK ALARMLAR:")
        for a in ctx['alerts']:
            print(f"    {a}")
    else:
        print("  [9] ANLIK KRİTİK ALARMLAR: Piyasa sakin, nötr akış.")
    if ctx['alerts_skipped']:
        print(f"    ℹ️ Akış alarmları çalıştırılmadı (kısmi pencere): {', '.join(ctx['alerts_skipped'])}")

    print(border + "\n")

# ═══════════════════════════════════════════════════════════════════════
# 6. ANA CANLI TAKİP DÖNGÜSÜ
# ═══════════════════════════════════════════════════════════════════════

def _timed(fn, *args):
    data = fn(*args)
    return data, tv2.CLOCK.now_ms()

def run_single_tracking_cycle(target_sym, session):
    clean = target_sym.upper().replace('.P', '').replace('_', '')
    is_mexc = 'LONGXIA' in clean
    provider = 'MEXC' if is_mexc else 'BINANCE'
    market = 'FUTURES'
    sym_key = 'LONGXIA_USDT' if is_mexc else clean
    display_sym = 'LONGXIA_USDT (MEXC/Bybit)' if is_mexc else f"{clean}.P (Binance)"
    settings = session.settings
    tv2.CLOCK.refresh()

    htf = {}
    depth = None
    depth_error = None
    if is_mexc:
        candles, kline_asof_ms = _timed(fetch_candles_mexc)
        depth_error = 'unsupported_provider'
    else:
        ex = session.executor
        fut_1m = ex.submit(_timed, fetch_candles_binance, clean, '1m', KLINE_LIMIT_1M)
        fut_htf = {}
        if settings['mtf'] == 'native':
            for label, _m, interval in MTF_TFS[1:]:
                fut_htf[label] = ex.submit(fetch_candles_binance, clean, interval, HTF_KLINE_LIMIT)
        fut_depth = ex.submit(fetch_orderbook_binance, clean) if settings['depth'] else None
        candles, kline_asof_ms = fut_1m.result()
        for label, fut in fut_htf.items():
            try:
                htf[label] = fut.result()
            except Exception as e:
                htf[label] = None
                print(f"  ⚠️ [{clean}] {label} mumları alınamadı ({e}) — 1m'den türetildi.")
        if fut_depth is not None:
            try:
                depth = fut_depth.result()
            except Exception as e:
                depth_error = f"{type(e).__name__}: {e}"
        else:
            depth_error = 'disabled'

    ref_price = candles['close'][-1] if candles and candles['close'] else 0.0
    sync = fetch_live_trades(provider, market, sym_key, reference_price=ref_price, max_pages=settings['max_pages'])
    pool = flow_manager.get_pool(provider, market, sym_key)
    # Snapshot anı = havuzun eksiksiz olduğu son an (son senkron isteğinin başlangıcı).
    # Senkron başarısız/atlandıysa şimdiki an alınır; aradaki boşluk kapsama oranında görünür.
    now_after_sync = tv2.CLOCK.now_ms()
    if not sync.get('error') and pool.known_until_ms is not None and 0 <= now_after_sync - pool.known_until_ms < 5000:
        captured_at_ms = pool.known_until_ms
    else:
        captured_at_ms = now_after_sync

    contaminated = False
    if pool.last_price > 0 and ref_price > 0:
        runtime_dev = abs(pool.last_price - ref_price) / ref_price
        if runtime_dev > 0.30:
            print(f"    🚨 [KRİTİK] {sym_key} flow havuzu kontamine! Son trade fiyatı: {pool.last_price:.6f}, Beklenen: {ref_price:.6f} — HAVUZ SIFIRLANDI!")
            pool.reset(captured_at_ms)
            contaminated = True

    curr_c = candles['close'][-1]
    prev_c = candles['close'][-2] if len(candles['close']) > 1 else curr_c
    chg_1m = ((curr_c - prev_c) / prev_c) * 100.0 if prev_c else 0.0

    history_rows = get_recent_minute_history(candles, limit=6)
    mtf_fat, mtf_str, tf_meta = {}, {}, {}
    for label, minutes, _interval in MTF_TFS:
        if minutes == 1:
            c_tf, src = candles, 'native'
        elif htf.get(label):
            c_tf, src = htf[label], 'native'
        else:
            c_tf, src = resample_candles(candles, minutes), 'resampled_1m'
        mtf_fat[label] = calc_fatigue(c_tf)
        mtf_str[label] = calc_structure(c_tf)
        tf_meta[label] = {'bars': len(c_tf['close']), 'source': src}
    realf = calc_realf(candles)

    flow = tv2.compute_flow_features(pool, captured_at_ms, float(get_whale_threshold(sym_key)))
    kcheck = tv2.pool_kline_check(pool, candles, captured_at_ms, kline_asof_ms)
    ob = tv2.orderbook_features(depth, captured_at_ms)
    if depth is None and depth_error:
        ob['ob_error'] = depth_error
    indicator_deltas, series = tv2.indicator_series_features(history_rows)
    alerts, alert_codes, div_text, alerts_skipped = _alerts(chg_1m, flow, realf, mtf_fat)

    session.seq += 1
    ctx = {
        'seq': session.seq, 'snapshot_id': tv2.make_snapshot_id(sym_key, captured_at_ms),
        'symbol': sym_key, 'provider': provider, 'market': market,
        'captured_at_ms': captured_at_ms, 'kline_asof_ms': kline_asof_ms,
        'candles': candles, 'price': curr_c, 'chg_1m': chg_1m,
        'history_rows': history_rows, 'mtf_fat': mtf_fat, 'mtf_str': mtf_str, 'tf_meta': tf_meta,
        'realf': realf, 'kline_quality': kline_quality(candles), 'indicator_deltas': indicator_deltas, 'series': series,
        'flow': flow, 'kcheck': kcheck, 'ob': ob, 'sync': sync, 'pool': pool, 'contaminated': contaminated,
        'alerts': alerts, 'alert_codes': alert_codes, 'div_text': div_text, 'alerts_skipped': alerts_skipped,
    }
    snap, snap_series = build_snapshot(session, ctx)
    print_live_dashboard(snap, snap_series, ctx, display_sym)

    session.last_capture_ms[sym_key] = captured_at_ms
    session.snapshots += 1
    if session.writer is not None:
        session.writer.add_snapshot(snap, snap_series)
        session.outcomes.register(sym_key, snap['snapshot_id'], kline_asof_ms, curr_c)
        session.outcomes.evaluate(sym_key, candles, tv2.CLOCK.now_ms())
        session.writer.flush()
    _flush_console()
    return snap

def _flush_console():
    try:
        sys.stdout.flush()
    except Exception:
        pass

def keep_system_awake(enable=True):
    """Takip açıkken Windows'un BOŞTA KALINCA uykuya (S3) geçmesini engeller — medya oynatıcıların yaptığı
    SetThreadExecutionState isteği. Ekranın kapanmasını engellemez, güç planını DEĞİŞTİRMEZ; ana iş parçacığı
    / program kapanınca istek kendiliğinden kalkar. Kapak kapatma ve güç tuşu yine uyutur."""
    if os.name != 'nt':
        return False
    try:
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if enable else 0)
        return ctypes.windll.kernel32.SetThreadExecutionState(ctypes.c_uint(flags)) != 0
    except Exception:
        return False

def disable_console_quickedit():
    """Windows konsolunda QuickEdit açıkken pencereye tıklamak/seçim yapmak yazmayı ve dolayısıyla takibi
    durdurur (uzun çalışmada sessiz veri kaybı). Yalnız BU pencerenin modunu değiştirir."""
    if os.name != 'nt':
        return False
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-10)               # STD_INPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        ENABLE_QUICK_EDIT_MODE, ENABLE_EXTENDED_FLAGS = 0x0040, 0x0080
        return bool(kernel32.SetConsoleMode(handle, (mode.value | ENABLE_EXTENDED_FLAGS) & ~ENABLE_QUICK_EDIT_MODE))
    except Exception:
        return False

# ═══════════════════════════════════════════════════════════════════════
# 7. MOTOR TESTLERİ (ağ gerektirmez): STRUCTURE v1.2 · canlı bar sızıntısı · alarm kapıları
# ═══════════════════════════════════════════════════════════════════════

def _t_candles(anchors, width=0.5, t0=1_758_000_000):
    """anchors: (bar, kapanış) noktaları arasında doğrusal kapanış; high/low = ±width."""
    closes = []
    for (i0, c0), (i1, c1) in zip(anchors, anchors[1:]):
        for i in range(i0, i1):
            closes.append(c0 + (c1 - c0) * (i - i0) / (i1 - i0))
    closes.append(anchors[-1][1])
    c = {k: [] for k in ('time', 'open', 'high', 'low', 'close', 'vol', 'amount')}
    prev = closes[0]
    for i, cl in enumerate(closes):
        c['time'].append(t0 + i * 60)
        c['open'].append(prev)
        c['close'].append(cl)
        c['high'].append(max(prev, cl) + width)
        c['low'].append(min(prev, cl) - width)
        c['vol'].append(1.0)
        c['amount'].append(1000.0)
        prev = cl
    return c

def _t_append(c, close, high=None, low=None, amount=1000.0):
    c = {k: list(v) for k, v in c.items()}
    prev = c['close'][-1]
    c['time'].append(c['time'][-1] + 60)
    c['open'].append(prev)
    c['close'].append(close)
    c['high'].append(high if high is not None else max(prev, close) + 0.5)
    c['low'].append(low if low is not None else min(prev, close) - 0.5)
    c['vol'].append(1.0)
    c['amount'].append(amount)
    return c

# Yalnız KAPANMIŞ barlardan gelen alanlar (canlı bar bunları değiştiremez).
# nearest_eqh / nearest_eql / *_touches listede YOK: bunlar "canlı fiyata göre en yakın bölge" olduğu için
# fiyat değişince değişmeleri beklenir; bölgelerin kendisi liq_ref_high/low ve *_active ile denetlenir.
CONFIRMED_KEYS = ('state', 'event', 'ext_seq', 'int_seq', 'regime', 'ready', 'protected_type', 'protected_level',
                  'eqh_active', 'eql_active', 'last_liq_event', 'liq_event_level', 'liq_ref_high', 'liq_ref_low',
                  'event_strength', 'atr', 'confirmed_bars')

def selftest_engines():
    """STRUCTURE v1.2 kuralları, canlı bar sızıntısı ve alarm kapıları (ağ yok)."""
    import random
    fails = []

    def check(name, cond, detail=''):
        print(f"  {'✓' if cond else '✗'} {name}" + (f" — {detail}" if detail and not cond else ''))
        if not cond:
            fails.append(name)

    up = [(0, 100), (12, 106), (24, 102), (36, 110), (48, 105), (60, 116), (72, 110), (84, 122), (96, 117)]
    c_up = _t_candles(up)
    st_up = calc_structure(c_up)
    check('yükselen dizide BULL + HH/HL', st_up['state'] == 'BULL' and st_up['ext_seq'] == 'HH/HL' and st_up['score'] > 50,
          f"{st_up['state']}/{st_up['ext_seq']}/{st_up['score']}")
    check('yükselen dizide korunan LOW ve pozitif mesafe', st_up['protected_type'] == 'LOW' and st_up['protected_distance_atr'] > 0,
          str(st_up['protected_type']))
    down = [(0, 120), (12, 114), (24, 118), (36, 108), (48, 113), (60, 100), (72, 106), (84, 92), (96, 97)]
    st_dn = calc_structure(_t_candles(down))
    check('düşen dizide BEAR + LH/LL', st_dn['state'] == 'BEAR' and st_dn['ext_seq'] == 'LH/LL' and st_dn['score'] < 50,
          f"{st_dn['state']}/{st_dn['ext_seq']}/{st_dn['score']}")

    # WARM: yeterli teyitli pivot yokken sahte RANGE/50 yok
    short = _t_candles([(0, 100), (20, 101), (40, 100.5)])
    st_short = calc_structure(short)
    check('hazır değilken WARM (score/regime None)', st_short['state'] == 'WARM' and st_short['score'] is None
          and st_short['regime'] is None and st_short['ready'] is False, str(st_short['state']))

    # v1.2 EQH bölgesi: iki eşit tepe → ORTALAMA fiyat, temas 2
    eq = [(0, 100), (12, 106), (24, 102), (36, 110), (48, 104), (60, 116), (72, 110), (84, 116.05), (96, 111)]
    c_eq = _t_candles(eq)
    st_eq = calc_structure(c_eq)
    exp_zone = ((116 + 0.5) + (116.05 + 0.5)) / 2.0
    check('EQH bölgesi iki tepenin ortalaması', st_eq['nearest_eqh'] is not None and abs(st_eq['nearest_eqh'] - exp_zone) < 1e-9,
          f"{st_eq['nearest_eqh']} beklenen {exp_zone}")
    check('EQH temas sayısı 2 · aktif 1', st_eq['eqh_touches'] == 2 and st_eq['eqh_active'] == 1, str(st_eq))

    zone = st_eq['nearest_eqh']
    atr_eq = st_eq['atr']
    # Süpürme yalnız KAPANMIŞ barda sayılır: önce canlı bar olarak ekle → olay yok
    c_sweep_live = _t_append(c_eq, zone - 0.4, high=zone + atr_eq * 0.5)
    st_live = calc_structure(c_sweep_live)                      # son bar CANLI
    check('canlı bardaki süpürme teyitli olay üretmez', st_live['last_liq_event'] == st_eq['last_liq_event']
          and st_live['sweep_forming'] is True, f"{st_live['last_liq_event']}/{st_live['sweep_forming']}")
    st_conf = calc_structure(c_sweep_live, is_bar_closed=True)  # aynı bar KAPANDI
    check('kapanmış barda EQH_SWEEP', st_conf['last_liq_event'] == 'EQH_SWEEP' and st_conf['liq_event_age'] == 0
          and abs(st_conf['liq_event_level'] - zone) < 1e-9, str(st_conf['last_liq_event']))

    # Aynı bölge ikinci kez süpürmede tekrar olay üretmez (bölge başına sweep kilidi)
    c_sweep2 = _t_append(c_sweep_live, zone - 0.5, high=zone + atr_eq * 0.5)
    st_sweep2 = calc_structure(c_sweep2, is_bar_closed=True)
    check('aynı bölge tekrar süpürmede yeni olay yok', st_sweep2['liq_event_age'] == 1, str(st_sweep2['liq_event_age']))

    # Kapanışla kabul → bölge tüketilir
    c_accept = _t_append(c_eq, zone + atr_eq * 0.6, high=zone + atr_eq * 0.8)
    st_accept = calc_structure(c_accept, is_bar_closed=True)
    check('kapanış bölgenin üstünde → bölge tüketildi', st_accept['eqh_active'] == 0 and st_accept['nearest_eqh'] is None,
          str(st_accept['eqh_active']))

    # Aktif bölge yokken swing seviyesi yedek likidite referansı (v1.2 fallback)
    c_swing = _t_append(_t_append(c_up, c_up['close'][-1] - 1.0), st_up['liq_ref_high'] - 1.0,
                        high=st_up['liq_ref_high'] + st_up['atr'] * 0.5)
    st_swing = calc_structure(c_swing, is_bar_closed=True)
    check('aktif EQ bölge yokken swing süpürmesi', st_up['eqh_active'] == 0 and st_swing['last_liq_event'] == 'HIGH_SWEEP',
          f"{st_up['eqh_active']}/{st_swing['last_liq_event']}")

    # FIFO: yön başına en fazla 3 aktif bölge
    many = [(0, 100), (12, 108), (24, 101), (36, 108.05), (48, 100), (60, 120), (72, 112), (84, 120.05), (96, 111),
            (108, 130), (120, 122), (132, 130.05), (144, 121), (156, 140), (168, 132), (180, 140.05), (192, 131)]
    st_many = calc_structure(_t_candles(many))
    check('EQH bölge sayısı 3 ile sınırlı', st_many['eqh_active'] <= 3, str(st_many['eqh_active']))

    # ── SIZINTI: canlı bar teyitli çıktıyı DEĞİŞTİREMEZ ──
    rng = random.Random(4242)
    leak_fail = []
    for seed in range(12):
        rr = random.Random(seed)
        price = 50.0
        c = {k: [] for k in ('time', 'open', 'high', 'low', 'close', 'vol', 'amount')}
        for i in range(260):
            o = price
            cl = round(o * (1 + rr.gauss(0.0002 * ((i // 40) % 3 - 1), 0.004)), 3)
            c['time'].append(1_758_000_000 + i * 60)
            c['open'].append(o)
            c['close'].append(cl)
            c['high'].append(round(max(o, cl) * (1 + abs(rr.gauss(0, 0.002))), 3))
            c['low'].append(round(min(o, cl) * (1 - abs(rr.gauss(0, 0.002))), 3))
            c['vol'].append(1.0)
            c['amount'].append(1e5)
            price = cl
        base = calc_structure(c)                                   # son bar canlı
        closed_only = calc_structure({k: v[:-1] for k, v in c.items()}, is_bar_closed=True)
        for k in CONFIRMED_KEYS:
            if base[k] != closed_only[k]:
                leak_fail.append((seed, k, base[k], closed_only[k]))
        # canlı barı aşırı manipüle et: teyitli alanlar yine değişmemeli
        spiked = {k: list(v) for k, v in c.items()}
        spiked['high'][-1] = spiked['high'][-1] * 1.5
        spiked['low'][-1] = spiked['low'][-1] * 0.5
        spiked['close'][-1] = spiked['close'][-1] * 1.4
        manipulated = calc_structure(spiked)
        for k in CONFIRMED_KEYS:
            if base[k] != manipulated[k]:
                leak_fail.append((seed, 'spike:' + k, base[k], manipulated[k]))
    check('canlı bar teyitli yapı alanlarını etkilemiyor (12 seri)', not leak_fail, str(leak_fail[:3]))

    # ── SIZINTI: bar hizalı seriler gelecekten etkilenmiyor ──
    c = _t_candles([(0, 100), (40, 104), (80, 99), (120, 107), (160, 103), (200, 110), (240, 106)])
    rows_full = get_recent_minute_history(c, limit=6)
    rows_trunc = get_recent_minute_history({k: v[:-1] for k, v in c.items()}, limit=6)
    check('realf_1m_ago geçmişten hesaplanıyor (gelecek sızıntısı yok)',
          rows_full[-2]['realf'] == rows_trunc[-1]['realf'] and rows_full[-2]['fat'] == rows_trunc[-1]['fat'],
          f"{rows_full[-2]['realf']} vs {rows_trunc[-1]['realf']}")

    # ── Alarm kapıları: kısmi pencere ve bayat orderbook karar verisi değil ──
    flow_full = {'1m_complete': True, 'cvd_1m_pct': 12.0, 'buyer_ratio_1m': 85.0, 'notional_1m': 50_000.0}
    flow_part = dict(flow_full, **{'1m_complete': False})
    fat = {'1m': {'state': 'NORMAL'}, '5m': {'state': 'NORMAL'}, '15m': {'state': 'NORMAL'}}
    realf_mid = {'score': 50.0}
    a_full = _alerts(-0.5, flow_full, realf_mid, fat)
    a_part = _alerts(-0.5, flow_part, realf_mid, fat)
    check('tam pencerede akış alarmları çalışır', 'BULL_CVD_DIVERGENCE' in a_full[1] and 'AGGRESSIVE_BUYER' in a_full[1], str(a_full[1]))
    check('kısmi pencerede akış alarmı YOK', not a_part[1] and 'flow_1m_incomplete' in a_part[3], str(a_part[1]))
    check('kısmi pencerede yorgunluk/REALF alarmı etkilenmez',
          'FATIGUE_EXTREME' in _alerts(0.0, flow_part, realf_mid, {'1m': {'state': 'ASIRI'}, '5m': {'state': 'NORMAL'}, '15m': {'state': 'NORMAL'}})[1])
    import ast
    import inspect
    fn = ast.parse(textwrap.dedent(inspect.getsource(_alerts))).body[0]
    if fn.body and isinstance(fn.body[0], ast.Expr) and isinstance(fn.body[0].value, ast.Constant):
        fn.body = fn.body[1:]                                   # docstring'i at, yalnız kodu incele
    code_only = ast.unparse(fn)
    check('alarm kodu orderbook alanlarına bakmıyor', 'ob_' not in code_only and 'orderbook' not in code_only.lower(),
          code_only[:120])
    check('_alerts imzasında orderbook yok', 'ob' not in inspect.signature(_alerts).parameters)

    print(f"\n  MOTOR TESTİ SONUCU: {'TÜMÜ GEÇTİ' if not fails else str(len(fails)) + ' HATA: ' + ', '.join(fails)}")
    return not fails

def parse_args(argv):
    ap = argparse.ArgumentParser(description='Canlı Takip Logger v2 — REALF / Fatigue / Structure / Order-Flow')
    ap.add_argument('targets', nargs='*', help='Coin veya grup: TEST, TOP100, OUTSIDE100, MEVCUT, ALL26, ETHUSDT ...')
    ap.add_argument('--log-dir', default=os.path.join(SCRIPT_DIR, 'logs'), help='Kayıt klasörü (varsayılan: bu klasördeki logs/)')
    ap.add_argument('--no-files', action='store_true', help='Dosyaya yazma (yalnız konsol)')
    ap.add_argument('--mtf', choices=['native', 'resample'], default='native',
                    help='3m-4h mum kaynağı: native = Binance\'ten gerçek mum (varsayılan), resample = eski davranış (500 adet 1m\'den türet)')
    ap.add_argument('--no-depth', action='store_true', help='Orderbook çekme')
    ap.add_argument('--max-pages', type=int, default=5, help='Coin başına tur içinde en fazla aggTrades sayfası (1000 işlem/sayfa)')
    ap.add_argument('--outcomes', nargs='?', const='latest', default=None, metavar='RUN',
                    help='Takip yerine sonuç değerlendirmesi yap (run klasörü adı ya da latest)')
    ap.add_argument('--selftest', action='store_true', help='Ağsız kendi kendine test')
    ap.add_argument('--allow-sleep', action='store_true',
                    help='Takip açıkken bilgisayarın boşta uyumasına izin ver (varsayılan: uyku engellenir)')
    return ap.parse_args(argv)

if __name__ == '__main__':
    args = parse_args(sys.argv[1:])

    if args.selftest:
        ok_infra = tv2.selftest()
        print()
        ok_engines = selftest_engines()
        sys.exit(0 if (ok_infra and ok_engines) else 1)

    if args.outcomes is not None:
        target = tv2.resolve_run_dir(args.log_dir, args.outcomes)
        if not target or not os.path.isdir(target):
            print(f"  ⚠️ Değerlendirilecek çalışma bulunamadı ({args.outcomes}) — klasör: {args.log_dir}")
            sys.exit(1)
        tv2.CLOCK.refresh(force=True)
        print(f"  ⚡ SONUÇ DEĞERLENDİRME: {target}")
        tv2.offline_evaluate(target)
        sys.exit(0)

    GROUP_MEVCUT = ['BTCUSDT', 'SOLUSDT', 'SYNUSDT', 'IOSTUSDT', 'SAGAUSDT', 'LONGXIA']
    GROUP_TOP100 = ['ETHUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'LINKUSDT',
                    'ADAUSDT', 'LTCUSDT', 'AVAXUSDT', 'SUIUSDT', 'AKEUSDT']
    GROUP_OUTSIDE100 = ['PONSUSDT', 'SKRUSDT', 'PROMUSDT', 'UAIUSDT', 'BULLAUSDT',
                        'OGUSDT', 'ZORAUSDT', 'TNSRUSDT', 'VELVETUSDT', 'ZKCUSDT']
    GROUP_ALL_26 = GROUP_MEVCUT + GROUP_TOP100 + GROUP_OUTSIDE100

    targets = [t.upper().replace('.P', '') for t in args.targets]

    expanded = []
    for t in targets:
        if t in ('ALL', 'TUMU', 'ALL26'):
            expanded = GROUP_ALL_26
            break
        elif t == 'MEVCUT':
            expanded.extend(GROUP_MEVCUT)
        elif t == 'TOP100':
            expanded.extend(GROUP_TOP100)
        elif t == 'OUTSIDE100':
            expanded.extend(GROUP_OUTSIDE100)
        elif t == 'TEST':
            expanded.extend(GROUP_TOP100 + GROUP_OUTSIDE100)
        else:
            clean = t.replace('_', '')
            if 'LONGXIA' in clean:
                expanded.append('LONGXIA')
            elif not clean.endswith('USDT'):
                expanded.append(clean + 'USDT')
            else:
                expanded.append(clean)

    if not expanded:
        expanded = GROUP_MEVCUT

    seen = set()
    track_list = []
    for c in expanded:
        if c not in seen:
            seen.add(c)
            track_list.append(c)

    settings = {'mtf': args.mtf, 'depth': not args.no_depth, 'max_pages': max(1, args.max_pages),
                'inter_coin_delay': 2 if len(track_list) > 15 else 3, 'cycle_delay': 3 if len(track_list) > 15 else 6}

    run = writer = outcomes = sink = None
    if not args.no_files:
        run = tv2.RunContext(args.log_dir, SCRIPT_DIR, sys.argv, settings)
        sink = tv2.ConsoleSink(run.run_dir)
        sys.stdout = tv2.TeeStream(sys.stdout, sink)
        sys.stderr = tv2.TeeStream(sys.stderr, sink)
        writer = tv2.SnapshotWriter(run.run_dir)
        outcomes = tv2.LiveOutcomeTracker(writer, run.run_id)
    session = TrackerSession(settings, run, writer, outcomes)
    quickedit_off = disable_console_quickedit()
    awake = False if args.allow_sleep else keep_system_awake(True)

    tv2.CLOCK.refresh(force=True)

    print("=" * 78)
    print(f"  ⚡ KONTRAT DOĞRULAMASI BAŞLIYOR ({len(track_list)} coin)...")
    track_list = verify_contracts(track_list)

    n_mevcut = sum(1 for c in track_list if get_coin_info(c)['class'] == 'MEVCUT')
    n_top100 = sum(1 for c in track_list if get_coin_info(c)['class'] == 'TOP100')
    n_out100 = sum(1 for c in track_list if get_coin_info(c)['class'] == 'OUTSIDE100')

    print(f"  ✅ {len(track_list)} coin doğrulandı ve takibe hazır")
    print(f"     MEVCUT: {n_mevcut} | TOP100: {n_top100} | OUTSIDE100: {n_out100}")
    print("=" * 78)
    print(f"  ⚡ CANLI TAKİP BAŞLATILDI: {len(track_list)} COİN  (Logger {tv2.TRACKER_VERSION})")
    print(f"  Coinler: {', '.join(track_list)}")
    print("  • Gerçek Taker Alım/Satım & Project Z CVD (İzole Havuz, aggTradeId boşluk takibi)")
    print("  • Dakikalık Birikim & Hacim Geçmişi")
    print(f"  • ZPTDIFAT MTF Yorgunluk Matrisi & STRUCTURE {STRUCTURE_VERSION} (mum kaynağı: {settings['mtf']})")
    print("  • REALF Akış/Fiyat Dengesi & 12 Tanı Metriği")
    print(f"  • Motorlar: STRUCTURE {STRUCTURE_VERSION} · REALF {REALF_ENGINE} · FATIGUE {FATIGUE_VERSION} · FC {tv2.FLOW_CONFIDENCE_VERSION} · şema {tv2.DATASET_SCHEMA} · logger {tv2.TRACKER_VERSION}")
    print(f"  • Borsa saati farkı: {tv2.CLOCK.offset_ms:+d} ms ({'senkron' if tv2.CLOCK.ok else 'ALINAMADI — yerel saat kullanılıyor'})")
    if not tv2.CLOCK.ok:
        hint = tv2.network_hint(tv2.CLOCK.last_error)
        print(f"  🚨 BINANCE BAĞLANTISI YOK: {tv2.CLOCK.last_error}")
        if hint:
            print(f"  👉 {hint}")
    if run is not None:
        print(f"  • KAYIT KLASÖRÜ : {run.run_dir}")
        print("      SAATLİK parçalar: console_YYYYMMDD_HH.txt (bu ekranın TAMAMI) · snapshots_YYYYMMDD_HH.jsonl / .csv (analiz)")
        print("      outcomes.jsonl: 60 dk dolan snapshot'ların sonuçları takip sürerken yazılır (uzun çalışmada durdurmaya gerek yok)")
        print(f"      Kod parmak izi: {run.code_fingerprint} · git: {run.git_commit or 'yok (klasör git deposu değil)'}")
        print("      GPT için günlük tablo: SONUCLARI_HESAPLA.bat (takip SÜRERKEN de çalıştırılabilir) → snapshots_with_outcomes_YYYYMMDD.csv")
        print("      Disk: ~20 KB/snapshot ≈ 20 coin için saatte ~20-25 MB (günde ~0,5 GB)")
    else:
        print("  • Dosya kaydı KAPALI (--no-files)")
    if quickedit_off:
        print("  • Bu pencerede QuickEdit kapatıldı: pencereye tıklamak takibi DONDURMAZ (metin için console_*.txt kullanın)")
    if awake:
        print("  • UYKU ENGELİ AÇIK: takip açıkken bilgisayar boşta kalınca uyumaz (ekran kapanabilir, takip sürer).")
        print("      Güç ayarları değişmedi; takip kapanınca normale döner. Kapak kapatma / güç tuşu yine uyutur. Şarjı takılı tutun.")
    elif args.allow_sleep:
        print("  • Uyku engeli KAPALI (--allow-sleep): bilgisayar uyursa takip de durur.")
    else:
        print("  ⚠️ Uyku engeli ayarlanamadı: bilgisayar boşta uyursa takip durur.")
    print("  • HAZIR sütunu: F=Fatigue 300 bar rank · S=4 dış pivot · R=rejim 200 bar (✗ = o satırın değeri güvenilmez)")
    print("  Durdurmak için Ctrl+C tuşlarına basabilirsiniz.")
    print("=" * 78 + "\n")

    for sym in track_list:
        clean = sym.upper().replace('.P', '').replace('_', '')
        is_mexc = 'LONGXIA' in clean
        p = 'MEXC' if is_mexc else 'BINANCE'
        m = 'FUTURES'
        k = 'LONGXIA_USDT' if is_mexc else clean
        try:
            fetch_live_trades(p, m, k, max_pages=settings['max_pages'])
        except Exception:
            pass
    time.sleep(1)

    inter_coin_delay = settings['inter_coin_delay']
    cycle_delay = settings['cycle_delay']
    cycle_no = 0

    try:
        while True:
            try:
                cycle_no += 1
                cycle_start = time.time()
                errors = 0
                hint_shown = False
                for sym in track_list:
                    try:
                        run_single_tracking_cycle(sym, session)
                    except Exception as e:
                        errors += 1
                        session.cycle_errors += 1
                        print(f"  ⚠️ [{sym}] Döngü hatası: {type(e).__name__}: {e}")
                        hint = tv2.network_hint(e)
                        if hint and not hint_shown:
                            print(f"  👉 {hint}")
                            hint_shown = True
                        _flush_console()
                    if len(track_list) > 1:
                        time.sleep(inter_coin_delay)
                gaps = sum(p.gap_events for p in flow_manager.pools())
                print(f"  ⏱ TUR #{cycle_no} bitti: {len(track_list)} coin · {time.time() - cycle_start:.0f} sn · hata {errors} · "
                      f"ağırlık maks {tv2.RATE.max_used_weight_1m}/2400 · toplam boşluk olayı {gaps}"
                      + (f" · snapshot {writer.snapshots} · sonuç {writer.outcomes}" if writer else ''))
                if run is not None:
                    dropped = writer.dropped_bytes + sink.dropped_bytes
                    if dropped:
                        print(f"  🚨 Diske yazılamadığı için {dropped / 1e6:.1f} MB kayıt bellekten atıldı (disk dolu / dosya kilitli?)")
                    run.write_meta(last_cycle=cycle_no, snapshots=session.snapshots, outcomes=writer.outcomes,
                                   cycle_errors=session.cycle_errors, gap_events=gaps, write_failures=writer.write_failures,
                                   dropped_bytes=dropped, max_used_weight_1m=tv2.RATE.max_used_weight_1m,
                                   updated_at_ms=int(time.time() * 1000))
                _flush_console()
                time.sleep(cycle_delay)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Takip hatası: {e}")
                time.sleep(10)
    except KeyboardInterrupt:
        print("\nTakip kullanıcı tarafından durduruldu.")
    finally:
        if writer is not None:
            writer.flush()
            run.write_meta(stopped_at_ms=int(time.time() * 1000), snapshots=session.snapshots, outcomes=writer.outcomes,
                           cycle_errors=session.cycle_errors, write_failures=writer.write_failures)
            print(f"  💾 Kayıt: {run.run_dir} · {writer.snapshots} snapshot · {writer.outcomes} sonuç")
            if writer.write_failures:
                print(f"  ⚠️ {writer.write_failures} yazma denemesi başarısız oldu (OneDrive kilidi?) — veriler tamponda kaldıysa kaybolmuş olabilir.")
        if sink is not None:
            sink.flush()
        session.executor.shutdown(wait=False)
        if awake:
            keep_system_awake(False)
