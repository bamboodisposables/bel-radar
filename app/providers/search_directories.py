from __future__ import annotations
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

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
    BANNED_DOMAINS = {"duckduckgo.com", "claritycheck.org", "claritycheck.net"}

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
    def _extract_name(title: str, domain: str) -> str | None:
        if not title:
            return None
        clean = " ".join(title.split())
        if domain and domain in clean.lower():
            clean = clean.replace(domain, "").strip()
        return clean[:255] or None

    @staticmethod
    def _extract_location(text: str) -> str | None:
        if not text:
            return None

        for marker in (" - ", " | ", ",", " · "):
            parts = text.split(marker)
            if len(parts) >= 3:
                for part in parts[1:]:
                    token = part.strip()
                    if token and any(ch.isdigit() for ch in token):
                        continue
                    if 3 <= len(token) <= 45:
                        return token
        return None

    @staticmethod
    def _to_number_forms(phone_e164: str) -> list[str]:
        local = phone_e164[3:] if phone_e164.startswith("+31") else phone_e164
        if local:
            local = f"0{local}"
        spaced = local
        if len(local) >= 10:
            spaced = f"{local[:2]} {local[2:4]} {local[4:6]} {local[6:8]} {local[8:]}"
        compact = local.replace(" ", "")
        return [phone_e164, local, spaced, compact]

    async def lookup(self, phone_e164: str, context=None) -> list[ProviderMatch]:
        number_forms = self._to_number_forms(phone_e164)
        queries = [f'"{number_forms[0]}" telefoonboeker', f'"{number_forms[0]}" directory']
        for number in number_forms[:2]:
            queries.extend(f'"{number}" site:{domain}' for domain in self.SEARCH_DOMAINS)

        timeout = httpx.Timeout(settings.REQUEST_TIMEOUT_SECONDS)
        results: list[ProviderMatch] = []
        seen: set[str] = set()

        for query in queries[:20]:
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

                matched = any(number in title or number in snippet for number in number_forms if number)
                platform = PLATFORM_LABELS.get(domain, domain or "Directory")
                name = self._extract_name(title, domain) or title
                location = self._extract_location(f"{title} {snippet}")

                results.append(
                    ProviderMatch(
                        platform=platform,
                        source=self.name,
                        match_type="exact" if matched else "context",
                        name=name,
                        account_handle=None,
                        account_url=href,
                        organization=None,
                        location=location,
                        confidence=0.61 if domain in self.SEARCH_DOMAINS else 0.48,
                        evidence=[f"directory_query={query}", f"directory_domain={domain}"],
                        details={
                            "platform": platform,
                            "title": title,
                            "snippet": snippet[:400],
                            "domain": domain,
                            "source_tier": "openbaar",
                        },
                        raw={"href": href, "query": query},
                    )
                )

        return results
