# Eksikler defteri

Tur 4. Eksikler kapanana kadar taşınır; ölçüsü olan her turda yeniden ölçülür.

Açık: **17** · bu turda açılan: 1 · bu turda kapanan: 0 · toplam kapanan: 8

## Açık

| No | Konu | Açıldığı tur | Ölçü (ilk → son) | Kapanma koşulu | Kaynak |
|---|---|---:|---|---|---|
| E-0001 | Farklı gün ve düşen/sıkışan rejim verisi | 1 | — | En az bir düşen rejim çalışmasının deftere girmesi | manual |
| E-0002 | Gerçek maliyet ve funding | 1 | — | Gerçekleşmiş komisyon/slippage/funding ölçümünün deftere girmesi | manual |
| E-0003 | H4 tanımının gözlenebilirliği | 1 | — | Başka günlerde de bağ yoksa H4 tanımı gözlenemez sayılmalı | manual |
| E-0004 | H2/H3 için 30-60 dk ufkunun ayrı olay tanımı | 1 | — | Uzun ufuk için ayrı tanımın yazılıp ölçülmesi | manual |
| E-0005 | Hiçbir adayda 30+ holdout olayı yok | 1 | 13 (tur 1) → 7 (tur 4) | Bir adayın holdout olay sayısının 30 olması | auto |
| E-0007 | H4_BASE: bu tanımla tetik yok | 1 | 0 (tur 1) → 0 (tur 4) | Aynı tanımla en az bir tetik gözlenmesi | auto |
| E-0008 | Tek güne dayanan kanıt | 1 | 1 (tur 1) → 1 (tur 4) | Deftere en az iki farklı günün girmesi | auto |
| E-0009 | Kalite vetosu en buyuk hareketleri eliyor | 2 | — | partial_flow vetosunun eledigi kazanan/kaybeden olaylarin ayri olculmesi | manual |
| E-0010 | Olaylar zamanda kumeleniyor; ham olay sayisi kaniti abartiyor | 2 | — | Kanit sayiminin ham olay yerine zaman kumesi bazina gecmesi | manual |
| E-0011 | Kacirilan hareketlerin cogu setup asamasinda eleniyor | 2 | — | Bu hareketleri tanimlayan yeni bir setup ailesinin yazilip olculmesi | manual |
| E-0012 | H5 yanlis ufukta olculuyor | 2 | — | H5 icin <=15 dk ufuk ve cikis tanimi yazilip olculmesi | manual |
| E-0013 | Ölçülen tepe zamanı dondurulmuş karar ufkuyla uyuşmuyor | 3 | 5 (tur 3) → 9 (tur 4) | Ufukların ölçülen tepe zamanıyla uyumlu hâle gelmesi | auto |
| E-0021 | REALF ayirt etmiyor: dagilim cok dar | 3 | — | Yuzdelik/olcek duzeltmesi sonrasi tetik ile kacirilan dagiliminin ayrismasi | manual |
| E-0022 | CVD pencereleri birbiriyle celisiyor | 3 | — | Tek akis durumu tanimlanip iki pencerenin celiskisinin olculmesi | manual |
| E-0023 | Yapi olay tazeligi bar bazli, zaman bazli degil | 3 | — | Tazeligin dakika cinsinden tanimlanip cok-TF kesisiminin olculebilir hale gelmesi | manual |
| E-0024 | Coin bazinda akis guveni tabani yok | 3 | — | Coin bazli guven tabani veya kanit agirliklandirmasi uygulanmasi | manual |
| E-0026 | H4_FRESH_15M: bu tanımla tetik yok | 4 | 0 (tur 4) | Aynı tanımla en az bir tetik gözlenmesi | auto |

## Kapanmış

| No | Konu | Açık | Ölçü (ilk → son) | Kanıt |
|---|---|---|---|---|
| E-0006 | Sonucu tamamlanmamış snapshot var | tur 1–2 | 327 (tur 1) | Koşul bu turda gözlenmedi. |
| E-0014 | H1_HTF_ALIGN: üç turdur ne durum ne kanıt değişiyor | tur 3–3 | 5 (tur 3) | Hatalı ölçüm: küme sayısı, kümesiz eski turların ham olay sayısıyla karşılaştırılmıştı. Kural düzeltildi (üç turun da küme temeli olmalı); durgunluk yeniden ölçülecek. |
| E-0015 | H1_SLOW_SETUP: üç turdur ne durum ne kanıt değişiyor | tur 3–3 | 3 (tur 3) | Hatalı ölçüm: küme sayısı, kümesiz eski turların ham olay sayısıyla karşılaştırılmıştı. Kural düzeltildi (üç turun da küme temeli olmalı); durgunluk yeniden ölçülecek. |
| E-0016 | H2_BASE: üç turdur ne durum ne kanıt değişiyor | tur 3–3 | 7 (tur 3) | Hatalı ölçüm: küme sayısı, kümesiz eski turların ham olay sayısıyla karşılaştırılmıştı. Kural düzeltildi (üç turun da küme temeli olmalı); durgunluk yeniden ölçülecek. |
| E-0017 | H2_GAP_EXPANDS: üç turdur ne durum ne kanıt değişiyor | tur 3–3 | 6 (tur 3) | Hatalı ölçüm: küme sayısı, kümesiz eski turların ham olay sayısıyla karşılaştırılmıştı. Kural düzeltildi (üç turun da küme temeli olmalı); durgunluk yeniden ölçülecek. |
| E-0018 | H2_SLOW_SETUP: üç turdur ne durum ne kanıt değişiyor | tur 3–3 | 1 (tur 3) | Hatalı ölçüm: küme sayısı, kümesiz eski turların ham olay sayısıyla karşılaştırılmıştı. Kural düzeltildi (üç turun da küme temeli olmalı); durgunluk yeniden ölçülecek. |
| E-0019 | H5_BASE: üç turdur ne durum ne kanıt değişiyor | tur 3–3 | 5 (tur 3) | Hatalı ölçüm: küme sayısı, kümesiz eski turların ham olay sayısıyla karşılaştırılmıştı. Kural düzeltildi (üç turun da küme temeli olmalı); durgunluk yeniden ölçülecek. |
| E-0020 | H5_FRESH_BREAK: üç turdur ne durum ne kanıt değişiyor | tur 3–3 | 2 (tur 3) | Hatalı ölçüm: küme sayısı, kümesiz eski turların ham olay sayısıyla karşılaştırılmıştı. Kural düzeltildi (üç turun da küme temeli olmalı); durgunluk yeniden ölçülecek. |

Otomatik eksik, koşulu kaybolduğunda kendiliğinden kapanır. Elle açılan eksik yalnız `--gap-close` ile, kanıt yazılarak kapanır.
