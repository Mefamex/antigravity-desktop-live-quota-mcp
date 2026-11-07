"""
Veri Yapıları ve Şema Modelleri (src/models.py)

Mefamex Mühendislik Prensibi:
Dış/yerel servislerden gelen ham yanıtlar (`raw_response`) kesilip biçilmeden
korunur; ayrıştırılmış (parsed) alanlar ise tip güvenli dataclass'lar ile sunulur.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class LanguageServerEndpoint:
    """Yerel çalışan Antigravity language_server bağlantı bilgisi."""

    pid: int
    csrf_token: str
    ports: list[int]


@dataclass(frozen=True)
class BucketQuota:
    """Tek bir kota havuzunun (örn. 5h veya weekly) durumu."""

    bucket_id: str
    display_name: str
    window: str
    remaining_fraction: float
    remaining_percent: int
    reset_time: str
    description: str = ""


@dataclass(frozen=True)
class GroupQuota:
    """Bir model ailesinin (örn. Gemini, Claude/GPT, Argon) kota grubu."""

    display_name: str
    description: str
    buckets: list[BucketQuota] = field(default_factory=list)


@dataclass(frozen=True)
class QuotaReport:
    """Hem ayrıştırılmış özeti hem de saf ham yanıtı taşıyan kota raporu."""

    ok: bool
    gemini_weekly_pct: int
    gemini_5h_pct: int
    claude_weekly_pct: int
    claude_5h_pct: int
    argon_weekly_pct: int
    groups: list[GroupQuota] = field(default_factory=list)
    raw_response: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """JSON serileştirmeye hazır sözlük döndürür."""
        return asdict(self)

    def format_compact(self) -> str:
        """Tek satırlık özet metin döndürür."""
        if not self.ok:
            return f"Kota alınamadı: {self.error}"
        return (
            f"⚡ Gemini: %{self.gemini_weekly_pct} (Haftalık) • %{self.gemini_5h_pct} (5s) | "
            f"Claude/GPT: %{self.claude_weekly_pct} (Haftalık) • %{self.claude_5h_pct} (5s) | "
            f"Argon: %{self.argon_weekly_pct}"
        )
