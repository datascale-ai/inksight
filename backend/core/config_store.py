from __future__ import annotations

import os
import json
import logging
import secrets
import hashlib
import aiosqlite
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
PAIR_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"

from migrations import run_main_db_migrations
from .db import get_main_db
from .config import (
    DEFAULT_CITY,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_MODEL,
    DEFAULT_IMAGE_PROVIDER,
    DEFAULT_IMAGE_MODEL,
    DEFAULT_LANGUAGE,
    DEFAULT_CONTENT_TONE,
    DEFAULT_MODES,
    DEFAULT_REFRESH_STRATEGY,
    DEFAULT_REFRESH_INTERVAL,
)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "inksight.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac TEXT NOT NULL,
                nickname TEXT DEFAULT '',
                modes TEXT DEFAULT 'STOIC,ROAST,ZEN,DAILY',
                refresh_strategy TEXT DEFAULT 'random',
                character_tones TEXT DEFAULT '',
                language TEXT DEFAULT 'zh',
                content_tone TEXT DEFAULT 'neutral',
                city TEXT DEFAULT '杭州',
                refresh_interval INTEGER DEFAULT 60,
                llm_provider TEXT DEFAULT 'deepseek',
                llm_model TEXT DEFAULT 'deepseek-chat',
                image_provider TEXT DEFAULT 'aliyun',
                image_model TEXT DEFAULT 'qwen-image-max',
                countdown_events TEXT DEFAULT '[]',
                time_slot_rules TEXT DEFAULT '[]',
                memo_text TEXT DEFAULT '',
                llm_api_key TEXT DEFAULT '',
                image_api_key TEXT DEFAULT '',
                mode_overrides TEXT DEFAULT '{}',
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)

        await db.execute("CREATE INDEX IF NOT EXISTS idx_configs_mac ON configs(mac)")

        # Device state table for persisting runtime state (cycle_index, etc.)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS device_state (
                mac TEXT PRIMARY KEY,
                cycle_index INTEGER DEFAULT 0,
                last_persona TEXT DEFAULT '',
                last_refresh_at TEXT DEFAULT '',
                pending_refresh INTEGER DEFAULT 0,
                pending_mode TEXT DEFAULT '',
                last_state_poll_at TEXT DEFAULT '',
                auth_token TEXT DEFAULT '',
                runtime_mode TEXT DEFAULT 'interval',
                expected_refresh_min INTEGER DEFAULT 0,
                last_reconnect_regen_at TEXT DEFAULT '',
                updated_at TEXT NOT NULL
            )
        """)

        # User system tables
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                mac TEXT NOT NULL,
                nickname TEXT DEFAULT '',
                bound_at TEXT NOT NULL,
                UNIQUE(user_id, mac),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_user_devices_user ON user_devices(user_id)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS device_memberships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                status TEXT NOT NULL DEFAULT 'active',
                nickname TEXT DEFAULT '',
                granted_by INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(mac, user_id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_device_memberships_user ON device_memberships(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_device_memberships_mac ON device_memberships(mac)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS device_claim_tokens (
                token_hash TEXT PRIMARY KEY,
                mac TEXT NOT NULL,
                nonce TEXT NOT NULL,
                pair_code TEXT DEFAULT '',
                source TEXT DEFAULT '',
                expires_at TEXT NOT NULL,
                used_at TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_device_claim_tokens_mac ON device_claim_tokens(mac)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_device_claim_tokens_pair_code ON device_claim_tokens(pair_code)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS device_access_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac TEXT NOT NULL,
                requester_user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                reviewed_by INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(mac, requester_user_id, status),
                FOREIGN KEY (requester_user_id) REFERENCES users(id)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_device_access_requests_mac ON device_access_requests(mac)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_device_access_requests_user ON device_access_requests(requester_user_id)")

        await run_main_db_migrations(
            db,
            defaults={
                "image_provider": DEFAULT_IMAGE_PROVIDER,
                "image_model": DEFAULT_IMAGE_MODEL,
            },
        )
        await _migrate_legacy_user_devices(db)
        await db.commit()


# ── User system ─────────────────────────────────────────────


def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return salt.hex() + ":" + dk.hex(), salt.hex()


def _verify_password(password: str, stored: str) -> bool:
    parts = stored.split(":", 1)
    if len(parts) != 2:
        return False
    salt = bytes.fromhex(parts[0])
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return secrets.compare_digest(parts[0] + ":" + dk.hex(), stored)


async def create_user(username: str, password: str) -> int | None:
    pw_hash, _ = _hash_password(password)
    now = datetime.now().isoformat()
    db = await get_main_db()
    try:
        cursor = await db.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username.strip(), pw_hash, now),
        )
        await db.commit()
        return cursor.lastrowid
    except aiosqlite.IntegrityError:
        return None


async def get_user_by_username(username: str) -> dict | None:
    db = await get_main_db()
    cursor = await db.execute(
        "SELECT id, username, password_hash, created_at FROM users WHERE username = ?",
        (username.strip(),),
    )
    row = await cursor.fetchone()
    if not row:
        return None
    return {"id": row[0], "username": row[1], "password_hash": row[2], "created_at": row[3]}


async def authenticate_user(username: str, password: str) -> dict | None:
    user = await get_user_by_username(username)
    if not user:
        return None
    if not _verify_password(password, user["password_hash"]):
        return None
    return user


async def _migrate_legacy_user_devices(db) -> None:
    cursor = await db.execute(
        """SELECT mac, user_id, nickname, bound_at
           FROM user_devices
           ORDER BY mac ASC, bound_at ASC, id ASC"""
    )
    rows = await cursor.fetchall()
    current_mac = ""
    owner_user_id = 0
    for mac, user_id, nickname, bound_at in rows:
        normalized_mac = str(mac or "").upper()
        if not normalized_mac:
            continue
        role = "member"
        granted_by = owner_user_id or None
        if normalized_mac != current_mac:
            current_mac = normalized_mac
            owner_user_id = int(user_id)
            role = "owner"
            granted_by = None
        await db.execute(
            """INSERT OR IGNORE INTO device_memberships
               (mac, user_id, role, status, nickname, granted_by, created_at, updated_at)
               VALUES (?, ?, ?, 'active', ?, ?, ?, ?)""",
            (
                normalized_mac,
                user_id,
                role,
                nickname or "",
                granted_by,
                bound_at or datetime.now().isoformat(),
                datetime.now().isoformat(),
            ),
        )


def _claim_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _normalize_pair_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


async def _generate_pair_code(db, now_iso: str) -> str:
    for _ in range(20):
        code = "".join(secrets.choice(PAIR_CODE_ALPHABET) for _ in range(8))
        cursor = await db.execute(
            """SELECT 1
               FROM device_claim_tokens
               WHERE pair_code = ? AND used_at = '' AND expires_at > ?
               LIMIT 1""",
            (code, now_iso),
        )
        if not await cursor.fetchone():
            return code
    raise RuntimeError("failed to generate pair code")


async def _is_pair_code_available(db, pair_code: str, now_iso: str) -> bool:
    cursor = await db.execute(
        """SELECT 1
           FROM device_claim_tokens
           WHERE pair_code = ? AND used_at = '' AND expires_at > ?
           LIMIT 1""",
        (pair_code, now_iso),
    )
    return (await cursor.fetchone()) is None


async def get_device_membership(
    mac: str,
    user_id: int,
    *,
    include_pending: bool = False,
) -> dict | None:
    db = await get_main_db()
    query = """SELECT dm.mac, dm.user_id, dm.role, dm.status, dm.nickname,
                      dm.granted_by, dm.created_at, dm.updated_at, u.username
               FROM device_memberships dm
               JOIN users u ON u.id = dm.user_id
               WHERE dm.mac = ? AND dm.user_id = ?"""
    params: list[object] = [mac.upper(), user_id]
    if not include_pending:
        query += " AND dm.status = 'active'"
    query += " LIMIT 1"
    cursor = await db.execute(query, tuple(params))
    row = await cursor.fetchone()
    if not row:
        return None
    return {
        "mac": row[0],
        "user_id": row[1],
        "role": row[2],
        "status": row[3],
        "nickname": row[4],
        "granted_by": row[5],
        "created_at": row[6],
        "updated_at": row[7],
        "username": row[8],
    }


async def get_device_owner(mac: str) -> dict | None:
    db = await get_main_db()
    cursor = await db.execute(
        """SELECT dm.mac, dm.user_id, dm.nickname, dm.created_at, u.username
           FROM device_memberships dm
           JOIN users u ON u.id = dm.user_id
           WHERE dm.mac = ? AND dm.role = 'owner' AND dm.status = 'active'
           LIMIT 1""",
        (mac.upper(),),
    )
    row = await cursor.fetchone()
    if not row:
        return None
    return {
        "mac": row[0],
        "user_id": row[1],
        "nickname": row[2],
        "created_at": row[3],
        "username": row[4],
    }


async def has_active_membership(mac: str, user_id: int) -> bool:
    membership = await get_device_membership(mac, user_id)
    return membership is not None and membership.get("status") == "active"


async def is_device_owner(mac: str, user_id: int) -> bool:
    membership = await get_device_membership(mac, user_id)
    return membership is not None and membership.get("role") == "owner"


async def upsert_device_membership(
    mac: str,
    user_id: int,
    *,
    role: str,
    status: str = "active",
    nickname: str = "",
    granted_by: int | None = None,
) -> dict:
    now = datetime.now().isoformat()
    db = await get_main_db()
    await db.execute(
        """INSERT INTO device_memberships
           (mac, user_id, role, status, nickname, granted_by, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(mac, user_id) DO UPDATE SET
               role = excluded.role,
               status = excluded.status,
               nickname = CASE
                   WHEN excluded.nickname != '' THEN excluded.nickname
                   ELSE device_memberships.nickname
               END,
               granted_by = excluded.granted_by,
               updated_at = excluded.updated_at""",
        (mac.upper(), user_id, role, status, nickname, granted_by, now, now),
    )
    await db.commit()
    return await get_device_membership(mac, user_id, include_pending=True)


async def create_claim_token(
    mac: str,
    source: str = "portal",
    ttl_minutes: int = 10,
    preferred_pair_code: str = "",
) -> dict | None:
    now = datetime.now()
    token = secrets.token_urlsafe(32)
    now_iso = now.isoformat()
    db = await get_main_db()
    await db.execute(
        "DELETE FROM device_claim_tokens WHERE used_at != '' OR expires_at <= ?",
        (now_iso,),
    )
    normalized_pair_code = _normalize_pair_code(preferred_pair_code)
    if normalized_pair_code:
        if not await _is_pair_code_available(db, normalized_pair_code, now_iso):
            return None
        pair_code = normalized_pair_code
    else:
        pair_code = await _generate_pair_code(db, now_iso)
    await db.execute(
        """INSERT INTO device_claim_tokens
           (token_hash, mac, nonce, pair_code, source, expires_at, used_at, created_at)
           VALUES (?, ?, ?, ?, ?, ?, '', ?)""",
        (
            _claim_token_hash(token),
            mac.upper(),
            secrets.token_hex(8),
            pair_code,
            source,
            (now + timedelta(minutes=ttl_minutes)).isoformat(),
            now_iso,
        ),
    )
    await db.commit()
    return {
        "token": token,
        "pair_code": pair_code,
        "expires_at": (now + timedelta(minutes=ttl_minutes)).isoformat(),
    }


async def get_pending_access_request(mac: str, requester_user_id: int) -> dict | None:
    db = await get_main_db()
    cursor = await db.execute(
        """SELECT id, mac, requester_user_id, status, reviewed_by, created_at, updated_at
           FROM device_access_requests
           WHERE mac = ? AND requester_user_id = ? AND status = 'pending'
           LIMIT 1""",
        (mac.upper(), requester_user_id),
    )
    row = await cursor.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "mac": row[1],
        "requester_user_id": row[2],
        "status": row[3],
        "reviewed_by": row[4],
        "created_at": row[5],
        "updated_at": row[6],
    }


async def create_access_request(mac: str, requester_user_id: int) -> dict:
    existing = await get_pending_access_request(mac, requester_user_id)
    if existing:
        return existing
    now = datetime.now().isoformat()
    db = await get_main_db()
    cursor = await db.execute(
        """INSERT INTO device_access_requests
           (mac, requester_user_id, status, reviewed_by, created_at, updated_at)
           VALUES (?, ?, 'pending', NULL, ?, ?)""",
        (mac.upper(), requester_user_id, now, now),
    )
    await db.commit()
    return {
        "id": cursor.lastrowid,
        "mac": mac.upper(),
        "requester_user_id": requester_user_id,
        "status": "pending",
        "reviewed_by": None,
        "created_at": now,
        "updated_at": now,
    }


async def consume_claim_token(user_id: int, token: str = "", pair_code: str = "") -> dict:
    now = datetime.now().isoformat()
    db = await get_main_db()
    normalized_pair_code = _normalize_pair_code(pair_code)
    if token:
        cursor = await db.execute(
            """SELECT token_hash, mac, expires_at, used_at
               FROM device_claim_tokens
               WHERE token_hash = ?
               LIMIT 1""",
            (_claim_token_hash(token),),
        )
    elif normalized_pair_code:
        cursor = await db.execute(
            """SELECT token_hash, mac, expires_at, used_at
               FROM device_claim_tokens
               WHERE pair_code = ?
                 AND used_at = ''
                 AND expires_at > ?
               ORDER BY created_at DESC
               LIMIT 1""",
            (normalized_pair_code, now),
        )
    else:
        return {"status": "invalid"}
    row = await cursor.fetchone()
    if not row:
        return {"status": "invalid"}
    token_hash, mac, expires_at, used_at = row
    if used_at or expires_at <= now:
        return {"status": "expired"}
    await db.execute(
        "UPDATE device_claim_tokens SET used_at = ? WHERE token_hash = ?",
        (now, token_hash),
    )
    await db.commit()

    existing = await get_device_membership(mac, user_id, include_pending=True)
    if existing and existing.get("status") == "active":
        return {"status": "already_member", "mac": mac, "role": existing.get("role")}

    owner = await get_device_owner(mac)
    if not owner:
        membership = await upsert_device_membership(mac, user_id, role="owner", status="active")
        return {"status": "claimed", "mac": mac, "role": membership.get("role", "owner")}

    pending = await create_access_request(mac, user_id)
    return {
        "status": "pending_approval",
        "mac": mac,
        "request_id": pending["id"],
        "owner_username": owner.get("username", ""),
    }


async def bind_device(user_id: int, mac: str, nickname: str = "") -> dict:
    normalized_mac = mac.upper()
    existing = await get_device_membership(normalized_mac, user_id, include_pending=True)
    if existing and existing.get("status") == "active":
        if nickname and nickname != existing.get("nickname", ""):
            await upsert_device_membership(
                normalized_mac,
                user_id,
                role=existing.get("role", "member"),
                status="active",
                nickname=nickname,
                granted_by=existing.get("granted_by"),
            )
        return {"status": "active", "role": existing.get("role", "member")}
    if existing and existing.get("status") == "pending":
        return {"status": "pending_approval"}
    owner = await get_device_owner(normalized_mac)
    if not owner:
        membership = await upsert_device_membership(
            normalized_mac,
            user_id,
            role="owner",
            status="active",
            nickname=nickname,
        )
        return {"status": "claimed", "role": membership.get("role", "owner")}
    await create_access_request(normalized_mac, user_id)
    return {"status": "pending_approval"}


async def unbind_device(user_id: int, mac: str) -> str:
    db = await get_main_db()
    membership = await get_device_membership(mac, user_id)
    if not membership:
        return "not_found"
    if membership.get("role") == "owner":
        cursor = await db.execute(
            """SELECT COUNT(1)
               FROM device_memberships
               WHERE mac = ? AND status = 'active' AND user_id != ?""",
            (mac.upper(), user_id),
        )
        row = await cursor.fetchone()
        if row and row[0]:
            return "owner_has_members"
    await db.execute(
        "DELETE FROM device_memberships WHERE user_id = ? AND mac = ?",
        (user_id, mac.upper()),
    )
    await db.execute(
        "DELETE FROM device_access_requests WHERE requester_user_id = ? AND mac = ?",
        (user_id, mac.upper()),
    )
    await db.commit()
    return "ok"


async def get_user_devices(user_id: int) -> list[dict]:
    db = await get_main_db()
    cursor = await db.execute(
        """SELECT dm.mac, dm.nickname, dm.created_at, dm.role, dm.status,
                  dh.last_seen
           FROM device_memberships dm
           LEFT JOIN (
               SELECT mac, MAX(created_at) as last_seen
               FROM device_heartbeats
               GROUP BY mac
           ) dh ON dm.mac = dh.mac
           WHERE dm.user_id = ? AND dm.status = 'active'
           ORDER BY dm.created_at DESC""",
        (user_id,),
    )
    rows = await cursor.fetchall()
    return [
        {
            "mac": r[0],
            "nickname": r[1],
            "bound_at": r[2],
            "role": r[3],
            "status": r[4],
            "last_seen": r[5],
        }
        for r in rows
    ]


async def get_device_members(mac: str) -> list[dict]:
    db = await get_main_db()
    cursor = await db.execute(
        """SELECT dm.user_id, u.username, dm.role, dm.status, dm.nickname,
                  dm.granted_by, dm.created_at, dm.updated_at
           FROM device_memberships dm
           JOIN users u ON u.id = dm.user_id
           WHERE dm.mac = ? AND dm.status = 'active'
           ORDER BY CASE dm.role WHEN 'owner' THEN 0 ELSE 1 END, dm.created_at ASC""",
        (mac.upper(),),
    )
    rows = await cursor.fetchall()
    return [
        {
            "user_id": row[0],
            "username": row[1],
            "role": row[2],
            "status": row[3],
            "nickname": row[4],
            "granted_by": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }
        for row in rows
    ]


async def get_pending_requests_for_owner(owner_user_id: int) -> list[dict]:
    db = await get_main_db()
    cursor = await db.execute(
        """SELECT dar.id, dar.mac, dar.requester_user_id, u.username, dar.status,
                  dar.created_at, dar.updated_at
           FROM device_access_requests dar
           JOIN users u ON u.id = dar.requester_user_id
           JOIN device_memberships dm
             ON dm.mac = dar.mac AND dm.user_id = ? AND dm.role = 'owner' AND dm.status = 'active'
           WHERE dar.status = 'pending'
           ORDER BY dar.created_at ASC""",
        (owner_user_id,),
    )
    rows = await cursor.fetchall()
    return [
        {
            "id": row[0],
            "mac": row[1],
            "requester_user_id": row[2],
            "requester_username": row[3],
            "status": row[4],
            "created_at": row[5],
            "updated_at": row[6],
        }
        for row in rows
    ]


async def approve_access_request(request_id: int, owner_user_id: int) -> dict | None:
    db = await get_main_db()
    cursor = await db.execute(
        """SELECT dar.id, dar.mac, dar.requester_user_id, dar.status
           FROM device_access_requests dar
           JOIN device_memberships dm
             ON dm.mac = dar.mac AND dm.user_id = ? AND dm.role = 'owner' AND dm.status = 'active'
           WHERE dar.id = ?
           LIMIT 1""",
        (owner_user_id, request_id),
    )
    row = await cursor.fetchone()
    if not row or row[3] != "pending":
        return None
    _, mac, requester_user_id, _status = row
    await upsert_device_membership(mac, requester_user_id, role="member", status="active", granted_by=owner_user_id)
    now = datetime.now().isoformat()
    await db.execute(
        "UPDATE device_access_requests SET status = 'approved', reviewed_by = ?, updated_at = ? WHERE id = ?",
        (owner_user_id, now, request_id),
    )
    await db.commit()
    return await get_device_membership(mac, requester_user_id)


async def reject_access_request(request_id: int, owner_user_id: int) -> bool:
    db = await get_main_db()
    cursor = await db.execute(
        """UPDATE device_access_requests
           SET status = 'rejected', reviewed_by = ?, updated_at = ?
           WHERE id = ? AND status = 'pending' AND mac IN (
               SELECT mac FROM device_memberships
               WHERE user_id = ? AND role = 'owner' AND status = 'active'
           )""",
        (owner_user_id, datetime.now().isoformat(), request_id, owner_user_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def share_device_with_user(owner_user_id: int, mac: str, target_user_id: int) -> dict:
    membership = await get_device_membership(mac, target_user_id, include_pending=True)
    if membership and membership.get("status") == "active":
        return {"status": "already_member", "membership": membership}
    created = await upsert_device_membership(
        mac,
        target_user_id,
        role="member",
        status="active",
        granted_by=owner_user_id,
    )
    db = await get_main_db()
    await db.execute(
        """UPDATE device_access_requests
           SET status = 'approved', reviewed_by = ?, updated_at = ?
           WHERE mac = ? AND requester_user_id = ? AND status = 'pending'""",
        (owner_user_id, datetime.now().isoformat(), mac.upper(), target_user_id),
    )
    await db.commit()
    return {"status": "shared", "membership": created}


async def revoke_device_member(owner_user_id: int, mac: str, target_user_id: int) -> bool:
    if owner_user_id == target_user_id:
        return False
    db = await get_main_db()
    cursor = await db.execute(
        """DELETE FROM device_memberships
           WHERE mac = ? AND user_id = ? AND role != 'owner' AND mac IN (
               SELECT mac FROM device_memberships
               WHERE user_id = ? AND role = 'owner' AND status = 'active'
           )""",
        (mac.upper(), target_user_id, owner_user_id),
    )
    await db.execute(
        "DELETE FROM device_access_requests WHERE mac = ? AND requester_user_id = ?",
        (mac.upper(), target_user_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def save_config(mac: str, data: dict) -> int:
    now = datetime.now().isoformat()
    refresh_strategy = data.get("refreshStrategy", "random")
    logger.info(
        f"[CONFIG SAVE] mac={mac}, refreshStrategy={refresh_strategy}, modes={data.get('modes')}"
    )

    db = await get_main_db()
    prev = await get_active_config(mac)
    await db.execute("UPDATE configs SET is_active = 0 WHERE mac = ?", (mac,))

    countdown_events_json = json.dumps(
        data.get("countdownEvents", []), ensure_ascii=False
    )
    time_slot_rules_json = json.dumps(
        data.get("timeSlotRules", []), ensure_ascii=False
    )
    memo_text = data.get("memoText", "")
    mode_overrides_json = json.dumps(
        data.get("modeOverrides", {}), ensure_ascii=False
    )
    from .crypto import encrypt_api_key
    raw_llm_key = data.get("llmApiKey", "")
    raw_image_key = data.get("imageApiKey", "")
    if raw_llm_key:
        llm_api_key = encrypt_api_key(raw_llm_key)
    else:
        prev = await get_active_config(mac)
        llm_api_key = (prev.get("llm_api_key") or "") if prev else ""
    if raw_image_key:
        image_api_key = encrypt_api_key(raw_image_key)
    else:
        prev = await get_active_config(mac)
        image_api_key = (prev.get("image_api_key") or "") if prev else ""
    cursor = await db.execute(
        """INSERT INTO configs
           (mac, nickname, modes, refresh_strategy, character_tones,
            language, content_tone, city, refresh_interval, llm_provider, llm_model, image_provider, image_model,
            countdown_events, time_slot_rules, memo_text, llm_api_key, image_api_key, mode_overrides, is_active, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
        (
            mac,
            data.get("nickname", ""),
            ",".join(data.get("modes", DEFAULT_MODES)),
            refresh_strategy,
            ",".join(data.get("characterTones", [])),
            data.get("language", DEFAULT_LANGUAGE),
            data.get("contentTone", DEFAULT_CONTENT_TONE),
            data.get("city", DEFAULT_CITY),
            data.get("refreshInterval", DEFAULT_REFRESH_INTERVAL),
            data.get("llmProvider", DEFAULT_LLM_PROVIDER),
            data.get("llmModel", DEFAULT_LLM_MODEL),
            data.get("imageProvider", DEFAULT_IMAGE_PROVIDER),
            data.get("imageModel", DEFAULT_IMAGE_MODEL),
            countdown_events_json,
            time_slot_rules_json,
            memo_text,
            llm_api_key,
            image_api_key,
            mode_overrides_json,
            now,
        ),
    )
    config_id = cursor.lastrowid

    # Keep only the latest 5 configs per device
    await db.execute(
        """DELETE FROM configs
           WHERE mac = ? AND id NOT IN (
               SELECT id FROM configs
               WHERE mac = ?
               ORDER BY created_at DESC
               LIMIT 5
           )""",
        (mac, mac),
    )

    await db.commit()
    logger.info(f"[CONFIG SAVE] ✓ Saved as id={config_id}, is_active=1")
    return config_id


def _row_to_dict(row, columns) -> dict:
    d = dict(zip(columns, row))
    d["modes"] = [m for m in d["modes"].split(",") if m]
    d["character_tones"] = [t for t in d["character_tones"].split(",") if t]
    d["refreshStrategy"] = d.get("refresh_strategy", DEFAULT_REFRESH_STRATEGY)
    d["refreshInterval"] = d.get("refresh_interval", DEFAULT_REFRESH_INTERVAL)
    d["contentTone"] = d.get("content_tone", DEFAULT_CONTENT_TONE)
    d["characterTones"] = d.get("character_tones", [])
    d["llmProvider"] = d.get("llm_provider", DEFAULT_LLM_PROVIDER)
    d["llmModel"] = d.get("llm_model", DEFAULT_LLM_MODEL)
    d["imageProvider"] = d.get("image_provider", DEFAULT_IMAGE_PROVIDER)
    d["imageModel"] = d.get("image_model", DEFAULT_IMAGE_MODEL)
    d["memoText"] = d.get("memo_text", "")
    # Parse JSON list fields from DB TEXT columns and normalize to arrays.
    # This avoids leaking raw JSON strings (for example "[]") to web clients.
    ce_raw = d.get("countdown_events", "[]")
    try:
        ce = json.loads(ce_raw) if isinstance(ce_raw, str) else ce_raw
    except (json.JSONDecodeError, TypeError):
        ce = []
    if not isinstance(ce, list):
        ce = []
    d["countdown_events"] = ce
    d["countdownEvents"] = ce

    tsr_raw = d.get("time_slot_rules", "[]")
    try:
        tsr = json.loads(tsr_raw) if isinstance(tsr_raw, str) else tsr_raw
    except (json.JSONDecodeError, TypeError):
        tsr = []
    if not isinstance(tsr, list):
        tsr = []
    d["time_slot_rules"] = tsr
    mo_raw = d.get("mode_overrides", "{}")
    try:
        mo = json.loads(mo_raw) if isinstance(mo_raw, str) else mo_raw
    except (json.JSONDecodeError, TypeError):
        mo = {}
    if not isinstance(mo, dict):
        mo = {}
    d["mode_overrides"] = mo
    d["modeOverrides"] = mo
    # Add mac field for cycle index tracking
    if "mac" not in d:
        d["mac"] = d.get("mac", "default")
    d["memo_text"] = d.get("memo_text", "")
    # Keep encrypted key for internal use, add flag for API response
    d["has_api_key"] = bool(d.get("llm_api_key", ""))
    d["has_image_api_key"] = bool(d.get("image_api_key", ""))
    return d


async def get_active_config(mac: str, log_load: bool = True) -> dict | None:
    db = await get_main_db()
    db.row_factory = None
    cursor = await db.execute(
        "SELECT * FROM configs WHERE mac = ? AND is_active = 1 ORDER BY id DESC LIMIT 1",
        (mac,),
    )
    row = await cursor.fetchone()
    if not row:
        return None
    columns = [desc[0] for desc in cursor.description]
    config = _row_to_dict(row, columns)
    if log_load:
        logger.info(
            f"[CONFIG LOAD] mac={mac}, id={config.get('id')}, refresh_strategy={config.get('refresh_strategy')}, modes={config.get('modes')}"
        )
    return config


async def get_config_history(mac: str) -> list[dict]:
    db = await get_main_db()
    db.row_factory = None
    cursor = await db.execute(
        "SELECT * FROM configs WHERE mac = ? ORDER BY created_at DESC",
        (mac,),
    )
    rows = await cursor.fetchall()
    if not rows:
        return []
    columns = [desc[0] for desc in cursor.description]
    return [_row_to_dict(r, columns) for r in rows]


async def activate_config(mac: str, config_id: int) -> bool:
    db = await get_main_db()
    cursor = await db.execute(
        "SELECT id FROM configs WHERE id = ? AND mac = ?", (config_id, mac)
    )
    if not await cursor.fetchone():
        return False
    await db.execute("UPDATE configs SET is_active = 0 WHERE mac = ?", (mac,))
    await db.execute("UPDATE configs SET is_active = 1 WHERE id = ?", (config_id,))
    await db.commit()
    return True


# ── Device state (cycle_index, pending_refresh, etc.) ──────


async def get_cycle_index(mac: str) -> int:
    db = await get_main_db()
    cursor = await db.execute(
        "SELECT cycle_index FROM device_state WHERE mac = ?", (mac,)
    )
    row = await cursor.fetchone()
    return row[0] if row else 0


async def set_cycle_index(mac: str, idx: int):
    now = datetime.now().isoformat()
    db = await get_main_db()
    await db.execute(
        """INSERT INTO device_state (mac, cycle_index, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(mac) DO UPDATE SET cycle_index = ?, updated_at = ?""",
        (mac, idx, now, idx, now),
    )
    await db.commit()


async def update_device_state(mac: str, **kwargs):
    """Update device state fields (last_persona, last_refresh_at, pending_refresh, etc.)."""
    now = datetime.now().isoformat()
    db = await get_main_db()
    # Ensure row exists
    await db.execute(
        """INSERT INTO device_state (mac, updated_at)
           VALUES (?, ?)
           ON CONFLICT(mac) DO UPDATE SET updated_at = ?""",
        (mac, now, now),
    )
    for key, value in kwargs.items():
        if key in (
            "last_persona",
            "last_refresh_at",
            "pending_refresh",
            "cycle_index",
            "pending_mode",
            "last_state_poll_at",
            "runtime_mode",
            "expected_refresh_min",
            "last_reconnect_regen_at",
        ):
            await db.execute(
                f"UPDATE device_state SET {key} = ? WHERE mac = ?",
                (value, mac),
            )
    await db.commit()


async def get_device_state(mac: str) -> dict | None:
    db = await get_main_db()
    db.row_factory = None
    cursor = await db.execute(
        "SELECT * FROM device_state WHERE mac = ?", (mac,)
    )
    row = await cursor.fetchone()
    if not row:
        return None
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))


async def set_pending_refresh(mac: str, pending: bool = True):
    now = datetime.now().isoformat()
    db = await get_main_db()
    await db.execute(
        """INSERT INTO device_state (mac, pending_refresh, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(mac) DO UPDATE SET pending_refresh = ?, updated_at = ?""",
        (mac, int(pending), now, int(pending), now),
    )
    await db.commit()


async def consume_pending_refresh(mac: str) -> bool:
    """Check and clear pending refresh flag. Returns True if was pending."""
    db = await get_main_db()
    cursor = await db.execute(
        "SELECT pending_refresh FROM device_state WHERE mac = ?", (mac,)
    )
    row = await cursor.fetchone()
    if row and row[0]:
        await db.execute(
            "UPDATE device_state SET pending_refresh = 0 WHERE mac = ?", (mac,)
        )
        await db.commit()
        return True
    return False


async def generate_device_token(mac: str) -> str:
    """Generate and store a new auth token for a device."""
    token = secrets.token_urlsafe(32)
    now = datetime.now().isoformat()
    db = await get_main_db()
    cursor = await db.execute(
        """UPDATE device_state SET auth_token = ?, updated_at = ? WHERE mac = ?""",
        (token, now, mac),
    )
    if cursor.rowcount == 0:
        await db.execute(
            """INSERT INTO device_state (mac, auth_token, updated_at) VALUES (?, ?, ?)""",
            (mac, token, now),
        )
    await db.commit()
    return token


async def validate_device_token(mac: str, token: str) -> bool:
    """Validate a device's auth token."""
    if not token:
        return False
    db = await get_main_db()
    cursor = await db.execute(
        "SELECT auth_token FROM device_state WHERE mac = ?", (mac,)
    )
    row = await cursor.fetchone()
    if not row or not row[0]:
        return False
    return row[0] == token
