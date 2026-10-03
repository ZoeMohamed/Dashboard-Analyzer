"""Validated server-side settings. Secret values never leave this module."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, SecretStr, computed_field, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.contracts import SourceName


def _split_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_values = [str(item) for item in value]
    else:
        raw_values = str(value).replace(";", ",").replace("\n", ",").split(",")
    result: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        item = raw.strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


# Environment variables are intentionally comma/newline separated instead of
# JSON. NoDecode prevents pydantic-settings from trying JSON parsing before our
# safe splitter sees legacy `.env` values from the old POC.
SecretPool = Annotated[list[SecretStr], NoDecode, BeforeValidator(_split_values)]
SourcePool = Annotated[list[SourceName], NoDecode, BeforeValidator(_split_values)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    database_url: SecretStr | None = None
    database_pool_min_size: int = Field(default=1, ge=1, le=10)
    database_pool_max_size: int = Field(default=5, ge=1, le=30)
    database_command_timeout_seconds: float = Field(default=15, ge=1, le=120)
    database_startup_attempts: int = Field(default=3, ge=1, le=8)

    active_sources: SourcePool = Field(default_factory=lambda: list(SourceName))
    source_result_limit: int = Field(default=50, ge=1, le=200)
    snapshot_evidence_limit: int = Field(default=100, ge=1, le=500)
    max_active_topics: int = Field(default=20, ge=1, le=100)
    source_ttl_minutes: int = Field(default=360, ge=5, le=10_080)

    apify_tokens: SecretPool = Field(default_factory=list)
    apify_token: SecretStr | None = None
    apify_key_max_attempts: int = Field(default=2, ge=1, le=5)
    apify_key_cooldown_seconds: int = Field(default=300, ge=10, le=86_400)
    apify_daily_run_limit: int = Field(default=30, ge=1, le=10_000)

    gemini_api_keys: SecretPool = Field(default_factory=list)
    gemini_api_key: SecretStr | None = None
    gemini_key_max_attempts: int = Field(default=2, ge=1, le=5)
    gemini_key_cooldown_seconds: int = Field(default=300, ge=10, le=86_400)
    gemini_monthly_analysis_limit: int = Field(default=300, ge=1, le=1_000_000)
    gemini_model: str = "gemini-3.8-flash"
    gemini_rpm: int = Field(default=8, ge=1, le=1_000)
    gemini_batch_size: int = Field(default=25, ge=1, le=50)

    # Empty means the YouTube adapter uses public search pages instead of the
    # Data API v3; the key is only read on the server.
    youtube_api_key: SecretStr | None = None

    refresh_token: SecretStr | None = None

    @model_validator(mode="after")
    def validate_pool_and_production_requirements(self) -> "Settings":
        if self.database_pool_min_size > self.database_pool_max_size:
            raise ValueError("DATABASE_POOL_MIN_SIZE tidak boleh melebihi maksimum")
        if self.app_env == "production" and self.database_url is None:
            raise ValueError("DATABASE_URL wajib pada production")
        return self

    @computed_field(repr=False)
    @property
    def apify_credentials(self) -> tuple[SecretStr, ...]:
        if self.apify_tokens:
            return tuple(self.apify_tokens)
        return (self.apify_token,) if self.apify_token else ()

    @computed_field(repr=False)
    @property
    def gemini_credentials(self) -> tuple[SecretStr, ...]:
        if self.gemini_api_keys:
            return tuple(self.gemini_api_keys)
        return (self.gemini_api_key,) if self.gemini_api_key else ()

    @property
    def gemini_api_key_values(self) -> list[str]:
        """Plain key values for the server-side Gemini client pool only.

        Deliberately a plain property (not a computed field) so the values never
        appear in serialized settings, health output, or logs.
        """
        return [key.get_secret_value() for key in self.gemini_credentials]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
