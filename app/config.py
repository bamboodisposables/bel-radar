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
    ENABLE_DDG_SCRAPING: bool = True
    DDG_MAX_RESULTS: int = 6
    REQUEST_TIMEOUT_SECONDS: int = 12
    CORS_ALLOWED_ORIGINS: str = "*"


settings = Settings()
