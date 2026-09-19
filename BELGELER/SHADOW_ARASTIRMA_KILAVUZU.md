# Shadow araştırma katmanı — shadow-v1

Bu sürüm üretim indikatörü veya işlem sistemi değildir. REALF, Fatigue, Structure ve alarm fonksiyonları değişmedi. Aşağıdaki sayısal seçimler araştırmanın tekrar üretilebilmesi için açıkça tanımlanmış deney kurallarıdır; doğrulanmış optimum eşikler değildir. Eski rapordaki elle uygulanan varyantlarla aynı deney sayılmaz.

## Çalıştırma

- Normal takip: `takip_TEST_20.bat`. Yeni snapshotlara shadow alanları otomatik eklenir.
- Sonuç onarımı: `SONUCLARI_HESAPLA.bat`. Artık yalnız son klasörü değil, bütün run klasörlerini işler. Canlı çalışmanın son ~66 dakikasını bekletir.
- Araştırma: `python research_report.py logs/run_20260918_015707 --fetch-history`.
- Aynı analizi indirilmiş mumlarla tekrar et: aynı komuttan `--fetch-history` kaldırılır.
- Kontrol: `python live_tracker.py --selftest` ve `python -m unittest -v test_research`.

`research_shadow_v1/` içinde RAPOR.md, audit.json, replay_with_outcomes.csv, events.csv, summary.csv, false_positives.csv, false_negatives.csv, filter_candidates.csv, segments.csv, conversions.csv, excluded_intervals.csv, entry_exit_timing.csv ve alignment_transitions.csv oluşur. Historical_cache yalnız herkese açık geçmiş OHLC verisidir. Kaynak snapshot, araştırma kodu ve tarihsel mum dosyalarının hash'leri audit.json içindedir.

## Tur döngüsü ve defter

İnceleme her turda yalnız **en yeni** çalışmaya bakar; arşiv yeniden taranmaz. Sıra:

1. `YENI_LOGLARI_HAZIRLA.bat` → `research_updates.py` en yeni runın eklenen satırlarını ve tamamlanan sonuçları ayırır; ardından `research_ledger.py` defteri günceller. İkisi de ağ istemez.
2. Eksik sonuç bildirilirse `SONUCLARI_HESAPLA.bat` (ağ ister) çalıştırılır.
3. Yeni kanıt geldiğinde `python research_report.py logs/<run> --fetch-history` (ağ ister) ve `python hypothesis_lab.py logs/<run>` yeniden çalıştırılır.
4. `python research_ledger.py` yeni lab çıktısını **tur** olarak deftere yazar.

Defter `ARASTIRMA/DEFTER/` altındadır: makine durumu `ledger.json`, insan tabloları `HIPOTEZ_DEFTERI.md`, `EKSIKLER.md` ve her turda ölçümden yeniden üretilen `KULLANIM_KILAVUZU.md` (hipotez başına işlem karakteri, başarı ve risk yüzdeleri). Lab tarafında `hypothesis_lab_v21/KARAKTER.md` + `character.csv` tepe/MFE/MAE/geri verme zamanlamasını, `veto_cost.csv` kalite vetosunun elediği olayları tutar.

- **Karar ufku hipotez başına**, ölçülen tepe zamanından türer: *medyan tepeyi içeren en küçük mevcut ufuk*. Getiriye göre seçilmez; lab her turda tepeyi yeniden ölçer, sapma `auto:horizon-drift` eksiği olarak açılır.
- **Kanıt 10 dakikalık kümede sayılır**, ham olayda değil: aynı kovadaki olaylar birlikte hareket eder. Durum merdiveni küme sayısına bakar.

- Bir run aynı menü sürümü ve aynı replay hash'i ile ikinci kez kaydedilmez (`NO_NEW_EVIDENCE`). Menü değişirse veya sonuçlar tamamlandığı için replay değişirse yeni tur açılır; böylece "aynı veriyi tekrar saymak" mümkün değildir.
- Durumlar sabit kuralla verilir, eşik aranmaz: `VERI_YOK` (tetik yok) · `YETERSIZ` (<30 olay) · `IZLENIYOR` (30+ olay ama holdout ince) · `ADAY` (excess hem TRAIN hem HOLDOUT'ta pozitif **ve** holdout 30+) · `ELENDI` (arka arkaya iki turda her ufukta pozitif değil, en az 10 olayla) · `TARAYICI` (H6/H7; işlem tetiği değil). Durum değişmesi kanıtın değiştiği anlamına gelir.
- Menüden çıkarılan varyant silinmez; kanıt olarak son ölçüsüyle durur.
- Eksikler taşınır ve ölçülür. Otomatik eksik (tetiksiz hipotez, ince holdout, tamamlanmamış sonuç, tek gün, sansürlü çıkış oranı) koşulu kaybolduğunda kendiliğinden kapanır; elle eksik yalnız kanıt yazılarak kapanır:
  `python research_ledger.py --gap-add "başlık" --gap-detail "..." --gap-close-when "..."` ve `python research_ledger.py --gap-close E-0003 --evidence "..."`.
- **Aynı kanıt yeniden ölçülürse tur açılmaz, tur revize edilir.** Tur kimliği = run + replay hash'i;
  menü ya da ölçüm kodu değişince aynı turun ölçüsü yenilenir (`revisions` sayacı). Farklı run/replay
  ise yeni tur açılır. Eleme (`ELENDI`) bu yüzden **farklı iki kanıt turu** ister.
- Lab çıktıları: `KARSILASTIRMA.md` (karar ufkunda aday tablosu), `KARAKTER.md` (+ `character.csv`:
  tepe/MFE/MAE/geri verme zamanlaması), `PLAN.md` (+ `plan_summary.csv`, `coin_class_summary.csv`:
  3 giriş × 5 çıkış politikası ve coin sınıfı), `veto_cost.csv` (kalite vetosunun elediği olaylar).
- Menü v2.4 ile eklenenler: `*_PULLBACK` varyantları (olay, %0.25 geri çekilmenin gerçekleştiği
  snapshot'ta doğar), `H1_REALF_PCTL` / `H1_FLOW_AGREE` / `H1_FLOW_MIXED` / `H1_CONF_FLOOR`
  (indikatör teşhislerinin ölçülebilir karşılığı), `H4_FRESH_15M` / `H5_FRESH_15M` (yapı tazeliği
  bar yerine **dakika** cinsinden). Eski varyantların hiçbiri silinmedi.
- Kayıt boyutu: saatlik `snapshots_*.csv` artık yazılmaz (JSONL asıl kaynak). Gerekirse
  `python snapshots_csv_uret.py logs/run_<id>` birebir üretir.
- Yapılan her iş `GÜNLÜK/`'e yazılır: `python gunluk_ekle.py "başlık" --sorun ... --cozum ... --dogrulama ...`
- Kontrol: `python test_research_ledger.py` ve `python test_research_updates.py`.

## Ortak kalite şartları

1m/5m/15m flow tam, saat senkron, sync hatası/contamination yok, zorunlu alan eksiği yok, kline zaman farkı 0–90 sn, son 300 mumda zaman boşluğu yok. İlgili Fatigue zaman dilimleri hazır; H1–H5 için REALF hazır olmalı. Structure yön/event kullanılan yerde kendi ready şartı da aranır. Eksik sayılar sıfır yerine null kalır.

Orderbook kullanılan ek varyantta `shadow_ob_valid=true` zorunlu: veri mevcut, stale=false, hata yok, sync hatası yok ve yaşı 0–5000 ms. Temel H1–H7 aşamaları orderbook kullanmaz. Rapordaki orderbook uyarıları yalnız bu koşulu sağlayan kayıtlarda yönlü filtre adayına dönüşür.

3 dakikadan uzun gözlem kesintisinde geçmişe bağlı state sıfırlanır. Kesinti piyasada setup yoktu anlamına gelmez. `health_events.jsonl` iyileşen bağlantı kesintilerini; run_meta içindeki active_outages hâlâ süren kesintileri kaydeder. Bütün coinlerin başarısız olduğu turlarda tekrar deneme aralığı 10→20→40→60 sn büyür. Bu, harici DNS/internet arızasını ortadan kaldırmaz.

## Ortak alanlar

Her H için `shadow_Hn_hypothesis_id`, `raw_candidate`, `setup`, `armed`, `trigger`, `trigger_condition`, `stage`, `eligible`, `blocked_reason`, `missing_conditions`, `event_group_id`, `event_start_ms`, `new_event`, `trigger_age_sec`, `trigger_snapshot_id` aynı önekle yazılır.

`trigger` olay grubunda bir kez true olur; `trigger_condition` koşulun her snapshot'taki değeridir. Tetiklenmeyen grubun ömrü ilk setup'tan itibaren 60 dk; tetiklenen grup, tetikten sonraki 60 dk +90 sn örnekleme payı tamamlanana kadar korunur. Kesintide kapanır. Bu kimlik istatistiksel bağımsızlık garantisi değildir. Rapor ayrıca aynı coin/H tetiklerini 60 dk arayla tekilleştirir. Gruplar farklı H'lerde ve coinlerde bağımsız varsayılmaz.

`post_trigger_followthrough_{1,3,5,10,20,30,60}m`: hedef anı geçen ilk snapshot fiyatının yönlü yüzde getirisi. H4/H5 short yönlü, diğerleri long. Hedef an +90 sn'ye kadar örnek kabul edilir; geç/kalitesiz ölçüm null. Resmî outcome ile aynı zaman çözünürlüğünde değildir. `confirmation_5m_delay_sec`: tetikten sonra 5m CVD'nin yönle ilk uyumlu olduğu gözleme gecikme. `H4_DECAY_5M`: gözlenen short 5m getirisi ≤0; veri yoksa null.

`setup_to_trigger_sec`, `observed_return_pct`, `observed_mfe_pct`, `observed_mae_pct`, `observed_giveback_pct`, `observed_peak_delay_sec`, `observed_trough_delay_sec`: sadece o ana kadar gözlenen snapshot fiyatlarına dayanır. Ara işlemlerdeki gerçek tepe/dip bu alanlarda görülmeyebilir.

`structure_opposes`, `flow5_opposes`, `gap_opposes`, `protected_level_broken`: her H1–H5 için güncel durum ve tetikten sonraki ilk görülme gecikmesi/getirisi/snapshot kimliği kaydedilir. Protected seviye tetik anındaki 1m korunan LOW (long) veya HIGH (short) seviyesidir; o andan sonra değiştirilmez. Alanlar çıkış adayı araştırmasıdır, otomatik emir değildir. Bir karşıt koşul tetik anında zaten varsa ilk sonraki geçerli gözlemde görüldüğü kaydedilir; yeni bir dönüş gerçekleştiği iddia edilmez.

`shadow_alignment_*`: Structure yönleri, REALF gap yönü ve flow yönleri ayrı kategoriler olarak tutulur. `pattern`, `previous`, `changed`, `duration_sec` birleşimin sırasını ve süresini gösterir. Birleştirilmiş AL/SAT skoru üretilmez; Fatigue context olarak korunur.

## Aşamaların tam tanımı

Akış UP: `cvd_turn_3m=UP` veya `cvd_slope_3m_norm>0 ve cvd_1m_delta>0`. DOWN tersi. Bu mevcut logger'ın **3m proxy** varyantıdır, 1m dönüşü diye sunulmaz. Ek `shadow_cvd_slope_1m_norm` = (2×buyer_ratio_1m−100)/100; önceki 1m oranı buyer_ratio_delta_1m'den çıkarılır. `shadow_cvd_turn_1m` iki ardışık dakikada −0.02→+0.02 (UP), tersi (DOWN). Ayrı deney için kaydedilir; production hesapları değişmez.

Fresh structure event: ready=true, BOS/CHOCH yönü uygun, event_age 0–3 bar. Her TF için freshness sınıfı 0–3 / 4–10 / >10 bar; bar süresi TF'ye bağlıdır.

| H | Raw / SETUP | ARMED | TRIGGER |
|---|---|---|---|
| H1 | Raw: 3m veya 5m Fatigue<35. Setup: buna ek 15m/1h/4h'den en az biri BULL/TR-UP ve REALF 35–55 | UnpricedFlow≥0 | Akış UP veya fresh 1m UP event; ayrıca 5m CVD delta>0 |
| H2 | Raw: UnpricedFlow>0. Setup: U>0.005, REALF<50, R²>0.45, agreement>0.5 | 1m Fatigue<83; fresh 5m bearish event yok | Akış UP, 5m CVD delta>0, buyer ratio delta>0 |
| H3 | Raw: fresh 5m/15m BOS UP. Setup: aynı TF'de strength>30 ve confidence>60 | 1m Fatigue<72, REALF 40–60 | 1m ve 5m CVD>0; buyer ratio1m>50 |
| H4 | Raw: son 15 dk içinde 1m Fatigue>83 görülmüş. Setup: REALF>58 veya U<0 | Fatigue delta1m<0 ve CVD delta1m<0 | Akış DOWN + fresh 3m/5m bearish event |
| H5 | Raw: 15m veya 1h BEAR/TR-DN. Setup: bu context'te son 15 dk içinde Fatigue delta3m>0 ve fiyat değişimi1m>0 görülmüş | U mevcut ve ≤0.005; CVD5m<0 | Bounce gözleminden sonraki bir snapshot'ta akış DOWN ve 1m/3m bearish state |
| H6 | Raw: 1m/3m/5m'den biri <30. Setup: üçü de <30 ve hazır. DEEP_RESET: ayrıca 15m<35 ve hazır | Yok; tarayıcı | Yok; giriş sinyali değil |
| H7 | Raw: 1m Fatigue<30. Setup: ayrıca beş extension özelliği mevcut | Yok; context filtresi | Yok; hard veto değil |

H1 için 'tüm üst TF bullish' ve H2 için 0.003/0.35 veya 0.010 eski araştırma varyantları bu tablodan farklıdır. Geçmiş raporda çalıştırılabilir test betiği bulunmadığı için eski 4/12/52/7/0 gibi olay sayıları birebir yeniden üretildi iddiası yoktur. Yeni sonuçlar sürümlü ve yeniden üretilebilirdir.

## H7 özellikleri

- `return_24h/3d/7d`: snapshot fiyatı / hedef zamandan önceki saatlik mum açılışı −1, yüzde. En fazla 60 dk zaman yuvarlaması; anchor_ms ve rounding_sec ayrıca kaydedilir. Tam kayan 24 saat getirisi değildir.
- `local_base_price`: son 60 kesintisiz, kapanmış 1m mumun en düşük low'u. `local_base_return` bu dibe göre yüzde getiri.
- `atr_extension`: fiyatın bu dipten uzaklığı / son kapalı 1m barın ATR'si. ATR, Structure atr_pct × son kapalı bar kapanışı /100 üzerinden bulunur.
- `h7_features_ready`: beş alanın tümü mevcut. Native 1h 499 mum 7 günü kapsar; resample/MEXC/yeni listelenme/yetersiz geçmişte null olabilir.
- Context: 24h>%20 PUMP; <%5 NORMAL; arası MID. Bunlar test gruplarıdır, işlem veto eşiği değildir. RVOL ve volume percentile mevcut REALF alanlarında kalır.

Eski runların H7 alanları geçmiş saatlik açılış ve t0 öncesindeki kapalı 1m mumlardan ayrı replay dosyasına eklenir. Sonradan bilinen final live-bar high/low kullanılmaz. Orijinal log sonradan bu alanları içeriyormuş gibi değiştirilmez.

## H3 sıralaması

Fresh BOS'un source timestamp'i ve ilk görülme zamanı ayrı kaydedilir. İlk gözlem fiyatının altına 2–10 dk sonra gelmesi retest proxy'sidir. Retest sonrası ayrı gözlemde REALF 40–60, Fatigue<72, akış UP ve CVD5m pozitif/iyileşiyor şartları reacceleration üretir. Protected level altına inme veya fresh 1m bearish event bu adayı iptal eder; 30 dk sonra state sona erer.

Retest derinliği yalnız gözlenen snapshot fiyatlarından hesaplanır; aradaki gerçek en düşük işlem fiyatı değildir. Protected survival da gözlenen fiyatlara dayanır. Bu H3 alt deneyi, yeni doğrulanmış H8 değildir.

## H6 dönüşüm ve censoring

Reset grubundan 60 dk içinde ilk H1/H2 setup snapshot kimliği, gecikmesi ve o snapshot'ın resmî outcome'u bağlanır. Resetle aynı anda zaten setup varsa CONCURRENT; sonradan oluşursa LATER. Eksik takip nedeniyle tüm pencere gözlenememiş ve dönüşmemiş gruplar censored işaretlenir; başarısız dönüşüm sayılmaz.

## Raporun yorumlanması

Brüt, 10 bps varsayımsal toplam maliyet sonrası net ve benchmark excess ayrıdır. `--cost-bps` ile maliyet duyarlılığı tekrar çalıştırılabilir. Varsayımsal maliyet gerçekleşen komisyon/funding/slippage değildir.

Piyasa referansı izlenen evrendeki diğer coinlerin eşit ağırlıklı sepetidir; tüm piyasa endeksi değildir. BTC/ETH eşit ağırlıklı referans da vardır. Benchmark entry dakikanın açılışı; snapshot entry anlık fiyat: arada <60 sn fark bulunduğundan excess yaklaşık ölçümdür.

False positive: H1–H5 tetiklerinde net 5m≤0. False negative: +20m>%1 veya +60m>%2 olan ve geçmiş 20 dk'da H1/H2/H3 tetiği olmayan gözlemler; aynı coin 60 dk tekilleştirilir. H6/H7 tarayıcı/context oldukları için kaçırılan long işlemin tetiği sayılmaz. Her H'nin eksik koşulları ayrıca CSV'dedir.

Filtre adayları sadece tetik anında bilinen uyarılardır. Kaç başarısız ve kaç başarılı olayı eleyecekleri TRAIN/HOLDOUT ayrı yazılır. Örnek seçip iyi sonucu ilan etmek yerine maliyet, sansürlenmiş gözlemler ve kaybolan kazananlar görünür tutulur.

İlk %70 zaman TRAIN, son %30 HOLDOUT; TRAIN +60m sonucu holdout'a taşıyorsa PURGED. Tek gün içi holdout gerçek farklı gün OOS değildir. 30/50/100 bağımsız olay ve farklı gün/rejim gereksinimi sürer. 2h/4h opsiyonel ufuklar uygulanmadı. Yeni günler toplanmadan hipotezler kanıtlanmış sayılmaz.

## Sonuç motoru düzeltmesi

Canlı motor eksik ara mum içeren outcome'u artık yazıp kuyruktan düşürmez; tekrar dener. Giriş mevcut 500 mumluk belleğin gerisindeyse `outcomes_deferred_offline` sayar ve kalıcı snapshot üzerinden sonraki çevrimdışı onarıma bırakır. Son 60 dakika takip kapanınca doğal olarak bekler; daha sonra sonuç komutu çalıştırılır. outcome_audit.json her onarımın kalan/tamamlanan sayısını kaydeder; eski run_meta sayaçları tarihsel kayıt olarak korunur.

JSONL varsa sonuç onarımının ve günlük tablonun asıl kaynağıdır; CSV gerektirmez. CSV yalnız eski JSONL'siz runlarda yedek kaynak olur. Yinelenen snapshot kimlikleri tekilleştirilir; başka snapshotlara ait sonuçlar tamamlanma sayısını şişirmez. Kaynak snapshot sayısı run_meta sayısından düşükse işlem mevcut raporu değiştirmeden durur. Bozuk JSONL sessizce atlanmaz; yalnız aktif runın henüz tamamlanmamış son satırı bekletilir. `--outcomes all` hatalı klasörü bildirip diğer klasörlerle devam eder ve eksik iş kaldığında başarısız çıkış kodu döndürür.
