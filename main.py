#!/usr/bin/env python3
"""
antigravity-quota-mcp — Main Entry Point (main.py)

Usage Modes:
1. MCP Server Mode (Default — invoked by `mcp_config.json`):
   $ python3 -B main.py
   - Starts a background UI Watcher guarded by `LeaderLock` (`fcntl.flock`).
   - Runs a zero-dependency JSON-RPC 2.0 MCP Stdio server on the main thread.

2. CLI Diagnostics and Manual Control Modes:
   $ python3 -B main.py --status     # Prints live quota and server/lock status
   $ python3 -B main.py --inject     # Performs a one-shot UI badge injection and exits
"""

from __future__ import annotations

import sys

# System hygiene: prevent creation of __pycache__ directories
sys.dont_write_bytecode = True

import argparse
import json
import signal
from typing import Any

from src.discovery import diagnose_cdp_status, discover_cdp_page_targets, discover_language_servers
from src.lock import LeaderLock
from src.logger import get_logger
from src.mcp_stdio import run_stdio_server
from src.notifier import is_notify_send_available, send_desktop_notification
from src.quota_client import fetch_live_quota
from src.scratch_cleaner import clean_scratch_cache
from src.ui_watcher import UIWatcherThread, inject_into_all_windows
from src.windows_setup import enable_cdp_windows

log = get_logger("main")


def _run_cli_status() -> int:
    """Prints a system and quota summary when invoked from the terminal with `--status`."""
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
        "cdp_diagnostics": diagnose_cdp_status(),
        "active_ui_leader_pid": holder,
        "quota_details": report.to_dict() if report.ok else {"error": report.error},
    }
    info["quota_details"].pop("raw_response", None)
    sys.stdout.write(json.dumps(info, ensure_ascii=False, indent=2) + "\n")
    return 0 if report.ok else 1


def _run_cli_inject() -> int:
    """Injects the badge into open windows when invoked from the terminal with `--inject`."""
    res = inject_into_all_windows(force=True)
    sys.stdout.write(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
    return 0 if res.get("ok") else 1


def _run_cli_clean_scratch(dry_run: bool = False, hours: float = 0.0) -> int:
    """Cleans brain scratch directories when invoked from the terminal with `--clean-scratch`."""
    res = clean_scratch_cache(older_than_hours=hours, dry_run=dry_run)
    sys.stdout.write(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
    return 0 if res.get("ok") else 1


def _run_cli_test_notify() -> int:
    """Sends a test desktop notification when invoked from the terminal with `--test-notify`."""
    if not is_notify_send_available():
        sys.stderr.write("[ERROR] `notify-send` was not found on your system (libnotify is not installed).\n")
        return 1

    ok = send_desktop_notification(
        title="⚡ Antigravity Live Quota Alert (Test)",
        message="Desktop notification system is working properly! You will be notified immediately at critical quota thresholds.",
        urgency="normal",
        icon="dialog-information",
    )
    res = {"ok": ok, "message": "Test notification sent." if ok else "Failed to send notification."}
    sys.stdout.write(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
    return 0 if ok else 1


def _run_cli_enable_cdp_windows() -> int:
    """Patches Windows Antigravity Desktop `.lnk` shortcuts with `--remote-debugging-port=0`."""
    res = enable_cdp_windows()
    sys.stdout.write(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
    return 0 if res.get("ok") else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Antigravity Desktop Live Quota Indicator and MCP Server"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show live quota and process/window status as JSON and exit.",
    )
    parser.add_argument(
        "--inject",
        action="store_true",
        help="Perform a one-shot badge injection into open Antigravity Desktop windows.",
    )
    parser.add_argument(
        "--clean-scratch",
        action="store_true",
        help="Clean Antigravity brain scratch/ temporary files.",
    )
    parser.add_argument(
        "--test-notify",
        action="store_true",
        help="Send a sample test notification to the desktop.",
    )
    parser.add_argument(
        "--enable-cdp-windows",
        action="store_true",
        help="Patch Windows Antigravity Desktop shortcuts (.lnk) with --remote-debugging-port=0.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report files and sizes to be cleaned without deleting anything.",
    )
    parser.add_argument(
        "--older-than-hours",
        type=float,
        default=0.0,
        help="Only clean scratch files older than this many hours (default: 0 = all).",
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

    if args.enable_cdp_windows:
        return _run_cli_enable_cdp_windows()

    # Default: MCP Stdio Server + Background UI Watcher with Leader Election
    leader_lock = LeaderLock()
    watcher = UIWatcherThread(lock=leader_lock)

    def _graceful_shutdown(signum: int, _frame: Any) -> None:
        log.info(f"Signal received ({signum}), shutting down cleanly...")
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
