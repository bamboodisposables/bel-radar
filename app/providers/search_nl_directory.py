from __future__ import annotations
from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.providers.base import BasePhoneProvider, ProviderMatch


PLATFORM_LABELS = {
    "telefoonboek.nl": "Telefoonboek",
    "telefoon-nummer.nl": "Telefoonnummer.nl",
    "telefoongids.nl": "Telefoongids",
    "detelefoonboek.nl": "De TelefoonGids",
    "kvk.nl": "KVK",
}


NETHERLANDS_DOMAINS = [
    "telefoonboek.nl",
    "telefoonnummer.nl",
    "telefoongids.nl",
    "detelefoonboek.nl",
    "kvk.nl",
]


def _is_netherlands_phone(phone_e164: str) -> bool:
    return phone_e164.startswith("+31")


def _to_nl_number_forms(phone_e164: str) -> list[str]:
    local = phone_e164[3:] if phone_e164.startswith("+31") else phone_e164
    if local:
        local = f"0{local}"
    spaced = local
    if len(local) >= 10:
        spaced = f"{local[:2]} {local[2:4]} {local[4:6]} {local[6:8]} {local[8:]}"
    return [phone_e164, local, spaced]


class DutchDirectoryProvider(BasePhoneProvider):
    name = "directory_nl"
    description = "Nederlandse publieke telefoon- en bedrijfsdirectories"

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
        platform = PLATFORM_LABELS.get(domain)
        if platform and platform in clean:
            clean = clean.replace(platform, "").strip()
        if clean:
            return clean[:255]
        return None

    async def lookup(self, phone_e164: str, context=None) -> list[ProviderMatch]:
        if not _is_netherlands_phone(phone_e164):
            return []

        number_forms = _to_nl_number_forms(phone_e164)
        queries = [
            f'"{number}" telefoonnummer',
            f'"{number}" directory',
            f'"{number}" "Nederland"',
        ]
        for domain in NETHERLANDS_DOMAINS:
            queries.append(f'"{number}" site:{domain}')

        timeout = httpx.Timeout(settings.REQUEST_TIMEOUT_SECONDS)
        results: list[ProviderMatch] = []
        seen: set[str] = set()

        for query in queries[:12]:
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
                platform = PLATFORM_LABELS.get(domain) or "Nederlandse directory"

                if not any(number in title or number in snippet for number in number_forms):
                    match_type = "context"
                else:
                    match_type = "exact"

                name = self._extract_name(title, domain)

                results.append(
                    ProviderMatch(
                        platform=platform,
                        source=self.name,
                        match_type=match_type,
                        name=name,
                        account_handle=None,
                        account_url=href,
                        organization=None,
                        location="Nederland",
                        confidence=0.84 if domain in NETHERLANDS_DOMAINS else 0.6,
                        evidence=[f"directory_nl_query={query}", f"directory_nl_domain={domain}"],
                        details={"platform": platform, "title": title, "snippet": snippet[:400], "domain": domain},
                        raw={"href": href, "query": query},
                    )
                )

        return results
