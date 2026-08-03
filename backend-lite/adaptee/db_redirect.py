"""把上游 core/ 的 SQLite 路径重定向到 backend-lite 目录，避免污染上游 backend/。

core 运行时（json_content/pipeline）会 lazy 调用 stats_store / config_store /
cache 的函数，它们读写 backend/inksight.db 和 backend/cache.db。这里把这些
模块级路径常量改写为 backend-lite 目录下的副本，并调上游建表函数初始化。

必须在任何 core DB 调用前调用 redirect_db_paths()。
"""
from __future__ import annotations

import os
from pathlib import Path

_LITE_DIR = Path(__file__).resolve().parent.parent
_INKSIGHT_DB = str(_LITE_DIR / "inksight.db")
_CACHE_DB = str(_LITE_DIR / "cache.db")


def redirect_db_paths() -> None:
    """改写 core 各模块的 DB 路径常量，指向 backend-lite 目录。"""
    import core.db as cdb
    import core.stats_store as stats
    import core.config_store as cstore
    import core.cache as cache

    cdb._MAIN_DB_PATH = _INKSIGHT_DB
    cdb._CACHE_DB_PATH = _CACHE_DB
    stats.DB_PATH = _INKSIGHT_DB
    cstore.DB_PATH = _INKSIGHT_DB
    # cache 模块若用 _CACHE_DB_PATH 常量
    if hasattr(cache, "_CACHE_DB_PATH"):
        cache._CACHE_DB_PATH = _CACHE_DB
    if hasattr(cache, "CACHE_DB_PATH"):
        cache.CACHE_DB_PATH = _CACHE_DB


async def init_upstream_tables() -> None:
    """调用上游建表函数（建在重定向后的 backend-lite 库里）。

    只建 core 运行时真正需要的表：stats_store（content_history 去重、
    device_heartbeats 在线判断）、config_store（photo_frame_index 等）。
    多用户相关表也会被 config_store.init_db 创建，空着不用，无害。
    """
    from core.stats_store import init_stats_db
    from core.config_store import init_db as config_init_db

    await init_stats_db()
    await config_init_db()