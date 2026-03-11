from __future__ import annotations

import io
import mimetypes
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from PIL import Image, ImageDraw

router = APIRouter(tags=["pages"])


def _load_web_page_html(filename: str) -> str:
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    html_path = project_root / "webconfig" / filename
    if not html_path.exists():
        raise FileNotFoundError(f"Static page not found in webconfig: {filename}")
    html = html_path.read_text(encoding="utf-8")
    if "/webconfig/i18n.js" not in html:
        html = html.replace("</body>", '<script src="/webconfig/i18n.js"></script></body>')
    if "/webconfig/role-banner.js" not in html:
        html = html.replace("</body>", '<script src="/webconfig/role-banner.js"></script></body>')
    return html


def _build_primary_config_url(mac: Optional[str] = None) -> Optional[str]:
    base = os.getenv("INKSIGHT_PRIMARY_WEBAPP_URL", "").strip().rstrip("/")
    if not base:
        return None
    target = f"{base}/config"
    if mac:
        target = f"{target}?mac={mac}"
    return target


def _legacy_config_bridge_html(mac: Optional[str] = None) -> str:
    primary_url = _build_primary_config_url(mac)
    primary_link = (
        f'<a href="{primary_url}" '
        'style="display:inline-flex;align-items:center;padding:10px 14px;border-radius:999px;'
        'background:#111827;color:#ffffff;text-decoration:none;font:600 14px/1.2 system-ui,sans-serif">'
        "Open primary config"
        "</a>"
        if primary_url
        else (
            '<code style="padding:2px 6px;background:#f3f4f6;border-radius:6px">'
            "INKSIGHT_PRIMARY_WEBAPP_URL"
            "</code>"
        )
    )
    legacy_href = f"/legacy/config?mac={mac}" if mac else "/legacy/config"
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
        Use the primary web app for daily device configuration. Legacy webconfig remains available only for diagnostics and mode authoring.
      </p>
      <div style="display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-bottom:20px">
        {primary_link}
        <a href="{legacy_href}" style="display:inline-flex;align-items:center;padding:10px 14px;border-radius:999px;border:1px solid #d1d5db;color:#374151;text-decoration:none;font:600 14px/1.2 system-ui,sans-serif">
          Open legacy config
        </a>
      </div>
      <p style="margin:0;color:#6b7280">
        If you want automatic redirects here, set <code>INKSIGHT_PRIMARY_WEBAPP_URL</code> to your web app base URL.
      </p>
    </main>
  </body>
</html>"""


@router.get("/", response_class=HTMLResponse)
async def preview_page():
    return HTMLResponse(content=_load_web_page_html("preview.html"))


@router.get("/preview", response_class=HTMLResponse)
async def preview_page_alias():
    return HTMLResponse(content=_load_web_page_html("preview.html"))


@router.get("/config", response_class=HTMLResponse)
async def config_page(mac: Optional[str] = None):
    primary_url = _build_primary_config_url(mac)
    if primary_url:
        return RedirectResponse(url=primary_url, status_code=307)
    return HTMLResponse(content=_legacy_config_bridge_html(mac))


@router.get("/legacy/config", response_class=HTMLResponse)
async def legacy_config_page():
    return HTMLResponse(content=_load_web_page_html("config.html"))


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    return HTMLResponse(content=_load_web_page_html("dashboard.html"))


@router.get("/editor", response_class=HTMLResponse)
async def editor_page():
    return HTMLResponse(content=_load_web_page_html("editor.html"))


@router.get("/webconfig/{asset_path:path}")
async def webconfig_asset(asset_path: str):
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    file_path = (project_root / "webconfig" / asset_path).resolve()
    webconfig_root = (project_root / "webconfig").resolve()
    if not str(file_path).startswith(str(webconfig_root)) or not file_path.exists() or not file_path.is_file():
        return JSONResponse(
            {"error": "asset_not_found", "message": "Webconfig asset not found"},
            status_code=404,
        )
    media_type, _ = mimetypes.guess_type(str(file_path))
    return Response(content=file_path.read_bytes(), media_type=media_type or "application/octet-stream")


@router.get("/thumbs/{filename}")
async def get_thumb(filename: str):
    project_root = Path(__file__).resolve().parent.parent.parent.parent
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
