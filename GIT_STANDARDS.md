# Git & Commit Standartları

> **Amaç:** `antigravity-desktop-live-quota-mcp` deposunda çalışan geliştiriciler ve AI kodlama ajanları için bağlayıcı Git kurallarıdır. Depoya dokunmadan önce bu kuralların okunması ve uygulanması zorunludur.

---

## 1. Altın Kural: Commit Serbest, Push İzne Tabi (Gatekeeping)

```
[ Lokal Kodlama ] ──> [ Atomik Commit ] ──> [ Hijyen Kontrolü ] ──> [ KULLANICI ONAYI ] ──> [ git push ]
```

- **Lokal Commit Serbesttir:** Küçük ve atomik commitler rollback'i kolaylaştırır; lokalde serbestçe alınır.
- **Push Kesinlikle İzne Tabidir:** **Hiçbir AI ajanı açık kullanıcı onayı almadan `git push` çalıştıramaz.**
- **Force Push Yasaktır:** Açık kullanıcı talimatı olmadıkça `git push --force` veya `-f` yasaktır.

---

## 2. Commit Mesaj Formatı (Conventional Commits v1.0.0)

Standart sözdizimi:
```text
<type>(<scope>): <açıklama>
<type>: <açıklama>
```

### Örnekler:
- `feat(ui): add live countdown timer for 5h and weekly quota reset`
- `fix(quota): pass forceRefresh to bypass language_server cache on click`
- `style(badge): brighten remaining time labels with #e2e8f0 slate color`
- `refactor(mcp): streamline leader election error handling in lock.py`
- `docs(readme): add authentic desktop screenshot and tool schemas`
- `perf(discovery): optimize DevToolsActivePort detection latency`
- `test(failover): verify automatic leader promotion on process termination`

---

## 3. Kabul Edilen `type` Değerleri

| Type | Kategori | Kullanım Alanı | SemVer |
| :--- | :--- | :--- | :--- |
| `feat` | Yeni Özellik | Yeni bir yetenek, UI bileşeni veya MCP aracı eklenmesi | MINOR |
| `fix` | Hata Giderme | Bug, kilitlenme, deadlock veya önbellek senkronizasyon çözümü | PATCH |
| `refactor` | Yeniden Yapılanma | Davranışı değiştirmeden mimari ve modül temizliği | - |
| `perf` | Performans | Başlangıç süresini veya kaynak tüketimini düşüren optimizasyon | - |
| `docs` | Dokümantasyon | README, TODO veya kılavuz güncellemeleri | - |
| `test` | Test | Birim/entegrasyon testi eklenmesi veya doğrulanması | - |
| `chore` | Bakım | `.gitignore`, bağımlılık, build veya temizlik görevleri | - |
| `style` | Görsel / Stil | UI rozet renkleri, CSS keyframes, font boyutları | - |

---

## 4. Yazım Kuralları (Google & Angular Standartları)

- **Emir Kipi (Imperative):** Geçmiş zaman (*"added"*, *"fixed"*) yerine doğrudan emir kipi (*"add"*, *"fix"*, *"update"*).
- **Küçük Harf (Lowercase):** `<type>` ve `<scope>` daima küçük harfle başlar.
- **Noktasız Bitiş:** Başlık satırının sonuna nokta (`.`) konmaz.
- **Uzunluk Sınırı:** Başlık 72 karakteri geçmemelidir (terminal okunabilirliği).
- **Netlik:** *"wip"*, *"fixes"*, *"update"*, *"commit"* gibi belirsiz mesajlar **kesinlikle yasaktır**.

---

## 5. Atomik Commit Kuralı (Atomic Commits)

- **Monolitik Commit Yasak:** Alakasız modülleri (UI payload + stdio RPC + docs) tek commit içine yığmak yasaktır.
- **Mantıksal Adım Sıralaması:**
  1. `feat(quota): add force_refresh flag to ConnectRPC client`
  2. `feat(ui): send forceRefresh payload on badge click`
  3. `style(ui): add 350ms blue pulse feedback on successful refresh`
  4. `docs(readme): document forceRefresh behavior`

---

## 6. Pre-Commit / Pre-Push Hijyeni

Commit veya push öncesi zorunlu 4 filtre:

1. **Secret & Key Taraması:** `.env`, API token, bot token veya SSH key depoya ASLA eklenemez.
2. **Kişisel Veri (PII) Hijyeni:** Telefon, raw kullanıcı ID'si, yerel IP/SSID ve şifreler depodan temizlenmelidir.
3. **Çöp Dosya Temizliği:** `__pycache__`, derleme çıktıları, `*.lock` ve işletim sistemi artıkları `.gitignore` ile engellenmelidir (`make delCache`).
4. **Doğrulama Şartı:** `make test` kontrolü geçmeden (Exit code: 0) commit atılamaz.
