import phonenumbers
from phonenumbers import carrier, geocoder, timezone
from phonenumbers.phonenumberutil import NumberParseException

from app.providers.base import BasePhoneProvider, ProviderMatch


class TelecomMetadataProvider(BasePhoneProvider):
    name = "phonenumbers_metadata"
    description = "Lokale metadata uit phonenumbers: land/streek/tijdzone/aanbieder"

    async def lookup(self, phone_e164: str, context=None) -> list[ProviderMatch]:
        try:
            parsed = phonenumbers.parse(phone_e164, None)
            if not phonenumbers.is_valid_number(parsed):
                return []
        except NumberParseException:
            return []

        return [
            ProviderMatch(
                source=self.name,
                match_type="inconclusive",
                name=carrier.name_for_number(parsed, "en") or "Telefoonlijn",
                organization="telecom metadata",
                location=geocoder.description_for_number(parsed, "en"),
                confidence=0.25,
                details={
                    "country_code": parsed.country_code,
                    "national_number": str(parsed.national_number),
                    "carrier": carrier.name_for_number(parsed, "en"),
                    "time_zones": list(timezone.time_zones_for_number(parsed)),
                    "source_tier": "officieel",
                },
                raw={"e164": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)},
            )
        ]
