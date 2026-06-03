from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import LookupRequest, LookupResult
from app.providers import get_providers
from app.providers.base import ProviderMatch
from app.services.cache import get_cached_payload, set_cached_payload
from app.services.normalizer import normalize_phone
from app.services.scoring import score_match


def _dedupe_matches(matches: Iterable[ProviderMatch]) -> list[ProviderMatch]:
    uniq: dict[tuple[str, str | None, str | None, str], ProviderMatch] = {}
    for match in matches:
        key = (
            match.source,
            (match.account_url or "").lower(),
            (match.name or "").lower(),
            match.match_type,
        )
        existing = uniq.get(key)
        if existing is None or score_match(match, "") > score_match(existing, ""):
            uniq[key] = match
    return list(uniq.values())


def _to_orm_result(request_id: str, match: ProviderMatch) -> LookupResult:
    return LookupResult(
        id=str(uuid.uuid4()),
        request_id=request_id,
        source=match.source,
        match_type=match.match_type,
        name=match.name,
        account_handle=match.account_handle,
        account_url=match.account_url,
        organization=match.organization,
        location=match.location,
        confidence=match.confidence,
        evidence=match.evidence,
        details=match.details,
        raw=match.raw,
        discovered_at=match.discovered_at,
    )


async def run_lookup_with_store(
    db: Session,
    request: LookupRequest,
    *,
    force_refresh: bool = False,
) -> list[LookupResult]:
    phone_e164 = request.phone_e164
    matches: list[ProviderMatch] = []
    providers = get_providers()

    for provider in providers:
        cached = None if force_refresh else get_cached_payload(db, phone_e164, provider.name)
        provider_matches: list[ProviderMatch] = []
        if cached is not None:
            provider_matches = provider.from_cache_payload(cached)
        else:
            provider_matches = await provider.lookup(phone_e164, context={"request_id": request.id})
            set_cached_payload(db, phone_e164, provider.name, provider.to_cache_payload(provider_matches))

        for match in provider_matches:
            match.confidence = score_match(match, phone_e164)
            matches.append(match)

    deduped = _dedupe_matches(matches)
    deduped_sorted = sorted(deduped, key=lambda x: x.confidence, reverse=True)

    results = [_to_orm_result(request.id, m) for m in deduped_sorted]
    request.status = "done"
    request.completed_at = datetime.now(timezone.utc)
    request.updated_at = request.completed_at

    if not results:
        request.error = "Geen match gevonden"

    for result in results:
        db.add(result)
    db.commit()
    db.refresh(request)
    return results


def create_lookup_request(
    db: Session,
    phone_raw: str,
    *,
    force_refresh: bool = False,
) -> tuple[LookupRequest, bool, str]:
    phone_e164 = normalize_phone(phone_raw)
    request = db.query(LookupRequest).filter_by(phone_e164=phone_e164).order_by(LookupRequest.created_at.desc()).first()
    if request and request.status == "done" and not force_refresh:
        created_new = False
    else:
        request = LookupRequest(
            id=str(uuid.uuid4()),
            phone_raw=phone_raw.strip(),
            phone_e164=phone_e164,
            status="running",
        )
        db.add(request)
        db.commit()
        db.refresh(request)
        created_new = True

    return request, created_new, phone_e164
