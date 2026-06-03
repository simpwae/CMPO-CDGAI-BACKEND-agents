"""Vercel Python entrypoint — exposes the FastAPI ASGI app.

NOTE: Vercel serverless functions are request/response and time-limited, so the
long-lived AG-UI SSE stream and the background delegation cascade are degraded
there. For the full live experience run the backend on a persistent host
(Render/Railway/Fly) and point NEXT_PUBLIC_API_BASE at it.
"""
from app.main import app  # noqa: F401  (Vercel's python runtime serves `app`)
