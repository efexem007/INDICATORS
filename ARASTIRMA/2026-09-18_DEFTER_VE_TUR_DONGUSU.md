# Tur defteri ve düzeltmeler — 2026-09-18 (düzenleme turu)

Kapsam: kod düzenlemesi. Yeni veri toplanmadı, kaynak loglara dokunulmadı, hiçbir üretim indikatörü/alarmı değişmedi. Amaç: her incelemenin yalnız **en yeni** çalışmaya bakması ve hipotez/eksik durumunun turdan tura **taşınıp ölçülebilmesi**.

## SORUN 1 — Kaydedilen iş "başarısız" görünüyordu

`research_updates.collect()` sonucu fonksiyonun içinde `print` ediyordu. Windows'ta stdout UTF-8 değilse (dosyaya yönlendirme, boru, görev zamanlayıcı) bu satır `UnicodeEncodeError` veriyordu — üstelik `db.commit()`'ten **sonra**. Sonuç: offsetler ilerlemiş olduğu hâlde `YENI_LOGLARI_HAZIRLA.bat` "Kaynak kontrolu basarisiz. Eski veri tekrar analiz edilmedi." yazıyordu ve o satırlar bir daha hiç raporlanmıyordu. Aynı sebeple 18 testin 14'ü hata veriyordu.

**Çözüm:** çıktı `report()` fonksiyonuna taşındı ve yalnız `__main__` içinde çağrılıyor; stdout UTF-8'e ayarlanıyor, olmazsa ASCII kaçışlı yazılıyor. `collect()` artık yalnız veri döndürür.

**Doğrulama:** `python test_research_updates.py` → **18/18 OK** (öncesinde 14 ERROR). Gerçek veride boru üzerinden çalıştırıldı, hata yok.

## SORUN 2 — sqlite bağlantısı kapanmıyordu

`mark_reviewed` içinde `with sqlite3.connect(...)` kullanılıyordu; bu bağlam yöneticisi commit eder ama **kapatmaz**. Windows'ta dosya kilidi kalıyor, durum klasörü silinemiyordu.

**Çözüm:** bağlantı `try/finally` ile kapatılıyor. **Doğrulama:** ilgili test artık temizlik hatası vermeden geçiyor.

## SORUN 3 — Gelişme hiçbir yerde taşınmıyordu

Her tur elle yazılan rapora bakıyordu; bir önceki turla karşılaştırma ve "hangi eksik kapandı" bilgisi kayboluyordu. Elle yazım hata da üretti: önceki rapor `H3_RETEST` için "holdout'ta olay yok (n=0)" diyordu; gerçekte holdout'ta 7 olay, 3 tam sonuç var, n=0 olan `H3_SLOW_SETUP`. Bu satır düzeltildi.

**Çözüm:** `research_ledger.py` ve `ARASTIRMA/DEFTER/` eklendi. Bir tur = bir run'ın lab tablosu. Makine durumu `ledger.json`, insan tabloları `HIPOTEZ_DEFTERI.md` + `EKSIKLER.md`. Sayılar `hypothesis_lab_v21/entry_summary.csv` tablosundan okunur; elle girilmez.

- **Tekrar sayma engeli:** aynı run + aynı menü sürümü + aynı replay hash'i ikinci kez tur açmaz (`NO_NEW_EVIDENCE`). Menü değişirse veya eksik sonuçlar tamamlandığı için replay değişirse yeni tur açılır.
- **Sabit durum merdiveni** (eşik aranmaz): `VERI_YOK` · `YETERSIZ` (<30 olay) · `IZLENIYOR` (30+ olay, holdout ince) · `ADAY` (excess hem TRAIN hem HOLDOUT'ta pozitif **ve** holdout 30+) · `ELENDI` (arka arkaya iki turda her ufukta pozitif değil, en az 10 olayla) · `TARAYICI` (H6/H7).
- **Eksikler taşınır ve ölçülür.** Otomatik eksik koşulu kaybolduğunda kendiliğinden kapanır; ölçüsü ilk→son olarak korunur, kapanınca da tabloda kalır. Elle eksik yalnız kanıt yazılarak kapanır.
- Menüden çıkarılan varyant silinmez, son ölçüsüyle kanıt olarak durur.

**Doğrulama:** `python test_research_ledger.py` → **20/20 OK**. Testler şunları kapsıyor: tekrar kayıt engeli, menü/replay değişince yeni tur, tetiksiz hipotezin eksiğinin tetik gelince kapanması, ADAY'ın iki bölüm + 30 holdout şartı, tek bölümün yetmemesi, elemenin iki tur ve 10 olay şartı, küçük örneklemin elenmemesi, eksik ölçüsünün trendi, ikinci günün tek-gün eksiğini kapatması, elle eksiğin kanıtsız kapanmaması, menüden çıkan varyantın korunması, sansürlü çıkış oranı eksiği, yabancı şema reddi, Δ sütunlarının büyümeyi göstermesi.

## SORUN 4 — v2.2 menüsü lab çıktısına yansımamıştı

Aday menüsüne `H1/H2/H3_SLOW_SETUP` eklenmişti ama run klasöründeki tablo hâlâ v2.1'di.

**Çözüm/Doğrulama:** `python hypothesis_lab.py logs/run_20260918_112149` yeniden çalıştırıldı; `audit.json` → `hypothesis-candidates-v2.2`, 17 varyant, replay hash'i aynı.

## SORUN 5 — Artımlı gelen kutusu hiç başlatılmamıştı

`ARASTIRMA/YENI_VERI_TAKIBI/` yoktu; ilk çalıştırma 6.100 satırın tamamını "yeni" sayacaktı.

**Çözüm/Doğrulama:** `python research_updates.py --baseline-latest` → 6.100 snapshot ve 5.773 sonuç "incelendi" olarak işaretlendi, batch üretilmedi. Bundan sonra yalnız gerçekten eklenen satırlar rapor edilir.

## Bu turun defter çıktısı (tur 1)

Run `run_20260918_112149`, menü `hypothesis-candidates-v2.2`, 6.100 satır, 327 sonuçsuz.

| Durum | Varyant |
|---|---|
| IZLENIYOR | H1_BASE (39 olay), H1_FLOW_CONFIRM (33) |
| YETERSIZ | H1_HTF_ALIGN, H2_BASE, H2_GAP_EXPANDS, H2_FLOW_CONFIRM, H3_BASE, H3_RETEST, H5_BASE, H5_HTF_ALIGN, H5_FRESH_BREAK, H1/H2/H3_SLOW_SETUP |
| VERI_YOK | H4_BASE |
| TARAYICI | H6_RESET, H6_DEEP_RESET |
| ADAY | — (hiçbiri 30 holdout olayına ulaşmadı) |

Açık eksik: 8 (4 elle + 4 otomatik). Otomatiklerin ölçüsü: holdout en iyi 13, tamamlanmamış sonuç 327, H4 tetik 0, farklı gün 1. Sansürlü çıkış oranı %16,2 olduğu için o eksik açılmadı (eşik %20).

## Değiştirilen dosyalar

| Dosya | Değişiklik |
|---|---|
| `research_ledger.py` | **YENİ** — tur defteri, durum merdiveni, eksik taşıma |
| `test_research_ledger.py` | **YENİ** — 20 test |
| `research_updates.py` | konsol çıktısı `report()`'a ayrıldı (UTF-8 güvenli); sqlite bağlantısı kapatılıyor |
| `YENI_LOGLARI_HAZIRLA.bat` | 2 adım: gelen kutusu → defter; hata durumunda defteri güncellemiyor |
| `BELGELER/SHADOW_ARASTIRMA_KILAVUZU.md` | "Tur döngüsü ve defter" bölümü |
| `ARASTIRMA/2026-09-18_ANALIZ_VE_HIPOTEZ_GELISIMI.md` | H3_RETEST düzeltmesi |
| `ARASTIRMA/DEFTER/` | `ledger.json`, `HIPOTEZ_DEFTERI.md`, `EKSIKLER.md` (tur 1) |
| `ARASTIRMA/YENI_VERI_TAKIBI/` | artımlı gelen kutusu başlangıcı |
| `logs/run_20260918_112149/hypothesis_lab_v21/` | v2.2 menüsüyle yeniden üretildi |

## Sonraki tur için gereken (sırayla)

1. `SONUCLARI_HESAPLA.bat` — 327 sonuçsuz snapshot'ı kapatır. **Ağ ister**; bu makinede Binance yalnız WARP açıkken erişilebilir.
2. `python research_report.py logs/run_20260918_112149 --fetch-history` (ağ ister) ve `python hypothesis_lab.py logs/run_20260918_112149`.
3. `python research_ledger.py` → tur 2. Replay hash'i değiştiği için tur açılır; Δ sütunları büyümeyi, `EKSIKLER.md` 327 → yeni değeri gösterir.
4. Farklı gün/rejim verisi toplandığında `auto:single-day` eksiği kendiliğinden kapanır.
