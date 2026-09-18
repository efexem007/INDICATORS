# CANLI STRATEJİ ARAŞTIRMA HİPOTEZLERİ
## Güncel Sürüm — 2026-09-17

> **Amaç:** Fatigue, Structure, REALF ve gerçek order-flow/CVD verilerini birlikte kullanarak **AL / SAT strateji aileleri** geliştirmek.
>
> Bu dokümandaki yüzdeler **win-rate değildir**. Her hipotezin şu anki **araştırma / kanıt gücünü** gösterir.
>
> Hipotezler sabit değildir. Yeni log, skor ve outcome verisi geldikçe sürüm yükseltilir:
> `H1 v2 → H1 v2.1 → H1 v3` gibi.

---

# 1. ANA MİMARİ

Sistemde her indikatörün görevi farklıdır:

### FATIGUE
**Görev:** Tarama / aday bulma / hareketin ne kadar uzadığını ölçme.

- Düşük Fatigue = hareket dinlenmiş / resetlenmiş olabilir.
- Yüksek Fatigue = hareket uzamış / yorulmuş olabilir.
- **Tek başına AL veya SAT üretmez.**
- Düşük Fatigue sert düşüşün ortasında da görülebilir.
- Yüksek Fatigue güçlü trend sırasında uzun süre yüksek kalabilir.

### STRUCTURE
**Görev:** Piyasa yapısı, yön, rejim ve setup türünü belirleme.

Kullanılacak ana alanlar:

- State
- Score
- BOS / CHOCH
- Event age
- Event strength
- Regime
- Confidence
- External / Internal swing sequence
- Protected level
- EQH / EQL
- Sweep

Structure tek başına tahmin motoru olarak değil, **context / setup classifier** olarak kullanılacaktır.

### REALF
**Görev:** Fiyat ile akış arasındaki fiyatlama farkını ölçmek.

Özellikle:

- REALF score
- RemainingUnpricedFlow
- RemainingUnpricedFlow slope
- Beta R²
- Component agreement
- Flow-implied price
- REALF delta / slope

Ana fikir:

- `RemainingUnpricedFlow > 0` → akış fiyatın önünde olabilir.
- `RemainingUnpricedFlow < 0` → fiyat akışın önünde olabilir.
- REALF tek başına AL/SAT değildir.

### CVD / BUYER RATIO / ORDER FLOW
**Görev:** Giriş zamanlaması / gerçek akış teyidi.

Sadece CVD'nin seviyesine değil:

- CVD level
- CVD delta
- CVD slope
- CVD turn
- Buyer ratio
- Flow confidence
- Window completeness

birlikte bakılacaktır.

Rol dağılımı:

- **1m CVD:** hızlı tetik
- **5m CVD:** kısa vadeli doğrulama
- **15m CVD:** ana flow context

---

# 2. ANA DURUM MAKİNESİ

Bir coin doğrudan `BUY` veya `SELL` olmaz.

Önerilen durum akışı:

```text
SCAN
  ↓
SETUP
  ↓
ARMED
  ↓
TRIGGER
  ↓
ENTRY
  ↓
MANAGE / EXIT
```

### SCAN
Fatigue veya başka tarayıcı coin'i aday havuzuna alır.

### SETUP
Structure + REALF coin'in anlamlı bir setup içinde olduğunu gösterir.

### ARMED
Setup hazırdır fakat gerçek akış teyidi henüz tamamlanmamıştır.

### TRIGGER
CVD / Buyer Ratio / Structure event gibi anlık tetik oluşur.

### ENTRY
Strateji kuralları tamamlanır.

---

# 3. H1 v2 — TREND PULLBACK LONG

## Araştırma gücü
**%63**

## Ana fikir

Üst zaman diliminde yükseliş yapısı devam ederken kısa zaman diliminde fiyat geri çekilir ve Fatigue yeniden düşer.

Amaç:

> Ana trend içinde geri çekilme bittikten sonra yeni yükseliş ayağını yakalamak.

## SETUP

Tercihen:

```text
15m / 1h / 4h Structure bullish context
+
3m ve/veya 5m Fatigue < 30–35
+
REALF yaklaşık 35–55
+
fiyat aşırı uzamış değil
```

Üst TF için özellikle:

- BULL
- TR-UP
- BOS UP
- CHOCH UP sonrası trend doğrulaması

olumlu kabul edilir.

## ARMED

Aşağıdakilerden birkaçı birlikte görülürse:

```text
Üst TF bullish
+
Alt TF bearish/pullback
+
5m veya 15m Fatigue düşük
+
REALF fair / flow-ahead
+
RemainingUnpricedFlow >= 0
```

## TRIGGER

Erken tetik:

```text
1m CVD slope DOWN → UP
```

veya

```text
1m Structure CHOCH UP
```

Güçlü tetik:

```text
1m CVD iyileşmesi
+
5m CVD slope iyileşmesi
+
5m Structure bearish baskının zayıflaması
```

## Kalite artırıcılar

- 5m flow confidence yüksek
- 15m flow complete
- Orderbook satış baskısı azalıyor
- Protected low yakınında tepki
- EQL sweep sonrası geri kazanım
- REALF aşağıdan yukarı dönüyor
- UnpricedFlow pozitif

## Veto / risk

- Yeni güçlü 5m BOS DN
- 15m/1h yapının tamamen bear'e dönmesi
- 5m CVD hızla kötüleşmesi
- Pump/extension çok yüksek
- Partial flow penceresini tam sinyal gibi kullanmak
- Fatigue düşük diye kör AL

---

# 4. H2 v2 — FLOW-LAG / REPRICING LONG

## Araştırma gücü
**%68**

Şu an en güçlü spesifik hipotezlerden biridir.

## Ana fikir

Gerçek/ölçülen akış fiyatın önüne geçmiştir fakat fiyat henüz bu akışı tam fiyatlamamıştır.

Amaç:

> Flow ile fiyat arasındaki fark kapanırken oluşan repricing hareketini yakalamak.

## SETUP

Ana koşullar:

```text
REALF < 50 tercih
+
RemainingUnpricedFlow > +0.005
+
Beta R² yeterli
+
REALF source / agreement kabul edilebilir
```

Güçlü aday:

```text
RemainingUnpricedFlow > +0.010
```

fakat tek başına yeterli değildir.

## Yeni önemli geliştirme: UnpricedFlow SLOPE

Sadece seviye değil, yönü de ölçülecek.

### Fırsat büyüyor

```text
+0.003
+0.005
+0.008
+0.012
```

Bu güçlü pozitif davranıştır.

### Fırsat kapanıyor

```text
+0.014
+0.013
+0.012
+0.010
```

Hâlâ pozitif olsa bile repricing farkı daralıyor olabilir.

Bu nedenle H2'de:

```text
UnpricedFlow level
+
UnpricedFlow slope
```

birlikte kullanılacaktır.

## ARMED

```text
REALF düşük/fair
+
UnpricedFlow pozitif
+
Fatigue aşırı yüksek değil
+
Structure tamamen karşı yönde güçlü değil
```

## TRIGGER

Erken:

```text
1m CVD slope negatiften pozitife
```

Güçlü:

```text
1m CVD turn UP
+
5m CVD delta iyileşiyor
+
Buyer Ratio yükseliyor
```

15m CVD'nin sıfırı geçmesi zorunlu değildir.

## Kalite artırıcılar

- R² > yaklaşık 0.45
- Flow confidence 5m > 60–70
- Flow complete = true
- 1m ve 5m CVD slope aynı yönde
- REALF delta yukarı
- Structure transition-up / bullish context
- Orderbook imbalance alıcı lehine

## Veto / risk

- UnpricedFlow hızla küçülüyor
- 5m CVD daha da negatife gidiyor
- REALF yükselirken flow desteği kayboluyor
- R² çok düşük
- Flow data partial
- Structure yeni güçlü BOS DN üretiyor

---

# 5. H3 v2 — BREAKOUT CONTINUATION LONG

## Araştırma gücü
**%50**

## Ana fikir

Yeni bir yapısal kırılımın gerçek akış desteğiyle devam etmesi.

Sadece BOS UP yeterli kabul edilmez.

## SETUP

```text
5m veya 15m BOS UP
+
event age düşük
+
event strength anlamlı
+
Structure confidence yüksek
+
Fatigue tercihen < 72
```

Tercihen:

```text
REGIME = EXP UP veya TR UP
```

## TRIGGER

```text
1m CVD pozitif
+
5m CVD pozitif / güçleniyor
+
Buyer Ratio destekliyor
```

Güçlü versiyon:

```text
BOS UP
+
5m CVD slope > 0
+
15m flow pozitif
+
REALF 40–60
```

## Neden REALF 40–60 tercih?

Breakout sırasında REALF çok yüksekse fiyat zaten akışın fazla önüne geçmiş olabilir.

Bu yüzden breakout için:

```text
REALF 40–60
```

daha sağlıklı bir başlangıç alanı olarak test edilecektir.

## Veto / risk

- REALF > 70
- Fatigue > 83
- BOS event çok eski
- 5m CVD negatif
- Orderbook güçlü satış baskısı
- Breakout sonrası hızlı CHOCH DN
- Expansion yokken sadece eski BOS'a güvenmek

---

# 6. H4 v2 — EXHAUSTION / REVERSAL SHORT

## Araştırma gücü
**%62**

## Ana fikir

Tepeyi tahmin etmek değil.

> Yükseliş önce yorulacak, sonra gerçekten bozulacak.

Bu nedenle:

```text
Fatigue > 83 = SHORT
```

kuralı kullanılmayacaktır.

## SETUP

Önce:

```text
Fatigue > 83
```

ve tercihen:

```text
REALF > 58
veya
RemainingUnpricedFlow < 0
```

Sonra Fatigue yüksekten çözülmeye başlar.

## ARMED

```text
Fatigue yüksekten düşüyor
+
REALF Price Ahead
+
CVD gücü zayıflıyor
```

## TRIGGER

Erken:

```text
1m CVD turn DOWN
```

Güçlü:

```text
1m CVD DOWN
+
3m/5m Structure CHOCH DN veya BOS DN
```

Daha güçlü:

```text
5m CVD de negatife geçiyor
+
REALF hâlâ Price Ahead
```

## Kalite artırıcılar

- Buyer Ratio hızlı düşüyor
- Orderbook satış baskısı artıyor
- High sweep sonrası geri dönüş
- EQH sweep
- Fatigue >83 sonrası negatif slope
- REALF >70
- UnpricedFlow negatif

## Veto

- 5m CVD hâlâ çok güçlü pozitif
- Structure bozulmamış
- 15m EXP UP devam ediyor
- Buyer Ratio sürekli yüksek
- Sadece Fatigue yüksek diye short açmak

---

# 7. H5 v2 — FAILED BOUNCE SHORT

## Araştırma gücü
**%45**

Henüz zayıf-orta düzey hipotezdir.

## Ana fikir

Ana yapı bearish iken fiyat kısa süre toparlanır fakat gerçek akış bu tepkiyi desteklemez.

Sonra düşüş yeniden başlar.

## SETUP

```text
15m / 1h Structure bearish
+
alt TF Fatigue dipten toparlanıyor
+
tepki yükselişi geliyor
```

Ancak:

```text
REALF repricing üretmiyor
veya
CVD zayıf kalıyor
```

## TRIGGER

```text
1m CVD tekrar DOWN
+
1m/3m Structure yeniden bearish
```

Güçlü:

```text
5m CVD yeniden negatife dönüyor
+
yeni BOS DN
```

## Veto

- 5m/15m CVD güçlü pozitife dönmesi
- 15m Structure bullish dönüş
- REALF güçlü Flow Ahead
- RemainingUnpricedFlow hızla pozitif büyüyor

---

# 8. H6 v1 — MULTI-TF RESET SCANNER

## Araştırma gücü
**%60**

Bu doğrudan trading stratejisi değildir.

Bir **aday coin bulma sistemi**dir.

## Ana fikir

Birden fazla kısa zaman diliminde Fatigue düşükse coin yeniden hareket etmeye hazır olabilir.

## Güçlü reset örneği

```text
1m < 30
3m < 30
5m < 30
```

Daha güçlü:

```text
1m < 30
3m < 30
5m < 30
15m < 30–35
```

## Çıktı

Coin doğrudan BUY olmaz.

Şuraya gönderilir:

```text
H1 Trend Pullback
veya
H2 Flow-Lag Repricing
```

## Kritik ders

Düşük Fatigue:

```text
= enerji / uzama sıfırlanmış olabilir
```

ama:

```text
≠ fiyat kesin yukarı gider
```

Düşüşün ortasında da düşük Fatigue görülebilir.

---

# 9. H7 v1 — PUMP / EXTENSION CONTEXT FILTER

## Durum
**Araştırma filtresi — hard veto değil**

## Amaç

Fatigue düşük olsa bile coin yakın geçmişte aşırı yükselmiş olabilir.

Bunun strateji performansına etkisini ölçmek.

## Kaydedilecek alanlar

- 24h return
- 3d return
- 7d return
- local-base return
- ATR extension
- RVOL
- volume percentile

## Araştırılacak gruplar

Örneğin:

```text
Fatigue < 30
+
24h return < +5%
```

ile:

```text
Fatigue < 30
+
24h return > +20%
```

ayrı ayrı test edilecek.

## Şimdilik

```text
Pump yüksek = otomatik ele
```

yapılmayacaktır.

Önce outcome verisiyle gerçek etkisi ölçülecektir.

---

# 10. CVD İÇİN GELİŞMİŞ KULLANIM

Sadece:

```text
CVD > 0
```

veya

```text
CVD < 0
```

bakılmayacak.

Ayrı özellikler:

```text
CVD_LEVEL
CVD_DELTA
CVD_SLOPE
CVD_TURN
BUYER_RATIO
FLOW_CONFIDENCE
WINDOW_COMPLETE
```

## Örnek

5m CVD:

```text
-120k
-95k
-70k
-50k
```

hâlâ negatiftir.

Ama satış baskısı hızla çözülmektedir.

Bu durum:

```text
CVD level negatif
ama
CVD slope pozitif
```

olarak ayrı değerlendirilecektir.

Bu erken dönüş yakalamada önemlidir.

---

# 11. STRUCTURE İÇİN GELİŞMİŞ KULLANIM

Sadece:

```text
BULL
BEAR
```

kullanılmayacak.

Aşağıdakiler birlikte değerlendirilecektir:

```text
STATE
EVENT
EVENT_AGE
EVENT_STRENGTH
REGIME
CONFIDENCE
EXT_SEQUENCE
INT_SEQUENCE
PROTECTED_LEVEL_DISTANCE_ATR
EQH_DISTANCE
EQL_DISTANCE
SWEEP_EVENT
SWEEP_AGE
```

## Özellikle event age

```text
BOS UP 3 bar önce
```

ile

```text
BOS UP 50 bar önce
```

aynı ağırlıkta kullanılmayacaktır.

Yeni/fresh event daha değerlidir.

---

# 12. FLOW DATA KALİTE KURALLARI

## Zorunlu

```text
FLOW_1M_COMPLETE
FLOW_5M_COMPLETE
FLOW_15M_COMPLETE
```

## Kural

Bir pencere `KISMİ / PARTIAL` ise:

- karar motorunda tam teyit sayılmayacak
- alarm üretiminde düşük ağırlık alacak
- yalnız context olarak tutulacak

## Confidence

Flow confidence özellikle:

- trade count
- effective sample
- notional
- coverage
- freshness

ile birlikte değerlendirilmelidir.

---

# 13. GÜNCEL HİPOTEZ GÜÇ TABLOSU

> Bunlar **win-rate değildir**.

| Hipotez | Sürüm | Araştırma Gücü | Durum |
|---|---:|---:|---|
| Trend Pullback Long | H1 v2 | **%63** | Güçleniyor |
| Flow-Lag Repricing Long | H2 v2 | **%68** | Şu an en güçlü spesifik long hipotezi |
| Breakout Continuation | H3 v2 | **%50** | Daha fazla filtre gerekli |
| Exhaustion Reversal Short | H4 v2 | **%62** | Short tarafında güçlü aday |
| Failed Bounce Short | H5 v2 | **%45** | Daha çok veri gerekli |
| Multi-TF Reset Scanner | H6 v1 | **%60** | Aday bulmada yararlı |
| Ana mimari | — | **%75** | Şu an en güçlü genel çıkarım |

---

# 14. ŞU ANKİ EN ÖNEMLİ LONG ÇEKİRDEĞİ

Şimdilik en değerli araştırma kombinasyonu:

```text
Üst TF bullish Structure
+
kısa TF düşük Fatigue
+
REALF düşük / fair
+
RemainingUnpricedFlow pozitif
+
1m CVD slope dönüşü
+
5m CVD iyileşmesi
```

Durum akışı:

```text
Fatigue düşük
    ↓
Structure setup uygun
    ↓
REALF fırsat gösteriyor
    ↓
ARMED
    ↓
1m CVD turn-up
    ↓
EARLY TRIGGER
    ↓
5m CVD teyidi
    ↓
STRONG ENTRY CANDIDATE
```

---

# 15. ŞU ANKİ EN ÖNEMLİ SHORT ÇEKİRDEĞİ

```text
Fatigue önce aşırı yüksek
+
REALF Price Ahead
+
Fatigue yüksekten çözülmeye başlıyor
+
1m CVD turn DOWN
+
Structure CHOCH DN / BOS DN
+
5m CVD teyidi
```

Ama:

```text
Fatigue > 83
```

tek başına short değildir.

---

# 16. YENİ VERİ GELDİĞİNDE GÜNCELLEME PROTOKOLÜ

Her yeni log geldiğinde:

1. Mevcut hipotez sürümü yeni dataya uygulanır.
2. Hangi şartların çalıştığı/çalışmadığı incelenir.
3. Yeni istisnalar bulunur.
4. Yeni filtre adayları oluşturulur.
5. Sinyal sayısını artırmak yerine kötü setup'ları elemek hedeflenir.
6. Gerekiyorsa hipotez sürümü yükseltilir.
7. Eski sürüm ile yeni sürüm karşılaştırılır.

Örnek:

```text
H2 v2
↓
Yeni veri: negatif örnekler pump sonrası geliyor
↓
24h extension context eklenir
↓
H2 v2.1
```

Her değişiklikte:

- ne değişti
- neden değişti
- hangi veri gösterdi
- eski güç
- yeni güç
- hangi koşul eklendi/çıkarıldı

kaydedilecektir.

---

# 17. OVERFIT KORUMASI

Hipotezler gelişecek fakat her yeni örneğe göre rastgele değiştirilmeyecek.

Bir koşulun kalıcı hale gelmesi için tercihen:

```text
30+ bağımsız olay → ilk anlamlı değerlendirme
50+ olay → daha ciddi kıyaslama
100+ olay + farklı gün/rejim → strateji adayı
```

Ayrıca:

- aynı coin'deki çok yakın snapshotlar bağımsız örnek sayılmayacak
- holdout / OOS test yapılacak
- maliyet/slippage eklenecek
- farklı market cap / likidite / rejim grupları ayrı test edilecek

---

# 18. SONUÇ

Şu anda sistemdeki ana mantık:

```text
FATIGUE
→ hangi coin hazır olabilir?

STRUCTURE
→ hangi yapı / yön / setup içindeyiz?

REALF
→ fiyatlama boşluğu var mı?

CVD + BUYER RATIO + ORDERBOOK
→ hareket gerçekten şimdi başlıyor mu?
```

Tek bir "süper skor" yerine:

```text
SETUP CLASSIFIER
+
OPPORTUNITY MODEL
+
TIMING MODEL
+
TRIGGER MODEL
```

yaklaşımı kullanılacaktır.

Ana hedef:

> **Daha çok sinyal üretmek değil, kötü sinyalleri azaltıp yüksek kaliteli setup sayısını artırmak.**
