# Hipotez kullanım kılavuzu

Tur 4 · run_20260918_112149 · menü `hypothesis-candidates-v2.4` · 2026-09-18T19:39:15Z

Bu kılavuz her turda ölçümden yeniden üretilir; hipotez geliştikçe kendisi de gelişir.
Sayılar **gözlenen davranıştır**, kâr vaadi değildir. Maliyet varsayımı toplam 10 bps; gerçekleşmiş komisyon/funding değildir.

**Kanıt seviyesi nasıl okunur:** kanıt 10 dakikalık kümede sayılır, ham olayda değil — aynı kovadaki olaylar birlikte hareket eder. Bir aday ancak karar ufkunda TRAIN ve HOLDOUT excess pozitifken ve holdout 30+ kümeye ulaştığında ADAY olur. Uzun süren bir kayıt çok küme, kısa kayıt az küme ekler; kısa kayıt tek başına karar değiştirmez, yalnız kanıta eklenir.

## H8_IGNITION_QUIET — YETERSIZ

*H8 ateşleme + öncesinde sıkışık 1m ATR (medyan altı)*

- **Karar ufku:** 20 dk (ölçülen medyan tepe 58 dk)
- **En güçlü hareket:** medyan 58 dakikada; tipik MFE %0.76, tipik MAE %-0.35 → ödül/risk **2.2**
- **Geri verme:** tepeden ufuk sonuna medyan %0.12; en kötü an medyan 10. dakikada
- **İlk karşıt akış sinyali:** medyan 7. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %48 · net medyan -0.0384 · excess TRAIN -0.1824 / HOLDOUT -0.2625
- **Kanıt:** 25 olay / 19 küme; holdout 6 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Hacim: realf_rvol >= 1.35 (bu runın p90 değeri)
  - Alıcı baskınlığı: buyer_ratio_1m >= 80 (p90)
  - CVD: cvd_1m_pct > 0
  - KAPI YOK: REALF bandı, yapı kırılımı, yorgunluk ve unpriced şartı bilerek aranmaz

**Plan:** `PULLBACK_25` + `ATR_GIVEBACK` — aynı olaylarda taban plana göre **+0.437** (eşleşme 9), dolum %36.0, isabet %22.2, çıkış ~20. dakika.

**Hangi coinlerde:** en iyi → BUYUK/OYNAK (net +0.09, isabet %67, 3 dolum), KUCUK/SAKIN (net +0.05, isabet %50, 12 dolum).
En kötü → BUYUK/SAKIN (net +0.01, isabet %50, 4 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H8_IGNITION — YETERSIZ

*H8 ateşleme: hacim+alıcı patlaması; REALF/yapı/fatigue kapısı YOK*

- **Karar ufku:** 20 dk (ölçülen medyan tepe 58 dk)
- **En güçlü hareket:** medyan 58 dakikada; tipik MFE %0.79, tipik MAE %-0.35 → ödül/risk **2.2**
- **Geri verme:** tepeden ufuk sonuna medyan %0.16; en kötü an medyan 10. dakikada
- **İlk karşıt akış sinyali:** medyan 6. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %50 · net medyan +0.0216 · excess TRAIN -0.1592 / HOLDOUT -0.1851
- **Kanıt:** 34 olay / 18 küme; holdout 6 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Hacim: realf_rvol >= 1.35 (bu runın p90 değeri)
  - Alıcı baskınlığı: buyer_ratio_1m >= 80 (p90)
  - CVD: cvd_1m_pct > 0
  - KAPI YOK: REALF bandı, yapı kırılımı, yorgunluk ve unpriced şartı bilerek aranmaz

**Plan:** `PULLBACK_25` + `HOLD_HORIZON` — aynı olaylarda taban plana göre **+0.270** (eşleşme 12), dolum %35.3, isabet %33.3, çıkış ~21. dakika.

**Hangi coinlerde:** en iyi → KUCUK/OYNAK (net +0.42, isabet %83, 6 dolum), BUYUK/OYNAK (net +0.09, isabet %67, 3 dolum).
En kötü → KUCUK/SAKIN (net -0.06, isabet %46, 13 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H1_BASE — YETERSIZ

*H1 mevcut shadow tanımı*

- **Karar ufku:** 60 dk (ölçülen medyan tepe 30 dk)
- **En güçlü hareket:** medyan 30 dakikada; tipik MFE %0.66, tipik MAE %-0.25 → ödül/risk **2.6**
- **Geri verme:** tepeden ufuk sonuna medyan %0.45; en kötü an medyan 29. dakikada
- **İlk karşıt akış sinyali:** medyan 7. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %64 · net medyan +0.1890 · excess TRAIN -0.2344 / HOLDOUT +0.1035
- **Kanıt:** 39 olay / 17 küme; holdout 5 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Yorgunluk: fat_3m veya fat_5m < 35 (sıfırlanmış)
  - Bağlam: HTF bull (15m/1h yukarı)
  - REALF: skor 35–55 bandı
  - Fiyatlanmamış akış: unpriced >= 0
  - Akış/yapı: akış UP ya da taze 1m UP yapı olayı
  - CVD: 5 dk CVD deltası pozitif

**Plan:** `PULLBACK_25` + `HOLD_HORIZON` — aynı olaylarda taban plana göre **+0.625** (eşleşme 8), dolum %20.5, isabet %37.5, çıkış ~61. dakika.

**Hangi coinlerde:** en iyi → BUYUK/OYNAK (net +0.32, isabet %67, 3 dolum), BUYUK/SAKIN (net +0.28, isabet %78, 9 dolum).
En kötü → ORTA/OYNAK (net -0.77, isabet %33, 9 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H2_FLOW_CONFIRM — YETERSIZ

*H2 + 5m CVD slope>0 ve flow confidence5m>=60*

- **Karar ufku:** 60 dk (ölçülen medyan tepe 36 dk)
- **En güçlü hareket:** medyan 36 dakikada; tipik MFE %1.08, tipik MAE %-0.36 → ödül/risk **3.0**
- **Geri verme:** tepeden ufuk sonuna medyan %0.79; en kötü an medyan 26. dakikada
- **İlk karşıt akış sinyali:** medyan 6. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %65 · net medyan +0.1987 · excess TRAIN -0.0329 / HOLDOUT +0.3232
- **Kanıt:** 20 olay / 17 küme; holdout 6 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Fiyatlanmamış akış: realf_unpriced_flow > 0.005 (gap açık)
  - REALF: skor < 50 (fiyat henüz gitmemiş)
  - REALF kalite: beta R² > 0.45 ve bileşen uyumu > 0.5
  - Yorgunluk: fat_1m < 83
  - Yapı: taze 5m DN olayı yok
  - Akış: akış UP, 5 dk CVD deltası pozitif, 1 dk alıcı oranı yükseliyor

**Plan:** `CONFIRM_3M` + `ATR_GIVEBACK` — aynı olaylarda taban plana göre **+0.090** (eşleşme 10), dolum %55.0, isabet %54.5, çıkış ~12. dakika.

**Hangi coinlerde:** en iyi → BUYUK/OYNAK (net +0.76, isabet %75, 4 dolum), ORTA/OYNAK (net +0.76, isabet %60, 5 dolum).
En kötü → BUYUK/SAKIN (net +0.08, isabet %67, 3 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H1_FLOW_MIXED — YETERSIZ

*H1 + cvd_1m ile cvd_5m ters işarette (çelişki bölgesi ayrı ölçülür)*

- **Karar ufku:** 60 dk (ölçülen medyan tepe 35 dk)
- **En güçlü hareket:** medyan 35 dakikada; tipik MFE %0.76, tipik MAE %-0.28 → ödül/risk **2.7**
- **Geri verme:** tepeden ufuk sonuna medyan %0.36; en kötü an medyan 23. dakikada
- **İlk karşıt akış sinyali:** medyan 5. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %70 · net medyan +0.3689 · excess TRAIN -0.2344 / HOLDOUT +0.1399
- **Kanıt:** 27 olay / 17 küme; holdout 6 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Yorgunluk: fat_3m veya fat_5m < 35 (sıfırlanmış)
  - Bağlam: HTF bull (15m/1h yukarı)
  - REALF: skor 35–55 bandı
  - Fiyatlanmamış akış: unpriced >= 0
  - Akış/yapı: akış UP ya da taze 1m UP yapı olayı
  - CVD: 5 dk CVD deltası pozitif

**Plan:** taban plan (`AT_TRIGGER` + `HOLD_HORIZON`) bu adayda en iyisi; denenen erken çıkışların hiçbiri 20 eşleşmede onu geçmedi.

**Hangi coinlerde:** en iyi → BUYUK/SAKIN (net +0.35, isabet %83, 6 dolum), BUYUK/OYNAK (net +0.32, isabet %67, 3 dolum).
En kötü → ORTA/OYNAK (net -0.53, isabet %14, 7 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H1_CONF_FLOOR — YETERSIZ

*H1 + flow_confidence_5m >= 50 (yapısal zayıf ölçümlü coinler dışarıda)*

- **Karar ufku:** 60 dk (ölçülen medyan tepe 31 dk)
- **En güçlü hareket:** medyan 31 dakikada; tipik MFE %0.70, tipik MAE %-0.26 → ödül/risk **2.7**
- **Geri verme:** tepeden ufuk sonuna medyan %0.45; en kötü an medyan 25. dakikada
- **İlk karşıt akış sinyali:** medyan 6. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %68 · net medyan +0.2629 · excess TRAIN -0.2164 / HOLDOUT -0.0069
- **Kanıt:** 37 olay / 17 küme; holdout 5 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Yorgunluk: fat_3m veya fat_5m < 35 (sıfırlanmış)
  - Bağlam: HTF bull (15m/1h yukarı)
  - REALF: skor 35–55 bandı
  - Fiyatlanmamış akış: unpriced >= 0
  - Akış/yapı: akış UP ya da taze 1m UP yapı olayı
  - CVD: 5 dk CVD deltası pozitif

**Plan:** `PULLBACK_25` + `PEAK_TIME` — aynı olaylarda taban plana göre **+0.616** (eşleşme 10), dolum %29.7, isabet %63.6, çıkış ~32. dakika.

**Hangi coinlerde:** en iyi → BUYUK/OYNAK (net +0.32, isabet %67, 3 dolum), BUYUK/SAKIN (net +0.28, isabet %78, 9 dolum).
En kötü → ORTA/OYNAK (net -0.77, isabet %22, 9 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H2_GAP_EXPANDS — YETERSIZ

*H2 + UnpricedFlow delta3m>=0*

- **Karar ufku:** 60 dk (ölçülen medyan tepe 30 dk)
- **En güçlü hareket:** medyan 30 dakikada; tipik MFE %0.73, tipik MAE %-0.41 → ödül/risk **1.8**
- **Geri verme:** tepeden ufuk sonuna medyan %0.48; en kötü an medyan 26. dakikada
- **İlk karşıt akış sinyali:** medyan 7. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %61 · net medyan +0.0995 · excess TRAIN -0.1704 / HOLDOUT +0.2451
- **Kanıt:** 23 olay / 16 küme; holdout 6 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Fiyatlanmamış akış: realf_unpriced_flow > 0.005 (gap açık)
  - REALF: skor < 50 (fiyat henüz gitmemiş)
  - REALF kalite: beta R² > 0.45 ve bileşen uyumu > 0.5
  - Yorgunluk: fat_1m < 83
  - Yapı: taze 5m DN olayı yok
  - Akış: akış UP, 5 dk CVD deltası pozitif, 1 dk alıcı oranı yükseliyor

**Plan:** `CONFIRM_3M` + `ATR_GIVEBACK` — aynı olaylarda taban plana göre **+0.195** (eşleşme 10), dolum %43.5, isabet %60.0, çıkış ~17. dakika.

**Hangi coinlerde:** en iyi → BUYUK/OYNAK (net +0.37, isabet %75, 4 dolum), BUYUK/SAKIN (net +0.12, isabet %67, 3 dolum).
En kötü → ORTA/OYNAK (net -0.32, isabet %20, 5 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H2_BASE — YETERSIZ

*H2 mevcut shadow tanımı*

- **Karar ufku:** 60 dk (ölçülen medyan tepe 38 dk)
- **En güçlü hareket:** medyan 38 dakikada; tipik MFE %0.73, tipik MAE %-0.35 → ödül/risk **2.1**
- **Geri verme:** tepeden ufuk sonuna medyan %0.41; en kötü an medyan 23. dakikada
- **İlk karşıt akış sinyali:** medyan 7. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %65 · net medyan +0.2409 · excess TRAIN -0.1115 / HOLDOUT +0.4412
- **Kanıt:** 26 olay / 15 küme; holdout 7 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Fiyatlanmamış akış: realf_unpriced_flow > 0.005 (gap açık)
  - REALF: skor < 50 (fiyat henüz gitmemiş)
  - REALF kalite: beta R² > 0.45 ve bileşen uyumu > 0.5
  - Yorgunluk: fat_1m < 83
  - Yapı: taze 5m DN olayı yok
  - Akış: akış UP, 5 dk CVD deltası pozitif, 1 dk alıcı oranı yükseliyor

**Plan:** taban plan (`AT_TRIGGER` + `HOLD_HORIZON`) bu adayda en iyisi; denenen erken çıkışların hiçbiri 18 eşleşmede onu geçmedi.

**Hangi coinlerde:** en iyi → ORTA/SAKIN (net +0.44, isabet %67, 3 dolum), BUYUK/OYNAK (net +0.32, isabet %80, 5 dolum).
En kötü → ORTA/OYNAK (net -0.12, isabet %40, 5 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H5_BASE — YETERSIZ

*H5 mevcut shadow tanımı*

- **Karar ufku:** 20 dk (ölçülen medyan tepe 15 dk)
- **En güçlü hareket:** medyan 15 dakikada; tipik MFE %0.33, tipik MAE %-1.06 → ödül/risk **0.3**
- **Geri verme:** tepeden ufuk sonuna medyan %0.91; en kötü an medyan 44. dakikada
- **İlk karşıt akış sinyali:** medyan 6. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %45 · net medyan -0.0948 · excess TRAIN +0.0052 / HOLDOUT -0.0567
- **Kanıt:** 20 olay / 15 küme; holdout 5 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Bağlam: HTF bear
  - Sıçrama: yakın geçmişte tepki yükselişi
  - Fiyatlanmamış akış: güçlü pozitif gap yok (unpriced <= 0.005)
  - CVD: cvd_5m < 0
  - Akış: akış DOWN
  - Yapı: 1m veya 3m durum DN

**Plan:** `CONFIRM_3M` + `PEAK_TIME` — aynı olaylarda taban plana göre **+0.021** (eşleşme 8), dolum %40.0, isabet %25.0, çıkış ~16. dakika.

**Hangi coinlerde:** en iyi → ORTA/OYNAK (net +0.20, isabet %56, 9 dolum), KUCUK/SAKIN (net -0.27, isabet %20, 5 dolum).
En kötü → KUCUK/SAKIN (net -0.27, isabet %20, 5 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H1_FLOW_AGREE — YETERSIZ

*H1 + cvd_1m ve cvd_5m ikisi de pozitif (akış pencereleri uyumlu)*

- **Karar ufku:** 60 dk (ölçülen medyan tepe 23 dk)
- **En güçlü hareket:** medyan 23 dakikada; tipik MFE %0.64, tipik MAE %-0.22 → ödül/risk **2.8**
- **Geri verme:** tepeden ufuk sonuna medyan %0.50; en kötü an medyan 30. dakikada
- **İlk karşıt akış sinyali:** medyan 6. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %60 · net medyan +0.1484 · excess TRAIN -0.2164 / HOLDOUT -0.2137
- **Kanıt:** 38 olay / 15 küme; holdout 5 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Yorgunluk: fat_3m veya fat_5m < 35 (sıfırlanmış)
  - Bağlam: HTF bull (15m/1h yukarı)
  - REALF: skor 35–55 bandı
  - Fiyatlanmamış akış: unpriced >= 0
  - Akış/yapı: akış UP ya da taze 1m UP yapı olayı
  - CVD: 5 dk CVD deltası pozitif

**Plan:** taban plan (`AT_TRIGGER` + `HOLD_HORIZON`) bu adayda en iyisi; denenen erken çıkışların hiçbiri 27 eşleşmede onu geçmedi.

**Hangi coinlerde:** en iyi → KUCUK/SAKIN (net +0.64, isabet %75, 4 dolum), BUYUK/OYNAK (net +0.49, isabet %67, 3 dolum).
En kötü → ORTA/OYNAK (net -0.94, isabet %44, 9 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H1_FLOW_CONFIRM — YETERSIZ

*H1 + 5m CVD slope>0 ve flow confidence5m>=60*

- **Karar ufku:** 60 dk (ölçülen medyan tepe 24 dk)
- **En güçlü hareket:** medyan 24 dakikada; tipik MFE %0.65, tipik MAE %-0.21 → ödül/risk **3.0**
- **Geri verme:** tepeden ufuk sonuna medyan %0.49; en kötü an medyan 30. dakikada
- **İlk karşıt akış sinyali:** medyan 7. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %61 · net medyan +0.1633 · excess TRAIN -0.2164 / HOLDOUT -0.2907
- **Kanıt:** 33 olay / 14 küme; holdout 4 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Yorgunluk: fat_3m veya fat_5m < 35 (sıfırlanmış)
  - Bağlam: HTF bull (15m/1h yukarı)
  - REALF: skor 35–55 bandı
  - Fiyatlanmamış akış: unpriced >= 0
  - Akış/yapı: akış UP ya da taze 1m UP yapı olayı
  - CVD: 5 dk CVD deltası pozitif

**Plan:** taban plan (`AT_TRIGGER` + `HOLD_HORIZON`) bu adayda en iyisi; denenen erken çıkışların hiçbiri 22 eşleşmede onu geçmedi.

**Hangi coinlerde:** en iyi → BUYUK/OYNAK (net +0.49, isabet %67, 3 dolum), BUYUK/SAKIN (net +0.31, isabet %78, 9 dolum).
En kötü → ORTA/OYNAK (net +0.22, isabet %57, 7 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H3_BASE — YETERSIZ

*H3 immediate breakout mevcut shadow tanımı*

- **Karar ufku:** 60 dk (ölçülen medyan tepe 40 dk)
- **En güçlü hareket:** medyan 40 dakikada; tipik MFE %1.00, tipik MAE %-0.44 → ödül/risk **2.3**
- **Geri verme:** tepeden ufuk sonuna medyan %0.18; en kötü an medyan 10. dakikada
- **İlk karşıt akış sinyali:** medyan 6. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %67 · net medyan +0.3516 · excess TRAIN +0.1673 / HOLDOUT +0.3507
- **Kanıt:** 24 olay / 14 küme; holdout 4 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Yapı: taze, güçlü ve teyitli BOS (kırılım)
  - Yorgunluk: fat_1m < 72
  - REALF: skor 40–60 bandı
  - CVD: cvd_1m > 0 ve cvd_5m > 0
  - Alıcı baskınlığı: buyer_ratio_1m > 50

**Plan:** `PULLBACK_25` + `HOLD_HORIZON` — aynı olaylarda taban plana göre **+0.229** (eşleşme 8), dolum %33.3, isabet %75.0, çıkış ~61. dakika.

**Hangi coinlerde:** en iyi → BUYUK/OYNAK (net +1.08, isabet %75, 4 dolum), BUYUK/SAKIN (net +0.69, isabet %89, 9 dolum).
En kötü → KUCUK/SAKIN (net +0.05, isabet %50, 6 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H3_RETEST — YETERSIZ

*H3 gözlenen breakout→retest→reacceleration*

- **Karar ufku:** 60 dk (ölçülen medyan tepe 42 dk)
- **En güçlü hareket:** medyan 42 dakikada; tipik MFE %1.10, tipik MAE %-0.37 → ödül/risk **2.9**
- **Geri verme:** tepeden ufuk sonuna medyan %0.34; en kötü an medyan 12. dakikada
- **İlk karşıt akış sinyali:** medyan 5. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %74 · net medyan +0.3099 · excess TRAIN +0.0314 / HOLDOUT +0.2753
- **Kanıt:** 27 olay / 14 küme; holdout 4 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Yapı: taze, güçlü ve teyitli BOS (kırılım)
  - Yorgunluk: fat_1m < 72
  - REALF: skor 40–60 bandı
  - CVD: cvd_1m > 0 ve cvd_5m > 0
  - Alıcı baskınlığı: buyer_ratio_1m > 50

**Plan:** `PULLBACK_25` + `PEAK_TIME` — aynı olaylarda taban plana göre **+0.147** (eşleşme 8), dolum %29.6, isabet %87.5, çıkış ~43. dakika.

**Hangi coinlerde:** en iyi → BUYUK/SAKIN (net +0.91, isabet %100, 9 dolum), BUYUK/OYNAK (net +0.62, isabet %75, 4 dolum).
En kötü → KUCUK/SAKIN (net +0.53, isabet %75, 4 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H1_HTF_ALIGN — YETERSIZ

*H1 + 15m bullish ve (1h veya 4h bullish), fresh 5m bearish olay yok*

- **Karar ufku:** 60 dk (ölçülen medyan tepe 35 dk)
- **En güçlü hareket:** medyan 35 dakikada; tipik MFE %0.71, tipik MAE %-0.24 → ödül/risk **3.0**
- **Geri verme:** tepeden ufuk sonuna medyan %0.40; en kötü an medyan 30. dakikada
- **İlk karşıt akış sinyali:** medyan 6. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %66 · net medyan +0.2629 · excess TRAIN -0.3022 / HOLDOUT +0.2085
- **Kanıt:** 29 olay / 13 küme; holdout 5 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Yorgunluk: fat_3m veya fat_5m < 35 (sıfırlanmış)
  - Bağlam: HTF bull (15m/1h yukarı)
  - REALF: skor 35–55 bandı
  - Fiyatlanmamış akış: unpriced >= 0
  - Akış/yapı: akış UP ya da taze 1m UP yapı olayı
  - CVD: 5 dk CVD deltası pozitif

**Plan:** taban plan (`AT_TRIGGER` + `HOLD_HORIZON`) bu adayda en iyisi; denenen erken çıkışların hiçbiri 19 eşleşmede onu geçmedi.

**Hangi coinlerde:** en iyi → BUYUK/SAKIN (net +0.40, isabet %88, 8 dolum), BUYUK/OYNAK (net +0.32, isabet %67, 3 dolum).
En kötü → ORTA/OYNAK (net -0.77, isabet %33, 3 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H1_REALF_PCTL — YETERSIZ

*H1 + realf_percentile >= 60 (ham 35–55 bandı ayırmıyor, yüzdelik sınanıyor)*

- **Karar ufku:** 60 dk (ölçülen medyan tepe 35 dk)
- **En güçlü hareket:** medyan 35 dakikada; tipik MFE %0.57, tipik MAE %-0.29 → ödül/risk **2.0**
- **Geri verme:** tepeden ufuk sonuna medyan %0.18; en kötü an medyan 30. dakikada
- **İlk karşıt akış sinyali:** medyan 6. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %65 · net medyan +0.2666 · excess TRAIN -0.2344 / HOLDOUT +0.1743
- **Kanıt:** 23 olay / 12 küme; holdout 5 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Yorgunluk: fat_3m veya fat_5m < 35 (sıfırlanmış)
  - Bağlam: HTF bull (15m/1h yukarı)
  - REALF: skor 35–55 bandı
  - Fiyatlanmamış akış: unpriced >= 0
  - Akış/yapı: akış UP ya da taze 1m UP yapı olayı
  - CVD: 5 dk CVD deltası pozitif

**Plan:** taban plan (`AT_TRIGGER` + `HOLD_HORIZON`) bu adayda en iyisi; denenen erken çıkışların hiçbiri 18 eşleşmede onu geçmedi.

**Hangi coinlerde:** en iyi → BUYUK/SAKIN (net +0.43, isabet %100, 4 dolum), BUYUK/OYNAK (net +0.39, isabet %100, 3 dolum).
En kötü → ORTA/OYNAK (net -1.28, isabet %0, 4 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H8_IGNITION_PULLBACK — YETERSIZ

*H8 ateşleme + %0.25 geri çekilme beklenir*

- **Karar ufku:** 20 dk (ölçülen medyan tepe 50 dk)
- **En güçlü hareket:** medyan 50 dakikada; tipik MFE %1.09, tipik MAE %-0.25 → ödül/risk **4.3**
- **Geri verme:** tepeden ufuk sonuna medyan %0.33; en kötü an medyan 14. dakikada
- **İlk karşıt akış sinyali:** medyan 2. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %42 · net medyan -0.0378 · excess TRAIN -0.1842 / HOLDOUT +0.2366
- **Kanıt:** 12 olay / 10 küme; holdout 3 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Hacim: realf_rvol >= 1.35 (bu runın p90 değeri)
  - Alıcı baskınlığı: buyer_ratio_1m >= 80 (p90)
  - CVD: cvd_1m_pct > 0
  - KAPI YOK: REALF bandı, yapı kırılımı, yorgunluk ve unpriced şartı bilerek aranmaz

**Plan:** taban plan (`AT_TRIGGER` + `HOLD_HORIZON`) bu adayda en iyisi; denenen erken çıkışların hiçbiri 12 eşleşmede onu geçmedi.

**Hangi coinlerde:** en iyi → KUCUK/SAKIN (net +0.08, isabet %57, 7 dolum).
En kötü → KUCUK/SAKIN (net +0.08, isabet %57, 7 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H5_FRESH_15M — YETERSIZ

*H5 armed + 15 dakika içinde 1m/3m DN olayı*

- **Karar ufku:** 20 dk (ölçülen medyan tepe 7 dk)
- **En güçlü hareket:** medyan 7 dakikada; tipik MFE %0.18, tipik MAE %-1.24 → ödül/risk **0.1**
- **Geri verme:** tepeden ufuk sonuna medyan %0.72; en kötü an medyan 37. dakikada
- **İlk karşıt akış sinyali:** medyan 6. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %23 · net medyan -0.3227 · excess TRAIN -0.0813 / HOLDOUT +0.0838
- **Kanıt:** 13 olay / 9 küme; holdout 2 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Bağlam: HTF bear
  - Sıçrama: yakın geçmişte tepki yükselişi
  - Fiyatlanmamış akış: güçlü pozitif gap yok (unpriced <= 0.005)
  - CVD: cvd_5m < 0
  - Akış: akış DOWN
  - Yapı: 1m veya 3m durum DN

**Plan:** `PULLBACK_25` + `HOLD_HORIZON` — aynı olaylarda taban plana göre **+0.116** (eşleşme 8), dolum %61.5, isabet %62.5, çıkış ~21. dakika.

**Hangi coinlerde:** en iyi → ORTA/OYNAK (net -0.08, isabet %43, 7 dolum), KUCUK/SAKIN (net -0.28, isabet %0, 3 dolum).
En kötü → KUCUK/SAKIN (net -0.28, isabet %0, 3 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H5_FRESH_BREAK — YETERSIZ

*H5 + fresh 1m/3m bearish event*

- **Karar ufku:** 20 dk (ölçülen medyan tepe 13 dk)
- **En güçlü hareket:** medyan 13 dakikada; tipik MFE %0.18, tipik MAE %-1.44 → ödül/risk **0.1**
- **Geri verme:** tepeden ufuk sonuna medyan %0.81; en kötü an medyan 35. dakikada
- **İlk karşıt akış sinyali:** medyan 6. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %25 · net medyan -0.4051 · excess TRAIN +0.0698 / HOLDOUT +0.1220
- **Kanıt:** 12 olay / 8 küme; holdout 2 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Bağlam: HTF bear
  - Sıçrama: yakın geçmişte tepki yükselişi
  - Fiyatlanmamış akış: güçlü pozitif gap yok (unpriced <= 0.005)
  - CVD: cvd_5m < 0
  - Akış: akış DOWN
  - Yapı: 1m veya 3m durum DN

**Plan:** taban plan (`AT_TRIGGER` + `HOLD_HORIZON`) bu adayda en iyisi; denenen erken çıkışların hiçbiri 11 eşleşmede onu geçmedi.

**Hangi coinlerde:** en iyi → ORTA/OYNAK (net -0.08, isabet %43, 7 dolum).
En kötü → ORTA/OYNAK (net -0.08, isabet %43, 7 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H1_BASE_PULLBACK — YETERSIZ

*H1 tetiği + %0.25 geri çekilme beklenir; olay geri çekilme anında doğar*

- **Karar ufku:** 60 dk (ölçülen medyan tepe 26 dk)
- **En güçlü hareket:** medyan 26 dakikada; tipik MFE %1.19, tipik MAE %-0.72 → ödül/risk **1.7**
- **Geri verme:** tepeden ufuk sonuna medyan %1.04; en kötü an medyan 12. dakikada
- **İlk karşıt akış sinyali:** medyan 2. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %60 · net medyan +0.3523 · excess TRAIN +0.1754 / HOLDOUT -0.1205
- **Kanıt:** 10 olay / 8 küme; holdout 3 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Yorgunluk: fat_3m veya fat_5m < 35 (sıfırlanmış)
  - Bağlam: HTF bull (15m/1h yukarı)
  - REALF: skor 35–55 bandı
  - Fiyatlanmamış akış: unpriced >= 0
  - Akış/yapı: akış UP ya da taze 1m UP yapı olayı
  - CVD: 5 dk CVD deltası pozitif

**Hangi coinlerde:** en iyi → ORTA/OYNAK (net +0.14, isabet %67, 6 dolum).
En kötü → ORTA/OYNAK (net +0.14, isabet %67, 6 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H5_HTF_ALIGN — YETERSIZ

*H5 + 15m ve 1h bearish*

- **Karar ufku:** 20 dk (ölçülen medyan tepe 19 dk)
- **En güçlü hareket:** medyan 19 dakikada; tipik MFE %0.38, tipik MAE %-1.08 → ödül/risk **0.4**
- **Geri verme:** tepeden ufuk sonuna medyan %0.94; en kötü an medyan 46. dakikada
- **İlk karşıt akış sinyali:** medyan 6. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %57 · net medyan +0.0009 · excess TRAIN +0.4706 / HOLDOUT +0.2144
- **Kanıt:** 7 olay / 7 küme; holdout 2 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Bağlam: HTF bear
  - Sıçrama: yakın geçmişte tepki yükselişi
  - Fiyatlanmamış akış: güçlü pozitif gap yok (unpriced <= 0.005)
  - CVD: cvd_5m < 0
  - Akış: akış DOWN
  - Yapı: 1m veya 3m durum DN

**Hangi coinlerde:** en iyi → ORTA/OYNAK (net -0.03, isabet %50, 4 dolum).
En kötü → ORTA/OYNAK (net -0.03, isabet %50, 4 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H3_RETEST_PULLBACK — YETERSIZ

*H3 retest tetiği + %0.25 geri çekilme beklenir*

- **Karar ufku:** 60 dk (ölçülen medyan tepe 49 dk)
- **En güçlü hareket:** medyan 49 dakikada; tipik MFE %1.57, tipik MAE %-0.15 → ödül/risk **10.7**
- **Geri verme:** tepeden ufuk sonuna medyan %0.35; en kötü an medyan 5. dakikada
- **İlk karşıt akış sinyali:** medyan 3. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %100 · net medyan +1.0086 · excess TRAIN +0.1764 / HOLDOUT +0.4893
- **Kanıt:** 8 olay / 7 küme; holdout 2 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Yapı: taze, güçlü ve teyitli BOS (kırılım)
  - Yorgunluk: fat_1m < 72
  - REALF: skor 40–60 bandı
  - CVD: cvd_1m > 0 ve cvd_5m > 0
  - Alıcı baskınlığı: buyer_ratio_1m > 50

**Plan:** `AT_TRIGGER` + `PEAK_TIME` — aynı olaylarda taban plana göre **+0.027** (eşleşme 8), dolum %100.0, isabet %87.5, çıkış ~49. dakika.

**Hangi coinlerde:** en iyi → BUYUK/SAKIN (net +0.65, isabet %100, 4 dolum).
En kötü → BUYUK/SAKIN (net +0.65, isabet %100, 4 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H1_SLOW_SETUP — YETERSIZ

*H1 + setup→trigger >= 15 dk; anında tetiklenen kurulumdan ayrı ölçülür*

- **Karar ufku:** 60 dk (ölçülen medyan tepe 27 dk)
- **En güçlü hareket:** medyan 27 dakikada; tipik MFE %1.34, tipik MAE %-0.27 → ödül/risk **5.1**
- **Geri verme:** tepeden ufuk sonuna medyan %1.10; en kötü an medyan 7. dakikada
- **İlk karşıt akış sinyali:** medyan 4. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %67 · net medyan +0.7393 · excess TRAIN +0.4939 / HOLDOUT +0.1762
- **Kanıt:** 6 olay / 6 küme; holdout 3 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Yorgunluk: fat_3m veya fat_5m < 35 (sıfırlanmış)
  - Bağlam: HTF bull (15m/1h yukarı)
  - REALF: skor 35–55 bandı
  - Fiyatlanmamış akış: unpriced >= 0
  - Akış/yapı: akış UP ya da taze 1m UP yapı olayı
  - CVD: 5 dk CVD deltası pozitif

**Hangi coinlerde:** en iyi → ORTA/OYNAK (net -1.15, isabet %33, 3 dolum).
En kötü → ORTA/OYNAK (net -1.15, isabet %33, 3 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H3_BASE_PULLBACK — YETERSIZ

*H3 tetiği + %0.25 geri çekilme beklenir*

- **Karar ufku:** 60 dk (ölçülen medyan tepe 41 dk)
- **En güçlü hareket:** medyan 41 dakikada; tipik MFE %0.68, tipik MAE %-0.18 → ödül/risk **3.8**
- **Geri verme:** tepeden ufuk sonuna medyan %0.33; en kötü an medyan 5. dakikada
- **İlk karşıt akış sinyali:** medyan 4. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %67 · net medyan +0.1732 · excess TRAIN +0.1232 / HOLDOUT +0.4966
- **Kanıt:** 9 olay / 6 küme; holdout 3 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Yapı: taze, güçlü ve teyitli BOS (kırılım)
  - Yorgunluk: fat_1m < 72
  - REALF: skor 40–60 bandı
  - CVD: cvd_1m > 0 ve cvd_5m > 0
  - Alıcı baskınlığı: buyer_ratio_1m > 50

**Plan:** taban plan (`AT_TRIGGER` + `HOLD_HORIZON`) bu adayda en iyisi; denenen erken çıkışların hiçbiri 8 eşleşmede onu geçmedi.

**Hangi coinlerde:** en iyi → BUYUK/SAKIN (net +0.05, isabet %100, 3 dolum).
En kötü → BUYUK/SAKIN (net +0.05, isabet %100, 3 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H3_SLOW_SETUP — YETERSIZ

*H3 + setup→trigger >= 15 dk*

- **Karar ufku:** 60 dk (ölçülen medyan tepe 30 dk)
- **En güçlü hareket:** medyan 30 dakikada; tipik MFE %1.08, tipik MAE %0.00
- **Geri verme:** tepeden ufuk sonuna medyan %0.64; en kötü an medyan 0. dakikada
- **İlk karşıt akış sinyali:** medyan 7. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %60 · net medyan +0.2388 · excess TRAIN — / HOLDOUT —
- **Kanıt:** 5 olay / 4 küme; holdout 1 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Yapı: taze, güçlü ve teyitli BOS (kırılım)
  - Yorgunluk: fat_1m < 72
  - REALF: skor 40–60 bandı
  - CVD: cvd_1m > 0 ve cvd_5m > 0
  - Alıcı baskınlığı: buyer_ratio_1m > 50

**Hangi coinlerde:** en iyi → BUYUK/SAKIN (net +0.63, isabet %100, 3 dolum).
En kötü → BUYUK/SAKIN (net +0.63, isabet %100, 3 dolum). Sınıf başına örneklem küçük; yön değil eğilim okunur.

## H2_SLOW_SETUP — YETERSIZ

*H2 + setup→trigger >= 15 dk*

- **Karar ufku:** 60 dk (ölçülen medyan tepe 17 dk)
- **En güçlü hareket:** medyan 17 dakikada; tipik MFE %2.15, tipik MAE %-0.34 → ödül/risk **6.3**
- **Geri verme:** tepeden ufuk sonuna medyan %0.83; en kötü an medyan 30. dakikada
- **İlk karşıt akış sinyali:** medyan 18. dakikada — tepeden çok önce geldiği için tek başına çıkış sebebi sayılmadı (ölçüldü: erken kesmek zarar verdi)
- **Başarı oranı (karar ufkunda, maliyet sonrası):** %75 · net medyan +0.9809 · excess TRAIN +2.4972 / HOLDOUT +0.7032
- **Kanıt:** 4 olay / 3 küme; holdout 1 küme. Bağımsız kanıt 30 kümenin altında; yön iddiası taşımaz.

**Belirteç bütünü** (tetik anında okunan alanlar):

  - Fiyatlanmamış akış: realf_unpriced_flow > 0.005 (gap açık)
  - REALF: skor < 50 (fiyat henüz gitmemiş)
  - REALF kalite: beta R² > 0.45 ve bileşen uyumu > 0.5
  - Yorgunluk: fat_1m < 83
  - Yapı: taze 5m DN olayı yok
  - Akış: akış UP, 5 dk CVD deltası pozitif, 1 dk alıcı oranı yükseliyor

## Bağlam katmanı (işlem tetiği değil)

- **H6_RESET** — H6 reset tarayıcısı; işlem tetiği değildir · 17 olay / 12 küme. Yön kararı için kullanılmaz; diğer hipotezlerin bağlamını okumak için izlenir.
- **H6_DEEP_RESET** — H6 deep reset tarayıcısı; işlem tetiği değildir · 9 olay / 8 küme. Yön kararı için kullanılmaz; diğer hipotezlerin bağlamını okumak için izlenir.

## Bu kılavuzun sınırları

- Hiçbir bölüm işlem izni değildir; ADAY olmayan bir hipotez için sayılar yalnız davranış tarifidir.
- Tek gün içi holdout, farklı gün OOS değildir; rejim değişince karakter de değişebilir.
- MFE/MAE gözlenen snapshot fiyatlarıdır, bar içi uçlar değildir: gerçek stop bunlardan daha erken tetiklenebilir.
- Ödül/risk oranı gözlenen MFE ve MAE medyanlarının oranıdır; varsayılan bir stop mesafesi değildir.
