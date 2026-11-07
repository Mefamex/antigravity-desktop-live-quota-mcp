"""
antigravity-quota-mcp — Merkezi Yapılandırma Modülü (config.py)

3 Katmanlı Ayar Önceliği:
1. Kod içi güvenli varsayılanlar (Bu dosyadaki sabitler)
2. Harici/Kullanıcı yapılandırması
3. Ortam değişkenleri (Environment Variable override — örn. AGY_QUOTA_POLL_SEC=15)
"""

from __future__ import annotations

import os
from pathlib import Path


def _env_int(key: str, default: int) -> int:
    val = os.environ.get(key)
    if val is not None and val.strip().isdigit():
        return int(val.strip())
    return default


def _env_bool(key: str, default: bool) -> bool:
    val = os.environ.get(key)
    if val is not None:
        return val.strip().lower() in ("1", "true", "yes", "on")
    return default


# ============================================================================
# 1. SUNUCU KİMLİK BİLGİLERİ
# ============================================================================
SERVER_NAME: str = "antigravity-desktop-live-quota-mcp"
SERVER_VERSION: str = "1.0.0"
PROTOCOL_VERSION: str = "2025-11-25"

# ============================================================================
# 2. DOSYA VE DİZİN YOLLARI
# ============================================================================
HOME_DIR: Path = Path.home()

# Antigravity Desktop'ın aktif Chrome DevTools portunu yazdığı dosya
DEVTOOLS_PORT_FILE: Path = Path(
    os.environ.get(
        "AGY_DEVTOOLS_PORT_FILE",
        str(HOME_DIR / ".config" / "Antigravity" / "DevToolsActivePort"),
    )
)

# Çoklu örnek (multi-instance) çalışmada sadece tek bir sürecin UI enjeksiyonu
# yapmasını sağlayan çekirdek (kernel) kilit dosyası (tmpfs üzerinde tutulur)
_runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
LOCK_FILE_PATH: Path = Path(_runtime_dir) / "antigravity-desktop-live-quota.lock"

# ============================================================================
# 3. ZAMANLAYICI VE YOKLAMA (POLLING) AYARLARI
# ============================================================================
# Pencere içindeki JS döngüsünün yerel language_server'dan kota çekme sıklığı (ms)
BROWSER_FETCH_INTERVAL_MS: int = _env_int("AGY_BROWSER_FETCH_MS", 30_000)

# Lider MCP sürecinin pencereyi (Ctrl+R veya yeni pencere açılmasına karşı) kontrol sıklığı (sn)
WATCHER_CHECK_INTERVAL_SEC: int = _env_int("AGY_WATCHER_CHECK_SEC", 8)

# Yerel HTTP ve WebSocket bağlantıları için zaman aşımı süresi (sn)
NETWORK_TIMEOUT_SEC: float = float(_env_int("AGY_NETWORK_TIMEOUT_SEC", 2))

# ============================================================================
# 4. GÖRSEL ROZET (UI BADGE) VE RENK EŞİKLERİ
# ============================================================================
UI_Injection_Enabled: bool = _env_bool("AGY_UI_INJECTION_ENABLED", True)

# DOM eleman kimliği ve hedef üst çubuk seçicisi
BADGE_ELEMENT_ID: str = "agy-live-quota-pill"
TARGET_BAR_SELECTOR: str = '[data-testid="title-menu-bar"]'

# Kalan yüzdeye göre renk eşikleri
THRESHOLD_HIGH_PCT: int = _env_int("AGY_THRESHOLD_HIGH", 50)  # > %50 Yeşil
THRESHOLD_LOW_PCT: int = _env_int("AGY_THRESHOLD_LOW", 20)    # > %20 Sarı, altı Kırmızı

# Kritik kota eşiğinde nabız (subtle pulse alert) uyarısı
PULSE_ALERT_THRESHOLD_PCT: int = _env_int("AGY_PULSE_ALERT_THRESHOLD_PCT", 15)  # <= %15 Nabız uyarısı
ENABLE_PULSE_ALERT: bool = _env_bool("AGY_ENABLE_PULSE_ALERT", True)

COLOR_HIGH: str = "#4ade80"   # Yeşil
COLOR_MEDIUM: str = "#fbbf24" # Sarı / Turuncu
COLOR_LOW: str = "#f87171"    # Kırmızı

# ============================================================================
# 5. LOGLAMA AYARLARI
# ============================================================================
# Not: MCP stdio protokolünde stdout SADECE JSON-RPC mesajları içindir.
# Tüm loglar kesinlikle stderr'e yazılır.
LOG_LEVEL: str = os.environ.get("AGY_LOG_LEVEL", "INFO").upper()
