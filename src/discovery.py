"""
Süreç ve Port Keşif Modülü (src/discovery.py)

Bu modül iki temel keşif görevini yerine getirir:
1. Çalışan Antigravity `language_server` sürecinin PID, `--csrf_token` ve
   dinlediği yerel TCP portlarını tespit eder.
2. `~/.config/Antigravity/DevToolsActivePort` dosyasını okuyarak aktif Electron
   penceresinin Chrome DevTools Protocol (CDP) WebSocket adreslerini bulur.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import config
from src.logger import get_logger
from src.models import LanguageServerEndpoint

log = get_logger("discovery")


def discover_language_servers() -> list[LanguageServerEndpoint]:
    """
    Sistemde çalışan `language_server` süreçlerini tarar ve `--csrf_token`
    parametresine sahip olanların PID, token ve port listesini döndürür.
    """
    endpoints: list[LanguageServerEndpoint] = []
    try:
        out = subprocess.check_output(
            ["pgrep", "-a", "language_server"],
            stderr=subprocess.DEVNULL,
            timeout=2.0,
        ).decode("utf-8", errors="ignore")
    except (subprocess.SubprocessError, OSError):
        return endpoints

    try:
        ss_out = subprocess.check_output(
            ["ss", "-tulpn"],
            stderr=subprocess.DEVNULL,
            timeout=2.0,
        ).decode("utf-8", errors="ignore")
    except (subprocess.SubprocessError, OSError):
        ss_out = ""

    # Önce Antigravity Desktop (`--subclient_type hub`) olan süreçlere öncelik ver
    lines = out.splitlines()
    lines.sort(key=lambda l: 0 if "--subclient_type hub" in l else 1)

    for line in lines:
        if "--csrf_token" not in line:
            continue
        parts = line.strip().split(maxsplit=1)
        if not parts or not parts[0].isdigit():
            continue

        pid = int(parts[0])
        m_token = re.search(r"--csrf_token[=\s]+([a-fA-F0-9\-]+)", line)
        if not m_token:
            continue
        csrf_token = m_token.group(1)

        ports: list[int] = []
        for sline in ss_out.splitlines():
            if f"pid={pid}," in sline and "LISTEN" in sline:
                m_port = re.search(r":(\d+)\s+", sline)
                if m_port:
                    port = int(m_port.group(1))
                    if port not in ports:
                        ports.append(port)

        if ports:
            endpoints.append(
                LanguageServerEndpoint(pid=pid, csrf_token=csrf_token, ports=ports)
            )

    return endpoints


def get_antigravity_desktop_process_info() -> dict[str, Any]:
    """
    Sistemde çalışan ana Antigravity Desktop Electron sürecini (/proc üzerinden)
    tespit eder ve `--remote-debugging-port` bayrağı durumunu döndürür.
    `language_server`, `antigravity-ide`, `python` ve `--type=` alt süreçlerini dışlar.
    """
    proc_root = Path("/proc")
    try:
        entries = list(proc_root.iterdir())
    except OSError:
        entries = []

    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            raw_cmd = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        if not raw_cmd:
            continue

        args = [a for a in raw_cmd.decode("utf-8", errors="ignore").split("\x00") if a]
        if not args:
            continue

        exe_name = Path(args[0]).name.lower()
        joined = " ".join(args)

        # Sadece ana Electron uygulaması (/opt/Antigravity/antigravity vb.)
        if exe_name != "antigravity" or "antigravity-ide" in args[0].lower():
            continue
        if "language_server" in joined or "python" in exe_name:
            continue
        if any(a.startswith("--type=") or a.startswith("--import=") for a in args[1:]):
            continue

        has_flag = any(
            a == "--remote-debugging-port" or a.startswith("--remote-debugging-port=")
            for a in args[1:]
        )
        explicit_port: int | None = None
        m_port = re.search(r"--remote-debugging-port[=\s]+(\d+)", joined)
        if m_port:
            port_val = int(m_port.group(1))
            if port_val > 0:
                explicit_port = port_val

        return {
            "running": True,
            "pid": pid,
            "has_remote_debugging_flag": has_flag,
            "explicit_debug_port": explicit_port,
        }

    return {
        "running": False,
        "pid": None,
        "has_remote_debugging_flag": False,
        "explicit_debug_port": None,
    }


def _resolve_cdp_port_and_file() -> tuple[int | None, Path, bool]:
    """
    Aktif CDP portunu, kullanılan port dosyasını ve dosyanın mevcut olup olmadığını
    çözümler. `DevToolsActivePort` yoksa açık `--remote-debugging-port=N` bayrağına
    bakar.
    """
    candidates: list[Path] = [config.DEVTOOLS_PORT_FILE]
    env_active = os.environ.get("AGY_BROWSER_ACTIVE_PORT_FILE")
    if env_active:
        env_path = Path(env_active)
        if env_path not in candidates:
            candidates.append(env_path)

    any_exists = False
    first_existing: Path | None = None

    for port_file in candidates:
        if not port_file.exists():
            continue
        any_exists = True
        if first_existing is None:
            first_existing = port_file
        try:
            lines = port_file.read_text(encoding="utf-8").strip().splitlines()
            if lines and lines[0].strip().isdigit():
                port_val = int(lines[0].strip())
                if port_val > 0:
                    return (port_val, port_file, True)
        except OSError:
            continue

    proc_info = get_antigravity_desktop_process_info()
    explicit_port = proc_info.get("explicit_debug_port")
    if isinstance(explicit_port, int) and explicit_port > 0:
        return (explicit_port, first_existing or config.DEVTOOLS_PORT_FILE, any_exists)

    return (None, first_existing or config.DEVTOOLS_PORT_FILE, any_exists)


def _fetch_cdp_targets_on_port(cdp_port: int) -> list[dict[str, Any]]:
    """Verilen yerel CDP portundan geçerli Antigravity pencere hedeflerini listeler."""
    url = f"http://127.0.0.1:{cdp_port}/json/list"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=config.NETWORK_TIMEOUT_SEC) as resp:
            targets = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception:
        return []

    valid_pages: list[dict[str, Any]] = []
    for t in targets:
        if t.get("type") != "page":
            continue
        page_url = str(t.get("url", ""))
        title = str(t.get("title", ""))
        ws_url = str(t.get("webSocketDebuggerUrl", ""))
        if not ws_url:
            continue
        # Sadece gerçek Antigravity uygulama pencerelerini seç (splash data: url'lerini atla)
        if page_url.startswith("http") or "Antigravity" in title:
            valid_pages.append(t)

    return valid_pages


def discover_cdp_page_targets() -> list[dict[str, Any]]:
    """
    `DevToolsActivePort` dosyasından (veya süreç bayrağından / `AGY_BROWSER_WS_URL`
    ortam değişkeninden) CDP portunu okur ve Antigravity Desktop'ın açık olan
    ana sayfa (`type == "page"`) hedeflerini döndürür.
    """
    cdp_port, _port_file, _exists = _resolve_cdp_port_and_file()
    if cdp_port is not None:
        pages = _fetch_cdp_targets_on_port(cdp_port)
        if pages:
            return pages

    ws_env = os.environ.get("AGY_BROWSER_WS_URL", "").strip()
    if ws_env.startswith("ws://"):
        parsed = urlparse(ws_env)
        if parsed.port:
            pages = _fetch_cdp_targets_on_port(parsed.port)
            if pages:
                return pages
        return [
            {
                "id": "env-ws",
                "type": "page",
                "title": "Antigravity",
                "webSocketDebuggerUrl": ws_env,
            }
        ]

    return []


def diagnose_cdp_status() -> dict[str, Any]:
    """
    CDP erişilebilirliğini, Antigravity Desktop süreç durumunu ve olası bağlantı
    hatalarının kesin nedenini + çözüm önerisini döndürür.
    """
    proc_info = get_antigravity_desktop_process_info()
    cdp_port, port_file, port_file_exists = _resolve_cdp_port_and_file()
    pages = discover_cdp_page_targets()

    if pages:
        reason = "ok"
        fix_hint = ""
    elif not proc_info["running"]:
        reason = "antigravity_not_running"
        fix_hint = "Antigravity Desktop çalışmıyor. Uygulamayı --remote-debugging-port=0 ile başlatın."
    elif not proc_info["has_remote_debugging_flag"] and not port_file_exists:
        reason = "cdp_disabled_in_antigravity_2_33"
        fix_hint = (
            "Antigravity Desktop (>= 2.33.0) --remote-debugging-port=0 olmadan başlatılmış. "
            "'make enable-cdp' (veya ./install.sh) çalıştırıp Antigravity Desktop'ı tamamen kapatıp yeniden açın."
        )
    elif cdp_port is None:
        reason = "port_file_missing"
        fix_hint = (
            "DevToolsActivePort dosyası bulunamadı veya okunamadı. "
            "Antigravity Desktop'ı --remote-debugging-port=0 ile başlatın."
        )
    else:
        reason = "cdp_unreachable_or_no_pages"
        fix_hint = (
            "CDP portu okundu ancak açık Antigravity pencere hedefi alınamadı; "
            "uygulamayı tamamen kapatıp yeniden açmayı deneyin."
        )

    return {
        "cdp_available": bool(pages),
        "port_file": str(port_file),
        "port_file_exists": port_file_exists,
        "cdp_port": cdp_port,
        "targets_count": len(pages),
        "antigravity_running": proc_info["running"],
        "antigravity_pid": proc_info["pid"],
        "has_remote_debugging_flag": proc_info["has_remote_debugging_flag"],
        "reason": reason,
        "fix_hint": fix_hint,
    }
