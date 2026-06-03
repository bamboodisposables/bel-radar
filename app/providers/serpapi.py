from __future__ import annotations

from app.config import settings
from app.providers.base import BasePhoneProvider, ProviderMatch
from urllib.parse import urlparse


PLATFORM_LABELS = {
    "facebook.com": "Facebook",
    "instagram.com": "Instagram",
    "linkedin.com": "LinkedIn",
    "x.com": "X/Twitter",
    "twitter.com": "X/Twitter",
    "tiktok.com": "TikTok",
    "youtube.com": "YouTube",
    "github.com": "GitHub",
}


PLATFORM_MARKERS = {
    "facebook",
    "instagram",
    "linkedin",
    "twitter",
    "x",
    "tiktok",
    "youtube",
    "github",
}


class SerpApiProvider(BasePhoneProvider):
    name = "serpapi"
    description = "SerpAPI JSON search (aanbevolen boven scraping)"

    @staticmethod
    def _clean_domain(link: str) -> str:
        parsed = urlparse(link)
        domain = parsed.netloc.lower().replace("www.", "")
        if not domain and "://" in link:
            domain = link.split("://", 1)[1].split("/", 1)[0].lower()
        return domain.strip()

    @staticmethod
    def _extract_handle(domain: str, link: str) -> str | None:
        try:
            path_parts = [p for p in urlparse(link).path.split("/") if p]
        except Exception:
            path_parts = []

        if domain == "linkedin.com" and len(path_parts) >= 2:
            if path_parts[0] in {"in", "company"}:
                return path_parts[1]

        if domain in {"instagram.com", "x.com", "twitter.com", "github.com", "tiktok.com", "youtube.com"}:
            if not path_parts:
                return None
            first = path_parts[0].lstrip("@")
            banned = {"share", "hashtag", "intent", "watch", "channel", "user", "@", "i", "explore", "shorts"}
            if first and first not in banned and len(first) > 1:
                return first

        if domain == "facebook.com":
            if not path_parts:
                return None
            if "profile" in path_parts[0].lower():
                return None
            return path_parts[0].lstrip("@")

        return None

    @staticmethod
    def _extract_name(title: str, domain: str) -> str | None:
        if not title:
            return None

        clean = " ".join(title.split())
        markers = list(PLATFORM_MARKERS) + [PLATFORM_LABELS.get(domain, "").lower()]
        for sep in (" | ", " - ", " • ", " · ", " — "):
            if sep in clean:
                parts = [p.strip() for p in clean.split(sep)]
                for part in parts:
                    lowered = part.lower()
                    if not part:
                        continue
                    if lowered in markers:
                        continue
                    if "@" in lowered and domain in {"x.com", "twitter.com"}:
                        continue
                    return part
        return clean

    async def lookup(self, phone_e164: str, context=None) -> list[ProviderMatch]:
        if not settings.SERPAPI_API_KEY:
            return []
        params = {
            "q": f'"{phone_e164}"',
            "api_key": settings.SERPAPI_API_KEY,
        }
        try:
            import httpx

            timeout = httpx.Timeout(settings.REQUEST_TIMEOUT_SECONDS)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(settings.SERPAPI_BASE_URL, params=params)
                if response.status_code != 200:
                    return []
                payload = response.json()
        except Exception:
            return []

        results = []
        for item in payload.get("organic_results", [])[: settings.DDG_MAX_RESULTS]:
            title = item.get("title") or ""
            link = item.get("link") or ""
            snippet = item.get("snippet") or ""
            if not link:
                continue
            domain = self._clean_domain(link)
            platform = PLATFORM_LABELS.get(domain) or domain
            handle = self._extract_handle(domain, link)
            identity_name = self._extract_name(title, domain)
            if f'"{phone_e164}"' in snippet:
                matched = True
            else:
                matched = phone_e164 in title
            results.append(
                ProviderMatch(
                    platform=platform,
                    source=self.name,
                    match_type="exact" if matched else "context",
                    name=identity_name[:255] if identity_name else None,
                    account_handle=handle,
                    account_url=link,
                    confidence=0.8,
                    evidence=[f"serpapi_query={phone_e164}"],
                    details={"platform": platform, "title": title, "snippet": snippet[:400], "domain": domain},
                    raw=item,
                )
            )
        return results
