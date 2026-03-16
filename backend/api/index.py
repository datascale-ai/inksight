from __future__ import annotations

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

app = FastAPI(title="InkSight API", version="1.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8081",
        "http://127.0.0.1:8081",
    ],
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
