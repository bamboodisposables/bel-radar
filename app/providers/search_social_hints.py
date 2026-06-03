from __future__ import annotations

from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.providers.base import BasePhoneProvider, ProviderMatch
from app.providers.http_utils import request_with_retries
from app.services.phone_variants import build_phone_variants, make_query_plan


class SocialHintProvider(BasePhoneProvider):
    name = "social_hints"
    description = "Social-platform landing pages als indicatieve hint"

    SOCIAL_DOMAINS = [
        "facebook.com",
        "instagram.com",
        "linkedin.com",
        "x.com",
        "twitter.com",
        "youtube.com",
        "tiktok.com",
    ]

    BANNED_DOMAINS = {"duckduckgo.com", "claritycheck.org", "claritycheck.net"}

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
    def _extract_name(title: str) -> str | None:
        if not title:
            return None
        text = " ".join(title.split())
        if " | " in text:
            text = text.split(" | ", 1)[0].strip()
        if " - " in text and len(text) > 45:
            text = text.split(" - ", 1)[0].strip()
        return text[:255] if text else None

    async def lookup(self, phone_e164: str, context=None) -> list[ProviderMatch]:
        if not settings.ENABLE_DDG_SCRAPING:
            return []

        number_forms = build_phone_variants(phone_e164)
        if not number_forms:
            return []

        queries = make_query_plan(
            phone_e164,
            base_queries=['"{phone}"'],
            broad_queries=[
                '{phone} social',
                '{phone} "contact"',
                '{phone} "bedrijf"',
            ],
        )

        # Social hints eerst exact per platform, daarna één brede fallback.
        for domain in self.SOCIAL_DOMAINS:
            for number in number_forms[:2]:
                queries.append(f'"{number}" site:{domain}')

        queries = list(dict.fromkeys(queries))[:22]

        timeout = httpx.Timeout(settings.SEARCH_REQUEST_TIMEOUT_SECONDS)
        results: list[ProviderMatch] = []
        seen: set[str] = set()

        for query in queries:
            url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
            try:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                    resp = await request_with_retries(
                        client,
                        "GET",
                        url,
                        scope="social_hints",
                        headers={"User-Agent": settings.HTTP_USER_AGENT},
                    )
                    if resp is None:
                        continue
                    resp.raise_for_status()
            except Exception:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            for link in soup.select("a.result__a")[: settings.DDG_MAX_RESULTS]:
                href = self._normalize_href(link.get("href", "").strip())
                if not href or href in seen:
                    continue
                seen.add(href)

                title = " ".join(link.get_text(" ", strip=True).split())
                parent = link.find_parent("div")
                snippet_node = parent.find_next_sibling("div") if parent else None
                snippet = " ".join(snippet_node.get_text(" ", strip=True).split()) if snippet_node else ""

                domain = self._clean_domain(href)
                if not domain or domain in self.BANNED_DOMAINS:
                    continue
                if domain not in self.SOCIAL_DOMAINS:
                    continue

                platform = domain.split(".")[0].title()
                results.append(
                    ProviderMatch(
                        platform=platform,
                        source=self.name,
                        match_type="context",
                        name=self._extract_name(title),
                        account_handle=None,
                        account_url=href,
                        organization=None,
                        location=None,
                        confidence=0.42,
                        evidence=[f"social_hint_query={query}"],
                        details={
                            "platform": platform,
                            "title": title,
                            "snippet": snippet[:350],
                            "domain": domain,
                            "source_tier": "indirect",
                            "signal_tier": "indirect",
                        },
                        raw={"query": query, "href": href, "snippet": snippet},
                    )
                )

        return results
