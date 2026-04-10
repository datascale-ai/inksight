"""
静态内容生成模块

职责：在 pipeline.py 进入 LLM 分发之前，拦截 5 个静态模式的请求，
从 SQLite 本地知识库中查询内容并返回，绕过 LLM 调用。

对于 preview 模式（mac 为空），使用随机选择，不写游标状态。

降级策略：
- 静态库无数据时，返回 fallback 内容 dict，并标记 `_static_fallback = True`，
  上层感知此标记后降级走原有 LLM 路径。
- 查询异常时记录日志，返回 fallback，不崩溃。
"""
from __future__ import annotations

import logging
import random
from datetime import date
from typing import Optional

from .static_store import (
    STATIC_MODE_IDS,
    fetch_next_poetry,
    fetch_next_riddle,
    fetch_thisday_record,
    is_poetry_available,
    is_riddle_available,
    is_thisday_available,
)

logger = logging.getLogger(__name__)

# 各模式的 fallback 内容（与原 JSON mode 定义中的 fallback 完全对齐）
_FALLBACKS: dict[str, dict] = {
    "POETRY": {
        "title":  "静夜思",
        "author": "唐·李白",
        "lines":  ["床前明月光", "疑是地上霜", "举头望明月", "低头思故乡"],
        "note":   "千古思乡名篇",
    },
    "RIDDLE": {
        "category": "谜语",
        "question": "两个胖子（打一城市名）",
        "hint":     "想想体重",
        "answer":   "合肥",
    },
    "THISDAY": {
        "year":         "1969",
        "event_title":  "人类首次登月",
        "event_desc":   "阿波罗11号宇航员阿姆斯特朗踏上月球表面，说出了那句著名的话。",
        "years_ago":     "57年前",
        "significance": "人类太空探索的里程碑",
    },
}


async def generate_static_content(
    mode_id: str,
    mac: str,
    date_ctx: Optional[dict] = None,
) -> dict:
    """静态内容生成入口。按 mode_id 分发到对应查询函数。

    Args:
        mode_id: 模式 ID（大写）
        mac:     设备 MAC 地址（用于防重游标）
        date_ctx: 日期上下文（THISDAY/ALMANAC 需要 month/day）

    Returns:
        内容字典，格式与原 JSON 模式的 fallback 一致。
        若静态库无数据，返回 fallback 并标记 `_static_fallback = True`。
    """
    mode_id = mode_id.upper()

    if mode_id not in STATIC_MODE_IDS:
        # 非静态模式，返回 fallback 标记让调用方走 LLM 路径
        return {"_static_fallback": True}

    today = date.today()
    month = today.month
    day = today.day

    # 从 date_ctx 提取月日（如果提供了更精确的日期）
    if date_ctx:
        if isinstance(date_ctx.get("month"), int):
            month = int(date_ctx["month"])
        if isinstance(date_ctx.get("day"), int):
            day = int(date_ctx["day"])

    is_preview = not mac or mac.upper() in ("PREVIEW", "N/A", "")

    try:
        if mode_id == "POETRY":
            return await _generate_poetry(mac, is_preview)
        if mode_id == "RIDDLE":
            return await _generate_riddle(mac, is_preview)
        if mode_id == "THISDAY":
            return await _generate_thisday(mac, is_preview, month, day)
    except Exception as e:
        logger.warning(f"[StaticContent] Query failed for {mode_id}: {e}", exc_info=True)

    # 任何异常，降级返回 fallback 并标记降级
    fb = dict(_FALLBACKS.get(mode_id, {}))
    fb["_static_fallback"] = True
    return fb


async def _generate_poetry(mac: str, is_preview: bool) -> dict:
    """生成诗词内容。"""
    if is_preview:
        # preview 模式：随机选择，不写游标
        if await is_poetry_available():
            from .db import get_main_db
            db = await get_main_db()
            cursor = await db.execute(
                "SELECT id, title, author, dynasty, lines_json, note FROM static_poetry ORDER BY RANDOM() LIMIT 1"
            )
            row = await cursor.fetchone()
            if row:
                import json as _json
                try:
                    lines = _json.loads(row[4])
                except Exception:
                    lines = []
                return {
                    "title": row[1] or "", "author": row[2] or "",
                    "lines": lines, "note": row[5] or "",
                }
        fb = dict(_FALLBACKS["POETRY"])
        fb["_static_fallback"] = True
        return fb

    result = await fetch_next_poetry(mac)
    if result:
        return result
    fb = dict(_FALLBACKS["POETRY"])
    fb["_static_fallback"] = True
    return fb


async def _generate_riddle(mac: str, is_preview: bool) -> dict:
    """生成谜语内容。"""
    if is_preview:
        if await is_riddle_available():
            from .db import get_main_db
            db = await get_main_db()
            cursor = await db.execute(
                "SELECT id, category, question, hint, answer FROM static_riddle ORDER BY RANDOM() LIMIT 1"
            )
            row = await cursor.fetchone()
            if row:
                return {
                    "category": row[1] or "谜语",
                    "question": row[2] or "",
                    "hint":     row[3] or "",
                    "answer":   row[4] or "",
                }
        fb = dict(_FALLBACKS["RIDDLE"])
        fb["_static_fallback"] = True
        return fb

    result = await fetch_next_riddle(mac)
    if result:
        return result
    fb = dict(_FALLBACKS["RIDDLE"])
    fb["_static_fallback"] = True
    return fb


def _build_daily_meta(date_ctx: Optional[dict]) -> dict:
    """构建 daily_meta 所需的日期元数字段。"""
    today = date.today()
    year = today.year
    day = today.day
    weekday = today.weekday()
    day_of_year = today.timetuple().tm_yday
    days_in_year = 366 if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0) else 365

    if date_ctx:
        if isinstance(date_ctx.get("year"), int):
            year = date_ctx["year"]
        if isinstance(date_ctx.get("day"), int):
            day = date_ctx["day"]
        if isinstance(date_ctx.get("weekday"), int):
            weekday = date_ctx["weekday"]
        if isinstance(date_ctx.get("day_of_year"), int):
            day_of_year = date_ctx["day_of_year"]
        if isinstance(date_ctx.get("days_in_year"), int):
            days_in_year = date_ctx["days_in_year"]

    lunar_months_cn = ["", "一月", "二月", "三月", "四月", "五月", "六月",
                       "七月", "八月", "九月", "十月", "十一月", "腊月"]
    weekdays_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return {
        "year":        year,
        "day":        day,
        "month_cn":    lunar_months_cn[today.month],
        "weekday_cn":  weekdays_cn[weekday],
        "day_of_year": day_of_year,
        "days_in_year": days_in_year,
    }


async def _generate_thisday(mac: str, is_preview: bool, month: int, day: int) -> dict:
    """生成历史上的今天内容。使用轮询索引展示当天不同事件。"""
    if is_preview:
        # preview：随机选一条
        if await is_thisday_available(month, day):
            from .db import get_main_db
            db = await get_main_db()
            cursor = await db.execute(
                "SELECT id, year, event_title, event_desc, years_ago, significance FROM static_thisday WHERE month = ? AND day = ? ORDER BY RANDOM() LIMIT 1",
                (month, day),
            )
            row = await cursor.fetchone()
            if row:
                return {
                    "year":         str(row[1]) if row[1] else "",
                    "event_title":  row[2] or "",
                    "event_desc":   row[3] or "",
                    "years_ago":    row[4] or "",
                    "significance": row[5] or "",
                }
        fb = dict(_FALLBACKS["THISDAY"])
        fb["_static_fallback"] = True
        return fb

    result = await fetch_thisday_record(month, day, mac)
    if result:
        return result
    fb = dict(_FALLBACKS["THISDAY"])
    fb["_static_fallback"] = True
    return fb


def should_use_static_fallback(content: dict) -> bool:
    """判断静态内容是否降级到 LLM。当静态库为空时返回 True。"""
    return bool(content.get("_static_fallback"))
