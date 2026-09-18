# H1–H7 Log-Tabanlı Hipotez Güncellemesi — 2026-09-18

> Durum: **SHADOW / RESEARCH**
>
> Bu dosya production formüllerini değiştirmez. Structure v1.2, REALF production motoru ve CVD hesaplama mantığı sabit tutulur. Aşağıdaki değişiklikler yalnızca shadow hypothesis engine kurallarını ve araştırma önceliklerini günceller.

## 1. Neden bu güncelleme yapıldı?

Önceki H1–H7 seti büyük ölçüde teorik/ön araştırma hipotezleriydi. Yüklenen console logları doğrudan taranmadan eşiklere fazla anlam yüklenmişti.

Bu güncellemede loglar doğrudan ayrıştırıldı ve koşullar mümkün olduğunca ölçülebilir hale getirildi.

## 2. İncelenen ana veri

Ana run:

- Structure: **v1.2**
- Coin: **20**
- Snapshot: **4.957**
- Zaman: **2026-09-18 01:57:25 → 07:29:54**
- Coin başına tipik snapshot aralığı: yaklaşık **79 saniye**
- 1m flow eksik/kısmi oranı: yaklaşık **%0,20**
- 5m flow eksik/kısmi oranı: yaklaşık **%0,22**
- 15m flow eksik/kısmi oranı: yaklaşık **%0,79**
- Orderbook alanı eksikliği: yaklaşık **%1,0**

07:30 sonrasında ağ/DNS problemi başladı. 08:00 logunda turlar 20/20 hata ile dönüyor ve snapshot sayısı 4.957'de sabit kalıyor. Bu bölüm hipotez kanıtına dahil edilmedi.

### Outcome dosyası uyarısı

Yüklenen `outcomes.jsonl` ana 4.957-snapshot run ile aynı run değildir.

- Dosyada: **207** tamamlanmış outcome
- run_id: **20260917_214621**
- t0 aralığı: yaklaşık **21:46:40 → 22:01:26**
- Ana run ile birebir aynı snapshot seti değildir.

Ana run console sayacında 4.052 outcome üretildiği görülüyor; fakat bu run'a ait `outcomes.jsonl` dosyası yüklenen dosya değildir.

Bu nedenle aşağıdaki sonuçlar **resmî outcome-engine sonucu değildir**. Console snapshot fiyatlarından, aynı coin'in gelecekteki snapshot fiyatına bağlanarak yaklaşık +3m/+5m/+10m/+20m/+30m/+60m ileri getiriler yeniden üretildi.

### Event dedup

Aynı koşulun art arda gelen her snapshotını bağımsız örnek saymamak için aynı coin için **10 dakikalık cooldown/dedup** uygulandı.

Ayrıca gecenin genel yukarı yönlü driftini ayırmak amacıyla 5 dakikalık zaman kovalarında piyasa medyanına göre yaklaşık excess-return kontrolü yapıldı.

Bu yüzden bu rapordaki “yön doğru oranı” **win rate değildir**.

---

# 3. H1 v2 → H1 v2.1 — TREND PULLBACK LONG

## Log bulgusu

H1'in çok katı yorumunda 1m + 3m + 5m Fatigue'ın aynı anda <35 olması ve tüm diğer triggerların birlikte oluşması örnek sayısını aşırı düşürüyor.

Katı trigger:
- yalnızca yaklaşık **4 bağımsız event**

Daha pratik araştırma varyantı:
- HTF 15m/1h/4h bullish
- REALF 35–55
- RemainingUnpricedFlow >= 0
- 1m Fatigue <35
- CVD dönüş/eğim yukarı
- 5m flow kötüleşmiyor

Bu varyantta yaklaşık **17 bağımsız event** oluştu.

Log-tabanlı medyan hareket:
- +5m: **+0,105%**
- +10m: **+0,188%**
- +20m: **+0,186%**

Pozitif yön oranı:
- +5m: yaklaşık **%62**
- +10m: yaklaşık **%81**
- +20m: yaklaşık **%85**

Ancak örnek sayısı hâlâ küçük ve piyasanın genel yukarı driftinin etkisi var.

## H1 v2.1 kuralı

### CONTEXT

- 15m bullish
- 1h bullish
- 4h bullish

### RESET

Birincil reset:

- **1m Fatigue <35**

Güç artırıcı:

- 3m Fatigue <35
- 5m Fatigue <35

Artık 1m+3m+5m'nin aynı anda <35 olması zorunlu hard gate değildir.

### REALF

- 35–55 tercih
- RemainingUnpricedFlow >= 0 tercih

### TRIGGER

- 1m CVD turn UP **veya** pozitif CVD slope
- 5m flow negatifleşmiyor / CVD slope >= 0

### VETO

- yeni güçlü 5m BOS DN
- HTF bearish flip
- kötüleşen 5m flow
- partial/stale flow
- aşırı extension

### STATUS

**PROMISING / SAMPLE STILL LIMITED**

H1 production kuralı yapılmaz. Shadow test devam eder.

---

# 4. H2 v2 → H2 v2.1 — FLOW-LAG / REPRICING LONG

H2 bu log setinde en anlamlı kısa-vade repricing adaylarından biri olmaya devam ediyor.

## UnpricedFlow threshold testi

Shadow varyantlar:

- >0.003
- >0.005
- >0.010

>0.010 örnek sayısını çok küçülttü. Bu nedenle güçlü sonuçlar görünse bile eşik hard gate yapılmamalıdır.

## R² bulgusu

R² >0.45 önceki varsayımda tercih edilen eşikti.

Loglarda:
- >0.35 daha fazla örnek sağladı
- >0.45 net biçimde üstün görünmedi
- >0.55 bazı kısa-vade örneklerde iyi görünse de sample küçüldü ve 30m davranışı tutarlı değildi

Bu nedenle R²'yi tek başına keskin veto yapmak için veri yeterli değildir.

## Daha dengeli varyant

Koşullar:

- REALF <50
- RemainingUnpricedFlow >0.003
- Beta R² >0.35
- UnpricedFlow Δ1 >=0
- CVD 3m slope >0 veya turn UP
- CVD 5m delta >0
- Buyer Ratio iyileşiyor

Yaklaşık **39 bağımsız event**:

- +5m medyan: **+0,087%**
- +10m medyan: **+0,159%**
- +20m medyan: **+0,179%**

Pozitif yön:
- +5m yaklaşık **%68**
- +10m yaklaşık **%73**
- +20m yaklaşık **%60**

Piyasa-medyanına göre excess avantaj en belirgin şekilde ilk **5 dakika** civarında görüldü; 20–60 dakikada avantaj zayıflıyor.

## H2 v2.1 kuralı

### ARMED

- REALF <50
- RemainingUnpricedFlow > **+0.003**

Kalite katmanları:

- >+0.003 = minimum research candidate
- >+0.005 = preferred
- >+0.010 = strong-gap tag, **hard gate değil**

R²:

- >0.35 = minimum research quality
- >0.45 = preferred
- >0.55 = high-quality tag

### ZORUNLU DAVRANIŞ

UnpricedFlow yalnız LEVEL olarak okunmaz.

- LEVEL pozitif
- slope/Δ kötüleşmiyor

Gap küçülürken “yüksek gap var” diye long kurulmaz.

### TRIGGER

- 1m/3m CVD turn veya slope UP
- 5m CVD delta >0

### CONFIRMATION

- Buyer Ratio artışı
- 1m Buyer Ratio >50
- 5m CVD pozitifleşme/iyileşme

Buyer Ratio artışı kalite artırır; şimdilik hard gate değildir.

### HORIZON

H2 şu aşamada daha çok **5–10 dakikalık repricing** hipotezi olarak ele alınmalıdır.

30–60m continuation sonucu H2'nin görevi gibi yorumlanmamalıdır.

### STATUS

**MEDIUM RESEARCH SUPPORT**

---

# 5. H3 v2 → H3 v2.1 — BREAKOUT CONTINUATION

## En önemli log bulgusu

Eski mantık:

fresh BOS UP
+
pozitif 1m ve 5m flow
=
continuation trigger

Loglarda bu “hemen giriş” mantığı desteklenmedi.

Yaklaşık **49 bağımsız event**:

- +5m medyan: **-0,029%**
- +10m medyan: **-0,026%**
- +20m medyan: **+0,139%**
- +30m medyan: **+0,258%**
- +60m medyan: **+0,699%**

Piyasa-relative davranış da benzer:

- ilk 5–10m: negatif/geride
- 20–60m: iyileşiyor

Bu, fresh breakout sonrası ilk bölümde **pullback/retest riski** olduğunu düşündürüyor.

## H3 v2.1 değişikliği

H3 artık doğrudan ENTRY trigger değildir.

### BREAKOUT ARMED

- fresh 5m veya 15m BOS UP
- düşük event age
- anlamlı event strength
- yüksek structure confidence
- regime TR UP / EXP UP
- REALF aşırı price-ahead değil
- Fatigue aşırı değil

Bu aşamada sadece:

**H3_ARMED**

### RETEST BEKLE

Fresh BOS'ta pozitif 1m+5m flow görülmesi tek başına giriş değildir.

İkinci aşama aranır:

- kısa pullback/retest
- REALF tekrar 40–60 bandına yaklaşır
- Fatigue yükselmeyi bırakır / reset olur
- 1m CVD yeniden UP döner
- 5m CVD pozitif kalır veya yeniden güçlenir
- yeni CHOCH DN/BOS DN oluşmaz

Sonra:

**H3_REACCEL_TRIGGER**

Bu yeni retest/re-acceleration triggerı henüz doğrulanmış değildir; bir sonraki shadow test varyantıdır.

### STATUS

**OLD IMMEDIATE TRIGGER WEAKENED**

H3'ün breakout context kısmı korunur, “hemen continuation entry” kısmı kaldırılır.

---

# 6. H4 v2 → H4 v2.1 — EXHAUSTION / REVERSAL SHORT

## Log bulgusu

Fatigue >83 yine tek başına short değildir.

Daha geniş exhaustion + bearish flow/structure flip varyantında yaklaşık **17 bağımsız event**:

Short yönüne göre:

- +5m medyan fayda: yaklaşık **+0,045%**
- +10m: yaklaşık **-0,051%**
- +20m: yaklaşık **-0,050%**

Yani gözlenen etki daha çok **çok kısa mean-reversion** karakterinde.

Daha katı:
- 5m CVD negatif
- bearish flip
- yüksek fatigue

varyantında yalnız **4 bağımsız event** kaldı. İlk 5m iyi görünse de bu sayı eşik değiştirmek için yeterli değildir.

## H4 v2.1 kuralı

### CONTEXT

- Fatigue >83
- REALF >58 **veya** RemainingUnpricedFlow <0
- Fatigue düşmeye başlamış

### TRIGGER

- 1m CVD DOWN
- 3m/5m bearish structural flip

### STRONG TAG

- 5m CVD <0
- Buyer Ratio <50

### YENİ ZAMAN KURALI

H4 şimdilik:

**TACTICAL EXHAUSTION / 5m FOLLOW-THROUGH TEST**

olarak ele alınır.

Trigger sonrası ilk yaklaşık 5 dakikada aşağı follow-through oluşmazsa hipotezin short tarafı hızla zayıflamış kabul edilir.

HTF bearish dönüş oluşmadan H4, “sustained reversal short” olarak yorumlanmaz.

### STATUS

**SHORT-HORIZON ONLY / LIMITED SAMPLE**

---

# 7. H5 v2 — FAILED BOUNCE SHORT

Bu log setinde H5'in tam koşulları çok nadir oluştu.

Operationalize edilen kurallarda yalnız yaklaşık **2–3 bağımsız event** elde edildi.

Bu sample ile:

- threshold değiştirilmez
- yeni veto eklenmez
- research confidence yüzdesi güncellenmez

## H5 kararı

**H5 v2 AYNI KALIYOR.**

Ancak durum:

**INSUFFICIENT CURRENT DATA**

olarak işaretlenir.

---

# 8. H6 v1 → H6 v1.1 — MULTI-TF RESET SCANNER

H6 entry sistemi değildir; bu özellik korunuyor.

## Log bulgusu

RESET:

- 1m <30
- 3m <30
- 5m <30

10m dedup sonrası yaklaşık **38 bağımsız reset event**.

DEEP RESET:

- 1m <30
- 3m <30
- 5m <30
- 15m <35

yaklaşık **13 bağımsız event**.

Deep reset grubunda log-tabanlı:

- +5m medyan: **+0,157%**
- +10m medyan: **+0,138%**
- +20m medyan: **+0,315%**

Piyasa-medyanına göre yaklaşık excess:

- +5m: **+0,071%**
- +10m: **+0,096%**
- +20m: **+0,110%**

Bu davranış iki ayrı v1.2 log segmentinde de aynı yönde görünmüştür, ancak sample hâlâ küçüktür.

## H6 v1.1

### RESET

- 1m + 3m + 5m Fatigue <30

### DEEP RESET

- RESET
- 15m Fatigue <35

### ÇIKTI

H6 kendi başına LONG/SHORT üretmez.

Şu etiketleri üretir:

- H6_RESET
- H6_DEEP_RESET

Sonra candidate:

- H1 trend pullback
- H2 flow-lag repricing

motorlarına aktarılır.

Direction:

Structure + CVD + REALF tarafından belirlenir.

### STATUS

**PROMISING SCANNER / NOT AN ENTRY SYSTEM**

---

# 9. H7 v1 — PUMP / EXTENSION CONTEXT FILTER

H7'yi güncellemek için gerekli ana alanlar console logunda yok:

- 24h return
- 3d return
- 7d return
- local-base return
- ATR extension

RVOL ve Volume Percentile mevcut; fakat bunlar tek başına H7'yi test etmeye yetmez.

## H7 kararı

**H7 v1 AYNI KALIYOR — UNTESTED.**

Bir sonraki logger/snapshot datasetinde yukarıdaki alanlar zorunlu tutulmalı.

---

# 10. Güncel araştırma durumu

Eski yüzde biçimli “research confidence” değerleri bu log analizi sonrası **otomatik olarak artırılmayacak veya azaltılmayacak**.

Resmî ana-run outcome dosyası eşleşmeden yeni yüzde üretmek yanlış kesinlik yaratır.

Şimdilik:

| Hipotez | Durum |
|---|---|
| H1 v2.1 | Promising, sample limited |
| H2 v2.1 | Medium support, strongest at short repricing horizon |
| H3 v2.1 | Immediate trigger weakened; retest model required |
| H4 v2.1 | Short-horizon exhaustion only |
| H5 v2 | Insufficient data |
| H6 v1.1 | Promising scanner |
| H7 v1 | Untested due missing extension fields |

---

# 11. Production için kesin kural

Bu rapor sonucunda:

- Structure v1.2 değiştirilmez
- REALF production formülü değiştirilmez
- Fatigue formülü değiştirilmez
- CVD hesabı değiştirilmez
- production trade triggerına otomatik yeni eşik eklenmez

Tüm yeni kurallar:

**SHADOW HYPOTHESIS ENGINE**

içinde paralel test edilir.

---

# 12. Bir sonraki veri turunda zorunlu doğrulama

Yeni ana-run `outcomes.jsonl` yüklendiğinde:

1. snapshot_id birebir join
2. raw candidate sayısı
3. 10m dedup event sayısı
4. ARMED
5. TRIGGER
6. +1/+3/+5/+10/+20/+30/+60m
7. MFE / MAE
8. market-relative excess return
9. TOP100 / OUTSIDE100
10. regime
11. RVOL
12. HTF yönü
13. partial/stale flow ayrımı
14. OOS doğrulama

yeniden hesaplanmalıdır.

Özellikle test edilecek shadow varyantlar:

### H2
- U >0.003 / >0.005 / >0.010
- R² >0.35 / >0.45 / >0.55
- gap slope positive vs shrinking
- Buyer Ratio rise on/off

### H3
- immediate breakout trigger
- retest + CVD re-acceleration
- event-age bucket
- Fatigue <60 vs 60–72

### H4
- 5m follow-through
- 5m CVD negative hard/soft
- HTF flip var/yok

### H6
- RESET
- DEEP RESET
- sonrasında H1/H2'ye dönüşüm oranı

---

## Ana sonuç

Loglar incelendiğinde en önemli değişiklik eşiklerin rastgele artırılıp azaltılması değil, **hipotezlerin zamanlama mantığının ayrıştırılmasıdır**:

- H2 = kısa-vade repricing
- H3 = breakout anında chase değil; breakout → retest → re-acceleration
- H4 = sustained reversal değil; önce kısa exhaustion/follow-through testi
- H6 = entry değil; reset candidate generator

Bu yapı yeni veri geldikçe versiyonlanacaktır.
