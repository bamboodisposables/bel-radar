from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from difflib import SequenceMatcher
from time import perf_counter
from urllib.parse import urlparse
import re
import uuid

from sqlalchemy.orm import Session

from app.config import settings
from app.models import LookupRequest, LookupResult, SourceRuntimeMetric
from app.providers import get_providers
from app.providers.base import ProviderMatch
from app.services.cache import get_cached_payload, set_cached_payload
from app.services.normalizer import normalize_phone
from app.services.scoring import score_match, score_multisource, source_priority_rank

_BUSINESS_SOURCES = {
    "kvk_api",
    "kvk_public",
    "directory_nl",
    "directory_sites",
    "duckduckgo_search",
    "serpapi",
    "twilio_lookup",
    "numlookup_api",
    "clearbit_lookup",
    "hunter_lookup",
    "social_hints",
}

_REPUTATION_SOURCES = {
    "phonenumbers_metadata",
    "numverify",
    "duckduckgo_search",
    "serpapi",
    "social_hints",
}

_NOISE_TOKENS = {
    "search",
    "zoeken",
    "resultaat",
    "resultaten",
    "telefoonnummer",
    "telefoonnummer.nl",
    "telefoongids",
    "pagina",
    "overzicht",
    "duckduckgo",
    "www",
    "official",
    "offici\u00eble",
    "company",
    "bedrijf",
}

_SIGNAL_PRIORITY = {
    "officieel": 3,
    "openbaar": 2,
    "indirect": 1,
}


def _normalize_name_key(value: str | None) -> str:
    if not value:
        return ""
    safe = re.sub(r"\s+", " ", re.sub(r"[^0-9a-zA-Z\u00c0-\u017f&.'\\-]", " ", value.lower()))
    safe = safe.replace("\u200b", "").strip()
    if safe in _NOISE_TOKENS:
        return ""
    return safe[:255]


def _normalize_url_key(raw_url: str | None) -> str:
    if not raw_url:
        return ""
    parsed = urlparse(raw_url)
    domain = (parsed.netloc or "").lower()
    if not domain and "://" in raw_url:
        domain = raw_url.split("://", 1)[1].split("/", 1)[0].lower()
    if not domain:
        return ""
    path = (parsed.path or "").rstrip("/")
    return f"{domain}{path}".strip().lower()


def _extract_signal_tier(details: dict | None, source_tier: str | None) -> str:
    if details and isinstance(details, dict):
        value = details.get("signal_tier")
        if value in _SIGNAL_PRIORITY:
            return value
        value = details.get("source_tier")
        if value in _SIGNAL_PRIORITY:
            return value
    return source_tier or "indirect"


def _normalize_signal_tier(value: str | None) -> int:
    return _SIGNAL_PRIORITY.get((value or "indirect").lower(), 1)


def _fuzzy_match_name(left: str | None, right: str | None) -> bool:
    left_key = _normalize_name_key(left)
    right_key = _normalize_name_key(right)
    if not left_key or not right_key:
        return False
    if left_key == right_key:
        return True
    if left_key in right_key or right_key in left_key:
        return True
    return SequenceMatcher(None, left_key, right_key).ratio() >= 0.89


def _segments(raw: str) -> list[str]:
    text = " ".join((raw or "").split())
    if not text:
        return []
    parts = [text]
    for sep in (" | ", " - ", " \u00b7 ", " \u2014 ", " \u2013 ", " • ", " · "):
        next_parts = []
        for part in parts:
            next_parts.extend([s.strip() for s in part.split(sep) if s.strip()])
        parts = next_parts
    return parts


def _extract_candidate_name(title: str, snippet: str | None, platform: str | None, account_url: str | None = None) -> str | None:
    platform_lower = (platform or "").lower()
    domain = urlparse(account_url or "").netloc.lower().replace("www.", "")

    candidates: list[str] = []
    for raw in (title, snippet or ""):
        for candidate in _segments(raw):
            cleaned = candidate.strip("-_|•·")
            if not cleaned:
                continue
            lowered = cleaned.lower()
            if lowered in _NOISE_TOKENS:
                continue
            if platform_lower and platform_lower in lowered:
                continue
            if domain and domain in lowered:
                continue
            if any(stop in lowered for stop in {"home", "result", "results", "pagina", "zoek", "search"}):
                continue
            if len(cleaned) < 3:
                continue
            if len(cleaned) > 4 and not any(ch.isalpha() for ch in cleaned):
                continue
            if re.search(r"\b\d{3,}\b", cleaned):
                continue
            candidates.append(cleaned)

    if candidates:
        return candidates[0][:255]

    for raw in (title, snippet or ""):
        text = " ".join((raw or "").split())
        if not text:
            continue
        legal = re.search(
            r"\b([A-Za-z\u00c0-\u017f0-9'\u2019.-]{3,90}\s(?:BV|B\\.V\\.?|NV|N\\.V\\.?|L\\.L\\.?|Ltd|Limited|B\\.A\\.?|GmbH|S\\.A\\.?|LLC))\b",
            text,
            flags=re.IGNORECASE,
        )
        if legal:
            return legal.group(1).strip()[:255]

    return None


def _enrich_match_identity(match: ProviderMatch) -> None:
    if match.name and match.name.strip():
        return

    details = match.details or {}
    candidate = _extract_candidate_name(
        details.get("title", "") or "",
        details.get("snippet", "") or "",
        match.platform,
        match.account_url,
    )
    if candidate:
        match.name = candidate
        return

    if match.organization:
        match.name = (match.organization or "")[:255]
        return

    handle = (match.account_handle or "").replace("@", "").strip()
    if handle:
        match.name = handle[:255]


def _merge_matches(existing: ProviderMatch, incoming: ProviderMatch) -> None:
    if incoming.name and not existing.name:
        existing.name = incoming.name
    if incoming.organization and not existing.organization:
        existing.organization = incoming.organization
    if incoming.account_handle and not existing.account_handle:
        existing.account_handle = incoming.account_handle
    if incoming.account_url and not existing.account_url:
        existing.account_url = incoming.account_url
    if incoming.location and not existing.location:
        existing.location = incoming.location
    if incoming.match_type == "exact":
        existing.match_type = "exact"

    existing.evidence = list(dict.fromkeys((existing.evidence or []) + (incoming.evidence or [])))

    if (incoming.confidence or 0.0) > (existing.confidence or 0.0):
        existing.confidence = incoming.confidence

    details = dict(existing.details or {})
    details.update(incoming.details or {})
    existing.details = details
    if not existing.raw:
        existing.raw = incoming.raw


def _dedupe_matches(matches: Iterable[ProviderMatch]) -> list[ProviderMatch]:
    deduped: list[ProviderMatch] = []

    for match in matches:
        _enrich_match_identity(match)
        merged = False

        incoming_source = (match.source or "").lower()
        incoming_platform = (match.platform or "").lower()
        incoming_url = _normalize_url_key(match.account_url)

        for existing in deduped:
            if (existing.source or "").lower() != incoming_source:
                continue
            if (existing.platform or "").lower() != incoming_platform:
                continue

            existing_url = _normalize_url_key(existing.account_url)
            same_url = bool(existing_url and incoming_url and existing_url == incoming_url)
            same_name = _fuzzy_match_name(existing.name, match.name)
            same_handle = bool(
                existing.account_handle and match.account_handle and existing.account_handle.lower() == match.account_handle.lower()
            )

            if same_url or same_name or same_handle:
                _merge_matches(existing, match)
                merged = True
                break

        if not merged:
            deduped.append(match)

    return deduped


def _entity_signature(match: ProviderMatch) -> tuple[str, str]:
    identity = match.name or match.organization or match.account_handle or match.platform or ""
    identity_key = _normalize_name_key(identity)
    if not identity_key:
        identity_key = _normalize_name_key(match.account_url) or "onbekende_entiteit"
    return (identity_key, (match.platform or "onbekend").lower())


def _aggregate_multisource(matches: Iterable[ProviderMatch]) -> list[ProviderMatch]:
    groups: dict[tuple[str, str], list[ProviderMatch]] = defaultdict(list)
    for match in matches:
        groups[_entity_signature(match)].append(match)

    grouped: list[ProviderMatch] = []

    for bucket in groups.values():
        ordered = sorted(
            bucket,
            key=lambda item: (item.confidence, source_priority_rank(item.source), item.match_type == "exact"),
            reverse=True,
        )
        if not ordered:
            continue

        primary = ordered[0]
        source_order: list[str] = []
        seen_sources: set[str] = set()
        source_stack: list[dict] = []
        exact_hit = False

        for item in ordered:
            source = item.source or "onbekende-bron"
            source_tier = _extract_signal_tier(item.details, (item.details or {}).get("source_tier"))
            source_stack.append(
                {
                    "source": source,
                    "platform": item.platform,
                    "match_type": item.match_type,
                    "signal_tier": source_tier,
                    "confidence": round(item.confidence, 3),
                }
            )
            if source not in seen_sources:
                seen_sources.add(source)
                source_order.append(source)
            if item.match_type == "exact":
                exact_hit = True

            if not primary.organization and item.organization:
                primary.organization = item.organization
            if not primary.account_handle and item.account_handle:
                primary.account_handle = item.account_handle
            if not primary.location and item.location:
                primary.location = item.location

        source_tiers = [_extract_signal_tier(primary.details, (primary.details or {}).get("source_tier"))]
        source_tiers.extend(x.get("signal_tier", "indirect") for x in source_stack)
        signal_tier = max(source_tiers, key=_normalize_signal_tier)

        details = dict(primary.details or {})
        details.update(
            {
                "source_stack": source_stack,
                "source_count": len(seen_sources),
                "primary_source": source_order[0],
                "supporting_sources": source_order[1:],
                "signal_tier": signal_tier,
            }
        )

        primary.details = details
        primary.source = source_order[0]
        primary.match_type = "exact" if exact_hit else "context"
        primary.confidence = score_multisource(primary.confidence, len(seen_sources))
        grouped.append(primary)

    return grouped


def _build_reputation_summary(phone_e164: str, matches: list[ProviderMatch]) -> ProviderMatch:
    sources = {match.source for match in matches if match.source}
    business_hits = [match for match in matches if (match.source or "") in _BUSINESS_SOURCES and match.match_type == "exact"]
    public_hits = [match for match in matches if (match.source or "") in _REPUTATION_SOURCES and match.match_type != "inconclusive"]
    exact_name_hits = [match for match in matches if match.match_type == "exact" and (match.name or match.organization)]
    mobile = phone_e164.startswith("+31") and phone_e164.replace("+31", "", 1).startswith("6")

    score = 0.22
    reasons: list[str] = []
    if mobile:
        score += 0.1
        reasons.append("Mobiel NL-nummer")
    if not business_hits:
        score += 0.22
        reasons.append("Geen zakelijke exacte match")
    if len(sources - {"phonenumbers_metadata"}) <= 1:
        score += 0.2
        reasons.append("Beperkte openbare footprint")
    if public_hits:
        score += min(0.08 * len(public_hits), 0.16)
        reasons.append(f"{len(public_hits)} openbare reputatiesignaal(s)")
    if exact_name_hits:
        score -= 0.14
        reasons.append("Zakelijke naam of organisatie gevonden")
    if any(match.source == "kvk_api" for match in matches):
        score -= 0.15
        reasons.append("Officiële KvK-match aanwezig")
    if any(match.source == "kvk_public" for match in matches):
        score -= 0.08
        reasons.append("Publieke KvK-vermelding gevonden")

    score = min(max(round(score, 3), 0.0), 1.0)
    if score >= 0.7:
        label = "Hoger reputatierisico"
    elif score >= 0.45:
        label = "Gemengd reputatiesignaal"
    else:
        label = "Laag reputatierisico"

    details = {
        "route": "spam",
        "risk_score": score,
        "risk_label": label,
        "source_count": len(sources),
        "official_hit_count": len([m for m in matches if m.source in {"kvk_api", "kvk_public"}]),
        "public_hit_count": len(public_hits),
        "source_tier": "indirect",
        "signal_tier": "indirect",
        "observed_sources": sorted(sources),
    }

    return ProviderMatch(
        source="reputation_model",
        platform="Spamcontrole",
        match_type="context",
        name=label,
        organization="lokale reputatie-analyse",
        confidence=score,
        evidence=reasons[:6] or ["Lokale analyse zonder extra reputatiesignalen"],
        details=details,
        raw={"phone_e164": phone_e164, "sources": sorted(sources)},
    )


def _to_orm_result(request_id: str, match: ProviderMatch) -> LookupResult:
    details = dict(match.details or {})
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
        details=details,
        raw=match.raw,
        discovered_at=match.discovered_at,
    )


async def _run_provider_lookup(
    provider,
    phone_e164: str,
    request_id: str,
    *,
    timeout_seconds: float,
    semaphore: asyncio.Semaphore,
) -> tuple[list[ProviderMatch], str | None]:
    async with semaphore:
        try:
            matches = await asyncio.wait_for(
                provider.lookup(phone_e164, context={"request_id": request_id}),
                timeout=timeout_seconds,
            )
            return matches, None
        except asyncio.TimeoutError:
            return [], f"timeout>{timeout_seconds:.1f}s"
        except Exception as exc:
            return [], str(exc)


async def run_lookup_with_store(
    db: Session,
    request: LookupRequest,
    *,
    force_refresh: bool = False,
    route: str = "business",
) -> list[LookupResult]:
    phone_e164 = request.phone_e164
    all_matches: list[ProviderMatch] = []
    request.error = None
    route = (route or "business").lower()
    providers = get_providers(route)
    concurrency = max(1, settings.LOOKUP_PROVIDER_CONCURRENCY)
    provider_timeout = max(1.0, settings.LOOKUP_PROVIDER_TIMEOUT_SECONDS)
    total_timeout = max(provider_timeout, settings.LOOKUP_TOTAL_TIMEOUT_SECONDS)
    semaphore = asyncio.Semaphore(concurrency)

    cached_payloads: dict[str, list[dict] | None] = {}
    provider_started_at: dict[str, float] = {}
    pending_tasks: dict[asyncio.Task, tuple] = {}

    for provider in providers:
        cached_payloads[provider.name] = None if force_refresh else get_cached_payload(db, phone_e164, provider.name)

    for provider in providers:
        cached = cached_payloads.get(provider.name)
        if cached is not None:
            provider_matches = provider.from_cache_payload(cached)
            hit = bool(provider_matches)
            for match in provider_matches:
                _enrich_match_identity(match)
                match.confidence = score_match(match, phone_e164)
                all_matches.append(match)
            db.add(
                SourceRuntimeMetric(
                    id=str(uuid.uuid4()),
                    request_id=request.id,
                    source=provider.name,
                    duration_ms=0.0,
                    result_count=len(provider_matches),
                    hit_count=1 if hit else 0,
                    error=None,
                )
            )
            continue

        provider_started_at[provider.name] = perf_counter()
        task = asyncio.create_task(
            _run_provider_lookup(
                provider,
                phone_e164,
                request.id,
                timeout_seconds=provider_timeout,
                semaphore=semaphore,
            )
        )
        pending_tasks[task] = (provider, provider_started_at[provider.name])

    lookup_started = perf_counter()
    while pending_tasks and (perf_counter() - lookup_started) < total_timeout:
        remaining = total_timeout - (perf_counter() - lookup_started)
        done, _ = await asyncio.wait(
            pending_tasks.keys(),
            timeout=remaining,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not done:
            break

        for task in done:
            provider, started_at = pending_tasks.pop(task)
            provider_matches: list[ProviderMatch] = []
            provider_error: str | None = None
            try:
                provider_matches, provider_error = await task
                if provider_error is None:
                    set_cached_payload(db, phone_e164, provider.name, provider.to_cache_payload(provider_matches))
                    for match in provider_matches:
                        _enrich_match_identity(match)
                        match.confidence = score_match(match, phone_e164)
                        all_matches.append(match)
            except Exception as exc:
                provider_error = str(exc)

            elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
            db.add(
                SourceRuntimeMetric(
                    id=str(uuid.uuid4()),
                    request_id=request.id,
                    source=provider.name,
                    duration_ms=elapsed_ms,
                    result_count=len(provider_matches),
                    hit_count=1 if provider_matches else 0,
                    error=provider_error,
                )
            )

    for task, (provider, started_at) in list(pending_tasks.items()):
        task.cancel()
        elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
        db.add(
            SourceRuntimeMetric(
                id=str(uuid.uuid4()),
                request_id=request.id,
                source=provider.name,
                duration_ms=elapsed_ms,
                result_count=0,
                hit_count=0,
                error=f"global-timeout>{total_timeout:.1f}s",
            )
        )
    if pending_tasks:
        await asyncio.gather(*pending_tasks.keys(), return_exceptions=True)

    deduped = _dedupe_matches(all_matches)
    aggregated = _aggregate_multisource(deduped)
    if route == "spam":
        aggregated = [_build_reputation_summary(phone_e164, deduped)] + aggregated[:4]
    aggregated_sorted = sorted(
        aggregated,
        key=lambda match: (match.confidence, source_priority_rank(match.source), match.match_type == "exact"),
        reverse=True,
    )

    results = [_to_orm_result(request.id, match) for match in aggregated_sorted]

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
    mode: str = "business",
) -> tuple[LookupRequest, bool, str]:
    phone_e164 = normalize_phone(phone_raw)
    mode = (mode or "business").lower()
    request = (
        db.query(LookupRequest)
        .filter_by(phone_e164=phone_e164, mode=mode)
        .order_by(LookupRequest.created_at.desc())
        .first()
    )
    if request and request.status == "done" and not force_refresh:
        created_new = False
    else:
        request = LookupRequest(
            id=str(uuid.uuid4()),
            phone_raw=phone_raw.strip(),
            phone_e164=phone_e164,
            mode=mode,
            status="running",
        )
        db.add(request)
        db.commit()
        db.refresh(request)
        created_new = True

    return request, created_new, phone_e164
