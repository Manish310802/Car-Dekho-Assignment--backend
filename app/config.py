"""Application configuration loaded from environment variables (.env)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM providers ---
    # Primary: OpenAI. Fallback: xAI Grok (OpenAI-API compatible).
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    xai_api_key: str | None = None
    xai_model: str = "grok-2-latest"

    # --- Database ---
    # Neon Postgres connection string. Falls back to a local SQLite file when
    # unset, so the app runs with zero external setup.
    database_url: str | None = None

    # --- CORS ---
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key or self.xai_api_key)


settings = Settings()
