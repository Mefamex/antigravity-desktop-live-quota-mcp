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
import re
import subprocess
import urllib.request
from typing import Any

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


def discover_cdp_page_targets() -> list[dict[str, Any]]:
    """
    `DevToolsActivePort` dosyasından CDP portunu okur ve Antigravity Desktop'ın
    açık olan ana sayfa (`type == "page"`) hedeflerini döndürür.
    """
    port_file = config.DEVTOOLS_PORT_FILE
    if not port_file.exists():
        return []

    try:
        lines = port_file.read_text(encoding="utf-8").strip().splitlines()
        if not lines or not lines[0].strip().isdigit():
            return []
        cdp_port = int(lines[0].strip())
    except OSError:
        return []

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
