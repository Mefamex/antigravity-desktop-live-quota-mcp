"""
Windows Setup & CDP Shortcut Patcher (src/windows_setup.py)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def enable_cdp_windows(script_path: Path | None = None) -> dict[str, Any]:
    """
    Runs `scripts/enable-cdp.ps1` on Windows to add `--remote-debugging-port=0`
    to Antigravity Desktop `.lnk` shortcuts.
    """
    if sys.platform != "win32":
        return {
            "ok": False,
            "error": "--enable-cdp-windows is only supported on Windows (win32).",
        }

    ps_script = script_path or (Path(__file__).resolve().parent.parent / "scripts" / "enable-cdp.ps1")
    if not ps_script.is_file():
        return {"ok": False, "error": f"PowerShell script not found: {ps_script}"}

    flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
    for shell in ("powershell", "pwsh"):
        try:
            out = subprocess.check_output(
                [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps_script)],
                stderr=subprocess.PIPE,
                timeout=10.0,
                creationflags=flags,
            ).decode("utf-8", errors="ignore").strip()
            if out:
                return json.loads(out)
            return {"ok": False, "error": "Empty output from enable-cdp.ps1"}
        except FileNotFoundError:
            continue
        except (subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
            return {"ok": False, "error": str(exc)}

    return {"ok": False, "error": "Neither powershell nor pwsh was found on PATH."}
