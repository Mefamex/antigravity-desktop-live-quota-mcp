# NOTES — Dahili Teknik Bellek ve Mühendislik Notları

> **Temel Felsefe:**  
> Kod dosyaları bir işin **"nasıl"** yapıldığını anlatır; git geçmişi **"ne zaman"** yapıldığını gösterir; `NOTES.md` ise o kodun **"neden"** o şekilde yazıldığını ve **"hangi alternatiflerin neden elendiğini"** açıklar.  
> Kod içine paragraflarca yorum satırı yığmak yerine, mimarinin görünmeyen kısıtları ve tecrübeleri burada diske sabitlenir.

---

## 1. Mimari Tercihler ve Gerekçeler (Architecture Decisions & Trade-offs)

### Saf Python Standart Kütüphanesi (Zero-Dependency)
- **Tercih:** Harici hiçbir paket (`mcp`, `websockets`, `pydantic`, `pyyaml`) yüklenmeden saf Python stdlib (`socket`, `struct`, `fcntl`, `urllib`, `json`) kullanıldı.
- **Kazanç:**
  - Soğuk başlangıç süresi **~55-70 ms**'dir (Resmi Python `mcp` SDK'sı `FastMCP` ile ~455 ms sürüyordu).
  - RAM tüketimi sadece **~9-12 MB**'dır (Harici paketlerle ~45-60 MB).
  - Arch Linux veya Python sürümü güncellense dahi paket kırılması yaşanmaz; sanal ortam (`venv`) gerektirmez.
- **Kabul Edilen Ödün (Trade-off):** RFC-6455 WebSocket istemcisi (`src/cdp_client.py`) ve JSON-RPC 2.0 stdio sunucusu (`src/mcp_stdio.py`) sıfırdan el ile yazıldı. Kod miktarı ~200 satır arttı ancak bakım maliyeti sıfırlandı.

### Çekirdek Seviyesinde Lider Seçimi (`fcntl.flock`)
- **Tercih:** `$XDG_RUNTIME_DIR/antigravity-desktop-live-quota.lock` dosyası üzerinde non-blocking Linux kernel kilidi uygulandı.
- **Kazanç:** Kullanıcı hem masaüstü uygulamasını, hem CLI'ı hem de yeni pencereleri açtığında yalnızca tek bir lider süreç CDP soketine bağlanır. Soket çakışması ve çift rozet riski %100 önlenir. Lider çökerse Linux çekirdeği kilidi anında serbest bırakır ve yedek süreç (`STANDBY`) sıfır gecikmeyle lider olur.

### v1.3.0 Denetim ve Mühendislik Kararları
1. **RFC-6455 Tam Çerçeve Uyumu (`src/cdp_client.py`):** Büyük CDP yanıtlarındaki parçalı çerçevelerin (`FIN=0` / `0x00` continuation) birleştirilmesi, sunucu `Ping` (`0x09`) çerçevelerine maskeli `Pong` (`0x0A`, `_send_ws_control_frame`) yanıtı verilmesi ve `Close` (`0x08`) kontrol çerçevelerinin temiz işlenmesi harici paket olmadan sağlandı.
2. **Dinamik Model Eşleme ve Kova Bazlı Burn-Rate (`src/ui_payload.py`):** Sabit model listesi yerine `detectActiveModelGroup(quota)` ile `quota.groups[].description` ve `displayName` üzerinden dinamik eşleştirme (yeni çıkacak modeller için anahtar kelime fallback'i ile) ve 5 saatlik Gemini (`g5h`) / Claude-GPT (`c5h`) kotaları için ayrı geçmiş tamponları kullanılarak kota `> +%5` arttığında kova bazlı burn-rate sıfırlaması uygulandı.
3. **Bulut Hız Sınırlama & Endpoint Önbelleği (`config.py`, `src/quota_client.py`, `src/ui_watcher.py`):** Tarayıcı kota yoklama aralığı `60.000 ms`, masaüstü bildirim denetimi `120 saniye` olarak ayarlandı; UI rozeti aktifken (`cdp_active=True`) bildirim kontrolünün `force_refresh=(not cdp_active)` ile yerel önbelleği okuması sağlanarak çift bulut yenilemesi önlendi. Çalışan `(pid, port, scheme, csrf_token)` uç noktası `_CACHED_ENDPOINT` içinde önbelleklenerek sonraki yerel çağrıların önbellek isabetinde `~2-4 ms` sürmesi sağlandı.
4. **Yerel CDP Güvenlik Dengesi ve Taşınabilir Kurulum (`install.sh`, `SECURITY.md`):** `--remote-debugging-port=0` bayrağının `127.0.0.1` loopback arayüzünde diğer yerel aynı-kullanıcı süreçlerine CDP (`Runtime.evaluate`) erişimi açması nedeniyle sıkı izolasyon isteyen kullanıcılar için `--no-cdp-launcher` seçeneği sunuldu (`AGY_UI_INJECTION_ENABLED=false` belgelemesiyle birlikte). Ayrıca `install.sh` içinde `$PATH` ve standart kurulum yollarından yönetilen sarmalayıcıyı atlayarak gerçek ikiliyi çözen `resolve_system_antigravity_bin()` eklendi.
5. **Tam İngilizce Kod Tabanı (`refactor(i18n)`):** Küresel topluluk uyumu için tüm kaynak kod, loglar, UI rozet/bildirim metinleri, kurulum/derleme betikleri ve testler davranış değişikliği olmaksızın tek izole commit ile %100 İngilizceye standardize edildi.

---

## 2. Denenip Vazgeçilen Yollar (Discarded Approaches)

1. **Statik CDP Portu Tanımlama:**
   - *Denenen:* `localhost:41943` gibi bir portu sabitlemek.
   - *Neden Elendi:* Antigravity Desktop kapatılıp yeniden açıldığında Chromium tabanı rastgele yeni bir boş porta (`34235`, `46557` vb.) bağlanır. Statik port `Connection refused (Errno 111)` hatasıyla çöktü. `~/.config/Antigravity/DevToolsActivePort` dosyasını dinamik okuyan `src/discovery.py` yazıldı.
2. **Boş `{}` İstek Gövdesi ile Kota Çekme:**
   - *Denenen:* `/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary` RPC'sine `{}` göndermek.
   - *Neden Elendi:* Dil sunucusu arka planda kendi önbelleğini tuttuğu için kullanıcı rozete tıkladığında buluttan güncel kotayı çekmiyordu; eski sayılar görünüyordu. `language_server` ikili dosyası tersine mühendislikle incelenerek `{ forceRefresh: true }` bayrağı keşfedildi ve uygulandı.
3. **Resmi Python `mcp` SDK (`FastMCP`):**
   - *Denenen:* Resmi paketle MCP sunucusu ayağa kaldırmak.
   - *Neden Elendi:* Sadece stdio üzerinden konuşmak için bile 28 harici paket (`starlette`, `uvicorn`, `anyio` vb.) belleğe yüklendi, başlangıç süresi 455 ms'ye fırladı. Saf Python `stdio` döngüsüne geçildi.
4. **Geniş ve Sağa Yaslı Rozet:**
   - *Denenen:* 513px genişliğinde, model isimlerini uzun yazan ve sağa yaslanan rozet.
   - *Neden Elendi:* Pencerenin arama kutusu ve pencere kontrolleriyle çakıştı. Sola yaslandı, isimler kısaltıldı (`⚡G:`, `Ar:`, `C:`), dinamik geri sayım eklendi ve genişlik ~400px'e çekildi.

---

## 3. Doğrulanmış Sistem Sınırları ve Eşikler (Verified Constraints)

- **Soğuk Başlangıç Gecikmesi:** `~55-70 ms` (Bizzat `make test` ile ölçüldü).
- **Rozet Boyutları:** Genişlik `400.8 px`, Yükseklik `24.0 px` (Üst bar yüksekliği: `35.0 px`).
- **Yoklama (Polling) Eşiği:**
  - Ağdan kota çekme (`BROWSER_FETCH_INTERVAL_MS`): `60.000 ms` (Bulut hız sınırlarını korumak için).
  - DOM geri sayım render döngüsü: `5.000 ms` (Ağ isteği yapmadan sadece yerel süreyi akıtır).
  - Lider izleyici kontrol sıklığı (`WATCHER_CHECK_INTERVAL_SEC`): `8 saniye`.
  - Lider masaüstü bildirim yoklaması (`WATCHER_NOTIFY_INTERVAL_SEC`): `120 saniye` (`cdp_active=True` iken yerel önbellekten okur).
- **Zaman Aşımı (Timeout):** Yerel socket ve HTTP bağlantıları için `2.0 saniye`.

---

## 4. Platform Gariplikleri ve Tuzaklar (Quirks & Gotchas)

1. **Stdout İzolasyonu (JSON-RPC 2.0 Kuralı):**
   - MCP `stdio` protokolünde `stdout` akışı yalnızca ve yalnızca geçerli JSON-RPC mesajlarına ayrılmıştır.
   - Eğer koddaki herhangi bir `print()` veya üçüncü parti kütüphane uyarısı `stdout`'a sızarsa istemci (Antigravity/Claude) JSON parse hatası verir ve bağlantıyı koparır.
   - **Emniyet:** `src/logger.py` modülü `%100` oranında `sys.stderr` akışına kilitlenmiştir.
2. **CSRF Token Zorunluluğu:**
   - `language_server` ConnectRPC isteklerinde `X-Codeium-Csrf-Token` başlığını zorunlu kılar.
   - Bu token süreç komut satırı argümanlarından (`--csrf_token=...`) veya tarayıcı içi `window.__APP_CONFIG__.csrfToken` nesnesinden okunmalıdır.
3. **Wayland & HiDPI Ölçekleme (devicePixelRatio):**
   - KDE Plasma 6 Wayland fractional scaling altında (örneğin `%125` veya `%132.5`) sabit piksel kenar boşlukları taşma yapabilir.
   - Bu nedenle rozet kapsülü `clamp(6px, 1vw, 12px)` ve `flex-shrink: 0` adaptif CSS kurallarıyla donatıldı.
4. **Antigravity 2.33.0+ Opt-In CDP Değişikliği (`--remote-debugging-port=0`):**
   - `2.31.0` ve `2.32.1` sürümlerindeki `app.asar` (`dist/main.js`), açılışta otomatik olarak `app.commandLine.appendSwitch('remote-debugging-port', '0')` ekliyordu.
   - `2.33.0` (2026-11-19) güncellemesiyle Google bu varsayılanı kaldırdı; bayrak verilmeden açıldığında `removeStaleActivePortFile()` ile `~/.config/Antigravity/DevToolsActivePort` dosyasını aktif olarak silmeye başladı (`dist/main.js`). Ayrıca bayrak verildiğinde `language_server` ortamına `AGY_BROWSER_ACTIVE_PORT_FILE` aktarıyor.
   - **Karar:** `sudo` gerektiren sistem dizinine (`/usr/share/applications/`) dokunmak veya paket güncellemelerinde ezilecek `app.asar` yaması yapmak yerine, XDG standardı `~/.local/share/applications/antigravity.desktop` + `~/.local/bin/antigravity` kullanıcı-seviyesi launcher override yaklaşımı seçildi. Böylece sonraki `pacman`/`yay` güncellemelerinde dahi CDP açık kalır.

---

## 5. Sahadan Süzülen İlkeler (Lessons Learned & Heuristics)

- **Tahminle Koda Girme:** Emin olmadığın API parametrelerini tahmin etmek yerine doğrudan ikili dosyayı veya protokolü incele (`strings /opt/Antigravity/resources/bin/language_server`).
- **Idempotency Şarttır:** Tarayıcıya enjekte edilen her script, kendisinden önce çalışan zamanlayıcıları (`clearInterval`), bekleyen `requestAnimationFrame` yeniden bağlama isteklerini (`reattachFrameId` üzerinden `cancelAnimationFrame`) ve gözlemcileri (`disconnect`) temizlemelidir. `MutationObserver` yalnızca `requestAnimationFrame` ile debounce edilerek çalışmalı; asla çift döngü veya hafıza sızıntısı bırakılamaz.
- **Her Değişiklik Canlı Kanıtla Kapanır:** Kod yazıldıktan sonra mutlaka `make test` koşturulmalı ve açık Antigravity penceresindeki DOM durumu CDP ile kontrol edilmelidir.

---

## 6. Açık Kaynak Güvenlik ve Katalog Uyumluluğu (Ecosystem & Catalog Compliance)

- **HOL Plugin Scanner & Açık Kaynak Standartları:**
  - Proje `awesome-ai-plugins` (1.000+ ⭐) kataloğuna eklenirken otomatik CI/CD güvenlik taramasından geçirildi.
  - Zero-dependency (sıfır harici paket) prensibine sahip projelerde dahi otomatik araçların denetim yapabilmesi için şu standart dosyaların bulunması zorunludur:
    1. `LICENSE`: Açık lisans şeffaflığı (MIT).
    2. `SECURITY.md`: Sorumlu güvenlik açığı bildirim kanalı (`info@mefamex.com`).
    3. `.github/dependabot.yml`: GitHub Actions adımlarının güvenlik güncellemelerini takip etmek için.
    4. `pyproject.toml` & `requirements.lock`: Standart Python paket indeksleme (PEP 621) ve sıfır bağımlılıklı deterministik lockfile (scanner'ın `DEPENDENCY_LOCKFILE_MISSING` kuralını 100/100 ile karşılar).
    5. `.github/workflows/scanner.yml`: Repoda her push ve PR'da HOL Plugin Scanner'ı (SHA-40 ile pinli actions) koşturan resmi CI iş akışı.
  - Bu standartlar tamamlandıktan sonra yerel ve CI katalog tarayıcısında skorumuz **100/100 (A+ Excellent)** tam puana ulaşmıştır (Security: 16/16, Operational Security: 20/20, Best Practices: 6/6, Code Quality: 10/10).

---

## 7. Git & Commit Standartları

Commit kuralları: https://github.com/Mefamex/mfmx-project-conventions/blob/main/GIT_STANDARDS.md adresinden okunabilir.
