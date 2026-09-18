import urllib.request
import json
import time
import math
import sys
import os
import csv
from datetime import datetime, timezone
from collections import deque

# Windows konsol UTF-8 ayarı
sys.stdout.reconfigure(encoding='utf-8')

SYMBOL_MEXC = 'LONGXIA_USDT'
SYMBOL_BYBIT = 'LONGXIAUSDT'

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
        url = 'https://fapi.binance.com/fapi/v1/exchangeInfo'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
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
# ═══════════════════════════════════════════════════════════════════════

class SymbolOrderFlow:
    def __init__(self, provider: str, market: str, symbol: str, max_trades=20000):
        self.provider = provider.upper()
        self.market = market.upper()
        self.symbol = symbol.upper()
        self.seen_trades = set()
        self.trades = deque(maxlen=max_trades)
        self.whale_trades = deque(maxlen=100)
        self.last_whale = None
        self.last_trade_price = 0.0
        self.integrity_errors = 0

    def ingest_trade(self, ts_ms: int, price: float, qty: float, is_buy: bool, trade_id: str, incoming_symbol: str, reference_price: float = 0.0):
        if incoming_symbol.upper() != self.symbol:
            self.integrity_errors += 1
            print(f"⚠️ [DATA INTEGRITY ERROR]: Sembol uyuşmazlığı reddedildi! Hedef={self.symbol}, Gelen={incoming_symbol}")
            return False

        if reference_price > 0.0:
            dev = abs(price - reference_price) / reference_price
            if dev > 0.40:
                self.integrity_errors += 1
                print(f"⚠️ [DATA INTEGRITY ERROR]: {self.symbol} için anormal fiyat reddedildi! Ref={reference_price}, Gelen={price}")
                return False

        if trade_id in self.seen_trades:
            return False
        self.seen_trades.add(trade_id)
        if len(self.seen_trades) > 50000:
            keep = set(list(self.seen_trades)[-10000:])
            self.seen_trades = keep

        usd = price * qty
        if price > 0 and qty > 0:
            self.trades.append((ts_ms, price, qty, usd, is_buy))
            self.last_trade_price = price

            wh_threshold = get_whale_threshold(self.symbol)

            if usd >= wh_threshold:
                wh_item = {
                    'time': datetime.fromtimestamp(ts_ms / 1000.0).strftime('%H:%M:%S'),
                    'symbol': self.symbol,
                    'price': price,
                    'usd': usd,
                    'side': 'BUY 🟢' if is_buy else 'SELL 🔴'
                }
                self.whale_trades.append(wh_item)
                self.last_whale = wh_item
            return True
        return False

    def get_window_stats(self, seconds=60):
        now_ms = int(time.time() * 1000)
        cutoff_ms = now_ms - (seconds * 1000)

        buy_usd = 0.0
        sell_usd = 0.0
        trade_count = 0
        min_ts = -1
        max_ts = -1

        for ts_ms, price, qty, usd, is_buy in self.trades:
            if ts_ms >= cutoff_ms:
                if is_buy:
                    buy_usd += usd
                else:
                    sell_usd += usd
                trade_count += 1
                if min_ts == -1 or ts_ms < min_ts:
                    min_ts = ts_ms
                if ts_ms > max_ts:
                    max_ts = ts_ms

        total_usd = buy_usd + sell_usd
        cvd_usd = buy_usd - sell_usd
        buy_ratio = (buy_usd / total_usd * 100.0) if total_usd > 0 else 50.0
        cvd_pct = (cvd_usd / total_usd * 100.0) if total_usd > 0 else 0.0

        score = 50.0 + 45.0 * math.tanh(cvd_pct / 22.0)
        score = max(0.0, min(100.0, score))

        if cvd_pct > 3.0:
            direction = "UP 🟢"
        elif cvd_pct < -3.0:
            direction = "DOWN 🔴"
        else:
            direction = "FLAT ⚪"

        window_coverage_sec = (max_ts - min_ts) / 1000.0 if trade_count > 1 else 0.0
        last_trade_age_ms = (now_ms - max_ts) if trade_count > 0 else (seconds * 1000.0)
        
        trade_count_factor = max(0.0, min(1.0, trade_count / 50.0))
        notional_factor = max(0.0, min(1.0, math.log10(total_usd + 1) / 5.0))
        freshness_factor = max(0.0, min(1.0, 1.0 - (last_trade_age_ms / 120000.0)))
        flow_confidence = min(100.0, math.sqrt(trade_count_factor * notional_factor * freshness_factor) * 100.0)

        return {
            'provider': self.provider,
            'market': self.market,
            'symbol': self.symbol,
            'buy_usd': buy_usd,
            'sell_usd': sell_usd,
            'total_usd': total_usd,
            'cvd_usd': cvd_usd,
            'buy_ratio': buy_ratio,
            'cvd_pct': cvd_pct,
            'score': round(score, 1),
            'direction': direction,
            'trade_count': trade_count,
            'total_notional': total_usd,
            'window_coverage_sec': window_coverage_sec,
            'last_trade_age_ms': last_trade_age_ms,
            'flow_confidence': flow_confidence,
            'last_whale': self.last_whale,
            'integrity_errors': self.integrity_errors
        }

class RealtimeOrderFlowManager:
    def __init__(self):
        self._flows = {}

    def _key(self, provider: str, market: str, symbol: str) -> tuple:
        return (provider.upper(), market.upper(), symbol.upper())

    def get_flow(self, provider: str, market: str, symbol: str) -> SymbolOrderFlow:
        key = self._key(provider, market, symbol)
        if key not in self._flows:
            self._flows[key] = SymbolOrderFlow(provider, market, symbol)
        return self._flows[key]

flow_manager = RealtimeOrderFlowManager()

# ═══════════════════════════════════════════════════════════════════════
# 2. VERİ ÇEKME FONKSİYONLARI (KLINES & TRADES - STRICT ISOLATION)
# ═══════════════════════════════════════════════════════════════════════

def fetch_candles_mexc(symbol=SYMBOL_MEXC, interval='Min1'):
    url = f"https://contract.mexc.com/api/v1/contract/kline/{symbol}?interval={interval}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        d = json.loads(resp.read().decode('utf-8'))
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

def fetch_candles_binance(symbol='SYNUSDT', interval='1m', limit=500):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = json.loads(resp.read().decode('utf-8'))
        return {
            'time': [int(k[0]) // 1000 for k in raw],
            'open': [float(k[1]) for k in raw],
            'high': [float(k[2]) for k in raw],
            'low': [float(k[3]) for k in raw],
            'close': [float(k[4]) for k in raw],
            'vol': [float(k[5]) for k in raw],
            'amount': [float(k[7]) for k in raw],
            'taker_buy': [float(k[10]) for k in raw]
        }

def fetch_live_trades(provider: str, market: str, symbol: str, reference_price: float = 0.0):
    clean_sym = symbol.upper().replace('.P', '').replace('_', '')
    flow = flow_manager.get_flow(provider, market, symbol)

    if provider.upper() == 'MEXC':
        try:
            url_m = f"https://contract.mexc.com/api/v1/contract/deals/{symbol}?limit=100"
            req_m = urllib.request.Request(url_m, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req_m, timeout=5) as r:
                deals = json.loads(r.read().decode('utf-8')).get('data', [])
                for d in deals:
                    tid = str(d.get('i', f"{d.get('t')}_{d.get('p')}_{d.get('v')}"))
                    flow.ingest_trade(
                        ts_ms=int(d.get('t', 0)),
                        price=float(d.get('p', 0)),
                        qty=float(d.get('v', 0)),
                        is_buy=(d.get('T') == 1),
                        trade_id=tid,
                        incoming_symbol=symbol,
                        reference_price=reference_price
                    )
        except Exception:
            pass
    else:
        try:
            url_bin = f"https://fapi.binance.com/fapi/v1/aggTrades?symbol={clean_sym}&limit=500"
            req_bin = urllib.request.Request(url_bin, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req_bin, timeout=5) as r:
                raw_t = json.loads(r.read().decode('utf-8'))
                for t in raw_t:
                    tid = str(t.get('a', f"{t.get('T')}_{t.get('p')}_{t.get('q')}"))
                    flow.ingest_trade(
                        ts_ms=int(t.get('T', 0)),
                        price=float(t.get('p', 0)),
                        qty=float(t.get('q', 0)),
                        is_buy=(not bool(t.get('m', False))),
                        trade_id=tid,
                        incoming_symbol=symbol,
                        reference_price=reference_price
                    )
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════════════════
# 3. İNDİKATÖR FORMÜLLERİ: ZPTDIFAT & REALF v4.2 & STRUCTURE v1.1
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

def calc_fatigue(candles, rank_win=300):
    closes = candles['close']
    n = len(closes)
    if n < 30:
        return {'fat': 50.0, 'state': 'WARMUP', 'abs': 50.0, 'rank': 50.0, 'bars': n}
    
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
    for i in range(start_r, n):
        x = abs_fat[i]
        win_sub = abs_fat[max(0, i-actual_win+1):i+1]
        less = sum(1 for v in win_sub if v < x)
        eq = sum(1 for v in win_sub if v == x)
        rank_fat[i] = (less + (eq + 1) / 2.0) / len(win_sub) * 100.0
        
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
        'bars': n
    }

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
            'beta': 0.0, 'beta_r2': 0.0, 'rvol': 1.0, 'percentile': 50.0, 'persistence': 50.0, 'net_pct': 0.0
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
        'net_pct': round(net_pct, 1)
    }

def calc_structure(candles, intLen=2, extLen=4, atrLen=14, intPromMin=0.35, extPromMin=0.80, eqTolAtr=0.12, breakBufferAtr=0.10, eventMemoryBars=40, adxLen=14, bbLen=20, regLookback=200):
    if 'open' not in candles or len(candles['close']) < max(atrLen, extLen * 2) + 10:
        return {'score': 50.0, 'state': 'WARMUP', 'event': 'NONE', 'ext_seq': 'WARMUP', 'regime': 'RANGE', 'conf': 0.0,
                'int_seq': 'WARMUP', 'event_age': 0, 'event_strength': 0.0, 'protected_level': 0.0, 'protected_type': 'NONE',
                'protected_distance_atr': 0.0, 'nearest_eqh': None, 'nearest_eql': None, 'eqh_distance_atr': None, 'eql_distance_atr': None,
                'last_liq_event': 'NONE', 'liq_event_age': 0, 'sweep_event': False}

    opens = candles['open']
    highs = candles['high']
    lows = candles['low']
    closes = candles['close']
    n = len(closes)

    def clamp(x, lo, hi): return max(lo, min(hi, x))

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
        
    atrPctRank = [50.0] * n
    for i in range(regLookback, n):
        win = atrp[i-regLookback:i]
        curr = atrp[i]
        less = sum(1 for x in win if x < curr)
        eq = sum(1 for x in win if x == curr)
        atrPctRank[i] = (less + 0.5 * eq) / regLookback * 100.0

    bbw = [0.0] * n
    for i in range(bbLen - 1, n):
        win = closes[i - bbLen + 1 : i + 1]
        basis = sum(win) / bbLen
        var = sum((x - basis)**2 for x in win) / bbLen
        dev = math.sqrt(var)
        upper = basis + 2.0 * dev
        lower = basis - 2.0 * dev
        bbw[i] = ((upper - lower) / basis * 100.0) if basis != 0 else 0.0
        
    bbwPctRank = [50.0] * n
    for i in range(regLookback, n):
        win = bbw[i-regLookback:i]
        curr = bbw[i]
        less = sum(1 for x in win if x < curr)
        eq = sum(1 for x in win if x == curr)
        bbwPctRank[i] = (less + 0.5 * eq) / regLookback * 100.0

    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    for i in range(1, n):
        up_move = highs[i] - highs[i-1]
        down_move = lows[i-1] - lows[i]
        if up_move > down_move and up_move > 0: plus_dm[i] = up_move
        if down_move > up_move and down_move > 0: minus_dm[i] = down_move
        
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
    adx_len = 14
    if n > adxLen * 2:
        adx[adxLen * 2 - 2] = sum(dx[adxLen-1 : adxLen*2-1]) / adx_len
        for i in range(adxLen * 2 - 1, n):
            adx[i] = (adx[i-1] * (adx_len - 1) + dx[i]) / adx_len

    def get_ph(idx, L, R):
        if idx - L < 0 or idx + R >= n: return False
        val = highs[idx]
        for i in range(idx - L, idx + R + 1):
            if i == idx: continue
            if highs[i] > val: return False
            if highs[i] == val and i > idx: return False
        return True

    def get_pl(idx, L, R):
        if idx - L < 0 or idx + R >= n: return False
        val = lows[idx]
        for i in range(idx - L, idx + R + 1):
            if i == idx: continue
            if lows[i] < val: return False
            if lows[i] == val and i > idx: return False
        return True

    extHigh0, extHigh1, extHighBar0, extHighBar1, extHighRel = None, None, None, None, 0
    extLow0, extLow1, extLowBar0, extLowBar1, extLowRel = None, None, None, None, 0
    extHighCount, extLowCount = 0, 0
    extHighProm, extLowProm = None, None
    
    intHigh0, intHigh1, intHighRel = None, None, 0
    intLow0, intLow1, intLowRel = None, None, 0

    persistence = 0.0
    structureState = 0
    lastEventType = 0
    lastEventDir = 0
    lastEventBar = None
    lastEventStrength = None

    protectedLowPrice, protectedLowBar = None, None
    protectedHighPrice, protectedHighBar = None, None
    brokenUpRefBar, brokenDownRefBar = None, None
    
    eqh_level = None
    eql_level = None
    last_liq_event = "NONE"
    liq_event_age = 0
    sweep_event = False

    for i in range(max(extLen, atrLen), n):
        pb = i - extLen
        pb_int = i - intLen
        atrP = atr[pb]
        atrP_int = atr[pb_int]

        # Internal
        if get_ph(pb_int, intLen, intLen):
            phInt = highs[pb_int]
            oppInt = intLow0
            promInt = abs(phInt - oppInt) / atrP_int if oppInt is not None and atrP_int > 0 else None
            if oppInt is None or (promInt is not None and promInt >= intPromMin):
                intHigh1 = intHigh0
                intHigh0 = phInt
                intHighRel = 1 if (intHigh1 is not None and phInt > intHigh1) else (-1 if (intHigh1 is not None and phInt < intHigh1) else 0)
        
        if get_pl(pb_int, intLen, intLen):
            plInt = lows[pb_int]
            oppInt = intHigh0
            promInt = abs(plInt - oppInt) / atrP_int if oppInt is not None and atrP_int > 0 else None
            if oppInt is None or (promInt is not None and promInt >= intPromMin):
                intLow1 = intLow0
                intLow0 = plInt
                intLowRel = 1 if (intLow1 is not None and plInt > intLow1) else (-1 if (intLow1 is not None and plInt < intLow1) else 0)

        # External
        if get_ph(pb, extLen, extLen):
            phExt = highs[pb]
            opp = extLow0 if extLow0 is not None and (extLowBar0 is not None and extLowBar0 < pb) else (extLow1 if extLow1 is not None and (extLowBar1 is not None and extLowBar1 < pb) else None)
            prom = abs(phExt - opp) / atrP if opp is not None and atrP > 0 else None
            bootstrap = (extHighCount == 0 or opp is None)
            
            if bootstrap or (prom is not None and prom >= extPromMin):
                oldHigh = extHigh0
                extHigh1 = extHigh0
                extHighBar1 = extHighBar0
                extHigh0 = phExt
                extHighBar0 = pb
                extHighProm = prom
                extHighCount += 1
                
                moveDir = 0
                if oldHigh is not None:
                    if phExt > oldHigh + atrP * eqTolAtr: moveDir = 1
                    elif phExt < oldHigh - atrP * eqTolAtr: moveDir = -1
                    else:
                        eqh_level = max(phExt, oldHigh)
                
                extHighRel = moveDir
                persistence = clamp(persistence * 0.70 + moveDir * 0.30, -1.0, 1.0)
                
                if eqh_level and phExt > eqh_level + atrP * breakBufferAtr:
                    last_liq_event = "HIGH_SWEEP"
                    liq_event_age = 0
                    sweep_event = True
                    eqh_level = None

        if get_pl(pb, extLen, extLen):
            plExt = lows[pb]
            opp = extHigh0 if extHigh0 is not None and (extHighBar0 is not None and extHighBar0 < pb) else (extHigh1 if extHigh1 is not None and (extHighBar1 is not None and extHighBar1 < pb) else None)
            prom = abs(plExt - opp) / atrP if opp is not None and atrP > 0 else None
            bootstrap = (extLowCount == 0 or opp is None)
            
            if bootstrap or (prom is not None and prom >= extPromMin):
                oldLow = extLow0
                extLow1 = extLow0
                extLowBar1 = extLowBar0
                extLow0 = plExt
                extLowBar0 = pb
                extLowProm = prom
                extLowCount += 1
                
                moveDir = 0
                if oldLow is not None:
                    if plExt > oldLow + atrP * eqTolAtr: moveDir = 1
                    elif plExt < oldLow - atrP * eqTolAtr: moveDir = -1
                    else:
                        eql_level = min(plExt, oldLow)
                
                extLowRel = moveDir
                persistence = clamp(persistence * 0.70 + moveDir * 0.30, -1.0, 1.0)
                
                if eql_level and plExt < eql_level - atrP * breakBufferAtr:
                    last_liq_event = "LOW_SWEEP"
                    liq_event_age = 0
                    sweep_event = True
                    eql_level = None

        extReady = (extHigh0 is not None and extHigh1 is not None and extLow0 is not None and extLow1 is not None)
        seqBull = extReady and extHighRel == 1 and extLowRel == 1
        seqBear = extReady and extHighRel == -1 and extLowRel == -1
        partialBull = not seqBull and not seqBear and (extHighRel == 1 or extLowRel == 1)
        partialBear = not seqBull and not seqBear and (extHighRel == -1 or extLowRel == -1)
        
        if extReady and structureState == 0:
            if seqBull:
                structureState = 2
                protectedLowPrice = extLow0
                protectedLowBar = extLowBar0
            elif seqBear:
                structureState = -2
                protectedHighPrice = extHigh0
                protectedHighBar = extHighBar0
            else:
                structureState = 1 if partialBull else (-1 if partialBear else 0)

        upBreakLevel = protectedHighPrice if structureState == -2 and protectedHighPrice is not None else extHigh0
        upBreakRefBar = protectedHighBar if structureState == -2 and protectedHighBar is not None else extHighBar0
        downBreakLevel = protectedLowPrice if structureState == 2 and protectedLowPrice is not None else extLow0
        downBreakRefBar = protectedLowBar if structureState == 2 and protectedLowBar is not None else extLowBar0
        
        atrNow = atr[i]
        buf = atrNow * breakBufferAtr
        
        breakHighNow = upBreakLevel is not None and closes[i] > upBreakLevel + buf and closes[i-1] <= upBreakLevel + buf
        breakLowNow = downBreakLevel is not None and closes[i] < downBreakLevel - buf and closes[i-1] >= downBreakLevel - buf
        
        def break_strength(lvl, dir_):
            rng = max(highs[i] - lows[i], 1e-8)
            bodyQ = abs(closes[i] - opens[i]) / rng
            closeLoc = (closes[i] - lows[i]) / rng if dir_ > 0 else (highs[i] - closes[i]) / rng
            disp = abs(closes[i] - lvl) / atrNow if atrNow > 0 else 0.0
            dispQ = clamp(disp / 1.50, 0.0, 1.0)
            return clamp(100.0 * (0.45 * dispQ + 0.30 * bodyQ + 0.25 * closeLoc), 0.0, 100.0)
        
        if breakHighNow and (brokenUpRefBar is None or brokenUpRefBar != upBreakRefBar):
            bs = break_strength(upBreakLevel, 1)
            if structureState == -2:
                structureState = 1
                lastEventType = 2
                protectedLowPrice = extLow0
                protectedLowBar = extLowBar0
            else:
                structureState = 2
                lastEventType = 1
                protectedLowPrice = extLow0
                protectedLowBar = extLowBar0
                protectedHighPrice = None
                protectedHighBar = None
            lastEventDir = 1
            lastEventBar = i
            lastEventStrength = bs
            brokenUpRefBar = upBreakRefBar

        if breakLowNow and (brokenDownRefBar is None or brokenDownRefBar != downBreakRefBar):
            bs = break_strength(downBreakLevel, -1)
            if structureState == 2:
                structureState = -1
                lastEventType = 2
                protectedHighPrice = extHigh0
                protectedHighBar = extHighBar0
            else:
                structureState = -2
                lastEventType = 1
                protectedHighPrice = extHigh0
                protectedHighBar = extHighBar0
                protectedLowPrice = None
                protectedLowBar = None
            lastEventDir = -1
            lastEventBar = i
            lastEventStrength = bs
            brokenDownRefBar = downBreakRefBar

        liq_event_age += 1
        sweep_event = False

    extReady = (extHigh0 is not None and extHigh1 is not None and extLow0 is not None and extLow1 is not None)
    seqBull = extReady and extHighRel == 1 and extLowRel == 1
    seqBear = extReady and extHighRel == -1 and extLowRel == -1
    partialBull = not seqBull and not seqBear and (extHighRel == 1 or extLowRel == 1)
    partialBear = not seqBull and not seqBear and (extHighRel == -1 or extLowRel == -1)

    intSeqBull = (intHighRel == 1 and intLowRel == 1)
    intSeqBear = (intHighRel == -1 and intLowRel == -1)
    intSeqText = 'HH/HL' if intSeqBull else ('LH/LL' if intSeqBear else ('HH/MIX' if intHighRel==1 else ('MIX/HL' if intLowRel==1 else ('LH/MIX' if intHighRel==-1 else ('MIX/LL' if intLowRel==-1 else 'EQ/RANGE')))))
    if intHigh0 is None or intLow0 is None:
        intSeqText = 'WARMUP'

    swingComp = 20.0 if seqBull else (-20.0 if seqBear else (8.0 if partialBull else (-8.0 if partialBear else 0.0)))
    eventAge = (n - 1) - lastEventBar if lastEventBar is not None else 99999
    eventDecay = clamp(1.0 - eventAge / eventMemoryBars, 0.0, 1.0) if lastEventBar is not None else 0.0
    eventBase = 15.0 if lastEventType == 1 else (10.0 if lastEventType == 2 else 0.0)
    eventComp = lastEventDir * eventBase * eventDecay
    breakQualityNorm = clamp((lastEventStrength - 30.0) / 70.0, 0.0, 1.0) if lastEventStrength is not None else 0.0
    breakComp = lastEventDir * 10.0 * breakQualityNorm * eventDecay
    persistenceComp = persistence * 5.0
    structureScore = clamp(50.0 + swingComp + eventComp + breakComp + persistenceComp, 0.0, 100.0)
    
    pivotConf = 25.0 if extReady else (14.0 if (extHighCount >= 2 or extLowCount >= 2) else 5.0)
    promHighSafe = extHighProm if extHighProm is not None else extPromMin
    promLowSafe = extLowProm if extLowProm is not None else extPromMin
    promAvgRaw = (promHighSafe + promLowSafe) / 2.0
    promConf = 25.0 * clamp(promAvgRaw / max(extPromMin * 2.5, 0.01), 0.0, 1.0)
    seqConf = 25.0 if (seqBull or seqBear) else (16.0 if (partialBull or partialBear) else (10.0 if extReady else 5.0))
    dynamicConf = 15.0 * abs(persistence) + 10.0 * ((lastEventStrength / 100.0) if lastEventStrength is not None and eventAge <= eventMemoryBars else 0.0)
    confidence = clamp(pivotConf + promConf + seqConf + dynamicConf, 0.0, 100.0)
    
    extSeqText = 'WARMUP' if not extReady else ('HH/HL' if seqBull else ('LH/LL' if seqBear else ('HH/MIX' if extHighRel==1 else ('MIX/HL' if extLowRel==1 else ('LH/MIX' if extHighRel==-1 else ('MIX/LL' if extLowRel==-1 else 'EQ/RANGE'))))))

    def get_state_short(s): return 'BULL' if s == 2 else ('TR-UP' if s == 1 else ('TR-DN' if s == -1 else ('BEAR' if s == -2 else 'RANGE')))
    def get_event_name(t, d): return 'BOS UP' if t == 1 and d == 1 else ('BOS DN' if t == 1 and d == -1 else ('CHOCH UP' if t == 2 and d == 1 else ('CHOCH DN' if t == 2 and d == -1 else 'NONE')))

    squeeze = atrPctRank[-1] <= 20.0 and bbwPctRank[-1] <= 20.0
    recentBullBreak = lastEventType == 1 and lastEventDir == 1 and eventAge <= 10
    recentBearBreak = lastEventType == 1 and lastEventDir == -1 and eventAge <= 10
    expansionUp = atrPctRank[-1] >= 70.0 and bbwPctRank[-1] >= 60.0 and recentBullBreak
    expansionDown = atrPctRank[-1] >= 70.0 and bbwPctRank[-1] >= 60.0 and recentBearBreak
    chaotic = atrPctRank[-1] >= 90.0 and confidence < 45.0
    
    if squeeze: regime = 'SQZ'
    elif expansionUp: regime = 'EXP UP'
    elif expansionDown: regime = 'EXP DN'
    elif chaotic: regime = 'CHAOS'
    elif structureState == 1: regime = 'TR-UP'
    elif structureState == -1: regime = 'TR-DN'
    elif structureState == 2 and adx[-1] >= 22.0: regime = 'TR UP'
    elif structureState == -2 and adx[-1] >= 22.0: regime = 'TR DN'
    else: regime = 'RANGE'
    
    currC = closes[-1]
    currAtr = atr[-1] if atr[-1] > 0 else 1.0
    protectedLvl = protectedHighPrice if structureState in (-1, -2) else protectedLowPrice
    protectedType = 'HIGH' if structureState in (-1, -2) else ('LOW' if structureState in (1, 2) else 'NONE')
    protectedDist = abs(currC - protectedLvl)/currAtr if protectedLvl else 0.0

    eqhDist = abs(currC - eqh_level)/currAtr if eqh_level else None
    eqlDist = abs(currC - eql_level)/currAtr if eql_level else None

    return {
        'score': round(structureScore, 1),
        'state': get_state_short(structureState),
        'event': get_event_name(lastEventType, lastEventDir),
        'ext_seq': extSeqText,
        'regime': regime,
        'conf': round(confidence, 1),
        'int_seq': intSeqText,
        'event_age': eventAge,
        'event_strength': round(lastEventStrength if lastEventStrength else 0, 1),
        'protected_level': protectedLvl,
        'protected_type': protectedType,
        'protected_distance_atr': round(protectedDist, 2),
        'nearest_eqh': eqh_level,
        'nearest_eql': eql_level,
        'eqh_distance_atr': round(eqhDist, 2) if eqhDist is not None else None,
        'eql_distance_atr': round(eqlDist, 2) if eqlDist is not None else None,
        'last_liq_event': last_liq_event,
        'liq_event_age': liq_event_age,
        'sweep_event': sweep_event
    }

def get_recent_minute_history(candles, limit=6):
    closes = candles['close']
    opens = candles['open']
    highs = candles['high']
    lows = candles['low']
    amounts = candles['amount']
    times = candles['time']
    taker_buys = candles.get('taker_buy', None)
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
            'time': t_str, 'close': c, 'chg': chg,
            'tot': tot, 'tb': tb, 'ts': ts, 'cvd': cvd, 'cvd_pct': cvd_pct,
            'fat': f_info['fat'], 'fat_st': f_info['state'],
            'realf': r_info['score']
        })
    return rows

# ═══════════════════════════════════════════════════════════════════════
# DELTAS & HISTORY (v2 Entegreleri)
# ═══════════════════════════════════════════════════════════════════════

class SnapshotHistory:
    def __init__(self):
        self.buffers = {}

    def push(self, symbol, snapshot):
        if symbol not in self.buffers:
            self.buffers[symbol] = deque(maxlen=10)
        self.buffers[symbol].append(snapshot)

    def get_history(self, symbol):
        if symbol not in self.buffers:
            return []
        return list(self.buffers[symbol])

history_mgr = SnapshotHistory()

def compute_deltas(symbol, curr_snap):
    hist = history_mgr.get_history(symbol)
    if not hist:
        return {}
    
    def get_ago(h_list, k, fallback=0.0):
        if len(h_list) > k:
            return h_list[-(k+1)]
        elif len(h_list) > 0:
            return h_list[0]
        return fallback

    d = {}
    r_hist = [h['realf_score'] for h in hist]
    d['realf_now'] = curr_snap['realf_score']
    d['realf_1m_ago'] = get_ago(r_hist, 1, d['realf_now'])
    d['realf_3m_ago'] = get_ago(r_hist, 3, d['realf_now'])
    d['realf_5m_ago'] = get_ago(r_hist, 5, d['realf_now'])
    d['realf_d1'] = d['realf_now'] - d['realf_1m_ago']
    d['realf_d3'] = d['realf_now'] - d['realf_3m_ago']
    d['realf_d5'] = d['realf_now'] - d['realf_5m_ago']

    u_hist = [h['realf_inventory'] for h in hist]
    d['unpriced_now'] = curr_snap['realf_inventory']
    d['unpriced_d1'] = d['unpriced_now'] - get_ago(u_hist, 1, d['unpriced_now'])
    d['unpriced_d3'] = d['unpriced_now'] - get_ago(u_hist, 3, d['unpriced_now'])
    d['unpriced_d5'] = d['unpriced_now'] - get_ago(u_hist, 5, d['unpriced_now'])

    f_hist = [h['fatigue_score'] for h in hist]
    d['fatigue_now'] = curr_snap['fatigue_score']
    d['fatigue_1m_ago'] = get_ago(f_hist, 1, d['fatigue_now'])
    d['fatigue_3m_ago'] = get_ago(f_hist, 3, d['fatigue_now'])
    d['fatigue_5m_ago'] = get_ago(f_hist, 5, d['fatigue_now'])
    d['fatigue_d1'] = d['fatigue_now'] - d['fatigue_1m_ago']
    d['fatigue_d3'] = d['fatigue_now'] - d['fatigue_3m_ago']
    d['fatigue_d5'] = d['fatigue_now'] - d['fatigue_5m_ago']

    cvd_hist_1m = [h['cvd_1m_usd'] for h in hist]
    d['cvd_1m_delta'] = curr_snap['cvd_1m_usd'] - get_ago(cvd_hist_1m, 1, curr_snap['cvd_1m_usd'])
    d['cvd_5m_delta'] = curr_snap['cvd_5m_usd'] - get_ago([h['cvd_5m_usd'] for h in hist], 1, curr_snap['cvd_5m_usd'])
    d['cvd_15m_delta'] = curr_snap['cvd_15m_usd'] - get_ago([h['cvd_15m_usd'] for h in hist], 1, curr_snap['cvd_15m_usd'])

    d['buyer_ratio_delta_1m'] = curr_snap['cvd_1m_buy_ratio'] - get_ago([h['cvd_1m_buy_ratio'] for h in hist], 1, curr_snap['cvd_1m_buy_ratio'])
    d['buyer_ratio_delta_5m'] = curr_snap['cvd_5m_buy_ratio'] - get_ago([h['cvd_5m_buy_ratio'] for h in hist], 1, curr_snap['cvd_5m_buy_ratio'])

    c_s = []
    for h in (hist + [curr_snap])[-5:]:
        c_s.append(h['cvd_1m_usd'])
    def slope(arr):
        n = len(arr)
        if n < 2: return 0.0
        x_m = sum(range(n))/n
        y_m = sum(arr)/n
        num = sum((i-x_m)*(arr[i]-y_m) for i in range(n))
        den = sum((i-x_m)**2 for i in range(n))
        return num/den if den != 0 else 0.0
    d['cvd_slope_3m'] = slope(c_s[-3:]) if len(c_s) >= 3 else 0.0
    d['cvd_slope_5m'] = slope(c_s)

    return d

class OutcomeEvaluator:
    def __init__(self):
        self.pending = []
        self.logs_dir = "logs"
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)

    def record_snapshot(self, snapshot_id, symbol, price, timestamp_ms):
        self.pending.append({
            'snapshot_id': snapshot_id,
            'symbol': symbol,
            'entry_price': price,
            'entry_time_ms': timestamp_ms,
            'evaluated': False
        })

    def evaluate(self, candles_dict, current_time_ms):
        sym_candles = {}
        # Fetching price history directly from provided candles_dict could be mapped, but we just use the latest candles for the current symbol cycle
        pass

    def evaluate_with_candles(self, symbol, candles):
        now_ms = int(time.time() * 1000)
        times = candles['time']
        highs = candles['high']
        lows = candles['low']
        closes = candles['close']
        
        evaluated_any = False
        outcomes_file = os.path.join(self.logs_dir, f"outcomes_{datetime.now().strftime('%Y%m%d')}.jsonl")
        
        for p in self.pending:
            if p['symbol'] != symbol or p['evaluated']:
                continue
            age_ms = now_ms - p['entry_time_ms']
            if age_ms >= 60 * 60 * 1000: # 60m passed, evaluate all
                start_ts = p['entry_time_ms'] / 1000.0
                entry_idx = -1
                for i in range(len(times)):
                    if times[i] >= start_ts:
                        entry_idx = i
                        break
                
                if entry_idx != -1:
                    def get_fwd(m):
                        idx = entry_idx + m
                        if idx < len(times):
                            return (closes[idx] - p['entry_price']) / p['entry_price'] * 100.0
                        return None
                    
                    def get_mfe_mae(m):
                        end_idx = min(len(times), entry_idx + m + 1)
                        if end_idx > entry_idx:
                            mh = max(highs[entry_idx:end_idx])
                            ml = min(lows[entry_idx:end_idx])
                            mfe = (mh - p['entry_price']) / p['entry_price'] * 100.0
                            mae = (ml - p['entry_price']) / p['entry_price'] * 100.0
                            return mfe, mae
                        return None, None

                    res = {'snapshot_id': p['snapshot_id'], 'symbol': symbol, 'entry_price': p['entry_price']}
                    res['fwd_ret_1m'] = get_fwd(1)
                    res['fwd_ret_3m'] = get_fwd(3)
                    res['fwd_ret_5m'] = get_fwd(5)
                    res['fwd_ret_10m'] = get_fwd(10)
                    res['fwd_ret_20m'] = get_fwd(20)
                    res['fwd_ret_30m'] = get_fwd(30)
                    res['fwd_ret_60m'] = get_fwd(60)

                    mfe5, mae5 = get_mfe_mae(5)
                    mfe10, mae10 = get_mfe_mae(10)
                    mfe20, mae20 = get_mfe_mae(20)
                    res['mfe_5m'], res['mae_5m'] = mfe5, mae5
                    res['mfe_10m'], res['mae_10m'] = mfe10, mae10
                    res['mfe_20m'], res['mae_20m'] = mfe20, mae20
                    
                    p['evaluated'] = True
                    evaluated_any = True
                    
                    with open(outcomes_file, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(res) + '\n')
                        
        self.pending = [p for p in self.pending if not p['evaluated']]

evaluator = OutcomeEvaluator()

def write_snapshot_files(snapshot):
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    dt_str = datetime.now().strftime('%Y%m%d')
    
    j_file = os.path.join(logs_dir, f"snapshots_{dt_str}.jsonl")
    with open(j_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(snapshot) + '\n')
        
    c_file = os.path.join(logs_dir, f"snapshots_{dt_str}.csv")
    file_exists = os.path.exists(c_file)
    with open(c_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(snapshot.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(snapshot)

# ═══════════════════════════════════════════════════════════════════════
# 4. CANLI DASHBOARD & ALARM YAZDIRMA
# ═══════════════════════════════════════════════════════════════════════

def print_live_dashboard(candles_1m, provider: str = 'BINANCE', market: str = 'FUTURES', symbol_key: str = 'SYNUSDT', display_sym: str = ''):
    if not display_sym:
        display_sym = f"{symbol_key}.P ({provider})"
    
    now_ms = int(time.time() * 1000)
    curr_c = candles_1m['close'][-1]
    prev_c = candles_1m['close'][-2] if len(candles_1m['close']) > 1 else curr_c
    chg_1m = ((curr_c - prev_c) / prev_c) * 100.0 if prev_c else 0.0
    last_ts = candles_1m['time'][-1]
    curr_time = datetime.fromtimestamp(last_ts).strftime('%Y-%m-%d %H:%M:%S')

    dt = datetime.now()
    ms3 = f"{dt.microsecond // 1000:03d}"
    snapshot_id = f"{symbol_key}_{dt.strftime('%Y%m%d_%H%M%S')}_{ms3}"
    
    bar_open_time = last_ts * 1000
    bar_close_time = (last_ts + 60) * 1000 - 1
    is_bar_closed = now_ms >= bar_close_time

    flow = flow_manager.get_flow(provider, market, symbol_key)
    if flow.last_trade_price > 0 and curr_c > 0:
        runtime_dev = abs(flow.last_trade_price - curr_c) / curr_c
        if runtime_dev > 0.30:
            print(f"    🚨 [KRİTİK] {symbol_key} flow havuzu kontamine! Son trade fiyatı: {flow.last_trade_price:.6f}, Beklenen: {curr_c:.6f} — HAVUZ SIFIRLANACAK!")
            flow.trades.clear()
            flow.whale_trades.clear()
            flow.last_whale = None
            flow.last_trade_price = 0.0
            flow.seen_trades.clear()

    cvd_1m = flow.get_window_stats(60)
    cvd_5m = flow.get_window_stats(300)
    cvd_15m = flow.get_window_stats(900)

    history_rows = get_recent_minute_history(candles_1m, limit=6)

    tfs = [('1m', 1), ('3m', 3), ('5m', 5), ('15m', 15), ('1h', 60), ('4h', 240)]
    mtf_fat = {}
    mtf_str = {}
    for label, m in tfs:
        c_tf = resample_candles(candles_1m, m)
        mtf_fat[label] = calc_fatigue(c_tf)
        mtf_str[label] = calc_structure(c_tf)
        
    realf = calc_realf(candles_1m)

    # Core Snapshot Dict
    snap = {
        'snapshot_id': snapshot_id,
        'captured_at_ms': now_ms,
        'bar_open_time': bar_open_time,
        'bar_close_time': bar_close_time,
        'is_bar_closed': is_bar_closed,
        'REALF_VERSION': "v4.2",
        'FATIGUE_VERSION': "ZPTDIFAT-v1",
        'STRUCTURE_VERSION': "v1.1",
        'symbol': symbol_key,
        'price': curr_c,
        'realf_score': realf['score'],
        'realf_inventory': realf['inventory'],
        'fatigue_score': mtf_fat['1m']['fat'],
        'cvd_1m_usd': cvd_1m['cvd_usd'],
        'cvd_5m_usd': cvd_5m['cvd_usd'],
        'cvd_15m_usd': cvd_15m['cvd_usd'],
        'cvd_1m_buy_ratio': cvd_1m['buy_ratio'],
        'cvd_5m_buy_ratio': cvd_5m['buy_ratio'],
        '1m_trade_count': cvd_1m['trade_count'],
        '1m_total_notional': cvd_1m['total_notional'],
        '1m_window_coverage_sec': cvd_1m['window_coverage_sec'],
        '1m_last_trade_age_ms': cvd_1m['last_trade_age_ms'],
        '1m_flow_confidence': cvd_1m['flow_confidence'],
        '5m_flow_confidence': cvd_5m['flow_confidence'],
        '15m_flow_confidence': cvd_15m['flow_confidence']
    }
    
    # Merge structure fields (from 1m)
    s1 = mtf_str['1m']
    snap.update({
        'int_seq': s1['int_seq'],
        'event_age': s1['event_age'],
        'event_strength': s1['event_strength'],
        'protected_level': s1['protected_level'],
        'protected_type': s1['protected_type'],
        'protected_distance_atr': s1['protected_distance_atr'],
        'nearest_eqh': s1['nearest_eqh'],
        'nearest_eql': s1['nearest_eql'],
        'eqh_distance_atr': s1['eqh_distance_atr'],
        'eql_distance_atr': s1['eql_distance_atr'],
        'last_liq_event': s1['last_liq_event'],
        'liq_event_age': s1['liq_event_age'],
        'sweep_event': s1['sweep_event']
    })

    deltas = compute_deltas(symbol_key, snap)
    snap.update(deltas)
    
    history_mgr.push(symbol_key, snap)
    write_snapshot_files(snap)
    evaluator.record_snapshot(snapshot_id, symbol_key, curr_c, now_ms)
    evaluator.evaluate_with_candles(symbol_key, candles_1m)

    coin_info = get_coin_info(symbol_key)
    class_tag = coin_info['class']
    rank_tag = f"#{coin_info['rank']}" if coin_info['rank'] > 0 else ""
    border = "=" * 78
    sub_border = "-" * 78
    print("\n" + border)
    print(f"  🔴 CANLI TAKİP: {display_sym} | {curr_time} | [{class_tag}] {rank_tag}")
    print(f"  FİYAT: {curr_c:.6f}  |  1m DEĞİŞİM: {chg_1m:+.2f}%  |  RVOL: {realf['rvol']}x")
    print(border)
    
    print("  [1] GERÇEK ALIM-SATIM & CVD AKIŞI (Taker Order-Flow):")
    print(f"    • DOĞRULAMA         : FLOW SOURCE: {provider} / {symbol_key} / {market}")
    print(f"    • PENCERE & EŞLEŞME : FLOW WINDOW: 1m | LAST TRADE SYMBOL: {symbol_key}")
    print(f"    • İZOLE HAVUZ       : {len(flow.trades)} trade | Son fiyat: {flow.last_trade_price:.6f} | Hata: {flow.integrity_errors}")
    if cvd_1m['integrity_errors'] > 0:
        print(f"    ⚠️ [VERİ İHLALİ KORUMASI]: {cvd_1m['integrity_errors']} adet yabancı/hatalı trade engellendi!")
    print(f"    • 1 Dakikalık Akış  : Alış: ${cvd_1m['buy_usd']:,.1f} | Satış: ${cvd_1m['sell_usd']:,.1f} ({cvd_1m['trade_count']} İşlem)")
    print(f"      Net CVD           : ${cvd_1m['cvd_usd']:+,.1f} ({cvd_1m['direction']}) | Alıcı Oranı: %{cvd_1m['buy_ratio']:.1f}")
    print(f"      Project Z Skoru   : {cvd_1m['score']:.1f} / 100")
    
    print(f"    • 5 Dakikalık Akış  : Net CVD: ${cvd_5m['cvd_usd']:+,.1f} | Alıcı: %{cvd_5m['buy_ratio']:.1f} | CVD: {cvd_5m['direction']}")
    print(f"    • 15 Dakikalık Akış : Net CVD: ${cvd_15m['cvd_usd']:+,.1f} | Alıcı: %{cvd_15m['buy_ratio']:.1f}")
    
    div_text = None
    if chg_1m < -0.3 and cvd_1m['cvd_pct'] > 5.0:
        div_text = "🔥 BOĞA UYUMSUZLUĞU (Bullish CVD Divergence): Fiyat düşüyor ama akıllı para ALIYOR!"
    elif chg_1m > 0.3 and cvd_1m['cvd_pct'] < -5.0:
        div_text = "🔥 AYI UYUMSUZLUĞU (Bearish CVD Divergence): Fiyat yükseliyor ama akıllı para SATIYOR!"
    if div_text:
        print(f"    ⭐ {div_text}")

    print(sub_border)

    print("  [2] DAKİKALIK BİRİKİM & İNDİKATÖR GEÇMİŞİ (Son 6 Mum):")
    print("    SAAT  | FİYAT    | 1m BAR% | ALICI $  | SATICI $ | NET CVD $ | FATIGUE | DURUM   | REALF")
    for r in history_rows:
        fat_tag = "🔴" if r['fat_st'] == "ASIRI" else "🟠" if r['fat_st'] == "YORGUN" else "🟢"
        print(f"    {r['time']} | {r['close']:.6f} | {r['chg']:+6.2f}% | ${r['tb']:7,.0f} | ${r['ts']:7,.0f} | ${r['cvd']:+8,.0f} | {r['fat']:5.1f} {fat_tag} | {r['fat_st']:7s} | {r['realf']:5.1f}")

    print(sub_border)

    print("  [3] ZPTDIFAT (Yorgunluk) & STRUCTURE v1.1 (MTF Matrisi):")
    print("    TF  | FATIGUE  | DURUM      || STR SCORE | STR DURUM | STR EVENT | REGIME     | CONF | INT_SEQ | EV_AGE | PROT_LVL")
    for label, _ in tfs:
        f_info = mtf_fat[label]
        s_info = mtf_str[label]
        color_tag = "🔴" if f_info['state'] == "ASIRI" else "🟠" if f_info['state'] == "YORGUN" else "🟢" if f_info['state'] == "NORMAL" else "🔵"
        st_tag = "🟢" if "BULL" in s_info['state'] or "UP" in s_info['state'] else ("🔴" if "BEAR" in s_info['state'] or "DN" in s_info['state'] else "⚪")
        p_lvl = f"{s_info['protected_level']:.4f}" if s_info['protected_level'] else "NONE"
        print(f"    {label:>3s} | {f_info['fat']:>8.1f} | {color_tag} {f_info['state']:<8s} || {s_info['score']:>9.1f} | {st_tag} {s_info['state']:<7s} | {s_info['event']:<9s} | {s_info['regime']:<10s} | {s_info['conf']:.1f} | {s_info['int_seq']:<7s} | {s_info['event_age']:<6} | {p_lvl}")

    print(sub_border)

    print("  [4] REALF v4.2 (Fiyat & Akış Değerleme Dengesi & 12 Tanı Metriği):")
    r_tag = "⚠️" if "AHEAD" in realf['state'] or "LAG" in realf['state'] else "⚖️"
    print(f"    • GENEL SKOR      : {realf['score']} / 100 ({r_tag} {realf['state']})")
    print(f"    • 4 BİLEŞEN       : Impact: {realf['impact_score']:.1f} | Memory: {realf['memory_score']:.1f} | Momentum: {realf['momentum_score']:.1f} | Activity: {realf['activity_score']:.1f}")
    print(f"    • UNPRICED FLOW   : RemainingUnpricedFlow: {realf['inventory']:+.5f} log units")
    print(f"    • FAST IMPULSE    : FastPrice: {realf['fast_price']:+.2f} | FastFlow: {realf['fast_flow']:+.2f}")
    print(f"    • REGRESYON MODEL : Beta: {realf['beta']:.5f} | Beta R²: {realf['beta_r2']:.3f}")
    print(f"    • HACİM & AKIŞ    : Dollar RVOL: {realf['rvol']:.2f}x | Volume Percentile: %{realf['percentile']:.1f} | Persistence: %{realf['persistence']:.1f}")
    print(f"    • WHALE DURUMU    : {realf['whale']} (Son 20 Bar İmzalı Hacim Net: {realf['net_pct']:+0.1f}%)")
    
    lw = cvd_1m.get('last_whale')
    if lw and lw.get('symbol') == symbol_key.upper():
        print(f"    • SON BÜYÜK EMİR  : [{lw['time']}] {lw['side']} ${lw['usd']:,.0f} @ {lw['price']:.6f} ({lw['symbol']})")

    print(sub_border)

    print("  [6] DELTA TRACKER:")
    if deltas:
        print(f"    • REALF Delta  : {deltas.get('realf_5m_ago', 0):.1f} → {deltas.get('realf_3m_ago', 0):.1f} → {deltas.get('realf_1m_ago', 0):.1f} → {deltas.get('realf_now', 0):.1f} (Δ {deltas.get('realf_d5', 0):+.1f})")
        print(f"    • Fatigue Delta: {deltas.get('fatigue_5m_ago', 0):.1f} → {deltas.get('fatigue_3m_ago', 0):.1f} → {deltas.get('fatigue_1m_ago', 0):.1f} → {deltas.get('fatigue_now', 0):.1f} (Δ {deltas.get('fatigue_d5', 0):+.1f})")
        print(f"    • CVD Slope    : 3m={deltas.get('cvd_slope_3m', 0):+.1f} | 5m={deltas.get('cvd_slope_5m', 0):+.1f}")
    else:
        print("    • Yeterli geçmiş bekleniyor...")

    print(sub_border)
    
    print("  [7] FLOW CONFIDENCE:")
    print(f"    • 1m Window : Conf={cvd_1m['flow_confidence']:.1f}% | Trades={cvd_1m['trade_count']} | Notional=${cvd_1m['total_notional']:,.0f}")
    print(f"    • 5m Window : Conf={cvd_5m['flow_confidence']:.1f}% | Trades={cvd_5m['trade_count']} | Notional=${cvd_5m['total_notional']:,.0f}")
    print(f"    • 15m Window: Conf={cvd_15m['flow_confidence']:.1f}% | Trades={cvd_15m['trade_count']} | Notional=${cvd_15m['total_notional']:,.0f}")

    print(sub_border)

    alerts = []
    if div_text:
        alerts.append(div_text)
    if mtf_fat['1m']['state'] == 'ASIRI' or mtf_fat['5m']['state'] == 'ASIRI' or mtf_fat['15m']['state'] == 'ASIRI':
        alerts.append("🚨 [AŞIRI YORGUNLUK]: Üst periyotlarda FAT > 83 tepe/tükeniş alarmı!")
    if mtf_fat['1m']['state'] == 'DINLENMIS':
        alerts.append("💡 [1m DİNLENMİŞ]: 1 dakikalık yorgunluk tamamen sıfırlandı.")
    if realf['score'] < 30.0:
        alerts.append("🔵 [PRICE LAG]: Fiyat akışın çok gerisinde (Akümülasyon / Patlama potansiyeli)!")
    elif realf['score'] > 70.0:
        alerts.append("🔴 [PRICE AHEAD]: Fiyat hacmin çok önüne geçti (Düzeltme riski)!")
    if cvd_1m['buy_ratio'] >= 70.0 and cvd_1m['total_usd'] > 2000.0:
        alerts.append("🟢 [AGRESİF ALICI]: 1 dakikalık işlemlerde %70+ ezici Taker Alıcı baskısı!")
    elif cvd_1m['buy_ratio'] <= 30.0 and cvd_1m['total_usd'] > 2000.0:
        alerts.append("🔴 [AGRESİF SATICI]: 1 dakikalık işlemlerde %70+ ezici Taker Satıcı baskısı!")

    if alerts:
        print("  [5] ANLIK KRİTİK ALARMLAR:")
        for a in alerts:
            print(f"    {a}")
    else:
        print("  [5] ANLIK KRİTİK ALARMLAR: Piyasa sakin, nötr akış.")
        
    print(border + "\n")

# ═══════════════════════════════════════════════════════════════════════
# 5. ANA CANLI TAKİP DÖNGÜSÜ
# ═══════════════════════════════════════════════════════════════════════

def run_single_tracking_cycle(target_sym):
    clean = target_sym.upper().replace('.P', '').replace('_', '')
    is_mexc = 'LONGXIA' in clean
    provider = 'MEXC' if is_mexc else 'BINANCE'
    market = 'FUTURES'
    sym_key = 'LONGXIA_USDT' if is_mexc else clean
    display_sym = 'LONGXIA_USDT (MEXC/Bybit)' if is_mexc else f"{clean}.P (Binance)"
    
    if is_mexc:
        candles = fetch_candles_mexc()
    else:
        candles = fetch_candles_binance(clean)
        
    ref_price = candles['close'][-1] if candles and candles['close'] else 0.0
    fetch_live_trades(provider, market, sym_key, reference_price=ref_price)
    print_live_dashboard(candles, provider, market, sym_key, display_sym)

if __name__ == '__main__':
    GROUP_MEVCUT = ['BTCUSDT', 'SOLUSDT', 'SYNUSDT', 'IOSTUSDT', 'SAGAUSDT', 'LONGXIA']
    GROUP_TOP100 = ['ETHUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'LINKUSDT',
                    'ADAUSDT', 'LTCUSDT', 'AVAXUSDT', 'SUIUSDT', 'AKEUSDT']
    GROUP_OUTSIDE100 = ['PONSUSDT', 'SKRUSDT', 'PROMUSDT', 'UAIUSDT', 'BULLAUSDT',
                        'OGUSDT', 'ZORAUSDT', 'TNSRUSDT', 'VELVETUSDT', 'ZKCUSDT']
    GROUP_ALL_26 = GROUP_MEVCUT + GROUP_TOP100 + GROUP_OUTSIDE100

    targets = []
    for arg in sys.argv[1:]:
        if not arg.startswith('-'):
            targets.append(arg.upper().replace('.P', ''))

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

    print("=" * 78)
    print(f"  ⚡ KONTRAT DOĞRULAMASI BAŞLIYOR ({len(track_list)} coin)...")
    track_list = verify_contracts(track_list)

    n_mevcut = sum(1 for c in track_list if get_coin_info(c)['class'] == 'MEVCUT')
    n_top100 = sum(1 for c in track_list if get_coin_info(c)['class'] == 'TOP100')
    n_out100 = sum(1 for c in track_list if get_coin_info(c)['class'] == 'OUTSIDE100')

    print(f"  ✅ {len(track_list)} coin doğrulandı ve takibe hazır")
    print(f"     MEVCUT: {n_mevcut} | TOP100: {n_top100} | OUTSIDE100: {n_out100}")
    print("=" * 78)
    print(f"  ⚡ CANLI TAKİP BAŞLATILDI: {len(track_list)} COİN")
    print(f"  Coinler: {', '.join(track_list)}")
    print("  • Gerçek Taker Alım/Satım & Project Z CVD (İzole Havuz)")
    print("  • Dakikalık Birikim & Hacim Geçmişi")
    print("  • ZPTDIFAT MTF Yorgunluk Matrisi & STRUCTURE v1.1")
    print("  • REALF v4.2 Akış/Fiyat Dengesi & 12 Tanı Metriği")
    print("  Durdurmak için Ctrl+C tuşlarına basabilirsiniz.")
    print("=" * 78 + "\n")

    for sym in track_list:
        clean = sym.upper().replace('.P', '').replace('_', '')
        is_mexc = 'LONGXIA' in clean
        p = 'MEXC' if is_mexc else 'BINANCE'
        m = 'FUTURES'
        k = 'LONGXIA_USDT' if is_mexc else clean
        try:
            fetch_live_trades(p, m, k)
        except Exception:
            pass
    time.sleep(1)

    inter_coin_delay = 2 if len(track_list) > 15 else 3
    cycle_delay = 3 if len(track_list) > 15 else 6

    while True:
        try:
            for sym in track_list:
                try:
                    run_single_tracking_cycle(sym)
                except Exception as e:
                    print(f"  ⚠️ [{sym}] Döngü hatası: {e}")
                if len(track_list) > 1:
                    time.sleep(inter_coin_delay)
            time.sleep(cycle_delay)
        except KeyboardInterrupt:
            print("\nTakip kullanıcı tarafından durduruldu.")
            break
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Takip hatası: {e}")
            time.sleep(10)
