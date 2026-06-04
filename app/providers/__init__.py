from app.providers.metadata import TelecomMetadataProvider
from app.providers.numverify import NumverifyProvider
from app.providers.search_kvk_api import KvkApiProvider
from app.providers.search_kvk_public import KvkPublicProvider
from app.providers.search_premium_apis import (
    ClearbitLookupProvider,
    HunterLookupProvider,
    NumlookupApiProvider,
    TwilioLookupProvider,
)
from app.providers.serpapi import SerpApiProvider
from app.providers.search_directories import DirectorySearchProvider
from app.providers.search_nl_directory import DutchDirectoryProvider
from app.providers.search_social_hints import SocialHintProvider
from app.providers.search_ddg import DuckDuckGoSearchProvider


def get_providers(route: str = "business"):
    route = (route or "business").lower()

    core = [
        TelecomMetadataProvider(),
        NumverifyProvider(),
    ]

    business = [
        SerpApiProvider(),
        KvkApiProvider(),
        KvkPublicProvider(),
        DutchDirectoryProvider(),
        DirectorySearchProvider(),
        DuckDuckGoSearchProvider(),
        SocialHintProvider(),
        TwilioLookupProvider(),
        NumlookupApiProvider(),
        ClearbitLookupProvider(),
        HunterLookupProvider(),
    ]

    reputation = [
        SerpApiProvider(),
        DuckDuckGoSearchProvider(),
        SocialHintProvider(),
        KvkPublicProvider(),
        DutchDirectoryProvider(),
        DirectorySearchProvider(),
        TwilioLookupProvider(),
        NumlookupApiProvider(),
        ClearbitLookupProvider(),
        HunterLookupProvider(),
    ]

    if route == "spam":
        return core + reputation

    if route in {"consent", "dashboard"}:
        return core

    return core + business
