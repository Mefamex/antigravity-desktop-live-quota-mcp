"""
ConnectRPC Kota İstemcisi Modülü (src/quota_client.py)

Yerel `language_server` sürecine `RetrieveUserQuotaSummary` çağrısı yapar,
gelen ham yanıtı (`raw_response`) korur ve model gruplarını (`QuotaReport`)
ayrıştırır.
"""

from __future__ import annotations

import json
import ssl
import urllib.request
from typing import Any

import config
from src.discovery import discover_language_servers
from src.logger import get_logger
from src.models import BucketQuota, GroupQuota, QuotaReport

log = get_logger("quota")

RPC_PATH = "/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary"


def _call_rpc_endpoint(port: int, csrf_token: str, force_refresh: bool = False) -> dict[str, Any] | None:
    """Belirtilen yerel porta HTTP veya HTTPS üzerinden ConnectRPC isteği gönderir."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Codeium-Csrf-Token": csrf_token,
    }
    payload = json.dumps({"forceRefresh": True}).encode("utf-8") if force_refresh else b"{}"

    for scheme in ("http", "https"):
        url = f"{scheme}://127.0.0.1:{port}{RPC_PATH}"
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        ctx = ssl._create_unverified_context() if scheme == "https" else None
        try:
            with urllib.request.urlopen(
                req, timeout=config.NETWORK_TIMEOUT_SEC, context=ctx
            ) as resp:
                raw_bytes = resp.read()
                data = json.loads(raw_bytes.decode("utf-8", errors="ignore"))
                if isinstance(data, dict) and "response" in data:
                    return data
        except Exception:
            continue

    return None


def _parse_quota_response(raw_data: dict[str, Any]) -> QuotaReport:
    """Ham RPC yanıtını ayrıştırarak QuotaReport nesnesine dönüştürür."""
    resp_obj = raw_data.get("response", {})
    raw_groups = resp_obj.get("groups", [])

    parsed_groups: list[GroupQuota] = []
    gemini_weekly = 100
    gemini_5h = 100
    claude_weekly = 100
    claude_5h = 100
    argon_weekly = 100

    for g in raw_groups:
        g_name = str(g.get("displayName", ""))
        g_desc = str(g.get("description", ""))
        parsed_buckets: list[BucketQuota] = []

        for b in g.get("buckets", []):
            frac = float(b.get("remainingFraction", 1.0))
            pct = int(round(frac * 100))
            window = str(b.get("window", ""))
            bucket = BucketQuota(
                bucket_id=str(b.get("bucketId", "")),
                display_name=str(b.get("displayName", "")),
                window=window,
                remaining_fraction=frac,
                remaining_percent=pct,
                reset_time=str(b.get("resetTime", "")),
                description=str(b.get("description", "")),
            )
            parsed_buckets.append(bucket)

            if "Argon" in g_name:
                if window == "weekly":
                    argon_weekly = pct
            elif "Gemini" in g_name:
                if window == "weekly":
                    gemini_weekly = pct
                elif window == "5h":
                    gemini_5h = pct
            elif "Claude" in g_name or "GPT" in g_name:
                if window == "weekly":
                    claude_weekly = pct
                elif window == "5h":
                    claude_5h = pct

        parsed_groups.append(
            GroupQuota(
                display_name=g_name,
                description=g_desc,
                buckets=parsed_buckets,
            )
        )

    return QuotaReport(
        ok=True,
        gemini_weekly_pct=gemini_weekly,
        gemini_5h_pct=gemini_5h,
        claude_weekly_pct=claude_weekly,
        claude_5h_pct=claude_5h,
        argon_weekly_pct=argon_weekly,
        groups=parsed_groups,
        raw_response=raw_data,
    )


def fetch_live_quota(force_refresh: bool = False) -> QuotaReport:
    """
    Aktif language_server süreçlerini keşfeder ve ilk başarılı olanından
    canlı kota raporunu döndürür.
    """
    endpoints = discover_language_servers()
    if not endpoints:
        return QuotaReport(
            ok=False,
            gemini_weekly_pct=0,
            gemini_5h_pct=0,
            claude_weekly_pct=0,
            claude_5h_pct=0,
            argon_weekly_pct=0,
            error="Çalışan Antigravity language_server süreci bulunamadı.",
        )

    for ep in endpoints:
        for port in ep.ports:
            raw_data = _call_rpc_endpoint(port, ep.csrf_token, force_refresh=force_refresh)
            if raw_data is not None:
                return _parse_quota_response(raw_data)

    return QuotaReport(
        ok=False,
        gemini_weekly_pct=0,
        gemini_5h_pct=0,
        claude_weekly_pct=0,
        claude_5h_pct=0,
        argon_weekly_pct=0,
        error="language_server portlarından yanıt alınamadı.",
    )
