from app.providers.metadata import TelecomMetadataProvider
from app.providers.numverify import NumverifyProvider
from app.providers.search_kvk_api import KvkApiProvider
from app.providers.search_kvk_public import KvkPublicProvider
from app.providers.serpapi import SerpApiProvider
from app.providers.search_directories import DirectorySearchProvider
from app.providers.search_nl_directory import DutchDirectoryProvider
from app.providers.search_ddg import DuckDuckGoSearchProvider


def get_providers():
    return [
        TelecomMetadataProvider(),
        SerpApiProvider(),
        KvkApiProvider(),
        KvkPublicProvider(),
        NumverifyProvider(),
        DuckDuckGoSearchProvider(),
        DutchDirectoryProvider(),
        DirectorySearchProvider(),
    ]
