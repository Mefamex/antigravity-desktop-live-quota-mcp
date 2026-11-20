"""
antigravity-quota-mcp — Central Configuration Module (config.py)

3-Tier Configuration Precedence:
1. Safe in-code defaults (constants in this file)
2. External/user configuration
3. Environment variable overrides (e.g., AGY_QUOTA_POLL_SEC=15)
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
# 1. SERVER IDENTITY
# ============================================================================
SERVER_NAME: str = "antigravity-desktop-live-quota-mcp"
SERVER_VERSION: str = "1.2.0"
PROTOCOL_VERSION: str = "2025-11-25"

# ============================================================================
# 2. FILE AND DIRECTORY PATHS
# ============================================================================
HOME_DIR: Path = Path.home()

# File where Antigravity Desktop writes the active Chrome DevTools port
DEVTOOLS_PORT_FILE: Path = Path(
    os.environ.get("AGY_DEVTOOLS_PORT_FILE")
    or os.environ.get("AGY_BROWSER_ACTIVE_PORT_FILE")
    or str(HOME_DIR / ".config" / "Antigravity" / "DevToolsActivePort")
)

# Kernel lock file (stored on tmpfs) ensuring only a single process performs
# UI injection during multi-instance execution
_runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
LOCK_FILE_PATH: Path = Path(_runtime_dir) / "antigravity-desktop-live-quota.lock"

# ============================================================================
# 3. TIMING AND POLLING SETTINGS
# ============================================================================
# Interval (ms) for the in-window JS loop to fetch quota from the local language_server
BROWSER_FETCH_INTERVAL_MS: int = _env_int("AGY_BROWSER_FETCH_MS", 60_000)

# Interval (sec) for the leader MCP process to check windows (handles Ctrl+R or new windows)
WATCHER_CHECK_INTERVAL_SEC: int = _env_int("AGY_WATCHER_CHECK_SEC", 8)

# Interval (sec) for the leader process to query cloud quota for desktop notifications
WATCHER_NOTIFY_INTERVAL_SEC: int = _env_int("AGY_WATCHER_NOTIFY_SEC", 120)

# Timeout duration (sec) for local HTTP and WebSocket connections
NETWORK_TIMEOUT_SEC: float = float(_env_int("AGY_NETWORK_TIMEOUT_SEC", 2))

# ============================================================================
# 4. VISUAL BADGE (UI BADGE) AND COLOR THRESHOLDS
# ============================================================================
UI_Injection_Enabled: bool = _env_bool("AGY_UI_INJECTION_ENABLED", True)

# DOM element ID and target top-bar selector
BADGE_ELEMENT_ID: str = "agy-live-quota-pill"
TARGET_BAR_SELECTOR: str = '[data-testid="title-menu-bar"]'

# Color thresholds based on remaining percentage
THRESHOLD_HIGH_PCT: int = _env_int("AGY_THRESHOLD_HIGH", 50)  # > 50% Green
THRESHOLD_LOW_PCT: int = _env_int("AGY_THRESHOLD_LOW", 20)    # > 20% Yellow, below Red

# Subtle pulse alert at critical quota threshold
PULSE_ALERT_THRESHOLD_PCT: int = _env_int("AGY_PULSE_ALERT_THRESHOLD_PCT", 15)  # <= 15% Pulse alert
ENABLE_PULSE_ALERT: bool = _env_bool("AGY_ENABLE_PULSE_ALERT", True)

COLOR_HIGH: str = "#4ade80"   # Green
COLOR_MEDIUM: str = "#fbbf24" # Yellow / Amber
COLOR_LOW: str = "#f87171"    # Red

# ============================================================================
# 5. LOGGING SETTINGS
# ============================================================================
# Note: In the MCP stdio protocol, stdout is ONLY for JSON-RPC messages.
# All logs are strictly written to stderr.
LOG_LEVEL: str = os.environ.get("AGY_LOG_LEVEL", "INFO").upper()

# ============================================================================
# 6. DESKTOP NOTIFICATION SETTINGS
# ============================================================================
ENABLE_DESKTOP_NOTIFICATIONS: bool = _env_bool("AGY_ENABLE_NOTIFICATIONS", True)
NOTIFICATION_CRITICAL_THRESHOLD_PCT: int = _env_int("AGY_NOTIFY_THRESHOLD_PCT", 15)
NOTIFICATION_COOLDOWN_MINUTES: int = _env_int("AGY_NOTIFY_COOLDOWN_MIN", 30)
ENABLE_RESET_NOTIFICATION: bool = _env_bool("AGY_ENABLE_RESET_NOTIFY", True)
NOTIFICATION_APP_NAME: str = "Antigravity Quota"

