from __future__ import annotations

import re
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.providers.base import BasePhoneProvider, ProviderMatch
from app.providers.http_utils import request_with_retries
from app.services.phone_variants import build_phone_variants, make_query_plan


PLATFORM_LABELS = {
    "kvk.nl": "KvK",
    "kvkzoeken.nl": "KvK Zoeken",
    "mijnbedrijfsgegevens.nl": "Mijn Bedrijfsgegevens",
    "handelsregister.nl": "Handelsregister",
    "kvkregister.nl": "KvK Register",
    "handelsregister.nl": "Handelsregister",
    "kvkregisters.nl": "KvK Register",
    "handelsregister.be": "Handelsregister BE",
}


class KvkPublicProvider(BasePhoneProvider):
    name = "kvk_public"
    description = "KvK publieke bron"

    KVK_MIRROR_DOMAINS = [
        "kvk.nl",
        "kvkzoeken.nl",
        "mijnbedrijfsgegevens.nl",
        "kvkregister.nl",
        "handelsregister.nl",
        "mijnbedrijfgegevens.nl",
        "handelsregister-basis.nl",
        "kvkregisters.nl",
    ]

    BANNED_DOMAINS = {
        "duckduckgo.com",
        "claritycheck.org",
        "claritycheck.net",
    }

    def __init__(self) -> None:
        self._phone_term_pattern = re.compile(r"\+?0?(31)?[0-9 ]+")

    @staticmethod
    def _normalize_domain(raw_url: str) -> str:
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
    def _clean_name(raw_text: str, domain: str) -> str | None:
        if not raw_text:
            return None

        text = " ".join(raw_text.split())
        if not text:
            return None

        platform = PLATFORM_LABELS.get(domain, "")
        if platform and platform.lower() in text.lower():
            text = re.sub(rf"\s*{re.escape(platform)}\s*", " ", text, flags=re.IGNORECASE).strip()

        for separator in (" - ", " | ", " · ", " • ", " — ", " – "):
            if separator in text:
                candidates = [segment.strip() for segment in text.split(separator)]
                for candidate in candidates:
                    if not candidate:
                        continue
                    if len(candidate) > 4:
                        return candidate[:255]

        legal = re.search(
            r"\b([A-Za-z\u00c0-\u017f0-9'\u2019.-]{3,90}\s(?:BV|B\.V\.?|NV|N\.V\.?|L\.L\.?|GmbH|Ltd|Limited|B\.A\.?|V\.O\.F\.?)\b)",
            text,
            flags=re.IGNORECASE,
        )
        if legal:
            return legal.group(1).strip()[:255]

        return text[:255]

    async def lookup(self, phone_e164: str, context=None) -> list[ProviderMatch]:
        if not settings.ENABLE_DDG_SCRAPING:
            return []

        number_forms = build_phone_variants(phone_e164)
        if not number_forms:
            return []

        queries = make_query_plan(
            phone_e164,
            base_queries=[
                '"{phone}" KvK',
                '"{phone}" "Kamer van Koophandel"',
                '"{phone}" handelsregister',
                '"{phone}" Telefoonnummer',
            ],
            broad_queries=[
                '{phone} handelsregister',
                '{phone} bedrijfsinformatie',
                '{phone} "offici"',
            ],
        )

        for domain in self.KVK_MIRROR_DOMAINS:
            for number in number_forms[:2]:
                queries.append(f'"{number}" site:{domain}')

        queries = list(dict.fromkeys(queries))[:28]

        timeout = httpx.Timeout(settings.SEARCH_REQUEST_TIMEOUT_SECONDS)
        results: list[ProviderMatch] = []
        seen: set[str] = set()

        for query in queries:
            url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
            try:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                    response = await request_with_retries(
                        client,
                        "GET",
                        url,
                        scope="kvk_public",
                        headers={"User-Agent": settings.HTTP_USER_AGENT},
                    )
                    if response is None:
                        continue
                    response.raise_for_status()
            except Exception:
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            for link in soup.select("a.result__a"):
                href = self._normalize_href(link.get("href", "").strip())
                if not href or href in seen:
                    continue

                title = " ".join(link.get_text(" ", strip=True).split())
                parent = link.find_parent("div")
                snippet_node = parent.find_next_sibling("div") if parent else None
                snippet = " ".join(snippet_node.get_text(" ", strip=True).split()) if snippet_node else ""

                domain = self._normalize_domain(href)
                if not domain or domain in self.BANNED_DOMAINS:
                    continue

                if not any((number in title) or (number in snippet) for number in number_forms if number):
                    continue

                seen.add(href)

                platform = PLATFORM_LABELS.get(domain, domain.split(".")[0].replace("kvk", "KvK").replace("-", " ").title())
                results.append(
                    ProviderMatch(
                        platform=platform,
                        source=self.name,
                        match_type="exact",
                        name=self._clean_name(title, domain),
                        account_handle=None,
                        account_url=href,
                        organization=None,
                        location=None,
                        confidence=0.84,
                        evidence=[f"kvk_public_query={query}"],
                        details={
                            "platform": platform,
                            "title": title,
                            "snippet": snippet[:420],
                            "domain": domain,
                            "source_tier": "officieel",
                            "signal_tier": "officieel",
                        },
                        raw={"href": href, "query": query},
                    )
                )

        return results[:settings.DDG_MAX_RESULTS]
