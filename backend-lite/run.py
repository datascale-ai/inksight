"""backend-lite 启动入口。

直接读取 .env 中的 LITE_HOST / LITE_PORT，再调用 uvicorn.run()。
这解决了直接使用 `uvicorn ... --host ... --port ...` 时命令行参数覆盖 .env 的问题。
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
import uvicorn


load_dotenv()


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


if __name__ == "__main__":
    host = os.environ.get("LITE_HOST", "0.0.0.0").strip() or "0.0.0.0"
    port = _env_int("LITE_PORT", 8090)
    reload = os.environ.get("LITE_RELOAD", "").strip().lower() in {"1", "true", "yes", "on"}
    uvicorn.run("api.index:app", host=host, port=port, reload=reload)
