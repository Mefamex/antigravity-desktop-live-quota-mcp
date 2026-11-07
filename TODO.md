# TODO — antigravity-desktop-live-quota-mcp

> **Bağlam ve Amaç:**
> Antigravity Desktop canlı kota göstergesi ve MCP sunucusunun kullanıcı geri bildirimleri doğrultusunda filtrelenmiş ve önceliklendirilmiş geliştirme listesi.

---

## 🚀 Aktif Geliştirme Sırası (Active Sprint)

- [x] **1. Dinamik Kalan Süre Sayacı (Live Countdown Tags):**
  - Rozetteki statik `/w` ve `/5h` etiketleri yerine `resetTime` verisinden hesaplanan kalan süre gösterilecek.
  - 5 saatlik kotalar için format: `1:20h` (1 saat 20 dakika formatında).
  - Haftalık kotalar için format: `3.5d` (gün cinsinden tek ondalıklı format).
  - Süre dolmuş veya hazırsa: `0m` veya `0d`.

- [x] **2. Aktif Model Vurgusu (Active Model Accent Highlight):**
  - Antigravity arayüzündeki aktif seçili modeli (`Select model` butonu) DOM üzerinden okuma.
  - O an aktif olan model grubunun (`⚡G`, `Ar` veya `C`) rozet etiketini dikkat çekici parlak/vurgulu bir renk (örneğin neon cyan/mavi veya temaya uygun parlak vurgu) ile öne çıkarma.
  - Pasif modeller standart yumuşak tonda kalacak.

- [x] **3. Yapılandırılabilir Kritik Eşik Nabız Uyarısı (Subtle Pulse Alert):**
  - Kota belirlenen kritik seviyenin altına indiğinde rozet çerçevesinde veya arka planında dikkat dağıtmayan zarif bir CSS nabız (pulse glow) efekti.
  - Kritik eşik yüzdesi `config.py` içerisinde `PULSE_ALERT_THRESHOLD_PCT` (varsayılan: %15 veya %20) olarak tanımlanacak ve ortam değişkeni (`AGY_PULSE_THRESHOLD_PCT`) ile ezilebilecek.

---

## 🔮 Gelecek Yol Haritası (Future Backlog)

- [ ] **Tüketim Hızı & Erime Tahmini (Burn-Rate Analytics):**
  - Oturum bazlı kota düşüş hızını hesaplayarak tahmini tükenme süresini modelleme (ilerleyen sürümlerde değerlendirilecek).

- [ ] **Tek Tıkla Brain / Scratch Temizliği:**
  - `~/.gemini/antigravity/brain/...` altındaki geçici veya eski scratch kalıntılarını arayüzden veya araçtan temizleme mekanizması (ihtiyaç halinde ele alınacak).

---

## ❌ İptal Edilen / Kapsam Dışı Bırakılanlar (Rejected)

- ~~**Rozete Tıklayınca Hızlı Menü (Quick Switcher Dropdown):**~~ Basitlik ve kompaktlık ilkesi gereği iptal edildi; tıklama sadece yenileme yapmaya devam edecek.
- ~~**Oturum Token Sayacı:**~~ Üst bar alanını doldurmamak adına iptal edildi.
- ~~**Bağlam Penceresi (Context Window) Barı:**~~ Odak dağıtmamak adına iptal edildi.
- ~~**Git Durumu & Değişen Dosya Sayacı:**~~ Üst barı gereksiz doldurmamak adına iptal edildi.
- ~~**Ajan Çalışma Durumu (Agent State Spinner):**~~ Gerek görülmediği için iptal edildi.
