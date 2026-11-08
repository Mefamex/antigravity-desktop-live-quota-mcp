#!/usr/bin/env python3
"""
antigravity-quota-mcp — Ana Giriş Noktası (main.py)

Kullanım Modları:
1. MCP Sunucu Modu (Varsayılan — `mcp_config.json` tarafından çağrılır):
   $ python3 -B main.py
   - Arka planda `LeaderLock` (`fcntl.flock`) korumalı UI Watcher başlatır.
   - Ana iş parçacığında sıfır bağımlılıklı JSON-RPC 2.0 MCP Stdio sunucusunu çalıştırır.

2. CLI Tanılama ve Manuel Kontrol Modları:
   $ python3 -B main.py --status     # Canlı kotayı ve sunucu/kilit durumunu ekrana basar
   $ python3 -B main.py --inject     # Tek seferlik UI rozet enjeksiyonu yapar ve çıkar
"""

from __future__ import annotations

import sys

# Sistem hijyeni: __pycache__ klasörlerinin oluşmasını engelle
sys.dont_write_bytecode = True

import argparse
import json
import signal
from typing import Any

from src.discovery import discover_cdp_page_targets, discover_language_servers
from src.lock import LeaderLock
from src.logger import get_logger
from src.mcp_stdio import run_stdio_server
from src.notifier import is_notify_send_available, send_desktop_notification
from src.quota_client import fetch_live_quota
from src.scratch_cleaner import clean_scratch_cache
from src.ui_watcher import UIWatcherThread, inject_into_all_windows

log = get_logger("main")


def _run_cli_status() -> int:
    """Terminalden `--status` ile çağrıldığında sistem ve kota özetini yazdırır."""
    endpoints = discover_language_servers()
    pages = discover_cdp_page_targets()
    report = fetch_live_quota()
    lock = LeaderLock()
    holder = lock.read_holder_pid()

    info: dict[str, Any] = {
        "quota_summary": report.format_compact(),
        "language_servers": [
            {"pid": e.pid, "ports": e.ports} for e in endpoints
        ],
        "cdp_windows": [
            {"id": p.get("id"), "title": p.get("title")} for p in pages
        ],
        "active_ui_leader_pid": holder,
        "quota_details": report.to_dict() if report.ok else {"error": report.error},
    }
    info["quota_details"].pop("raw_response", None)
    sys.stdout.write(json.dumps(info, ensure_ascii=False, indent=2) + "\n")
    return 0 if report.ok else 1


def _run_cli_inject() -> int:
    """Terminalden `--inject` ile çağrıldığında rozeti pencereye enjekte eder."""
    res = inject_into_all_windows(force=True)
    sys.stdout.write(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
    return 0 if res.get("ok") else 1


def _run_cli_clean_scratch(dry_run: bool = False, hours: float = 0.0) -> int:
    """Terminalden `--clean-scratch` ile çağrıldığında brain scratch dizinlerini temizler."""
    res = clean_scratch_cache(older_than_hours=hours, dry_run=dry_run)
    sys.stdout.write(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
    return 0 if res.get("ok") else 1


def _run_cli_test_notify() -> int:
    """Terminalden `--test-notify` ile çağrıldığında test masaüstü bildirimi gönderir."""
    if not is_notify_send_available():
        sys.stderr.write("[HATA] Sisteminizde `notify-send` bulunamadı (libnotify kurulu değil).\n")
        return 1

    ok = send_desktop_notification(
        title="⚡ Antigravity Canlı Kota Uyarısı (Test)",
        message="Masaüstü bildirim sistemi başarıyla çalışıyor! Kritik kota eşiklerinde anında haberdar edileceksiniz.",
        urgency="normal",
        icon="dialog-information",
    )
    res = {"ok": ok, "message": "Test bildirimi gönderildi." if ok else "Bildirim gönderilemedi."}
    sys.stdout.write(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Antigravity Desktop Canlı Kota Göstergesi ve MCP Sunucusu"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Canlı kota ve süreç/pencere durumunu JSON olarak gösterir ve çıkar.",
    )
    parser.add_argument(
        "--inject",
        action="store_true",
        help="Açık Antigravity Desktop penceresine rozeti tek seferlik enjekte eder.",
    )
    parser.add_argument(
        "--clean-scratch",
        action="store_true",
        help="Antigravity brain scratch/ geçici dosyalarını temizler.",
    )
    parser.add_argument(
        "--test-notify",
        action="store_true",
        help="Masaüstüne örnek bir test bildirimi gönderir.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Silme işlemi yapmadan temizlenecek dosya ve boyutları raporlar.",
    )
    parser.add_argument(
        "--older-than-hours",
        type=float,
        default=0.0,
        help="Kaç saatten eski scratch dosyalarının temizleneceği (varsayılan: 0 = tümü).",
    )
    args = parser.parse_args()

    if args.status:
        return _run_cli_status()

    if args.inject:
        return _run_cli_inject()

    if args.clean_scratch:
        return _run_cli_clean_scratch(dry_run=args.dry_run, hours=args.older_than_hours)

    if args.test_notify:
        return _run_cli_test_notify()

    # Varsayılan: MCP Stdio Sunucusu + Lider Seçimli Arka Plan UI İzleyicisi
    leader_lock = LeaderLock()
    watcher = UIWatcherThread(lock=leader_lock)

    def _graceful_shutdown(signum: int, _frame: Any) -> None:
        log.info(f"Sinyal alındı ({signum}), temiz çıkış yapılıyor...")
        watcher.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _graceful_shutdown)
    signal.signal(signal.SIGTERM, _graceful_shutdown)

    watcher.start()
    try:
        run_stdio_server(lock=leader_lock)
    finally:
        watcher.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
