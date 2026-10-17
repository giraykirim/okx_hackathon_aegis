# Person 2 → Person 1 Koordinasyon Yanıtı: `aegis-operational-v2-human-preserved` ve 32 Ek Vaka

Tarih: 17 Ekim 2026  
İncelenen Person 1 dalı: `codex/person1-laya-coordination` (`4ff56b7fcfb031f988cd61dd63af89b21953f12a`, `da8d0c2825c816c12d1b314bb1e438f463c19635`)

## 1. Sürümlü ML Etiket Politikası (`ml/label_policy_v2.py`)

`ml/label_policy.py` (`aegis-operational-v1`) mevcut kanıt paketlerinin SHA-256 bütünlüğünü bozmamak için byte-özdeş bırakıldı. Person 1'in 5 grup / 20 vaka kararını uygulayan yeni sürümlü politika `ml/label_policy_v2.py` (`VERSION = 'aegis-operational-v2-human-preserved'`) olarak eklendi ve `scripts/ml/test_label_policy_v2.py` ile doğrulandı:

| Grup | Bağlam Özeti | İnsan Kararı | `v1` | `v2` | Durum |
|---|---|---|---|---|---|
| `6035c658446bc766` (4) | `age=40`, `approval=False`, `intent=True` | `REVIEW` | `HALT` | `REVIEW` | Çözüldü |
| `b507903e784e923b` (4) | `age=-2.1`, `intent=True` | `REVIEW` | `HALT` | `REVIEW` | Çözüldü |
| `bd4f3224298b7c68` (4) | `age=15.1`, `intent=True` | `REVIEW` | `HALT` | `REVIEW` | Çözüldü |
| `c328abb0010e5796` (4) | `age=40`, `approval=True`, `intent=True` | `REVIEW` | `HALT` | `REVIEW` | Çözüldü |
| `cb09120331fb2593` (4) | `intent=False`, `permission_revoked=None` | `CONTINUE` | `CONTINUE` | `CONTINUE` | Korundu |

- Sonlu sayısal `feed_age_seconds > 15` veya `< -2` durumu (başka bir `HALT` nedeni yoksa) hem `intent_requested=True` hem `intent_requested=False` için `REVIEW` (`stale_or_future_feed`) döner; böylece emir niyetinin varlığı etiketi daha hafif yapmaz.
- Sayısal olmayan / sonlu olmayan (`NaN`, `Inf`, `bool`, `str`) zaman damgaları ve tüm bütünlük/yetki/miktar ihlalleri `HALT` kalır.
- Backend Python deterministik vetoları (`aegis.policy.check`) nihai otoritedir; model etiketi hiçbir zaman emir izni değildir.

## 2. Dondurulmuş 161 İnsan Kararında Tespit Edilen 32 Ek Vaka

`data/reviewed_learning/expanded-v2-20261017T120738Z/human_confirmed_unsplit_v2-r169/candidates.jsonl` içindeki 161 satırın tamamı `v1` ile karşılaştırıldığında, önceki 20 vakalık denetimde listelenmeyen **32 ek uyuşmazlık** bulundu:

- **Örüntü:** `intent_requested=True`, diğer tüm alanlar sağlıklı, ancak 8 güvenlik bayrağından tam biri `None` (`api_timeout`, `agents_disagree`, `unknown_order`, `duplicate_intent`, `permission_revoked`, `injection_detected`, `deployment_integrity_failure`, `excess_exposure` × 4 miktar = 32 satır).
- **Neden önceki denetimde görünmedi:** Önceki denetim yalnızca `human_label != suggested_label` farklarını listeledi. `suggested_label` zaten bilinmeyen (`None`) alanda `REVIEW` döndürdüğü için insan kararıyla (`REVIEW`) uyuştu; fakat `aegis-operational-v1` `facts.get(field)` kontrolünde `None` değerini `False` gibi ele alıp `CONTINUE` döndürüyordu (`16 stale/future + 32 null-bayrak = 48` toplam `v1` farkı).
- **`v2` çözümü:** `intent_requested=True` iken bu 8 güvenlik bayrağından herhangi biri `None` ise `v2` `REVIEW` (`safety_flag_unknown_with_intent`) döner. `intent_requested=False` iken tek başına `None` güvenlik bayrağı `CONTINUE` (yalnızca izleme) kalır (`cb09120331fb2593` ile tam uyumlu).
- **Sonuç:** `ml/label_policy_v2.py`, dondurulmuş `v2-r169` paketindeki **161 / 161** insan kararıyla birebir eşleşmektedir. Tüm offline ML testleri (**249 / 249**) ve `ruff` kontrolleri geçti.

## 3. `build_shadow_context` (`aegis-trusted-context-shadow-v1`) Mutabakat Notu

- Person 1'in `backend/aegis/laya_context.py` içindeki proposal-sonrası 16 alanlı salt-okunur shadow bağlam kurucusu (`state.operational`), `None` koruma kuralı (`unknown_values_are_not_false`), `PENDING` ≠ `UNKNOWN` ayrımı ve kimlik/metin/bakiye sızdırmama sınırları Person 2 (`ml`) şemasıyla uyumludur.
- **Taşıma katmanı notu:** Canlı LAN servisi (`scripts/ml/serve_selected.py`) şu an `unknown` listesi boş değilse (`feed_age_seconds` veya 10 boolean bayraktan biri `None` ise) güvenli tarafta kalarak `REVIEW, abstained=True, confidence=0.0` döner. `v2` etiket politikasında `intent_requested=False, permission_revoked=None` izleme etiketi `CONTINUE` olsa da, canlı HTTP zarfında `None` alanlı isteklerde fail-closed abstention davranışı koordineli bir karara kadar değiştirilmemiştir.
