"""
Masaüstü Bildirim Yöneticisi (src/notifier.py)

Linux masaüstü bildirimlerini (`notify-send`) sıfır harici Python bağımlılığıyla
yönetir.

Özellikler:
1. Kritik Eşik Uyarısı: Kota belirlenen eşiğin (%15) altına düştüğünde uyarı gönderir.
2. Kota Yenilenme Müjdesi: 5 saatlik veya haftalık sayaç sıfırlanıp kota tazelendiğinde bildirim verir.
3. Cooldown & Anti-Spam: Sürekli aynı bildirimle kullanıcıyı rahatsız etmez (30 dk cooldown).
4. Tekil Lider Koruması: Yalnızca `LEADER` olan süreç bildirim gönderir.
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
    """Sistemde `notify-send` ikili dosyasının bulunup bulunmadığını kontrol eder."""
    return shutil.which("notify-send") is not None


def send_desktop_notification(
    title: str,
    message: str,
    urgency: str = "normal",
    icon: str = "dialog-warning",
    timeout_ms: int = 5000,
) -> bool:
    """
    Sistemdeki `notify-send` üzerinden yerel masaüstü bildirimi gönderir.

    :param title: Bildirim başlığı.
    :param message: Bildirim metni.
    :param urgency: 'low', 'normal' veya 'critical'.
    :param icon: Bildirim ikonu adı veya yolu.
    :param timeout_ms: Bildirimin ekranda kalma süresi (ms).
    :return: Bildirim başarıyla tetiklendiyse True, aksi halde False.
    """
    if not is_notify_send_available():
        log.debug("`notify-send` bulunamadığı için bildirim atlandı.")
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
            log.info(f"Masaüstü bildirimi gönderildi -> {title}")
            return True
        else:
            log.warning(f"notify-send hata döndürdü: {res.stderr.strip()}")
            return False
    except Exception as exc:
        log.warning(f"Masaüstü bildirimi gönderilemedi: {exc}")
        return False


class QuotaNotifier:
    """
    Kota durumunu izleyerek kritik düşüşlerde ve yenilenmelerde
    kontrollü masaüstü bildirimi üreten durum takipçisi.
    """

    def __init__(self) -> None:
        self.last_alert_times: dict[str, float] = {}
        self.last_known_pcts: dict[str, int] = {}

    def check_and_notify(self, report: QuotaReport, is_leader: bool = True) -> list[str]:
        """
        Gelen kota raporunu analiz eder ve gerekliyse masaüstü bildirimi gönderir.
        Yalnızca `is_leader=True` ve `ENABLE_DESKTOP_NOTIFICATIONS=True` ise tetiklenir.
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

                # 1. Kota Yenilenme Kontrolü (Reset Notification)
                if config.ENABLE_RESET_NOTIFICATION and prev_pct is not None:
                    # Kota önceki ölçümde %50 veya altındaydı, şimdi %90 üzerine çıktıysa (yenilenmiş)
                    if prev_pct <= 50 and pct >= 90:
                        title = f"🔄 AI Kotası Yenilendi: {g_name} ({bucket.window})"
                        msg = f"Kotanız tazelendi (%{pct})! Çalışmaya tam kapasite devam edebilirsiniz."
                        if send_desktop_notification(title, msg, urgency="normal", icon="emblem-default"):
                            sent_alerts.append(title)
                        # Alert cooldown'ını sıfırla ki tekrar düşerse uyarı alabilsin
                        self.last_alert_times.pop(b_id, None)
                        continue

                # 2. Kritik Kota Düşüşü Uyarısı (Critical Threshold Notification)
                if pct <= threshold_pct:
                    last_alert = self.last_alert_times.get(b_id, 0.0)
                    if (now - last_alert) >= cooldown_sec:
                        title = f"⚠️ Kritik AI Kota Uyarısı: {g_name} ({bucket.window})"
                        msg = (
                            f"Kalan Kota: %{pct}\n"
                            f"{bucket.description or 'Kotanız tükenmek üzere!'}\n"
                            f"Model değiştirmeyi veya kota yenilenmesini beklemeyi düşünebilirsiniz."
                        )
                        if send_desktop_notification(title, msg, urgency="critical", icon="dialog-warning"):
                            sent_alerts.append(title)
                            self.last_alert_times[b_id] = now

        return sent_alerts
