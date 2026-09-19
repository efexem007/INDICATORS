# Tur 3 — işlem karakteri, karar ufku, küme sayımı, H8 ailesi ve indikatör teşhisi (2026-09-18)

Kapsam: yalnız `run_20260918_112149`. Yeni veri toplanmadı; menü v2.3'e çıktı, lab yeniden üretildi, defter tur 3'ü açtı. Üretim indikatörleri ve alarm formülleri **değişmedi**. Hiçbir satır işlem kuralı değildir.

## 1. Uygulananlar

**(a) Karar ufku hipotez başına, ölçülen tepe zamanından türüyor.** Kural sabit: *medyan tepeyi içeren en küçük mevcut ufuk*. Tur 2 ölçümü → H1 35 dk, H2 41 dk, H3 41 dk, H5 15 dk ⇒ H1/H2/H3 için 60 dk, H4/H5/H6/H8 için 20 dk. Ufuk getiriye göre seçilmiyor; lab her turda tepeyi yeniden ölçüyor ve sapmayı `KARAKTER.md` + `audit.json` içinde bildiriyor.

**(b) Kanıt artık kümede sayılıyor.** 10 dakikalık kovalar: aynı kovadaki olaylar birlikte hareket ettiği için tek kanıt sayılıyor. Etkisi hemen görüldü: `H1_BASE` 39 olay ama **17 küme**, holdout 13 olay ama **5 küme**. Durum merdiveni artık kümeye bakıyor → `H1_BASE` ve `H1_FLOW_CONFIRM` IZLENIYOR'dan **YETERSIZ**'e düştü. Bu bir kötüleşme değil, sayımın dürüstleşmesidir.

**(c) İşlem karakteri ölçülüyor ve kılavuza dönüşüyor.** Her aday için: en güçlü hareket ne zaman geliyor (medyan tepe dakikası, ≤10/20/30 dk payları), MFE/MAE, tepeden geri verme, en kötü anın zamanı, ilk karşıt akış sinyalinin zamanı, karar ufkunda isabet oranı. Çıktılar: `hypothesis_lab_v21/character.csv` + `KARAKTER.md`, ve her turda yeniden üretilen `ARASTIRMA/DEFTER/KULLANIM_KILAVUZU.md`.

**(d) Kalite vetosunun maliyeti ölçülüyor.** `veto_suppressed.csv` + `veto_cost.csv`: vetonun eldiği olaylar ve sonuçları. Bu turda vetolu 215 snapshot'ın hiçbirinde H1–H3 tetik koşulu sağlanmıyordu; yani veto bu turda doğrudan bir tetik kesmedi — kaçırılan 4 hareket tetik öncesi aşamada elendi.

**(e) H8 ailesi eklendi** (kaçırılanların %72'si setup aşamasında eleniyordu): `H8_IGNITION` = hacim (realf_rvol ≥ 1.35 = p90) + alıcı baskınlığı (buyer_ratio_1m ≥ 80 = p90) + cvd_1m > 0, **REALF/yapı/fatigue/unpriced kapısı olmadan**; `H8_IGNITION_QUIET` = aynısı + öncesinde sıkışık 1m ATR (≤ medyan). Eşikler bu runın kendi dağılım yüzdelikleri; getiriye bakılmadan seçildi.

## 2. H8 sonucu: teyitsiz ateşleme kenar taşımıyor

| Aday | Olay | Küme | İsabet | Tepe | MFE | MAE | excess20 TR/HO |
|---|---:|---:|---:|---:|---:|---:|---|
| H8_IGNITION | 34 | 18 | %50 | 58 dk | %0.79 | %-0.35 | -0.159 / -0.185 |
| H8_IGNITION_QUIET | 25 | 19 | %48 | 58 dk | %0.76 | %-0.35 | -0.182 / -0.263 |

Hareket var (MFE %0.79, geri verme yalnız %0.16) ama **excess iki bölümde de negatif**: ateşleme sonrası fiyat yükseliyor, sepet de yükseliyor. Bu turda H8 beta üretiyor, alfa değil. Ayrıca ölçülen tepe 58 dakikada — dondurulmuş 20 dk ufkunun dışında; defter bunu `auto:horizon-drift` eksiği olarak açtı (5 varyantta sapma var).

## 3. İndikatör teşhisi (6.100 satır üzerinde)

**REALF ayırt etmiyor.** Skor dağılımı çok dar: genel p25–p75 = **43–56**, medyan 49. Tetik anında medyan **46**, kaçırılan hareketlerde **45**. Yani tetik, kaçırılan ve sıradan gözlem neredeyse aynı REALF değerine sahip. `H1`'in `realf 35-55` kapısı pratikte orta kütlenin tamamını kapsıyor → filtre gibi görünen ama ayırmayan bir şart. (E-0021)

**CVD pencereleri birbiriyle çelişiyor.** `cvd_1m` ile `cvd_5m` yalnız **%64** aynı işarette. İkisini birden isteyen onay kapıları olayların üçte birini keyfi biçimde eliyor; iki pencere aynı şeyi ölçmüyor. (E-0022)

**Yapı olay tazeliği bar bazlı olduğu için çok-TF şartlar gözlenemez.** Taze olay (≤3 bar) tek başına: 1m %11.6, 3m %11.1, 5m %12.4, 15m %14.5. Ama kesişim: 1m+3m **%1.9**, 1m+3m+5m **%0.4** (6.100 satırda 22 gözlem). 3 bar 1m'de 3 dakika, 5m'de 15 dakika demek; aynı anda taze olma şartı bu yüzden neredeyse imkânsız. **H4'ün sıfır tetiği bunun özel hâli.** Tazelik dakika cinsinden tanımlanmalı. (E-0023)

**Coin bazında akış güveni tabanı yok.** `flow_confidence_5m` medyanı OGUSDT 32, TNSRUSDT 43, ZKCUSDT 54 — bu coinlerde akış alanları yapısal olarak zayıf ölçüm, ama kanıt aynı ağırlıkta sayılıyor. (E-0024)

**Sorun görünmeyenler:** `realf_source_quality` %90 tam 100 (kalan 93–99.7), `cvd_5m_delta` boşluk oranı %1, orderbook stale 32 satır. Fatigue bu turda incelenmedi (kullanıcı: son sürüm).

## 4. Defter durumu (tur 3)

- Durum değişikliği: `H1_BASE`, `H1_FLOW_CONFIRM` → YETERSIZ (küme sayımı); `H8_IGNITION`, `H8_IGNITION_QUIET` → YETERSIZ (yeni).
- **ADAY yok.** En yüksek holdout kümesi 7 (H2_BASE); eşik 30.
- Açık eksik: 16 → 4'ü indikatör (E-0021…E-0024), 1'i ufuk sapması (E-0013), gerisi önceki turlardan.
- 🔴 **Kendi hatam ve düzeltmesi:** durgunluk eksiği (E-0014…E-0020) yanlış tetiklendi — tur 3'ün küme sayısını, kümesi olmayan tur 1–2'nin ham olay sayısıyla karşılaştırdım. Kural düzeltildi (üç turun da küme temeli olmalı), yanlış açılan 7 eksik gerekçesi yazılarak kapatıldı, regresyon testi eklendi.

## 5. Doğrulama

`python test_research.py` 16/16 · `python test_research_updates.py` 18/18 · `python test_research_ledger.py` **27/27** (7 yeni test: küme sayımının durumu belirlemesi, karar ufku hücresinin yargılaması, karakterin taşınması ve tabloya basılması, ufuk sapması eksiği, üç düz turda durgunluk, büyüyen kanıtın durgunluk sayılmaması, kılavuzun başarı/risk ile üretilmesi).

## 6. Değiştirilen dosyalar

| Dosya | Değişiklik |
|---|---|
| `hypothesis_candidates.py` | v2.3: karar ufku kuralı + dondurulmuş tepe ölçümleri, H8 ailesi, `ignore_quality` maskesi, `update_masks` |
| `hypothesis_lab.py` | `observed_shape` (karakter), küme sayımı, karar ufkuna göre karşılaştırma, `character.csv`/`KARAKTER.md`, `veto_suppressed.csv`/`veto_cost.csv`, sapma denetimi |
| `research_ledger.py` | karar ufku hücresi, küme temelli merdiven, karakterin taşınması, `KULLANIM_KILAVUZU.md`, ufuk sapması + durgunluk eksikleri |
| `test_research_ledger.py` | 20 → 27 test |
| `ARASTIRMA/DEFTER/` | tur 3 + kullanım kılavuzu |
