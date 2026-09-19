# Güncel log analizi ve hipotez gelişimi — 2026-09-18

Kapsam: yalnız en son çalışma `run_20260918_112149` (11:21–16:26, 6.100 snapshot, 5.773 tam sonuç, 327 olgunlaşmamış). Eski runlar yeniden taranmadı, kaynak loglara dokunulmadı. Aşağıdaki sayılar mevcut `research_shadow_v1` ve `hypothesis_lab_v21` çıktılarından okundu; hiçbiri işlem kuralı değildir.

## 1. Bu turun ana bulgusu: net getiri ile excess ayrışıyor

Bugün izlenen evren yükseliyordu (84 long olayın 65'i HTF BULL bağlamında). Bu yüzden net getiri hipotezlerin başarısı gibi görünüyor ama sepetle karşılaştırınca tablo tersine dönüyor.

| H | n | net5 | excess5 | net20 | excess20 | net60 | excess60 | excess60 isabet |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| H1 | 38 | -0.069 | -0.141 | 0.080 | -0.200 | 0.226 | -0.215 | %44.7 |
| H2 | 24 | 0.058 | -0.005 | -0.012 | -0.136 | 0.263 | 0.055 | %58.3 |
| H3 | 22 | -0.156 | -0.042 | -0.126 | -0.140 | 0.417 | 0.368 | %72.7 |
| H5 | 19 | -0.100 | 0.037 | -0.166 | -0.080 | -0.702 | -0.118 | %42.1 |
| H6 | 17 | -0.019 | 0.028 | 0.007 | -0.146 | -0.316 | -0.501 | %23.5 |

Buradan çıkan karar kuralı: bir aday yalnız **excess**'te, hem TRAIN hem HOLDOUT'ta tabanı geçiyorsa aday sayılır. `hypothesis_lab.py` karşılaştırma tablosuna holdout excess sütunu eklendi ve bu kural tablonun sınırlar bölümüne yazıldı.

Bu kuralın ilk sonucu bir düzeltmedir: önceki turda en iyi görünen `H1_FLOW_CONFIRM` (net5 tabanlı filtre taramasında en tutarlı aday) excess20 ile bakıldığında TRAIN'de -0.232, HOLDOUT'ta -0.040 veriyor; yani taban H1'i excess'te geçmiyor. Aynı şekilde `cvd5_negative` vetosu net5'e göre kazandırıyor görünürken excess20'ye göre iki bölümde de zarar veriyor (TR -0.091, HO -0.083). Filtre sıralaması ölçüt değişince tersine döndüğü için, net5 tabanlı filtre listesi tek başına kanıt sayılmamalıdır.

## 2. Hipotez bazında bugünkü log ne söylüyor

**H1** — hiçbir ufukta sepeti geçemiyor (excess 1m'den 60m'e kadar negatif, isabet %21–45). Denenen filtrelerin hiçbiri TRAIN'de tabanı anlamlı düzeltmiyor; düzeltenler örneklemi 3–4 olaya indiriyor. Bugünkü veriyle H1'in katkısı yön değil beta görünüyor.

**H2** — excess'i sıfıra yakın seyredip 30m (+0.133) ve 60m'de (+0.055) pozitife dönüyor. Buna karşılık her onay eki holdout'ta zarar veriyor: `H2_GAP_EXPANDS` ve `H2_FLOW_CONFIRM` holdout excess'i tabanın altına indiriyor, `gap_contracting` vetosu holdout'ta 2 kaybedene karşılık 1 kazanan eliyor. H2 için doğru yön filtre eklemek değil, ufku uzatmak olarak görünüyor.

**H3** — 30 dakikaya kadar aleyhte, 60m'de excess +0.368 ve 22 olayın 16'sı sepeti geçiyor. Taban H3, excess60'ta hem TRAIN (+0.167) hem HOLDOUT (+0.351) pozitif olan tek hipotez. Ancak `H3_RETEST` bu iddiayı taşıyacak kadar kanıt vermiyor: holdout'ta 7 olaydan yalnız 3'ünün 20m sonucu var. **Düzeltme:** bu cümle ilk yazımda "holdout'ta olay yok (n=0)" diyordu; n=0 olan `H3_SLOW_SETUP`'un holdout'u. `H3_RETEST` holdout excess20 +0.217, excess60 +0.275 — üç gözlemle yön iddiası taşımaz. Sayılar artık elle değil, `hypothesis_lab_v21/entry_summary.csv` tablosundan deftere okunuyor (`ARASTIRMA/DEFTER/`).

**H4** — 0 tetik. Nedeni artık ölçülü: 280 armed snapshot'ın **%100'ünde** eksik olan tek koşul `fresh_bear3_or5`. Armed anına en yakın taze 3m/5m DN olayının zaman uzaklığı dağılımı ±15 dakikalık bantta **tek bir gözlem bile içermiyor**; medyan uzaklık 79 dakika (öncesinde), 280 armed snapshot'ın 106'sı hiç DN olayı görmemiş sembollere ait. Yani iki koşul "nadiren aynı anda" değil, bu veride saatlerce ayrık. Eşik gevşetmek bunu çözmez; bant ±15 dakikaya açılsa bile tetik sayısı sıfır kalır.

**H5** — tek tutarlı pozitif bölgesi çok kısa ufuk: HOLDOUT'ta excess 3m +0.105 ve 5m +0.127, sonrasında sert negatif (60m -0.442). TRAIN'de tüm ufuklarda zayıf pozitif. H5 incelenecekse 3–5 dakikalık olay olarak incelenmeli, 20/60m sonuçlarıyla yargılanmamalı.

**H6 / H7** — armed ve trigger aşamaları `shadow_research.py` içinde tanımı gereği `False`; bunlar tarayıcı ve bağlam katmanı. "0 armed" bir eksiklik değil, tasarım. H7'nin 927 setup kaydı tam biçimli bağlam gözlemidir.

**Rejim uyarısı**: H4 ve H5 short hipotezleri; bugünün yükselen/genişleyen rejiminde üretmemeleri ya da kaybetmeleri hipotezler hakkında değil, örneklem rejimi hakkında bilgi verir. Bunlar için düşen rejim verisi toplanmadan karar verilmemeli.

## 3. Çıkış yöntemi: dinamik çıkışlar ufka kadar tutmayı geçmiyor

`exit_summary.csv`'deki 66 eşleştirilmiş karşılaştırma:

| Politika | daha iyi | daha kötü | eşit | medyan fark |
|---|---:|---:|---:|---:|
| FLOW_STRUCTURE | 21 | 40 | 5 | -0.052 |
| ATR_GIVEBACK | 15 | 24 | 27 | 0.000 |

FLOW_STRUCTURE hem TRAIN (-0.044) hem HOLDOUT (-0.103) medyanında zarar veriyor: ilk karşıt akış/yapı sinyali kazançlı işlemleri erken kesiyor. ATR_GIVEBACK satırlarının 27'si tam sıfır, yani kural çoğu olayda hiç tetiklenmiyor (1 ATR ilerleme nadiren görülüyor); tetiklendiğinde de kazandırmaktan çok kaybettiriyor. Bu turda çıkış kuralı değiştirilmedi; bulgu, mevcut iki adayın ufka kadar tutmaya üstünlüğü olmadığıdır.

## 4. Yeni bulunan boyut: kurulumun olgunlaşma süresi

Setup'tan tetiğe geçen süreye göre long olaylar (H1+H2+H3):

| setup→trigger | n | excess5 | excess20 | excess60 |
|---|---:|---:|---:|---:|
| 0 sn | 14 | -0.122 | -0.212 | -0.132 |
| 1–5 dk | 16 | -0.085 | -0.225 | -0.027 |
| 5–15 dk | 38 | -0.046 | -0.184 | 0.101 |
| >15 dk | 14 | -0.097 | 0.208 | 0.400 |

\>15 dk kovası bölümlere ayrıldığında da pozitif kalıyor (TRAIN +0.472, HOLDOUT +0.081). Üç ayrı hipotezde aynı yöne işaret ettiği için bu, tek bir varyantın şansından farklı bir sinyaldir. Menüye üç yeni aday eklendi (`hypothesis-candidates-v2.2`):

| Aday | n | excess20 | Holdout n | Holdout excess20 |
|---|---:|---:|---:|---:|
| H1_BASE | 39 | -0.195 | 13 | 0.042 |
| H1_SLOW_SETUP | 6 | 0.067 | 3 | 0.081 |
| H2_BASE | 24 | -0.136 | 7 | -0.240 |
| H2_SLOW_SETUP | 4 | 0.490 | 2 | 0.342 |
| H3_BASE | 23 | -0.152 | 3 | 0.138 |
| H3_SLOW_SETUP | 4 | 0.387 | 0 | — |

Örneklemler 4–6 olay; hepsi INSUFFICIENT sayılır ve hiçbiri işlem kuralına yükseltilmez. Değeri, bir sonraki günlerde toplanacak veride izlenecek somut ve ucuz bir ayrımı tanımlamasıdır. Eşik 15 dakika olarak sabitlendi ve optimize edilmedi.

## 5. Denenip elenen fikirler

Bu turda üretilip veriyle reddedilen üç fikir kayda geçiyor, çünkü elenen koşul da gelişmedir:

- **flow_15m'i hizalama şartına eklemek.** Hizalama desenleri tablosunda tüm bileşenleri UP olan kova tek negatif olmayan kovaydı, ama 15m yapı+akış şartı bölümlere ayrıldığında H1 ve H3'ün TRAIN excess20 değerini kötüleştiriyor, holdout'u düzeltmiyor. Reddedildi.
- **Hizalama oluştuktan sonra ≥60 sn bekleyip girmek.** 84 long olayın 74'ü hizalama 1 dakikadan gençken tetikleniyor; bekleyen kova TRAIN'de -0.431, HOLDOUT'ta +0.081, n=3/3. Karar verilemez, reddedildi.
- **`cvd5_negative` vetosunu H1'e kalıcı filtre yapmak.** net5 ölçütünde en tutarlı görünen filtre, excess20 ölçütünde iki bölümde de zarar veriyor. Reddedildi; ölçüt farkı ayrıca yukarıda kayda geçti.

## 6. Bu turda koda uygulananlar

- `hypothesis_candidates.py` → v2.2: `H1_SLOW_SETUP`, `H2_SLOW_SETUP`, `H3_SLOW_SETUP` eklendi. Eski varyantların hiçbiri silinmedi; menü kanıt olarak duruyor. `slow_setup` yalnız tetik anında bilinen `setup_to_trigger_sec` alanını okur, ileriye bakmaz.
- `hypothesis_lab.py`: karşılaştırma tablosuna holdout excess sütunu ve karar ölçütünün excess olduğu notu eklendi.
- `research_updates.py`: iki hata düzeltildi. (1) Daha önce işlenmiş bir kaynak dosya kaybolduğunda yalnız en yeni runın snapshot parçaları kontrol ediliyordu; kaybolan `outcomes.jsonl` veya eski runların kaynakları sessizce "henüz yok" sayılıyordu. Artık işlenmiş her kaynağın yokluğu çalışmayı durduruyor. (2) `pending_outcomes` olgunlaşmamış kayıtlarla gerçek eksikleri aynı sayıda topluyordu ve bu sayı hiç sıfırlanamıyordu. Artık ufku dolduğu hâlde sonucu olmayanlar (`ripe_missing_outcomes`, kapatılabilir gerçek eksik) ile beklemesi gerekenler (`immature_outcomes`) ayrı raporlanıyor; ilki varsa çıktı `SONUCLARI_HESAPLA.bat` öneriyor. Ölçüt `tracker_v2` ile aynı: t0 + 60 dk + 30 sn, çalışma sürüyorsa +6 dk.
- `test_research_updates.py` eklendi: 18 test; değiştirilmiş/kısalmış/kaybolmuş kaynak, eksik run_meta sayısı, yarım satır, revize sonuç, baseline hash kontrolü ve ripe/immature ayrımı kapsanıyor.

Bu turda **değiştirilmeyenler**: üretim indikatörleri ve alarm formülleri, H1–H5 eşikleri, çıkış kuralları, mevcut run klasörlerindeki raporlar. `hypothesis_lab_v21/KARSILASTIRMA.md` kasıtlı olarak üzerine yazılmadı; v2.2 tablosu ancak lab yeniden çalıştırıldığında klasöre yazılır.

## 7. Sonraki tur için gereken kanıt

- Farklı gün ve özellikle düşen/sıkışan rejim verisi; H4 ve H5 hakkında bugünden karar çıkarılamaz.
- Her hipotez için 30+ holdout olay; bugün en kalabalık aday 13 holdout olayında.
- H4 için armed durumu ile yapı kırılımı arasındaki gecikme dağılımının başka günlerde de ölçülmesi: bağ hiç yoksa H4 tanımı bu hâliyle gözlenemez sayılmalı.
- H2 ve H3'ün 30–60 dakikalık ufuklarının ayrı olay tanımıyla sınanması.
- Gerçek maliyet ve funding; şu an sabit 10 bps varsayımı var.
