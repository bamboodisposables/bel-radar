import httpx

from app.config import settings
from app.providers.base import BasePhoneProvider, ProviderMatch


class NumverifyProvider(BasePhoneProvider):
    name = "numverify"
    description = "NumVerify API met validatie, land, type en providerinformatie"

    async def lookup(self, phone_e164: str, context=None) -> list[ProviderMatch]:
        if not settings.NUMVERIFY_API_KEY:
            return []

        timeout = httpx.Timeout(settings.REQUEST_TIMEOUT_SECONDS)
        headers = {"apikey": settings.NUMVERIFY_API_KEY}
        params = {"number": phone_e164}

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(
                    settings.NUMVERIFY_BASE_URL,
                    headers=headers,
                    params=params,
                )
                if resp.status_code != 200:
                    return []
                payload = resp.json()
        except Exception:
            return []

        if not payload.get("valid"):
            return []

        return [
            ProviderMatch(
                source=self.name,
                match_type="context",
                name=payload.get("carrier") or "Onbekende gebruiker",
                location=payload.get("location"),
                organization=payload.get("carrier"),
                confidence=0.35,
                details={
                    "country_code": payload.get("country_code"),
                    "country_name": payload.get("country_name"),
                    "line_type": payload.get("line_type"),
                    "carrier": payload.get("carrier"),
                    "source_tier": "officieel",
                },
                raw=payload,
            )
        ]
