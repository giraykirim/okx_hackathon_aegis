# OpenCode verimlilik uygulaması ve eklenti araştırması

18 Ekim 2026 · AEGIS · Windows · OpenCode Desktop 2.0.32

Sonraki işlem: kullanıcı onayından sonra dört seçilen araç kuruldu. Ayrıntılı kurulum, sürümler ve doğrulama kaydı `docs/OPENCODE_ADDONS_SETUP_2026-10-18.md` içinde. Aşağıdaki “kurulmadı” ifadeleri araştırmanın yapıldığı ilk aşamanın durumudur.

## Karar

Önceki incelemede saptanan günlük geliştirme sorunları için ortak test çalıştırıcısı, ortam kontrolü, salt okunur dosya bütünlüğü kontrolü, proje talimatları ve ağ koruması düzeltmesi uygulandı. OpenCode'un arama bağımlılığı da bilgisayarda çalışır duruma getirildi. Eklentiler bu çalışma kapsamında kurulmadı; aşağıdaki seçimler güncel üretici belgeleri üzerinden netleştirildi. EVREN ile bu adayların uçtan uca performansı henüz ölçülmedi.

Önerilen sıra: **Serena → Context7 → arayüz işlerinde Playwright CLI + skill**. Plannotator yalnız ihtiyaç halinde, manuel inceleme için. DCP, Superpowers'ın tüm iş akışı ve çok ajanlı büyük paketler ilk kurulumda eklenmemeli. Bu sıralama projede gözlenen darboğazlara göre yaptığım değerlendirmedir; üreticilerin hız garantisi değildir.

## 1. Uygulanan öncelikler

| Değişiklik | Sağladığı davranış |
|---|---|
| `scripts/dev.py` | Backend, ML, frontend, web3 ve araç testleri tek girişten çalışıyor. Alt sürecin gerçek hata kodu korunuyor. Tam çıktı dosyada, kısa sonuç JSON raporunda tutuluyor. |
| `doctor` | Python ortamlarını, Node, Git, ripgrep ve gerekli yerel bağımlılıkları kontrol ediyor. Kurulum, servis başlatma veya model ağırlığı yükleme yapmıyor. |
| `integrity` | `.gitattributes` içinde açıkça belirtilen 191 yolu Git HEAD checkout filtreleriyle karşılaştırıyor; dosyaları değiştirmiyor. |
| Kök `AGENTS.md` | Person 1/2/3 sınırlarını, doğru komutları, dar kapsamlı görevleri ve hash hassas dosyaların korunmasını tanımlıyor. |
| `docs/DEVELOPMENT_WORKFLOW.md` | Günlük kullanım ve kısa görev devri şablonu. |
| `backend/tests/_offline_guard.py` | `socketpair` sırasında bütün süreç için ağ bağlantısını geri açan davranış kaldırıldı. İstisna ilgili iş parçacığında socketpair süresi ve loopback adresleriyle sınırlandı. |
| `backend/tests/test_offline_guard.py` | Dört yeni test: dış bağlantının engellenmesi, iç loopback istisnası, diğer iş parçacığının engellenmesi ve hata sonrası iznin kapanması. Gerçek ağ kullanılmıyor. |
| `scripts/devtools/test_runner.py` | Çıkış kodu, tam hata kaydı, zaman aşımı, eksik araç ve salt okunur bütünlük kontrolü için 10 regresyon testi. |
| `frontend/package.json` | Açık `test` komutu eklendi. |
| `.gitignore` | Geçici geliştirme raporları ve Python önbellekleri sürüm kontrolü dışında. |

Test alt süreçlerine bilinen operatör/sağlayıcı anahtar değişkenleri aktarılmıyor. Bu, genel bir güvenlik yalıtımı değildir; test altyapısının hesabın anahtarlarına ihtiyaç duymamasını sağlar.

### OpenCode arama düzeltmesi

Bilgisayardaki mevcut resmi Codex dağıtımından gelen ripgrep 15.2.0, mevcut kullanıcı araç dizinine ve OpenCode'un arama önbelleği dizinine yerleştirildi:

- `C:/Users/hackathon/AppData/Local/HackathonTools/bin/rg.exe`
- `C:/Users/hackathon/.cache/opencode/bin/rg.exe`

Yeni bir sistem PATH değişikliği gerekmedi. OpenCode 2.0.32'nin paketlenmiş CLI'ı ile proje kökünde ayrı bir yerel servis üzerinden `fs.find` çağrısı yapıldı; `AGENTS` araması doğru proje dosyalarını döndürdü, çıkış kodu 0 oldu. Açık masaüstü oturumu yeniden başlatılmadı. Bu kontrol model çağrısı içermedi.

Bilgisayarda eski genel OpenCode CLI 1.19.3 ile masaüstünün paketlenmiş CLI 2.0.32'si birlikte bulunuyor. Yeni eklenti işlemlerinde masaüstüyle eşleşen V2 kullanılmalı; komut adının aynı olması sürümün aynı olduğu anlamına gelmiyor.

## 2. Doğrulama

Son tam koşu: `.devtools/runs/20261018T180919.926523Z-12240/summary.json`.

| Paket | Geçen test | Alt süreç süresi | Çıkış kodu |
|---|---:|---:|---:|
| Backend | 229 | 14,226 sn | 0 |
| ML | 256 | 20,767 sn | 0 |
| Frontend | 61 | 3,239 sn | 0 |
| Web3 | 3 | 1,711 sn | 0 |
| Geliştirme araçları | 10 | 0,612 sn | 0 |
| **Toplam** | **559** | **40,555 sn** | **0** |

Önceki 545 teste dört backend ve 10 çalıştırıcı testi eklendi. Önceki ML çıktısındaki “testler OK, araç çıkışı 1” çelişkisi yeni çalıştırıcı üzerinden tekrarlanmadı; 256 test ve çıkış kodu 0 birlikte kaydedildi.

Bilerek olmayan bir backend test yolu verildiğinde pytest'in 4 hata kodu çalıştırıcıdan da 4 olarak çıktı. Bu beklenen başarısızlık denemesi `.devtools/runs/20261018T180713.424398Z-23336/summary.json` içinde. Ayrıca başarılı bir sürecin stderr'e yazmasının başarısızlık sayılmadığı ve 7 hata kodunun aynen aktarıldığı regresyon testleri geçti.

Ortam kontrolü başarılı; 191 açık dosya yolunda bütünlük uyuşmazlığı yok. Son bütünlük raporu `.devtools/runs/20261018T181007.658692Z-26960/summary.json`. Değişen Python dosyalarının Ruff kontrolleri ve biçim kontrolü başarılı. Git boşluk/hata kontrolü temiz. Backend koşusunda Starlette/AnyIO bağımlılığından bir kullanımdan kaldırma uyarısı var; test başarısızlığı yok. Bu kapsamda bağımlılık sürümü değiştirilmedi.

Bu yaklaşık 41 saniye yalnız son test alt süreçlerinin toplamıdır. Önceki 53 dakika 24 saniyelik araştırma ve düzeltme işinin artık 41 saniyede yapılacağı anlamına gelmez. Kazanç hedefi yanlış teşhis, tekrarlanan geniş test koşuları ve gereksiz model turlarını azaltmaktır.

## 3. Eklenti seçiminde sürüm farkı

OpenCode V1 eklenti örnekleri V2'ye doğrudan kopyalanmamalı. V2'nin eklenti API'si ve yapılandırması farklı; V1 `plugin` örnekleri yerine adayın V2 talimatı izlenmeli. [Resmi V1 → V2 geçiş belgesi](https://opencode.ai/v2/docs/build/plugins/migrate-v1)

V2'de MCP için Code Mode varsayılan. Bu nedenle yalnız araç çağrılarını birleştirmek amacıyla ayrıca “code mode” eklentisi eklemek ilk ihtiyaç değil. Sunucu talimatları ve sonuçları yine bağlama girebildiğinden gereksiz MCP sunucuları sürekli açık tutulmamalı. [OpenCode V2 MCP belgesi](https://opencode.ai/v2/docs/mcp-servers/)

## 4. Net kısa liste

### Serena — kod içinde gezinme için ilk aday

**AEGIS'te kullanım:** bir fonksiyonun tanımını ve çağıranlarını bulmak, backend politikası ile testleri arasındaki ilişkiyi çıkarmak, frontend sembollerini hedefli okumak. Metin aramasının yerine her durumda geçmez; sembol ve referans takibinde anlamlıdır.

**Önerilen düzen:** yalnız AEGIS projesine bağlı yerel MCP, `ide` bağlamı ve başlangıçta açık proje yolu. `ide`, mevcut dosya/shell araçlarını tamamlar; tek proje yapılandırması gereksiz araçları azaltabilir. Serena v2 ayrıca işlemleri tek çağrıda birleştiren REPL arayüzü sunuyor. Önce basit araç arayüzüyle doğrulama, ardından EVREN ile ayrı REPL denemesi uygun. [Serena yapılandırması](https://oraios.github.io/serena/02-usage/050_configuration.html)

**Kurulum tercihi:** sürümü sabitlenmiş yerel kurulum. Üretici, Git'in en güncel kaynağını `uvx` ile çalıştırmanın her yeni commit'te yavaş yeniden eşitlemeye yol açabileceğini belirtiyor. Bu, hız hedefimiz açısından önemli. İlk indeksleme ile sonraki sıcak sorgular ayrı ölçülmeli. [Çalıştırma ve kurulum tercihi](https://oraios.github.io/serena/02-usage/020_running.html)

**Kabul ölçütü:** backend ve frontend'den seçilmiş birer sembolün gerçek referanslarını bulmalı; mevcut aramaya göre daha az okuma/model turuyla aynı doğru sonuca ulaşmalı. Başlatma ve indeksleme maliyeti kazancı aşıyorsa sürekli açık tutulmamalı. Bu projede henüz kurulup ölçülmedi.

### Context7 — gerektiğinde belge getirme

**AEGIS'te kullanım:** Next.js, FastAPI veya kullanılan bir paketin sürüme bağlı API davranışını doğrulamak. Her kod değişikliğinde çağrılması gerekmiyor. Frontend'in kurulu Next.js belgeleri zaten yerelde; önce bunlar kullanılmalı.

Güncel resmi kurulum CLI + skill ve MCP seçenekleri sunuyor; `ctx7 setup` OpenCode'u hedefleyebiliyor. CLI Node 22.13+ istiyor; bu bilgisayardaki Node 24.22.0 uygun. Ücretsiz API anahtarı daha yüksek limit için öneriliyor. OAuth ve anahtar oluşturma akışı var. [Context7 resmi deposu](https://github.com/upstash/context7)

**Tercihim:** ihtiyaç anında CLI + skill; sürekli MCP ancak kullanım sıklığı bunu haklı çıkarırsa. Bilinen kütüphane kimliği ve sürümle sorgulamak gereksiz eşleştirme adımını azaltır. Sorguya özel kod veya anahtar eklenmemeli. Yerel dokümanda bulunan bilgi için dış istek yapılmaması proje kuralı olarak korunmalı.

**Kabul ölçütü:** seçilmiş bir API sorusuna doğru sürümden kaynak getirmeli ve ilgisiz görevlerde kendiliğinden belge çağrısı üretmemeli. Bu öneri belge hatalarından doğan yeniden çalışmayı azaltmaya yöneliktir; modelin üretim hızını artırmaz.

### Playwright CLI + skill — arayüz çalışmaları için

**AEGIS'te kullanım:** panelde form doğrulaması, hata/boş/yükleniyor durumları, gezinme ve ekran görüntüleri. UI akışının gerçekten çalıştığını göstermek için anlamlı; backend test koşularını hızlandırmak için değil.

Microsoft'un güncel deposu, kodlama ajanlarında token verimliliği için CLI + skill yaklaşımını öneriyor. Sürekli tarayıcı durumu ve yoğun sayfa incelemesi gereken döngülerde MCP ayrı seçenek. CLI Node 18+ istiyor; mevcut sürüm uygun. [Playwright CLI](https://github.com/microsoft/playwright-cli), [Playwright MCP](https://github.com/microsoft/playwright-mcp)

**Tercihim:** ilk arayüz görevinde CLI + skill. OpenCode'un skill keşfi ve bir tarayıcı akışı ayrıca doğrulanmalı; genel ajan desteği, bu bilgisayardaki EVREN/OpenCode birleşiminde ölçülmüş uyum demek değildir. Senaryo ve tarayıcı ilk kurulum maliyeti ayrı kaydedilmeli. Canlı borsa/cüzdan işlemi günlük UI doğrulamasına dahil edilmemeli.

### Plannotator — isteğe bağlı görsel inceleme

Kapsamlı plan ve dosya incelemelerine yorum bırakmak için uygun. Güncel depo V2 `plugins` yapılandırmasını ve gerçek V2 sunucusuyla CI kontrolünü belgeliyor. V2'de `workflow: manual`, otomatik `submit_plan` kaydını kapatıp incelemeyi isteğe bağlı bırakıyor. [OpenCode eklenti belgesi](https://github.com/backnotprop/plannotator/blob/main/apps/opencode-plugin/README.md)

**Tercihim:** yalnız manuel kullanım. Her küçük düzeltmeye plan onayı eklemek kullanıcının bekleme şikâyetini artırır. Native komut desteği gibi özellikler host sürümüne bağlı olduğundan masaüstünde ayrıca denenmeli. İlk üç aracın önüne alınmamalı.

## 5. İlk pakete almadıklarım

| Aday | Güncel bulgu | AEGIS için karar |
|---|---|---|
| DCP | V2 kurulumu var. Geliştirici yeni bağlam yönetimi çalışmalarının çoğunu Sleev'e taşıdığını belirtiyor. Kırpma, önbellek öneklerini bozarak cache miss artırabilir. | Önce kısa görevler ve yerleşik özetleme. Daha az token otomatik olarak daha kısa süre veya daha düşük ücret değildir. |
| Superpowers | V2 2.0.4+ desteği var; Windows Git tabanlı kurulumlar için özel sorun giderme talimatları bulunuyor. | Gerektiğinde sistematik hata ayıklama/doğrulama becerileri değerlendirilebilir. Bütün iş akışını ilk anda eklemek yeni talimat ve aşamalar getirir. |
| Oh My OpenAgent / OmO | Güncel ana README, senpi üzerinde çalışan ayrı `omo` uygulamasını ve OpenCode sürümünden geçişi anlatıyor. | Mevcut OpenCode'a basit hız eklentisi gibi kurulması önerilmiyor. Uygulama değiştirmek bu araştırmanın hedefi değil. |
| Ek Code Mode paketi | OpenCode V2 zaten MCP Code Mode sunuyor. | Önce yerleşik özellik; aynı amaca hizmet eden ikinci katman gereksiz. |

Kaynaklar: [DCP durumu ve önbellek etkisi](https://github.com/Tarquinen/opencode-dynamic-context-pruning), [Superpowers OpenCode ve Windows talimatları](https://github.com/obra/superpowers/blob/main/docs/README.opencode.md), [OmO güncel ana deposu](https://github.com/code-yeongyu/oh-my-openagent), [OpenCode Code Mode](https://opencode.ai/v2/docs/mcp-servers/).

Sleev'in geliştirici tarafından önerilmesi, EVREN ile AEGIS'te doğrulandığı anlamına gelmez. Ayrı bir proxy katmanını yalnız bu öneriye dayanarak kurmak yerine somut bir ihtiyaç ve karşılaştırma aranmalı.

## 6. Bundan sonraki çalışma düzeni

1. Tek somut sonuç ve izin verilen dosya gruplarıyla görev aç.
2. Yeni ortamda bir kez `python scripts/dev.py doctor` çalıştır.
3. İlgili dosyayı/sembolü hedefli ara; bütün projeyi tekrar okutma.
4. Önce ilgili testi çalıştır. Başarısızsa tam kayıt dosyasını bir kez incele.
5. Düzeltme bitince ilgili paket, son değişiklikten sonra tam paketleri çalıştır.
6. Hash hassas dosyalara dokunulduysa `python scripts/dev.py integrity` ile farkı gör; otomatik dönüştürme yapma.
7. Sonucu, değişen dosyaları, test raporunu ve sonraki adımı kısa devir özetiyle bırak. Bağımsız sonraki iş için yeni oturum kullan.

Yerleşik özetleme bağlam sınırına yaklaşmayı yönetir; görev sınırında temiz oturum ve kalıcı devir özeti hâlâ faydalıdır. [OpenCode özetleme belgesi](https://opencode.ai/v2/docs/compaction/)

Eklenti denemesinde aynı model, aynı başlangıç dosyaları ve benzer kabul koşulları kullanılmalı. Duvar saati, model turu, araç çağrısı, test tekrarı, ilk açılış ve sıcak çalışma ayrı tutulmalı. Tek denemeden yüzde hızlanma çıkarılmamalı. Başarı ölçütü yalnız süre değil, aynı doğru sonucu daha az yeniden çalışmayla üretmek.

## 7. Açık kalan sınırlar

- `integrity`, açık EOL yollarını HEAD ile karşılaştırır. Bütün tarihsel manifestlerin yetkili dosya–hash envanteri değildir. Mevcut testlerin manifest kontrolleri korunuyor; tam envanter/göç çalışması ayrıca tasarlanmalı.
- Yeni Windows/Linux checkout ve CI matrisi bu çalışmada kurulmadı. Test kanıtı mevcut Windows ortamına aittir.
- ML ortamı mevcut kardeş `aegis/.venv` dizininden bulunuyor. Başka bilgisayarda `.venv-ml` veya `AEGIS_ML_PYTHON` ile açık yol gerekir.
- Test başarısı canlı borsa işlemi, dağıtım, yeni model eğitimi veya jüri kanıt sürecinin tamamlandığı anlamına gelmez.
- Değişiklikler yerel çalışma ağacında; otomatik commit yapılmadı. Eklenti uyumluluğunun belge üzerinden teyidi ile yerel kurulum testi ayrı tutuldu.

Günlük komutlar ve devir şablonu: `docs/DEVELOPMENT_WORKFLOW.md`. Önceki 53 dakikalık işlemin ayrıntılı incelemesi: `C:/Users/hackathon/Documents/OpenCode-AEGIS-Inceleme-2026-10-18.md`.
