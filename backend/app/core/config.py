"""Application configuration via pydantic-settings.

All secrets come from environment variables / .env — never hard-coded.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "VoyageMind API"
    environment: str = "development"  # development | test | production
    debug: bool = True

    # Infrastructure
    database_url: str = "sqlite:///./voyagemind.db"
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret: str = "dev-only-secret-change-me-32-bytes-min!"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Rate limiting (in-memory, per-IP; auth endpoints get a stricter budget)
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 300
    auth_rate_limit_per_minute: int = 15

    # LLM provider abstraction (spec §14): swap providers via config only
    llm_provider: str = "gemini"  # gemini | ollama | openai
    llm_model: str = ""  # provider-specific model override; adapters have sane defaults
    gemini_api_key: str = ""
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # External data providers (called only from MCP/tools layer)
    travel_mcp_url: str = "http://localhost:8001"
    open_meteo_base_url: str = "https://api.open-meteo.com/v1"
    duffel_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
