from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Caller ID Platform"
    API_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "sqlite:///./callerid.db"
    DEFAULT_COUNTRY: str = "NL"
    CACHE_TTL_SECONDS: int = 86400
    MAX_BULK_ITEMS: int = 150
    DEFAULT_BULK_CONCURRENCY: int = 4

    NUMVERIFY_API_KEY: str | None = None
    NUMVERIFY_BASE_URL: str = "https://api.apilayer.com/number_verification/validate"
    SERPAPI_API_KEY: str | None = None
    SERPAPI_BASE_URL: str = "https://serpapi.com/search.json"
    KVK_API_KEY: str | None = None
    KVK_API_BASE_URL: str = "https://api.kvk.nl/api/v2/zoeken"
    TWILIO_ACCOUNT_SID: str | None = None
    TWILIO_AUTH_TOKEN: str | None = None
    TWILIO_LOOKUP_BASE_URL: str = "https://lookups.twilio.com/v2/PhoneNumbers"
    NUMLOOKUP_API_KEY: str | None = None
    NUMLOOKUP_API_BASE_URL: str = "https://api.numlookupapi.com/v1/validate"
    CLEARBIT_API_KEY: str | None = None
    CLEARBIT_API_BASE_URL: str = "https://person.clearbit.com/v2/combined/find"
    HUNTER_API_KEY: str | None = None
    HUNTER_API_BASE_URL: str = "https://api.hunter.io/v2/phone-search"
    ENABLE_DDG_SCRAPING: bool = True
    RESPECT_ROBOTS: bool = True
    HTTP_USER_AGENT: str = "BelRadar/1.0 (+https://belradar.local)"
    DDG_MAX_RESULTS: int = 6
    SEARCH_RETRY_ATTEMPTS: int = 3
    SEARCH_RETRY_DELAY_SECONDS: float = 0.9
    SEARCH_RATE_LIMIT_MS: int = 950
    REQUEST_TIMEOUT_SECONDS: int = 12
    SEARCH_REQUEST_TIMEOUT_SECONDS: int = 15
    CORS_ALLOWED_ORIGINS: str = "*"


settings = Settings()
