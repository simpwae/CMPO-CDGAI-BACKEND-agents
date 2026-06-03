"""Mutable runtime state (Maryam's mode), persisted to the DB.

Seeded from settings, overridable at runtime by the operator, and rehydrated
from the config collection on startup so a restart keeps the chosen mode.
"""
from __future__ import annotations

from app.config import get_settings

_mode: str | None = None


def get_mode() -> str:
    global _mode
    if _mode is None:
        _mode = get_settings().maryam_mode
    return _mode


def set_mode(mode: str) -> str:
    global _mode
    if mode not in ("assist", "auto"):
        raise ValueError("mode must be 'assist' or 'auto'")
    _mode = mode
    return _mode


async def load_mode_from_db() -> str:
    """Rehydrate mode from persisted config (called on startup)."""
    from app.lib.db.factory import get_repo

    repo = await get_repo()
    rows = await repo.find("config", {"key": "maryam_mode"}, limit=1)
    if rows:
        set_mode(rows[0]["value"])
    return get_mode()


async def persist_mode() -> None:
    from app.lib.db.factory import get_repo

    repo = await get_repo()
    await repo.update_one(
        "config", {"key": "maryam_mode"}, {"value": get_mode()}, upsert=True
    )
