from app.providers.base import ProviderMatch

BASE_SOURCE_WEIGHT = {
    "phonenumbers_metadata": 0.28,
    "numverify": 0.35,
    "serpapi": 0.84,
    "duckduckgo_search": 0.67,
    "duckduckgo": 0.67,
    "directory_sites": 0.62,
    "directory_nl": 0.66,
    "kvk_api": 0.94,
    "kvk_public": 0.8,
    "twilio_lookup": 0.9,
    "numlookup_api": 0.82,
    "clearbit_lookup": 0.86,
    "hunter_lookup": 0.8,
    "social_hints": 0.32,
    "social_platform_hints": 0.32,
}

SOURCE_PRIORITY = {
    "serpapi": 100,
    "kvk_api": 95,
    "kvk_public": 88,
    "directory_nl": 82,
    "directory_sites": 78,
    "duckduckgo_search": 72,
    "duckduckgo": 72,
    "twilio_lookup": 68,
    "numlookup_api": 66,
    "clearbit_lookup": 64,
    "hunter_lookup": 62,
    "numverify": 54,
    "phonenumbers_metadata": 48,
    "social_hints": 32,
    "social_platform_hints": 32,
}

SOURCE_TRUST_BONUS = {
    "officieel": 0.14,
    "openbaar": 0.06,
    "indirect": 0.0,
}

SOURCE_SIGNAL_BONUS_BY_SOURCES = {
    2: 0.06,
    3: 0.1,
    4: 0.14,
    5: 0.18,
}


def score_match(match: ProviderMatch, phone_e164: str) -> float:
    score = BASE_SOURCE_WEIGHT.get(match.source, 0.2)

    if match.match_type == "exact":
        score += 0.15

    if match.name:
        score += 0.05
    if match.account_url:
        score += 0.06
    if match.account_handle:
        score += 0.05
    if match.organization:
        score += 0.05
    if match.location:
        score += 0.03

    if match.source in {"kvk_api", "kvk_public", "directory_nl", "directory_sites", "search_kvk_public", "search_nl_directory"}:
        score += 0.02

    source_tier = (match.details or {}).get("source_tier")
    score += SOURCE_TRUST_BONUS.get(source_tier, 0.0)

    if phone_e164.replace("+", "") in (match.name or ""):
        score -= 0.1

    return min(max(round(score, 3), 0.0), 1.0)


def score_multisource(confidence: float, source_count: int) -> float:
    if source_count >= 2:
        bonus = SOURCE_SIGNAL_BONUS_BY_SOURCES.get(source_count, 0.2)
        confidence = confidence + bonus
    return min(max(round(confidence, 3), 0.0), 1.0)


def source_priority_rank(source: str | None) -> int:
    return SOURCE_PRIORITY.get(source or "", 0)
