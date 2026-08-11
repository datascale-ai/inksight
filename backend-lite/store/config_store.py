"""单设备配置 + 设备运行状态 CRUD。"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .db import get_conn, _lock

# ---------------- config（单行） ----------------

_CONFIG_INT_FIELDS = {"refresh_interval", "focus_listening", "always_active"}
_CONFIG_JSON_FIELDS = {"time_slot_rules", "countdown_events", "mode_overrides"}
_CONFIG_FLOAT_FIELDS = {"latitude", "longitude"}


def get_config() -> dict[str, Any]:
    with _lock:
        row = get_conn().execute("SELECT * FROM config WHERE id=1").fetchone()
    if row is None:
        return {}
    cfg = dict(row)
    for k in _CONFIG_JSON_FIELDS:
        try:
            cfg[k] = json.loads(cfg.get(k) or "[]") if k != "mode_overrides" else json.loads(cfg.get(k) or "{}")
        except (ValueError, TypeError):
            cfg[k] = [] if k != "mode_overrides" else {}
    # modes 存 CSV
    cfg["modes"] = [m.strip() for m in (cfg.get("modes") or "").split(",") if m.strip()]
    return cfg


def update_config(patch: dict[str, Any]) -> dict[str, Any]:
    """部分更新 config 单行。未知字段忽略。"""
    allowed = {
        "modes", "refresh_strategy", "refresh_interval", "city",
        "latitude", "longitude", "language", "content_tone",
        "time_slot_rules", "countdown_events", "memo_text",
        "focus_listening", "always_active",
        "llm_provider", "llm_model", "image_provider", "image_model",
        "mode_overrides",
    }
    sets: list[str] = []
    vals: list[Any] = []
    for k, v in patch.items():
        if k not in allowed:
            continue
        if k in _CONFIG_INT_FIELDS and not isinstance(v, int):
            v = int(bool(v))
        if k == "modes" and isinstance(v, list):
            v = ",".join(m.strip() for m in v if str(m).strip())
        if k in _CONFIG_JSON_FIELDS:
            v = json.dumps(v, ensure_ascii=False)
        if k in _CONFIG_FLOAT_FIELDS and v is not None:
            v = float(v)
        sets.append(f"{k}=?")
        vals.append(v)
    if not sets:
        return get_config()
    with _lock:
        conn = get_conn()
        conn.execute(f"UPDATE config SET {', '.join(sets)} WHERE id=1", vals)
        conn.commit()
    return get_config()


# ---------------- device_state（按 mac，单用户实际只有一行） ----------------

def get_state(mac: str) -> dict[str, Any]:
    with _lock:
        row = get_conn().execute(
            "SELECT * FROM device_state WHERE mac=?", (mac,)
        ).fetchone()
    if row is None:
        return {
            "mac": mac, "pending_refresh": 0, "pending_mode": "",
            "runtime_mode": "interval", "cycle_index": 0, "last_persona": "",
            "last_refresh_at": "", "auth_token": "", "ota_url": "", "ota_version": "",
        }
    return dict(row)


def upsert_state(mac: str, **patch: Any) -> dict[str, Any]:
    allowed = {
        "pending_refresh", "pending_mode", "runtime_mode", "cycle_index",
        "last_persona", "last_refresh_at", "auth_token", "ota_url", "ota_version",
    }
    cur = get_state(mac)
    cur.update({k: v for k, v in patch.items() if k in allowed})
    with _lock:
        conn = get_conn()
        conn.execute(
            """INSERT INTO device_state (mac, pending_refresh, pending_mode, runtime_mode,
               cycle_index, last_persona, last_refresh_at, auth_token, ota_url, ota_version)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(mac) DO UPDATE SET
                 pending_refresh=excluded.pending_refresh,
                 pending_mode=excluded.pending_mode,
                 runtime_mode=excluded.runtime_mode,
                 cycle_index=excluded.cycle_index,
                 last_persona=excluded.last_persona,
                 last_refresh_at=excluded.last_refresh_at,
                 auth_token=excluded.auth_token,
                 ota_url=excluded.ota_url,
                 ota_version=excluded.ota_version""",
            (mac, cur["pending_refresh"], cur["pending_mode"], cur["runtime_mode"],
             cur["cycle_index"], cur["last_persona"], cur["last_refresh_at"],
             cur["auth_token"], cur["ota_url"], cur["ota_version"]),
        )
        conn.commit()
    return cur


def consume_pending_refresh(mac: str) -> bool:
    """读取并清除 pending_refresh。"""
    s = get_state(mac)
    if s.get("pending_refresh"):
        upsert_state(mac, pending_refresh=0)
        return True
    return False


def consume_pending_mode(mac: str) -> str | None:
    """读取并清除 pending_mode。"""
    s = get_state(mac)
    pm = s.get("pending_mode") or ""
    if pm:
        upsert_state(mac, pending_mode="")
        return pm
    return None


def advance_cycle(mac: str, modes: list[str]) -> tuple[int, str]:
    """推进 cycle_index，返回 (新 idx, 选中 persona)。"""
    if not modes:
        return 0, "STOIC"
    s = get_state(mac)
    idx = int(s.get("cycle_index") or 0)
    persona = modes[idx % len(modes)]
    upsert_state(mac, cycle_index=idx + 1, last_persona=persona,
                 last_refresh_at=datetime.now().isoformat(timespec="seconds"))
    return idx, persona


# ---------------- heartbeats ----------------

def add_heartbeat(mac: str, battery_voltage: float, wifi_rssi: int) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    with _lock:
        conn = get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO heartbeats (mac, ts, battery_voltage, wifi_rssi) VALUES (?,?,?,?)",
            (mac, ts, battery_voltage, wifi_rssi),
        )
        # 滚动保留最近 100 条/设备
        conn.execute(
            """DELETE FROM heartbeats WHERE mac=? AND ts NOT IN (
                 SELECT ts FROM heartbeats WHERE mac=? ORDER BY ts DESC LIMIT 100)""",
            (mac, mac),
        )
        conn.commit()


def is_online(mac: str, within_minutes: int = 15) -> bool:
    with _lock:
        row = get_conn().execute(
            "SELECT MAX(ts) AS latest FROM heartbeats WHERE mac=?", (mac,)
        ).fetchone()
    if not row or not row["latest"]:
        return False
    try:
        latest = datetime.fromisoformat(row["latest"])
    except ValueError:
        return False
    return (datetime.now() - latest).total_seconds() < within_minutes * 60


# ---------------- alert_state（单行） ----------------

def get_alert() -> dict[str, Any]:
    with _lock:
        row = get_conn().execute("SELECT * FROM alert_state WHERE id=1").fetchone()
    return dict(row) if row else {"active": 0, "text": ""}


def set_alert(active: bool, text: str = "") -> dict[str, Any]:
    with _lock:
        conn = get_conn()
        conn.execute(
            "UPDATE alert_state SET active=?, text=? WHERE id=1",
            (int(bool(active)), text),
        )
        conn.commit()
    return get_alert()