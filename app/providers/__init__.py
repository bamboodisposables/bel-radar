from app.providers.metadata import TelecomMetadataProvider
from app.providers.numverify import NumverifyProvider
from app.providers.serpapi import SerpApiProvider
from app.providers.search_directories import DirectorySearchProvider
from app.providers.search_nl_directory import DutchDirectoryProvider
from app.providers.search_ddg import DuckDuckGoSearchProvider


def get_providers():
    return [
        TelecomMetadataProvider(),
        SerpApiProvider(),
        NumverifyProvider(),
        DuckDuckGoSearchProvider(),
        DutchDirectoryProvider(),
        DirectorySearchProvider(),
    ]
