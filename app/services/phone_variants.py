from __future__ import annotations

from collections.abc import Iterable
import re


def _unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if not item:
            continue
        cleaned = item.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _nl_local_variants(clean_digits: str) -> tuple[str, str, str, str]:
    local = clean_digits[2:] if clean_digits.startswith("31") else clean_digits
    if local.startswith("0"):
        local = local[1:]

    national = f"0{local}" if local else ""
    spaced = (
        f"{national[:2]} {national[2:4]} {national[4:6]} {national[6:8]} {national[8:]}"
        if len(national) >= 10
        else (f"{national[:2]} {national[2:4]} {national[4:]}" if len(national) >= 7 else national)
    )
    compact = national.replace(" ", "")

    return national, compact, spaced, local


def build_phone_variants(phone_e164: str) -> list[str]:
    if not phone_e164:
        return []

    digits = re.sub(r"\D", "", phone_e164)
    if not digits:
        return []

    if digits.startswith("0031"):
        digits = digits[2:]

    is_nl = digits.startswith("31")
    national, compact, spaced, local = _nl_local_variants(digits)

    variants = [
        f"+{digits}",
        digits,
        compact,
        spaced,
        national,
        f"0031{digits[2:]}" if is_nl else f"{digits}",
        f"+31{local}" if local else "",
        f"0031{local}" if local else "",
        f"+31{compact[1:]}" if compact.startswith("0") else "",
    ]

    # region-prefix test variant zonder nul, typisch gebruikt in advertenties
    if local and len(local) >= 8:
        variants.append(f"{local[:2]}{local[2:]}")

    return _unique(variants)


def make_query_plan(phone_e164: str, *, base_queries: list[str], broad_queries: list[str] | None = None) -> list[str]:
    variants = build_phone_variants(phone_e164)
    broad_queries = broad_queries or []

    planned: list[str] = []
    for number in variants[:3]:
        for template in base_queries:
            planned.append(template.format(phone=number))

    for variant in variants[:1]:
        for template in broad_queries:
            if "{phone}" in template:
                planned.append(template.format(phone=variant))
            else:
                planned.append(template)

    return _unique(planned)
