# Z TRACKER — RUN 20260918_015707 SHADOW TEST RAPORU
## Tarih: 2026-09-18
## Durum: RESEARCH / SHADOW — PRODUCTION DEĞİŞİKLİĞİ YOK

> Bu rapor yalnızca logger/outcome verisinden hipotez testi ve geliştirme notu üretir.
> Fatigue, Structure v1.2, REALF ve CVD production formülleri değiştirilmez.

# 1. EXECUTIVE SUMMARY

Ana run:
- run_id: `20260918_015707`
- snapshot: **4.957**
- unique snapshot_id: **4.957**
- duplicate: **0**
- coin: **20**
- outcome: **4.052**
- snapshot_id ile eşleşen complete outcome: **4.052 / 4.052**
- JSONL parse hatası: **0**

Ana araştırma sonucu:

1. **H1 mevcut haliyle aşırı seyrek.** Orijinal 3m/5m reset + HTF bullish + REALF + flow trigger operationalizasyonunda yalnız **4 bağımsız event** kaldı. Sonuçlar olumlu görünse de bu sayı kural güncellemek için yetersiz.
2. **H2 kısa-vade repricing hipotezi olarak yaşamaya devam ediyor.** U >0.003 ve R² >0.35 varyantı 12 bağımsız event verdi; +5m medyan +0.075%, +10m +0.359%, +20m +0.219%. Ancak sample küçüktür.
3. **H2 U >0.010 hard threshold yapılamaz.** Yalnız **1 bağımsız event** kaldı. Bu eşik yalnız `STRONG_GAP_TAG` olabilir.
4. **H3 immediate-breakout entry desteklenmiyor.** 52 bağımsız eventte +5m medyan yaklaşık +0.007%, +10m medyan 0.000%; buna karşılık +30m +0.214%, +60m +0.605%. Breakout → retest → re-acceleration modeli test edilmelidir.
5. **H4 kısa-horizon exhaustion olarak anlamlı aday.** 7 bağımsız eventte short yönlü +5m medyan +0.359%, hit 85.7%; ancak +30m medyan negatife, +60m belirgin negatife dönüyor. Sustained reversal olarak kullanılmamalı.
6. **H5 bu run'da test edilemedi.** Operational trigger 0 bağımsız event.
7. **H6 reset scanner umut verici ama entry değildir.** 20 bağımsız reset eventinde +5m medyan +0.184%, +20m +0.141%; deep reset yalnız 4 event olduğu için doğrulanmış sayılamaz.

# 2. DATA HEALTH

## Snapshot bütünlüğü

| Kontrol | Sonuç |
|---|---:|
| Toplam snapshot | 4.957 |
| Unique snapshot_id | 4.957 |
| Duplicate | 0 |
| Bozuk JSONL satırı | 0 |
| required_fields_missing | 0 |
| Coin sayısı | 20 |

Saatlik snapshot sayıları:
- 01: 22
- 02: 883
- 03: 880
- 04: 927
- 05: 902
- 06: 899
- 07: 444

## Outcome

- outcomes.jsonl satırı: **4.052**
- parse hatası: **0**
- snapshot_id eşleşmesi: **4.052**
- outcome_complete=true: **4.052**

Bu run için artık forward-return ve MFE/MAE analizi resmî outcome dosyasıyla yapılabilir.

## Flow completeness

- 1m complete: **%99.80**
- 5m complete: **%99.78**
- 15m complete: **%99.21**

Bu kalite seviyesi araştırma için yeterlidir; partial pencereler trigger hesaplarında yine veto edilmelidir.

## Orderbook / sync

- orderbook alanı null: yaklaşık **%1.01**
- ob_stale=true snapshot: **131**
- sync_error dolu snapshot: **9**
- pool gap snapshot: **0**

Orderbook stale/null kayıtları orderbook tabanlı hipotezlerde dışarıda tutulmalıdır.

## Console / bağlantı

07 ve 08 saatlerinde DNS/name-resolution hataları belirginleşiyor:
- 07: yaklaşık 831 DNS eşleşmesi
- 08: yaklaşık 327 DNS eşleşmesi

Bu nedenle son bölümde logger canlı kalsa bile piyasa verisi güvenilirliği ayrıca izlenmelidir. `run_meta` içinde cycle_errors=1183 bulunması bu bölümle birlikte değerlendirilmelidir.

# 3. MARKET / REGIME NOTU

Bu raporun ilk turunda amaç hipotezlerin yön ve zaman ufku davranışını ayırmaktır.
Market-wide drift için ayrı benchmark/excess-return katmanı bir sonraki turda zorunlu tutulacaktır.

Structure state dağılımında 15m büyük ölçüde bullish iken 4h tarafı daha karışıktır. Bu yüzden yalnız 15m yönüne bakarak H1/H3 güçlendirilmemelidir.

# 4. H1 — TREND PULLBACK LONG

## Test edilen varyant A — mevcut mantığa yakın

Koşullar:
- 15m + 1h + 4h bullish state
- 3m veya 5m Fatigue <35
- REALF 35–55
- RemainingUnpricedFlow >=0
- 1m/5m complete
- CVD turn/slope UP
- 5m CVD delta >=0

Sonuç:
- raw candidate: **6**
- 10m cooldown sonrası bağımsız event: **4**

Forward medyan:
- +5m: **+0.062%**
- +10m: **+0.072%**
- +20m: **+0.371%**
- +30m: **+0.532%**
- +60m: **+0.837%**

20m directional MFE medyan: **+0.464%**
20m directional MAE medyan: **-0.019%**

### Karar

Sonuç güzel görünmesine rağmen **n=4**.
H1 v2 production veya threshold güncellemesi YOK.

## Test edilen varyant B — 1m+3m+5m hepsi <35

Bağımsız event: **0**

### Karar

Bu kombinasyon hard gate olursa sistemi gereksiz yere susturuyor.

## Test edilen varyant C — yalnız 1m reset

Bağımsız event: **12**

- +5m medyan: **-0.012%**
- +10m: **+0.050%**
- +20m: **+0.201%**
- +60m: **+0.317%**

Ancak mean sonuçlarda büyük negatif outlier etkisi görülüyor ve 20m MAE medyanı yaklaşık -0.300%.

### H1 geliştirme notu

`1m Fatigue <35` tek başına reset tanımı olarak fazla gevşek.
Bir sonraki testte 3 ayrı reset tipi tutulmalı:

- H1_RESET_FAST = 1m <35
- H1_RESET_LTF = 3m veya 5m <35
- H1_RESET_STACKED = 1m + (3m veya 5m) <35

Bu etiketler hard gate olmadan ayrı outcome segmentleri üretmeli.

# 5. H2 — FLOW-LAG / REPRICING LONG

Test grid:
- UnpricedFlow: >0.003 / >0.005 / >0.010
- Beta R²: >0.35 / >0.45 / >0.55
- gap kötüleşmiyor: unpriced_d1 >=0
- CVD turn/slope UP
- 5m CVD delta >0
- Buyer Ratio delta 1m >0
- complete flow

## U >0.003, R² >0.35

Bağımsız event: **12**

- +5m medyan: **+0.075%**
- +10m: **+0.359%**
- +20m: **+0.219%**
- +60m: **+0.260%**
- +5m hit: **75%**
- +10m hit: **75%**

20m MFE medyan: **+0.675%**
20m MAE medyan: **-0.238%**

## U >0.005

Bağımsız event: **6**

- +5m medyan: **+0.086%**
- +10m: **+0.539%**
- +20m: **+0.254%**

Sample yarıya düştüğü için görünen artışın gerçek edge olduğu söylenemez.

## U >0.010

Bağımsız event: **1**

Bu eşikten performans sonucu çıkarılamaz.

## R²

R² 0.35 → 0.45 değişimi bu sample içinde belirgin ayrışma yaratmadı.
R² >0.55 sample'ı daha da küçülttü.

### H2 güncelleme önerisi — SHADOW ONLY

Eski düşünce:
- U >0.005 tercih
- R² >0.45 tercih

Yeni shadow sınıflandırma:

- `U >0.003` = MINIMUM_CANDIDATE
- `U >0.005` = PREFERRED_GAP
- `U >0.010` = STRONG_GAP_TAG, hard gate değil

R²:
- >0.35 = research-eligible
- >0.45 = preferred-quality tag
- >0.55 = high-R² tag

En önemli kural:
**UnpricedFlow level tek başına kullanılmayacak; slope/delta kötüleşiyorsa candidate kalitesi düşürülecek.**

# 6. H3 — BREAKOUT CONTINUATION

Operational immediate trigger:
- fresh 5m veya 15m BOS/CHOCH UP
- event age düşük
- event strength >=30
- confidence >=70
- TR/EXP UP regime
- Fatigue <72
- REALF 40–60
- 1m ve 5m CVD pozitif
- Buyer Ratio 1m >50
- complete flow

Bağımsız event: **52**

Forward:
- +1m medyan: +0.011%
- +3m: +0.016%
- +5m: **+0.007%**
- +10m: **0.000%**
- +20m: **+0.129%**
- +30m: **+0.214%**
- +60m: **+0.605%**

### Kritik yorum

Bu pattern breakout sonrası yön devamını tamamen reddetmiyor.
Ama **entry timing breakout anında güçlü değil**.

Veri daha çok:
`BREAKOUT → kısa retest/absorbsiyon → sonra continuation`
hipotezini destekliyor.

### H3 v2.1 candidate

H3 iki aşamaya ayrılmalı:

1. `H3_BREAKOUT_ARMED`
2. `H3_REACCEL_TRIGGER`

REACCEL için araştırılacak:
- breakout sonrası 2–10m retest
- fiyat protected level altına kalıcı geçmiyor
- REALF 40–60/fair bölgesine geri geliyor
- 1m CVD yeniden UP dönüyor
- 5m CVD pozitif kalıyor veya yeniden güçleniyor
- Fatigue kısa reset yapıyor
- bearish CHOCH/BOS oluşmuyor

Bu henüz production kuralı değildir.

# 7. H4 — EXHAUSTION / REVERSAL SHORT

Base trigger:
- Fatigue >83
- fatigue_delta_1m <0
- REALF >58 veya UnpricedFlow <0
- CVD turn/slope DOWN
- 3m/5m bearish structure event
- complete flow

Bağımsız event: **7**

Short-direction medyan:
- +1m: +0.073%
- +3m: +0.158%
- +5m: **+0.359%**
- +10m: +0.101%
- +20m: +0.218%
- +30m: **-0.184%**
- +60m: **-0.832%**

+5m directional hit: **85.7%**

### Kritik yorum

H4 şu an:
**TACTICAL EXHAUSTION / SHORT-HORIZON MEAN REVERSION**

olarak davranıyor.

H4'ü uzun süreli trend reversal olarak yorumlamak bu sample ile desteklenmiyor.

### Strong filter

5m CVD <0 + Buyer Ratio <50 eklendiğinde yalnız **1 event** kalıyor.
Bu nedenle hard veto/gate yapılmaz.

### Yeni test

H4 trigger sonrası:
- 1m
- 3m
- 5m

follow-through oluşmazsa setup'ın decay hızını ölç.

`H4_DECAY_5M` araştırma özelliği eklenmeli.

# 8. H5 — FAILED BOUNCE SHORT

Operational koşullarda bağımsız event: **0**.

### Karar

H5 v2 aynen kalır.
Threshold değiştirilmez.
Research strength yükseltilmez/düşürülmez.

Durum:
**INSUFFICIENT DATA**

Bir sonraki logger analizinde H5 setup/armed aşamaları trigger'dan ayrı sayılmalı. Böylece sorun gerçekten pattern azlığı mı yoksa trigger'ın fazla sert olması mı anlaşılır.

# 9. H6 — MULTI-TF RESET SCANNER

## RESET
1m + 3m + 5m Fatigue <30

- raw: 75
- bağımsız event: **20**

Forward medyan:
- +5m: **+0.184%**
- +10m: +0.088%
- +20m: +0.141%
- +30m: +0.484%
- +60m: +0.577%

## DEEP RESET
1m + 3m + 5m <30 ve 15m <35

- raw: 11
- bağımsız event: **4**

Sample çok küçüktür.

### Karar

H6 scanner olarak tutulmalı.
Doğrudan LONG üretmemeli.

Bir sonraki önemli metrik:
- H6_RESET → H1_SETUP dönüşüm oranı
- H6_RESET → H2_SETUP dönüşüm oranı
- dönüşüme kadar geçen süre
- conversion sonrası outcome

# 10. H7 — PUMP / EXTENSION FILTER

Bu run'da H7 için gerekli tüm extension alanları eksiksiz biçimde mevcut değil:
- 24h return
- 3d return
- 7d return
- local-base return
- ATR extension

RVOL / percentile tek başına H7 kararına yetmez.

### Karar

H7 v1:
**UNTESTED / LOGGER FEATURE GAP**

# 11. BEST SETUPS

Bu turda istatistiksel olarak en ilginç aileler:

- H2: 5–20m repricing davranışı
- H3: immediate giriş değil, gecikmeli continuation/re-acceleration
- H4: ilk 5m tactical exhaustion
- H6: candidate/reset scanner

Bu sıralama performans rankingi değildir; yalnız bir sonraki araştırma turunda en çok bilgi üretecek alanları gösterir.

# 12. FALSE POSITIVE ODAĞI

Özellikle incelenecek false-positive tipleri:

## H2
- gap pozitif ama slope küçülüyor
- 1m trigger var fakat 5m CVD follow-through yok
- Buyer Ratio tek snapshot yükselip geri dönüyor

## H3
- breakout chase: ilk 5–10m retest içinde girişin erken kalması
- BOS fresh ama price/flow already extended

## H4
- ilk 5m short çalışıyor fakat yapı bozulmadığı için trend tekrar yukarı devam ediyor

# 13. FALSE NEGATIVE ODAĞI

Bir sonraki analizde:
- büyük +20m/+60m hareket yapıp H1–H7'ye hiç girmeyen eventler çıkarılmalı
- bunların Structure / REALF / Fatigue / CVD profili cluster edilmelidir

Özellikle H3 re-acceleration candidate bu analizden türetilmelidir.

# 14. FEATURE FINDINGS

Şimdilik en önemli feature dersleri:

1. **UnpricedFlow slope**, H2 için level kadar kritik.
2. **Event age**, H3 için yalnız BOS var/yok bilgisinden daha anlamlı.
3. **Horizon**, hipotezin kendisinin bir parçası olmalı:
   - H2: kısa repricing
   - H4: ilk 5m exhaustion
   - H3: daha gecikmeli continuation
4. Fatigue threshold tek başına yön üretmiyor; H1/H6 farkı bunu tekrar gösteriyor.

# 15. SEGMENT FINDINGS

Bu ilk raporda TOP20/TOP100/OUTSIDE100, RVOL ve regime segmentlerine göre yeterli bağımsız event sayısı her hipotezde oluşmadığı için güçlü segment sonucu yazılmıyor.

Segmentasyon bir sonraki çok-run birleşik analizde yapılmalıdır.

# 16. UPDATED HYPOTHESES

Production değişikliği YOK.

Shadow candidate:
- H1 v2 → H1 reset taxonomy araştırması
- H2 v2 → H2 v2.1 candidate quality tiers
- H3 v2 → H3 v2.1 breakout-armed + reacceleration
- H4 v2 → H4 v2.1 tactical 5m exhaustion
- H5 v2 → aynı
- H6 v1 → H6 v1.1 reset/deep-reset scanner labels
- H7 v1 → aynı, logger feature bekliyor

# 17. NEW CANDIDATE HYPOTHESES

## H8 candidate — BREAKOUT RETEST REACCELERATION

Context:
- fresh H3 breakout event

Wait:
- 2–10m retest

Armed:
- protected level korunuyor
- REALF fair'e dönüyor
- Fatigue resetleniyor

Trigger:
- CVD 1m turn UP
- 5m CVD pozitif/iyileşiyor
- bearish structural invalidation yok

Bu pattern en az 30 bağımsız event oluşmadan versioned hypothesis yapılmamalıdır.

# 18. RESEARCH-STRENGTH UPDATE

Eski yüzdeler otomatik değiştirilmez.

Bu run sonrası nitel durum:
- H1: insufficient-small sample
- H2: promising but small sample
- H3 immediate: timing weak; delayed model worth testing
- H4: short-horizon candidate, small sample
- H5: insufficient
- H6: promising scanner, not entry
- H7: untested

Bunlar WIN RATE değildir.

# 19. WHAT WE STILL DON'T KNOW

- Çoklu gün / farklı market regime robustness
- Market-relative excess return
- Fees/slippage sonrası edge
- H2 performansının pump coinlerde bozulup bozulmadığı
- H3 ideal retest süresi
- H4 decay süresi ve stop/invalidasyon davranışı
- H5 setup'ın gerçekten nadir mi yoksa trigger'ın fazla sert mi olduğu
- H6 reset → H1/H2 conversion oranı

# 20. NEXT DATA COLLECTION PRIORITIES

1. Aynı şema ve code_fingerprint ile daha fazla run.
2. En az 30/50/100 bağımsız event yaklaşımı.
3. H7 için extension alanlarını logger'a ekleme planı:
   - return_24h
   - return_3d
   - return_7d
   - local_base_return
   - atr_extension
4. H3 için breakout timestamp + retest depth + reaccel delay araştırma alanları.
5. H4 için trigger sonrası 1/3/5/10m follow-through ve decay etiketi.
6. H6 için setup conversion tracking.
7. TOP20/TOP100/OUTSIDE100 ve regime bazlı OOS segment analizi.

# İNDİKATÖR GELİŞTİRME PLANI

Production formüllerine dokunma.

## FATIGUE
Formül değişikliği yok.
Shadow'da sadece:
- reset type
- reset duration
- fatigue slope
- fatigue recovery speed
etiketleri üretilecek.

## STRUCTURE v1.2
Formül değişikliği yok.
Araştırmada:
- event freshness bucket
- breakout→retest depth
- protected-level survival
- reacceleration timing
çıkarılacak.

## REALF
Motor değişikliği yok.
Araştırmada:
- UnpricedFlow level bucket
- slope/delta
- gap expansion/contraction
- Beta R² quality tier
ayrı feature olarak tutulacak.

## CVD / FLOW
Hesap değişikliği yok.
Araştırmada:
- trigger
- follow-through
- failed-trigger
- 5m confirmation delay
etiketleri ayrılacak.

## LOGGER
En yüksek öncelikli yeni alanlar:
- H7 extension alanları
- hypothesis setup/armed/trigger tag'leri
- event_group_id
- trigger_age_sec
- post-trigger follow-through flags

Bütün yeni alanlar SHADOW/RESEARCH amaçlı olmalı; production sinyalini otomatik değiştirmemelidir.
