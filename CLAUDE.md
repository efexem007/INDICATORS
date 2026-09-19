# CLAUDE.md — SON VERSION (canlı takip + hipotez araştırması)

> **Bu dosyayı önce oku.** Bu klasörde çalışan her AI/agent, kullanıcı ayrıca hatırlatmasa bile
> aşağıdaki kuralları uygular. Tek seferlik değil, **her turda** geçerlidir.

---

## 🔴 KALICI KURAL 1 — Burası `project z` değildir

Bu klasör **ayrı bir git deposudur** ve AVCI/`project z` deposuna ait değildir.

- Buradaki işler **`project z/uygulama günlügü/`'ne yazılmaz**, **G numarası alınmaz**, indekse eklenmez.
- `project z` içinde hiçbir şey başlatılmaz, değiştirilmez.
- Kayıt bu klasörde durur: kısa iş kaydı `GÜNLÜK/`, ayrıntılı araştırma `ARASTIRMA/`.

## 🔴 KALICI KURAL 2 — Yapılan her iş `GÜNLÜK/`'e yazılır

```bash
python gunluk_ekle.py "Kısa başlık" --sorun "..." --cozum "..." --dogrulama "..." \
    --dosya "dosya.py: ne değişti"
```

- Biçim sabit: **SORUN → ÇÖZÜM → DOĞRULAMA + değiştirilen dosyalar**.
- `GÜNLÜK/00_INDEKS.md` otomatik güncellenir; elle düzenlenmez.
- Ayrıntılı sayı/tablo günlüğe kopyalanmaz; `ARASTIRMA/` içindeki tarihli rapora işaret edilir.

## 🔴 KALICI KURAL 3 — Dokümantasyon güncel kalır

Bir davranışı değiştirdiysen ilgili belgeyi **aynı turda** güncelle:

| Değişen | Güncellenecek |
|---|---|
| Alanlar, logger davranışı | `BELGELER/LOGGER_V2_ALANLAR.md` |
| Araştırma akışı, tur döngüsü, defter | `BELGELER/SHADOW_ARASTIRMA_KILAVUZU.md` |
| Hipotez tanımı / belirteç | `hypothesis_candidates.py` (`VARIANTS`, `INDICATORS`) + kılavuz |
| Klasör düzeni, giriş noktaları | `README.md` |

## 🔴 KALICI KURAL 4 — Araştırma disiplini

- **Yalnız en yeni çalışma incelenir.** Arşiv yeniden taranmaz (`research_updates.py` + `research_ledger.py`).
- **Eşik aranmaz.** Karar ufku ölçülen tepe zamanından türer; aday menüsü ölçümden önce dondurulur.
- **Kanıt kümede sayılır** (10 dk kovası), ham olayda değil.
- **Hiçbir sonuç işlem kuralı değildir.** ADAY olmayan bir hipotez için sayılar yalnız davranış tarifidir.
- Üretim indikatörleri ve alarm formülleri (REALF, Fatigue, Structure) araştırma turlarında **değiştirilmez**;
  denenecek her şey aday menüsüne **yeni varyant** olarak eklenir, eskisi silinmez.
- Bir hata bulursan düzelt ve **günlüğe yaz**; sessizce düzeltme yok.

## 🔴 KALICI KURAL 5 — Kayıt şişirilmez

- Saatlik CSV kapalıdır (`tracker_v2.WRITE_HOURLY_CSV = False`): JSONL asıl kaynaktır, CSV onun skaler
  alt kümesidir. Gerekirse `python snapshots_csv_uret.py logs/run_<id>` ile birebir üretilir.
- Aynı kanıt (aynı run + aynı replay) yeniden ölçülürse defter **yeni tur açmaz, turu revize eder**.

---

## Çalıştırma

| İş | Komut |
|---|---|
| Canlı takip (20 coin) | `takip_TEST_20.bat` |
| Eksik sonuçları tamamla (**ağ ister**) | `SONUCLARI_HESAPLA.bat` |
| Yeni logları işle + defteri güncelle | `YENI_LOGLARI_HAZIRLA.bat` |
| Araştırma raporu (**ağ ister**) | `python research_report.py logs/run_<id> --fetch-history` |
| Aday değerlendirmesi | `python hypothesis_lab.py logs/run_<id>` |
| Defter turu | `python research_ledger.py` |
| Testler | `python test_research.py`, `python test_research_updates.py`, `python test_research_ledger.py` |

Windows konsolunda Türkçe karakter için `PYTHONIOENCODING=utf-8`; `.bat` dosyaları `chcp 65001` yapar.
Binance bu makinede yalnız uygun ağda erişilebilir; erişim yoksa ağsız adımlar (defter, gelen kutusu,
lab, testler) yine çalışır.
