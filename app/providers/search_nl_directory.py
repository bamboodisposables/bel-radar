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
    "telefoonboek.nl": "Telefoonboek",
    "telefoonnummer.nl": "Telefoonnummer.nl",
    "telefoongids.nl": "Telefoongids",
    "telefoonnummers.info": "Telefoonnummers.info",
    "detelefoongids.nl": "De TelefoonGids",
    "telefoonnummer.info": "Telefoonnummer.info",
    "nummer-zoeken.net": "Nummer Zoeken",
    "telefoonnummerzoeken.net": "Telefoonnummerzoeken",
    "bedrijfstelefoongids.nl": "Bedrijfstelefoongids",
    "nationaletelefoongids.nl": "Nationale Telefoongids",
    "telefoongids-nl.nl": "Telefoongids-NL",
    "telefoonnummers.org": "Telefoonnummers.org",
    "kvk.nl": "KvK",
    "kvkzoeken.nl": "KvK Zoeken",
    "mijnbedrijfsgegevens.nl": "Mijn Bedrijfsgegevens",
    "handelsregister.nl": "Handelsregister",
    "kvkregister.nl": "KvK Register",
    "handelsregister.nl": "Handelsregister",
    "handelsregister-basis": "Handelsregister",
    "kamerregisters.nl": "Kamerregister",
    "mijnbedrijfregister.nl": "Mijn Bedrijfsregister",
}

NETHERLANDS_DOMAINS = [
    "telefoonboek.nl",
    "telefoonnummer.nl",
    "telefoongids.nl",
    "detelefoongids.nl",
    "telefoonnummer.info",
    "telefoonnummers.info",
    "nummer-zoeken.net",
    "telefoonnummerzoeken.net",
    "bedrijfstelefoongids.nl",
    "nationaletelefoongids.nl",
    "telefoonnummers.org",
    "telefoongids-nl.nl",
    "kvk.nl",
    "kvkzoeken.nl",
    "mijnbedrijfsgegevens.nl",
    "handelsregister.nl",
    "kvkregister.nl",
    "kamerregisters.nl",
    "handelsregisternummer.nl",
    "bedrijfsgegevens.nl",
    "mijnbedrijfgegevens.nl",
    "officiele-telefoongids.nl",
]

DUTCH_CITIES = {
    "amsterdam",
    "rotterdam",
    "den haag",
    "utrecht",
    "eindhoven",
    "tilburg",
    "groningen",
    "almere",
    "breda",
    "nijmegen",
    "arnhem",
    "enschede",
    "haarlem",
    "zaanstad",
    "amersfoort",
    "apeldoorn",
    "zoetermeer",
    "zwolle",
    "maastricht",
    "delft",
    "leiden",
    "apeldoorn",
    "lelystad",
    "almelo",
    "helmond",
}

DUTCH_PROVINCES = {
    "noord-holland",
    "zuid-holland",
    "utrecht",
    "noord-brabant",
    "limburg",
    "gelderland",
    "overijssel",
    "drenthe",
    "friesland",
    "groningen",
    "flevoland",
    "zeeland",
    "noord-friesland",
}


def _is_netherlands_phone(phone_e164: str) -> bool:
    return phone_e164.startswith("+31")


def _extract_dutch_location(text: str) -> str | None:
    if not text:
        return None

    lowered = text.lower()

    for province in DUTCH_PROVINCES:
        if re.search(rf"\\b{re.escape(province)}\\b", lowered):
            return province.title()

    for city in DUTCH_CITIES:
        if re.search(rf"\\b{re.escape(city)}\\b", lowered):
            return city.title()

    postal_match = re.search(r"\\b[1-9][0-9]{3}\s?[a-z]{2}\s*,?\s*([a-z\-\' ]{3,40})", lowered)
    if postal_match:
        return postal_match.group(1).strip().title()

    return None


class DutchDirectoryProvider(BasePhoneProvider):
    name = "directory_nl"
    description = "Nederlandse publieke telefoon- en bedrijfsdirectories"

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
    def _extract_name(title: str, domain: str) -> str | None:
        if not title:
            return None

        clean = " ".join(title.split())
        platform = PLATFORM_LABELS.get(domain)
        if platform:
            clean = re.sub(rf"\\s*{re.escape(platform)}\\s*", " ", clean, flags=re.IGNORECASE).strip(" -|•·")
        return clean[:255] if clean else None

    async def lookup(self, phone_e164: str, context=None) -> list[ProviderMatch]:
        if not _is_netherlands_phone(phone_e164) or not settings.ENABLE_DDG_SCRAPING:
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
                '{phone} site:kvk.nl',
                '{phone} site:kvkzoeken.nl',
                '{phone} "Nederland"',
                '{phone} "telefoonnummer"',
                '{phone} "Kamer van Koophandel"',
            ],
        )

        for domain in NETHERLANDS_DOMAINS:
            for number in number_forms[:2]:
                queries.append(f'"{number}" site:{domain}')

        queries = list(dict.fromkeys(queries))[:30]

        results: list[ProviderMatch] = []
        seen: set[str] = set()
        timeout = httpx.Timeout(settings.SEARCH_REQUEST_TIMEOUT_SECONDS)

        for query in queries:
            url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
            try:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                    resp = await request_with_retries(
                        client,
                        "GET",
                        url,
                        scope="directory_nl",
                        headers={"User-Agent": settings.HTTP_USER_AGENT},
                    )
                    if resp is None:
                        continue
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

                location = _extract_dutch_location(f"{title} {snippet}")
                matched = any(number in title or number in snippet for number in number_forms if number)
                platform = PLATFORM_LABELS.get(domain, domain or "Directory.nl")

                results.append(
                    ProviderMatch(
                        platform=platform,
                        source=self.name,
                        match_type="exact" if matched else "context",
                        name=self._extract_name(title, domain) or title,
                        account_handle=None,
                        account_url=href,
                        organization=None,
                        location=location,
                        confidence=0.86 if domain in NETHERLANDS_DOMAINS else 0.6,
                        evidence=[f"directory_nl_query={query}", f"directory_nl_domain={domain}"],
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

        return results[:settings.DDG_MAX_RESULTS + 10]
