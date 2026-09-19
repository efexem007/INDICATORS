# Tur 2 incelemesi — tamamlanan sonuçlar ne değiştirdi (2026-09-18)

Kapsam: yalnız `run_20260918_112149`. Bu turda yeni olay toplanmadı; **327 eksik sonuç tamamlandı** (6.100/6.100, eksik mum 0), rapor ve lab yeniden üretildi, defter tur 2'yi açtı. Eski runlar taranmadı. Aşağıdaki hiçbir satır işlem kuralı değildir.

## BULGU 1 — Eksik sonuçlar rastgele değildi, holdout'u bozuyordu

Eksik 327 kayıt çalışmanın **son ~66 dakikasında** toplanmıştı; yani tam da holdout bölümünde. Tamamlanınca iki hipotezin holdout işareti döndü:

| Varyant | holdout n | excess20 HO | excess60 HO |
|---|---|---|---|
| H5_BASE | 5 → 6 | -0.235 → **-0.057** | -0.442 → **+0.230** |
| H5_HTF_ALIGN | 1 → 2 | -0.235 → **+0.214** | -0.490 → **+0.414** |
| H6_DEEP_RESET | 3 → 4 | +0.809 → **+0.124** | +1.401 (aynı) |
| H3_BASE | 3 → 4 | +0.138 → **+0.037** | +0.351 (aynı) |
| H3_RETEST | 3 → 7 | +0.217 → **+0.185** | +0.275 (aynı) |

**Sonuç:** önceki turun "H5 uzun ufukta sert negatif (60m -0.442)" cümlesi sansürlü örneklemin ürünüydü. Eksik sonuç varken holdout yorumu yapılmamalı. Defter bunu artık tur farkı olarak gösteriyor; `research_updates.py` de ufku dolmuş eksikleri ayrı sayıp uyarıyor (bu turda 327 → 0, eksik E-0006 kapandı).

## BULGU 2 — Ham olay sayısı kanıtı abartıyor (zaman kümelenmesi)

H1/H2/H3 taban olaylarının **%76'sı**, 3+ olay içeren 10 dakikalık kovalarda; en kalabalık kovada 12 olay var (piyasa hepsini birlikte hareket ettiriyor).

| Varyant | olay | ayrı 10 dk kovası | etkin/ham |
|---|---:|---:|---:|
| H1_BASE | 39 | 17 | 0.44 |
| H1_FLOW_CONFIRM | 33 | 14 | 0.42 |
| H2_BASE | 26 | 15 | 0.58 |
| H3_BASE | 24 | 14 | 0.58 |

**Sonuç:** "30 olay" eşiği iyimser; 30 ham olay ≈ 13–17 bağımsız gözlem. Eşiği düşürmek değil, sayımı **zaman kümesi** bazına çevirmek gerekiyor (eksik E-0010).

## BULGU 3 — Kanıt birikme hızı bazı adaylar için ölçülemez düzeyde

5 saatlik çalışma başına olay hızından, 30 **holdout** olayına ulaşmak için gereken gün sayısı:

| Aday | olay/saat | 30 holdout için gün (5 sa/gün) |
|---|---:|---:|
| H1_BASE | 7.8 | ~2.5 |
| H1_FLOW_CONFIRM | 6.6 | ~3.0 |
| H3_RETEST | 5.4 | ~3.7 |
| H2_BASE | 5.2 | ~3.8 |
| H5_FRESH_BREAK | 2.4 | ~8.3 |
| H1_SLOW_SETUP | 1.2 | ~16.6 |
| H2_SLOW_SETUP | 0.8 | ~24.9 |

**Sonuç:** H1/H2/H3 tabanları birkaç günde karar verilebilir; `SLOW_SETUP` aday ailesi bu tempoda **haftalar** ister. Bunları "az sonra karar veririz" diye beklemek yerine ya daha uzun toplama ya da daha geniş evren gerekir.

## BULGU 4 — Ufuk yanlış seçilmiş: tepe 20 dakikadan sonra geliyor

Tam 60 dakika gözlenen tetiklerde:

| H | n | tepe gecikmesi (medyan) | ilk 10 dk'da tepe | MFE medyan | geri verme medyan |
|---|---:|---:|---:|---:|---:|
| H1 | 31 | 35 dk | %29 | %0.71 | %0.49 |
| H2 | 19 | 41 dk | %11 | %0.74 | %0.41 |
| H3 | 21 | 41 dk | %19 | **%1.02** | **%0.15** |
| H5 (short) | 17 | **15 dk** | %47 | %0.31 | **%0.88** |

**Sonuç:**
- Long tarafta karar ufku 20 dakika olduğu sürece hareketin yarısı ölçüm dışında kalıyor; H3'ün 60m'de görünen kenarı bunun doğal sonucu.
- H3 en yüksek MFE'yi en düşük geri vermeyle üretiyor — "tut" davranışına en uygun aday.
- H5 kazandığından fazlasını geri veriyor (%0.31 MFE'ye karşı %0.88 geri verme) ve tepesini 15 dakikada yapıyor. H5'i 20/60 dakikada ölçmek hipotezi değil, ufku test ediyor (eksik E-0012).
- FLOW_STRUCTURE çıkışının neden zarar verdiği de buradan okunuyor: ilk karşıt akışta çıkmak, medyan 35–41 dakikadaki tepeden çok önce kesiyor.

## BULGU 5 — Kaçırılan hareketler filtreyle değil, yeni kurulumla yakalanır

39 kaçırılan hareketin (20m > %1 veya 60m > %2) engel dağılımı:

| Engel | adet |
|---|---:|
| Üç hipotezde de **setup** oluşmadı | 28 |
| Kalite vetosu (`partial_flow`) | 4 |
| Kısmen trigger/armed aşamasında | 7 |

**Sonuç:** kaçırılanların %72'sinde kurulum hiç oluşmuyor; mevcut H1–H3'e onay/filtre eklemek bu hareketleri geri getirmez — bunlar **yeni bir setup ailesi** ister (eksik E-0011). Ayrı olarak 4 hareket kalite vetosuyla elendi; en büyüğü AKE +%6,6 (20m). Veto veri güvenliği için doğru ama maliyeti bugüne kadar ölçülmemişti (eksik E-0009).

## Bu turda deftere yansıyanlar

- Tur 2 kaydedildi (aynı run, yeni replay hash — 327 sonuç tamamlandığı için). Δ olay her yerde 0, Δ holdout n H3_RETEST'te +4, H2_BASE'de +2, birkaç adayda +1.
- Kapanan eksik: **E-0006** (tamamlanmamış sonuç 327 → 0).
- Açılan eksik: **E-0009** kalite vetosunun maliyeti · **E-0010** zaman kümelenmesi · **E-0011** setup ailesi boşluğu · **E-0012** H5'in ufku.
- Durum değişikliği yok: hâlâ 0 ADAY, 2 IZLENIYOR, 12 YETERSIZ, 1 VERI_YOK, 2 TARAYICI.

## Değiştirilmeyenler

Üretim indikatörleri, alarm formülleri, H1–H5 eşikleri, aday menüsü (v2.2), çıkış kuralları ve olay tanımları bu turda **değişmedi**. Yukarıdaki bulgular ölçüm sonucudur; uygulanacak değişiklikler kullanıcı kararına bırakıldı.
