"""
Desktop Notification Manager (src/notifier.py)

Manages Linux desktop notifications (`notify-send`) with zero external Python
dependencies.

Features:
1. Critical Threshold Alert: Sends an alert when quota drops below the configured threshold (15%).
2. Quota Refresh Notification: Notifies when the 5-hour or weekly counter resets and quota is restored.
3. Cooldown & Anti-Spam: Avoids repeatedly disturbing the user with identical alerts (30-min cooldown).
4. Single-Leader Guard: Only the `LEADER` process sends notifications.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from typing import Any

import config
from src.logger import get_logger
from src.models import QuotaReport

log = get_logger("notifier")


def is_notify_send_available() -> bool:
    """Checks whether the `notify-send` binary is available on the system."""
    return shutil.which("notify-send") is not None


def send_desktop_notification(
    title: str,
    message: str,
    urgency: str = "normal",
    icon: str = "dialog-warning",
    timeout_ms: int = 5000,
) -> bool:
    """
    Sends a local desktop notification via the system's `notify-send` command.

    :param title: Notification title.
    :param message: Notification body text.
    :param urgency: 'low', 'normal', or 'critical'.
    :param icon: Notification icon name or path.
    :param timeout_ms: Display duration on screen (ms).
    :return: True if the notification was triggered successfully, False otherwise.
    """
    if not is_notify_send_available():
        log.debug("`notify-send` not found; skipping notification.")
        return False

    cmd = [
        "notify-send",
        "-a",
        config.NOTIFICATION_APP_NAME,
        "-u",
        urgency,
        "-i",
        icon,
        "-t",
        str(timeout_ms),
        title,
        message,
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=3)
        if res.returncode == 0:
            log.info(f"Desktop notification sent -> {title}")
            return True
        else:
            log.warning(f"notify-send returned an error: {res.stderr.strip()}")
            return False
    except Exception as exc:
        log.warning(f"Failed to send desktop notification: {exc}")
        return False


class QuotaNotifier:
    """
    State tracker that monitors quota status and emits controlled desktop
    notifications on critical drops and quota refreshes.
    """

    def __init__(self) -> None:
        self.last_alert_times: dict[str, float] = {}
        self.last_known_pcts: dict[str, int] = {}

    def check_and_notify(self, report: QuotaReport, is_leader: bool = True) -> list[str]:
        """
        Analyzes the incoming quota report and sends desktop notifications if needed.
        Triggers only when `is_leader=True` and `ENABLE_DESKTOP_NOTIFICATIONS=True`.
        """
        if not is_leader or not config.ENABLE_DESKTOP_NOTIFICATIONS:
            return []

        if not report.ok or not report.groups:
            return []

        sent_alerts: list[str] = []
        now = time.time()
        cooldown_sec = config.NOTIFICATION_COOLDOWN_MINUTES * 60.0
        threshold_pct = config.NOTIFICATION_CRITICAL_THRESHOLD_PCT

        for group in report.groups:
            g_name = group.display_name or "Model"
            for bucket in group.buckets:
                b_id = bucket.bucket_id or f"{g_name}_{bucket.window}"
                pct = bucket.remaining_percent

                prev_pct = self.last_known_pcts.get(b_id)
                self.last_known_pcts[b_id] = pct

                # 1. Quota Refresh Check (Reset Notification)
                if config.ENABLE_RESET_NOTIFICATION and prev_pct is not None:
                    # Quota was <= 50% in the previous check and is now >= 90% (refreshed)
                    if prev_pct <= 50 and pct >= 90:
                        title = f"🔄 AI Quota Refreshed: {g_name} ({bucket.window})"
                        msg = f"Quota refreshed ({pct}%)! Full capacity restored."
                        if send_desktop_notification(title, msg, urgency="normal", icon="emblem-default"):
                            sent_alerts.append(title)
                        # Reset alert cooldown so future drops can still trigger an alert
                        self.last_alert_times.pop(b_id, None)
                        continue

                # 2. Critical Quota Drop Alert (Critical Threshold Notification)
                if pct <= threshold_pct:
                    last_alert = self.last_alert_times.get(b_id, 0.0)
                    if (now - last_alert) >= cooldown_sec:
                        title = f"⚠️ Critical AI Quota Alert: {g_name} ({bucket.window})"
                        msg = (
                            f"Remaining Quota: {pct}%\n"
                            f"{bucket.description or 'Your quota is running low!'}\n"
                            f"Consider switching models or waiting for the quota reset."
                        )
                        if send_desktop_notification(title, msg, urgency="critical", icon="dialog-warning"):
                            sent_alerts.append(title)
                            self.last_alert_times[b_id] = now

        return sent_alerts
