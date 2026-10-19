# OpenCode yardımcı araçları — kurulum kaydı

18 Ekim 2026 · Windows · OpenCode Desktop/CLI 2.0.32

## Kurulanlar ve kullanım

| Araç | Sürüm | OpenCode içinden kullanım | Doğrulama |
|---|---|---|---|
| Serena | 2.0.0 | “Serena ile bu fonksiyonun tanımını ve çağıranlarını bul.” | MCP bağlı; backend Python dosyasında `deny_external_network` ve iç fonksiyonları, frontend TypeScript dosyasında `DashboardPage` bulundu. |
| Context7 CLI + `find-docs` skill | 0.8.0 | “@find-docs ile kullandığım sürümün API belgesini doğrula.” | Anahtarsız kütüphane araması ve sürüm belirtilen Next.js belge sorgusu başarılı. |
| Playwright CLI + skill | 0.1.22 | “@playwright-cli ile yerel panelin şu akışını test et.” | Ayrı Edge oturumu açıldı, sayfa sorgulandı ve yalnız test oturumu kapatıldı. |
| Plannotator | Eklenti ve Windows CLI 0.28.23 | `/plannotator-review`, `/plannotator-annotate dosya.md`, `/plannotator-last` | OpenCode V2 eklenti durumu `active`; üç native komut kayıtlı; yerel belge inceleme ekranı HTTP 200 döndürdü. |

Bunlar farklı türde entegrasyonlardır: Serena bir MCP sunucusu; Context7 ve Playwright ihtiyaç anında kullanılan CLI + skill; Plannotator gerçek OpenCode eklentisi ve onu tamamlayan Windows çalıştırıcısıdır.

EVREN sağlayıcısı ve seçili model ayarları kurulum öncesi yedekle karşılaştırıldı; değişmediler. Kurulum ve bağlantı doğrulamaları EVREN model çağrısı içermedi. Bu, karşılaştırmalı EVREN hız ölçümü değildir.

## Günlük davranış

- Serena aktif proje kökünü çalışma dizininden bulur. `ide` bağlamı, klasik araç arayüzü, planlama ve belleksiz mod kullanılıyor. Dashboard otomatik açılmıyor.
- AEGIS için `.serena/project.yml`, `backend`, `frontend`, `web3` ve `scripts` dizinlerine odaklanır. Bağımlılıklar, `.env` dosyaları, model/veri/ML kanıtları ve sözleşme çıktıları gezinme kapsamının dışında. Serena burada salt okunur; uygulama değişiklikleri OpenCode'un normal düzenleme araçlarıyla yapılır. Bu ayarlar güvenlik sandbox'ı değildir.
- Context7 öncesinde kurulu sürümle eşleşen yerel belge kullanılır. CLI için yeni paket indiren `npx @latest` yerine sabit yerel çalıştırıcı tanımlandı. Anahtarsız kota şu anda çalışıyor; daha yüksek limit gerekirse sonradan hesap bağlanabilir. Deneme sırasında açılan giriş bekleyişi iptal edildi; kullanıcı adına hesap oluşturulmadı.
- Playwright yerel Edge ile çalışıyor; ek tarayıcı indirmesi gerekmedi. Ayrı oturum kullanılır, mevcut kişisel tarayıcı oturumuna bağlanılmaz. Varsayılan başlangıç örneği: `playwright-cli.cmd -s=aegis-ui open about:blank --browser=msedge`.
- Plannotator `workflow: manual` ile yapılandırıldı. Otomatik plan onayı, Inbox veya ek ajan hook'ları kurulmadı. Native komutlar model üzerinden shell komutu yazdırmadan inceleme başlatabilir; kullanıcı isterse çağrılır.
- Global OpenCode talimatı `C:/Users/hackathon/.config/opencode/AGENTS.md` bu dar kullanım kurallarını açıklar. Her yeni görevde tekrar kurulum/güncelleme yapılmamalı.

## Dosyalar ve geri alma

Ana OpenCode ayarı: `C:/Users/hackathon/.config/opencode/opencode.jsonc`.

Kurulum öncesi birebir yedek: `C:/Users/hackathon/AppData/Local/HackathonTools/opencode-addons/opencode-before-*.jsonc`. Yedek sağlayıcı ayarlarını içerebileceğinden paylaşılmamalı.

Yerel npm paketleri ve sürüm kilidi: `C:/Users/hackathon/AppData/Local/HackathonTools/opencode-addons/package.json` ve `package-lock.json`. Plannotator ayrıca OpenCode'un kendi paket yöneticisiyle tam sürüm belirtilerek kuruldu; etkin yapılandırmada tek Plannotator kaydı var.

Kararlı çalıştırıcılar mevcut kullanıcı PATH'indeki `C:/Users/hackathon/AppData/Local/HackathonTools/bin/` altında:

- `ctx7.cmd`
- `playwright-cli.cmd`
- `uv.exe` ve `uvx.exe`
- `plannotator.exe`

Serena çalıştırıcısı MCP ayarında mutlak yolla kullanılır: `C:/Users/hackathon/.local/bin/serena.exe`. Python araç ortamı proje sanal ortamlarından ayrıdır. Genel `opencode.cmd` eski V1 olduğundan V2 eklenti yönetiminde masaüstünün paketlenmiş çalıştırıcısı kullanılmalıdır:

`C:/Users/hackathon/AppData/Roaming/ai.opencode.desktop/cli/2.0.32-x64/opencode-cli.exe`

Kaldırma gerektiğinde önce ilgili OpenCode kaydı/skill kaldırılır; test raporları ve proje kaynakları silinmez. Bütün eski ayarı geri yüklemek yerine sonradan eklenen diğer ayarları koruyarak yalnız ilgili kaydı çıkarmak tercih edilir. Bu çalışmada commit yapılmadı.

## Doğrulama kayıtları

`C:/Users/hackathon/AppData/Local/HackathonTools/opencode-addons/` altında:

- `serena-smoke.json`: Python ve TypeScript sembol sorguları başarılı.
- `serena-smoke-stderr.log`: dil sunucusu başlangıç kaydı.
- `context7-smoke.txt`: kaynak URL'siyle sürümlü Next.js belge sonucu. Buradaki v16.2.9 sorgusu bağlantı denemesidir; projenin kurulu Next.js sürümünün aynı olduğunu iddia etmez.
- `plannotator-smoke.json`: inceleme sunucusu HTTP 200 kontrolü.
- `plannotator-smoke.log`: test sunucusu kaydı; testin kendi süreci kapatıldı.
- `plannotator-win32-x64.exe.sha256`: üreticinin yayımladığı özet. İndirilen çalıştırıcı şu değerle eşleşti: `78c5f322bb208822782e9e2d8bb47cefb18de4fa7adaf57c4add256ee97ec740`.

Test tarayıcısının oluşturduğu `.playwright-cli/` dosyaları projede yerinde bırakıldı ve `.gitignore` kapsamına alındı. Otomatik onay denetimi, geçici dosyaları taşıyıp boş klasörü kaldırma adımını engelledi; ayrıntılı gerekçe sunmadı. Bu adım kurulum için gerekli değildi.

Plannotator indirmesinde sistemin GitHub çözümlemesiyle bağlantı zaman aşımına uğradı. Tek indirme isteği için Google DNS yanıtındaki GitHub adresi kullanıldı; TLS doğrulaması açık kaldı. Sistem DNS/hosts ayarları değiştirilmedi. İndirme resmi GitHub sürüm varlığından yapıldı ve hem yayımlanan `.sha256` dosyası hem sürüm sayfasındaki özetle eşleştirildi. Gelecekte GitHub'dan indirme yine etkilenebilir; bu kurulum genel ağ ayarı düzeltmesi değildir.

Bu turda uygulama kaynakları değişmediği için önceki 559 test yeniden koşturulmadı. Kuruluma özel bağlantı/işlev kontrolleri ve Git fark kontrolü yapıldı. Hız kazancı veya gelecekteki model maliyeti için henüz A/B ölçümü yok.

## Resmi kaynaklar

- [Serena kurulumu](https://oraios.github.io/serena/02-usage/010_installation.html)
- [Context7](https://github.com/upstash/context7)
- [Playwright CLI](https://github.com/microsoft/playwright-cli)
- [Plannotator OpenCode V2 kurulumu](https://github.com/backnotprop/plannotator/blob/main/apps/opencode-plugin/README.md)
- [Plannotator v0.28.23 varlıkları ve özetleri](https://github.com/backnotprop/plannotator/releases/expanded_assets/v0.28.23)
- [OpenCode MCP](https://opencode.ai/v2/docs/mcp-servers/)
- [OpenCode skill keşfi](https://opencode.ai/v2/docs/skills/)
