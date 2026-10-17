# ATK + LAYA spot araştırması

Capture (UTC): 20261017T102105Z

Gerçek ATK: 15000 ham mum, 1000 public işlem, 10 spot çift, 45 ikili kombinasyon. QA: PASS.

## Likidite ve oynaklık

| Çift | Spread bps | 50 seviye bid / ask USDT | 1H std bps | Politika kapsamı |
|---|---:|---:|---:|---|
| BTC-USDT | 0.012 | 531,459 / 351,510 | 36.01 | BTC monitoring |
| ETH-USDT | 0.041 | 613,086 / 839,826 | 49.94 | OUT OF SCOPE / HALT |
| USDC-USDT | 0.100 | 7,559,747 / 4,239,481 | 0.57 | OUT OF SCOPE / HALT |
| ZEC-USDT | 0.762 | 198,882 / 122,904 | 113.04 | OUT OF SCOPE / HALT |
| XRP-USDT | 0.765 | 881,324 / 892,733 | 60.06 | OUT OF SCOPE / HALT |
| FIL-USDT | 0.883 | 159,645 / 77,261 | 141.48 | OUT OF SCOPE / HALT |
| SOL-USDT | 0.954 | 1,193,138 / 1,405,198 | 61.63 | OUT OF SCOPE / HALT |
| DOGE-USDT | 1.245 | 1,432,924 / 793,356 | 65.66 | OUT OF SCOPE / HALT |
| WLD-USDT | 3.865 | 345,265 / 251,306 | 128.98 | OUT OF SCOPE / HALT |
| NEAR-USDT | 3.885 | 454,008 / 413,314 | 152.11 | OUT OF SCOPE / HALT |

## Saatlik eşleştirilmiş kombinasyonlar

Aşağıda en düşük korelasyonlu 10 kombinasyon; 45 kombinasyonun tamamı analysis.json içinde.

| A / B | Korelasyon | Eşleşen saat | 50/50 log-getiri proxy std (bps/saat) |
|---|---:|---:|---:|
| USDC-USDT / DOGE-USDT | -0.1364 | 298 | 32.79 |
| ETH-USDT / USDC-USDT | -0.1354 | 298 | 24.93 |
| USDC-USDT / WLD-USDT | -0.1271 | 298 | 64.45 |
| USDC-USDT / FIL-USDT | -0.0844 | 298 | 70.72 |
| BTC-USDT / USDC-USDT | -0.0820 | 298 | 17.99 |
| USDC-USDT / NEAR-USDT | -0.0793 | 298 | 76.03 |
| USDC-USDT / XRP-USDT | -0.0788 | 298 | 30.01 |
| SOL-USDT / USDC-USDT | -0.0738 | 298 | 30.79 |
| USDC-USDT / ZEC-USDT | -0.0300 | 298 | 56.51 |
| NEAR-USDT / FIL-USDT | 0.4636 | 298 | 125.61 |

## LAYA entegrasyonu ve sınırlar

Yerel CUDA shadow inference: 110 senaryo. Politika/model uyuşmazlığı: 109; tehlikeli HALT → CONTINUE: 106.

Aday etiket sayıları: {'CONTINUE': 1, 'HALT': 106, 'REVIEW': 3}. Tamamı PENDING_HUMAN_REVIEW; gold etiket DEĞİL.

- Model seçimi: mevcut base checkpoint; sürüm/hash: f38a07fa01dbf242cc120da859b2cffa18eb8631b28db88d2e54e14876a15c3e.
- Deterministik veto ve modelin daha kısıtlayıcı kararı korunur. Hiçbiri işlem izni vermez.
- Model güveni kalibre değil; üretim onayı yok. Bu tarama doğruluk testi veya benchmark değildir.
- ETH/SOL ve diğer semboller mevcut BTC-only politikası dışında: otomatik trade kapsamına eklenmedi.
- Anlık orderbook/ticker ölçümleri eşzamanlı değil; snapshotlar artık güncel sayılmaz.
- 50 seviyelik derinlik sabit fiyat bandı değildir; çiftler arasında doğrudan karşılaştırmak yanıltabilir.
- Korelasyon kısa, seçilim yanlı bir penceredir; stablecoin çiftleri de bulunabilir. Düşük korelasyon alım tavsiyesi değildir.
- 50/50 log-getiri ortalaması sadece betimsel proxy: gerçek sepet, arbitraj, ücret/slippage veya kâr backtesti değildir.
- Tarihsel mumlar fiyat/gelecek getiri etiketi olarak kullanılmadı. Açık mumlar analiz dışında.
- Sentetik sorunlar gerçek incident diye sunulmaz. Her senaryo aynı capture grubunda tutulur.
- Yeni veri train/val/test/challenge ile birleştirilmedi. Örtüşen zaman pencereleri purge edilmeden split yapılmamalı.
- Backend/frontend değiştirilmedi. Bu, çalıştırılmış yerel ATK→LAYA araştırma hattıdır; backend servis entegrasyonu değildir.
- Emir, private endpoint, credential okuma veya yeni paket kurulumu yok.

## Tekrar çalıştırma

```powershell
# Mevcut CUDA Python ortamından:
python scripts/ml/spot_research.py collect
python scripts/ml/spot_research.py infer data/atk_spot/<capture-id>
```

## Kaynaklar

- https://github.com/okx/agent-tradekit
- https://www.okx.com/docs-v5/en/#order-book-trading-market-data
- https://github.com/NandhaKishorM/laya/blob/main/docs/finetune.md

Cleanup: önce backup, sonra yalnızca bu capture ve scripts/ml/spot_research.py, test_spot_research.py, atk_public_isolation.mjs eklerini overlap kontrolüyle kaldır. Mevcut checkpoint, backend ve owner dosyalarına dokunma. System-wide değişiklik: NONE.
