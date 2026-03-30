from __future__ import annotations

import asyncio
import os
import json
import logging
import secrets
import hashlib
import hmac
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
                mode_language TEXT DEFAULT '',
                content_tone TEXT DEFAULT 'neutral',
                city TEXT DEFAULT '杭州',
                latitude REAL,
                longitude REAL,
                timezone TEXT DEFAULT '',
                admin1 TEXT DEFAULT '',
                country TEXT DEFAULT '',
                refresh_interval INTEGER DEFAULT 60,
                llm_provider TEXT DEFAULT 'deepseek',
                llm_model TEXT DEFAULT 'deepseek-chat',
                image_provider TEXT DEFAULT 'aliyun',
                image_model TEXT DEFAULT 'qwen-image-max',
                countdown_events TEXT DEFAULT '[]',
                time_slot_rules TEXT DEFAULT '[]',
                memo_text TEXT DEFAULT '',
                mode_overrides TEXT DEFAULT '{}',
                focus_listening INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)

        await db.execute("CREATE INDEX IF NOT EXISTS idx_configs_mac ON configs(mac)")

        # 迁移旧版本中可能仍包含 llm_api_key / image_api_key 列的 configs 表：
        # 在新结构中彻底移除这两个字段。
        try:
            cursor = await db.execute("PRAGMA table_info(configs)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            if "llm_api_key" in column_names or "image_api_key" in column_names:
                logger.info("[MIGRATION] Migrating configs table to drop llm_api_key/image_api_key columns")
                # 创建新表（目标结构与上面的 CREATE TABLE 保持一致）
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS configs_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        mac TEXT NOT NULL,
                        nickname TEXT DEFAULT '',
                        modes TEXT DEFAULT 'STOIC,ROAST,ZEN,DAILY',
                        refresh_strategy TEXT DEFAULT 'random',
                        character_tones TEXT DEFAULT '',
                        language TEXT DEFAULT 'zh',
                        mode_language TEXT DEFAULT '',
                        content_tone TEXT DEFAULT 'neutral',
                        city TEXT DEFAULT '杭州',
                        latitude REAL,
                        longitude REAL,
                        timezone TEXT DEFAULT '',
                        admin1 TEXT DEFAULT '',
                        country TEXT DEFAULT '',
                        refresh_interval INTEGER DEFAULT 60,
                        llm_provider TEXT DEFAULT 'deepseek',
                        llm_model TEXT DEFAULT 'deepseek-chat',
                        image_provider TEXT DEFAULT 'aliyun',
                        image_model TEXT DEFAULT 'qwen-image-max',
                        countdown_events TEXT DEFAULT '[]',
                        time_slot_rules TEXT DEFAULT '[]',
                        memo_text TEXT DEFAULT '',
                        mode_overrides TEXT DEFAULT '{}',
                        focus_listening INTEGER DEFAULT 0,
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT NOT NULL
                    )
                """)
                await db.execute("""
                    INSERT INTO configs_new (
                        id, mac, nickname, modes, refresh_strategy,
                        character_tones, language, content_tone, city, latitude, longitude, timezone, admin1, country,
                        refresh_interval, llm_provider, llm_model,
                        image_provider, image_model,
                        countdown_events, time_slot_rules, memo_text,
                        mode_overrides, focus_listening, is_active, created_at
                    )
                    SELECT
                        id, mac, nickname, modes, refresh_strategy,
                        character_tones, language, content_tone, city, NULL, NULL, '', '', '',
                        refresh_interval, llm_provider, llm_model,
                        image_provider, image_model,
                        countdown_events, time_slot_rules, memo_text,
                        mode_overrides, 0, is_active, created_at
                    FROM configs
                """)
                await db.execute("DROP TABLE configs")
                await db.execute("ALTER TABLE configs_new RENAME TO configs")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_configs_mac ON configs(mac)")
                await db.commit()
                logger.info("[MIGRATION] configs table migration completed")
        except Exception as e:
            logger.warning(f"[MIGRATION] Failed to migrate configs table: {e}", exc_info=True)
            await db.rollback()

        _EXPECTED_COLUMNS = {
            "llm_provider": "TEXT DEFAULT 'deepseek'",
            "llm_model": "TEXT DEFAULT 'deepseek-chat'",
            "image_provider": "TEXT DEFAULT 'aliyun'",
            "image_model": "TEXT DEFAULT 'qwen-image-max'",
            "countdown_events": "TEXT DEFAULT '[]'",
            "time_slot_rules": "TEXT DEFAULT '[]'",
            "memo_text": "TEXT DEFAULT ''",
            "mode_overrides": "TEXT DEFAULT '{}'",
            "mode_language": "TEXT DEFAULT ''",
            "focus_listening": "INTEGER DEFAULT 0",
            "latitude": "REAL",
            "longitude": "REAL",
            "timezone": "TEXT DEFAULT ''",
            "admin1": "TEXT DEFAULT ''",
            "country": "TEXT DEFAULT ''",
        }
        try:
            cursor = await db.execute("PRAGMA table_info(configs)")
            existing = {row[1] for row in await cursor.fetchall()}
            for col, typedef in _EXPECTED_COLUMNS.items():
                if col not in existing:
                    await db.execute(f"ALTER TABLE configs ADD COLUMN {col} {typedef}")
                    logger.info("[MIGRATION] Added column configs.%s", col)
            await db.commit()
        except Exception as e:
            logger.warning("[MIGRATION] Failed to add missing columns: %s", e, exc_info=True)
            await db.rollback()

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
                alert_token TEXT DEFAULT '',
                alert_token_created_at TEXT DEFAULT '',
                updated_at TEXT NOT NULL
            )
        """)
        # Migration: add focus_listening column if missing
        try:
            cursor = await db.execute("PRAGMA table_info(configs)")
            columns = await cursor.fetchall()
            names = [c[1] for c in columns]
            if "focus_listening" not in names:
                await db.execute("ALTER TABLE configs ADD COLUMN focus_listening INTEGER DEFAULT 0")
                await db.commit()
        except Exception:
            logger.warning("[MIGRATION] Failed to add focus_listening column", exc_info=True)

        # Migration: add alert token columns if missing
        try:
            cursor = await db.execute("PRAGMA table_info(device_state)")
            columns = await cursor.fetchall()
            names = [c[1] for c in columns]
            if "alert_token" not in names:
                await db.execute("ALTER TABLE device_state ADD COLUMN alert_token TEXT DEFAULT ''")
            if "alert_token_created_at" not in names:
                await db.execute("ALTER TABLE device_state ADD COLUMN alert_token_created_at TEXT DEFAULT ''")
            await db.commit()
        except Exception:
            logger.warning("[MIGRATION] Failed to add alert token columns", exc_info=True)

        # User system tables
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                phone TEXT UNIQUE,
                email TEXT UNIQUE,
                role TEXT NOT NULL DEFAULT 'user',
                invite_code TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        # Migration: add phone/email columns if missing.
        # NOTE: SQLite does NOT support adding a UNIQUE column constraint via ALTER TABLE ADD COLUMN.
        # We add the column first, then enforce uniqueness via a UNIQUE index.
        try:
            await db.execute("ALTER TABLE users ADD COLUMN phone TEXT")
            await db.commit()
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN email TEXT")
            await db.commit()
        except Exception:
            pass

        # Enforce uniqueness (NULL allowed) via indexes
        await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone_unique ON users(phone)")
        await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email)")

        # Migration: add role column if missing
        try:
            await db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
            await db.commit()
        except Exception:
            pass

        # Migration: add invite_code column if missing
        try:
            await db.execute("ALTER TABLE users ADD COLUMN invite_code TEXT DEFAULT ''")
            await db.commit()
        except Exception:
            pass

        # Invitation codes table 
        await db.execute("""
            CREATE TABLE IF NOT EXISTS invitation_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                is_used INTEGER DEFAULT 0,
                generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                used_by_user_id INTEGER,
                FOREIGN KEY (used_by_user_id) REFERENCES users(id)
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_invitation_codes_used_by ON invitation_codes(used_by_user_id)"
        )
        await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_invitation_codes_code ON invitation_codes(code)"
        )
        
        # Migration: 如果表已存在但缺少 id 列，需要迁移
        try:
            # 检查是否存在旧表结构（没有 id 列）
            cursor = await db.execute("PRAGMA table_info(invitation_codes)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if "id" not in column_names:
                logger.info("[MIGRATION] Migrating invitation_codes table: adding id column")
                # 创建新表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS invitation_codes_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        code TEXT NOT NULL UNIQUE,
                        is_used INTEGER DEFAULT 0,
                        generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        used_by_user_id INTEGER,
                        FOREIGN KEY (used_by_user_id) REFERENCES users(id)
                    )
                """)
                # 迁移数据
                await db.execute("""
                    INSERT INTO invitation_codes_new (code, is_used, generated_at, used_by_user_id)
                    SELECT code, is_used, generated_at, used_by_user_id FROM invitation_codes
                """)
                # 删除旧表
                await db.execute("DROP TABLE invitation_codes")
                # 重命名新表
                await db.execute("ALTER TABLE invitation_codes_new RENAME TO invitation_codes")
                # 重新创建索引
                await db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_invitation_codes_used_by ON invitation_codes(used_by_user_id)"
                )
                await db.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_invitation_codes_code ON invitation_codes(code)"
                )
                await db.commit()
                logger.info("[MIGRATION] invitation_codes table migration completed")
        except Exception as e:
            logger.warning(f"[MIGRATION] Failed to migrate invitation_codes table: {e}", exc_info=True)

        # API quotas table API额度表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS api_quotas (
                user_id INTEGER PRIMARY KEY,
                total_calls_made INTEGER DEFAULT 0,
                free_quota_remaining INTEGER DEFAULT 5,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        # User LLM config table 用户级别的LLM配置表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_llm_config (
                user_id INTEGER PRIMARY KEY,
                llm_access_mode TEXT DEFAULT 'preset',
                provider TEXT DEFAULT 'deepseek',
                api_key TEXT DEFAULT '',
                base_url TEXT DEFAULT '',
                image_provider TEXT DEFAULT 'aliyun',
                image_api_key TEXT DEFAULT '',
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY,
                push_enabled INTEGER DEFAULT 0,
                push_time TEXT DEFAULT '08:00',
                push_modes TEXT DEFAULT '[]',
                widget_mode TEXT DEFAULT 'STOIC',
                locale TEXT DEFAULT 'zh',
                timezone TEXT DEFAULT 'Asia/Shanghai',
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS push_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                push_token TEXT NOT NULL,
                platform TEXT NOT NULL,
                push_time TEXT DEFAULT '08:00',
                timezone TEXT DEFAULT 'Asia/Shanghai',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, push_token),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_push_tokens_user ON push_tokens(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_push_tokens_token ON push_tokens(push_token)")

        # Shared modes table for Discover page
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shared_modes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode_id VARCHAR(50) NOT NULL,
                name VARCHAR(100) NOT NULL UNIQUE,
                description TEXT,
                category VARCHAR(20) NOT NULL,
                author_id INTEGER NOT NULL,
                config_json TEXT NOT NULL,
                thumbnail_url VARCHAR(255),
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (author_id) REFERENCES users(id)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_shared_modes_category ON shared_modes(category)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_shared_modes_author ON shared_modes(author_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_shared_modes_active ON shared_modes(is_active)")
        await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_shared_modes_name ON shared_modes(name)")

        # Custom modes table - user-specific custom modes stored in database
        # Check if table exists and if it has the mac column
        cursor = await db.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='custom_modes'
        """)
        table_exists = await cursor.fetchone()
        
        if table_exists:
            # Check if mac column exists
            cursor = await db.execute("PRAGMA table_info(custom_modes)")
            columns = [row[1] for row in await cursor.fetchall()]
            if "mac" not in columns:
                # Table exists but doesn't have mac column - need to migrate
                logger.info("[MIGRATION] custom_modes table exists without mac column. Migrating...")
                # Check if table has any data
                cursor = await db.execute("SELECT COUNT(*) FROM custom_modes")
                count = (await cursor.fetchone())[0]
                if count > 0:
                    logger.warning(f"[MIGRATION] Found {count} existing custom_modes records. Deleting them for migration (mac field is required).")
                    await db.execute("DELETE FROM custom_modes")
                
                # Drop old indexes
                try:
                    await db.execute("DROP INDEX IF EXISTS idx_custom_modes_user")
                    await db.execute("DROP INDEX IF EXISTS idx_custom_modes_mode_id")
                except Exception:
                    pass
                
                # Drop and recreate table with mac column
                await db.execute("DROP TABLE custom_modes")
                logger.info("[MIGRATION] Recreated custom_modes table with mac column")
        
        # Create table with mac column (if it doesn't exist or was just dropped)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS custom_modes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode_id VARCHAR(50) NOT NULL,
                user_id INTEGER NOT NULL,
                mac VARCHAR(17) NOT NULL,
                definition_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(mode_id, user_id, mac),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Create indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_custom_modes_user ON custom_modes(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_custom_modes_mode_id ON custom_modes(mode_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_custom_modes_mac ON custom_modes(mac)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_custom_modes_user_mac ON custom_modes(user_id, mac)")

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


async def create_user(
    username: str,
    password: str,
    *,
    phone: str | None = None,
    email: str | None = None,
    invite_code: str = "",
) -> int | None:
    """创建用户基础记录。

    注意：本函数**只负责 users 表插入**，不涉及邀请码占用或额度初始化。
    在需要强一致性的注册流程中，请优先使用更高层的封装函数（例如带邀请码校验的注册逻辑）。
    """
    pw_hash, _ = _hash_password(password)
    now = datetime.now().isoformat()
    db = await get_main_db()
    try:
        cursor = await db.execute(
            """
            INSERT INTO users (username, password_hash, phone, email, role, invite_code, created_at)
            VALUES (?, ?, ?, ?, 'user', ?, ?)
            """,
            (
                username.strip(),
                pw_hash,
                (phone or None),
                (email or None),
                invite_code or "",
                now,
            ),
        )
        await db.commit()
        return cursor.lastrowid
    except aiosqlite.IntegrityError:
        # 用户名 / 手机号 / 邮箱 唯一性冲突时返回 None，由上层决定错误文案
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


def _parse_json_blob(value: str | None, fallback):
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (json.JSONDecodeError, TypeError):
        parsed = fallback
    return parsed if isinstance(parsed, type(fallback)) else fallback


def _default_user_preferences(user_id: int) -> dict:
    return {
        "user_id": user_id,
        "push_enabled": False,
        "push_time": "08:00",
        "push_modes": [],
        "widget_mode": "STOIC",
        "locale": "zh",
        "timezone": "Asia/Shanghai",
        "updated_at": "",
    }


async def get_user_preferences(user_id: int) -> dict:
    db = await get_main_db()
    cursor = await db.execute(
        """SELECT user_id, push_enabled, push_time, push_modes, widget_mode, locale, timezone, updated_at
           FROM user_preferences WHERE user_id = ? LIMIT 1""",
        (user_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return _default_user_preferences(user_id)
    return {
        "user_id": row[0],
        "push_enabled": bool(row[1]),
        "push_time": row[2] or "08:00",
        "push_modes": _parse_json_blob(row[3], []),
        "widget_mode": (row[4] or "STOIC").upper(),
        "locale": row[5] or "zh",
        "timezone": row[6] or "Asia/Shanghai",
        "updated_at": row[7] or "",
    }


async def save_user_preferences(user_id: int, data: dict) -> dict:
    current = await get_user_preferences(user_id)
    now = datetime.now().isoformat()
    push_enabled = bool(data.get("push_enabled", current["push_enabled"]))
    push_time = str(data.get("push_time", current["push_time"]) or current["push_time"]).strip()[:5] or "08:00"
    push_modes = data.get("push_modes", current["push_modes"])
    if not isinstance(push_modes, list):
        push_modes = current["push_modes"]
    push_modes = [str(mode).strip().upper() for mode in push_modes if str(mode).strip()]
    widget_mode = str(data.get("widget_mode", current["widget_mode"]) or current["widget_mode"]).strip().upper() or "STOIC"
    locale = str(data.get("locale", current["locale"]) or current["locale"]).strip().lower() or "zh"
    timezone = str(data.get("timezone", current["timezone"]) or current["timezone"]).strip() or "Asia/Shanghai"

    db = await get_main_db()
    await db.execute(
        """
        INSERT INTO user_preferences
            (user_id, push_enabled, push_time, push_modes, widget_mode, locale, timezone, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            push_enabled = excluded.push_enabled,
            push_time = excluded.push_time,
            push_modes = excluded.push_modes,
            widget_mode = excluded.widget_mode,
            locale = excluded.locale,
            timezone = excluded.timezone,
            updated_at = excluded.updated_at
        """,
        (
            user_id,
            int(push_enabled),
            push_time,
            json.dumps(push_modes, ensure_ascii=False),
            widget_mode,
            locale,
            timezone,
            now,
        ),
    )
    await db.commit()
    return await get_user_preferences(user_id)


async def register_push_token(
    user_id: int,
    push_token: str,
    platform: str,
    timezone: str,
    push_time: str = "08:00",
) -> dict:
    now = datetime.now().isoformat()
    db = await get_main_db()
    await db.execute(
        """
        INSERT INTO push_tokens
            (user_id, push_token, platform, push_time, timezone, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, push_token) DO UPDATE SET
            platform = excluded.platform,
            push_time = excluded.push_time,
            timezone = excluded.timezone,
            updated_at = excluded.updated_at
        """,
        (user_id, push_token, platform, push_time, timezone, now, now),
    )
    await db.commit()
    return {
        "user_id": user_id,
        "push_token": push_token,
        "platform": platform,
        "push_time": push_time,
        "timezone": timezone,
        "updated_at": now,
    }


async def unregister_push_token(user_id: int, push_token: str) -> int:
    db = await get_main_db()
    cursor = await db.execute(
        "DELETE FROM push_tokens WHERE user_id = ? AND push_token = ?",
        (user_id, push_token),
    )
    await db.commit()
    return cursor.rowcount


async def authenticate_user(username: str, password: str) -> dict | None:
    user = await get_user_by_username(username)
    if not user:
        return None
    if not _verify_password(password, user["password_hash"]):
        return None
    return user


async def get_user_role(user_id: int) -> str | None:
    """根据 user_id 获取用户的 role（权限）。

    返回 'root' 或 'user'，如果用户不存在则返回 None。
    """
    db = await get_main_db()
    cursor = await db.execute(
        "SELECT role FROM users WHERE id = ?",
        (user_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return None
    return row[0] or "user"  # 默认为 'user'


# ── API quota & invitation helpers ────────────────────────────


async def init_user_api_quota(user_id: int, *, free_quota: int = 5) -> None:
    """为新用户初始化 API 调用额度（幂等）。

    默认 5 次免费额度，可通过 free_quota 参数调整。
    """
    db = await get_main_db()
    await db.execute(
        """
        INSERT OR IGNORE INTO api_quotas (user_id, total_calls_made, free_quota_remaining)
        VALUES (?, 0, ?)
        """,
        (user_id, free_quota),
    )
    await db.commit()


async def get_user_api_quota(user_id: int) -> dict | None:
    """查询用户当前额度信息。"""
    db = await get_main_db()
    cursor = await db.execute(
        "SELECT user_id, total_calls_made, free_quota_remaining FROM api_quotas WHERE user_id = ?",
        (user_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return None
    return {
        "user_id": row[0],
        "total_calls_made": row[1],
        "free_quota_remaining": row[2],
    }


async def consume_user_free_quota(user_id: int, *, amount: int = 1) -> bool:
    """在额度足够时原子性扣减免费额度，并累计调用次数。

    仅当 free_quota_remaining >= amount 时成功扣减并返回 True；
    否则不修改记录并返回 False。
    """
    if amount <= 0:
        return True

    db = await get_main_db()
    cursor = await db.execute(
        """
        UPDATE api_quotas
        SET
            free_quota_remaining = free_quota_remaining - ?,
            total_calls_made     = total_calls_made + 1
        WHERE user_id = ?
          AND free_quota_remaining >= ?
        """,
        (amount, user_id, amount),
    )
    await db.commit()
    return cursor.rowcount > 0


async def get_quota_owner_for_mac(mac: str) -> int | None:
    """根据设备 MAC 查找与其绑定的计费用户（当前策略：设备 owner）。

    如果找不到 owner，则返回 None，上层可以选择降级为不计费或使用其他策略。
    """
    owner = await get_device_owner(mac)
    if not owner:
        return None
    try:
        return int(owner.get("user_id"))
    except (TypeError, ValueError):
        return None


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


async def get_or_create_claim_token(
    mac: str,
    source: str = "portal",
    ttl_minutes: int = 10,
) -> dict:
    now_iso = datetime.now().isoformat()
    db = await get_main_db()
    cursor = await db.execute(
        """SELECT pair_code, expires_at
           FROM device_claim_tokens
           WHERE mac = ?
             AND used_at = ''
             AND expires_at > ?
           ORDER BY created_at DESC
           LIMIT 1""",
        (mac.upper(), now_iso),
    )
    row = await cursor.fetchone()
    if row:
        return {
            "token": "",
            "pair_code": row[0],
            "expires_at": row[1],
        }
    created = await create_claim_token(mac, source=source, ttl_minutes=ttl_minutes)
    if created is None:
        raise RuntimeError("failed to create claim token")
    return created


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
    # 注意：API key 不再保存到设备配置中，改为使用用户级别的配置（user_llm_config 表）
    # 这里依赖 configs 表的默认值将 is_active 设为 1，因此不再显式写入该列，避免列数不匹配。
    cursor = await db.execute(
        """INSERT INTO configs
           (mac, nickname, modes, refresh_strategy, character_tones,
            language, mode_language, content_tone, city, latitude, longitude, timezone, admin1, country,
            refresh_interval, llm_provider, llm_model, image_provider, image_model,
            countdown_events, time_slot_rules, memo_text, mode_overrides, focus_listening, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            mac,
            data.get("nickname", ""),
            ",".join(data.get("modes", DEFAULT_MODES)),
            refresh_strategy,
            ",".join(data.get("characterTones", [])),
            data.get("language", DEFAULT_LANGUAGE),
            data.get("modeLanguage", ""),
            data.get("contentTone", DEFAULT_CONTENT_TONE),
            data.get("city", DEFAULT_CITY),
            data.get("latitude"),
            data.get("longitude"),
            data.get("timezone", ""),
            data.get("admin1", ""),
            data.get("country", ""),
            data.get("refreshInterval", DEFAULT_REFRESH_INTERVAL),
            data.get("llmProvider", DEFAULT_LLM_PROVIDER),
            data.get("llmModel", DEFAULT_LLM_MODEL),
            data.get("imageProvider", DEFAULT_IMAGE_PROVIDER),
            data.get("imageModel", DEFAULT_IMAGE_MODEL),
            countdown_events_json,
            time_slot_rules_json,
            memo_text,
            mode_overrides_json,
            1 if bool(data.get("is_focus_listening", False)) else 0,
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


async def update_focus_listening(mac: str, enabled: bool) -> bool:
    """轻量更新 focus_listening：复制当前 active config 并仅修改开关字段。"""
    normalized_mac = mac.upper()
    db = await get_main_db()
    prev = await get_active_config(normalized_mac)
    if not prev:
        return False

    for attempt in range(5):
        try:
            await db.execute("UPDATE configs SET is_active = 0 WHERE mac = ?", (normalized_mac,))
            break
        except Exception as e:
            if "database is locked" in str(e).lower():
                await asyncio.sleep(0.15 * (attempt + 1))
                continue
            raise
    else:
        return False

    prev_modes = prev.get("modes", DEFAULT_MODES)
    modes_str = ",".join(prev_modes) if isinstance(prev_modes, list) else str(prev_modes or ",".join(DEFAULT_MODES))
    prev_tones = prev.get("character_tones", [])
    tones_str = ",".join(prev_tones) if isinstance(prev_tones, list) else str(prev_tones or "")
    ce_val = prev.get("countdown_events", "[]")
    countdown_events_json = ce_val if isinstance(ce_val, str) else json.dumps(ce_val, ensure_ascii=False)
    tsr_val = prev.get("time_slot_rules", "[]")
    time_slot_rules_json = tsr_val if isinstance(tsr_val, str) else json.dumps(tsr_val, ensure_ascii=False)
    mo_val = prev.get("mode_overrides", "{}")
    mode_overrides_json = mo_val if isinstance(mo_val, str) else json.dumps(mo_val, ensure_ascii=False)

    for attempt in range(5):
        try:
            await db.execute(
                """INSERT INTO configs
                   (mac, nickname, modes, refresh_strategy, character_tones,
                    language, mode_language, content_tone, city, refresh_interval, llm_provider, llm_model, image_provider, image_model,
                    countdown_events, time_slot_rules, memo_text, mode_overrides, focus_listening, is_active, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                (
                    normalized_mac,
                    prev.get("nickname", "") or "",
                    modes_str,
                    prev.get("refresh_strategy", DEFAULT_REFRESH_STRATEGY),
                    tones_str,
                    prev.get("language", DEFAULT_LANGUAGE),
                    prev.get("mode_language", ""),
                    prev.get("content_tone", DEFAULT_CONTENT_TONE),
                    prev.get("city", DEFAULT_CITY),
                    int(prev.get("refresh_interval", DEFAULT_REFRESH_INTERVAL) or DEFAULT_REFRESH_INTERVAL),
                    prev.get("llm_provider", DEFAULT_LLM_PROVIDER),
                    prev.get("llm_model", DEFAULT_LLM_MODEL),
                    prev.get("image_provider", DEFAULT_IMAGE_PROVIDER),
                    prev.get("image_model", DEFAULT_IMAGE_MODEL),
                    countdown_events_json,
                    time_slot_rules_json,
                    str(prev.get("memo_text", "") or ""),
                    mode_overrides_json,
                    1 if enabled else 0,
                    datetime.now().isoformat(),
                ),
            )
            await db.execute(
                """DELETE FROM configs
                   WHERE mac = ? AND id NOT IN (
                       SELECT id FROM configs
                       WHERE mac = ?
                       ORDER BY created_at DESC
                       LIMIT 5
                   )""",
                (normalized_mac, normalized_mac),
            )
            await db.commit()
            return True
        except Exception as e:
            try:
                await db.rollback()
            except Exception:
                pass
            if "database is locked" in str(e).lower():
                await asyncio.sleep(0.2 * (attempt + 1))
                continue
            raise
    return False


async def get_or_create_alert_token(mac: str, regenerate: bool = False) -> str:
    normalized_mac = mac.upper()
    now = datetime.now().isoformat()
    db = await get_main_db()
    cursor = await db.execute("SELECT alert_token FROM device_state WHERE mac = ?", (normalized_mac,))
    row = await cursor.fetchone()
    existing = (row[0] if row and row[0] else "").strip() if row else ""
    if existing and not regenerate:
        return existing
    token = secrets.token_urlsafe(32)
    await db.execute(
        """INSERT INTO device_state (mac, alert_token, alert_token_created_at, updated_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(mac) DO UPDATE SET alert_token = ?, alert_token_created_at = ?, updated_at = ?""",
        (normalized_mac, token, now, now, token, now, now),
    )
    await db.commit()
    return token


async def validate_alert_token(mac: str, token: str) -> bool:
    normalized_mac = mac.upper()
    provided = (token or "").strip()
    if not provided:
        return False
    db = await get_main_db()
    cursor = await db.execute("SELECT alert_token FROM device_state WHERE mac = ?", (normalized_mac,))
    row = await cursor.fetchone()
    expected = (row[0] if row and row[0] else "").strip() if row else ""
    if not expected:
        return False
    return hmac.compare_digest(expected, provided)


def _row_to_dict(row, columns) -> dict:
    d = dict(zip(columns, row))
    d["modes"] = [m for m in d["modes"].split(",") if m]
    d["character_tones"] = [t for t in d["character_tones"].split(",") if t]
    d["refreshStrategy"] = d.get("refresh_strategy", DEFAULT_REFRESH_STRATEGY)
    d["refreshInterval"] = d.get("refresh_interval", DEFAULT_REFRESH_INTERVAL)
    d["contentTone"] = d.get("content_tone", DEFAULT_CONTENT_TONE)
    d["mode_language"] = d.get("mode_language", "")
    d["modeLanguage"] = d["mode_language"]
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
    d["focus_listening"] = int(d.get("focus_listening", 0) or 0)
    d["is_focus_listening"] = bool(d["focus_listening"])
    # Add mac field for cycle index tracking
    if "mac" not in d:
        d["mac"] = d.get("mac", "default")
    d["memo_text"] = d.get("memo_text", "")
    # 设备配置中不再存储 API key，相关标记统一为 False
    d["has_api_key"] = False
    d["has_image_api_key"] = False
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
    if config.get("llm_provider"):
        config["llm_provider"] = ""
    if config.get("llm_model"):
        config["llm_model"] = ""
    if config.get("image_provider"):
        config["image_provider"] = ""
    if config.get("image_model"):
        config["image_model"] = ""
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


async def remove_mode_from_all_configs(mode_id: str, mac: str | None = None) -> int:
    normalized_mode_id = str(mode_id or "").strip().upper()
    if not normalized_mode_id:
        return 0
    db = await get_main_db()
    if mac:
        cursor = await db.execute(
            """
            SELECT id, modes, mode_overrides
            FROM configs
            WHERE mac = ? AND (modes LIKE ? OR mode_overrides LIKE ?)
            """,
            (mac.upper(), f"%{normalized_mode_id}%", f"%{normalized_mode_id}%"),
        )
    else:
        cursor = await db.execute(
            "SELECT id, modes, mode_overrides FROM configs WHERE modes LIKE ? OR mode_overrides LIKE ?",
            (f"%{normalized_mode_id}%", f"%{normalized_mode_id}%"),
        )
    rows = await cursor.fetchall()
    updated = 0
    for config_id, modes_raw, overrides_raw in rows:
        modes = [
            m.strip().upper()
            for m in str(modes_raw or "").split(",")
            if m.strip() and m.strip().upper() != normalized_mode_id
        ]
        if not modes:
            modes = list(DEFAULT_MODES)

        try:
            overrides = json.loads(overrides_raw) if isinstance(overrides_raw, str) else overrides_raw
        except (json.JSONDecodeError, TypeError):
            overrides = {}
        if not isinstance(overrides, dict):
            overrides = {}
        cleaned_overrides = {
            str(key).strip().upper(): value
            for key, value in overrides.items()
            if str(key).strip().upper() != normalized_mode_id
        }

        await db.execute(
            "UPDATE configs SET modes = ?, mode_overrides = ? WHERE id = ?",
            (
                ",".join(modes),
                json.dumps(cleaned_overrides, ensure_ascii=False),
                config_id,
            ),
        )
        updated += 1
    if updated:
        await db.commit()
    return updated


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


# ── Custom Modes (Database) ──────────────────────────────────────


async def get_user_custom_modes(user_id: int, mac: str | None = None) -> list[dict]:
    """Get all custom modes for a specific user, optionally filtered by device MAC."""
    db = await get_main_db()
    if mac:
        cursor = await db.execute(
            """
            SELECT mode_id, mac, definition_json, created_at, updated_at
            FROM custom_modes
            WHERE user_id = ? AND mac = ?
            ORDER BY created_at DESC
            """,
            (user_id, mac.upper()),
        )
    else:
        cursor = await db.execute(
            """
            SELECT mode_id, mac, definition_json, created_at, updated_at
            FROM custom_modes
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
    rows = await cursor.fetchall()
    modes = []
    for row in rows:
        try:
            definition = json.loads(row[2])
            modes.append({
                "mode_id": row[0],
                "mac": row[1],
                "definition": definition,
                "created_at": row[3],
                "updated_at": row[4],
            })
        except json.JSONDecodeError:
            logger.error(f"[CUSTOM_MODES] Failed to parse definition for mode {row[0]}")
    return modes


async def get_custom_mode(user_id: int, mode_id: str, mac: str | None = None) -> dict | None:
    """
    Get a specific custom mode for a user *and* device.

    重要：为了保证设备隔离，这里必须同时按 user_id 和 mac 过滤；
    如果调用方没有提供 mac，则直接返回 None，而不是在所有设备中“拍脑袋选一条”。
    """
    if not mac:
        logger.warning(
            "[CUSTOM_MODES] get_custom_mode called without mac (user_id=%s, mode_id=%s) – returning None to preserve device isolation",
            user_id,
            mode_id,
        )
        return None

    db = await get_main_db()
    cursor = await db.execute(
        """
        SELECT mac, definition_json, created_at, updated_at
        FROM custom_modes
        WHERE user_id = ? AND mode_id = ? AND mac = ?
        """,
        (user_id, mode_id.upper(), mac.upper()),
    )
    row = await cursor.fetchone()
    if not row:
        return None
    try:
        definition = json.loads(row[1])
        return {
            "mode_id": mode_id.upper(),
            "mac": row[0],
            "definition": definition,
            "created_at": row[2],
            "updated_at": row[3],
        }
    except json.JSONDecodeError:
        logger.error(f"[CUSTOM_MODES] Failed to parse definition for mode {mode_id}")
        return None


async def save_custom_mode(user_id: int, mode_id: str, definition: dict, mac: str) -> bool:
    """Save or update a custom mode for a user and device."""
    db = await get_main_db()
    mode_id = mode_id.upper()
    mac = mac.upper()
    now = datetime.now().isoformat()
    definition_json = json.dumps(definition, ensure_ascii=False)
    
    try:
        await db.execute(
            """
            INSERT INTO custom_modes (mode_id, user_id, mac, definition_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(mode_id, user_id, mac) DO UPDATE SET
                definition_json = ?,
                updated_at = ?
            """,
            (mode_id, user_id, mac, definition_json, now, now, definition_json, now),
        )
        await db.commit()
        logger.info(f"[CUSTOM_MODES] Saved custom mode {mode_id} for user {user_id} on device {mac}")
        return True
    except Exception as e:
        logger.error(f"[CUSTOM_MODES] Failed to save custom mode {mode_id} for user {user_id} on device {mac}: {e}")
        await db.rollback()
        return False


async def delete_custom_mode(user_id: int, mode_id: str, mac: str | None = None) -> bool:
    """
    Delete a custom mode for a specific user and device.

    重要：不再支持“只按 user_id + mode_id 删除所有设备上的记录”，
    避免在一台设备上删除时把同一用户其他设备上的同名模式也一并删掉。
    调用方必须提供 mac，否则这里会直接返回 False。
    """
    if not mac:
        logger.warning(
            "[CUSTOM_MODES] delete_custom_mode called without mac (user_id=%s, mode_id=%s) – refusing to delete to preserve device isolation",
            user_id,
            mode_id,
        )
        return False

    db = await get_main_db()
    mode_id = mode_id.upper()
    try:
        cursor = await db.execute(
            """
            DELETE FROM custom_modes
            WHERE user_id = ? AND mode_id = ? AND mac = ?
            """,
            (user_id, mode_id, mac.upper()),
        )
        await db.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(
                "[CUSTOM_MODES] Deleted custom mode %s for user %s on device %s",
                mode_id,
                user_id,
                mac,
            )
        return deleted
    except Exception as e:
        logger.error(
            "[CUSTOM_MODES] Failed to delete custom mode %s for user %s on device %s: %s",
            mode_id,
            user_id,
            mac,
            e,
        )
        await db.rollback()
        return False


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


# ── User LLM Config (Global user-level settings) ──────────────────────


async def get_user_llm_config(user_id: int) -> dict | None:
    """获取用户级别的 LLM 配置（包含可选的自定义模型名）。"""
    db = await get_main_db()
    # 检查表结构，兼容旧版本（没有 image / model 相关列）
    cursor = await db.execute("PRAGMA table_info(user_llm_config)")
    columns = [col[1] for col in await cursor.fetchall()]
    has_access_mode_column = "llm_access_mode" in columns
    has_image_config = "image_provider" in columns and "image_api_key" in columns
    has_model_column = "model" in columns
    has_image_model_column = "image_model" in columns
    has_image_base_url_column = "image_base_url" in columns
    
    # Build SELECT with backward compatibility across schema versions.
    if has_access_mode_column and has_image_config and has_model_column and has_image_model_column:
        extra_cols = ", image_base_url" if has_image_base_url_column else ""
        cursor = await db.execute(
            f"SELECT llm_access_mode, provider, api_key, base_url, image_provider, image_api_key, model, image_model{extra_cols} FROM user_llm_config WHERE user_id = ?",
            (user_id,),
        )
    elif has_access_mode_column and has_image_config and has_model_column:
        cursor = await db.execute(
            "SELECT llm_access_mode, provider, api_key, base_url, image_provider, image_api_key, model FROM user_llm_config WHERE user_id = ?",
            (user_id,),
        )
    elif has_access_mode_column and has_image_config:
        cursor = await db.execute(
            "SELECT llm_access_mode, provider, api_key, base_url, image_provider, image_api_key FROM user_llm_config WHERE user_id = ?",
            (user_id,),
        )
    elif has_access_mode_column:
        cursor = await db.execute(
            "SELECT llm_access_mode, provider, api_key, base_url FROM user_llm_config WHERE user_id = ?",
            (user_id,),
        )
    elif has_image_config and has_model_column and has_image_model_column:
        cursor = await db.execute(
            "SELECT provider, api_key, base_url, image_provider, image_api_key, model, image_model FROM user_llm_config WHERE user_id = ?",
            (user_id,),
        )
    elif has_image_config and has_model_column:
        cursor = await db.execute(
            "SELECT provider, api_key, base_url, image_provider, image_api_key, model FROM user_llm_config WHERE user_id = ?",
            (user_id,),
        )
    elif has_image_config:
        cursor = await db.execute(
            "SELECT provider, api_key, base_url, image_provider, image_api_key FROM user_llm_config WHERE user_id = ?",
            (user_id,),
        )
    else:
        cursor = await db.execute(
            "SELECT provider, api_key, base_url FROM user_llm_config WHERE user_id = ?",
            (user_id,),
        )
    row = await cursor.fetchone()
    if not row:
        return None
    from .crypto import decrypt_api_key
    offset = 0
    llm_access_mode = "preset"
    if has_access_mode_column:
        llm_access_mode = row[0] or "preset"
        offset = 1
    result: dict[str, str] = {
        "llm_access_mode": llm_access_mode,
        "provider": row[0 + offset] or "deepseek",
        "api_key": decrypt_api_key(row[1 + offset] or "") if row[1 + offset] else "",
        "base_url": row[2 + offset] or "",
    }
    idx = 3 + offset
    if has_image_config:
        result["image_provider"] = row[idx] or "aliyun"
        result["image_api_key"] = decrypt_api_key(row[idx + 1] or "") if row[idx + 1] else ""
        idx += 2
    else:
        result["image_provider"] = "aliyun"
        result["image_api_key"] = ""
    if has_model_column and len(row) > idx:
        result["model"] = row[idx] or ""
        idx += 1
    if has_image_model_column and len(row) > idx:
        result["image_model"] = row[idx] or ""
        idx += 1
    if has_image_base_url_column and len(row) > idx:
        result["image_base_url"] = row[idx] or ""
    return result


async def save_user_llm_config(
    user_id: int,
    llm_access_mode: str = "preset",
    provider: str = "deepseek",
    model: str = "",
    api_key: str = "",
    base_url: str = "",
    image_provider: str = "aliyun",
    image_model: str = "",
    image_api_key: str = "",
    image_base_url: str = "",
) -> bool:
    """保存用户级别的 LLM 配置。"""
    from .crypto import encrypt_api_key
    
    db = await get_main_db()
    now = datetime.now().isoformat()
    
    encrypted_key = encrypt_api_key(api_key) if api_key else ""
    encrypted_image_key = encrypt_api_key(image_api_key) if image_api_key else ""
    
    # 检查表结构，兼容旧版本
    cursor = await db.execute("PRAGMA table_info(user_llm_config)")
    columns = [col[1] for col in await cursor.fetchall()]
    has_access_mode_column = "llm_access_mode" in columns
    has_image_config = "image_provider" in columns and "image_api_key" in columns
    has_model_column = "model" in columns
    has_image_model_column = "image_model" in columns
    has_image_base_url_column = "image_base_url" in columns

    # 如果表没有 llm_access_mode 列，先添加
    if not has_access_mode_column:
        try:
            await db.execute("ALTER TABLE user_llm_config ADD COLUMN llm_access_mode TEXT DEFAULT 'preset'")
            await db.commit()
            has_access_mode_column = True
        except Exception as e:
            logger.warning(f"[USER_LLM_CONFIG] Failed to add llm_access_mode column: {e}")
            await db.rollback()
    
    # 如果表没有图像配置 / model 列，先添加
    if not has_image_config:
        try:
            await db.execute("ALTER TABLE user_llm_config ADD COLUMN image_provider TEXT DEFAULT 'aliyun'")
            await db.execute("ALTER TABLE user_llm_config ADD COLUMN image_api_key TEXT DEFAULT ''")
            await db.commit()
            has_image_config = True
        except Exception as e:
            logger.warning(f"[USER_LLM_CONFIG] Failed to add image columns: {e}")
            await db.rollback()
    if not has_model_column:
        try:
            await db.execute("ALTER TABLE user_llm_config ADD COLUMN model TEXT DEFAULT ''")
            await db.commit()
            has_model_column = True
        except Exception as e:
            logger.warning(f"[USER_LLM_CONFIG] Failed to add model column: {e}")
            await db.rollback()
    if not has_image_model_column:
        try:
            await db.execute("ALTER TABLE user_llm_config ADD COLUMN image_model TEXT DEFAULT ''")
            await db.commit()
            has_image_model_column = True
        except Exception as e:
            logger.warning(f"[USER_LLM_CONFIG] Failed to add image_model column: {e}")
            await db.rollback()
    if not has_image_base_url_column:
        try:
            await db.execute("ALTER TABLE user_llm_config ADD COLUMN image_base_url TEXT DEFAULT ''")
            await db.commit()
            has_image_base_url_column = True
        except Exception as e:
            logger.warning(f"[USER_LLM_CONFIG] Failed to add image_base_url column: {e}")
            await db.rollback()
    
    try:
        if has_access_mode_column and has_image_config and has_image_model_column:
            await db.execute(
                """INSERT INTO user_llm_config (user_id, llm_access_mode, provider, model, api_key, base_url, image_provider, image_api_key, image_model, image_base_url, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                       llm_access_mode = excluded.llm_access_mode,
                       provider = excluded.provider,
                       model = excluded.model,
                       api_key = excluded.api_key,
                       base_url = excluded.base_url,
                       image_provider = excluded.image_provider,
                       image_api_key = excluded.image_api_key,
                       image_model = excluded.image_model,
                       image_base_url = excluded.image_base_url,
                       updated_at = excluded.updated_at""",
                (user_id, llm_access_mode, provider, model, encrypted_key, base_url, image_provider, encrypted_image_key, image_model, image_base_url, now),
            )
        elif has_access_mode_column and has_image_config:
            await db.execute(
                """INSERT INTO user_llm_config (user_id, llm_access_mode, provider, model, api_key, base_url, image_provider, image_api_key, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                       llm_access_mode = excluded.llm_access_mode,
                       provider = excluded.provider,
                       model = excluded.model,
                       api_key = excluded.api_key,
                       base_url = excluded.base_url,
                       image_provider = excluded.image_provider,
                       image_api_key = excluded.image_api_key,
                       updated_at = excluded.updated_at""",
                (user_id, llm_access_mode, provider, model, encrypted_key, base_url, image_provider, encrypted_image_key, now),
            )
        elif has_access_mode_column:
            await db.execute(
                """INSERT INTO user_llm_config (user_id, llm_access_mode, provider, model, api_key, base_url, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                       llm_access_mode = excluded.llm_access_mode,
                       provider = excluded.provider,
                       model = excluded.model,
                       api_key = excluded.api_key,
                       base_url = excluded.base_url,
                       updated_at = excluded.updated_at""",
                (user_id, llm_access_mode, provider, model, encrypted_key, base_url, now),
            )
        elif has_image_config and has_image_model_column:
            await db.execute(
                """INSERT INTO user_llm_config (user_id, provider, model, api_key, base_url, image_provider, image_api_key, image_model, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                       provider = excluded.provider,
                       model = excluded.model,
                       api_key = excluded.api_key,
                       base_url = excluded.base_url,
                       image_provider = excluded.image_provider,
                       image_api_key = excluded.image_api_key,
                       image_model = excluded.image_model,
                       updated_at = excluded.updated_at""",
                (user_id, provider, model, encrypted_key, base_url, image_provider, encrypted_image_key, image_model, now),
            )
        elif has_image_config:
            await db.execute(
                """INSERT INTO user_llm_config (user_id, provider, model, api_key, base_url, image_provider, image_api_key, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                       provider = excluded.provider,
                       model = excluded.model,
                       api_key = excluded.api_key,
                       base_url = excluded.base_url,
                       image_provider = excluded.image_provider,
                       image_api_key = excluded.image_api_key,
                       updated_at = excluded.updated_at""",
                (user_id, provider, model, encrypted_key, base_url, image_provider, encrypted_image_key, now),
            )
        else:
            await db.execute(
                """INSERT INTO user_llm_config (user_id, provider, model, api_key, base_url, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                       provider = excluded.provider,
                       model = excluded.model,
                       api_key = excluded.api_key,
                       base_url = excluded.base_url,
                       updated_at = excluded.updated_at""",
                (user_id, provider, model, encrypted_key, base_url, now),
            )
        await db.commit()
        return True
    except Exception as e:
        logger.error(f"[USER_LLM_CONFIG] Failed to save config for user {user_id}: {e}")
        await db.rollback()
        return False


async def delete_user_llm_config(user_id: int) -> bool:
    """删除用户级别的 LLM 配置（BYOK）。删除后将回退到平台默认 key + 额度模式。"""
    db = await get_main_db()
    try:
        cursor = await db.execute(
            "DELETE FROM user_llm_config WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"[USER_LLM_CONFIG] Failed to delete config for user {user_id}: {e}")
        await db.rollback()
        return False
