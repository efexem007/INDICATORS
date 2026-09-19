# v2.4 — PULLBACK varyantları ve dört indikatör maddesinin ölçülmüş karşılığı (2026-09-18)

Kapsam: `run_20260918_112149` (tur 4, revizyon). Menü v2.3 → **v2.4**, 19 → **29 varyant**. Eski varyantların hiçbiri silinmedi. Üretim indikatörleri ve alarm formülleri değişmedi. Hiçbir satır işlem kuralı değildir.

Yöntem notu: dört indikatör maddesi **tanımı sessizce değiştirerek değil**, ölçülebilir varyant olarak eklendi. Böylece "daha iyi mi" sorusu her turda kendi kanıtıyla yanıtlanıyor ve eski tanım karşılaştırma tabanı olarak duruyor.

## 1. PULLBACK: kovalamamak ölçüldü

Olay artık taban tetikte değil, **%0.25 geri çekilmenin gerçekleştiği snapshot'ta** doğuyor (10 dk pencere, gelmezse olay yok). Böylece `fwd_ret`, `excess` ve karakter alanları gerçek giriş anına bağlı.

| Varyant | Olay | Küme | Net (karar ufku) | Excess ALL | Holdout excess | Taban excess (ALL / HO) |
|---|---:|---:|---:|---:|---:|---|
| H3_BASE_PULLBACK | 9 | 6 | +0.173 | **+0.662** | **+0.497** | +0.351 / +0.351 |
| H3_RETEST_PULLBACK | 8 | 7 | **+1.009** | +0.591 | +0.489 | +0.275 / +0.275 |
| H8_IGNITION_PULLBACK | 12 | 10 | −0.038 | +0.054 | **+0.237** | −0.159 / −0.185 |
| H1_BASE_PULLBACK | 10 | 8 | +0.352 | −0.092 | −0.121 | −0.234 / +0.103 |

H3 ailesinde geri çekilmeyi beklemek tabanı geçiyor; H8'de negatif excess'i pozitife çeviriyor; **H1'de ise geçmiyor** — bu, plan ızgarasındaki "H1_BASE + PULLBACK_25 = +0.625" satırıyla çelişiyor. Sebep: plan ızgarası taban olayların alt kümesini eşleştirir, varyant ise kendi 60 dakikalık tekilleştirme akışını kurar; ikisi aynı olay kümesi değildir. 8–12 olayla ikisi de kanıt değil; ayrım artık her turda kendi kaydını biriktiriyor.

## 2. REALF: yüzdelik de ayırmıyor

`H1_REALF_PCTL` = H1 + `realf_percentile ≥ 60`.

| | Olay | Küme | Excess60 ALL | Holdout |
|---|---:|---:|---:|---:|
| H1_BASE | 39 | 17 | −0.216 | +0.103 |
| H1_REALF_PCTL | 23 | 12 | −0.214 | +0.174 |

Yüzdelik kapısı olayların %41'ini eliyor ve excess'i **değiştirmiyor**. Yani sorun ölçeğin ham mı yüzdelik mi olduğu değil: REALF bu veride tetik, kaçırılan hareket ve sıradan gözlemi ayırmıyor (dağılım p25–p75 = 43–56, medyanlar 46/45/49). Eksik E-0021 açık kalıyor; çözüm ölçek değişimi değil, REALF'in bileşen tanımına bakmak.

## 3. CVD pencereleri: "çelişki bölgesi" kötü değil

| Varyant | Olay | Küme | Excess60 ALL | Holdout |
|---|---:|---:|---:|---:|
| H1_FLOW_AGREE (cvd_1m ve cvd_5m ikisi de +) | 38 | 15 | −0.254 | −0.214 |
| H1_FLOW_MIXED (ikisi ters işarette) | 27 | 17 | **+0.003** | **+0.140** |

Onay kapılarının attığı bölge, tuttuğu bölgeden **kötü değil**. İki pencereyi birden şart koşmak bu veride kanıtlanmış bir fayda getirmiyor. (Sınır: iki varyant ayrı tekilleştirme akışı olduğu için olayların tam bölüntüsü değildir; yön göstergesi olarak okunmalı.) Eksik E-0022 açık; doğru adım tek bir akış durumu tanımlayıp ufkunu açıkça yazmak.

## 4. Yapı tazeliği: sorun bar/dakika değil

`H4_FRESH_15M` = H4 armed + **15 dakika** içinde 3m/5m DN olayı → **hâlâ 0 tetik**. Bar yerine dakika kullanmak H4'ü canlandırmadı: bu veride H4'ün armed anı ile ayı yapı olayı gerçekten hiç örtüşmüyor (daha önce ölçülen medyan uzaklık 79 dakika). Bu, H4 tanımının bu hâliyle **gözlenemez** olduğunun ikinci bağımsız kanıtı (E-0003 / E-0007).

`H5_FRESH_15M` = H5 armed + 15 dk içinde 1m/3m DN: 13 olay, 9 küme, excess60 ALL −0.190, holdout +0.084. Taban H5'e (20 olay) göre daha az olay, belirgin üstünlük yok.

Dakika tazeliği yine de kalıcı bir kazanım: çok zaman dilimli şartların neden gözlenemez olduğunu gösteren `fresh_within()` artık menüde ve `BAR_MINUTES` tablosuyla açık.

## 5. Akış güveni tabanı: küçük ama tek yönlü iyileşme

`H1_CONF_FLOOR` = H1 + `flow_confidence_5m ≥ 50`: 37 olay (2 olay eleniyor), excess60 ALL **−0.041** (H1_BASE −0.216), holdout −0.007 (H1_BASE +0.103). ALL tarafında belirgin iyileşme, holdout'ta düz. Yapısal zayıf ölçümlü coinleri dışarıda tutmak ucuz bir düzeltme gibi görünüyor; E-0024 için ilk somut ölçüm.

## 6. Altyapı: şişkinlik ve kayıt düzeni

- **Saatlik `snapshots_*.csv` artık yazılmıyor.** JSONL asıl kaynak; CSV onun skaler alt kümesiydi. `snapshots_csv_uret.py` birebir geri üretiyor — doğrulandı: 509/509 satır, tüm sütunlar aynı. Öz-test hem açık hem kapalı yolu ölçüyor.
- **Aynı kanıt yeniden ölçülünce defter yeni tur açmıyor, turu revize ediyor** (`revisions` sayacı). Tur kimliği artık ölçüm kodunu da içeriyor, böylece hangi kodun ürettiği kayıtlı. 3 turluk şişme yerine 1 tur + revizyon.
- **Bu klasör kendi günlüğünü tutuyor:** `GÜNLÜK/` + `gunluk_ekle.py` (SORUN → ÇÖZÜM → DOĞRULAMA şablonu, indeks otomatik) ve `CLAUDE.md` (bu klasörde çalışan her ajan için kural: `project z`'ye yazma, her işi günlüğe yaz, belgeleri güncel tut).
- **Klasör düzeni** hiçbir şey silinmeden sadeleşti: referans belgeler `BELGELER/` altına taşındı (kod içi yollar güncellendi), kök `README.md` klasör haritasını ve iş akışını anlatıyor.

## 7. Doğrulama

`test_research.py` 16/16 · `test_research_updates.py` 18/18 · `test_research_ledger.py` **29/29** · `tracker_v2.py selftest` TÜMÜ GEÇTİ · `live_tracker.py --selftest` TÜMÜ GEÇTİ.

Tur 4 (revizyon 2): 29 varyant, **0 ADAY**, 2 VERI_YOK (H4_BASE, H4_FRESH_15M), 2 TARAYICI, kalanı YETERSIZ; açık eksik 17.

## 8. Sonraki veri için beklenti

Yeni tarama başladığında: `YENI_LOGLARI_HAZIRLA.bat` → `SONUCLARI_HESAPLA.bat` → `research_report.py --fetch-history` → `hypothesis_lab.py` → `research_ledger.py`. Yeni run farklı bir kanıt turu açacağı için ilk kez **iki bağımsız gün** karşılaştırılabilecek: `auto:single-day` eksiği kapanabilir, eleme kuralı ilk kez gerçekten çalışabilir ve PULLBACK varyantları ikinci ölçümünü alacak.
