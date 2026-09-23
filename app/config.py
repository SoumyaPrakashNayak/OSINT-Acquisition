"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable overrides."""

    app_name: str = "OSINT Intelligence Component"
    app_version: str = "0.1.0"
    debug: bool = False

    # Search Provider settings
    # Options: "mock", "searxng", "serpapi", "tavily", "custom"
    search_provider: str = "mock"
    search_api_key: str | None = None
    search_api_url: str | None = None
    search_timeout_seconds: float = 10.0
    max_results_per_query: int = 10

    # Acquisition / Web Fetcher settings
    # Options: "mock", "http"
    fetcher_type: str = "mock"
    fetch_timeout_seconds: float = 15.0
    max_response_size_mb: int = 10
    max_redirects: int = 5
    max_concurrent_fetches: int = 5
    fetch_user_agent: str = "SIRIS-OSINT-Component/0.1"

    # Extraction settings (Phase 4)
    min_content_words: int = 50
    high_content_words: int = 200
    max_extracted_links: int = 100

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
