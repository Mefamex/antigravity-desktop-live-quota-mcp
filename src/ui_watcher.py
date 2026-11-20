"""
Background UI Watcher and Injector Module (src/ui_watcher.py)

How It Works:
1. Checks leadership using `LeaderLock` (`fcntl.flock`).
   - If another `antigravity-quota-mcp` process on the system is already the leader,
     this process stays in **STANDBY** mode and does not touch CDP sockets.
   - The leader process monitors open Antigravity Desktop windows; if the badge
     is not yet present (or the page was refreshed via `Ctrl+R`), it injects
     the badge into the window.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import config
from src.cdp_client import cdp_evaluate
from src.discovery import diagnose_cdp_status, discover_cdp_page_targets
from src.lock import LeaderLock
from src.logger import get_logger
from src.notifier import QuotaNotifier
from src.quota_client import fetch_live_quota
from src.ui_payload import build_check_badge_js, build_injection_js

log = get_logger("watcher")


def inject_into_all_windows(force: bool = False) -> dict[str, Any]:
    """
    Scans all open Antigravity Desktop windows and injects the badge.
    When `force=False`, only injects into windows where the badge is missing.
    """
    pages = discover_cdp_page_targets()
    if not pages:
        diag = diagnose_cdp_status()
        msg = diag.get("fix_hint") or "No open Antigravity Desktop window (CDP target) found."
        return {
            "ok": False,
            "injected_count": 0,
            "already_active_count": 0,
            "message": msg,
            "diagnostics": diag,
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
                log.info(f"Live quota badge injected -> '{title}'")
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
    Background watcher thread backed by leader election (`LeaderLock`).
    Runs with `daemon=True`; terminates immediately when the main MCP process exits.
    """

    def __init__(self, lock: LeaderLock) -> None:
        super().__init__(name="agy-ui-watcher", daemon=True)
        self.lock = lock
        self._stop_event = threading.Event()
        self._was_leader = False
        self._cdp_warning_logged = False
        self._last_notify_check_ts = 0.0
        self._notifier = QuotaNotifier()

    def stop(self) -> None:
        """Stops the watcher loop and releases the lock."""
        self._stop_event.set()
        self.lock.release()

    def run(self) -> None:
        if not config.UI_Injection_Enabled:
            log.info("UI injection is disabled by configuration.")
            return

        while not self._stop_event.is_set():
            if self.lock.try_acquire():
                if not self._was_leader:
                    log.info("This process has become active as the UI Leader.")
                    self._was_leader = True
                cdp_active = False
                try:
                    res = inject_into_all_windows(force=False)
                    cdp_active = bool(res.get("ok"))
                    if cdp_active:
                        self._cdp_warning_logged = False
                    elif (
                        res.get("diagnostics", {}).get("reason") == "cdp_disabled_in_antigravity_2_33"
                        and not self._cdp_warning_logged
                    ):
                        log.warning(res["message"])
                        self._cdp_warning_logged = True
                except Exception as exc:
                    log.debug(f"UI watch loop error: {exc}")

                # While acting as Leader, check desktop notifications (rate-limited);
                # when the UI badge is active (`cdp_active=True`), the local cache is
                # refreshed inside the page, avoiding duplicate cloud RPC calls.
                if config.ENABLE_DESKTOP_NOTIFICATIONS:
                    now = time.monotonic()
                    if (now - self._last_notify_check_ts) >= config.WATCHER_NOTIFY_INTERVAL_SEC:
                        self._last_notify_check_ts = now
                        try:
                            live_quota = fetch_live_quota(force_refresh=(not cdp_active))
                            if live_quota.ok:
                                self._notifier.check_and_notify(live_quota, is_leader=True)
                        except Exception as exc:
                            log.debug(f"Notification check error: {exc}")
            else:
                if self._was_leader:
                    log.info("UI Leadership moved to another process; switching to standby mode.")
                    self._was_leader = False

            self._stop_event.wait(timeout=float(config.WATCHER_CHECK_INTERVAL_SEC))
