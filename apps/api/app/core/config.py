"""Application configuration via pydantic-settings.

All settings are read from environment variables or a .env file.
Access the singleton via ``get_settings()``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    AliasChoices,
    AnyHttpUrl,
    Field,
    PostgresDsn,
    RedisDsn,
    SecretStr,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve workspace root directory to load the shared .env file
_root_dir = Path(__file__).resolve().parents[4]
_env_path = _root_dir / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_env_path), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    APP_NAME: str = "DayCache API"
    APP_VERSION: str = "0.1.0"
    APP_ENV: Literal["development", "staging", "production"] = Field(
        "development",
        validation_alias=AliasChoices("API_ENV", "APP_ENV"),
    )

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------
    # No fallback default in code — must be configured via environment or .env
    SECRET_KEY: SecretStr = Field(
        ...,
        validation_alias=AliasChoices("API_SECRET_KEY", "SECRET_KEY"),
    )

    # ------------------------------------------------------------------
    # Session / Cookie Configuration
    # ------------------------------------------------------------------
    SESSION_TTL: int = 30 * 24 * 60 * 60  # 30 days in seconds
    SESSION_COOKIE_NAME: str = "daycache_session"
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_DOMAIN: str | None = None
    SESSION_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    SESSION_COOKIE_PATH: str = "/"

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
    DATABASE_URL: PostgresDsn = Field(
        ...,
        validation_alias=AliasChoices("DATABASE_URL"),
    )

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    REDIS_URL: RedisDsn = Field(
        ...,
        validation_alias=AliasChoices("REDIS_URL"),
    )

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    CORS_ORIGINS: str | list[AnyHttpUrl] = Field(
        default=[],
        validation_alias=AliasChoices("API_CORS_ORIGINS", "CORS_ORIGINS"),
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
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

    # ------------------------------------------------------------------
    # Media uploads
    # ------------------------------------------------------------------
    MEDIA_MAX_SIZE: int = 50 * 1024 * 1024  # 50 MB — images and videos
    MEDIA_UPLOAD_TTL: int = 300  # presigned PUT URL lifetime in seconds
    MEDIA_READ_URL_TTL: int = 3600  # signed read URL lifetime in seconds

    # ------------------------------------------------------------------
    # AI Embeddings
    # ------------------------------------------------------------------
    AI_EMBEDDING_PROVIDER: Literal["mock", "openai", "gemini", "ollama"] = "mock"
    AI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_API_KEY: SecretStr = SecretStr("")
    GEMINI_API_KEY: SecretStr = SecretStr("")
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # ------------------------------------------------------------------
    # AI LLM
    # ------------------------------------------------------------------
    AI_LLM_PROVIDER: Literal["mock", "openai", "gemini", "ollama"] = "mock"
    AI_LLM_MODEL: str = "gemini-2.0-flash"
    AI_LLM_API_KEY: SecretStr = SecretStr("")

    # ------------------------------------------------------------------
    # Recall Feature Settings
    # ------------------------------------------------------------------
    RECALL_RELEVANCE_THRESHOLD: float = 0.5
    RECALL_RATE_LIMIT: int = 20


@lru_cache
def get_settings() -> Settings:
    """Return the cached Settings singleton."""
    return Settings()  # type: ignore
