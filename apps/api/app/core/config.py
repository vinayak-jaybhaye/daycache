"""Application configuration via pydantic-settings.

All settings are read from environment variables or a .env file.
Access the singleton via ``get_settings()``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, PostgresDsn, RedisDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    APP_NAME: str = "DayCache API"
    APP_VERSION: str = "0.1.0"
    APP_ENV: Literal["development", "staging", "production"] = "development"

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------
    SECRET_KEY: SecretStr = SecretStr("change-me-in-production-must-be-32-chars!")

    @field_validator("SECRET_KEY", mode="after")
    @classmethod
    def secret_key_min_length(cls, v: SecretStr) -> SecretStr:
        if len(v.get_secret_value()) < 32:
            msg = "SECRET_KEY must be at least 32 characters"
            raise ValueError(msg)
        return v

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    DATABASE_URL: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://daycache:daycache@localhost:5432/daycache"
    )

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    REDIS_URL: RedisDsn = RedisDsn("redis://localhost:6379/0")

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    CORS_ORIGINS: list[AnyHttpUrl] = [
        AnyHttpUrl("http://localhost:3000"),
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Accept comma-separated string or a JSON list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    LOG_LEVEL: str = "INFO"

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    STORAGE_LOCAL_ROOT: str = "/tmp/daycache"

    # S3 / R2 (only required when STORAGE_BACKEND="s3")
    S3_BUCKET: str = ""
    S3_REGION: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: SecretStr = SecretStr("")
    S3_ENDPOINT_URL: str = ""  # for Cloudflare R2 / MinIO


@lru_cache
def get_settings() -> Settings:
    """Return the cached Settings singleton."""
    return Settings()
