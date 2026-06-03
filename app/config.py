"""Central configuration loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM keys
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # Orchestration
    maryam_mode: str = "assist"  # "assist" | "auto"

    # Mongo
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "cdgai"

    # CORS
    frontend_origin: str = "http://localhost:3000"

    # Model routing (configurable; confirm current names at build time)
    claude_model_lead: str = "claude-opus-4-8"        # Maryam, Naqash
    claude_model_default: str = "claude-sonnet-4-6"   # everyone else
    gemini_model_lead: str = "gemini-2.5-pro"
    gemini_model_default: str = "gemini-2.5-flash"


@lru_cache
def get_settings() -> Settings:
    return Settings()
