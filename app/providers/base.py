from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class ProviderMatch:
    source: str
    platform: Optional[str] = None
    match_type: str = "inconclusive"
    name: Optional[str] = None
    account_handle: Optional[str] = None
    account_url: Optional[str] = None
    organization: Optional[str] = None
    location: Optional[str] = None
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BasePhoneProvider:
    name = "base"
    description = "Base interface"
    enabled = True

    async def lookup(self, phone_e164: str, context: dict[str, Any] | None = None) -> list[ProviderMatch]:
        raise NotImplementedError

    def to_cache_payload(self, matches: list[ProviderMatch]) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for match in matches:
            data = asdict(match)
            data["discovered_at"] = match.discovered_at.isoformat()
            payload.append(data)
        return payload

    def from_cache_payload(self, payload: list[dict[str, Any]]) -> list[ProviderMatch]:
        out: list[ProviderMatch] = []
        for item in payload:
            item = dict(item)
            da = item.get("discovered_at")
            if isinstance(da, str):
                item["discovered_at"] = datetime.fromisoformat(da)
            out.append(ProviderMatch(**item))
        return out
