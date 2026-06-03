from __future__ import annotations
import re
from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.providers.base import BasePhoneProvider, ProviderMatch


PLATFORM_LABELS = {
    "telefoonboek.nl": "Telefoonboek",
    "telefoonnummer.nl": "Telefoonnummer.nl",
    "telefoongids.nl": "Telefoongids",
    "detelefoonboek.nl": "De TelefoonGids",
    "kvk.nl": "KvK",
}

NETHERLANDS_DOMAINS = [
    "telefoonboek.nl",
    "telefoonnummer.nl",
    "telefoongids.nl",
    "detelefoonboek.nl",
    "kvk.nl",
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
    "middelburg",
    "leiden",
    "maastricht",
    "delft",
    "heemskerk",
    "alkmaar",
    "s-hertogenbosch",
    "assen",
    "venlo",
    "dordrecht",
    "hilversum",
    "helmond",
    "lelystad",
    "roosendaal",
    "spijkenisse",
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


def _to_nl_number_forms(phone_e164: str) -> list[str]:
    local = phone_e164[3:] if phone_e164.startswith("+31") else phone_e164
    if local:
        local = f"0{local}"
    spaced = local
    if len(local) >= 10:
        spaced = f"{local[:2]} {local[2:4]} {local[4:6]} {local[6:8]} {local[8:]}"
    compact = local.replace(" ", "")
    return [phone_e164, local, spaced, compact]


def _extract_dutch_location(text: str) -> str | None:
    if not text:
        return None

    lowered = text.lower()

    for province in DUTCH_PROVINCES:
        if re.search(rf"\b{re.escape(province)}\b", lowered):
            return province.title()

    for city in DUTCH_CITIES:
        if re.search(rf"\b{re.escape(city)}\b", lowered):
            return city.title()

    postal_match = re.search(
        r"\b[1-9][0-9]{3}\s?[a-z]{2}\s*,?\s*([a-z\-\' ]{3,40})",
        lowered,
    )
    if postal_match:
        return postal_match.group(1).strip().title()

    return None


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
        if platform and platform.lower() in clean.lower():
            clean = re.sub(rf"\s*{re.escape(platform)}\s*", " ", clean, flags=re.IGNORECASE).strip()
        return clean[:255] or None

    async def lookup(self, phone_e164: str, context=None) -> list[ProviderMatch]:
        if not _is_netherlands_phone(phone_e164):
            return []

        number_forms = _to_nl_number_forms(phone_e164)
        queries = [f'"{number}" telefoonnummer' for number in number_forms[:2]]
        for number in number_forms[:1]:
            queries.extend(
                [
                    f'"{number}" directory',
                    f'"{number}" "Nederland"',
                    f'"{number}" kvk',
                ]
            )
        for domain in NETHERLANDS_DOMAINS:
            queries.append(f'"{number_forms[0]}" site:{domain}')

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
                title = " ".join(link.get_text(" ", strip=True).split())
                if not href or href in seen:
                    continue
                seen.add(href)

                parent = link.find_parent("div")
                snippet_node = parent.find_next_sibling("div") if parent else None
                snippet = " ".join(snippet_node.get_text(" ", strip=True).split()) if snippet_node else ""
                domain = self._clean_domain(href)
                location = _extract_dutch_location(f"{title} {snippet}")
                platform = PLATFORM_LABELS.get(domain, domain or "Directory.nl")

                matched = any(number in title or number in snippet for number in number_forms)
                match_type = "exact" if matched else "context"
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
                        location=location,
                        confidence=0.84 if domain in NETHERLANDS_DOMAINS else 0.6,
                        evidence=[f"directory_nl_query={query}", f"directory_nl_domain={domain}"],
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
