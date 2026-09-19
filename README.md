# SON VERSION — canlı takip ve hipotez araştırması

20 coinlik canlı takipçi (REALF / Fatigue / Structure motorları + akış ölçümü) ve onun kayıtları üzerinde
çalışan shadow araştırma katmanı. **Ayrı bir depodur; `project z` ile karışmaz.** Kurallar: [CLAUDE.md](CLAUDE.md).

## Klasör haritası

| Yol | İçerik |
|---|---|
| `*.py` (kök) | Çalışan kod. `live_tracker.py` + `tracker_v2.py` takip; `shadow_research.py` + `research_report.py` araştırma katmanı; `hypothesis_candidates.py` + `hypothesis_lab.py` + `trade_plan.py` aday değerlendirme; `research_updates.py` artımlı gelen kutusu; `research_ledger.py` tur defteri |
| `*.bat` (kök) | Tek tık girişler: `takip_TEST_20.bat`, `SONUCLARI_HESAPLA.bat`, `YENI_LOGLARI_HAZIRLA.bat` |
| `BELGELER/` | Referans belgeler: alan sözlüğü (`LOGGER_V2_ALANLAR.md`), araştırma kılavuzu (`SHADOW_ARASTIRMA_KILAVUZU.md`), Pine kaynakları (`REALF.txt`, `AVCITDIALT.txt`) |
| `GÜNLÜK/` | Çalışma günlüğü — ne yapıldı, ne doğrulandı. `00_INDEKS.md` otomatik üretilir |
| `ARASTIRMA/` | Tarihli araştırma raporları · `DEFTER/` tur defteri (hipotez durumu, eksikler, kullanım kılavuzu) · `YENI_VERI_TAKIBI/` artımlı gelen kutusu durumu |
| `HIPOTEZLER/` | Hipotez kataloğu (kullanıcı metni) |
| `TALİMALATLAR/` | Kullanıcı talimat arşivi |
| `logs/` | `run_<id>/` başına ham kayıt: `console_*.txt`, `snapshots_*.jsonl`, `outcomes.jsonl`, `run_meta.json` ve üretilen `research_shadow_v1/` + `hypothesis_lab_v21/` klasörleri |
| `_yedek_20260917_v2oncesi/` | Logger v2 öncesi yedek; dokunulmaz |

## Bir tur nasıl işler

```
takip_TEST_20.bat            → logs/run_<id>/ altına kayıt
SONUCLARI_HESAPLA.bat        → eksik sonuçları tamamlar (ağ ister)
YENI_LOGLARI_HAZIRLA.bat     → yalnız yeni satırları ayırır + defteri günceller
research_report.py <run>     → research_shadow_v1/ (ağ ister: geçmiş mumlar)
hypothesis_lab.py <run>      → hypothesis_lab_v21/ (aday tabloları, karakter, plan)
research_ledger.py           → ARASTIRMA/DEFTER/ turu
```

## Nereye bakmalı

- **Hipotezler ne durumda?** `ARASTIRMA/DEFTER/HIPOTEZ_DEFTERI.md`
- **Nasıl kullanılır, başarı/risk ne?** `ARASTIRMA/DEFTER/KULLANIM_KILAVUZU.md` (her turda yeniden üretilir)
- **Neler eksik?** `ARASTIRMA/DEFTER/EKSIKLER.md`
- **Giriş/çıkış planı ve coin sınıfları?** `logs/run_<id>/hypothesis_lab_v21/PLAN.md`
- **İşlem karakteri (tepe/geri verme zamanları)?** `logs/run_<id>/hypothesis_lab_v21/KARAKTER.md`
- **Alan tanımları?** `BELGELER/LOGGER_V2_ALANLAR.md`

## Kayıt boyutu

Saatlik `snapshots_*.csv` varsayılan olarak **yazılmaz**: JSONL asıl kaynaktır, CSV onun skaler alt
kümesidir. Gerekirse birebir üretilir:

```bash
python snapshots_csv_uret.py logs/run_20260918_112149
```
