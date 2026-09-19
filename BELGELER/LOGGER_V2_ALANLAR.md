# Canlı Takip Logger v2 — Alan Sözlüğü ve Tanımlar

> Bu dosya `snapshots.jsonl` / `snapshots.csv` / `outcomes.jsonl` dosyalarını analiz edecek kişi
> (GPT dahil) içindir. Her alanın **tam** tanımı burada. Kod: `live_tracker.py` (motorlar, ekran)
> + `tracker_v2.py` (akış havuzu, kayıt, sonuç değerlendirici).

## 0. Hızlı başlangıç

| İş | Komut |
|---|---|
| 20 test coinini takip et (saatlerce / günlerce açık kalabilir) | `takip_TEST_20.bat` (= `python live_tracker.py TEST`) |
| GPT için günlük tabloları üret (takip **sürerken de** çalışır) | `SONUCLARI_HESAPLA.bat` (= `python live_tracker.py --outcomes latest`) |
| Ağsız öz-test (altyapı + motorlar, 63 kontrol) | `python live_tracker.py --selftest` |
| Yalnız altyapı testi | `python tracker_v2.py selftest` |
| Shadow durum makinesi ve sonuç onarım testleri | `python -m unittest -v test_research` |
| Bütün eski çalışmaların eksik sonuçlarını tamamla | `python live_tracker.py --outcomes all` |
| H1–H7, FP/FN, segment ve benchmark raporu | `python research_report.py logs/run_20260918_015707 --fetch-history` |
| Eski MTF davranışı (3m–4h'yi 1m'den türet) | `python live_tracker.py TEST --mtf resample` |
| Kayıtları OneDrive dışına yaz | `python live_tracker.py TEST --log-dir C:\AVCI_LOGS` |

Her çalıştırma `logs/run_YYYYMMDD_HHMMSS/` klasörü açar. Uzun çalışmada dosyalar büyümesin diye kayıtlar
**saatlik parçalara** bölünür (parça adı = snapshot'ın yakalandığı yerel saat):

| Dosya | İçerik |
|---|---|
| `console_YYYYMMDD_HH.txt` | O saatte ekrana basılan **her şey** (Windows konsolu yalnız son ~9001 satırı tutar; eski "12 dakikalık TXT" sorununun sebebi buydu). |
| `snapshots_YYYYMMDD_HH.jsonl` | Snapshot başına 1 satır: tüm skaler alanlar + seriler (`*_series`). |
| `snapshots_YYYYMMDD_HH.csv` | Aynı skaler alanlar; sütunlar çalışma boyunca sabit, **her parçanın kendi başlığı var**. |
| `outcomes.jsonl` | 60 dakikası dolan snapshot'ların ileri getiri / MFE / MAE sonuçları — **takip sürerken sürekli yazılır**. |
| `snapshots_with_outcomes_YYYYMMDD.csv` | `SONUCLARI_HESAPLA.bat` üretir: o günün tüm saatlik CSV parçaları + sonuç sütunları. **İstatistik / GPT için bu dosyaları kullan** (gün başına bir dosya). |
| `run_meta.json` | Çalıştırma ayarları, sürümler, kod parmak izi, tur/snapshot/sonuç sayaçları, son güncelleme zamanı. |

Uzun çalışma notları:
- Disk: ~20 KB/snapshot (JSONL ~10, konsol ~7, CSV ~2.6, sonuç ~0.5) → 20 coinde saatte ~20–25 MB, günde ~0,5 GB.
- `SONUCLARI_HESAPLA.bat` takip sürerken çalıştırılırsa son ~66 dakikayı canlı değerlendiriciye bırakır (çift kayıt olmaz);
  tabloyu istediğin sıklıkta yeniden üretebilirsin. Birleşik tablo Excel'de açıksa `.csv.tmp` olarak yazılır.
- Takip penceresinde QuickEdit kapatılır: pencereye tıklamak programı dondurmaz. Metin kopyalamak için `console_*.txt` kullan.
- WARP / internet kesilirse takip kapanmaz, her turda yeniden dener; kesinti süresi pencerelerde kapsama düşüşü ve
  `pool_gap_*` alanlarında görünür.
- **Uyku:** Bu laptop S3 bekleme kullanır (işlemci ve ağ kartı kapanır; internet bağlı olsa da hiçbir program çalışmaz)
  ve 30 dk boşta kalınca uyur. Takip açıkken Windows'a "sistem gerekli" isteği gönderilir (`SetThreadExecutionState`,
  medya oynatıcılarla aynı yöntem): boşta uyku engellenir, ekran kapanabilir, güç ayarları değişmez, takip kapanınca
  istek kalkar. **Kapak kapatma ve güç tuşu yine uyutur.** İstenmezse `--allow-sleep`. Uykuya girilirse takip uyanınca
  kaldığı yerden devam eder; aradaki süre veride boşluk olarak görünür.
- Disk yazılamazsa (dolu / kilitli) kayıtlar bellekte en fazla 64 MB tutulur; aşılırsa en eskisi atılır ve ekranda uyarı çıkar.

Genel kurallar:
- Tüm `*_ms` alanları **Binance sunucu saatine göre epoch milisaniye** (yerel saat farkı `clock_offset_ms` ile düzeltilir).
- **Veri yoksa değer `null`/boş**; sahte 50 / sahte %50 yazılmaz (eski ekrandaki "Alıcı %50" gibi değerler JSON'da `null`'dur).
- Hiçbir yeni alan skoru etkilemez. REALF / Fatigue / Structure skor, durum, olay ve rejim hesapları
  önceki sürümle **birebir aynıdır** (1.170 seri + 1.371 önek üzerinde karşılaştırıldı, 0 fark).

## 1. Kimlik, sürüm, zaman

**ZORUNLU alanlar** (her snapshot'ta dolu olmalı; eksikse kayıt `required_fields_missing` ile işaretlenir ve
`run_meta.invalid_snapshots` artar): `dataset_schema`, `tracker_version`, `structure_version`, `realf_engine`,
`fatigue_version`, `run_id`, `code_fingerprint`, `snapshot_id`, `symbol`, `captured_at_ms`, `kline_asof_ms`, `price`.

| Alan | Tanım |
|---|---|
| `dataset_schema` | Kayıt şeması (**2**). |
| `tracker_version` | Logger sürümü (**v2.1-shadow**; eski kayıtlar v2 kalır). |
| `structure_version` | **v1.2** — STRUCTURE v1.2 Audited (§6). Eski `v1.1` etiketi kodda ve kayıtlarda kalmadı. |
| `realf_engine` | **REALF_PY_V4_2_DERIVED** — Pine REALF v4.2'den TÜRETİLMİŞ Python motoru; birebir kopya değildir (farklar §9.1). Formül değişmedi, yalnız adı gerçeğe uygun hale getirildi. |
| `fatigue_version` | **ZPTDIFAT_PY_V1_4_DERIVED** — ZP TDIALT + FATIGUE MTF v1.4'ten türetilmiş yorgunluk motoru (farklar §9.2). |
| `flow_confidence_version` | `fc-v1` (§4). |
| `mtf_source` | `native` = 3m/5m/15m/1h/4h Binance'ten gerçek mum (499 bar) · `resample` = 500 adet 1m'den türetilmiş (eski davranış). |
| `git_commit` | Klasör git deposuysa kısa commit, değilse `null`. Eski kayıtların commit'i sonradan uydurulmaz. |
| `git_dirty` | Çalışan üç Python kaynak dosyasında commit edilmemiş fark var mı. Commit tek başına çalışan kodu temsil etmeyebilir. |
| `code_fingerprint` | `live_tracker.py` + `tracker_v2.py` + `shadow_research.py` içeriğinin sha256'sının ilk 16 hanesi. Eski v2 yalnız ilk iki dosyayı kullanır. **Kod değişirse değişir**. |
| `required_fields_missing` | Boş string = kayıt tam. Doluysa hangi zorunlu alanların eksik olduğunu `|` ile listeler. |
| `alerts_skipped` | Kısmi pencere yüzünden çalıştırılmayan alarm grupları (`flow_1m_incomplete`). |
| `run_id`, `seq` | Çalıştırma kimliği ve çalıştırma içindeki snapshot sıra no'su. |
| `snapshot_id` | `AKE_20260917_113800_341` = sembol (USDT'siz) + yerel tarih/saat + milisaniye. Benzersiz. |
| `symbol`, `provider`, `market`, `coin_class`, `coin_rank`, `whale_threshold_usd` | Kayıt defterinden. |
| `captured_at_ms` | **Snapshot anı** = işlem havuzunun eksiksiz olduğu son an (son aggTrades isteğinin başladığı an). Tüm akış pencereleri bu anda biter. |
| `captured_at_local` | Aynı an, yerel saat ISO (+03:00). |
| `clock_offset_ms`, `clock_synced` | Binance saati − yerel saat; senkron başarılı mı. |
| `kline_asof_ms` | 1m mumların çekildiği an. **`price` bu anın fiyatıdır; sonuçlar bu andan ölçülür.** |
| `flow_asof_ms` | Havuzun "bu ana kadar tam" dediği an (normalde = `captured_at_ms`). |
| `prev_snapshot_age_sec` | Aynı coinin bir önceki snapshot'ından beri geçen süre (tur süresi ~60–90 sn). |
| `bar_open_time`, `bar_close_time` | Son 1m barın açılış / kapanış zamanı (ms; kapanış = açılış + 59 999). |
| `is_bar_closed` | `kline_asof_ms` anında bar kapanmış mıydı. Binance son barı açık döndürdüğü için **neredeyse her zaman `false`**: tüm "now" değerleri canlı (yarım) bar içerir. |
| `bar_progress_sec` | Canlı barın kaçıncı saniyesinde ölçüldü (0–60). Canlı değer ile kapalı bar farkını yorumlarken kullan. |
| `price`, `chg_1m_pct` | Son 1m kapanış (anlık fiyat) ve bir önceki bar kapanışına göre % değişim. |

## 2. Hazırlık (warmup) — sahte değer ile gerçek değeri ayır

| Alan | Tanım |
|---|---|
| `tf_{tf}_bars`, `tf_{tf}_source` | O zaman diliminde kullanılan bar sayısı ve kaynağı (`native` / `resampled_1m`). `tf` ∈ 1m, 3m, 5m, 15m, 1h, 4h. |
| `fat_{tf}_ready` | Yorgunluk rank penceresi (300 bar) dolu mu (bar ≥ 320). `false` ise değer Pine ile karşılaştırılamaz. |
| `fat_{tf}_rank_window` | Gerçekte kullanılan rank penceresi uzunluğu. |
| `str_{tf}_ready` | 4 dış pivot (2 tepe + 2 dip) oluştu mu. `false` → yapı/dizilim güvenilmez. |
| `str_{tf}_regime_ready` | Rejim yüzdelikleri için ≥ 201 bar var mı. `false` → `regime` sahte (ATR/BBW rank 50 sabit). |
| `realf_ready`, `realf_bars` | REALF için ≥ 420 bar (Pine tablosundaki WARMUP x/420 eşiği). |

`--mtf resample` ile 500 adet 1m'den türetilen satırlar hiçbir zaman tam hazır olmaz (15m = 34 bar, 1h = 9 bar, 4h = 3 bar);
v2 varsayılanı `native` bu yüzden seçildi.

## 3. Akış pencereleri (gerçek taker işlemleri — aggTrades havuzu)

Havuz, Binance **aggTradeId sürekliliği** ile tutulur: her turda son id'den itibaren `fromId` ile sayfa sayfa
(1000 işlem/sayfa, tur başına en fazla `--max-pages`, varsayılan 5) çekilir. Sayfa sınırı aşılırsa en yeni
işlemlere atlanır ve aradaki süre **boşluk** olarak kaydedilir. Eski sürüm her turda yalnız son 500 işlemi
çekiyordu; 20 coinlik ~70 sn'lik turda likit coinlerde (ETH vb.) 5m/15m pencerelerinin büyük kısmı hiç
görülmüyordu. Artık her pencerenin gerçek dolu oranı ölçülüyor.

Pencere `W` ∈ `1m`, `5m`, `15m`; hepsi `(captured_at_ms − W, captured_at_ms]` aralığı:

| Alan | Tanım |
|---|---|
| `flow_{W}_buy_usd`, `flow_{W}_sell_usd` | Taker alış / satış notional'ı ($). Alış = `m == false` (alıcı taker). |
| `cvd_{W}` | alış − satış ($). |
| `cvd_{W}_pct` | cvd / toplam × 100. Veri yoksa `null`. |
| `buyer_ratio_{W}` | alış / toplam × 100 (**notional ağırlıklı**). Veri yoksa `null`. |
| `flow_{W}_score`, `flow_{W}_direction` | Ekrandaki "Project Z Skoru" (50 + 45·tanh(cvd%/22)) ve yön (±%3 eşik). |
| `trade_count_{W}` | Gerçek işlem sayısı = Σ(lastTradeId − firstTradeId + 1). |
| `agg_count_{W}` | aggTrade satırı sayısı. |
| `notional_{W}` | Toplam notional ($). |
| `n_eff_{W}` | Hacim konsantrasyonu düzeltmeli etkin işlem sayısı = (Σ$)² / Σ($²). 1 dev işlem + 100 küçük işlem ≈ 1. |
| `window_coverage_sec_{W}`, `window_coverage_ratio_{W}` | Pencerenin gerçekten veriyle dolu süresi / oranı (başlangıç öncesi + boşluklar düşülür). Takip başladıktan sonra 15m penceresi ~15 dk'da dolar. |
| `1m_complete`, `5m_complete`, `15m_complete` | **Karar/alarm uygunluğu:** kapsama ≥ %99,9 ise `true`. Kısmi pencere yine kaydedilir ama **alarm üretmez** (`alerts_skipped=flow_1m_incomplete`) ve analizde karar verisi sayılmamalıdır. |
| `last_trade_age_ms` | `captured_at_ms` − son işlemin zamanı. |
| `large_buy_count_{W}`, `large_buy_value_{W}`, `large_sell_count_{W}`, `large_sell_value_{W}` | `whale_threshold_usd` üstü **burst**'ler. Burst = aynı milisaniye + aynı taker yönündeki ardışık aggTrade'lerin toplamı (tek bir market emrinin birden fazla fiyat kademesini süpürmesi tek işlem sayılır). |
| `whale_net_notional_{W}` | büyük alış $ − büyük satış $. |
| `last_whale_time_ms`, `last_whale_side`, `last_whale_usd`, `last_whale_price` | Havuzdaki (son 17 dk) en son büyük burst; fiyat = burst VWAP. |

**Deltalar ve eğim** (aynı havuzdan, borsa saatine göre tam 1 dakika önceki aynı pencereye kıyasla; ilgili
aralığın kapsaması < %95 ise `null`):

| Alan | Tanım |
|---|---|
| `cvd_1m_delta` | cvd(son 60 sn) − cvd(60–120 sn önce). |
| `cvd_5m_delta` | cvd(son 5 dk) − cvd(1–6 dk önce). |
| `cvd_15m_delta` | cvd(son 15 dk) − cvd(1–16 dk önce). |
| `buyer_ratio_delta_1m`, `buyer_ratio_delta_5m` | Aynı mantıkla alıcı oranı farkı (puan). |
| `flow_delta_coverage_ratio` | Delta hesabına giren aralıkların en düşük kapsaması. |
| `cvd_slope_3m`, `cvd_slope_5m` | Son 3 / 5 dakikanın kümülatif CVD eğrisinin (dakika adımlı, 4 / 6 nokta) en küçük kareler eğimi, **$/dk**. |
| `cvd_slope_3m_norm`, `cvd_slope_5m_norm` | Eğim / aynı dakikaların ortalama dakikalık hacmi → coinler arası karşılaştırılabilir (≈ −1…+1). |
| `cvd_slope_prev_3m_norm` | Bir önceki 3 dakikanın (3–6 dk önce) normalize eğimi. |
| `cvd_turn_3m` | `UP`: önceki ≤ −0.02 ve şimdiki ≥ +0.02 · `DOWN`: tersi · `NONE` · kapsama yetersizse `null`. "CVD negatife giderken yön değiştirdi mi?" sorusunun doğrudan alanı. |

**Tamlık kanıtı** — son KAPANMIŞ 1m barda havuz toplamı / Binance kline toplamı:

| Alan | Tanım |
|---|---|
| `kcheck_status` | `ok` · `pool_incomplete` (o bar havuzda tam değil) · `no_bar`. |
| `pool_vs_kline_notional_ratio`, `pool_vs_kline_trades_ratio`, `pool_vs_kline_taker_buy_ratio` | `ok` iken ~1.000 olmalı. Binance aggTrades sigorta fonu / ADL işlemlerini içermez; likidasyon anlarında 1'in biraz altı normaldir. İlk gerçek çalışmada (17 Eyl, 20 coin) 61 kontrolün 57'si tam 1.0000, BNB ±%0,2. |

> **Kline oturma süresi:** Binance REST mumu, bar kapandıktan sonraki ilk birkaç saniyede henüz tamamlanmamış olabilir
> (ölçüm: kapanıştan 1,3 sn ve 2,8 sn sonra çekilen mumlarda hacim %13 ve %31 eksikti; aynı mumlar sonradan havuz toplamıyla
> birebir eşitlendi). Kontrol artık mum çekiminden **en az 10 sn önce kapanmış** barı kullanır. **17 Eyl 21:11'den önce başlatılan
> çalışmalarda** (`run_20260917_210045` dahil) `kline_asof_ms − (kcheck_bar_open + 60000) < 10000` olan satırlarda bu oranları yok say.

**Senkron teşhisi**: `sync_mode` (`bootstrap`, `continuous`, `jump`, `weight_guard*`, `weight_skip`, `id_reset`),
`sync_pages`, `sync_fetched`, `sync_gap_ms`, `sync_error`, `pool_gap_events`, `pool_gap_ms_total`, `pool_resets`,
`pool_integrity_errors`, `pool_contamination_reset`, `used_weight_1m` (Binance IP ağırlığı, limit 2400/dk;
1500 üstünde ek sayfa açılmaz, 2100 üstünde senkron atlanır — aynı IP'deki AVCI backend'ini de korur).

## 4. FLOW_CONFIDENCE (shadow — hiçbir skora girmez)

`flow_confidence_{W}` (0–100) = 100 × count^0.40 × notional^0.30 × coverage^0.20 × freshness^0.10

| Bileşen | Alan | Formül |
|---|---|---|
| count | `fc_{W}_count` | n_eff / (n_eff + 50) |
| notional | `fc_{W}_notional` | clamp((log10($) − 2) / 4, 0, 1) → $100 = 0 · $10k = 0.5 · $1M+ = 1 |
| coverage | `fc_{W}_coverage` | `window_coverage_ratio_{W}` |
| freshness | `fc_{W}_freshness` | clamp(1 − last_trade_age / W, 0, 1) |

Herhangi bir bileşen 0 ise sonuç 0. Örnek (1m): 4 işlem / $310 / tam kapsama / son işlem 10 sn önce → **18.5**;
1800 işlem / $4.8M → **~99**. Bileşenler ayrıca kaydedildiği için ağırlıkları analizde yeniden kurabilirsin.

## 5. REALF, Fatigue ve bar hizalı deltalar

REALF (1m): `realf_score`, `realf_state`, `realf_impact`, `realf_memory`, `realf_momentum`, `realf_activity`,
`realf_unpriced_flow` (= RemainingUnpricedFlow, log birimi), `realf_fast_price`, `realf_fast_flow`, `realf_beta`,
`realf_beta_r2`, `realf_rvol`, `realf_percentile`, `realf_persistence`, `realf_net_pct`, `realf_whale` — ekrandakiyle aynı.

| Yeni REALF alanı | Tanım |
|---|---|
| `realf_component_spread` | max − min (Impact, Memory, Momentum). |
| `realf_component_agreement` | Pine'daki "Component agreement": \|0.9·(core−50)\| / Σ wᵢ\|bileşenᵢ−50\|, 0–1. Düşük = alt motorlar birbirine ters. |
| `realf_implied_price`, `realf_implied_gap_pct` | fiyat × exp(RemainingUnpricedFlow) ve % farkı. Envanterin fiyat karşılığıdır, **tahmin değildir**. |
| `realf_source` | `CLV_PROXY_1M`: REALF baskıyı mumun kapanış konumundan tahmin eder (Pine'ın 1m davranışı); gerçek taker hacmi kullanılmaz. |
| `realf_source_quality`, `kline_gaps_300`, `zero_volume_share_300` | 100 × (bar/420) × (1 − zaman boşluğu payı) × (1 − sıfır hacimli bar payı), son 300 bar. |

**Bar hizalı seriler** — "Son 6 Mum" tablosunun aynısı: her değer o barın KAPANIŞINDAKİ veriyle yeniden
hesaplanır; son eleman canlı bardır. Yani `*_1m_ago` = bir önceki barın kapanış değeri (tur zamanlamasından bağımsız).

| Alan | Tanım |
|---|---|
| `realf_now`, `realf_1m_ago`, `realf_3m_ago`, `realf_5m_ago` | Canlı bar, 1 / 3 / 5 bar önceki kapanış. |
| `realf_d1`, `realf_d3`, `realf_d5` | now − ago. |
| `unpriced_now`, `unpriced_d1`, `unpriced_d3`, `unpriced_d5` | RemainingUnpricedFlow için aynı. |
| `fatigue_now`, `fatigue_1m_ago`, `fatigue_3m_ago`, `fatigue_5m_ago`, `fatigue_delta_1m`, `fatigue_delta_3m`, `fatigue_delta_5m` | 1m yorgunluk için aynı. |
| `absolute_fatigue`, `relative_rank` | 1m yorgunluğun mutlak (RSI/StochRSI/%B bileşimi) ve 300 bar içindeki göreli sırası. |
| JSONL serileri: `realf_series`, `fatigue_series`, `unpriced_series`, `bar_time_series`, `bar_close_series`, `bar_notional_series`, `bar_taker_buy_series`, `bar_cvd_series`, `bar_trades_series` | Eskiden yeniye 6 değer (son = canlı bar). `bar_cvd_series` Binance kline taker verisidir (tam, boşluksuz). |

Her zaman dilimi için yorgunluk: `fat_{tf}`, `fat_{tf}_state`, `fat_{tf}_abs`, `fat_{tf}_rank` (+ §2 hazırlık alanları).

## 6. Structure (her zaman dilimi: `str_{tf}_*`)

**Motor: STRUCTURE v1.2 Audited.** Kaynak: `Masaüstü/plan/STRUCTURE_v1.1.pine` (çekirdek motor) +
`plan/Yeni klasör/STRUCTURE_v1_2_AUDIT_REPORT.md` (v1.2 farkları). v1.2, v1.1 çekirdeğini değiştirmez; üç şey ekler:
çok bölgeli EQH/EQL likidite hafızası, bölge başına bağımsız sweep kilidi, hazır değilken **WARM** (sahte `RANGE`/50 yok).

**Teyitli bar kuralı (Pine `barstate.isconfirmed`):** pivotlar, BOS/CHOCH state machine, likidite bölgeleri ve
süpürmeler **yalnız kapanmış barlarda** işlenir. Canlı (açık) bar yalnız üç şeyi etkiler: olay yaşlanmasıyla skor,
fiyata göre mesafe alanları ve `sweep_forming`. Böylece yarım bar yapıyı değiştiremez (öz-testte 12 seride doğrulandı).

Alanlar: `score`, `state` (`BULL` / `TR-UP` / `RANGE` / `TR-DN` / `BEAR` / **`WARM`**), `event`
(`BOS UP` / `BOS DN` / `CHOCH UP` / `CHOCH DN` / `NONE`), `ext_seq`, `regime`, `conf`.
Dikkat: `regime` = `TR-UP` **geçiş** (state 1), `TR UP` **trend** (state 2 ve ADX ≥ 22) demektir.
**`ready=false` iken** (yeterli teyitli pivot yok) `state='WARM'`, `score`/`event`/`regime`/`conf` = `null`.

| Alan | Tanım |
|---|---|
| `confirmed_bars` | Motorun işlediği kapanmış bar sayısı (canlı bar hariç). |
| `int_seq` | İç (2 bar) pivotların dizilimi: `HH/HL`, `LH/LL`, `HH/MIX`, `MIX/HL`, `LH/MIX`, `MIX/LL`, `EQ/RANGE`, `WARMUP`. Dış yapıya karşı mikro yapı. |
| `event_age` | Son BOS/CHOCH'tan beri geçen bar (canlı bar = 0). Olay yoksa `null`. |
| `event_strength` | Kırılım kalitesi 0–100 (0.45 × ATR cinsinden kopuş + 0.30 × gövde + 0.25 × kapanış konumu). |
| `event_time_ms` | Olay barının açılış zamanı (aynı olayı snapshot'lar arasında tekilleştirmek için). |
| `protected_type`, `protected_level` | Yapıyı geçersiz kılacak seviye: yükseliş yapısında `LOW`, düşüşte `HIGH`; yoksa `NONE` / `null`. |
| `protected_distance_atr` | **İşaretli** ATR mesafesi: `LOW` için (fiyat − seviye)/ATR, `HIGH` için (seviye − fiyat)/ATR. Pozitif = seviye sağlam; 0'a yaklaşma = invalidation'a yaklaşma; negatif = canlı barda seviyenin ötesinde. |
| `nearest_eqh`, `eqh_distance_atr`, `eqh_touches` | Fiyatın ÜSTÜNDEKİ en yakın aktif eşit-tepe bölgesi, (bölge − fiyat)/ATR ve o bölgenin teyitli temas sayısı. |
| `nearest_eql`, `eql_distance_atr`, `eql_touches` | Fiyatın ALTINDAKİ en yakın aktif eşit-dip bölgesi, (fiyat − bölge)/ATR ve temas sayısı. |
| `eqh_active`, `eql_active` | **v1.2 çok bölgeli hafıza:** yön başına en fazla 3 aktif bölge (sınır dolunca en eski düşer). Bölge: art arda iki dış pivot 0.12 ATR içindeyse **ikisinin ORTALAMASI** (Pine `(extHigh0+extHigh1)/2`). Toleransa düşen yeni pivot aynı bölgeye **temas** sayılır (temas sayısı artar, sweep kilidi sıfırlanır). Kapanış bölgenin 0.10 ATR ötesine geçerse bölge **tüketilir**. |
| `liq_ref_high`, `liq_ref_low` | Likidite referansı: aktif bölge varsa bölge fiyatı, yoksa **son dış swing seviyesi** (v1.2 fallback). |
| `last_liq_event` | `EQH_SWEEP` / `EQL_SWEEP` (bölge süpürmesi) · `HIGH_SWEEP` / `LOW_SWEEP` (aktif bölge yokken swing süpürmesi) · `NONE`. Süpürme = fitil seviyenin 0.10 ATR ötesine geçip **kapanışın** seviyenin berisinde kalması; yalnız KAPANMIŞ barda sayılır. Her bölge/seviye yeni temasa kadar bir kez. |
| `liq_event_age`, `liq_event_level` | Süpürmeden beri geçen bar (canlı bar dahil sayılır) ve süpürülen seviye. |
| `sweep_event` | Süpürme son KAPANMIŞ barda mı (teyitli). |
| `sweep_forming` | Canlı barda oluşmakta olan süpürme — **teyitsiz, karar verisi değil**; bar kapanmadan geri alınabilir. |
| `atr_pct` | ATR(14) / fiyat × 100 (son kapanmış bar). |

## 7. Orderbook (Binance depth, ilk 20 kademe; snapshot başına 1 istek)

| Alan | Tanım |
|---|---|
| `ob_best_bid`, `ob_best_ask` | En iyi alış / satış. |
| `spread_bps` | (ask − bid) / mid × 10 000. |
| `microprice_deviation_bps` | microprice = (bid × askQty + ask × bidQty)/(bidQty + askQty); (microprice − mid)/mid × 10 000. Pozitif = yukarı kısa vadeli baskı. |
| `orderbook_imbalance` | (Σ bid$ − Σ ask$) / (Σ bid$ + Σ ask$), ilk 20 kademe. |
| `ob_imbalance_top5` | Aynısı ilk 5 kademe. |
| `ob_bid_notional_20`, `ob_ask_notional_20` | İlk 20 kademe $ toplamları. |
| `ob_depth_span_bps` | 20. kademenin mid'e uzaklığı (derinliğin ne kadar fiyat aralığına yayıldığı). |
| `ob_timestamp_ms` | Binance'in orderbook zaman damgası (`E`). |
| `ob_age_ms` | `captured_at_ms − ob_timestamp_ms`. Canlı ölçüm: tipik 0,5–1,5 sn. |
| `ob_stale` | Yaş > 5 sn (veya zaman damgası yok / veri yok) → `true`. **Bayat orderbook karar verisi değildir**; zaten hiçbir alarm orderbook alanlarına bakmaz (öz-testte kodla doğrulanır). |
| `ob_error` | Hata / `disabled` (`--no-depth`) bilgisi. |

`alerts`: ekrandaki alarmların kodları, `|` ile ayrılmış (`BULL_CVD_DIVERGENCE`, `BEAR_CVD_DIVERGENCE`,
`FATIGUE_EXTREME`, `FATIGUE_RESTED_1M`, `REALF_PRICE_LAG`, `REALF_PRICE_AHEAD`, `AGGRESSIVE_BUYER`, `AGGRESSIVE_SELLER`).

## 8. Sonuçlar (`outcomes.jsonl`, `snapshots_with_outcomes_YYYYMMDD.csv`)

`t0_ms` = snapshot'ın `kline_asof_ms`'i, `entry_price` = snapshot `price`.

| Alan | Tanım |
|---|---|
| `fwd_ret_{H}m`, H ∈ 1, 3, 5, 10, 20, 30, 60 | t0 + H dakikaya **en yakın** 1m bar kapanışının entry'ye göre % getirisi. Çözünürlük ±30 sn (1 dk ufkunda gerçek süre 30–90 sn). |
| `mfe_{H}m`, `mae_{H}m`, H ∈ 5, 10, 20, 30, 60 | t0 → o çıkış kapanışı arasında en yüksek / en düşük fiyatın % sapması (LONG bakışı; SHORT için MFE = −MAE). Yol = entry + yakalama barının kapanışı + sonraki barların high/low'u. Yakalama barının high/low'u t0 öncesini içerebileceği için kullanılmaz (MFE/MAE ≥ 0 / ≤ 0). |
| `outcome_complete` | Tüm ufuklar için mum bulundu mu. Eksikse satır yazılmaz; sonraki çalıştırmada tekrar denenir. |
| `source` | `live` (takip sırasında, 60 dk dolunca) / `offline` (`SONUCLARI_HESAPLA.bat`). |

Takip sürerken sonuçlar `outcomes.jsonl`'e kendiliğinden yazılır. Takip durdurulunca son 60 dakikanın snapshot'ları
canlı değerlendirilemez; bunlar için takip bittikten ≥ 61 dk sonra `SONUCLARI_HESAPLA.bat` çalıştır (Binance'ten geçmiş
1m mumlarını çeker; tekrar çalıştırmak güvenlidir). Takip sürerken de çalıştırılabilir: o zaman yalnız 66 dakikadan eski ve
henüz sonucu yazılmamış snapshot'ları hesaplar. `outcomes.jsonl`'de aynı `snapshot_id` nadiren iki kez görünebilir;
birleşik tablo tekilleştirilmiş sonucu kullanır.

## 9. Bilinen sınırlar (analizde hesaba kat)

### 9.1 REALF motoru neden `REALF_PY_V4_2_DERIVED`
Formüle dokunulmadı; yalnız adı gerçeğe uygun hale getirildi, çünkü Python sürümü Pine REALF v4.2'nin birebir kopyası
değil: EMA(3) yumuşatması yok (impactGap, momentumGap), beta gecikmesiz (Pine `beta[1]`), momentler son 100 barın düz
ortalaması (Pine `f_mr` = 100 + azalan ağırlıklı eski gözlemler), priceScale tabanı 1e-5 (Pine ATR tabanlı), RVOL tabanı
20 bar SMA (Pine `f_mr`), whale kuralı sadeleştirilmiş, `ready` eşiği 420 bar. TradingView değerlerine yakın ama aynı
değildir; karşılaştırırken bunu hesaba kat.

### 9.2 Fatigue motoru neden `ZPTDIFAT_PY_V1_4_DERIVED`
Bileşenler ve ağırlıklar Pine ZP TDIALT + FATIGUE MTF v1.4 ile aynı (RSI14 0.35 · StochRSI %K 0.20 · BB%B 0.45 →
absolute → 300 bar rank → 0.70/0.30 adaptive → EWMA α=0.30, eşikler 30/72/83). Farklar: Pine `fatStrict` 300 barlık
geçerli seri şartını **kesin** uygular (yoksa değer üretmez), Python değeri üretir ve `fat_{tf}_ready` bayrağıyla
işaretler; EWMA tohumu Pine'da ilk `adaptive`, Python'da ilk `absolute`; zaman sürekliliği (`fatGapCheck`) denetimi yok.

### 9.3 Structure v1.2 uygulama notları
- Kaynak Pine dosyası v1.1'dir; v1.2 farkları denetim raporundan uygulanmıştır (çok bölge, sweep kilidi, WARM).
- v1.1 Pine dosyasında dış pivot prominence yedeği yanlışlıkla **iç** swing değişkenine (`intLow1`/`intHigh1`) düşüyor;
  v1.2 denetim raporu "external motor yalnız `extLow*/extHigh*` kullanır" dediği için bu motor `extLow1`/`extHigh1`
  kullanır (v1.2 davranışı).
- `ta.pivothigh/pivotlow` yorumu: sol tarafta eşitlik kabul, sağ tarafta kesin büyüklük (`>=` sol, `>` sağ).
- `ta.percentrank` yorumu: son `regLookback` **önceki** değerin kaçı ≤ şimdiki (yetersiz geçmişte `null` → rejim
  volatilite sınıflarına girmez, yalnız yapı temelli olur).
- MTF satırları Pine'ın hafif (`CONF LITE`) MTF anlık görüntüsü değil, her zaman diliminde **tam motordur** —
  Pine paneliyle birebir aynı sayılar beklenmemeli (Pine MTF'i basitleştirir).
- Doğrulama: `python live_tracker.py --selftest` içinde v1.2 senaryoları (bölge ortalaması, temas, sweep kilidi,
  tüketim, FIFO, fallback, WARM) ve 12 seride "canlı bar teyitli alanları değiştiremez" sızıntı testi.

4. aggTrades sigorta fonu / ADL işlemlerini içermez (Binance belgesi).
5. `bar_*_series` ve kline tabanlı alanlar kapanmış barlarda tamdır; canlı bar yarımdır (`bar_progress_sec`). Snapshot
   dakikanın ilk ~5 saniyesinde alındıysa (`bar_progress_sec` < 5) bir önceki barın mumu Binance'te henüz oturmamış olabilir;
   o satırlarda `realf_1m_ago`, `fatigue_1m_ago`, `*_d1`, `bar_*_series[-2]` hafif sapabilir.
6. Tur süresi coin sayısına bağlı (~60–90 sn). "1m önce" alanları bara / borsa saatine hizalıdır, tura değil.
7. MEXC (LONGXIA) işlemlerinde sıralı id yok → boşluk yalnız zaman tabanlı tahmin; orderbook ve çevrimdışı sonuç yok.
