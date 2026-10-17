# ATK işlem yaşam döngüsü → LAYA: sentetik veri ve düzeltme planı

17 Ekim 2026. Çalışan kod, dataset ve sonuçlar hazır; kritik model hatası henüz çözülmedi.

## Tamamlanan çalışma

Resmî ATK CLI 1.4.8 için `list-tools --json` gerçek olarak çalıştırıldı. Komut keşfi dışında hiçbir authenticated ATK komutu kullanılmadı. Public kaynak: `data/atk_spot/20261017T102105Z`, kaynak hashleri doğrulandı. Emir fiyat/miktar fixture'ları gerçek BTC-USDT tickSz/lotSz/minSz ve public orderbook ölçeğine dayanıyor; demo hesap desteği, bakiye ve özel emir çıktıları gerçek hesapta doğrulanmış DEĞİL.

Son dataset: `data/trade_lifecycle/20261017T103022Z`.

- Normal spot: market, limit, post_only, FOK, IOC.
- Algo fixture'ları: conditional, OCO, trailing, trigger, chase, iceberg, TWAP.
- İki yön: buy / sell.
- 15 operasyon senaryo ailesi, iki miktar/durum varyantı.
- 720 benzersiz satır: CONTINUE 240 / REVIEW 240 / HALT 240.
- Ana sette yalnızca mevcut politikanın desteklediği BTC-USDT var; sembol adından HALT öğrenme kestirmesi kaldırıldı.
- Tüm expected etiketleri modelden bağımsız, sürümlü aday oracle'dan geliyor. LAYA çıktısı hedef etikete dönüşmüyor.
- Tamamı SYNTHETIC_DERIVED ve PENDING_HUMAN_REVIEW. Hiçbiri gerçek özel hesap/trade kaydı veya insan onaylı gold değil.
- `fixtures.json`: güvenilir olduğu varsayılan simülasyon bağlamı, request fixture, sıralı event izi ve minimal response subsetleri.
- `metadata.csv`: kaynak/family/grup/etiket gerekçesi. `human_review.csv`: boş insan inceleme kuyruğu.
- `coverage.json`: kapsanan ve kapsanmayan alanlar; “bütün işlemler kapsandı” iddiası yok.

## İşlem aşamaları ve tutarlılık

Preflight → submit/ack → sorgu/reconciliation → güvenli terminal izleri üretildi. Submit timeout'unda belirsiz emir HALT; kör tekrar yasak. Cancel/amend ACK tek başına terminal onay değildir: REVIEW. İptal/değişiklik izleri uygun emir türleriyle sınırlandı; market/FOK/IOC için hayalî bekleyen amendable emir üretilmedi. FOK'a kısmi dolum verilmedi. Algo parent `effective` durumu dolmuş child emir gibi gösterilmedi; güvenli terminal fixture'ı iptal ile sınırlandı.

Response subsetleri ATK araç alanlarını yansıtan steril mock'lardır; tam API round-trip uyumluluğu veya exchange'in gerçekten bu cevabı döndürdüğü iddia edilmez. Gerçek ordId, kullanıcı kimliği, fee, PnL, fill veya credential uydurulmadı. Kaynak public piyasa live snapshot'ıdır; örneklerin OKX_DEMO bağlamı ise yalnızca offline simülasyondur, gerçek demo deneyi değildir.

Eksikler: batch içinde mixed failures, bağlı TP/SL yarışları, STP, quote-sized market buy, fee varyasyonları, detaylı precision/minimum sınır matrisi, gerçek demo davranışı ve türevler. Para/miktar/zaman boyutları sürekli olduğundan tüm kombinasyonlar sonlu bir veri çekimiyle tüketilemez.

## Gerçek LAYA shadow sonucu

Mevcut yerel base checkpoint CUDA ile yüklendi. Checkpoint sürüm/hash:
`f38a07fa01dbf242cc120da859b2cffa18eb8631b28db88d2e54e14876a15c3e`.

| Aday oracle etiketi | Model CONTINUE | Model REVIEW | Model HALT |
|---|---:|---:|---:|
| CONTINUE | 198 | 42 | 0 |
| REVIEW | 240 | 0 | 0 |
| HALT | 240 | 0 | 0 |

720/720 giriş işlendi. Kırpılan giriş: 0. Median inference yaklaşık 37.15 ms. HALT→CONTINUE: 240/240. Bu, insan onaysız adaylar üzerindeki tanısal taramadır; bağımsız test başarımı değildir. Model yeni eğitim görmedi. Mevcut base model, bu operasyonel kararı güvenilir vermiyor; sınıf dengeleme veya yalnızca BTC kullanmak tek başına bunu düzeltmedi. Confidence kalibre değil ve güvenlik kapısı olarak kullanılmıyor. Seçili model değiştirilmedi.

## Yapısal doğrulama

Resmî LAYA dry-run: 720 satır / 720 valid item / sıfır skipped. Varsayılan dört epoch/effective batch64 için dry-run bütçesi 648 optimizer-train + 72 internal calibration, 44 optimizer update. Bu bir gerçek eğitim çalışması değildir; bağımsız kalibrasyon güvenilirliği de kanıtlamaz. Aynı ailelerin internal calibration/train'e dağılması kaynak bağımsızlığı sağlamaz.

15 lifecycle testi + önceki 7 spot analitik testi + 7 dataset testi: 29 PASS. Kontroller: oracle önceliği, submit/read timeout ayrımı, gerekli context yokluğu, ACK/final ayrımı, gerçek minSz/lotSz/tickSz ızgarasında miktar ve fiyatlar, FOK/market/algoda imkânsız state üretmeme, etiketi input'a koymama. Bu testler tüm exchange davranışlarını doğrulamaz. Boş insan incelemesiyle export denemesi beklendiği gibi engellendi; eski dataset ve yeni manifest hashleri yeniden doğrulandı.

## Bu sayede kritik bulgu çözülebilir mi?

Evet, bu tür karar sınırlarını öğreten, bağımsız etiketli veri faydalı olabilir; ama çözüm garantisi yok. 720 satır yalnızca 15 aile ve TEK public capture'dan türedi. Çoğaltılmış varyantlar 720 bağımsız kanıt değildir. Önceki başarısız head-only deneyi küçük veride öğrenmedi; daha fazla benzer JSON üretmek tek başına modelin öğrenmesini sağlamaz.

1. Gerçek insan, her aile ve varyantın oracle etiketini/bağlamını gözden geçirsin. Özellikle lifecycle'e eklenen oracle kuralları Person 1 onayı bekleyen PROPOSED kurallardır; backend politikası değiştirilmedi.
2. Public kaynak sadece piyasa ölçeğini doğrular. Yetki, approval, journal ve reconciliation için gerçek backend/ATK demo test logları ancak ekip tarafından anonimleştirilip açıkça sağlanırsa eklenmeli. Public endpoint'ten private order output çekilemez. Bu görev demo/live emir yetkisi vermiyor.
3. Aynı source capture, parent case ve paraphrase'leri tek split'te tut. Yeni veri UNSPLIT; eski train/val/test/challenge değişmedi. Aynı capture'ı rastgele 70/15/15 bölmek bağımsız test yaratmaz. Başka capture/family ve özellikle yeni gerçek hata izleri gerekir.
4. Kritik HALT→CONTINUE vakaları için eğitimden bağımsız challenge tasarla; dev/VAL ile seçilen modelin nihai testini yalnızca bir kez çalıştır. Bu 720 satırın tamamı artık tanısal olarak görüldü; dokunulmamış final test diye sunulamaz.
5. Resmî LAYA rehberindeki **label-encoding positive control** ile pipeline'ın öğrenebildiğini sınayın: küçük yapay bir debug kopyasında cevap etiketi input'a açıkça yazılır. Bu kopya kasıtlı leakage içerir, yalnızca hata ayıklama içindir; gerçek dataset/başarım raporuna ASLA karışmaz. Kontrol de öğrenmiyorsa veri büyütmek yerine optimizer/head/checkpoint/encoding hattını inceleyin.
6. Kontrol öğrenirse gerçek girdide kompakt JSON / doğal dil A-B testi, yeterli update bütçesi, birden fazla seed ve küçük head-only deneyi yapın. Full encoder yalnızca smoke stabil ve yerel RTX4060'ın ölçülen ~8GiB VRAM'ine sığıyorsa, bir OOM'da durarak ayrı deney olabilir. Varsayılan birkaç düzine update'i başarılı fine-tune varsaymayın.
7. Seçim metrikleri: HALT recall, HALT→CONTINUE oranı, REVIEW→CONTINUE, confusion matrix, macro-F1, CONTINUE'nin gereksiz bloklanması, ECE/Brier/abstention ve gecikme. Başarı yalnızca toplam accuracy değildir. Kalibrasyon ve final test kaynak bağımsız olmalı.
8. Başarılı fine-tune bile yetki/credential/journal/duplicate veto'sunu kaldıramaz. CONTINUE yalnızca izlemeye devam demektir; trade approval değildir. Üretim onayı hâlen FALSE.

## Kullanım ve inceleme kapısı

Repo kökünde mevcut CUDA Python ortamıyla:

```powershell
python scripts/ml/trade_lifecycle_data.py build
python scripts/ml/trade_lifecycle_data.py scan --directory data/trade_lifecycle/<capture-id>
python scripts/ml/lifecycle_review_gate.py prepare data/trade_lifecycle/<capture-id>
# human_review.csv insan tarafından doldurulduktan sonra:
python scripts/ml/lifecycle_review_gate.py export data/trade_lifecycle/<capture-id>
```

Export kapısı tüm 720 satır için insan etiketi, onay, reviewer role, timezone'lu tarih ve gerekçe ister; boş inceleme ile export engellenir. Bu bir kimlik doğrulama sistemi değildir: gerçek inceleme sorumluluğu ekiptedir. Export edilmiş veri de bağımsız split/VAL yokken otomatik eğitim yetkisi değildir. Mevcut doğrudan LAYA CLI bu kapıyı teknik olarak bypass edebilir; prosedürün atlanmaması gerekir.

## Kaynaklar ve geri teslim

- ATK spot: https://github.com/okx/agent-trade-kit/blob/github-main/docs/modules/spot.md
- LAYA resmî fine-tune, calibration ve positive-control rehberi: https://github.com/NandhaKishorM/laya/blob/main/docs/finetune.md
- Kurulu sürümün gerçek komut listesi: capture içindeki atk_capabilities.json (1.4.8).

No orders, private endpoint, auth/credential read, yeni paket, system-wide değişiklik veya PATH değişikliği. Backend/frontend ve owner hesabı değişmedi. Code/model push yapılmadı.

Cleanup: backup'tan sonra yalnızca yeni scripts/ml/trade_lifecycle_data.py, test_trade_lifecycle.py, lifecycle_review_gate.py; data/trade_lifecycle altındaki bu görev capture'ları; bu rapor ve outputs/ATK-LAYA-LIFECYCLE-REPORT.md kopyası overlap kontrolüyle kaldırılabilir. İlk 20261017T102922Z capture'ı erken generator sürümüne ait; son 20261017T103022Z tercih edilmeli. Önceki dataset, checkpoint ve teammate dosyalarını kaldırma. Şu anda hiçbir cleanup çalıştırılmadı.
