"""VoyageMind application configuration."""

import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # AWS / Bedrock
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "amazon.nova-pro-v1:0"
    bedrock_lite_model_id: str = "amazon.nova-lite-v1:0"

    # Redis
    redis_url: str = "redis://localhost:6379"
    cache_ttl_seconds: int = 3600

    # Database
    database_url: str = "postgresql://localhost:5432/voyagemind"

    # API Keys (external services)
    amadeus_api_key: str = ""
    amadeus_api_secret: str = ""
    openweather_api_key: str = ""
    rapidapi_key: str = ""

    # App
    debug: bool = False
    log_level: str = "INFO"
    mock_mode: bool = True  # Use mock data when True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
