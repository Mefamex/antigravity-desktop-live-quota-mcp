"""
Data Structures and Schema Models (src/models.py)

Mefamex Engineering Principle:
Raw responses (`raw_response`) from external/local services are preserved
untruncated; parsed fields are exposed via type-safe dataclasses.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class LanguageServerEndpoint:
    """Connection details for a locally running Antigravity language_server."""

    pid: int
    csrf_token: str
    ports: list[int]


@dataclass(frozen=True)
class BucketQuota:
    """State of a single quota bucket (e.g., 5h or weekly)."""

    bucket_id: str
    display_name: str
    window: str
    remaining_fraction: float
    remaining_percent: int
    reset_time: str
    description: str = ""


@dataclass(frozen=True)
class GroupQuota:
    """Quota group for a model family (e.g., Gemini, Claude/GPT, Argon)."""

    display_name: str
    description: str
    buckets: list[BucketQuota] = field(default_factory=list)


@dataclass(frozen=True)
class QuotaReport:
    """Quota report carrying both the parsed summary and the raw response."""

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
        """Returns a dictionary ready for JSON serialization."""
        return asdict(self)

    def format_compact(self) -> str:
        """Returns a single-line summary string."""
        if not self.ok:
            return f"Quota unavailable: {self.error}"
        return (
            f"⚡ Gemini: {self.gemini_weekly_pct}% (Weekly) • {self.gemini_5h_pct}% (5h) | "
            f"Claude/GPT: {self.claude_weekly_pct}% (Weekly) • {self.claude_5h_pct}% (5h) | "
            f"Argon: {self.argon_weekly_pct}%"
        )
