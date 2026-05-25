from __future__ import annotations

import io
import mimetypes
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from PIL import Image, ImageDraw

router = APIRouter(tags=["pages"])


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent


def _backend_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _console_index_path() -> Path:
    return _backend_root() / "static" / "console" / "index.html"


def _read_file_response(root: Path, asset_path: str, not_found_message: str) -> Response | JSONResponse:
    root = root.resolve()
    file_path = (root / asset_path).resolve()
    try:
        file_path.relative_to(root)
    except ValueError:
        return JSONResponse({"error": "asset_not_found", "message": not_found_message}, status_code=404)
    if file_path != root and file_path.exists() and file_path.is_file():
        media_type, _ = mimetypes.guess_type(str(file_path))
        return Response(content=file_path.read_bytes(), media_type=media_type or "application/octet-stream")
    return JSONResponse({"error": "asset_not_found", "message": not_found_message}, status_code=404)


def _primary_webapp_base() -> str:
    return os.getenv("INKSIGHT_PRIMARY_WEBAPP_URL", "").strip().rstrip("/")


def _primary_webapp_url(path: str, mac: Optional[str] = None) -> str:
    base = _primary_webapp_base()
    if not base:
        return ""
    target = f"{base}{path}"
    if mac:
        separator = "&" if "?" in target else "?"
        target = f"{target}{separator}mac={mac}"
    return target


def _build_primary_config_url(mac: Optional[str] = None) -> Optional[str]:
    base = os.getenv("INKSIGHT_PRIMARY_WEBAPP_URL", "").strip().rstrip("/")
    if not base:
        return None
    target = f"{base}/config"
    if mac:
        target = f"{target}?mac={mac}"
    return target


def _legacy_config_bridge_html(mac: Optional[str] = None) -> str:
    primary_url = _build_primary_config_url(mac) or _primary_webapp_url("/config", mac)
    primary_action = (
        f'<a href="{primary_url}" style="display:inline-flex;align-items:center;padding:10px 14px;border-radius:999px;background:#111827;color:#ffffff;text-decoration:none;font:600 14px/1.2 system-ui,sans-serif">Open primary config</a>'
        if primary_url
        else '<span style="display:inline-flex;align-items:center;padding:10px 14px;border-radius:999px;background:#f3f4f6;color:#374151;font:600 14px/1.2 system-ui,sans-serif">Set INKSIGHT_PRIMARY_WEBAPP_URL to enable redirects</span>'
    )
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>InkSight Config</title>
  </head>
  <body style="margin:0;background:#fffdf8;color:#1f2937;font:16px/1.6 system-ui,sans-serif">
    <main style="max-width:720px;margin:0 auto;padding:64px 24px">
      <p style="margin:0 0 12px;color:#9a3412;font-weight:700;letter-spacing:.08em;text-transform:uppercase">Primary Surface</p>
      <h1 style="margin:0 0 16px;font-size:36px;line-height:1.1">Device configuration moved to the web app.</h1>
      <p style="margin:0 0 24px;max-width:56ch">
        The backend no longer serves the legacy config page at <code>/config</code>.
        Use the primary web app for daily device configuration.
      </p>
      <div style="display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-bottom:20px">
        {primary_action}
      </div>
      <p style="margin:0;color:#6b7280">
        Legacy webconfig HTML has been retired. Device APIs remain available on this backend.
      </p>
    </main>
  </body>
</html>"""


def _legacy_removed_html(title: str, target_url: str) -> str:
    primary_action = (
        f'<a href="{target_url}" style="display:inline-flex;align-items:center;padding:10px 14px;border-radius:999px;background:#111827;color:#ffffff;text-decoration:none;font:600 14px/1.2 system-ui,sans-serif">Open primary web app</a>'
        if target_url
        else '<span style="display:inline-flex;align-items:center;padding:10px 14px;border-radius:999px;background:#f3f4f6;color:#374151;font:600 14px/1.2 system-ui,sans-serif">Set INKSIGHT_PRIMARY_WEBAPP_URL to enable web app links</span>'
    )
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
  </head>
  <body style="margin:0;background:#fffdf8;color:#1f2937;font:16px/1.6 system-ui,sans-serif">
    <main style="max-width:720px;margin:0 auto;padding:64px 24px">
      <p style="margin:0 0 12px;color:#9a3412;font-weight:700;letter-spacing:.08em;text-transform:uppercase">Legacy page retired</p>
      <h1 style="margin:0 0 16px;font-size:36px;line-height:1.1">{title} moved to the primary web app.</h1>
      <p style="margin:0 0 24px;max-width:58ch">
        This backend host now focuses on device APIs and rendering. Use the primary web app for browser UI.
      </p>
      {primary_action}
    </main>
  </body>
</html>"""


@router.get("/", response_class=HTMLResponse)
async def backend_landing_page():
    return FileResponse(_console_index_path(), media_type="text/html")


@router.get("/preview", response_class=HTMLResponse)
async def preview_page_alias():
    target = _primary_webapp_url("/preview")
    if target:
        return RedirectResponse(url=target, status_code=307)
    return HTMLResponse(content=_legacy_removed_html("Preview", target), status_code=410)


@router.get("/config", response_class=HTMLResponse)
async def config_page(mac: Optional[str] = None):
    primary_url = _build_primary_config_url(mac)
    if primary_url:
        return RedirectResponse(url=primary_url, status_code=307)
    return HTMLResponse(content=_legacy_config_bridge_html(mac))


@router.get("/legacy/config", response_class=HTMLResponse)
async def legacy_config_page():
    return HTMLResponse(content=_legacy_removed_html("Device configuration", _primary_webapp_url("/config")), status_code=410)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    target = _primary_webapp_url("/config")
    if target:
        return RedirectResponse(url=target, status_code=307)
    return HTMLResponse(content=_legacy_removed_html("Dashboard", target), status_code=410)


@router.get("/editor", response_class=HTMLResponse)
async def editor_page():
    target = _primary_webapp_url("/config")
    if target:
        return RedirectResponse(url=target, status_code=307)
    return HTMLResponse(content=_legacy_removed_html("Mode editor", target), status_code=410)


@router.get("/webconfig/{asset_path:path}")
async def webconfig_asset(asset_path: str):
    if asset_path.startswith("assets/art/"):
        return _read_file_response(
            _backend_root() / "static" / "art",
            asset_path[len("assets/art/"):],
            "Static art asset not found",
        )
    return _read_file_response(_project_root() / "webconfig", asset_path, "Webconfig asset not found")


@router.get("/static/{asset_path:path}")
async def static_asset(asset_path: str):
    return _read_file_response(_backend_root() / "static", asset_path, "Static asset not found")


@router.get("/thumbs/{filename}")
async def get_thumb(filename: str):
    project_root = _project_root()
    thumb_path = project_root / "webconfig" / "thumbs" / filename
    if thumb_path.exists() and thumb_path.is_file():
        return Response(content=thumb_path.read_bytes(), media_type="image/png")

    mode_name = Path(filename).stem.upper() if filename else "MODE"
    img = Image.new("L", (400, 300), 248)
    draw = ImageDraw.Draw(img)
    draw.rectangle([(18, 18), (382, 282)], outline=180, width=1)
    draw.text((170, 130), mode_name[:16], fill=40)
    draw.text((110, 165), "No static thumbnail", fill=110)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")
