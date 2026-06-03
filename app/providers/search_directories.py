from __future__ import annotations
from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.providers.base import BasePhoneProvider, ProviderMatch


PLATFORM_LABELS = {
    "telefoonboek.nl": "Telefoonboek",
    "yellowpages.com": "Yellow Pages",
    "manta.com": "Manta",
    "yelp.com": "Yelp",
    "opencorporates.com": "OpenCorporates",
}


class DirectorySearchProvider(BasePhoneProvider):
    name = "directory_sites"
    description = "Publieke telefoon- en bedrijfsdirectories"

    SEARCH_DOMAINS = [
        "telefoonboek.nl",
        "yellowpages.com",
        "manta.com",
        "yelp.com",
        "opencorporates.com",
    ]

    @staticmethod
    def _clean_domain(raw_url: str) -> str:
        parsed = urlparse(raw_url)
        domain = parsed.netloc.lower().replace("www.", "")
        if not domain and "://" in raw_url:
            domain = raw_url.split("://", 1)[1].split("/", 1)[0].lower()
        return domain.strip()

    @staticmethod
    def _extract_name(title: str, domain: str) -> str | None:
        if not title:
            return None
        clean = " ".join(title.split())
        if domain and domain in clean.lower():
            clean = clean.replace(domain, "").strip()
        return clean or None

    async def lookup(self, phone_e164: str, context=None) -> list[ProviderMatch]:
        queries = [f'"{phone_e164}" telefoonboeker', f'"{phone_e164}" directory']
        queries.extend(f'"{phone_e164}" site:{domain}' for domain in self.SEARCH_DOMAINS)

        timeout = httpx.Timeout(settings.REQUEST_TIMEOUT_SECONDS)
        results: list[ProviderMatch] = []
        seen: set[str] = set()

        for query in queries:
            url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
            try:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                    resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                    resp.raise_for_status()
            except Exception:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select("a.result__a")

            for link in items[: settings.DDG_MAX_RESULTS]:
                href = link.get("href", "").strip()
                title = " ".join(link.get_text(" ", strip=True).split())
                if not href or href in seen:
                    continue
                seen.add(href)

                parent = link.find_parent("div")
                snippet_node = parent.find_next_sibling("div") if parent else None
                snippet = " ".join(snippet_node.get_text(" ", strip=True).split()) if snippet_node else ""
                domain = self._clean_domain(href)

                matched = phone_e164 in title or phone_e164 in snippet
                platform = PLATFORM_LABELS.get(domain, domain or "Directory")
                name = self._extract_name(title, domain)

                results.append(
                    ProviderMatch(
                        platform=platform,
                        source=self.name,
                        match_type="exact" if matched else "context",
                        name=name[:255] if name else None,
                        account_handle=None,
                        account_url=href,
                        confidence=0.61 if domain in self.SEARCH_DOMAINS else 0.48,
                        evidence=[f"directory_query={query}", f"directory_domain={domain}"],
                        details={"platform": platform, "title": title, "snippet": snippet[:400], "domain": domain},
                        raw={"href": href, "query": query},
                    )
                )

        return results
