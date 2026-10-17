# AEGIS öğrenme hattı kontrolü — 17 Ekim 2026

## Sonuç: positive control PASS; DATA/INTEGRATION BLOCKED

Planın backend gerektirmeyen bölümü gerçek GPU eğitimiyle tamamlandı. Gerçek operasyon
verisiyle fine-tune ve backend entegrasyonu yapılmadı: yeni backend sürümü/Person 1 bağlam
onayı, bağımsız 120 iz ve gerçek insan incelemesi henüz sağlanmadı.

## Gerçek çalıştırma

- Run: ml/debug_learning/20261017T104341Z.
- Bilerek cevabı içeren, tamamen ayrı debug veri: 48 train + 12 diagnostic validation.
- Resmî, kurulu LAYA 0.4.8 CLI; torch2.14.1+cu130, CUDA13.0; RTX4060 Laptop.
- Head-only, soft-CE, seed17, 8 epoch, micro-batch1, accumulation1. İkinci 16-epoch denemesi gerekmedi.
- Resmî internal split: 44 optimizer-train + 4 calibration; 12 diagnostic-val ayrı.
- 352 planlanan update; optimizer hook ile 347 gerçek step gözlendi. AMP yolu ve scheduler
  ilk-adım uyarısı konsol kaydında korundu; fark gizlenmedi. Paket kodu değiştirilmedi.
- Eğitim/save/reload/diagnostic inference süresi yaklaşık 46,54 saniye.
- Peak torch allocated VRAM: 2322,55 MiB. Bu ölçüm tüm cihaz kullanımını temsil etmez.
- Mean epoch loss: 1.2634, .9578, .5742, .0704, .3138, .00496, .02328, .00146.
- Encoder'ın 170 parametre tensörü donuk ve hash bazında değişmemiş. Head'de 35 tensörden
  31'i değişmiş; örneklenen gradyanlar sonlu ve sıfırdan farklı.
- Resmî before accuracy: 4/12; kaydet/yükle sonrası: 12/12. Kırpılan giriş: 0.

| Debug hedefi | CONTINUE | REVIEW | HALT |
|---|---:|---:|---:|
| CONTINUE | 4 | 0 | 0 |
| REVIEW | 0 | 4 | 0 |
| HALT | 0 | 0 | 4 |

Bu, etiket girdiye açıkça yazıldığı için kasıtlı kolay bir kontroldür. Operasyonel başarı,
genelleme, bağımsız test veya gerçek HALT hatasının çözüldüğü iddia edilmez. Debug checkpoint
asla gerçek işlem modelinin yerine geçmez. Confidence kalibre değildir; 4 calibration item
uyarısı korunmuştur. ECE/accuracy'nin debug sonuçları üretim kalite ölçüsü değildir.

## Tanı

Eğitim, label encoding, head güncellemesi ve reload yolu en azından bu kolay görevi öğreniyor.
Bu nedenle “eğitim hattı hiç öğrenemiyor” açıklaması bu çalıştırma için desteklenmiyor.
Gerçek girdinin temsili, etiket kalitesi, update bütçesi ve encoder/head kapasitesi hâlâ
araştırılması gereken etkenler. Hangisinin tek kök neden olduğunu bu deney belirlemiyor.
Önceki gerçek görev taramasındaki HALT→CONTINUE hatası çözülmüş sayılmıyor.

## Uygulanan korumalar ve doğrulama

learning_control.py: ayrı karantina veri/checkpoint dizinleri, önce/sonra immutable hash
kontrolü, sınırlı retry, timeout, gerçek optimizer/gradient/weight audit ve reload ölçümü.

reviewed_learning.py: allowlist context serializer, null/missing bilgiyi sağlıklı varsaymama,
blind review export, backend ACK, trace hash, grup leakage ve 60/30/30 denetimleri; iki-seed
bounded eğitim, VAL seçimi ve final test için atomic one-shot marker. Person 1 onayı olmadan
HTTP sözleşmesi veya backend dosyası değiştirilmedi. Bu kod backend'e deploy edilmiş değildir.

17 yeni gate/metric unit testi + 15 lifecycle + 7 dataset + 7 spot analitik testi: 46 PASS.
Unit testlerdeki onay/trace örnekleri geçici, açıkça UNIT_TEST_ONLY fixture'lardır; gerçek
review/veri diye kaydedilmezler. Gerçek iki-seed ve final-test yolları yalnızca gerekli
veri/onaylar geldiğinde çalıştırılabilir; mevcut testler gerçek backend e2e kanıtı değildir.

Mevcut train/val/test/challenge, 720 aday paketi ve seçili checkpoint için görev başı snapshot
hashleri korundu. Yeni debug/checkpoint hashleri epochs-8.json içinde. Modelin head-update
auditi process-local gözlem hook'larıyla yapıldı; kurulu LAYA dosyaları düzenlenmedi.

## Backend durumu ve gereken iki adım

Read-only remote HEAD kontrolünde main=366005ac24a7b5148a7096a58165f8050e32ec05 görüldü;
local HEAD=674a0d2c32acf55c30764dd92b15ada43ac65059. Bu önceden bilinen fark yeni backend
teslimi/onayı olarak kabul edilmedi. Fetch/pull/merge/checkout/push yapılmadı; kirli worktree korundu.

1. Person 1 yeni backend commit'ini ve güvenilir bağlam eşleşmesini paylaşmalı; network/order
   kapalı offline testlerden anonimleştirilmiş izler sağlamalı.
2. Gerçek reviewer yeni 120 örneği kör biçimde incelemeli. Eksik grup/sınıf varsa çoğaltmak
   yerine eksik raporlanacak. Detaylar REVIEWED_LEARNING_HANDOFF.md içinde.

## Tekrar üretim ve kaynak

Repo kökünde mevcut GPU Python ile `python scripts/ml/learning_control.py run` yeni,
ayrı bir debug run oluşturur; önceki checkpoint üzerine yazmaz. Resmî CLI argümanları,
önce/sonra metrikleri ve checkpoint hashleri epochs-8.json; konsol epochs-8.log içinde.

Resmî label-encoding kontrol rehberi:
https://github.com/NandhaKishorM/laya/blob/main/docs/finetune.md#diagnose-a-run-that-stays-at-chance

No real/demo order, credential read, yeni paket, system-wide/PATH/security değişikliği.
User-level yerel dosyalar/checkpointler dışında değişiklik yok. Owner hesabı etkilenmedi.
VS Code'da rapor, kod ve handoff açıldı.

Cleanup: backup ve overlap kontrolünden sonra yalnızca bu görevin data/debug_learning/run,
ml/debug_learning/run, models/debug_learning/run dizinleri; yeni üç script, iki rapor ve
outputs/AEGIS-LEARNING-CONTROL-REPORT.md kopyası kaldırılabilir. Yeni modeller .gitignore
ile dışlandı; önceki modelleri, ortamı veya teammate dosyalarını kaldırma. Cleanup çalıştırılmadı.
