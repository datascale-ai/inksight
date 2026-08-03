"""backend-lite FastAPI 入口。

- 启动时把上游 backend/ 注入 sys.path，使 `from core.xxx import ...` 可用。
- 初始化 lite.db。
- 挂载固件路由 + 管理路由 + 静态管理页。
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# 先加载 .env，让 core/crypto 能读到 LLM_ENCRYPTION_KEY
load_dotenv()

# 注入上游 backend/ 到 sys.path
_BACKEND_DIR = os.environ.get("INKSIGHT_BACKEND_DIR") or str(
    Path(__file__).resolve().parent.parent.parent / "backend"
)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from store.db import close_db, init_db

from . import routes_admin, routes_device, routes_render

logging.basicConfig(
    level=os.environ.get("LITE_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("backend-lite")


class _AccessLogFilter(logging.Filter):
    """Hide noisy high-frequency polling endpoints from uvicorn.access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        noisy = (
            " /api/admin/state ",
            "/api/device/",
            "/state HTTP/1.1",
            "/alert-bmp?w=400&h=300",
        )
        if "uvicorn.access" in record.name and any(token in msg for token in noisy):
            # Keep render/config/heartbeat visible; hide only state/alert-bmp polling noise.
            if "/alert-bmp" in msg or "/state HTTP/1.1" in msg:
                return False
        return True


_uvicorn_access_logger = logging.getLogger("uvicorn.access")
if not any(isinstance(f, _AccessLogFilter) for f in _uvicorn_access_logger.filters):
    _uvicorn_access_logger.addFilter(_AccessLogFilter())


app = FastAPI(title="InkSight backend-lite", version="0.1.0")


def _install_native_dither_fallbacks() -> None:
    """在缺少 native dithering 动态库时，回退到 Pillow 方案。

    这样 MOYU/ARTWALL 这类依赖图片量化的模式不会直接 500。
    有 native 库时仍优先走上游实现。
    """
    from PIL import Image
    from core.config import EINK_4COLOR_PALETTE
    import core.native_dither as native_dither

    orig_bw = native_dither.atkinson_bw
    orig_palette = native_dither.atkinson_palette
    warned = {"bw": False, "palette": False}

    def _bw_fallback(gray: Image.Image) -> Image.Image:
        try:
            return orig_bw(gray)
        except RuntimeError as exc:
            if not warned["bw"]:
                logger.warning("[startup] native dithering unavailable, fallback to Pillow B/W dithering: %s", exc)
                warned["bw"] = True
            return gray.convert("1", dither=Image.Dither.FLOYDSTEINBERG)

    def _palette_fallback(rgb: Image.Image, colors: int) -> Image.Image:
        try:
            return orig_palette(rgb, colors)
        except RuntimeError as exc:
            if not warned["palette"]:
                logger.warning("[startup] native palette dithering unavailable, fallback to Pillow quantize: %s", exc)
                warned["palette"] = True
            palette_img = Image.new("P", (1, 1))
            palette_img.putpalette(EINK_4COLOR_PALETTE + [0] * (768 - len(EINK_4COLOR_PALETTE)))
            fallback_colors = 3 if colors == 3 else 4
            return rgb.convert("RGB").quantize(
                palette=palette_img,
                dither=Image.Dither.FLOYDSTEINBERG,
                colors=fallback_colors,
            )

    native_dither.atkinson_bw = _bw_fallback
    native_dither.atkinson_palette = _palette_fallback


@app.on_event("startup")
async def _startup() -> None:
    # 1) 重定向上游 core DB 路径到 backend-lite 目录（必须在任何 core DB 调用前）
    from adaptee.db_redirect import redirect_db_paths, init_upstream_tables

    redirect_db_paths()
    # 2) 初始化 backend-lite 自有库
    init_db()
    # 2.5) 安装 native dithering 缺失时的运行时降级，避免图片模式直接 500
    _install_native_dither_fallbacks()
    # 3) 初始化上游 stats_store / config_store / cache / static_store 表（core 运行时 lazy 依赖）
    try:
        await init_upstream_tables()
        from core.cache import init_cache_db
        from core.static_store import init_static_tables, migrate_device_state_columns
        await init_cache_db()
        await init_static_tables()
        await migrate_device_state_columns()
    except Exception:
        logger.exception("[startup] upstream table init failed")
    # 4) 触发上游模式注册表预加载（扫描 builtin/custom 目录）
    try:
        from core.mode_registry import get_registry

        get_registry()
    except Exception:
        logger.exception("[startup] mode registry preload failed")
    logger.info("[startup] backend-lite ready")


@app.on_event("shutdown")
async def _shutdown() -> None:
    """关闭 SQLite 连接/aiosqlite 工作线程，避免 Ctrl+C 后 Python 卡在退出阶段。"""
    try:
        from core.db import close_all

        await close_all()
    except Exception:
        logger.exception("[shutdown] upstream DB close failed")
    try:
        close_db()
    except Exception:
        logger.exception("[shutdown] lite DB close failed")
    logger.info("[shutdown] backend-lite connections closed")


# 固件路由（/api 前缀）
app.include_router(routes_render.router)
app.include_router(routes_device.router)
# 管理路由（/api/admin）
app.include_router(routes_admin.router)


# 静态管理页
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/")
async def root():
    return FileResponse(str(_STATIC_DIR / "index.html"))