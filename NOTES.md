# NOTES — Dahili Teknik Bellek ve Mühendislik Notları

> **Temel Felsefe:**  
> Kod dosyaları bir işin **"nasıl"** yapıldığını anlatır; git geçmişi **"ne zaman"** yapıldığını gösterir; `NOTES.md` ise o kodun **"neden"** o şekilde yazıldığını ve **"hangi alternatiflerin neden elendiğini"** açıklar.  
> Kod içine paragraflarca yorum satırı yığmak yerine, mimarinin görünmeyen kısıtları ve tecrübeleri burada diske sabitlenir.

---

## 1. Mimari Tercihler ve Gerekçeler (Architecture Decisions & Trade-offs)

### Saf Python Standart Kütüphanesi (Zero-Dependency)
- **Tercih:** Harici hiçbir paket (`mcp`, `websockets`, `pydantic`, `pyyaml`) yüklenmeden saf Python stdlib (`socket`, `struct`, `fcntl`, `urllib`, `json`) kullanıldı.
- **Kazanç:**
  - Soğuk başlangıç süresi **~68-80 ms**'dir (Resmi Python `mcp` SDK'sı `FastMCP` ile ~455 ms sürüyordu).
  - RAM tüketimi sadece **~9-12 MB**'dır (Harici paketlerle ~45-60 MB).
  - Arch Linux veya Python sürümü güncellense dahi paket kırılması yaşanmaz; sanal ortam (`venv`) gerektirmez.
- **Kabul Edilen Ödün (Trade-off):** RFC-6455 WebSocket istemcisi (`src/cdp_client.py`) ve JSON-RPC 2.0 stdio sunucusu (`src/mcp_stdio.py`) sıfırdan el ile yazıldı. Kod miktarı ~200 satır arttı ancak bakım maliyeti sıfırlandı.

### Çekirdek Seviyesinde Lider Seçimi (`fcntl.flock`)
- **Tercih:** `$XDG_RUNTIME_DIR/antigravity-desktop-live-quota.lock` dosyası üzerinde non-blocking Linux kernel kilidi uygulandı.
- **Kazanç:** Kullanıcı hem masaüstü uygulamasını, hem CLI'ı hem de yeni pencereleri açtığında yalnızca tek bir lider süreç CDP soketine bağlanır. Soket çakışması ve çift rozet riski %100 önlenir. Lider çökerse Linux çekirdeği kilidi anında serbest bırakır ve yedek süreç (`STANDBY`) sıfır gecikmeyle lider olur.

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

- **Soğuk Başlangıç Gecikmesi:** `68.0 ms` — `85.0 ms` (Bizzat `make test` ile ölçüldü).
- **Rozet Boyutları:** Genişlik `400.8 px`, Yükseklik `24.0 px` (Üst bar yüksekliği: `35.0 px`).
- **Yoklama (Polling) Eşiği:**
  - Ağdan kota çekme: `30.000 ms` (Sunucuya yük bindirmemek için).
  - DOM geri sayım render döngüsü: `5.000 ms` (Ağ isteği yapmadan sadece yerel süreyi akıtır).
  - Lider izleyici kontrol sıklığı: `8 saniye`.
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

---

## 5. Sahadan Süzülen İlkeler (Lessons Learned & Heuristics)

- **Tahminle Koda Girme:** Emin olmadığın API parametrelerini tahmin etmek yerine doğrudan ikili dosyayı veya protokolü incele (`strings /opt/Antigravity/resources/bin/language_server`).
- **Idempotency Şarttır:** Tarayıcıya enjekte edilen her script, kendisinden önce çalışan zamanlayıcıları (`clearInterval`) ve gözlemcileri (`disconnect`) temizlemelidir. Asla çift döngü veya hafıza sızıntısı bırakılamaz.
- **Her Değişiklik Canlı Kanıtla Kapanır:** Kod yazıldıktan sonra mutlaka `make test` koşturulmalı ve açık Antigravity penceresindeki DOM durumu CDP ile kontrol edilmelidir.

---

## 6. Açık Kaynak Güvenlik ve Katalog Uyumluluğu (Ecosystem & Catalog Compliance)

- **HOL Plugin Scanner & Açık Kaynak Standartları:**
  - Proje `awesome-ai-plugins` (1.000+ ⭐) kataloğuna eklenirken otomatik CI/CD güvenlik taramasından geçirildi.
  - Zero-dependency (sıfır harici paket) prensibine sahip projelerde dahi otomatik araçların denetim yapabilmesi için şu standart dosyaların bulunması zorunludur:
    1. `LICENSE`: Açık lisans şeffaflığı (MIT).
    2. `SECURITY.md`: Sorumlu güvenlik açığı bildirim kanalı (`info@mefamex.com`).
    3. `.github/dependabot.yml`: GitHub Actions adımlarının güvenlik güncellemelerini takip etmek için.
    4. `pyproject.toml` & `requirements.txt`: Standart Python paket indeksleme ve sıfır-bağımlılık manifestosu.
  - Bu standartlar tamamlandıktan sonra katalog botu skorumuzu **68'den 92'ye (A+)** yükseltmiş ve tüm kapıları yeşile çevirmiştir (PR #1222).

---

## 7. Git & Commit Standartları

Commit kuralları: https://github.com/Mefamex/mfmx-project-conventions/blob/main/GIT_STANDARDS.md adresinden okunabilir.
