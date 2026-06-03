from __future__ import annotations
import re
from urllib.parse import quote_plus

import httpx

from app.config import settings
from app.providers.base import BasePhoneProvider, ProviderMatch


def _iter_kvk_records(payload: dict) -> list[dict]:
    if not isinstance(payload, dict):
        return []

    candidates: list = []
    nested = payload.get("results") or payload.get("data") or payload.get("result")
    if isinstance(nested, list):
        candidates = nested
    elif isinstance(nested, dict):
        candidates = nested.get("items") or nested.get("bedrijven") or nested.get("companies") or []
        if not isinstance(candidates, list):
            candidates = []

    if not candidates:
        candidates = payload.get("bedrijven") or payload.get("companies") or []
        if not isinstance(candidates, list):
            candidates = []

    return [item for item in candidates if isinstance(item, dict)]


def _parse_city_from_address(record: dict) -> str | None:
    for key in ("plaats", "city", "gemeente", "address_city"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    address = record.get("address") or record.get("addresss") or record.get("vestiging")
    if isinstance(address, dict):
        for key in ("city", "plaats", "town", "municipality"):
            value = address.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return None


def _parse_name(record: dict) -> str | None:
    for key in ("name", "handelsnaam", "tradeName", "detailedTradeName"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:255]

    for key in ("detailed", "tradenames", "tradeNames"):
        value = record.get(key)
        if isinstance(value, dict):
            for nested_key in ("current", "original", "short", "businessName"):
                nested = value.get(nested_key)
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()[:255]

    return None


def _normalize_phone(phone: str | None) -> str:
    if not phone:
        return ""
    return re.sub(r"\D", "", phone)


class KvkApiProvider(BasePhoneProvider):
    name = "kvk_api"
    description = "Officiële KVK bedrijfsinformatie"

    def _extract_kvk_query(self, phone_e164: str) -> str:
        return f'"{phone_e164}"'

    async def lookup(self, phone_e164: str, context=None) -> list[ProviderMatch]:
        if not settings.KVK_API_KEY:
            return []

        timeout = httpx.Timeout(settings.REQUEST_TIMEOUT_SECONDS)
        params = {
            "q": self._extract_kvk_query(phone_e164),
            "page": 1,
            "size": 20,
        }
        headers = {
            "apikey": settings.KVK_API_KEY,
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    settings.KVK_API_BASE_URL,
                    params=params,
                    headers=headers,
                )
        except Exception:
            return []

        if response.status_code == 403:
            return []
        if response.status_code not in {200, 201}:
            return []

        try:
            payload = response.json()
        except Exception:
            return []

        records = _iter_kvk_records(payload)
        if not records:
            return []

        results = []
        for record in records:
            if not isinstance(record, dict):
                continue

            organization = record.get("tradeNames")
            organization = _parse_name(record.get("tradeNames", {})) if isinstance(organization, dict) else organization
            if not isinstance(organization, str):
                organization = None
            if isinstance(organization, str) and organization.strip():
                organization = organization.strip()[:255]

            city = _parse_city_from_address(record)
            name = _parse_name(record) or organization or city
            website = record.get("website")
            if isinstance(website, dict):
                website = website.get("url")
            if not isinstance(website, str):
                website = None
            raw_phone = _normalize_phone(record.get("phoneNumber") or record.get("phone"))
            number_variants = {_normalize_phone(phone_e164), _normalize_phone(phone_e164[3:])}
            if raw_phone and raw_phone not in number_variants and not any(
                raw_phone.endswith(variant) for variant in number_variants if variant
            ):
                continue

            results.append(
                ProviderMatch(
                    platform="KvK",
                    source=self.name,
                    match_type="exact",
                    name=name,
                    account_handle=None,
                    account_url=website,
                    organization=organization,
                    location=city,
                    confidence=0.94,
                    evidence=[f"kvk_query={quote_plus(phone_e164)}", "kvk_api_match=true"],
                    details={
                        "platform": "KvK",
                        "kvk_number": record.get("kvkNumber") or record.get("dossiernummer") or record.get("kvk"),
                        "source_tier": "officieel",
                    },
                    raw=record,
                )
            )

        return results
