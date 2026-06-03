from app.providers.base import ProviderMatch


BASE_SOURCE_WEIGHT = {
    "phonenumbers_metadata": 0.25,
    "numverify": 0.35,
    "duckduckgo_search": 0.74,
    "directory_sites": 0.66,
}


def score_match(match: ProviderMatch, phone_e164: str) -> float:
    score = BASE_SOURCE_WEIGHT.get(match.source, 0.2)
    if match.match_type == "exact":
        score += 0.15
    if match.name:
        score += 0.05
    if match.account_url:
        score += 0.05
    if match.account_handle:
        score += 0.05
    if match.organization:
        score += 0.05
    if phone_e164.replace("+", "") in (match.name or ""):
        score -= 0.1
    return min(max(round(score, 3), 0.0), 1.0)
