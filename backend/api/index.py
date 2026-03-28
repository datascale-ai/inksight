from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import api_routers, page_routers
from api.shared import (
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
    inksight_error_handler,
    lifespan,
    limiter,
)
from core.errors import InkSightError


def _build_cors_settings() -> tuple[list[str], str | None]:
    """Resolve allowed browser Origins for CORS.

    - Default: local Next.js + Expo Web on 3000 / 8081.
    - INKSIGHT_CORS_ORIGINS: comma-separated extra origins (e.g. LAN IP for phone / Expo).
    - INKSIGHT_CORS_ALLOW_LAN=1: allow any http(s) Origin on private IPv4 + localhost (dev only).
    """
    defaults = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8081",
        "http://127.0.0.1:8081",
    ]
    seen = set(defaults)
    origins = list(defaults)
    extra = os.getenv("INKSIGHT_CORS_ORIGINS", "")
    for part in extra.split(","):
        origin = part.strip()
        if origin and origin not in seen:
            seen.add(origin)
            origins.append(origin)

    origin_regex = None
    flag = os.getenv("INKSIGHT_CORS_ALLOW_LAN", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        # RFC1918 + loopback; any port (Expo / dev servers on arbitrary ports).
        origin_regex = (
            r"^https?://("
            r"localhost|127\.0\.0\.1"
            r"|192\.168\.\d{1,3}\.\d{1,3}"
            r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
            r"|172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
            r")(?::\d+)?$"
        )
    return origins, origin_regex


_cors_origins, _cors_origin_regex = _build_cors_settings()

app = FastAPI(title="InkSight API", version="1.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=_cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_exception_handler(InkSightError, inksight_error_handler)

for router in api_routers:
    app.include_router(router, prefix="/api")
    app.include_router(router, prefix="/api/v1")

for router in page_routers:
    app.include_router(router)
