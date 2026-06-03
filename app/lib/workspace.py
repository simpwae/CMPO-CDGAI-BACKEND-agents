"""Real on-disk workspace where developer agents write project files.

Agents produce multi-file projects; we write them under a per-order project
folder so there are real files/folders on disk (locally / on a persistent host).
On read-only serverless filesystems we fall back to a temp dir; either way the
files are also persisted as artifacts (Mongo) so the dashboard can show the tree.
"""
from __future__ import annotations

import re
from pathlib import Path

# backend/app/lib/workspace.py -> parents[2] == backend/
_PRIMARY_ROOT = Path(__file__).resolve().parents[2] / "workspace"
_FALLBACK_ROOT = Path("/tmp/cdgai-workspace")

_counter = 0


def slugify(text: str, default: str = "project") -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:40].rstrip("-")) or default


def new_project(order: str) -> str:
    """A stable-ish project folder name for one order."""
    global _counter
    _counter += 1
    return f"{slugify(order)}-{_counter:03d}"


def _root() -> Path:
    try:
        _PRIMARY_ROOT.mkdir(parents=True, exist_ok=True)
        return _PRIMARY_ROOT
    except OSError:
        _FALLBACK_ROOT.mkdir(parents=True, exist_ok=True)
        return _FALLBACK_ROOT


def _safe_join(base: Path, relpath: str) -> Path:
    # Prevent path traversal; normalise the LLM-provided path.
    rel = relpath.strip().lstrip("/").replace("\\", "/")
    target = (base / rel).resolve()
    if base.resolve() not in target.parents and target != base.resolve():
        raise ValueError(f"unsafe path: {relpath}")
    return target


def write_file(project: str, relpath: str, content: str) -> str | None:
    """Write one file under workspace/<project>/<relpath>. Returns the path or None."""
    try:
        base = _root() / project
        base.mkdir(parents=True, exist_ok=True)
        target = _safe_join(base, relpath)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target)
    except Exception:
        return None  # disk not writable (e.g. serverless) — artifact still persists


def list_tree(project: str) -> list[str]:
    base = _root() / project
    if not base.exists():
        return []
    return sorted(
        str(p.relative_to(base)).replace("\\", "/")
        for p in base.rglob("*") if p.is_file()
    )
