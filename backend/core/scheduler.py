"""
静态数据调度器

负责定时更新静态数据库中的内容：
- 日更任务 (job_daily_thisday): 每天 04:00 从 Wikipedia 获取历史今日
- 周更任务 (job_weekly_update): 每周一 03:00 通过 LLM 生成新谜语

古诗词数据仅在首次初始化时加载一次，之后保持不变。

使用方法：
    from core.scheduler import scheduler, job_weekly_update
    scheduler.start()

    # 或手动触发
    await job_weekly_update()
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date
from datetime import datetime
from typing import Optional

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .db import get_main_db

logger = logging.getLogger(__name__)

# ── 全局调度器实例 ────────────────────────────────────────────

scheduler = AsyncIOScheduler()


async def start_scheduler() -> None:
    """启动 APScheduler，将所有任务加入调度队列。

    如果诗词数据库尚未初始化（为空），会自动触发首次全量加载。
    """
    if scheduler.running:
        logger.warning("[Scheduler] Already running, skipping start")
        return

    # 检查诗词数据库是否需要初始化
    from .static_store import is_poetry_initialized
    if not await is_poetry_initialized():
        logger.info("[Scheduler] Poetry DB empty, triggering initial load...")
        await job_initial_load()

    # 日更任务：每天 04:00 更新历史今日
    scheduler.add_job(
        job_daily_thisday,
        CronTrigger(hour=4, minute=0),
        id="daily_thisday",
        name="Daily Thisday Update",
        misfire_grace_time=3600,
    )

    # 周更任务：每周一 03:00 通过 LLM 生成新谜语
    scheduler.add_job(
        job_weekly_update,
        CronTrigger(day_of_week="mon", hour=3, minute=0),
        id="weekly_update",
        name="Weekly Static Data Update",
        misfire_grace_time=7200,
    )

    scheduler.start()
    logger.info("[Scheduler] Started with %d jobs", len(scheduler.get_jobs()))


async def stop_scheduler() -> None:
    """停止调度器。"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Stopped")


# ── 日更任务 ──────────────────────────────────────────────────


async def job_daily_thisday() -> None:
    """日更任务：每天从 Wikipedia 获取当天的历史事件并写入数据库。"""
    now = datetime.now()
    month, day = now.month, now.day
    logger.info("[DailyJob] Starting thisday update for %02d/%02d", month, day)

    try:
        events = await _fetch_wikipedia_thisday(month, day)
        if events:
            await _save_thisday_events(month, day, events)
            logger.info("[DailyJob] THISDAY updated with %d events", len(events))
        else:
            logger.warning("[DailyJob] THISDAY no events fetched, skipping save")
    except Exception as e:
        logger.error("[DailyJob] THISDAY update failed: %s", e, exc_info=True)


# ── 周更任务 ──────────────────────────────────────────────────


async def job_weekly_update() -> None:
    """周更任务：更新 RIDDLE（谜语）。

    通过 LLM 实时生成谜语数据。

    原子性操作（先插后删原则）：
    - 开启事务 → 插入新数据 → 删除旧数据（只保留最新 N 条）→ 提交
    - 任意环节失败 → 回滚，保留所有旧数据
    """
    logger.info("[WeeklyJob] Starting weekly update (RIDDLE)")

    # --- RIDDLE（通过 LLM 生成 100 条）---
    try:
        riddles = await _load_riddles_from_json()
        if riddles:
            await _save_riddles_with_cleanup(riddles, keep_count=100)
            logger.info("[WeeklyJob] RIDDLE updated with %d riddles", len(riddles))
        else:
            logger.warning("[WeeklyJob] RIDDLE no data loaded, skipping save")
    except Exception as e:
        logger.error("[WeeklyJob] RIDDLE update failed: %s", e, exc_info=True)


async def job_initial_load() -> None:
    """首次全量加载任务：将所有诗词数据一次性拉取并存入数据库。

    调用 _fetch_all_poems_from_github() 获取全量数据（约 23000 首），
    然后分批写入数据库。

    注意：此任务应在系统初始化时执行一次。
    """
    logger.info("[InitialLoad] Starting initial full load of poems")

    try:
        # 全量拉取所有诗词
        poems = await _fetch_all_poems_from_github()
        if poems:
            # 分批写入，每批 1000 条
            batch_size = 1000
            total_batches = (len(poems) + batch_size - 1) // batch_size
            logger.info("[InitialLoad] Total %d poems, will save in %d batches", len(poems), total_batches)

            for i in range(0, len(poems), batch_size):
                batch = poems[i:i + batch_size]
                batch_num = i // batch_size + 1
                await _save_all_poems(batch)
                logger.info("[InitialLoad] Saved batch %d/%d (%d poems)", batch_num, total_batches, len(batch))

            logger.info("[InitialLoad] Completed: %d poems saved", len(poems))
        else:
            logger.warning("[InitialLoad] No poems fetched, skipping save")
    except Exception as e:
        logger.error("[InitialLoad] Failed: %s", e, exc_info=True)


# ═══════════════════════════════════════════════════════════════
# 数据获取函数
# ═══════════════════════════════════════════════════════════════

# ── THISDAY 数据获取 ──────────────────────────────────────────


async def _fetch_wikipedia_thisday(month: int, day: int) -> list[dict]:
    """从 Wikipedia API 抓取当天的历史事件（中文内容）。

    API: https://zh.wikipedia.org/api/rest_v1/feed/onthisday/all/{month}/{day}

    返回格式：
        [{
            "year": 1969,
            "title": "...",
            "desc": "...",
            "years_ago": "57年前",
            "significance": "..."
        }, ...]
    """
    url = f"https://zh.wikipedia.org/api/rest_v1/feed/onthisday/all/{month:02d}/{day:02d}"
    headers = {
        "User-Agent": "InkSight/1.0 (https://github.com/your-repo)",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0, limits=httpx.Limits(max_keepalive_connections=5)) as client:
            resp = await client.get(url, headers=headers)

        if resp.status_code != 200:
            logger.warning("[Wikipedia] HTTP %d for %02d/%02d", resp.status_code, month, day)
            return []

        data = resp.json()
        events: list[dict] = []

        # 解析 "selected" 字段（主要历史事件）
        for item in data.get("selected", []):
            year = item.get("year")
            if not year or not isinstance(year, int):
                continue

            text = item.get("text", "")
            # 过滤掉太短的事件描述
            if len(text) < 10:
                continue

            # 提取 Wikipedia 页面摘要作为 significance
            pages = item.get("pages", [])
            significance = ""
            for page in pages[:1]:
                desc = page.get("extract", "")
                if desc:
                    significance = desc[:100]  # 截断到 100 字符
                else:
                    desc = page.get("description", "")
                    if desc:
                        significance = desc[:100]

            years_ago = _calc_years_ago(year)

            events.append({
                "year": year,
                "title": text,
                "desc": text,
                "years_ago": years_ago,
                "significance": significance,
            })

            # 限制最多 20 条事件
            if len(events) >= 20:
                break

        logger.info("[Wikipedia] Fetched %d events for %02d/%02d", len(events), month, day)
        return events

    except Exception as e:
        logger.error("[Wikipedia] Fetch failed for %02d/%02d: %s", month, day, e, exc_info=True)
        return []


def _calc_years_ago(year: int) -> str:
    """计算距离今年的年份差。"""
    try:
        current_year = date.today().year
        diff = current_year - year
        if diff <= 0:
            return "今年"
        if diff == 1:
            return "1年前"
        return f"{diff}年前"
    except Exception:
        return ""


# ── POETRY 数据获取 ──────────────────────────────────────────


async def _fetch_all_poems_from_github() -> list[dict]:
    """从 chinese-poetry GitHub 一次性拉取所有古诗词数据。

    数据源：https://github.com/chinese-poetry/chinese-poetry
    - 全唐诗：1 个分片 (poet.tang.0.json，约 1000 首)
    - 宋词：22 个分片 (ci.song.0.json ~ ci.song.21000.json，每个约 1000 首)

    首次拉取约 23000 首诗词存入数据库，之后每周增量更新新数据。
    """
    import urllib.parse

    base_url = "https://raw.githubusercontent.com/chinese-poetry/chinese-poetry/master"

    poems: list[dict] = []
    collections = [
        ("全唐诗", "poet.tang.", [0]),          # 唐诗只有 1 个分片
        ("宋词", "ci.song.", list(range(0, 22000, 1000))),  # 宋词 22 个分片
    ]

    try:
        async with httpx.AsyncClient(timeout=120.0, limits=httpx.Limits(max_keepalive_connections=5)) as client:
            for dir_name, prefix, shard_indices in collections:
                for i in shard_indices:
                    encoded_dir = urllib.parse.quote(dir_name)
                    url = f"{base_url}/{encoded_dir}/{prefix}{i}.json"
                    try:
                        resp = await client.get(url)
                        if resp.status_code == 200:
                            data = resp.json()
                            for item in data:
                                # 统一数据格式
                                if "poet." in prefix:
                                    # 唐诗格式：{title, author, paragraphs}
                                    title = item.get("title", "")
                                    author = item.get("author", "")
                                else:
                                    # 宋词格式：{author, paragraphs, rhythmic}
                                    title = item.get("rhythmic", "")
                                    author = item.get("author", "")

                                poems.append({
                                    "title": title,
                                    "author": author,
                                    "dynasty": "唐" if "tang" in prefix else "宋",
                                    "lines": item.get("paragraphs", []),
                                    "note": _extract_poem_note(item),
                                    "season_tag": _guess_season_from_poem(item),
                                })
                            logger.info("[GitHub] Fetched %s %d, total poems: %d", dir_name, i, len(poems))
                    except Exception as e:
                        logger.debug("[GitHub] Failed to fetch %s: %s", url, e)
                        continue

        logger.info("[GitHub] Total poems fetched: %d", len(poems))
        return poems

    except Exception as e:
        logger.error("[GitHub] Failed to fetch all poems: %s", e, exc_info=True)
        return []


async def _fetch_poems_from_github(count: int = 100) -> list[dict]:
    """从 chinese-poetry GitHub 拉取指定数量的古诗词数据（用于增量更新）。"""
    import random

    all_poems = await _fetch_all_poems_from_github()
    if all_poems:
        random.shuffle(all_poems)
    return all_poems[:count]


def _extract_poem_note(item: dict) -> str:
    """从诗词数据中提取注释或简介。"""
    return item.get("note", item.get("translate", ""))[:200]


def _guess_season_from_poem(item: dict) -> str:
    """根据诗词内容猜测季节标签。"""
    text = "".join(item.get("paragraphs", []))
    spring = ["春", "柳", "花", "燕", "东风"]
    summer = ["夏", "荷", "蝉", "烈日"]
    autumn = ["秋", "月", "桂", "枫", "西风"]
    winter = ["冬", "雪", "梅", "寒"]

    for kw in spring:
        if kw in text:
            return "春"
    for kw in summer:
        if kw in text:
            return "夏"
    for kw in autumn:
        if kw in text:
            return "秋"
    for kw in winter:
        if kw in text:
            return "冬"

    return "四时皆宜"


# ── RIDDLE 谜语获取 ───────────────────────────────────────────


async def _load_riddles_from_json() -> list[dict]:
    """通过 LLM 实时生成 100 条不重复的谜语。

    每次周更时调用 LLM 生成新的谜语数据。
    """
    import random

    riddles = await _generate_riddles_with_llm(count=100)
    random.shuffle(riddles)
    logger.info("[Riddles] Generated total %d riddles", len(riddles))
    return riddles[:100]


async def _generate_riddles_with_llm(count: int = 50) -> list[dict]:
    """使用 LLM 生成不重复的谜语。

    Args:
        count: 需要生成的谜语数量

    Returns:
        谜语列表，每条包含 category, question, hint, answer
    """
    from .content import call_llm

    # 根据需要的数量调整批次
    batch_size = min(count, 20)
    batches = (count + batch_size - 1) // batch_size

    all_riddles = []
    existing_questions: set[str] = set()

    for _ in range(batches):
        prompt = f"""请生成 {batch_size} 条中国传统谜语，以 JSON 数组格式返回。

要求：
1. 每条谜语包含以下字段：category（字谜/物谜/地名谜/人名谜）, question（谜面，20字以内）, hint（提示）, answer（谜底）
2. 谜语要有趣味性，不能太简单也不能太难
3. 谜底以"谜底："开头，方便解析

格式示例：
[
  {{"category": "字谜", "question": "一加一（打一字）", "hint": "不等于二", "answer": "谜底：王"}},
  {{"category": "物谜", "question": "千条线，万条线（打一自然现象）", "hint": "从天而降", "answer": "谜底：雨"}}
]

请直接返回 JSON 数组，不要其他文字："""

        try:
            response = await call_llm(
                prompt=prompt,
                system_prompt="你是一个专业的谜语专家，擅长创作中国传统谜语。只返回 JSON 数组，不要其他文字。",
                temperature=0.9,
                max_tokens=4000,
            )

            if response:
                # 尝试解析 JSON
                riddles = _parse_riddles_from_response(response)
                for r in riddles:
                    q = r.get("question", "")
                    # 去除重复
                    if q and q not in existing_questions:
                        # 清理谜底字段（去掉"谜底："前缀）
                        answer = r.get("answer", "")
                        if answer.startswith("谜底："):
                            answer = answer[3:]
                        r["answer"] = answer
                        existing_questions.add(q)
                        all_riddles.append(r)

        except Exception as e:
            logger.error("[LLM Riddles] Generation failed: %s", e, exc_info=True)
            raise  # 重新抛出异常以便调试

        # 避免请求过多
        if len(all_riddles) >= count:
            break

    return all_riddles


def _parse_riddles_from_response(response: str) -> list[dict]:
    """从 LLM 响应中解析谜语 JSON。"""
    import re

    riddles = []

    # 尝试直接解析 JSON
    try:
        riddles = json.loads(response)
        if isinstance(riddles, list):
            return riddles
    except json.JSONDecodeError:
        pass

    # 尝试提取 JSON 数组
    patterns = [
        r'\[[\s\S]*\]',  # 整个数组
        r'\{[\s\S]*\}',  # 单个或多个对象
    ]

    for pattern in patterns:
        matches = re.findall(pattern, response)
        for match in matches:
            try:
                data = json.loads(match)
                if isinstance(data, list):
                    riddles.extend(data)
                elif isinstance(data, dict):
                    riddles.append(data)
            except json.JSONDecodeError:
                continue

    # 验证每条谜语格式
    valid_riddles = []
    for r in riddles:
        if isinstance(r, dict) and "question" in r and "answer" in r:
            valid_riddles.append(r)

    return valid_riddles


# ═══════════════════════════════════════════════════════════════
# 数据写入函数（事务安全）
# ═══════════════════════════════════════════════════════════════

# ── THISDAY 写入 ──────────────────────────────────────────────


async def _save_thisday_events(month: int, day: int, events: list[dict]) -> None:
    """将当天的历史事件写入 static_thisday 表。

    先删除旧数据，再插入新数据（事务保护）。
    """
    db = await get_main_db()

    try:
        await db.execute("BEGIN TRANSACTION")

        # 删除当天旧数据
        await db.execute(
            "DELETE FROM static_thisday WHERE month = ? AND day = ?",
            (month, day),
        )

        # 插入新数据
        for event in events:
            await db.execute(
                """INSERT INTO static_thisday
                   (month, day, year, event_title, event_desc, years_ago, significance)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    month,
                    day,
                    event["year"],
                    event["title"],
                    event["desc"],
                    event["years_ago"],
                    event.get("significance", ""),
                ),
            )

        await db.execute("COMMIT")
        logger.info("[DB] THISDAY saved %d events for %02d/%02d", len(events), month, day)

    except Exception as e:
        await db.execute("ROLLBACK")
        logger.error("[DB] THISDAY save failed, rolled back: %s", e, exc_info=True)
        raise


# ── POETRY 写入 ───────────────────────────────────────────────


async def _save_poems_with_cleanup(poems: list[dict], keep_count: int = 100) -> None:
    """将新诗词写入 static_poetry 表，并清理旧数据。

    原子性操作：先插新数据 → 再删旧数据（只保留最新 keep_count 条）。
    """
    db = await get_main_db()

    try:
        await db.execute("BEGIN TRANSACTION")

        # 查询当前旧数据数量
        result = await db.execute("SELECT COUNT(*) FROM static_poetry")
        row = await result.fetchone()
        old_count = row[0] if row else 0
        logger.info("[DB] POETRY before save: %d records", old_count)

        # 先插新数据
        insert_count = 0
        for poem in poems:
            lines_json = json.dumps(poem.get("lines", []), ensure_ascii=False)
            await db.execute(
                """INSERT INTO static_poetry
                   (title, author, dynasty, lines_json, note, season_tag)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    poem.get("title", ""),
                    poem.get("author", ""),
                    poem.get("dynasty", ""),
                    lines_json,
                    poem.get("note", ""),
                    poem.get("season_tag", ""),
                ),
            )
            insert_count += 1

        logger.info("[DB] POETRY inserted %d new records", insert_count)

        # 插入成功后再删旧数据（按 created_at 升序，删除最早的直到只剩 keep_count 条）
        await db.execute(
            """DELETE FROM static_poetry
               WHERE id IN (
                   SELECT id FROM static_poetry
                   ORDER BY created_at ASC
                   LIMIT MAX(0, (SELECT COUNT(*) FROM static_poetry) - ?)
               )""",
            (keep_count,),
        )

        # 查询删除后的数量
        result = await db.execute("SELECT COUNT(*) FROM static_poetry")
        row = await result.fetchone()
        new_count = row[0] if row else 0
        deleted_count = old_count + insert_count - new_count

        await db.execute("COMMIT")
        logger.info("[DB] POETRY saved: inserted %d, deleted %d (kept %d), final count: %d",
                    insert_count, deleted_count, new_count, new_count)

    except Exception as e:
        await db.execute("ROLLBACK")
        logger.error("[DB] POETRY save failed, rolled back: %s", e, exc_info=True)
        raise


async def _save_all_poems(poems: list[dict]) -> None:
    """将诗词数据批量写入 static_poetry 表（用于首次全量加载，不清理旧数据）。"""
    db = await get_main_db()

    try:
        await db.execute("BEGIN TRANSACTION")

        # 查询当前数量
        result = await db.execute("SELECT COUNT(*) FROM static_poetry")
        row = await result.fetchone()
        old_count = row[0] if row else 0

        insert_count = 0
        for poem in poems:
            lines_json = json.dumps(poem.get("lines", []), ensure_ascii=False)
            await db.execute(
                """INSERT INTO static_poetry
                   (title, author, dynasty, lines_json, note, season_tag)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    poem.get("title", ""),
                    poem.get("author", ""),
                    poem.get("dynasty", ""),
                    lines_json,
                    poem.get("note", ""),
                    poem.get("season_tag", ""),
                ),
            )
            insert_count += 1

        await db.execute("COMMIT")

        result = await db.execute("SELECT COUNT(*) FROM static_poetry")
        row = await result.fetchone()
        new_count = row[0] if row else 0

        logger.info("[DB] POETRY initial load: inserted %d, total now: %d (was %d)",
                    insert_count, new_count, old_count)

    except Exception as e:
        await db.execute("ROLLBACK")
        logger.error("[DB] POETRY batch save failed, rolled back: %s", e, exc_info=True)
        raise


# ── RIDDLE 写入 ────────────────────────────────────────────────


async def _save_riddles_with_cleanup(riddles: list[dict], keep_count: int = 100) -> None:
    """将新谜语写入 static_riddle 表，并清理旧数据。"""
    db = await get_main_db()

    try:
        await db.execute("BEGIN TRANSACTION")

        # 查询当前旧数据数量
        result = await db.execute("SELECT COUNT(*) FROM static_riddle")
        row = await result.fetchone()
        old_count = row[0] if row else 0
        logger.info("[DB] RIDDLE before save: %d records", old_count)

        # 插入新数据
        insert_count = 0
        for item in riddles:
            await db.execute(
                """INSERT INTO static_riddle
                   (category, question, hint, answer)
                   VALUES (?, ?, ?, ?)""",
                (
                    item.get("category", ""),
                    item.get("question", ""),
                    item.get("hint", ""),
                    item.get("answer", ""),
                ),
            )
            insert_count += 1

        logger.info("[DB] RIDDLE inserted %d new records", insert_count)

        # 删除旧数据
        await db.execute(
            """DELETE FROM static_riddle
               WHERE id IN (
                   SELECT id FROM static_riddle
                   ORDER BY created_at ASC
                   LIMIT MAX(0, (SELECT COUNT(*) FROM static_riddle) - ?)
               )""",
            (keep_count,),
        )

        # 查询删除后的数量
        result = await db.execute("SELECT COUNT(*) FROM static_riddle")
        row = await result.fetchone()
        new_count = row[0] if row else 0
        deleted_count = old_count + insert_count - new_count

        await db.execute("COMMIT")
        logger.info("[DB] RIDDLE saved: inserted %d, deleted %d, final count: %d",
                    insert_count, deleted_count, new_count)

    except Exception as e:
        await db.execute("ROLLBACK")
        logger.error("[DB] RIDDLE save failed, rolled back: %s", e, exc_info=True)
        raise
