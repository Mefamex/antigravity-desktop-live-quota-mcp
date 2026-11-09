# TODO — antigravity-desktop-live-quota-mcp

> **Bağlam ve Amaç (Context Anchor):**
> Google Antigravity Desktop (2.0) uygulamasında menüler altında gizli kalan canlı AI model kotalarını, kalan geri sayım sürelerini ve aktif konuşulan modeli sıfır bağımlılıklı Python MCP sunucusuyla üst başlık çubuğuna (`[data-testid="title-menu-bar"]`) enjekte eden ve yapay zekâ ajanlarına anlık kota sorgulama araçları sağlayan sistemin geliştirme ve takip listesi.

---

## 📋 Ajan & Geliştirici Kuralları

- **Sıralı İlerleme:** Aktif sprint listesini yukarıdan aşağıya takip et; kapsama girmeyen yan işlere dallanma.
- **Tahmin Yasak:** Varsayımla koda girme; mimari kısıtları ve gerekçeleri [`NOTES.md`](./NOTES.md) dosyasına sabitle.
- **Kırmızı Çizgiler:** `sudo`, veri silme (`rm`), kontrolsüz refaktör veya `git push` izinsiz çalıştırılamaz.
- **Arşivleme Kuralı:** Biten madde `TODO.md`'den çıkarılır; zaman damgası ve doğrulama çıktısıyla [`TODO.DONE.md`](./TODO.DONE.md)'nin **en üstüne** eklenir.
- **Doğrulama Şartı:** `make test` veya canlı çalışma kanıtı (Exit code: 0) sunulmadan görev tamamlanamaz.

---

## 🚀 1. Aktif Sprint (Active Sprint)
*Şu anda tüm çekirdek aktif sprint maddeleri tamamlanmış ve `TODO.DONE.md`'ye aktarılmıştır.*

- [x] **Dinamik Kalan Süre Sayacı:** 5 saatlik kotalar için `0:50h` ve haftalık kotalar için `6.8d` / `7.0d` canlı formatı.
- [x] **Aktif Model Vurgusu:** Açık sohbetteki modele göre ilgili etiketin (`⚡G:`) parlayıp öne çıkarılması.
- [x] **Kritik Eşik Nabız Uyarısı:** Kota `%15`'in altına indiğinde devreye giren dikkat dağıtmayan CSS nabız efekti.
- [x] **Anında Zorlamalı Bulut Yenilemesi:** Tıklamada `{ forceRefresh: true }` ile language_server önbellek baypası.
- [x] **Adaptif & İri Yüzde Tasarımı:** `%91` gibi kota yüzdelerinin `12px bold` yapılması ve HiDPI adaptifliği.

---

## 📌 2. Yüksek Öncelik (High Priority)
*Aktif sprint biter bitmez sırada bekleyen kritik maddeler:*

*(Şu anda aktif bekleyen yüksek öncelikli hata veya görev bulunmamaktadır. Tüm maddeler tamamlanıp TODO.DONE.md'ye aktarılmıştır.)*

---

## 🛠️ 3. Backlog (Medium & Low Priority)
*Sistemi tamamlayıcı geliştirmeler:*

- [ ] **Kullanıcı Geri Bildirimlerine Göre İnce Ayarlar:** Canlı kullanımda ortaya çıkabilecek font/renk talepleri.

---

## 🔮 4. Gelecek Yol Haritası (Future Roadmap)
*İleride değerlendirilecek uzun vadeli fikir ve genişletmeler:*

- [x] **Tüketim Hızı & Erime Tahmini (Burn-Rate Analytics):**
  - Oturum bazlı dakika başına kota düşüş hızını hesaplayarak tahmini tükenme süresini rozet tooltip'inde canlı gösterme (tamamlandı).
- [x] **Tek Tıkla Brain / Scratch Temizliği (`clean_scratch_cache`):**
  - `~/.gemini/antigravity/brain/...` altındaki geçici scratch kalıntılarını temizleyen güvenli MCP aracı, CLI bayrağı (`--clean-scratch`) ve Makefile hedefi (`make clean-scratch`) (tamamlandı).

---

## ❌ 5. İptal / Kapsam Dışı (Rejected)
*Tartışılmış ancak sadelik, arayüz ferahlığı ve mimari tercih gereği vazgeçilmiş kararlar (tekrar gündeme gelmemesi için gerekçesiyle tutulur):*

- ~~**Rozete Tıklayınca Hızlı Menü (Quick Switcher Dropdown):**~~ Basitlik ve kompaktlık ilkesi gereği iptal edildi; tıklama sadece anlık zorlamalı bulut yenilemesi yapmaya odaklandı.
- ~~**Oturum Token Sayacı:**~~ Üst bar alanını gereksiz doldurmamak adına iptal edildi.
- ~~**Bağlam Penceresi (Context Window) Barı:**~~ Odak dağıtmamak adına iptal edildi.
- ~~**Git Durumu & Değişen Dosya Sayacı:**~~ Üst barı gereksiz doldurmamak adına iptal edildi.
- ~~**Ajan Çalışma Durumu (Agent State Spinner):**~~ Gerek görülmediği için iptal edildi.
