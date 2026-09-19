# Tur 4 — giriş/çıkış planı, coin sınıfı ve belirteç bütünü (2026-09-18)

Kapsam: yalnız `run_20260918_112149`. Yeni veri yok; ölçüm kodu genişledi. Üretim indikatörleri ve alarm formülleri değişmedi. Hiçbir satır işlem kuralı değildir.

## 1. Eklenen: plan ızgarası (3 giriş × 5 çıkış), aynı olaylarda eşleşmiş

Politikalar ölçümden **önce** yazıldı, hiçbir sayısı aranmadı. Giriş: `AT_TRIGGER` (tetikten sonraki ilk gözlem), `PULLBACK_25` (%0.25 geri çekilme, en çok 10 dk beklenir, gelmezse işlem yok), `CONFIRM_3M` (3 dk sonra hâlâ lehteyse gir). Çıkış: `HOLD_HORIZON`, `PEAK_TIME` (ailenin ölçülen medyan tepe dakikası), `STALL_10M` (10 dakikadır yeni lehte uç yok — "yükselip düzleşme"), `FLOW_STRUCTURE`, `ATR_GIVEBACK`. Dolum her zaman sinyalden **sonraki** gözlemdedir.

## 2. Ana sonuç: sorun çıkışta değil, girişte

Aynı olaylarda, `AT_TRIGGER` girişiyle çıkış politikaları (taban = ufka kadar tut):

| Aday | HOLD net / isabet | STALL_10M | FLOW_STRUCTURE | ATR_GIVEBACK | PEAK_TIME |
|---|---|---|---|---|---|
| H3_RETEST | **+0.578 / %87** | −0.114 (−0.72) | −0.100 (−0.54) | +0.133 (−0.25) | +0.129 (−0.29) |
| H3_BASE | **+0.590 / %73** | −0.173 (−0.61) | −0.092 (−0.46) | +0.095 (−0.27) | −0.047 (−0.32) |
| H2_BASE | **+0.293 / %61** | −0.156 (−0.25) | −0.000 (−0.20) | +0.029 (−0.12) | −0.027 (−0.20) |
| H1_BASE | **+0.205 / %63** | −0.069 (−0.11) | −0.072 (−0.13) | +0.018 (−0.03) | −0.006 (−0.20) |

(parantez: aynı olaylarda tabana göre eşleşmiş fark)

**Beş çıkış politikasının beşi de ufka kadar tutmayı geçemedi.** Sebep karakter tablosunda: ilk karşıt akış sinyali medyan 5–7. dakikada geliyor, tepe ise 30–42. dakikada. "Yükselip düz-ser" gözlemi doğru ama erken kesmek, düzleşmeden kaçınmanın bedelinden pahalı.

**Girişte ise kazanç var.** `PULLBACK_25` (kovalama, geri çekilmeyi bekle) eşleşmiş farkı: H1_BASE **+0.625** (8 eşleşme), H8_IGNITION +0.270, H3_BASE +0.229, H3_RETEST +0.147 (PEAK_TIME ile). Bedeli: dolum oranı %20–35, yani olayların üçte ikisinde işlem açılmıyor. Örneklemler 8–12 eşleşme; bu bir kural değil, izlenecek somut bir aday.

## 3. Coin sınıfı: aynı hipotez her coinde aynı şeyi yapmıyor

Sınıflar runın kendi verisinden: büyüklük = 5 dakikalık **gerçek $ hacim** üçlükleri, oynaklık = 1m ATR medyanı (%0.182). Taban planla:

| Aday | En iyi sınıf | En kötü sınıf |
|---|---|---|
| H3_RETEST | BUYUK/SAKIN net +0.91, isabet **%100** (9 dolum) | KUCUK/SAKIN +0.53, %75 |
| H3_BASE | BUYUK/OYNAK +1.08, %75 · BUYUK/SAKIN +0.69, %89 | KUCUK/SAKIN +0.05, %50 |
| H1_BASE | KUCUK/SAKIN +0.28, %80 · BUYUK/SAKIN +0.28, %78 | **ORTA/OYNAK −0.77, %33** |
| H1_HTF_ALIGN | BUYUK/SAKIN +0.40, %88 | ORTA/OYNAK −0.77, %33 |
| H2_GAP_EXPANDS | BUYUK/OYNAK +0.37, %75 | ORTA/OYNAK −0.32, %20 |
| H5_BASE | ORTA/OYNAK +0.20, %56 | KUCUK/SAKIN −0.27, %20 |
| H8_IGNITION | KUCUK/OYNAK +0.42, %83 | KUCUK/SAKIN −0.06, %46 |

İki desen: **H1/H2 ailesi orta boy oynak coinlerde bozuluyor**, **H3 ailesi büyük coinlerde en iyi**, **H5 (short) küçük sakin coinlerde çalışmıyor ama orta/oynakta nefes alıyor**. Sınıf başına 3–9 dolum; bu bir eğilim, kanıt değil.

## 4. Belirteç bütünü kılavuza girdi

`hypothesis_candidates.INDICATORS` her aile için tetik anında okunan alanları ve eşiklerini insan diliyle tutuyor (H1–H8). Kılavuz bunu her turda basıyor, yani tanım değişince kılavuz da değişiyor. `KULLANIM_KILAVUZU.md` artık aday başına: karar ufku, tepe zamanı, MFE/MAE ve ödül/risk, geri verme, ilk karşıt sinyal, başarı oranı, kanıt seviyesi, **belirteç bütünü**, **plan** ve **hangi coin sınıflarında** bölümlerini içeriyor.

## 5. Bu turda düzeltilen üç kendi hatam

1. **Coin büyüklüğü yanlış alandan geliyordu.** `fc_5m_notional` bir notional değil, 0–1 arası normalize edilmiş güven bileşeni. Gerçek `notional_5m` ($) alanına geçildi; ETH/BNB/XRP'nin 1.0'da satüre olması bu yüzdendi.
2. **Tur kimliği ölçüm kodunu içermiyordu.** Aynı veriyi yeni ölçüm koduyla işlemek `NO_NEW_EVIDENCE` dönüyordu; artık `code_hashes` de kimliğe dâhil.
3. 🔴 **Eleme kuralı aynı kanıtı iki kez saydı.** Tur 3 ve 4 aynı run/replay olduğu için `H1_FLOW_CONFIRM`, `H8_IGNITION`, `H8_IGNITION_QUIET` yanlışlıkla **ELENDI** oldu. Kural düzeltildi: eleme artık **farklı kanıt turu** (farklı run veya farklı replay) ister. Yanlış tur geri alınıp doğru kuralla yeniden kaydedildi; regresyon testi eklendi.

## 6. Doğrulama

`test_research.py` 16/16 · `test_research_updates.py` 18/18 · `test_research_ledger.py` **28/28**.

Tur 4 durumu: durum değişikliği yok — **0 ADAY**, 1 VERI_YOK (H4), 2 TARAYICI, kalanı YETERSIZ; açık eksik 16.

## 7. Değiştirilen dosyalar

| Dosya | Değişiklik |
|---|---|
| `trade_plan.py` | **YENİ** — giriş/çıkış politikaları, eşleşmiş plan ızgarası, coin sınıfları, `PLAN.md` |
| `hypothesis_candidates.py` | `INDICATORS` belirteç bütünü (H1–H8) |
| `hypothesis_lab.py` | plan ızgarası entegrasyonu, coin sınıfı sütunu, audit'e belirteç/politika bilgisi |
| `research_ledger.py` | plan + coin sınıfı okuma, kılavuza belirteç/plan/coin bölümleri, tur kimliğine kod hash'i, eleme kuralı farklı kanıt şartı |
| `test_research_ledger.py` | 27 → 28 test |
