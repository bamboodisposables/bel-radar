from __future__ import annotations

from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.providers.base import BasePhoneProvider, ProviderMatch


class KvkPublicProvider(BasePhoneProvider):
    name = "kvk_public"
    description = "KvK publieke zoekresultaten"
    BANNED_DOMAINS = {"duckduckgo.com", "claritycheck.org", "claritycheck.net"}
    KVK_MIRROR_DOMAINS = [
        "kvk.nl",
        "kvkzoeken.nl",
        "mijnbedrijfsgegevens.nl",
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

    def _to_number_forms(self, phone_e164: str) -> list[str]:
        local = phone_e164[3:] if phone_e164.startswith("+31") else phone_e164
        if local:
            local = f"0{local}"
        spaced = local
        if len(local) >= 10:
            spaced = f"{local[:2]} {local[2:4]} {local[4:6]} {local[6:8]} {local[8:]}"
        compact = local.replace(" ", "")
        return [phone_e164, local, spaced, compact]

    async def lookup(self, phone_e164: str, context=None) -> list[ProviderMatch]:
        if not settings.ENABLE_DDG_SCRAPING:
            return []

        number_forms = self._to_number_forms(phone_e164)
        queries = [f'"{number}" KvK' for number in number_forms[:2]]
        queries.append(f'"{number_forms[0]}" site:kvk.nl')
        queries.append(f'"{number_forms[0]}" "KVK-nummer"')
        queries.append(f'"{number_forms[0]}" "KvK zoeken op telefoonnummer"')
        queries.append(f'"{number_forms[0]}" "KvK bedrijf"')
        if number_forms[1]:
            queries.append(f'"{number_forms[1]}" site:kvk.nl')
        for domain in self.KVK_MIRROR_DOMAINS:
            if domain == "kvk.nl":
                continue
            queries.append(f'"{number_forms[0]}" site:{domain}')

        results: list[ProviderMatch] = []
        seen: set[str] = set()
        timeout = httpx.Timeout(settings.REQUEST_TIMEOUT_SECONDS)

        for query in queries:
            url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
            try:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                    response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                    response.raise_for_status()
            except Exception:
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            for link in soup.select("a.result__a")[: settings.DDG_MAX_RESULTS]:
                href = self._normalize_href(link.get("href", "").strip())
                title = " ".join(link.get_text(" ", strip=True).split())
                if not href or href in seen:
                    continue
                seen.add(href)

                parent = link.find_parent("div")
                snippet_node = parent.find_next_sibling("div") if parent else None
                snippet = " ".join(snippet_node.get_text(" ", strip=True).split()) if snippet_node else ""

                domain = self._clean_domain(href)
                if domain in self.BANNED_DOMAINS or not domain:
                    continue

                matched = any(number in title or number in snippet for number in number_forms if number)
                if not matched:
                    continue

                result = ProviderMatch(
                    platform="KvK",
                    source=self.name,
                    match_type="exact",
                    name=title[:255] if title else None,
                    account_handle=None,
                    account_url=href,
                    organization=None,
                    location=None,
                    confidence=0.74,
                    evidence=[f"kvk_public_query={query}"],
                    details={
                        "platform": "KvK",
                        "title": title,
                        "snippet": snippet[:350],
                        "domain": domain,
                        "source_tier": "officieel",
                    },
                    raw={"href": href, "query": query},
                )
                results.append(result)

        return results
