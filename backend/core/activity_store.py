from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import Request

from .db import get_main_db

logger = logging.getLogger(__name__)


def _client_ip(request: Request | None) -> str:
    if request is None:
        return ""
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
    if forwarded:
        return forwarded
    if request.client:
        return request.client.host or ""
    return ""


def _hash_ip(ip: str) -> str:
    if not ip:
        return ""
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:24]


def _json_safe(metadata: dict[str, Any] | None) -> str:
    if not metadata:
        return "{}"
    try:
        return json.dumps(metadata, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return "{}"


async def log_user_activity(
    user_id: int | None,
    event_name: str,
    *,
    request: Request | None = None,
    source: str = "web",
    path: str = "",
    method: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    """Best-effort activity logging; never break the user-facing request."""
    event = (event_name or "").strip()
    if not event:
        return
    try:
        db = await get_main_db()
        req_path = path or (str(request.url.path) if request else "")
        req_method = method or (request.method if request else "")
        user_agent = (request.headers.get("user-agent") or "")[:300] if request else ""
        await db.execute(
            """
            INSERT INTO user_activity_events
                (user_id, event_name, source, path, method, ip_hash, user_agent, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                event,
                source,
                req_path[:300],
                req_method[:16],
                _hash_ip(_client_ip(request)),
                user_agent,
                _json_safe(metadata),
                datetime.now().isoformat(),
            ),
        )
        await db.commit()
    except Exception:
        logger.warning("[ACTIVITY] Failed to log event=%s user_id=%s", event, user_id, exc_info=True)
