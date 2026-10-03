from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = ""
    refresh_token: str = ""

    # Apify configuration
    apify_tokens: str = ""
    apify_token: str = ""
    apify_key_max_attempts: int = 4
    apify_key_cooldown_seconds: int = 300

    gemini_model: str = "gemini-3.8-flash"
    gemini_api_keys: str = ""
    gemini_api_key: str = ""
    gemini_key_max_attempts: int = 4
    gemini_key_cooldown_seconds: int = 300

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def gemini_api_key_values(self) -> list[str]:
        import re
        values = [self.gemini_api_key, *re.split(r"[\s,;]+", self.gemini_api_keys)]
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))

    def get_apify_token_pool(self) -> list[str]:
        raw = self.apify_tokens or self.apify_token
        tokens = [t.strip() for t in raw.split(",") if t.strip()]
        return list(dict.fromkeys(tokens))

    def get_gemini_key_pool(self) -> list[str]:
        return self.gemini_api_key_values


@lru_cache
def get_settings() -> Settings:
    return Settings()
