# antigravity-desktop-live-quota-mcp

|              |                                                               |
| ------------ | ------------------------------------------------------------- |
| **Author**   | [Mefamex (Mehmet Akif Akkoç)](https://github.com/Mefamex)      |
| **Website**  | [https://www.mefamex.com](https://www.mefamex.com)            |
| **License**  | MIT                                                           |
| **Created**  | 2026-11-07                                                    |
| **Updated**  | 2026-11-08                                                    |
| **Stack**    | Python ≥ 3.10 (Sıfır Harici Bağımlılık / Pure Python Stdlib)  |
| **Platform** | Linux (Arch Linux, KDE Plasma 6, Wayland, X11)                |
| **Status**   | ✅ Production Ready                                            |

Google Antigravity Desktop (2.0) uygulamasında menüler altında gizli kalan canlı yapay zekâ model kotalarını, sıfırlanma geri sayımlarını ve aktif seçili modeli doğrudan pencerenin üst başlık çubuğuna (`[data-testid="title-menu-bar"]`) enjekte eden, sıfır bağımlılıklı hafif bir Model Context Protocol (MCP) sunucusudur. Harici bir sistem servisi veya paket yöneticisi yükü getirmeden yapay zekâ ajanlarına anlık kota telemetrisi sağlar.

---

## 1. Mimari ve Görsel Önizleme (Architecture & Preview)

### Sistem Veri Akış Şeması

```text
[ Antigravity Desktop Window ]
         │
         ├── DevToolsActivePort ──> [ discovery.py ] ──> [ cdp_client.py (RFC-6455) ]
         │                                                      │
         └── language_server   ──> [ quota_client.py ] ────────┴──> [ title-menu-bar ]
              (ConnectRPC)           (forceRefresh=true)               (Canlı Rozet)
```

### Arayüz Önizlemesi

<p align="center">
  <img src="assets/preview.png" alt="Antigravity Desktop Live Quota Badge" width="100%">
</p>

### Kritik Mimari Metrikleri

- **Soğuk Başlangıç Gecikmesi:** `68.0 ms — 80.3 ms` (Resmi Python MCP SDK'sına göre ~6 kat daha hızlı).
- **Bellek Tüketimi:** `~9 — 12 MB RAM` (Ekstra runtime veya sanal ortam yükü yoktur).
- **Harici Bağımlılık:** `0` (Yalnızca Python standart kütüphanesi: `socket`, `fcntl`, `struct`, `urllib`).
- **Arayüz Etki Alanı:** `~400 px` genişlik, `24 px` yükseklik (Başlık çubuğu kontrollerini sıkıştırmaz).

---

## 2. Belge Haritası (Repository Doc Map)

| Belge | Amacı ve Sorumluluğu |
| :--- | :--- |
| [`README.md`](./README.md) | Proje vitrini, mimari detaylar ve operasyonel kullanım kılavuzu |
| [`NOTES.md`](./NOTES.md) | Dahili teknik bellek, elenen yöntemler, sistem kısıtları ve Git referansı |
| [`TODO.md`](./TODO.md) | 5 seviyeli görev takibi, aktif sprint ve gelecek yol haritası |
| [`TODO.DONE.md`](./TODO.DONE.md) | Tamamlanan ve doğrulanan adımların ters kronolojik teknik günlüğü |
| [`config.py`](./config.py) | 3 katmanlı ayar motoru (`Ortam Değişkeni > config.py > Varsayılanlar`) |
| [`Makefile`](./Makefile) | Marmelab self-documenting yaşam döngüsü yöneticisi (6 zorunlu hedef + testler) |
| [`install.sh`](./install.sh) | Tek komutla `mcp_config.json` kaydı ve otomatik enjeksiyon betiği |

---

## 3. Temel Yetenekler ve Özellikler (Key Features)

* **5 Kota Türünün Tam Entegrasyonu:** `⚡G` (Gemini Flash/Pro 5h ve haftalık), `Ar` (Gemini 4 Argon haftalık) ve `C` (Claude/GPT 5h ve haftalık) kotalarını eşzamanlı izler.
* **Dinamik Kalan Süre Sayacı:** Statik etiketler yerine `resetTime` verisinden canlı hesaplanan geri sayımları gösterir (`0:50h`, `6.8d`, `7.0d`). Yerel DOM döngüsü (5 sn) ağ trafiği üretmeden süreyi akıtır.
* **Aktif Model Vurgusu:** Sohbet oturumunda kullanılan modele göre ilgili etiketi (`⚡G:`, `Ar:`, `C:`) parlak arka plan kapsülü ve hafif ışıltı ile görsel olarak öne çıkarır.
* **Anında Zorlamalı Bulut Yenilemesi:** Rozete tıklandığında `{ forceRefresh: true }` parametresi gönderilerek yerel dil sunucusunun önbelleği (`cache.ClearAndRefresh`) temizlenir; güncel veri Google bulutundan anında çekilir.
* **Çift Katmanlı Çakışma Koruması:** Linux çekirdek kilidi (`fcntl.flock`) ile birden fazla pencere/CLI açıldığında tek bir `LEADER` belirlenir. Diğer süreçler `STANDBY` modunda bekler; lider kapanırsa otomatik devir (failover) gerçekleşir.
* **Adaptif ve Responsive Stil:** HiDPI ve fractional scaling ekranlar için `clamp(6px, 1vw, 12px)` ve `flex-shrink: 0` CSS kuralları ile pencere genişliğine uyum sağlar.
* **Tüketim Hızı & Erime Tahmini (Burn-Rate Analytics):** Dakika başına kota düşüş hızını (`% / saat`) hesaplayarak 5 saatlik kota için tahmini tükenme süresini (`ETA: ~X dk`) tooltip üzerinde anlık modeller.
* **Kritik Kota & Yenilenme Masaüstü Bildirimleri:** Kota kritik eşiğe (`<= %15`) düştüğünde veya sayaç sıfırlanıp yenilendiğinde Linux masaüstüne (`notify-send`) 30 dk anti-spam korumalı yerel bildirim gönderir.
* **Tek Tıkla Scratch Temizliği:** Antigravity brain dizininde biriken geçici oturum kalıntılarını güvenle temizleyen `clean_scratch_cache` aracı ve `make clean-scratch` komutu.

---

## 4. Teknoloji Yığını ve Gereksinimler (Tech Stack & Prerequisites)

- **Çalışma Ortamı:** Linux (Arch Linux, Ubuntu, Debian, Fedora vb. — Wayland veya X11).
- **Yorumlayıcı:** Python ≥ 3.10 (Sanal ortam gerektirmez, sistem Python'u ile çalışır).
- **Hedef Uygulama:** Google Antigravity Desktop (2.0) sürümü.
- **Harici Bağımlılıklar:** `dependencies = []` (Harici hiçbir `pip` veya `npm` paketi gerekmez).

---

## 5. Kurulum ve Hızlı Başlangıç (Installation & Quick Start)

### 1. Depoyu Klonlayın ve Dizine Girin
```bash
# Depoyu yerel diskinize indirin
cd /mnt/DiskD/SOFTWARE/Github-repos/antigravity-desktop-live-quota-mcp
```

### 2. Tek Komutla Otomatik Kurun
```bash
# MCP kaydını yapar, izinleri ayarlar ve açık pencereye rozeti enjekte eder
make install
```

### 3. Manuel Kurulum Alternatifi
Dilerseniz `~/.gemini/config/mcp_config.json` dosyası içerisindeki `"mcpServers"` bloğuna doğrudan şu girdiyi ekleyebilirsiniz:

```json
"antigravity-desktop-live-quota-mcp": {
  "command": "python3",
  "args": [
    "-B",
    "/mnt/DiskD/SOFTWARE/Github-repos/antigravity-desktop-live-quota-mcp/main.py"
  ],
  "disabled": false
}
```

---

## 6. Yapılandırma (Configuration Guide)

[`config.py`](file:///mnt/DiskD/SOFTWARE/Github-repos/antigravity-desktop-live-quota-mcp/config.py) dosyası 3 katmanlı ayar önceliği uygular:
```text
Ortam Değişkeni (ENV)  ──>  config.py Sabitleri  ──>  Kod İçi Güvenli Varsayılanlar
```

Hassas veriler veya geçici ayarlar kod değiştirilmeden ortam değişkenleri üzerinden ezilebilir:

| Değişken | Varsayılan | Açıklama |
| :--- | :--- | :--- |
| `AGY_BROWSER_FETCH_MS` | `30000` | Tarayıcı JS döngüsünün yerel kota sorgulama periyodu (milisaniye) |
| `AGY_WATCHER_CHECK_SEC` | `8` | Lider sürecin pencere varlığını ve rozet durumunu denetleme sıklığı (saniye) |
| `AGY_THRESHOLD_HIGH` | `50` | Yeşil gösterge eşik yüzdesi (`> %50`) |
| `AGY_THRESHOLD_LOW` | `20` | Sarı gösterge eşik yüzdesi (`> %20`, altı kırmızı) |
| `AGY_PULSE_ALERT_THRESHOLD_PCT` | `15` | Kritik kota kırmızı nabız animasyonu eşiği (`≤ %15`) |
| `AGY_ENABLE_PULSE_ALERT` | `true` | Nabız animasyonunu etkinleştirme bayrağı |

---

## 7. Kullanım ve Komutlar (Usage & CLI Reference)

### 7.1. Terminal ve Makefile Komutları

```bash
# Kullanılabilir tüm hedefleri renkli ve açıklamalı listeler
make help

# Canlı kota raporunu ve açık pencereleri JSON olarak terminale basar
make status

# Açık olan Antigravity Desktop penceresine rozeti anında zorla enjekte eder
make inject

# Masaüstüne örnek bir kritik kota test bildirimi gönderir
make test-notify

# Soğuk başlangıç, liderlik kilidi, failover ve enjeksiyon testlerini koşturur
make test

# Commit/Push öncesi derleme kalıntılarını temizler ve test zincirini doğrular
make verify

# Ortamdaki bytecode ve önbellek kalıntılarını siler
make clean

# Antigravity brain scratch/ geçici oturum dosyalarını temizler
make clean-scratch
```

### 7.2. Sunulan Model Context Protocol (MCP) Araçları

Yapay zekâ ajanları (`gemini`, `claude`, `codex`) stdio üzerinden bu araçları çağırabilir:

| Araç Adı | Parametreler | Görev ve Açıklama |
| :--- | :--- | :--- |
| `get_quota_status` | `include_raw: bool`<br>`force_refresh: bool` | Gemini, Claude/GPT ve Argon kota yüzdelerini, kalan sıfırlanma sürelerini ve ham language_server çıktısını döndürür. |
| `reinject_badge` | `force: bool` | Antigravity Desktop penceresindeki rozeti yeniden oluşturur ve tıklandığı andaki verilerle tazeler. |
| `get_instance_status` | *(yok)* | Sürecin PID numarasını, `LEADER` / `STANDBY` rolünü ve aktif kilit dosya yolunu bildirir. |
| `clean_scratch_cache` | `dry_run: bool`<br>`older_than_hours: float` | Antigravity brain altındaki geçici oturum scratch dosyalarını güvenle temizler. |

---

## 8. Güvenlik, Gizlilik ve Kırmızı Çizgiler (Safety & Privacy)

- **Sıfır Dış Ağ Trafiği:** Bu sunucu ve enjekte edilen tarayıcı scripti, hiçbir harici sunucuya veya üçüncü taraf analitik servisine veri göndermez.
- **Sadece Yerel İletişim (Localhost-Only):** Tüm iletişim yerel makinedeki `127.0.0.1` soketleri ve `language_server` süreciyle sınırlıdır.
- **Stdout Akış İzolasyonu:** JSON-RPC 2.0 protokol bütünlüğünü bozmamak için `stdout` akışına kesinlikle log basılmaz; tüm operasyonel loglar `sys.stderr` üzerinden yürütülür.
- **Sıfır İkili Dosya Değişikliği:** Antigravity Desktop ikili dosyalarına (`binary patch`) dokunulmaz; yalnızca Chrome DevTools Protocol (`Runtime.evaluate`) üzerinden arayüz manipülasyonu yapılır.

---

## 9. Lisans ve Katkı (License)

Bu proje **MIT Lisansı** altında açık kaynak olarak yayınlanmıştır.  
Tüm hakları saklıdır © 2026 [Mefamex](https://www.mefamex.com).
