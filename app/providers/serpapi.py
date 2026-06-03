from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.providers.http_utils import request_with_retries
from app.providers.base import BasePhoneProvider, ProviderMatch
from app.services.phone_variants import build_phone_variants


PLATFORM_LABELS = {
    "facebook.com": "Facebook",
    "instagram.com": "Instagram",
    "linkedin.com": "LinkedIn",
    "x.com": "X/Twitter",
    "twitter.com": "X/Twitter",
    "tiktok.com": "TikTok",
    "youtube.com": "YouTube",
    "github.com": "GitHub",
    "kvk.nl": "KvK",
    "kvkzoeken.nl": "KvK Zoeken",
    "mijnbedrijfsgegevens.nl": "Mijn Bedrijfsgegevens",
    "handelsregister.nl": "Handelsregister",
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

GOOGLE_BANNED_DOMAINS = {
    "google.com",
    "googleusercontent.com",
    "gstatic.com",
    "maps.google.com",
    "youtube.com",
}

OFFICIAL_DOMAINS = {
    "kvk.nl",
    "kvkzoeken.nl",
    "mijnbedrijfsgegevens.nl",
    "handelsregister.nl",
    "kvkregister.nl",
    "handelsregister-basis.nl",
    "kvkregisters.nl",
}

PUBLIC_DOMAINS = {
    "telefoonboek.nl",
    "telefoonnummer.nl",
    "telefoongids.nl",
    "detelefoonboek.nl",
    "nummer-zoeken.net",
    "telefoonnummerzoeken.net",
    "bedrijfstelefoongids.nl",
    "mijnbedrijfsgegevens.nl",
    "handelsregister.nl",
}


class SerpApiProvider(BasePhoneProvider):
    name = "serpapi"
    description = "SerpAPI + Google HTML fallback"
    GOOGLE_SEARCH_BASE_URL = "https://r.jina.ai/http://www.google.com/search"

    @staticmethod
    def _clean_domain(link: str) -> str:
        parsed = urlparse(link)
        domain = parsed.netloc.lower().replace("www.", "")
        if not domain and "://" in link:
            domain = link.split("://", 1)[1].split("/", 1)[0].lower()
        return domain.strip()

    @staticmethod
    def _extract_signal_tier(domain: str) -> str:
        if domain in OFFICIAL_DOMAINS:
            return "officieel"
        if domain in PUBLIC_DOMAINS:
            return "openbaar"
        return "indirect"

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
                for part in [p.strip() for p in clean.split(sep)]:
                    if not part:
                        continue
                    lowered = part.lower()
                    if lowered in markers:
                        continue
                    if "@" in lowered and domain in {"x.com", "twitter.com"}:
                        continue
                    return part

        if " - " in clean:
            candidate = clean.split(" - ", 1)[0].strip()
            if candidate and candidate.lower() not in markers:
                return candidate

        legal = re.search(
            r"\b([A-Za-zÀ-ÿ0-9'’.-]{3,90}\s(?:BV|B\.V\.?|NV|N\.V\.?|B\.A\.?|Ltd|Limited|GmbH|S\.A\.?|LLC))\b",
            clean,
            flags=re.IGNORECASE,
        )
        if legal:
            return legal.group(1).strip()[:255]

        return clean[:255]

    @staticmethod
    def _to_provider_match(
        *,
        platform: str,
        domain: str,
        title: str,
        link: str,
        snippet: str,
        matched: bool,
        query: str,
        confidence: float,
    ) -> ProviderMatch:
        identity_name = (title and SerpApiProvider._extract_name(title, domain)) or title
        source_tier = SerpApiProvider._extract_signal_tier(domain)
        return ProviderMatch(
            platform=platform,
            source="serpapi",
            match_type="exact" if matched else "context",
            name=identity_name[:255] if identity_name else None,
            account_handle=SerpApiProvider._extract_handle(domain, link),
            account_url=link,
            confidence=confidence,
            evidence=[f"search_query={query}"],
            details={
                "platform": platform,
                "title": title,
                "snippet": snippet[:420],
                "domain": domain,
                "source_tier": source_tier,
                "signal_tier": source_tier,
            },
            raw={"link": link, "snippet": snippet[:420], "query": query},
        )

    async def _lookup_serpapi(self, phone_e164: str) -> list[ProviderMatch]:
        if not settings.SERPAPI_API_KEY:
            return []

        number_forms = build_phone_variants(phone_e164)
        if not number_forms:
            return []

        params = {
            "q": f'"{number_forms[0]}"',
            "api_key": settings.SERPAPI_API_KEY,
            "num": settings.DDG_MAX_RESULTS,
        }

        try:
            timeout = httpx.Timeout(settings.SEARCH_REQUEST_TIMEOUT_SECONDS)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await request_with_retries(
                    client,
                    "GET",
                    settings.SERPAPI_BASE_URL,
                    scope="serpapi",
                    params=params,
                )
                if response is None:
                    return []
                if response.status_code != 200:
                    return []
                payload = response.json()
        except Exception:
            return []

        results: list[ProviderMatch] = []
        for item in payload.get("organic_results", [])[: settings.DDG_MAX_RESULTS]:
            title = item.get("title") or ""
            link = item.get("link") or ""
            snippet = item.get("snippet") or ""
            if not link:
                continue
            domain = self._clean_domain(link)
            if not domain or domain in self.GOOGLE_BANNED_DOMAINS:
                continue

            matched = any(form and (form in title or form in snippet) for form in number_forms)
            platform = PLATFORM_LABELS.get(domain) or domain
            source_tier = self._extract_signal_tier(domain)
            results.append(
                self._to_provider_match(
                    platform=platform,
                    domain=domain,
                    title=title,
                    link=link,
                    snippet=snippet,
                    matched=matched,
                    query=f'"{number_forms[0]}"',
                    confidence=0.84 if source_tier != "indirect" else 0.66,
                )
            )
        return results

    async def _lookup_google_html(self, phone_e164: str) -> list[ProviderMatch]:
        number_forms = build_phone_variants(phone_e164)
        if not number_forms:
            return []

        queries = [f'"{number}"' for number in number_forms[:2]]
        results: list[ProviderMatch] = []
        seen: set[str] = set()

        timeout = httpx.Timeout(settings.SEARCH_REQUEST_TIMEOUT_SECONDS)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            for query in queries:
                try:
                    response = await request_with_retries(
                        client,
                        "GET",
                        self.GOOGLE_SEARCH_BASE_URL,
                        scope="serpapi",
                        params={"q": query, "num": settings.DDG_MAX_RESULTS},
                        headers={"User-Agent": "Mozilla/5.0"},
                    )
                except Exception:
                    continue
                if response is None or response.status_code != 200:
                    continue

                html = response.text
                soup = BeautifulSoup(html, "html.parser")
                parsed_any = False
                heading_tags = soup.select("h3")

                for heading in heading_tags[: settings.DDG_MAX_RESULTS]:
                    title = " ".join(heading.get_text(" ", strip=True).split())
                    if not title:
                        continue

                    anchor = heading.find_parent("a")
                    if not anchor:
                        continue
                    link = (anchor.get("href") or "").strip()
                    if not link or link in seen:
                        continue

                    snippet_node = anchor.find_parent("div")
                    snippet = ""
                    if snippet_node:
                        next_snippet = snippet_node.find_next("div")
                        if next_snippet:
                            snippet = " ".join(next_snippet.get_text(" ", strip=True).split())

                    domain = self._clean_domain(link)
                    if not domain or domain in self.GOOGLE_BANNED_DOMAINS:
                        continue

                    seen.add(link)
                    parsed_any = True
                    platform = PLATFORM_LABELS.get(domain) or domain
                    source_tier = self._extract_signal_tier(domain)
                    matched = any(form and (form in title or form in snippet) for form in number_forms)
                    results.append(
                        self._to_provider_match(
                            platform=platform,
                            domain=domain,
                            title=title,
                            link=link,
                            snippet=snippet,
                            matched=matched,
                            query=query,
                            confidence=0.76 if source_tier != "indirect" else 0.58,
                        )
                    )

                if parsed_any:
                    continue

                for title, link in re.findall(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", html):
                    title = " ".join(title.split())
                    link = (link or "").strip()
                    if not title or not link or link in seen:
                        continue
                    domain = self._clean_domain(link)
                    if not domain or domain in self.GOOGLE_BANNED_DOMAINS:
                        continue

                    seen.add(link)
                    platform = PLATFORM_LABELS.get(domain) or domain
                    matched = any(form and form in title for form in number_forms)
                    results.append(
                        self._to_provider_match(
                            platform=platform,
                            domain=domain,
                            title=title,
                            link=link,
                            snippet="",
                            matched=matched,
                            query=query,
                            confidence=0.72 if matched else 0.56,
                        )
                    )

        return results

    async def lookup(self, phone_e164: str, context=None) -> list[ProviderMatch]:
        serpapi_results = await self._lookup_serpapi(phone_e164)
        google_results = []

        try:
            google_results = await self._lookup_google_html(phone_e164)
        except Exception:
            google_results = []

        results: list[ProviderMatch] = []
        results.extend(serpapi_results)
        results.extend(google_results)

        if not results:
            return []

        seen: set[str] = set()
        deduped: list[ProviderMatch] = []
        for item in results:
            key = (item.account_url or "").lower().strip()
            if key and key not in seen:
                seen.add(key)
                deduped.append(item)

        return deduped[: settings.DDG_MAX_RESULTS * 2]
