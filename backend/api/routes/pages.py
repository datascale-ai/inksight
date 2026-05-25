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


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent


def _backend_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


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


def _backend_landing_html() -> str:
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>InkSight Console</title>
    <style>
      :root { color-scheme: light; --ink:#17201b; --muted:#647067; --paper:#fffaf0; --card:#ffffff; --line:#e8ddca; --accent:#0f766e; --bad:#b91c1c; }
      * { box-sizing: border-box; }
      body { margin:0; min-height:100vh; background:radial-gradient(circle at top left,#e4f3df 0,#fffaf0 36%,#f7efe0 100%); color:var(--ink); font:15px/1.55 ui-serif, Georgia, Cambria, "Times New Roman", serif; }
      main { width:min(1120px, calc(100% - 32px)); margin:0 auto; padding:42px 0 54px; }
      header { display:flex; justify-content:space-between; gap:20px; align-items:flex-end; margin-bottom:24px; }
      h1 { margin:0; font-size:42px; line-height:1; letter-spacing:-.04em; }
      .eyebrow { margin:0 0 10px; color:var(--accent); font:700 12px/1.2 ui-sans-serif, system-ui, sans-serif; letter-spacing:.14em; text-transform:uppercase; }
      .sub { margin:12px 0 0; max-width:64ch; color:var(--muted); }
      .auth { display:flex; gap:8px; align-items:center; flex-wrap:wrap; justify-content:flex-end; max-width:560px; }
      input { width:180px; padding:11px 12px; border:1px solid var(--line); border-radius:12px; background:#fffdf8; color:var(--ink); font:14px ui-sans-serif, system-ui, sans-serif; }
      button, a.btn { border:0; border-radius:999px; padding:11px 15px; background:#17201b; color:#fff; cursor:pointer; text-decoration:none; font:700 13px/1 ui-sans-serif, system-ui, sans-serif; }
      button.secondary, a.secondary { background:#fffdf8; color:#334139; border:1px solid var(--line); }
      .status { margin:0 0 18px; padding:12px 14px; border:1px solid var(--line); border-radius:16px; background:rgba(255,255,255,.62); color:var(--muted); font-family:ui-sans-serif, system-ui, sans-serif; }
      .status.error { color:var(--bad); border-color:#fecaca; background:#fff1f2; }
      .grid { display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:14px; }
      .card { background:rgba(255,255,255,.8); border:1px solid var(--line); border-radius:22px; padding:18px; box-shadow:0 18px 50px rgba(74,58,34,.08); }
      .metric-label { margin:0; color:var(--muted); font:700 12px/1.2 ui-sans-serif, system-ui, sans-serif; letter-spacing:.08em; text-transform:uppercase; }
      .metric-value { margin:10px 0 4px; font-size:34px; line-height:1; letter-spacing:-.04em; }
      .metric-note { margin:0; color:var(--muted); font-size:13px; }
      .wide { grid-column:span 2; }
      table { width:100%; border-collapse:collapse; font-family:ui-sans-serif, system-ui, sans-serif; font-size:13px; }
      th, td { text-align:left; padding:10px 8px; border-bottom:1px solid #eee2ce; }
      th { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }
      .bars { display:flex; align-items:flex-end; gap:7px; height:132px; padding-top:14px; }
      .bar { flex:1; min-width:10px; border-radius:999px 999px 4px 4px; background:linear-gradient(180deg,#0f766e,#83b799); position:relative; }
      .bar span { position:absolute; left:50%; bottom:-24px; transform:translateX(-50%) rotate(-38deg); transform-origin:center; color:var(--muted); font-size:10px; white-space:nowrap; }
      .empty { color:var(--muted); font-family:ui-sans-serif, system-ui, sans-serif; }
      @media (max-width:820px) { header { align-items:flex-start; flex-direction:column; } .auth { justify-content:flex-start; } .grid { grid-template-columns:1fr; } .wide { grid-column:auto; } input { width:100%; } }
    </style>
  </head>
  <body>
    <main>
      <header>
        <div>
          <p class="eyebrow">InkSight Console</p>
          <h1>Backend pulse.</h1>
          <p class="sub">A root-only operational view for users, active sessions, renders, and devices on the backend host. Sign in here with the same InkSight root account; this login is scoped to web.inksight.site.</p>
        </div>
        <form id="loginForm" class="auth">
          <input id="username" name="username" placeholder="Username" autocomplete="username" />
          <input id="password" name="password" type="password" placeholder="Password" autocomplete="current-password" />
          <button id="login" type="submit">Sign in</button>
          <button id="logout" class="secondary" type="button">Sign out</button>
        </form>
      </header>
      <p id="status" class="status">Sign in with a root account to load protected metrics. Device APIs remain available under /api/*.</p>
      <section id="metrics" class="grid" aria-live="polite">
        <article class="card"><p class="metric-label">Users</p><p id="usersTotal" class="metric-value">--</p><p id="usersNote" class="metric-note">registered</p></article>
        <article class="card"><p class="metric-label">DAU</p><p id="dau" class="metric-value">--</p><p id="activeNote" class="metric-note">user activity events</p></article>
        <article class="card"><p class="metric-label">Active Devices</p><p id="devicesActive" class="metric-value">--</p><p id="devicesNote" class="metric-note">today</p></article>
        <article class="card"><p class="metric-label">Renders</p><p id="rendersToday" class="metric-value">--</p><p id="rendersNote" class="metric-note">today</p></article>
        <article class="card wide"><p class="metric-label">New Users</p><div id="userBars" class="bars"><p class="empty">No data yet.</p></div></article>
        <article class="card wide"><p class="metric-label">Renders</p><div id="renderBars" class="bars"><p class="empty">No data yet.</p></div></article>
        <article class="card wide"><p class="metric-label">Top Modes 7d</p><div id="topModes" class="empty">No data yet.</div></article>
        <article class="card wide"><p class="metric-label">User Events 7d</p><div id="topEvents" class="empty">No data yet.</div></article>
      </section>
    </main>
    <script>
      const $ = (id) => document.getElementById(id);

      function fmt(n) {
        if (n === null || n === undefined) return "--";
        return Number(n).toLocaleString();
      }

      function setStatus(text, isError = false) {
        const el = $("status");
        el.textContent = text;
        el.className = isError ? "status error" : "status";
      }

      function renderTable(rows, columns) {
        if (!rows || rows.length === 0) return '<p class="empty">No data yet.</p>';
        const head = columns.map((c) => `<th>${c.label}</th>`).join("");
        const body = rows.map((row) => `<tr>${columns.map((c) => `<td>${row[c.key] || ""}</td>`).join("")}</tr>`).join("");
        return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
      }

      function renderBars(id, rows, key = "count") {
        if (!rows || rows.length === 0) {
          $(id).innerHTML = '<p class="empty">No data yet.</p>';
          return;
        }
        const ordered = [...rows].reverse();
        const max = Math.max(...ordered.map((d) => d[key] || 0), 1);
        $(id).innerHTML = ordered.map((d) => {
          const value = d[key] || 0;
          const h = Math.max(8, Math.round(value / max * 110));
          const label = String(d.day || "").slice(5);
          return `<div class="bar" title="${d.day}: ${value}" style="height:${h}px"><span>${label}</span></div>`;
        }).join("");
      }

      function render(data) {
        $("usersTotal").textContent = fmt(data.users.total);
        $("usersNote").textContent = `+${fmt(data.users.today_new)} today / +${fmt(data.users.new_7d)} 7d`;
        $("dau").textContent = fmt(data.users.dau);
        $("activeNote").textContent = `WAU ${fmt(data.users.wau)} / MAU ${fmt(data.users.mau)}`;
        $("devicesActive").textContent = fmt(data.devices.active_today);
        $("devicesNote").textContent = `${fmt(data.devices.bound)} bound / ${fmt(data.devices.active_7d)} active 7d`;
        $("rendersToday").textContent = fmt(data.rendering.today);
        $("rendersNote").textContent = `${fmt(data.rendering.last_7d)} 7d / ${fmt(data.rendering.avg_ms_today)}ms avg`;
        renderBars("userBars", data.series.new_users);
        renderBars("renderBars", data.series.renders);
        $("topModes").innerHTML = renderTable(data.top.modes, [{ key: "mode", label: "Mode" }, { key: "count", label: "Renders" }]);
        $("topEvents").innerHTML = renderTable(data.top.events, [{ key: "event_name", label: "Event" }, { key: "count", label: "Count" }]);
        setStatus(`Loaded at ${new Date().toLocaleString()}. Root session is active on this backend domain.`);
      }

      async function loadConsole() {
        setStatus("Loading metrics...");
        try {
          const res = await fetch("/api/admin/console/summary", { cache: "no-store", credentials: "same-origin" });
          if (res.status === 401) {
            setStatus("Sign in with a root account to load metrics.");
            return;
          }
          if (res.status === 403) throw new Error("Current account is not root.");
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          render(await res.json());
        } catch (err) {
          setStatus(`Failed to load console metrics: ${err.message}`, true);
        }
      }

      async function login(event) {
        event.preventDefault();
        const username = $("username").value.trim();
        const password = $("password").value;
        if (!username || !password) {
          setStatus("Username and password are required.", true);
          return;
        }
        setStatus("Signing in...");
        try {
          const res = await fetch("/api/auth/login", {
            method: "POST",
            credentials: "same-origin",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ username, password }),
          });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          $("password").value = "";
          await loadConsole();
        } catch (err) {
          setStatus(`Sign-in failed: ${err.message}`, true);
        }
      }

      async function logout() {
        await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" }).catch(() => {});
        setStatus("Signed out on this backend domain.");
      }

      $("loginForm").addEventListener("submit", login);
      $("logout").addEventListener("click", logout);
      fetch("/api/analytics/pageview", {
        method: "POST",
        credentials: "same-origin",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ path: location.pathname, source: "backend_console" }),
        keepalive: true,
      }).catch(() => {});
      loadConsole();
    </script>
  </body>
</html>"""


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
    return HTMLResponse(content=_backend_landing_html())


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
