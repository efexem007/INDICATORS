# 2026-09-18 — Tur defteri, karakter olcumu, plan ve indikator varyantlari

## SORUN

Inceleme her turda tum arsivi tariyordu, hipotez/eksik durumu turdan tura tasinmiyordu; karar ufku sabit 20 dk idi, kanit ham olayda sayiliyordu, giris/cikis plani ve coin ayrimi yoktu. Ayrica research_updates.collect() ciktiyi fonksiyon icinde yazdirdigi icin UTF-8 olmayan stdout'ta commit SONRASI patlayip 'basarisiz' yaziyordu.

## ÇÖZÜM

Artimli gelen kutusu + tur defteri (ARASTIRMA/DEFTER) eklendi; karar ufku olculen tepe zamanindan turer; kanit 10 dk kumesinde sayilir; isle karakteri ve her turda yeniden uretilen kullanim kilavuzu; giris/cikis plan izgarasi ve coin sinif ayrimi (trade_plan.py); menu v2.4 ile pullback varyantlari ve dort indikator maddesinin olculebilir karsiligi. Saatlik CSV kapatildi (JSONL asil kaynak), ayni kanit yeniden olculurse tur revize edilir.

## DOĞRULAMA

test_research 16/16, test_research_updates 18/18, test_research_ledger 29/29; tracker_v2 selftest TÜMÜ GEÇTİ (CSV açık/kapalı iki yol da ölçülüyor), live_tracker --selftest TÜMÜ GEÇTİ. Gercek veriyle 4 tur kaydedildi (run_20260918_112149, 6100 satir, 6100 sonuc). CSV geri uretimi 509/509 satirda birebir ayni. Ayrinti: ARASTIRMA/2026-09-18_DEFTER_VE_TUR_DONGUSU.md, _TUR2_INCELEME.md, _TUR3_KARAKTER_VE_INDIKATOR.md, _TUR4_PLAN_VE_COIN_SINIFI.md

## Değiştirilen dosyalar

| Dosya | Değişiklik |
|---|---|
| `research_ledger.py` | tur defteri, durum merdiveni, kullanim kilavuzu, tur revizyonu |
| `research_updates.py` | konsol ciktisi ayrildi, sqlite kapatiliyor |
| `hypothesis_candidates.py` | v2.4 menu, INDICATORS belirtec butunu, pullback takibi, dakika tazeligi |
| `hypothesis_lab.py` | karakter olcumu, kume sayimi, veto maliyeti, plan entegrasyonu |
| `trade_plan.py` | YENI - giris/cikis politikalari ve coin siniflari |
| `tracker_v2.py` | saatlik CSV kapatildi (WRITE_HOURLY_CSV) |
| `snapshots_csv_uret.py` | YENI - JSONL'den CSV geri uretimi |
| `gunluk_ekle.py + CLAUDE.md + README.md` | YENI - bu klasorun kayit ve duzen kurallari |
