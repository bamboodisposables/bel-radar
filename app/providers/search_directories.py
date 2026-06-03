from __future__ import annotations

from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.providers.base import BasePhoneProvider, ProviderMatch
from app.providers.http_utils import request_with_retries
from app.services.phone_variants import build_phone_variants, make_query_plan


PLATFORM_LABELS = {
    "telefoonboek.nl": "Telefoonboek",
    "yellowpages.com": "Yellow Pages",
    "manta.com": "Manta",
    "yelp.com": "Yelp",
    "opencorporates.com": "OpenCorporates",
    "nummer-zoeken.net": "Nummer Zoeken",
    "telefoonnummer.nl": "Telefoonnummer.nl",
    "telefoonnummerzoeken.net": "Telefoonnummerzoeken",
    "bedrijfstelefoongids.nl": "Bedrijfstelefoongids",
    "nationaletelefoongids.nl": "Nationale Telefoongids",
    "telefoongids-nl.nl": "Telefoongids-NL",
    "telefoonnummers.org": "Telefoonnummers.org",
    "kvk.nl": "KvK",
    "kvkzoeken.nl": "KvK Zoeken",
    "mijnbedrijfsgegevens.nl": "Mijn Bedrijfsgegevens",
    "handelsregister.nl": "Handelsregister",
    "telefoonboek.be": "Telefoonboek BE",
    "mijnbedrijfgegevens.nl": "Mijn Bedrijfsgegevens",
}

SEARCH_DOMAINS = [
    "telefoonboek.nl",
    "nummer-zoeken.net",
    "telefoonnummer.nl",
    "telefoongids.nl",
    "detelefoonboek.nl",
    "telefoonnummer.info",
    "telefoonnummers.info",
    "telefoonnummerzoeken.net",
    "bedrijfstelefoongids.nl",
    "nationaletelefoongids.nl",
    "telefoongids-nl.nl",
    "telefoonnummers.org",
    "kvk.nl",
    "kvkzoeken.nl",
    "mijnbedrijfsgegevens.nl",
    "mijnbedrijfgegevens.nl",
    "handelsregister.nl",
    "openbedrijvenregister.nl",
    "kamervoorpagina.nl",
    "opencorporates.com",
    "yellowpages.com",
    "manta.com",
    "yelp.com",
]


def _clean_domain(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    domain = parsed.netloc.lower().replace("www.", "")
    if not domain and "://" in raw_url:
        domain = raw_url.split("://", 1)[1].split("/", 1)[0].lower()
    return domain.strip()


def _normalize_href(raw_url: str) -> str:
    if not raw_url:
        return raw_url
    parsed = urlparse(raw_url)
    if parsed.hostname in {"duckduckgo.com", "www.duckduckgo.com"} and parsed.path in {"/l/", "/l"}:
        next_url = parse_qs(parsed.query).get("uddg", [None])[0]
        if next_url:
            return unquote(next_url)
    return raw_url


def _extract_name(title: str, domain: str) -> str | None:
    if not title:
        return None
    clean = " ".join(title.split())
    if domain and domain in clean.lower():
        clean = clean.replace(domain, "").strip()
    return clean[:255] or None


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


class DirectorySearchProvider(BasePhoneProvider):
    name = "directory_sites"
    description = "Publieke telefoon- en bedrijfsdirectories"
    BANNED_DOMAINS = {"duckduckgo.com", "claritycheck.org", "claritycheck.net"}

    @staticmethod
    def _is_target_domain(domain: str) -> bool:
        return bool(_clean_domain(f"{domain}"))

    async def lookup(self, phone_e164: str, context=None) -> list[ProviderMatch]:
        number_forms = build_phone_variants(phone_e164)
        if not number_forms:
            return []

        queries = make_query_plan(
            phone_e164,
            base_queries=[
                '"{phone}" directory',
                '"{phone}" bedrijfsinformatie',
                '"{phone}" telefoonnummer',
            ],
            broad_queries=[
                '{phone} "bedrijf"',
                '{phone} "KvK"',
                '{phone} "handelsregister"',
            ],
        )

        for domain in SEARCH_DOMAINS:
            for number in number_forms[:2]:
                queries.append(f'"{number}" site:{domain}')

        queries = list(dict.fromkeys(queries))[:30]

        timeout = httpx.Timeout(settings.REQUEST_TIMEOUT_SECONDS)
        results: list[ProviderMatch] = []
        seen: set[str] = set()

        for query in queries[:18]:
            url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
            try:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                    resp = await request_with_retries(
                        client,
                        "GET",
                        url,
                        scope="directory_sites",
                        headers={"User-Agent": settings.HTTP_USER_AGENT},
                    )
                    if resp is None:
                        continue
                    resp.raise_for_status()
            except Exception:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            for link in soup.select("a.result__a")[: settings.DDG_MAX_RESULTS]:
                href = link.get("href", "").strip()
                href = _normalize_href(href)
                if not href or href in seen:
                    continue
                seen.add(href)

                title = " ".join(link.get_text(" ", strip=True).split())
                parent = link.find_parent("div")
                snippet_node = parent.find_next_sibling("div") if parent else None
                snippet = " ".join(snippet_node.get_text(" ", strip=True).split()) if snippet_node else ""

                domain = _clean_domain(href)
                if not domain or domain in self.BANNED_DOMAINS or not self._is_target_domain(domain):
                    continue

                matched = any(number in title or number in snippet for number in number_forms if number)
                platform = PLATFORM_LABELS.get(domain, domain or "Directory")
                name = _extract_name(title, domain) or title
                location = _extract_location(f"{title} {snippet}")

                base_confidence = 0.64 if domain in SEARCH_DOMAINS[:12] else 0.5
                if domain in {"kvk.nl", "kvkzoeken.nl", "mijnbedrijfsgegevens.nl", "handelsregister.nl"}:
                    base_confidence = 0.76

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
                        confidence=base_confidence,
                        evidence=[f"directory_query={query}", f"directory_domain={domain}"],
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
