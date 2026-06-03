from __future__ import annotations

from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.providers.base import BasePhoneProvider, ProviderMatch


class KvkPublicProvider(BasePhoneProvider):
    name = "kvk_public"
    description = "KvK publieke zoekresultaten"

    @staticmethod
    def _clean_domain(raw_url: str) -> str:
        parsed = urlparse(raw_url)
        domain = parsed.netloc.lower().replace("www.", "")
        if not domain and "://" in raw_url:
            domain = raw_url.split("://", 1)[1].split("/", 1)[0].lower()
        return domain.strip()

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
        base = number_forms[0]
        queries = [f'"{base}" KvK', f'"{base}" site:kvk.nl']
        if number_forms[1]:
            queries.extend([f'"{number_forms[1]}" KvK', f'"{number_forms[1]}" site:kvk.nl'])

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
                href = link.get("href", "").strip()
                title = " ".join(link.get_text(" ", strip=True).split())
                if not href or href in seen:
                    continue
                seen.add(href)

                parent = link.find_parent("div")
                snippet_node = parent.find_next_sibling("div") if parent else None
                snippet = " ".join(snippet_node.get_text(" ", strip=True).split()) if snippet_node else ""

                matched = any(number in title or number in snippet for number in number_forms)
                if not matched:
                    continue

                domain = self._clean_domain(href)
                result = ProviderMatch(
                    platform="KvK",
                    source=self.name,
                    match_type="exact",
                    name=title[:255] if title else None,
                    account_handle=None,
                    account_url=href,
                    organization=None,
                    location=None,
                    confidence=0.7,
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
