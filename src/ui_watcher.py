"""
Arka Plan UI İzleyici ve Enjektör Modülü (src/ui_watcher.py)

Çalışma Mantığı:
1. `LeaderLock` (`fcntl.flock`) ile liderlik kontrolü yapar.
   - Eğer sistemde çalışan başka bir `antigravity-quota-mcp` süreci zaten liderse,
     bu süreç **YEDEK (Standby)** modda bekler ve CDP soketlerine dokunmaz.
   - Lider olan süreç ise açık Antigravity Desktop pencerelerini kontrol eder;
     rozet henüz eklenmemişse (veya `Ctrl+R` ile sayfa yenilenmişse) rozeti
     pencereye enjekte eder.
"""

from __future__ import annotations

import threading
from typing import Any

import config
from src.cdp_client import cdp_evaluate
from src.discovery import discover_cdp_page_targets
from src.lock import LeaderLock
from src.logger import get_logger
from src.notifier import QuotaNotifier
from src.quota_client import fetch_live_quota
from src.ui_payload import build_check_badge_js, build_injection_js

log = get_logger("watcher")


def inject_into_all_windows(force: bool = False) -> dict[str, Any]:
    """
    Açık olan tüm Antigravity Desktop pencerelerini tarar ve rozeti enjekte eder.
    `force=False` ise yalnızca rozeti eksik olan pencerelere enjeksiyon yapar.
    """
    pages = discover_cdp_page_targets()
    if not pages:
        return {
            "ok": False,
            "injected_count": 0,
            "already_active_count": 0,
            "message": "Açık Antigravity Desktop penceresi (CDP hedefi) bulunamadı.",
        }

    check_js = build_check_badge_js()
    inject_js = build_injection_js()

    injected = 0
    already_active = 0
    errors: list[str] = []

    for page in pages:
        ws_url = str(page.get("webSocketDebuggerUrl", ""))
        title = str(page.get("title", "Antigravity"))
        try:
            if not force:
                chk = cdp_evaluate(ws_url, check_js)
                is_present = (
                    chk.get("result", {}).get("result", {}).get("value") is True
                )
                if is_present:
                    already_active += 1
                    continue

            res = cdp_evaluate(ws_url, inject_js)
            val = res.get("result", {}).get("result", {}).get("value")
            if val == "OK":
                injected += 1
                log.info(f"Canlı kota rozeti enjekte edildi -> '{title}'")
            else:
                errors.append(f"{title}: {val}")
        except Exception as exc:
            errors.append(f"{title}: {exc}")

    return {
        "ok": (injected > 0 or already_active > 0),
        "injected_count": injected,
        "already_active_count": already_active,
        "total_pages": len(pages),
        "errors": errors,
    }


class UIWatcherThread(threading.Thread):
    """
    Lider seçimi (`LeaderLock`) destekli arka plan izleyici iş parçacığı.
    `daemon=True` olarak çalışır; ana MCP süreci kapandığında anında sonlanır.
    """

    def __init__(self, lock: LeaderLock) -> None:
        super().__init__(name="agy-ui-watcher", daemon=True)
        self.lock = lock
        self._stop_event = threading.Event()
        self._was_leader = False
        self._notifier = QuotaNotifier()

    def stop(self) -> None:
        """İzleyici döngüsünü durdurur ve kilidi serbest bırakır."""
        self._stop_event.set()
        self.lock.release()

    def run(self) -> None:
        if not config.UI_Injection_Enabled:
            log.info("UI enjeksiyonu yapılandırma ile devre dışı bırakıldı.")
            return

        while not self._stop_event.is_set():
            if self.lock.try_acquire():
                if not self._was_leader:
                    log.info("Bu süreç UI Lideri olarak aktifleşti.")
                    self._was_leader = True
                try:
                    inject_into_all_windows(force=False)
                except Exception as exc:
                    log.debug(f"UI kontrol döngüsü hatası: {exc}")

                # Lider iken masaüstü bildirimlerini kontrol et
                if config.ENABLE_DESKTOP_NOTIFICATIONS:
                    try:
                        live_quota = fetch_live_quota(force_refresh=True)
                        if live_quota.ok:
                            self._notifier.check_and_notify(live_quota, is_leader=True)
                    except Exception as exc:
                        log.debug(f"Bildirim kontrol hatası: {exc}")
            else:
                if self._was_leader:
                    log.info("UI Liderliği başka bir sürece geçti, yedek moda geçildi.")
                    self._was_leader = False

            self._stop_event.wait(timeout=float(config.WATCHER_CHECK_INTERVAL_SEC))
