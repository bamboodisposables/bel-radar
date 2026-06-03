from __future__ import annotations

from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.providers.base import BasePhoneProvider, ProviderMatch
from app.providers.http_utils import request_with_retries
from app.services.phone_variants import build_phone_variants, make_query_plan


PLATFORM_LABELS = {
    "facebook.com": "Facebook",
    "instagram.com": "Instagram",
    "linkedin.com": "LinkedIn",
    "x.com": "X/Twitter",
    "twitter.com": "X/Twitter",
    "tiktok.com": "TikTok",
    "youtube.com": "YouTube",
    "github.com": "GitHub",
    "telefoonnummer.nl": "Telefoonnummer.nl",
    "telefoongids.nl": "Telefoongids",
    "kvk.nl": "KvK",
    "kvkzoeken.nl": "KvK Zoeken",
    "mijnbedrijfsgegevens.nl": "Mijn Bedrijfsgegevens",
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


class DuckDuckGoSearchProvider(BasePhoneProvider):
    name = "duckduckgo_search"
    description = "Publieke zoekresultaten als publieke aanwijzing"
    BANNED_DOMAINS = {"duckduckgo.com", "claritycheck.net", "claritycheck.org", "search.brave.com"}

    SOCIAL_DOMAINS = [
        "facebook.com",
        "instagram.com",
        "linkedin.com",
        "x.com",
        "twitter.com",
        "tiktok.com",
        "youtube.com",
        "github.com",
    ]

    @staticmethod
    def _clean_domain(raw_url: str) -> str:
        parsed = urlparse(raw_url)
        domain = parsed.netloc.lower().replace("www.", "")
        if not domain and "://" in raw_url:
            domain = raw_url.split("://", 1)[1].split("/", 1)[0].lower()
        return domain.strip()

    @staticmethod
    def _normalize_href(raw_url: str) -> str:
        if not raw_url:
            return raw_url
        parsed = urlparse(raw_url)
        if parsed.hostname in {"duckduckgo.com", "www.duckduckgo.com"} and parsed.path in {"/l/", "/l"}:
            next_url = parse_qs(parsed.query).get("uddg", [None])[0]
            if next_url:
                return unquote(next_url)
        return raw_url

    @staticmethod
    def _extract_handle(domain: str, raw_url: str) -> str | None:
        try:
            path_parts = [p for p in urlparse(raw_url).path.split("/") if p]
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
        if not settings.ENABLE_DDG_SCRAPING:
            return []

        number_forms = build_phone_variants(phone_e164)
        if not number_forms:
            return []

        queries = make_query_plan(
            phone_e164,
            base_queries=[
                '"{phone}" telefoonnummer',
                '"{phone}" bedrijfsgegevens',
                '"{phone}" bedrijf',
            ],
            broad_queries=[
                '{phone} "openbaar"',
                '{phone} "website"',
                '{phone} "KvK"',
            ],
        )
        for domain in self.SOCIAL_DOMAINS:
            for number in number_forms[:1]:
                queries.append(f'"{number}" site:{domain}')

        queries = list(dict.fromkeys(queries))[:14]

        results: list[ProviderMatch] = []
        timeout = httpx.Timeout(settings.REQUEST_TIMEOUT_SECONDS)

        for query in queries:
            url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
            try:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                    resp = await request_with_retries(
                        client,
                        "GET",
                        url,
                        scope="duckduckgo_search",
                        headers={"User-Agent": settings.HTTP_USER_AGENT},
                    )
                    if resp is None:
                        continue
                    resp.raise_for_status()
            except Exception:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select("a.result__a")
            seen = set()

            for link in items[: settings.DDG_MAX_RESULTS]:
                href = link.get("href", "").strip()
                href = self._normalize_href(href)
                title = " ".join(link.get_text(" ", strip=True).split())
                if not href or href in seen:
                    continue
                seen.add(href)

                parent = link.find_parent("div")
                snippet_node = parent.find_next_sibling("div") if parent else None
                snippet = " ".join(snippet_node.get_text(" ", strip=True).split()) if snippet_node else ""

                domain = self._clean_domain(href)
                if not domain or domain in self.BANNED_DOMAINS:
                    continue
                if domain in self.SOCIAL_DOMAINS:
                    # Socialen worden apart behandeld via social_hints.
                    continue

                matched = any(number in title or number in snippet for number in number_forms if number)
                platform = PLATFORM_LABELS.get(domain) or domain
                social_handle = self._extract_handle(domain, href)

                results.append(
                    ProviderMatch(
                        platform=platform,
                        source=self.name,
                        match_type="exact" if matched else "context",
                        name=self._extract_name(title, domain),
                        account_handle=social_handle,
                        account_url=href,
                        confidence=0.72 if matched else 0.48,
                        evidence=[f"search_query={query}", f"source_domain={domain}"],
                        details={
                            "platform": platform,
                            "title": title,
                            "snippet": snippet[:400],
                            "domain": domain,
                            "source_tier": "openbaar",
                            "signal_tier": "openbaar",
                        },
                        raw={"href": href, "query": query},
                    )
                )

        return results
