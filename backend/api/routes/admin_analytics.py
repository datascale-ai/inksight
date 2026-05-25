from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Request

from core.activity_store import log_user_activity
from core.auth import decode_session_token, get_current_root_user
from core.db import get_main_db

router = APIRouter(tags=["admin-analytics"])

_LEGACY_NGINX_VISITS_TOTAL = 25070
_LEGACY_NGINX_VISITORS_TOTAL = 6052
_LEGACY_NGINX_VISITS_START_DATE = "2026-05-11"


def _optional_user_id(request: Request, ink_session: Optional[str]) -> int | None:
    tokens = []
    if ink_session:
        tokens.append(ink_session)
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        tokens.append(auth[7:])
    for token in tokens:
        payload = decode_session_token(token)
        if not payload or "sub" not in payload:
            continue
        try:
            return int(payload["sub"])
        except (TypeError, ValueError):
            continue
    return None


@router.post("/analytics/pageview")
async def analytics_pageview(
    body: dict,
    request: Request,
    ink_session: Optional[str] = Cookie(default=None),
):
    await log_user_activity(
        _optional_user_id(request, ink_session),
        "page.view",
        request=request,
        source=str(body.get("source") or "webapp"),
        path=str(body.get("path") or request.headers.get("referer") or "/"),
        method="GET",
        metadata={"mac": str(body.get("mac") or "")[:17]},
    )
    return {"ok": True}


async def _scalar(sql: str, params: tuple = ()) -> int | float:
    db = await get_main_db()
    cursor = await db.execute(sql, params)
    row = await cursor.fetchone()
    value = row[0] if row else 0
    return value or 0


async def _rows(sql: str, params: tuple = ()) -> list[dict]:
    db = await get_main_db()
    cursor = await db.execute(sql, params)
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in await cursor.fetchall()]


async def _analytics_overview_payload() -> dict:
    """Root-only analytics summary for the operations dashboard."""
    return {
        "users": {
            "total": await _scalar("SELECT COUNT(*) FROM users"),
            "today_new": await _scalar("SELECT COUNT(*) FROM users WHERE date(created_at)=date('now','localtime')"),
            "new_7d": await _scalar("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now','localtime','-7 days')"),
            "new_30d": await _scalar("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now','localtime','-30 days')"),
            "with_device": await _scalar("SELECT COUNT(DISTINCT user_id) FROM device_memberships WHERE status='active'"),
            "dau": await _scalar(
                """
                SELECT COUNT(DISTINCT user_id) FROM user_activity_events
                WHERE user_id IS NOT NULL
                  AND date(created_at)=date('now','localtime')
                  AND event_name != 'auth.register'
                """
            ),
            "wau": await _scalar(
                """
                SELECT COUNT(DISTINCT user_id) FROM user_activity_events
                WHERE user_id IS NOT NULL
                  AND created_at >= datetime('now','localtime','-7 days')
                  AND event_name != 'auth.register'
                """
            ),
            "mau": await _scalar(
                """
                SELECT COUNT(DISTINCT user_id) FROM user_activity_events
                WHERE user_id IS NOT NULL
                  AND created_at >= datetime('now','localtime','-30 days')
                  AND event_name != 'auth.register'
                """
            ),
            "device_active_24h": await _scalar(
                """
                WITH active_devices AS (
                    SELECT DISTINCT mac FROM device_heartbeats WHERE created_at >= datetime('now','localtime','-24 hours')
                    UNION
                    SELECT DISTINCT mac FROM render_logs WHERE created_at >= datetime('now','localtime','-24 hours')
                )
                SELECT COUNT(DISTINCT dm.user_id)
                FROM device_memberships dm
                JOIN active_devices ad ON ad.mac = dm.mac
                WHERE dm.status = 'active'
                """
            ),
            "login_users_today": await _scalar(
                """
                SELECT COUNT(DISTINCT user_id) FROM user_activity_events
                WHERE user_id IS NOT NULL
                  AND event_name='auth.login'
                  AND date(created_at)=date('now','localtime')
                """
            ),
        },
        "devices": {
            "bound": await _scalar("SELECT COUNT(DISTINCT mac) FROM device_memberships WHERE status='active'"),
            "active_today": await _scalar(
                """
                WITH active_devices AS (
                    SELECT DISTINCT mac FROM device_heartbeats WHERE date(created_at)=date('now','localtime')
                    UNION
                    SELECT DISTINCT mac FROM render_logs WHERE date(created_at)=date('now','localtime')
                )
                SELECT COUNT(*) FROM active_devices
                """
            ),
            "active_7d": await _scalar(
                """
                WITH active_devices AS (
                    SELECT DISTINCT mac FROM device_heartbeats WHERE created_at >= datetime('now','localtime','-7 days')
                    UNION
                    SELECT DISTINCT mac FROM render_logs WHERE created_at >= datetime('now','localtime','-7 days')
                )
                SELECT COUNT(*) FROM active_devices
                """
            ),
            "heartbeats_today": await _scalar("SELECT COUNT(*) FROM device_heartbeats WHERE date(created_at)=date('now','localtime')"),
        },
        "rendering": {
            "today": await _scalar("SELECT COUNT(*) FROM render_logs WHERE date(created_at)=date('now','localtime')"),
            "last_7d": await _scalar("SELECT COUNT(*) FROM render_logs WHERE created_at >= datetime('now','localtime','-7 days')"),
            "avg_ms_today": await _scalar(
                "SELECT ROUND(AVG(render_time_ms), 0) FROM render_logs WHERE date(created_at)=date('now','localtime') AND status='success'"
            ),
            "errors_today": await _scalar("SELECT COUNT(*) FROM render_logs WHERE date(created_at)=date('now','localtime') AND status!='success'"),
            "fallback_today": await _scalar("SELECT COUNT(*) FROM render_logs WHERE date(created_at)=date('now','localtime') AND is_fallback=1"),
        },
        "content": {
            "custom_modes": await _scalar("SELECT COUNT(*) FROM custom_modes"),
            "shared_modes": await _scalar("SELECT COUNT(*) FROM shared_modes WHERE is_active=1"),
            "users_with_llm_config": await _scalar("SELECT COUNT(*) FROM user_llm_config"),
        },
        "traffic": {
            "historical_visits": {
                "total": _LEGACY_NGINX_VISITS_TOTAL
                + await _scalar("SELECT COUNT(*) FROM user_activity_events WHERE event_name='page.view'"),
                "legacy_total": _LEGACY_NGINX_VISITS_TOTAL,
                "tracked_total": await _scalar("SELECT COUNT(*) FROM user_activity_events WHERE event_name='page.view'"),
                "start_date": _LEGACY_NGINX_VISITS_START_DATE,
                "source": "one-time nginx estimate plus page.view events",
            },
            "historical_visitors": {
                "total": _LEGACY_NGINX_VISITORS_TOTAL
                + await _scalar(
                    """
                    SELECT COUNT(*) FROM (
                        SELECT DISTINCT ip_hash, user_agent
                        FROM user_activity_events
                        WHERE event_name='page.view'
                          AND (ip_hash != '' OR user_agent != '')
                    )
                    """
                ),
                "legacy_total": _LEGACY_NGINX_VISITORS_TOTAL,
                "tracked_total": await _scalar(
                    """
                    SELECT COUNT(*) FROM (
                        SELECT DISTINCT ip_hash, user_agent
                        FROM user_activity_events
                        WHERE event_name='page.view'
                          AND (ip_hash != '' OR user_agent != '')
                    )
                    """
                ),
                "start_date": _LEGACY_NGINX_VISITS_START_DATE,
                "source": "one-time nginx ip+ua estimate plus distinct page.view ip+ua",
            },
        },
        "activity": {
            "events_today": await _scalar("SELECT COUNT(*) FROM user_activity_events WHERE date(created_at)=date('now','localtime')"),
            "events_7d": await _scalar("SELECT COUNT(*) FROM user_activity_events WHERE created_at >= datetime('now','localtime','-7 days')"),
            "events_total": await _scalar("SELECT COUNT(*) FROM user_activity_events"),
            "pageviews_today": await _scalar("SELECT COUNT(*) FROM user_activity_events WHERE event_name='page.view' AND date(created_at)=date('now','localtime')"),
            "pageviews_7d": await _scalar("SELECT COUNT(*) FROM user_activity_events WHERE event_name='page.view' AND created_at >= datetime('now','localtime','-7 days')"),
            "pageviews_total": await _scalar("SELECT COUNT(*) FROM user_activity_events WHERE event_name='page.view'"),
            "visitors_today": await _scalar(
                """
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT ip_hash, user_agent
                    FROM user_activity_events
                    WHERE event_name='page.view'
                      AND date(created_at)=date('now','localtime')
                      AND (ip_hash != '' OR user_agent != '')
                )
                """
            ),
            "visitors_7d": await _scalar(
                """
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT ip_hash, user_agent
                    FROM user_activity_events
                    WHERE event_name='page.view'
                      AND created_at >= datetime('now','localtime','-7 days')
                      AND (ip_hash != '' OR user_agent != '')
                )
                """
            ),
            "visitors_total": await _scalar(
                """
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT ip_hash, user_agent
                    FROM user_activity_events
                    WHERE event_name='page.view'
                      AND (ip_hash != '' OR user_agent != '')
                )
                """
            ),
            "logins_today": await _scalar("SELECT COUNT(*) FROM user_activity_events WHERE event_name='auth.login' AND date(created_at)=date('now','localtime')"),
            "logins_7d": await _scalar("SELECT COUNT(*) FROM user_activity_events WHERE event_name='auth.login' AND created_at >= datetime('now','localtime','-7 days')"),
            "logins_total": await _scalar("SELECT COUNT(*) FROM user_activity_events WHERE event_name='auth.login'"),
            "events_today_by_name": await _rows(
                """
                SELECT event_name, COUNT(*) AS count
                FROM user_activity_events
                WHERE date(created_at)=date('now','localtime')
                GROUP BY event_name
                ORDER BY count DESC
                LIMIT 12
                """
            ),
            "events_7d_by_name": await _rows(
                """
                SELECT event_name, COUNT(*) AS count
                FROM user_activity_events
                WHERE created_at >= datetime('now','localtime','-7 days')
                GROUP BY event_name
                ORDER BY count DESC
                LIMIT 12
                """
            ),
            "events_total_by_name": await _rows(
                """
                SELECT event_name, COUNT(*) AS count
                FROM user_activity_events
                GROUP BY event_name
                ORDER BY count DESC
                LIMIT 12
                """
            ),
        },
        "series": {
            "new_users": await _rows(
                """
                SELECT date(created_at) AS day, COUNT(*) AS count
                FROM users
                GROUP BY day
                ORDER BY day DESC
                LIMIT 14
                """
            ),
            "active_devices": await _rows(
                """
                SELECT day, COUNT(DISTINCT mac) AS count
                FROM (
                    SELECT date(created_at) AS day, mac FROM device_heartbeats
                    UNION ALL
                    SELECT date(created_at) AS day, mac FROM render_logs
                )
                GROUP BY day
                ORDER BY day DESC
                LIMIT 14
                """
            ),
            "renders": await _rows(
                """
                SELECT date(created_at) AS day, COUNT(*) AS count
                FROM render_logs
                GROUP BY day
                ORDER BY day DESC
                LIMIT 14
                """
            ),
            "activity_events": await _rows(
                """
                SELECT date(created_at) AS day, COUNT(DISTINCT user_id) AS active_users
                FROM user_activity_events
                WHERE user_id IS NOT NULL AND event_name != 'auth.register'
                GROUP BY day
                ORDER BY day DESC
                LIMIT 14
                """
            ),
        },
        "top": {
            "events": await _rows(
                """
                SELECT event_name, COUNT(*) AS count
                FROM user_activity_events
                WHERE created_at >= datetime('now','localtime','-7 days')
                GROUP BY event_name
                ORDER BY count DESC
                LIMIT 12
                """
            ),
            "modes": await _rows(
                """
                SELECT persona AS mode, COUNT(*) AS count
                FROM render_logs
                WHERE created_at >= datetime('now','localtime','-7 days')
                GROUP BY persona
                ORDER BY count DESC
                LIMIT 12
                """
            ),
        },
    }


@router.get("/admin/analytics/overview")
async def admin_analytics_overview(_: int = Depends(get_current_root_user)):
    return await _analytics_overview_payload()


@router.get("/admin/console/summary")
async def admin_console_summary(_: int = Depends(get_current_root_user)):
    return await _analytics_overview_payload()
