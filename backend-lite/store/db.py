"""SQLite 连接与表初始化（lite.db）。

单用户、单设备：所有配置以单行形式存储。
"""
from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

_DB_PATH = os.environ.get(
    "LITE_DB_PATH",
    str(Path(__file__).resolve().parent.parent / "lite.db"),
)

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    """返回进程级单例连接（check_same_thread=False，由 _lock 串行化写入）。"""
    global _conn
    if _conn is None:
        conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _conn = conn
    return _conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    modes TEXT DEFAULT 'STOIC,ROAST,ZEN,DAILY',
    refresh_strategy TEXT DEFAULT 'random',
    refresh_interval INTEGER DEFAULT 60,
    city TEXT DEFAULT '杭州',
    latitude REAL,
    longitude REAL,
    language TEXT DEFAULT 'zh',
    content_tone TEXT DEFAULT 'neutral',
    time_slot_rules TEXT DEFAULT '[]',
    countdown_events TEXT DEFAULT '[]',
    memo_text TEXT DEFAULT '',
    focus_listening INTEGER DEFAULT 0,
    always_active INTEGER DEFAULT 0,
    llm_provider TEXT DEFAULT 'deepseek',
    llm_model TEXT DEFAULT '',
    image_provider TEXT DEFAULT 'aliyun',
    image_model TEXT DEFAULT '',
    mode_overrides TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS device_state (
    mac TEXT PRIMARY KEY,
    pending_refresh INTEGER DEFAULT 0,
    pending_mode TEXT DEFAULT '',
    runtime_mode TEXT DEFAULT 'interval',
    cycle_index INTEGER DEFAULT 0,
    last_persona TEXT DEFAULT '',
    last_refresh_at TEXT DEFAULT '',
    auth_token TEXT DEFAULT '',
    ota_url TEXT DEFAULT '',
    ota_version TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS llm_key (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    provider TEXT DEFAULT 'deepseek',
    api_key TEXT DEFAULT '',
    base_url TEXT DEFAULT '',
    image_api_key TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS heartbeats (
    mac TEXT,
    ts TEXT,
    battery_voltage REAL,
    wifi_rssi INTEGER,
    PRIMARY KEY (mac, ts)
);

CREATE TABLE IF NOT EXISTS alert_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    active INTEGER DEFAULT 0,
    text TEXT DEFAULT ''
);
"""


def init_db() -> None:
    with _lock:
        conn = get_conn()
        conn.executescript(SCHEMA)
        # 单行种子数据
        conn.execute("INSERT OR IGNORE INTO config (id) VALUES (1)")
        conn.execute("INSERT OR IGNORE INTO llm_key (id) VALUES (1)")
        conn.execute("INSERT OR IGNORE INTO alert_state (id) VALUES (1)")
        conn.commit()


def close_db() -> None:
    """关闭 backend-lite 自有 SQLite 连接，确保进程可干净退出。"""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None