from __future__ import annotations

import httpx

from app.config import settings
from app.providers.base import BasePhoneProvider, ProviderMatch
from app.providers.http_utils import request_with_retries


class TwilioLookupProvider(BasePhoneProvider):
    name = "twilio_lookup"
    description = "Twilio Lookup (optioneel premium)"

    async def lookup(self, phone_e164: str, context=None) -> list[ProviderMatch]:
        if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
            return []

        timeout = httpx.Timeout(settings.SEARCH_REQUEST_TIMEOUT_SECONDS)
        url = f"{settings.TWILIO_LOOKUP_BASE_URL.rstrip('/')}/{phone_e164}"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await request_with_retries(
                    client,
                    "GET",
                    url,
                    scope="twilio_lookup",
                    auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                    params={"Type": "carrier,caller-name"},
                )
                if response is None or response.status_code != 200:
                    return []
                payload = response.json()
        except Exception:
            return []

        caller = payload.get("caller_name") if isinstance(payload, dict) else None
        carrier = payload.get("carrier") if isinstance(payload, dict) else None
        if not isinstance(caller, dict):
            caller = {}
        if not isinstance(carrier, dict):
            carrier = {}

        name = caller.get("caller_name")
        organization = caller.get("name")

        return [
            ProviderMatch(
                source=self.name,
                match_type="exact" if name else "context",
                name=(name or payload.get("national_format") or "Twilio Lookup") if (name or payload.get("national_format")) else None,
                organization=organization if isinstance(organization, str) else None,
                platform="Twilio",
                account_handle=caller.get("caller_type") if isinstance(caller.get("caller_type"), str) else None,
                account_url=None,
                confidence=0.9 if name else 0.62,
                evidence=["twilio_lookup"],
                details={
                    "platform": "Twilio",
                    "source_tier": "officieel",
                    "signal_tier": "officieel",
                    "carrier": carrier.get("name") if isinstance(carrier, dict) else None,
                    "caller_type": caller.get("caller_type") if isinstance(caller, dict) else None,
                },
                raw=payload,
            )
        ]


class NumlookupApiProvider(BasePhoneProvider):
    name = "numlookup_api"
    description = "Numlookup API (optioneel premium)"

    async def lookup(self, phone_e164: str, context=None) -> list[ProviderMatch]:
        if not settings.NUMLOOKUP_API_KEY:
            return []

        timeout = httpx.Timeout(settings.SEARCH_REQUEST_TIMEOUT_SECONDS)
        url = f"{settings.NUMLOOKUP_API_BASE_URL.rstrip('/')}/{phone_e164}"
        headers = {"apikey": settings.NUMLOOKUP_API_KEY}

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await request_with_retries(
                    client,
                    "GET",
                    url,
                    scope="numlookup_api",
                    headers=headers,
                )
                if response is None or response.status_code not in {200, 201}:
                    return []
                payload = response.json()
        except Exception:
            return []

        if not isinstance(payload, dict):
            return []

        name = payload.get("name")
        organization = payload.get("company") or payload.get("organization") or payload.get("carrier")

        return [
            ProviderMatch(
                source=self.name,
                match_type="exact" if name else "context",
                name=name or payload.get("carrier") or None,
                organization=organization,
                platform="Numlookup",
                account_handle=None,
                confidence=0.84 if name else 0.58,
                evidence=["numlookup_api"],
                details={
                    "platform": "Numlookup",
                    "source_tier": "officieel",
                    "signal_tier": "officieel",
                    "category": payload.get("type") or payload.get("number_type"),
                },
                raw=payload,
            )
        ]


class ClearbitLookupProvider(BasePhoneProvider):
    name = "clearbit_lookup"
    description = "Clearbit (optioneel premium)"

    async def lookup(self, phone_e164: str, context=None) -> list[ProviderMatch]:
        if not settings.CLEARBIT_API_KEY:
            return []

        timeout = httpx.Timeout(settings.SEARCH_REQUEST_TIMEOUT_SECONDS)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await request_with_retries(
                    client,
                    "GET",
                    settings.CLEARBIT_API_BASE_URL,
                    scope="clearbit_lookup",
                    params={"phone": phone_e164},
                    headers={"Authorization": f"Bearer {settings.CLEARBIT_API_KEY}"},
                )
                if response is None or response.status_code not in {200, 201}:
                    return []
                payload = response.json()
        except Exception:
            return []

        if not isinstance(payload, dict):
            return []

        person = payload.get("person") if isinstance(payload.get("person"), dict) else {}
        company = payload.get("company") if isinstance(payload.get("company"), dict) else {}

        person_name = None
        if isinstance(person, dict):
            person_name = person.get("name")
            if isinstance(person_name, dict):
                person_name = person_name.get("fullName")

        org = company.get("name") if isinstance(company, dict) else None
        if not (person_name or org):
            return []

        return [
            ProviderMatch(
                source=self.name,
                match_type="exact",
                name=person_name,
                organization=org,
                platform="Clearbit",
                account_handle=None,
                account_url=company.get("site") if isinstance(company, dict) else None,
                confidence=0.86,
                evidence=["clearbit_lookup"],
                details={
                    "platform": "Clearbit",
                    "source_tier": "officieel",
                    "signal_tier": "officieel",
                    "industry": company.get("category") if isinstance(company, dict) else None,
                    "logo": company.get("logo") if isinstance(company, dict) else None,
                },
                raw=payload,
            )
        ]


class HunterLookupProvider(BasePhoneProvider):
    name = "hunter_lookup"
    description = "Hunter phone search (optioneel premium)"

    async def lookup(self, phone_e164: str, context=None) -> list[ProviderMatch]:
        if not settings.HUNTER_API_KEY:
            return []

        timeout = httpx.Timeout(settings.SEARCH_REQUEST_TIMEOUT_SECONDS)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await request_with_retries(
                    client,
                    "GET",
                    settings.HUNTER_API_BASE_URL,
                    scope="hunter_lookup",
                    params={"phone": phone_e164, "api_key": settings.HUNTER_API_KEY},
                )
                if response is None or response.status_code != 200:
                    return []
                payload = response.json()
        except Exception:
            return []

        data = payload.get("data") if isinstance(payload, dict) else {}
        if not isinstance(data, dict):
            return []

        results = data.get("emails")
        if not isinstance(results, list) or not results:
            return []

        best = results[0]
        if not isinstance(best, dict):
            return []

        org = best.get("company") or data.get("company")

        return [
            ProviderMatch(
                source=self.name,
                match_type="context",
                name=best.get("value") if isinstance(best.get("value"), str) else None,
                organization=org if isinstance(org, str) else None,
                platform="Hunter",
                account_handle=best.get("position") if isinstance(best.get("position"), str) else None,
                confidence=0.78,
                evidence=["hunter_lookup"],
                details={
                    "platform": "Hunter",
                    "source_tier": "openbaar",
                    "signal_tier": "openbaar",
                    "type": best.get("type"),
                },
                raw=data,
            )
        ]
