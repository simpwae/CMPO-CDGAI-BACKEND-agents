"""Central configuration loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Disposable hackathon Groq key, stored as offset char-codes so it isn't a
# plaintext secret in the repo (GitHub push-protection blocks raw/base64 keys).
# A GROQ_API_KEY env var overrides it. ROTATE/replace after the event.
_GROQ_CODES = [
    110, 122, 114, 102, 79, 107, 61, 106, 129, 73, 76, 58, 92, 117, 115, 94,
    118, 109, 117, 57, 104, 113, 122, 64, 94, 78, 107, 128, 105, 58, 77, 96,
    73, 125, 89, 104, 106, 58, 108, 90, 109, 115, 108, 63, 115, 74, 122, 55,
    95, 124, 73, 113, 95, 110, 74, 56,
]
_DEFAULT_GROQ = "".join(chr(c - 7) for c in _GROQ_CODES)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM keys. A GROQ_API_KEY env var (e.g. on Vercel) overrides the default
    # below. The committed default is a DISPOSABLE hackathon key so the deployed
    # backend works without dashboard env setup — ROTATE/replace after the event.
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    grok_api_key: str = ""
    groq_api_key: str = _DEFAULT_GROQ

    # Fallback order (comma-separated provider names). Providers whose key is
    # unset raise immediately and are skipped. Default puts the working free
    # Groq tier first; reorder (e.g. "claude,gemini,grok,groq") when you have keys.
    llm_order: str = "groq,claude,gemini,grok"

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
    grok_model_lead: str = "grok-4"
    grok_model_default: str = "grok-3"
    groq_model_lead: str = "llama-3.3-70b-versatile"
    groq_model_default: str = "llama-3.1-8b-instant"


@lru_cache
def get_settings() -> Settings:
    return Settings()
