# Düzenleme durumu — analiz öncesi

Amaç: indikatörlerin birlikte davranışı üzerinden setup, giriş, takip, geçersizleşme ve çıkış yöntemlerini inceleyebilecek güvenilir veri hazırlamak. Bu aşama strateji sonucu veya kârlılık iddiası üretmez.

| Kontrol maddesi | Durum |
|---|---|
| Canlı outcome eksik ara mumda kayboluyor | Düzeltildi; tekrar deneme ve çevrimdışı bekleyen sayacı eklendi |
| Tüm runlarda sonuç onarımı / günlük tablo | Komut eklendi; JSONL asıl kaynak; eksik kaynak koruması var |
| DNS / bağlantı kesintisi | Süren/iyileşen kesinti takibi, tekrar deneme aralığı ve veri kalite vetosu eklendi; harici bağlantı sorunu kendiliğinden çözülmüş sayılmaz |
| H1–H7 raw/setup/armed/trigger ve olay kimliği | Ayrı shadow katmanda eklendi; kurallar kılavuzda açık |
| H7 24h/3d/7d/local-base/ATR extension | Eklendi; yetersiz geçmiş null, saatlik zaman yuvarlaması açık |
| H3 breakout→retest→reacceleration | Zaman/depth/survival alanları eklendi; snapshot çözünürlüğünde araştırma |
| H4 follow-through / decay | 1–60m takip ve 5m decay eklendi |
| H5 setup/armed ayrımı | Eklendi; eksik U geçerli sayılmaz; bounce öncesi trigger engellendi |
| H6→H1/H2 dönüşümü | Kimlik/gecikme/outcome bağlantısı; concurrent/later/censored ayrımı var |
| İndikatör uyum sırası ve süresi | Alignment pattern/değişim kaydı ve ayrı export eklendi |
| Giriş sonrası hareket ve çıkış adayları | Gözlenen MFE/MAE/giveback, ilk karşıt yapı/akış/gap/seviye olayı eklendi |
| FP/FN / kaçırılan hareket | Tekrarlanabilir olay exportları ve H bazında eksik koşullar var; yorum sonraki analizde |
| Segment / maliyet / benchmark | Ayrı çıktılar var; benchmark izlenen evren sepeti ve BTC/ETH, tam piyasa endeksi değil |
| Git sürümü | Commit + dirty + üç kaynak dosyanın fingerprint'i; eski commit uydurulmaz |
| +2h / +4h | Opsiyonel; bu sürümde uygulanmadı |
| İstatistiksel yeterlilik / farklı günler | Kodla oluşturulamaz; sonraki veri incelemesinde değerlendirilecek |

Önceki turda 6 run için 11.754 outcome tamamlanmıştı. Duraklama sonrasında kaynak loglarda harici değişiklikler, yeni run ve eksilen snapshot parçaları görüldü. Bu eski sayı güncel klasör bütünlüğü kanıtı değildir. Özellikle run_20260918_015707 içinde 02–07 saatlerinin snapshot parçaları son kontrolde görünmüyordu. Bu düzenleme turunda kaynak loglara dokunulmadı. Veri incelemesinden önce mevcut kaynak seti ayrıca doğrulanmalıdır; yeni koruma eksik seti tam sanarak rapor üretmez.

Çalışan eski takip süreci dosya değişikliklerini otomatik yüklemez. Yeni alanlar takip programının sonraki başlatılmasında devreye girer. Eski veri ayrı replay ile işlenebilir; yeni alanlar eski ham loglara yazılmaz.

Alanlar ve deney tanımları: `BELGELER/SHADOW_ARASTIRMA_KILAVUZU.md`. Mevcut üretim indikatörleri ve alarm formülleri korunmuştur. Sonraki adım veri bütünlüğünün doğrulanması, ardından gerçek olaylarla hipotez ve giriş/çıkış incelemesidir.
