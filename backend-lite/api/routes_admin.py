"""管理页 API（/api/admin/*）。阶段 1 只放 config/modes/refresh/set-mode；
LLM key / 预览交互 / OTA 在后续阶段补全。局域网免认证。"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from store import config_store

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/config")
async def admin_get_config():
    return config_store.get_config()


@router.put("/config")
async def admin_put_config(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if isinstance(body, dict):
        return config_store.update_config(body)
    return JSONResponse({"error": "invalid body"}, status_code=400)


@router.patch("/config")
async def admin_patch_config(request: Request):
    return await admin_put_config(request)


@router.get("/modes")
async def admin_list_modes():
    """列出所有已注册模式（builtin + custom），供管理页多选。"""
    from core.mode_registry import get_registry

    registry = get_registry()
    items = []
    for info in sorted(registry.list_modes(), key=lambda m: m.mode_id):
        items.append({
            "mode_id": info.mode_id,
            "display_name": info.display_name or info.mode_id,
            "source": info.source,
        })
    return {"modes": items}


@router.post("/refresh")
async def admin_refresh(request: Request):
    """触发设备刷新。body 可选 {mac}，默认用最近一次心跳的 mac。"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    mac = (body.get("mac") or "").strip().upper() or _last_mac()
    if not mac:
        return JSONResponse({"error": "no device mac known"}, status_code=400)
    config_store.upsert_state(mac, pending_refresh=1)
    return {"ok": True, "mac": mac}


@router.post("/set-mode")
async def admin_set_mode(request: Request):
    """设置下次刷新的模式。body {mode, mac?}。"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    mode = (body.get("mode") or "").strip().upper()
    mac = (body.get("mac") or "").strip().upper() or _last_mac()
    if not mac or not mode:
        return JSONResponse({"error": "need mode and mac"}, status_code=400)
    config_store.upsert_state(mac, pending_mode=mode, pending_refresh=1)
    return {"ok": True, "mac": mac, "mode": mode}


@router.post("/runtime")
async def admin_runtime(request: Request):
    """设置运行模式。body {mode: active|interval, mac?}。"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    mode = (body.get("mode") or "interval").strip()
    mac = (body.get("mac") or "").strip().upper() or _last_mac()
    if not mac:
        return JSONResponse({"error": "no device mac known"}, status_code=400)
    config_store.upsert_state(mac, runtime_mode=mode)
    return {"ok": True, "mac": mac, "runtime_mode": mode}


@router.get("/state")
async def admin_state():
    """管理页展示设备状态。返回最近心跳 mac 的 state。"""
    mac = _last_mac()
    if not mac:
        return {"online": False, "state": None}
    return {
        "mac": mac,
        "online": config_store.is_online(mac),
        "state": config_store.get_state(mac),
    }


@router.get("/alert")
async def admin_get_alert():
    return config_store.get_alert()


@router.put("/alert")
@router.post("/alert")
async def admin_set_alert(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    active = bool(body.get("active", False))
    text = (body.get("text") or "")[:64]
    config_store.set_alert(active, text)
    return config_store.get_alert()


def _last_mac() -> str:
    """取最近一次心跳的 mac。"""
    from store.db import get_conn, _lock
    with _lock:
        row = get_conn().execute(
            "SELECT mac FROM heartbeats ORDER BY ts DESC LIMIT 1"
        ).fetchone()
    return row["mac"] if row else ""

# ---------------- LLM key（阶段 2） ----------------
from store import secret_store

@router.get("/llm-key")
async def admin_get_llm_key():
    data = secret_store.get_llm_key_masked()
    cfg = config_store.get_config()
    if cfg.get("llm_provider"):
        data["provider"] = cfg.get("llm_provider")
    data["model"] = cfg.get("llm_model") or ""
    return data

@router.put("/llm-key")
async def admin_put_llm_key(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        return JSONResponse({"error":"invalid body"}, status_code=400)

    secret_store.set_llm_key(body)

    cfg_patch = {}
    if "provider" in body:
        cfg_patch["llm_provider"] = body.get("provider") or ""
    if "model" in body:
        cfg_patch["llm_model"] = body.get("model") or ""
    if cfg_patch:
        config_store.update_config(cfg_patch)

    data = secret_store.get_llm_key_masked()
    cfg = config_store.get_config()
    if cfg.get("llm_provider"):
        data["provider"] = cfg.get("llm_provider")
    data["model"] = cfg.get("llm_model") or ""
    return data


# ---------------- OTA（阶段 4） ----------------
import os, uuid, json
_OTA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ota_files")
os.makedirs(_OTA_DIR, exist_ok=True)

@router.post("/ota/upload")
async def ota_upload(request: Request):
    """接收 multipart 上传 bin，写 ota_files/，返回设备可达 URL。"""
    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "filename"):
        return JSONResponse({"error":"no file"}, status_code=400)
    fname = f"{uuid.uuid4().hex[:8]}_{upload.filename}"
    path = os.path.join(_OTA_DIR, fname)
    with open(path, "wb") as f:
        f.write(await upload.read())
    host = request.headers.get("Host") or request.url.hostname or "localhost"
    url = f"http://{host}/api/admin/ota/file/{fname}"
    mac = _last_mac()
    if mac:
        config_store.upsert_state(mac, ota_url=url, ota_version=upload.filename or "")
    return {"url": url, "mac": mac}

@router.post("/ota/set")
async def ota_set(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    url = (body.get("ota_url") or "").strip()
    ver = (body.get("ota_version") or "").strip()
    mac = (body.get("mac") or "").strip().upper() or _last_mac()
    if not mac:
        return JSONResponse({"error":"no device mac known"}, status_code=400)
    config_store.upsert_state(mac, ota_url=url, ota_version=ver)
    return {"ok": True, "mac": mac, "ota_url": url}

@router.get("/ota/file/{name}")
async def ota_file(name: str):
    """设备从此拉取 bin。"""
    from fastapi.responses import FileResponse
    path = os.path.join(_OTA_DIR, name)
    if not os.path.isfile(path) or ".." in name or "/" in name:
        return Response(status_code=404)
    return FileResponse(path, media_type="application/octet-stream", filename=name)
