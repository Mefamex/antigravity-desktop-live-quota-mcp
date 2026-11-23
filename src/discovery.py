"""
Process and Port Discovery Module (src/discovery.py)

This module performs two primary discovery tasks:
1. Detects the PID, `--csrf_token`, and local listening TCP ports of running
   Antigravity `language_server` processes.
2. Reads `~/.config/Antigravity/DevToolsActivePort` to find Chrome DevTools
   Protocol (CDP) WebSocket addresses for active Electron windows.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import config
from src.logger import get_logger
from src.models import LanguageServerEndpoint

log = get_logger("discovery")


def _win32_creation_flags() -> int:
    """Returns CREATE_NO_WINDOW on Windows to prevent console window flashes."""
    if sys.platform == "win32":
        return int(getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
    return 0


def _run_win32_powershell_json(ps_script: str, timeout: float = 4.0) -> list[dict[str, Any]]:
    """Executes a PowerShell command returning JSON objects and normalizes to a list."""
    for shell in ("powershell", "pwsh"):
        try:
            out = subprocess.check_output(
                [shell, "-NoProfile", "-NonInteractive", "-Command", ps_script],
                stderr=subprocess.DEVNULL,
                timeout=timeout,
                creationflags=_win32_creation_flags(),
            ).decode("utf-8", errors="ignore").strip()
            if not out:
                return []
            parsed = json.loads(out)
            if isinstance(parsed, dict):
                return [parsed]
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, dict)]
            return []
        except (subprocess.SubprocessError, OSError, json.JSONDecodeError):
            continue
    return []


def _parse_netstat_listening_ports(netstat_out: str) -> dict[int, list[int]]:
    """Parses `netstat -ano -p tcp` output into a `{pid: [port, ...]}` map."""
    ports_by_pid: dict[int, list[int]] = {}
    for line in netstat_out.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        local_addr, foreign_addr, state, pid_str = parts[1], parts[2], parts[3], parts[-1]
        if not pid_str.isdigit():
            continue
        is_listening = (
            state.upper() == "LISTENING"
            or foreign_addr in ("0.0.0.0:0", "[::]:0", "*:*")
        )
        if not is_listening:
            continue
        m_port = re.search(r":(\d+)$", local_addr)
        if not m_port:
            continue
        pid = int(pid_str)
        port = int(m_port.group(1))
        ports = ports_by_pid.setdefault(pid, [])
        if port not in ports:
            ports.append(port)
    return ports_by_pid


def _parse_ss_listening_ports(ss_out: str) -> dict[int, list[int]]:
    """Parses `ss -tulpn` output into a `{pid: [port, ...]}` map."""
    ports_by_pid: dict[int, list[int]] = {}
    for line in ss_out.splitlines():
        if "LISTEN" not in line or "pid=" not in line:
            continue
        m_port = re.search(r":(\d+)\s+", line)
        if not m_port:
            continue
        port = int(m_port.group(1))
        for m_pid in re.finditer(r"pid=(\d+)", line):
            pid = int(m_pid.group(1))
            ports = ports_by_pid.setdefault(pid, [])
            if port not in ports:
                ports.append(port)
    return ports_by_pid


def _extract_csrf_token_from_cmdline(cmdline: str) -> str:
    """Extracts `--csrf_token` value from a process command line if present."""
    m_token = re.search(r"--csrf_token[=\s]+([a-fA-F0-9\-]+)", cmdline)
    return m_token.group(1) if m_token else ""


def _extract_host_bridge_port_from_cmdline(cmdline: str) -> int | None:
    """Extracts `--host_bridge_url=http://127.0.0.1:<port>` port if present."""
    m_url = re.search(r"--host_bridge_url[=\s]+https?://127\.0\.0\.1:(\d+)", cmdline)
    return int(m_url.group(1)) if m_url else None


def _extract_token_from_cdp() -> str:
    """Extracts the CSRF/bridge token from an open Antigravity window via CDP."""
    pages = discover_cdp_page_targets()
    if not pages:
        return ""
    from src.cdp_client import cdp_evaluate

    js_expr = (
        "(window.__APP_CONFIG__ && window.__APP_CONFIG__.csrfToken) "
        "|| new URLSearchParams((window.location.hash || '').replace(/^#/, '')).get('t') "
        "|| ''"
    )
    for page in pages:
        ws_url = str(page.get("webSocketDebuggerUrl", ""))
        if not ws_url:
            continue
        try:
            res = cdp_evaluate(ws_url, js_expr)
            val = res.get("result", {}).get("result", {}).get("value")
            if isinstance(val, str) and val.strip():
                return val.strip()
        except Exception:
            continue
    return ""


def _extract_from_logs(logs_dir: Path | None = None) -> tuple[list[int], str]:
    """
    Scans recent `main.log` / `language_server.log` files for v2.34.0+ Hub URLs
    (`https://127.0.0.1:<port>/#t=<token>`), returning `(ports, token)`.
    """
    root = logs_dir or config.ANTIGRAVITY_LOGS_DIR
    if not root.is_dir():
        return ([], "")

    candidates: list[Path] = []
    for name in ("main.log", "language_server.log"):
        candidates.extend(root.rglob(name))

    try:
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        pass

    ports: list[int] = []
    token = ""
    for log_file in candidates[:4]:
        try:
            text = log_file.read_text(encoding="utf-8", errors="ignore")[-32768:]
        except OSError:
            continue
        for m in re.finditer(r"https?://127\.0\.0\.1:(\d+)/?(?:#t=([A-Za-z0-9\-_.~]+))?", text):
            port = int(m.group(1))
            if port not in ports:
                ports.append(port)
            if not token and m.group(2):
                token = m.group(2)
    return (ports, token)


def _discover_server_processes_and_ports() -> tuple[list[tuple[int, str]], dict[int, list[int]]]:
    """Collects `(pid, cmdline)` pairs and listening ports per PID for the current OS."""
    if sys.platform == "win32":
        ps_cmd = (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -like 'language_server*' -or "
            "$_.CommandLine -match 'csrf_token|read_host_bridge_token_from_stdin' } | "
            "Select-Object ProcessId, CommandLine | ConvertTo-Json -Compress"
        )
        rows = _run_win32_powershell_json(ps_cmd)
        processes: list[tuple[int, str]] = []
        for row in rows:
            pid_val = row.get("ProcessId")
            cmdline = str(row.get("CommandLine") or "")
            if isinstance(pid_val, int) and cmdline:
                processes.append((pid_val, cmdline))

        try:
            netstat_out = subprocess.check_output(
                ["netstat", "-ano", "-p", "tcp"],
                stderr=subprocess.DEVNULL,
                timeout=3.0,
                creationflags=_win32_creation_flags(),
            ).decode("utf-8", errors="ignore")
        except (subprocess.SubprocessError, OSError):
            netstat_out = ""
        return (processes, _parse_netstat_listening_ports(netstat_out))

    processes = []
    try:
        out = subprocess.check_output(
            ["pgrep", "-a", "language_server"],
            stderr=subprocess.DEVNULL,
            timeout=2.0,
        ).decode("utf-8", errors="ignore")
    except (subprocess.SubprocessError, OSError):
        return ([], {})

    for line in out.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2 and parts[0].isdigit():
            processes.append((int(parts[0]), parts[1]))

    try:
        ss_out = subprocess.check_output(
            ["ss", "-tulpn"],
            stderr=subprocess.DEVNULL,
            timeout=2.0,
        ).decode("utf-8", errors="ignore")
    except (subprocess.SubprocessError, OSError):
        ss_out = ""
    return (processes, _parse_ss_listening_ports(ss_out))


def discover_language_servers() -> list[LanguageServerEndpoint]:
    """
    Scans running `language_server` processes on the system and returns the PID,
    token, and port list. Supports both legacy `--csrf_token` CLI flags and
    Antigravity v2.34.0+ `--read_host_bridge_token_from_stdin` via CDP/log fallback.
    """
    endpoints: list[LanguageServerEndpoint] = []
    processes, ports_by_pid = _discover_server_processes_and_ports()
    if not processes:
        return endpoints

    # Prioritize Antigravity Desktop processes (--subclient_type hub) first
    processes.sort(key=lambda item: 0 if "--subclient_type hub" in item[1] else 1)

    cdp_token_cache: str | None = None
    log_fallback_cache: tuple[list[int], str] | None = None

    for pid, cmdline in processes:
        is_v234_bridge = (
            "--read_host_bridge_token_from_stdin" in cmdline
            or "--host_bridge_url" in cmdline
        )
        csrf_token = _extract_csrf_token_from_cmdline(cmdline)
        if not csrf_token and not is_v234_bridge:
            continue

        ports = list(ports_by_pid.get(pid, []))
        bridge_port = _extract_host_bridge_port_from_cmdline(cmdline)
        if bridge_port and bridge_port not in ports and not ports:
            ports.append(bridge_port)

        if not csrf_token:
            if cdp_token_cache is None:
                cdp_token_cache = _extract_token_from_cdp()
            csrf_token = cdp_token_cache

        if not csrf_token or not ports:
            if log_fallback_cache is None:
                log_fallback_cache = _extract_from_logs()
            log_ports, log_token = log_fallback_cache
            if not csrf_token:
                csrf_token = log_token
            if not ports:
                ports = list(log_ports)

        if csrf_token and ports:
            endpoints.append(
                LanguageServerEndpoint(pid=pid, csrf_token=csrf_token, ports=ports)
            )

    return endpoints


def _parse_desktop_process_flags(pid: int, joined_cmd: str) -> dict[str, Any]:
    """Extracts remote-debugging flag status and explicit port from a command line."""
    has_flag = bool(re.search(r"--remote-debugging-port(?:[=\s]+\d+)?(?:\s|$)", joined_cmd))
    explicit_port: int | None = None
    m_port = re.search(r"--remote-debugging-port[=\s]+(\d+)", joined_cmd)
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


def _get_win32_antigravity_desktop_process_info() -> dict[str, Any]:
    """Detects the main Antigravity Desktop Electron process on Windows via CIM."""
    ps_cmd = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -in @('Antigravity.exe', 'Antigravity IDE.exe', 'agy.exe') } | "
        "Select-Object ProcessId, Name, CommandLine | ConvertTo-Json -Compress"
    )
    for row in _run_win32_powershell_json(ps_cmd):
        pid_val = row.get("ProcessId")
        cmdline = str(row.get("CommandLine") or "")
        name = str(row.get("Name") or "").lower()
        if not isinstance(pid_val, int) or not cmdline:
            continue
        if "language_server" in cmdline.lower() or "python" in name:
            continue
        if "--type=" in cmdline or "--import=" in cmdline:
            continue
        return _parse_desktop_process_flags(pid_val, cmdline)

    return {
        "running": False,
        "pid": None,
        "has_remote_debugging_flag": False,
        "explicit_debug_port": None,
    }


def get_antigravity_desktop_process_info() -> dict[str, Any]:
    """
    Detects the main Antigravity Desktop Electron process running on the system
    and returns the `--remote-debugging-port` flag status.
    Excludes `language_server`, `antigravity-ide`, `python`, and `--type=` child processes.
    """
    if sys.platform == "win32":
        return _get_win32_antigravity_desktop_process_info()

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
        # Split cmdline arriving as a single string due to Electron/Chromium setproctitle
        if len(args) == 1 and " " in args[0]:
            args = args[0].split()

        exe_name = Path(args[0]).name.lower()
        joined = " ".join(args)

        # Only the main Electron app (/opt/Antigravity/antigravity, etc.)
        if exe_name != "antigravity" or "antigravity-ide" in args[0].lower():
            continue
        if "language_server" in joined or "python" in exe_name:
            continue
        if any(a.startswith("--type=") or a.startswith("--import=") for a in args[1:]):
            continue

        return _parse_desktop_process_flags(pid, joined)

    return {
        "running": False,
        "pid": None,
        "has_remote_debugging_flag": False,
        "explicit_debug_port": None,
    }


def _resolve_cdp_port_and_file() -> tuple[int | None, Path, bool]:
    """
    Resolves the active CDP port, the port file used, and whether the file exists.
    Falls back to the explicit `--remote-debugging-port=N` flag if `DevToolsActivePort`
    is unavailable.
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
    """Lists valid Antigravity window targets from the given local CDP port."""
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
        # Select only real Antigravity app windows (skip splash data: URLs)
        if page_url.startswith("http") or "Antigravity" in title:
            valid_pages.append(t)

    return valid_pages


def discover_cdp_page_targets() -> list[dict[str, Any]]:
    """
    Reads the CDP port from `DevToolsActivePort` (or process flag / `AGY_BROWSER_WS_URL`
    env var) and returns open main page (`type == "page"`) targets for Antigravity Desktop.
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
    Returns CDP availability, Antigravity Desktop process status, and the exact
    reason + fix hint for any potential connection errors.
    """
    proc_info = get_antigravity_desktop_process_info()
    cdp_port, port_file, port_file_exists = _resolve_cdp_port_and_file()
    pages = discover_cdp_page_targets()

    if pages:
        reason = "ok"
        fix_hint = ""
    elif not proc_info["running"]:
        reason = "antigravity_not_running"
        fix_hint = "Antigravity Desktop is not running. Launch the application with --remote-debugging-port=0."
    elif not proc_info["has_remote_debugging_flag"] and not port_file_exists:
        reason = "cdp_disabled_in_antigravity_2_33"
        enable_cmd = (
            "python main.py --enable-cdp-windows"
            if sys.platform == "win32"
            else "make enable-cdp (or ./install.sh)"
        )
        fix_hint = (
            "Antigravity Desktop (>= 2.33.0) was started without --remote-debugging-port=0. "
            f"Run '{enable_cmd}', then completely quit and reopen Antigravity Desktop."
        )
    elif cdp_port is None:
        reason = "port_file_missing"
        fix_hint = (
            "DevToolsActivePort file was not found or could not be read. "
            "Launch Antigravity Desktop with --remote-debugging-port=0."
        )
    else:
        reason = "cdp_unreachable_or_no_pages"
        fix_hint = (
            "CDP port was read, but no open Antigravity window target could be retrieved; "
            "try completely quitting and reopening the application."
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
