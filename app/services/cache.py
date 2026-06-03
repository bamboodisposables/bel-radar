from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.config import settings
import uuid
from app.models import CacheEntry, expire_cache_entry


def get_cached_payload(db: Session, phone_e164: str, source: str) -> list[dict] | None:
    now = datetime.now(timezone.utc)
    entry = (
        db.query(CacheEntry)
        .filter(
            CacheEntry.phone_e164 == phone_e164,
            CacheEntry.source == source,
            CacheEntry.expires_at > now,
        )
        .one_or_none()
    )
    if not entry:
        return None
    return entry.payload


def set_cached_payload(db: Session, phone_e164: str, source: str, payload: Iterable[dict]) -> None:
    now = datetime.now(timezone.utc)
    expires = expire_cache_entry(settings.CACHE_TTL_SECONDS)

    existing = (
        db.query(CacheEntry)
        .filter(and_(CacheEntry.phone_e164 == phone_e164, CacheEntry.source == source))
        .one_or_none()
    )
    if existing is None:
        existing = CacheEntry(
            id=str(uuid.uuid4()),
            phone_e164=phone_e164,
            source=source,
            payload=list(payload),
            created_at=now,
            expires_at=expires,
        )
        db.add(existing)
    else:
        existing.payload = list(payload)
        existing.created_at = now
        existing.expires_at = expires

    db.commit()
