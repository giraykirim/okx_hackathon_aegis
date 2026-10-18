# AEGIS — OpenCode & EvrenLLM Geçiş ve Geliştirme Rehberi

Bu rehber, **OKX Hackathon AEGIS** projesini hiçbir veri veya konfigürasyon kaybı olmadan **OpenCode** ortamına taşıyıp **EvrenLLM** destekli modellerle geliştirmeye devam etmeniz için hazırlanmıştır.

---

## 1. Proje Konumu ve Dosya Bütünlüğü

Proje dosyaları bilgisayarınızda şu yerel dizinde eksiksiz olarak bulunmaktadır:

```
c:\Users\hackathon\Documents\Codex\2026-10-16\bu-bilgisayar-d-n-al-nm\okx_hackathon_aegis
```

### Durum Özeti (Sıfır Kayıp Garantisi):
- **Git Durumu:** Son değişiklikler (`1c7afc9` - case-insensitive live header, LAN dev operatör kilidi kaldırma, timeline periyodik polling) yerel git geçmişine commit edilmiştir.
- **ModernBERT-Large Eğitilmiş Model:** 881 satırlık (161 V2 Gold + 720 OKX ATK trade_lifecycle) model ağırlıkları `ml/lan_inference/v2-tuned-seed17-20261017/` dizininde mevcuttur (97.73% doğruluk, 0.9915 güven skoru).
- **Yerel Gizli Değişkenler:** `backend/.env` ve `frontend/.env.local` dosyaları yapılandırılmış haldedir.
- **EvrenLLM Entegrasyonu:** `backend/.env` dosyasına `~/.config/opencode/.evren-key` içindeki EvrenLLM API anahtarı eklenmiş, model `glm-5.3` olarak seçilmiştir.

---

## 2. OpenCode'da Projeyi Açma

Bilgisayarınızda OpenCode Masaüstü uygulaması kuruludur:
- **Uygulama Yolu:** `C:\Users\hackathon\AppData\Local\Programs\@opencodedesktop\OpenCode.exe`
- **Masaüstü Kısayolu:** Masaüstünüzdeki `OpenCode` kısayolu

### Adımlar:
1. **OpenCode**'u açın.
2. Menüden **File -> Open Folder** (Klasör Aç) seçeneğine tıklayın.
3. Proje dizinini seçin:
   `c:\Users\hackathon\Documents\Codex\2026-10-16\bu-bilgisayar-d-n-al-nm\okx_hackathon_aegis`
4. Projeniz tüm dosyaları, git geçmişi ve bağımlılıklarıyla birlikte OpenCode içinde hazır olacaktır.

---

## 3. OpenCode EvrenLLM Model Ayarları

OpenCode yapılandırma dosyanız (`C:\Users\hackathon\.config\opencode\opencode.jsonc`) EvrenLLM ile eşleştirilmiştir:

- **Sağlayıcı:** `evren` (`https://evren-llmapi.ssyz.org.tr/v1`)
- **API Anahtarı Dosyası:** `~/.config/opencode/.evren-key`
- **Kullanılabilir EvrenLLM Modelleri:**
  - `evren/glm-5.3` (Varsayılan model — 524k context, güçlü reasoning)
  - `evren/deepseek-v4.1-flash` (Küçük / hızlı model — 1M context, 65k output)
  - `evren/qwen3.8-flash-next`
  - `evren/gemma-4-31b`
  - `evren/auto`

OpenCode chat veya komut satırında model seçerken doğrudan `evren/glm-5.3` veya `evren/deepseek-v4.1-flash` kullanabilirsiniz.

---

## 4. Servisleri Başlatma Komutları

OpenCode terminalinde 3 ayrı sekmede veya arka planda aşağıdaki servisleri çalıştırabilirsiniz:

### Terminal 1: LAYA ML Çıkarım Servisi (Port 8771)
```powershell
$tools = "C:\Users\hackathon\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\HackathonTools"
$env:Path = "$tools\python\tools;$tools\bin;$env:Path"
cd backend
.venv\Scripts\python.exe ..\ml\serve_v2_tuned.py --port 8771
```
*Sağlık kontrolü:* `http://127.0.0.1:8771/health`

### Terminal 2: AEGIS FastAPI Backend (Port 8080)
> **Not:** Port 8000 makinede başka bir hackathon sürecine aittir, AEGIS backend **port 8080** üzerinde çalışır.
```powershell
$tools = "C:\Users\hackathon\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\HackathonTools"
$env:Path = "$tools\python\tools;$tools\bin;$env:Path"
cd backend
.venv\Scripts\python.exe -m uvicorn aegis.app:create_app --factory --host 127.0.0.1 --port 8080
```
*Sağlık kontrolü:* `http://127.0.0.1:8080/api/snapshot`

### Terminal 3: Next.js Frontend Paneli (Port 3000)
```powershell
$tools = "C:\Users\hackathon\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\HackathonTools"
$node = "$tools\node\node-v24.22.0-win-x64"
$env:Path = "$node;$tools\bin;$env:Path"
cd frontend
cmd.exe /c "npm run dev -- -p 3000"
```
*Arayüz:* `http://localhost:3000` veya yerel ağdaki cihazlardan `http://192.168.1.34:3000`

---

## 5. AEGIS Mimarisi ve TradeCourt Konseyi

AEGIS körü körüne işlem açan bir bot değil, **Yapay Zeka Destekli İşlem Öncesi Risk Güvenlik Duvarı**dır (Pre-Trade Risk Firewall).

Her 10 saniyelik döngüde 4 sandalyeli **TradeCourt Konseyi** toplanır:

1. **1. Sandalye: Regime Magistrate (LAYA)**
   - Model: `aegis-laya-v2-tuned-seed17-7612b93c13cc` (ModernBERT-large, port 8771)
   - Görev: Operasyonel bağlamı (volatilite, ATK sağlığı, anomali) sınıflandırır.
2. **2. Sandalye: Opportunity Advocate (EVREN LLM)**
   - Model: `glm-5.3` (EvrenLLM)
   - Görev: Piyasa verilerini (OKX TR canlı BTC-USDT ticker) ve 15m trend mumlarını analiz ederek işlem önerisi (`proposal`) üretir.
3. **3. Sandalye: Risk Prosecutor (EVREN LLM)**
   - Model: `glm-5.3` (EvrenLLM)
   - Görev: Karşı-tez sunar ve risk kurallarını denetler.
4. **4. Sandalye: Presiding Arbiter (Risk Gate)**
   - Model: `policy-deterministic-v2` (Python Deterministic Rule Engine)
   - Görev: Kesin karar verir. `MARKET_ONLY` modunda sermayeyi korumak için güvenli **`NO_TRADE`** veya **`VETO`** kararı uygulayarak yetkisiz para transferlerini engeller.

---

## 6. OpenCode İçinde EvrenLLM ile Odaklanabileceğiniz Görevler

OpenCode'a geçtikten sonra istemlerinizde şu odak alanlarını belirtebilirsiniz:

1. **EvrenLLM TradeCourt Promptları & Structured Output (Person 1):**
   - `backend/aegis/integrations.py` dosyasındaki EvrenLLM istemlerini optimize etmek.
   - `glm-5.3` modelinin piyasa koşullarına göre `BUY`, `SELL` veya `NO_TRADE` tezlerini JSON structured output formatında döndürmesini test etmek.

2. **OKX Demo İşlem Entegrasyonu (Person 2):**
   - OKX TR Demo API anahtarlarınızı `backend/.env` dosyasına ekleyip (`AEGIS_OKX_DEMO_API_KEY`, vb.) `AEGIS_DEMO_ENABLED=true` yaparak sanal fonlarla canlı sandbox emir iletimini test etmek.

3. **Avalanche Fuji On-chain Kanıtlar (Person 3):**
   - ERC-8004 Agent ID 273 kimliği ve `/api/web3/verify` zincir üstü teyit akışını genişletmek.

---

## 7. Önemli Hatırlatmalar ve İpuçları

- **Ağ Koruması:** `contracts/openapi.yaml` kontratı ve 143 korumalı model/veri seti hash'i projenin kurallarına bağlıdır; kontrat yapısını bozmadan genişletiniz.
- **Port Çakışması:** Port `8000` sistemde `ankara_events` tarafından kullanılmaktadır. AEGIS için daima `8080` (backend) ve `3000` (frontend) portlarını kullanınız.
- **Yerel Operatör:** `frontend/src/app/page.tsx` ve `activity/page.tsx` yerel Wi-Fi IP'nizi (`192.168.*`) otomatik tanıdığı için "Judge Lock" kilidi olmadan yönetim kontrolleri serbesttir.
