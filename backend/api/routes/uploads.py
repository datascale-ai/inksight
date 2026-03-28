from __future__ import annotations

import io
import json
import logging
import os
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from PIL import Image, UnidentifiedImageError

from api.shared import limiter

router = APIRouter(tags=["uploads"])
logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_UPLOAD_DIR = _BACKEND_ROOT / "runtime_uploads"
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024

_last_cleanup_monotonic = 0.0
_CLEANUP_INTERVAL_SEC = 3600.0


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        return default


def _max_age_seconds() -> int | None:
    """None = disabled. Based on last access (mtime touched on each GET)."""
    days = _env_int("INKSIGHT_UPLOADS_MAX_AGE_DAYS", 30)
    if days <= 0:
        return None
    return days * 86400


def _max_total_bytes() -> int | None:
    """None = disabled."""
    mb = _env_int("INKSIGHT_UPLOADS_MAX_TOTAL_MB", 512)
    if mb <= 0:
        return None
    return mb * 1024 * 1024


def _touch_pair(bin_path: Path, meta_path: Path) -> None:
    now = time.time()
    try:
        os.utime(bin_path, (now, now))
        if meta_path.exists():
            os.utime(meta_path, (now, now))
    except OSError:
        pass


def _delete_pair(bin_path: Path, meta_path: Path) -> None:
    try:
        bin_path.unlink(missing_ok=True)
    except OSError:
        pass
    try:
        meta_path.unlink(missing_ok=True)
    except OSError:
        pass


def _list_upload_bins() -> list[Path]:
    if not _UPLOAD_DIR.is_dir():
        return []
    return sorted(_UPLOAD_DIR.glob("*.bin"))


def _total_bin_bytes() -> int:
    total = 0
    for p in _list_upload_bins():
        try:
            total += p.stat().st_size
        except OSError:
            continue
    return total


def cleanup_runtime_uploads(*, force: bool = False) -> None:
    """Drop stale or excess files under runtime_uploads. Safe to call from POST/GET (throttled)."""
    global _last_cleanup_monotonic
    now_m = time.monotonic()
    if not force and (now_m - _last_cleanup_monotonic) < _CLEANUP_INTERVAL_SEC:
        return
    _last_cleanup_monotonic = now_m

    if not _UPLOAD_DIR.is_dir():
        return

    max_age = _max_age_seconds()
    max_bytes = _max_total_bytes()
    now = time.time()
    removed = 0

    for bin_path in _list_upload_bins():
        stem = bin_path.stem
        try:
            uuid.UUID(stem)
        except ValueError:
            _delete_pair(bin_path, _UPLOAD_DIR / f"{stem}.json")
            removed += 1
            continue
        meta_path = _upload_meta_path(stem)
        if not meta_path.exists():
            _delete_pair(bin_path, meta_path)
            removed += 1
            continue
        if max_age is not None:
            try:
                mtime = bin_path.stat().st_mtime
            except OSError:
                continue
            if now - mtime > max_age:
                _delete_pair(bin_path, meta_path)
                removed += 1

    for json_path in _UPLOAD_DIR.glob("*.json"):
        stem = json_path.stem
        if not (_UPLOAD_DIR / f"{stem}.bin").exists():
            try:
                json_path.unlink(missing_ok=True)
                removed += 1
            except OSError:
                pass

    if max_bytes is not None:
        total = _total_bin_bytes()
        if total > max_bytes:
            bins = []
            for p in _list_upload_bins():
                try:
                    bins.append((p.stat().st_mtime, p.stat().st_size, p))
                except OSError:
                    continue
            bins.sort(key=lambda x: x[0])
            for _mtime, size, bin_path in bins:
                if total <= max_bytes:
                    break
                stem = bin_path.stem
                _delete_pair(bin_path, _upload_meta_path(stem))
                total -= size
                removed += 1

    if removed:
        logger.info(
            "[UPLOADS] cleanup removed=%d INKSIGHT_UPLOADS_MAX_AGE_DAYS=%s INKSIGHT_UPLOADS_MAX_TOTAL_MB=%s",
            removed,
            os.getenv("INKSIGHT_UPLOADS_MAX_AGE_DAYS", "30"),
            os.getenv("INKSIGHT_UPLOADS_MAX_TOTAL_MB", "512"),
        )


def _ensure_upload_dir() -> None:
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _upload_file_path(upload_id: str) -> Path:
    return _UPLOAD_DIR / f"{upload_id}.bin"


def _upload_meta_path(upload_id: str) -> Path:
    return _UPLOAD_DIR / f"{upload_id}.json"


def _public_origin(request: Request) -> str:
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    forwarded_host = (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    host = forwarded_host or (request.headers.get("host") or "").split(",")[0].strip()
    if host:
        protocol = forwarded_proto or request.url.scheme or "http"
        return f"{protocol}://{host}"
    return str(request.base_url).rstrip("/")


def _validate_image_payload(payload: bytes, claimed_content_type: str) -> str:
    try:
        with Image.open(io.BytesIO(payload)) as img:
            img.verify()
        with Image.open(io.BytesIO(payload)) as img:
            detected = Image.MIME.get(img.format or "", "")
    except (UnidentifiedImageError, OSError):
        raise ValueError("invalid image payload")

    content_type = detected or claimed_content_type
    if not content_type.startswith("image/"):
        raise ValueError("only image/* is allowed")
    return content_type


@router.post("/uploads")
@limiter.limit("30/minute")
async def upload_image(request: Request):
    payload = await request.body()
    if not payload:
        return JSONResponse({"error": "invalid_request", "message": "missing file"}, status_code=400)
    if len(payload) > _MAX_UPLOAD_BYTES:
        return JSONResponse({"error": "file_too_large", "message": "max 10MB"}, status_code=413)

    claimed_content_type = (request.headers.get("x-upload-content-type") or "").strip().lower()
    if not claimed_content_type.startswith("image/"):
        return JSONResponse({"error": "invalid_file", "message": "only image/* is allowed"}, status_code=400)

    try:
        content_type = _validate_image_payload(payload, claimed_content_type)
    except ValueError as exc:
        return JSONResponse({"error": "invalid_file", "message": str(exc)}, status_code=400)

    _ensure_upload_dir()
    upload_id = str(uuid.uuid4())
    _upload_file_path(upload_id).write_bytes(payload)
    _upload_meta_path(upload_id).write_text(
        json.dumps({"content_type": content_type}, ensure_ascii=True),
        encoding="utf-8",
    )

    cleanup_runtime_uploads(force=True)

    origin = _public_origin(request)
    return JSONResponse({"ok": True, "id": upload_id, "url": f"{origin}/api/uploads/{upload_id}"})


@router.get("/uploads/{upload_id}")
@limiter.limit("120/minute")
async def get_upload(upload_id: str, request: Request):
    try:
        uuid.UUID(upload_id)
    except ValueError:
        return JSONResponse({"error": "not_found"}, status_code=404)

    file_path = _upload_file_path(upload_id)
    meta_path = _upload_meta_path(upload_id)
    if not file_path.exists() or not meta_path.exists():
        return JSONResponse({"error": "not_found"}, status_code=404)

    _touch_pair(file_path, meta_path)
    cleanup_runtime_uploads(force=False)

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        content_type = str(meta.get("content_type") or "application/octet-stream")
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        content_type = "application/octet-stream"

    try:
        payload = file_path.read_bytes()
    except OSError:
        return JSONResponse({"error": "not_found"}, status_code=404)

    return Response(
        content=payload,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
