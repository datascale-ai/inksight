from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogText:
    name: str
    tip: str = ""


@dataclass(frozen=True)
class CatalogItem:
    mode_id: str
    category: str  # "core" | "more" | "custom"
    zh: CatalogText
    en: CatalogText


# Single source of truth for builtin mode grouping + UI copy.
# - Builtin (including builtin_json): define here to keep preview/config in sync.
# - Custom modes: generated dynamically by backend and forced into category="custom".
BUILTIN_CATALOG: list[CatalogItem] = [
    # ── Core (recommended) ─────────────────────────────────────
    CatalogItem(
        mode_id="DAILY",
        category="core",
        zh=CatalogText(name="每日", tip="语录、书籍推荐、冷知识的综合日报"),
        en=CatalogText(name="Everyday", tip="A daily digest: quotes, book picks, and fun facts"),
    ),
    CatalogItem(
        mode_id="WEATHER",
        category="core",
        zh=CatalogText(name="天气", tip="实时天气和未来趋势看板"),
        en=CatalogText(name="Weather", tip="Current weather and forecast dashboard"),
    ),
    CatalogItem(
        mode_id="ZEN",
        category="core",
        zh=CatalogText(name="禅意", tip="一个大字表达当下心境"),
        en=CatalogText(name="Zen", tip="A single character to reflect your mood"),
    ),
    CatalogItem(
        mode_id="BRIEFING",
        category="core",
        zh=CatalogText(name="简报", tip="科技热榜 + AI 洞察简报"),
        en=CatalogText(name="Briefing", tip="Tech trends + AI insights briefing"),
    ),
    CatalogItem(
        mode_id="STOIC",
        category="core",
        zh=CatalogText(name="斯多葛", tip="每日一句哲学箴言"),
        en=CatalogText(name="Stoic", tip="A daily stoic quote"),
    ),
    CatalogItem(
        mode_id="POETRY",
        category="core",
        zh=CatalogText(name="诗词", tip="古诗词与简短注解"),
        en=CatalogText(name="Poetry", tip="Classical poetry with a short note"),
    ),
    CatalogItem(
        mode_id="ARTWALL",
        category="core",
        zh=CatalogText(name="画廊", tip="根据时令生成黑白艺术画"),
        en=CatalogText(name="Gallery", tip="Seasonal black & white generative art"),
    ),
    CatalogItem(
        mode_id="ALMANAC",
        category="core",
        zh=CatalogText(name="老黄历", tip="农历、节气、宜忌信息"),
        en=CatalogText(name="Almanac", tip="Lunar calendar, solar terms, and daily luck"),
    ),
    CatalogItem(
        mode_id="RECIPE",
        category="core",
        zh=CatalogText(name="食谱", tip="按时段推荐三餐方案"),
        en=CatalogText(name="Recipe", tip="Meal ideas based on time of day"),
    ),
    CatalogItem(
        mode_id="COUNTDOWN",
        category="core",
        zh=CatalogText(name="倒计时", tip="重要日程倒计时/正计时"),
        en=CatalogText(name="Countdown", tip="Countdown / count-up for important events"),
    ),
    # ── More (everything else builtin) ─────────────────────────
    CatalogItem(
        mode_id="MEMO",
        category="more",
        zh=CatalogText(name="便签", tip="展示自定义便签文字"),
        en=CatalogText(name="Memo", tip="Show your custom memo text"),
    ),
    CatalogItem(
        mode_id="HABIT",
        category="more",
        zh=CatalogText(name="打卡", tip="每日习惯完成进度"),
        en=CatalogText(name="Habits", tip="Daily habit progress"),
    ),
    CatalogItem(
        mode_id="ROAST",
        category="more",
        zh=CatalogText(name="毒舌", tip="轻松幽默的吐槽风格内容"),
        en=CatalogText(name="Roast", tip="Lighthearted, sarcastic daily roast"),
    ),
    CatalogItem(
        mode_id="FITNESS",
        category="more",
        zh=CatalogText(name="健身", tip="居家健身动作与建议"),
        en=CatalogText(name="Fitness", tip="At-home workout tips"),
    ),
    CatalogItem(
        mode_id="LETTER",
        category="more",
        zh=CatalogText(name="慢信", tip="来自不同时空的一封慢信"),
        en=CatalogText(name="Letter", tip="A slow letter from another time"),
    ),
    CatalogItem(
        mode_id="THISDAY",
        category="more",
        zh=CatalogText(name="今日历史", tip="历史上的今天重大事件"),
        en=CatalogText(name="On This Day", tip="Major events in history today"),
    ),
    CatalogItem(
        mode_id="RIDDLE",
        category="more",
        zh=CatalogText(name="猜谜", tip="谜题与脑筋急转弯"),
        en=CatalogText(name="Riddle", tip="Riddles and brain teasers"),
    ),
    CatalogItem(
        mode_id="QUESTION",
        category="more",
        zh=CatalogText(name="每日一问", tip="值得思考的开放式问题"),
        en=CatalogText(name="Daily Question", tip="A thought-provoking open question"),
    ),
    CatalogItem(
        mode_id="BIAS",
        category="more",
        zh=CatalogText(name="认知偏差", tip="认知偏差与心理效应"),
        en=CatalogText(name="Bias", tip="A cognitive bias or psychological effect"),
    ),
    CatalogItem(
        mode_id="STORY",
        category="more",
        zh=CatalogText(name="微故事", tip="可在 30 秒内读完的微故事"),
        en=CatalogText(name="Micro Story", tip="A complete micro fiction in three parts"),
    ),
    CatalogItem(
        mode_id="LIFEBAR",
        category="more",
        zh=CatalogText(name="进度条", tip="年/月/周/人生进度条"),
        en=CatalogText(name="Life Bar", tip="Progress bars for year / month / week / life"),
    ),
    CatalogItem(
        mode_id="CHALLENGE",
        category="more",
        zh=CatalogText(name="微挑战", tip="每天一个 5 分钟微挑战"),
        en=CatalogText(name="Challenge", tip="A 5-minute daily micro challenge"),
    ),
    CatalogItem(
        mode_id="WORD_OF_THE_DAY",
        category="more",
        zh=CatalogText(name="每日一词", tip="每日精选一个英语单词，展示其拼写与释义"),
        en=CatalogText(name="Word of the Day", tip="One English word with a short explanation"),
    ),
    CatalogItem(
        mode_id="MY_QUOTE",
        category="more",
        zh=CatalogText(name="自定义语录", tip="可随机生成，或输入你自己的语录内容"),
        en=CatalogText(name="Custom Quote", tip="Supports custom input or random generation"),
    ),
    CatalogItem(
        mode_id="MY_ADAPTIVE",
        category="custom",
        zh=CatalogText(name="自适应照片", tip="上传本地照片，自适应 4.2\" 墨水屏显示"),
        en=CatalogText(name="Adaptive Photo", tip="Upload a local photo and auto-fit it to the 4.2\" e-ink screen"),
    ),
]


def builtin_catalog_map() -> dict[str, CatalogItem]:
    return {item.mode_id.upper(): item for item in BUILTIN_CATALOG}

