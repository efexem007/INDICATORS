"""Fixed, versioned experiment candidates; no production orders or score changes.

The candidate menu is frozen before reading its evaluation results. Baseline v1
stays available alongside every candidate. No automatic promotion from this run.
"""
import shadow_research as sh

VERSION = 'hypothesis-candidates-v2.4'
VARIANTS = {
    'H1_BASE': 'H1 mevcut shadow tanımı',
    'H1_HTF_ALIGN': 'H1 + 15m bullish ve (1h veya 4h bullish), fresh 5m bearish olay yok',
    'H1_FLOW_CONFIRM': 'H1 + 5m CVD slope>0 ve flow confidence5m>=60',
    'H2_BASE': 'H2 mevcut shadow tanımı',
    'H2_GAP_EXPANDS': 'H2 + UnpricedFlow delta3m>=0',
    'H2_FLOW_CONFIRM': 'H2 + 5m CVD slope>0 ve flow confidence5m>=60',
    'H3_BASE': 'H3 immediate breakout mevcut shadow tanımı',
    'H3_RETEST': 'H3 gözlenen breakout→retest→reacceleration',
    'H4_BASE': 'H4 mevcut shadow tanımı; tetik yoksa eşik düşürülmez',
    'H5_BASE': 'H5 mevcut shadow tanımı',
    'H5_HTF_ALIGN': 'H5 + 15m ve 1h bearish',
    'H5_FRESH_BREAK': 'H5 + fresh 1m/3m bearish event',
    'H1_SLOW_SETUP': 'H1 + setup→trigger >= 15 dk; anında tetiklenen kurulumdan ayrı ölçülür',
    'H2_SLOW_SETUP': 'H2 + setup→trigger >= 15 dk',
    'H3_SLOW_SETUP': 'H3 + setup→trigger >= 15 dk',
    'H6_RESET': 'H6 reset tarayıcısı; işlem tetiği değildir',
    'H6_DEEP_RESET': 'H6 deep reset tarayıcısı; işlem tetiği değildir',
    'H8_IGNITION': 'H8 ateşleme: hacim+alıcı patlaması; REALF/yapı/fatigue kapısı YOK',
    'H8_IGNITION_QUIET': 'H8 ateşleme + öncesinde sıkışık 1m ATR (medyan altı)',
    'H1_BASE_PULLBACK': 'H1 tetiği + %0.25 geri çekilme beklenir; olay geri çekilme anında doğar',
    'H3_BASE_PULLBACK': 'H3 tetiği + %0.25 geri çekilme beklenir',
    'H3_RETEST_PULLBACK': 'H3 retest tetiği + %0.25 geri çekilme beklenir',
    'H8_IGNITION_PULLBACK': 'H8 ateşleme + %0.25 geri çekilme beklenir',
    'H1_REALF_PCTL': 'H1 + realf_percentile >= 60 (ham 35–55 bandı ayırmıyor, yüzdelik sınanıyor)',
    'H1_FLOW_AGREE': 'H1 + cvd_1m ve cvd_5m ikisi de pozitif (akış pencereleri uyumlu)',
    'H1_FLOW_MIXED': 'H1 + cvd_1m ile cvd_5m ters işarette (çelişki bölgesi ayrı ölçülür)',
    'H1_CONF_FLOOR': 'H1 + flow_confidence_5m >= 50 (yapısal zayıf ölçümlü coinler dışarıda)',
    'H4_FRESH_15M': 'H4 armed + 15 DAKİKA içinde 3m/5m DN olayı (bar yerine dakika tazeliği)',
    'H5_FRESH_15M': 'H5 armed + 15 dakika içinde 1m/3m DN olayı',
}

# Bir varyant geri çekilme bekliyorsa olayı taban tetikte değil, geri çekilmenin
# gerçekleştiği snapshot'ta doğar: böylece fwd_ret/excess/karakter alanları gerçek
# giriş anına bağlanır, sonradan düzeltme gerekmez.
PULLBACK_OF = {'H1_BASE_PULLBACK': 'H1_BASE', 'H3_BASE_PULLBACK': 'H3_BASE',
               'H3_RETEST_PULLBACK': 'H3_RETEST', 'H8_IGNITION_PULLBACK': 'H8_IGNITION'}
PULLBACK_PCT = 0.25
PULLBACK_WINDOW_MS = 10 * 60_000

BAR_MINUTES = {'1m': 1, '3m': 3, '5m': 5, '15m': 15, '1h': 60, '4h': 240}
FRESH_MINUTES = 15


def fresh_within(s, tf, direction, minutes=FRESH_MINUTES):
    """Freshness in minutes, not in bars: 3 bars is 3 minutes on 1m but 15 on 5m,
    which is why multi-timeframe 'fresh' conditions were almost never observable."""
    age = sh.number(s, f'str_{tf}_event_age')
    return (s.get(f'str_{tf}_ready') is True
            and s.get(f'str_{tf}_event') in (f'BOS {direction}', f'CHOCH {direction}')
            and age is not None and 0 <= age * BAR_MINUTES[tf] <= minutes)


def flow_agrees(s, sign=1):
    one, five = sh.number(s, 'cvd_1m'), sh.number(s, 'cvd_5m')
    return one is not None and five is not None and sign * one > 0 and sign * five > 0


def flow_mixed(s):
    one, five = sh.number(s, 'cvd_1m'), sh.number(s, 'cvd_5m')
    return one is not None and five is not None and one != 0 and five != 0 and (one > 0) != (five > 0)

# Karar ufku, ölçülen tepe zamanından türer, aranmaz: bir ailenin medyan tepe gecikmesini
# İÇEREN en küçük mevcut ufuk seçilir. Tur 2 ölçümü (run_20260918_112149, tam 60 dk gözlenen
# tetikler): H1 35 dk, H2 41 dk, H3 41 dk, H5 15 dk; H4 tetiksiz. Lab her turda tepe zamanını
# yeniden ölçer, defter de sapmayı eksik olarak açar — bu sabitler dondurulmuş ölçümdür.
OUTCOME_HORIZONS = (1, 3, 5, 10, 20, 30, 60)
MEASURED_PEAK_MIN = {'H1': 35, 'H2': 41, 'H3': 41, 'H5': 15}
DECISION_HORIZON = {'H1': 60, 'H2': 60, 'H3': 60, 'H4': 20, 'H5': 20, 'H6': 20, 'H7': 20, 'H8': 20}


def family(variant):
    return variant.split('_')[0]


def decision_horizon(variant):
    """Hipotezin kendi hareketinin ölçüldüğü ufuk; H8 ölçülene kadar varsayılan 20 dk."""
    return DECISION_HORIZON[family(variant)]


def horizon_rule(peak_min):
    """Medyan tepeyi içeren en küçük mevcut ufuk; tepe yoksa None."""
    if peak_min is None:
        return None
    for horizon in OUTCOME_HORIZONS:
        if horizon >= peak_min:
            return horizon
    return OUTCOME_HORIZONS[-1]


# H8 eşikleri bu run'ın KENDİ dağılımından alındı ve hiçbir getiriye bakılmadan seçildi:
# realf_rvol p90, buyer_ratio_1m p90, str_1m_atr_pct p50. Amaç, kaçırılan hareketlerin
# %72'sini eleyen kapıları (REALF durumu, yapı kırılımı, fatigue, unpriced) hiç kullanmadan
# "önce patlama, teyit sonra" mekanizmasının kendi başına kenar taşıyıp taşımadığını ölçmek.
IGNITION_RVOL = 1.35
IGNITION_BUYER_PCT = 80.0
QUIET_ATR_PCT = 0.193


def ignition(s):
    rvol, buyer, cvd = sh.number(s, 'realf_rvol'), sh.number(s, 'buyer_ratio_1m'), sh.number(s, 'cvd_1m_pct')
    return (rvol is not None and rvol >= IGNITION_RVOL and buyer is not None
            and buyer >= IGNITION_BUYER_PCT and cvd is not None and cvd > 0)


def quiet_base(s):
    atr = sh.number(s, 'str_1m_atr_pct')
    return atr is not None and atr <= QUIET_ATR_PCT


# Belirteç bütünü: her ailenin tetik anında okuduğu alanlar ve eşikleri.
# shadow_research.py içindeki components sözlüğünün insan okunur karşılığıdır;
# tanım değişirse burası da değişmeli — defterin kullanım kılavuzu buradan üretilir.
INDICATORS = {
    'H1': ['Yorgunluk: fat_3m veya fat_5m < 35 (sıfırlanmış)',
           'Bağlam: HTF bull (15m/1h yukarı)',
           'REALF: skor 35–55 bandı',
           'Fiyatlanmamış akış: unpriced >= 0',
           'Akış/yapı: akış UP ya da taze 1m UP yapı olayı',
           'CVD: 5 dk CVD deltası pozitif'],
    'H2': ['Fiyatlanmamış akış: realf_unpriced_flow > 0.005 (gap açık)',
           'REALF: skor < 50 (fiyat henüz gitmemiş)',
           'REALF kalite: beta R² > 0.45 ve bileşen uyumu > 0.5',
           'Yorgunluk: fat_1m < 83',
           'Yapı: taze 5m DN olayı yok',
           'Akış: akış UP, 5 dk CVD deltası pozitif, 1 dk alıcı oranı yükseliyor'],
    'H3': ['Yapı: taze, güçlü ve teyitli BOS (kırılım)',
           'Yorgunluk: fat_1m < 72',
           'REALF: skor 40–60 bandı',
           'CVD: cvd_1m > 0 ve cvd_5m > 0',
           'Alıcı baskınlığı: buyer_ratio_1m > 50'],
    'H4': ['Tükeniş: yakın geçmişte aşırı uzama',
           'REALF: skor > 58 ya da unpriced < 0 (fiyat akışın önünde)',
           'Yorgunluk: 1 dk yorgunluk deltası negatif',
           'CVD: cvd_1m deltası negatif',
           'Akış: akış DOWN',
           'Yapı: taze 3m veya 5m DN olayı  ⚠ bu veride hiç eşzamanlı görülmedi'],
    'H5': ['Bağlam: HTF bear',
           'Sıçrama: yakın geçmişte tepki yükselişi',
           'Fiyatlanmamış akış: güçlü pozitif gap yok (unpriced <= 0.005)',
           'CVD: cvd_5m < 0',
           'Akış: akış DOWN',
           'Yapı: 1m veya 3m durum DN'],
    'H6': ['Yorgunluk: 1m/3m/5m birlikte 30 altına reset'],
    'H7': ['Yorgunluk: fat_1m < 30', 'Uzama geçmişi: 24s/3g/7g ve ATR uzaması hazır'],
    'H8': ['Hacim: realf_rvol >= 1.35 (bu runın p90 değeri)',
           'Alıcı baskınlığı: buyer_ratio_1m >= 80 (p90)',
           'CVD: cvd_1m_pct > 0',
           'KAPI YOK: REALF bandı, yapı kırılımı, yorgunluk ve unpriced şartı bilerek aranmaz'],
}


SLOW_SETUP_SEC = 15 * 60


def slow_setup(s, h):
    """Setup that took a long time to mature; known at the trigger, no lookahead."""
    delay = sh.number(s, f'shadow_{h}_setup_to_trigger_sec')
    return delay is not None and delay >= SLOW_SETUP_SEC


def candidate_masks(s, ignore_quality=False):
    base = {f'H{i}': bool(s.get(f'shadow_H{i}_trigger_condition')) for i in range(1, 6)}
    confirmed_flow = sh.gt(s, 'cvd_slope_5m_norm', 0) and sh.between(s, 'flow_confidence_5m', 60, 100)
    masks = {
        'H1_BASE': base['H1'],
        'H1_HTF_ALIGN': base['H1'] and sh.state(s, '15m', 'UP') and any(sh.state(s, tf, 'UP') for tf in ('1h', '4h')) and not sh.event(s, '5m', 'DN'),
        'H1_FLOW_CONFIRM': base['H1'] and confirmed_flow,
        'H2_BASE': base['H2'],
        'H2_GAP_EXPANDS': base['H2'] and sh.number(s, 'unpriced_d3') is not None and s['unpriced_d3'] >= 0,
        'H2_FLOW_CONFIRM': base['H2'] and confirmed_flow,
        'H3_BASE': base['H3'],
        'H3_RETEST': bool(s.get('shadow_H3_reaccel_trigger')),
        'H4_BASE': base['H4'],
        'H5_BASE': base['H5'],
        'H5_HTF_ALIGN': base['H5'] and all(sh.state(s, tf, 'DN') for tf in ('15m', '1h')),
        'H5_FRESH_BREAK': base['H5'] and any(sh.event(s, tf, 'DN') for tf in ('1m', '3m')),
        'H1_SLOW_SETUP': base['H1'] and slow_setup(s, 'H1'),
        'H2_SLOW_SETUP': base['H2'] and slow_setup(s, 'H2'),
        'H3_SLOW_SETUP': base['H3'] and slow_setup(s, 'H3'),
        'H6_RESET': bool(s.get('shadow_H6_setup')),
        'H6_DEEP_RESET': bool(s.get('shadow_H6_setup')) and s.get('shadow_reset_type') == 'DEEP_RESET',
        'H8_IGNITION': ignition(s),
        'H8_IGNITION_QUIET': ignition(s) and quiet_base(s),
        'H1_REALF_PCTL': base['H1'] and sh.gt(s, 'realf_percentile', 60),
        'H1_FLOW_AGREE': base['H1'] and flow_agrees(s),
        'H1_FLOW_MIXED': base['H1'] and flow_mixed(s),
        'H1_CONF_FLOOR': base['H1'] and sh.between(s, 'flow_confidence_5m', 50, 100),
        'H4_FRESH_15M': bool(s.get('shadow_H4_armed')) and any(fresh_within(s, tf, 'DN') for tf in ('3m', '5m')),
        'H5_FRESH_15M': bool(s.get('shadow_H5_armed')) and any(fresh_within(s, tf, 'DN') for tf in ('1m', '3m')),
    }
    for variant in PULLBACK_OF:  # filled in by the tracker, never true at the base trigger
        masks[variant] = False
    if ignore_quality:  # only for measuring what the quality veto costs; never for evaluation
        return {k: bool(v) for k, v in masks.items()}
    valid = not sh.quality(s)
    return {k: bool(v and valid) for k, v in masks.items()}


class CandidateTracker:
    """Emit every mask and one observation per symbol/variant per 60 minutes."""
    def __init__(self):
        self.last = {}
        self.pending = {}  # (run, symbol, base variant) -> (trigger time, trigger price)

    def pullbacks(self, s):
        """A patient entry is its own event, born at the snapshot where the retrace happens."""
        now, price = s['captured_at_ms'], sh.number(s, 'price')
        out = {}
        for variant, base in PULLBACK_OF.items():
            key = (s.get('run_id'), s['symbol'], base)
            armed, hit = self.pending.get(key), False
            if armed and price:
                t0, trigger_price = armed
                direction = -1 if base.startswith(('H4', 'H5')) else 1
                if now - t0 > PULLBACK_WINDOW_MS:
                    self.pending.pop(key, None)
                elif now > t0 and direction * (price / trigger_price - 1) * 100 <= -PULLBACK_PCT:
                    hit, _ = True, self.pending.pop(key, None)
            out[variant] = hit and not sh.quality(s)
        return out

    def arm(self, s, events):
        price = sh.number(s, 'price')
        for base in set(PULLBACK_OF.values()):
            if events.get(base) and price:
                self.pending[(s.get('run_id'), s['symbol'], base)] = (s['captured_at_ms'], price)

    def update_masks(self, s, masks):
        """Same 60 minute spacing for any mask set, so the veto pass counts like the main one."""
        now = s['captured_at_ms']
        events = {}
        for name, selected in masks.items():
            key = (s.get('run_id'), s['symbol'], name)
            previous = self.last.get(key)
            new = selected and (previous is None or now - previous >= sh.EVENT_MS)
            if new:
                self.last[key] = now
            events[name] = new
        return events

    def update(self, s):
        out = {'hypothesis_candidates_version': VERSION}
        masks = candidate_masks(s)
        masks.update(self.pullbacks(s))
        events = self.update_masks(s, masks)
        self.arm(s, events)
        for name, selected in masks.items():
            out[f'research_{name}_condition'] = selected
            out[f'research_{name}_event'] = events[name]
        return out


def exit_condition(policy, snapshot, direction, observed_peak, current_return, entry_atr_pct):
    """Only information at this observation; lab executes at the NEXT observation."""
    if sh.quality(snapshot):
        return False
    if policy == 'FLOW_STRUCTURE':
        cvd1 = sh.number(snapshot, 'cvd_1m')
        cvd5 = sh.number(snapshot, 'cvd_5m')
        opposed = 'DN' if direction > 0 else 'UP'
        return (cvd1 is not None and direction * cvd1 < 0 and
                ((cvd5 is not None and direction * cvd5 < 0) or sh.event(snapshot, '1m', opposed)))
    if policy == 'ATR_GIVEBACK':
        return (entry_atr_pct is not None and entry_atr_pct > 0 and
                observed_peak >= entry_atr_pct and observed_peak - current_return >= entry_atr_pct)
    raise ValueError(policy)
