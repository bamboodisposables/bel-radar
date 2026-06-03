from __future__ import annotations

import phonenumbers
from app.config import settings


class PhoneNormalizationError(ValueError):
    pass


def normalize_phone(raw: str) -> str:
    if not raw:
        raise PhoneNormalizationError("Leeg telefoonnummer")
    value = raw.strip()
    try:
        parsed = phonenumbers.parse(value, settings.DEFAULT_COUNTRY)
    except phonenumbers.NumberParseException as exc:
        raise PhoneNormalizationError("Ongeldig nummerformaat") from exc

    if not phonenumbers.is_possible_number(parsed):
        raise PhoneNormalizationError("Nummer is niet mogelijk")
    if not phonenumbers.is_valid_number(parsed):
        raise PhoneNormalizationError("Nummer is niet geldig")

    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
