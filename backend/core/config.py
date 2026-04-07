"""
InkSight 配置文件
包含所有常量、映射表和配置项
"""

import logging

logger = logging.getLogger(__name__)

# ==================== 屏幕配置 ====================
SCREEN_WIDTH = 400   # Default; overridable per-request via w/h query params
SCREEN_HEIGHT = 300  # Default; overridable per-request via w/h query params

# 墨水屏颜色（1-bit 黑白）
EINK_BACKGROUND = 1  # 白色
EINK_FOREGROUND = 0  # 黑色

EINK_4COLOR_PALETTE = [
    0, 0, 0,        # 0: black
    255, 255, 255,   # 1: white
    232, 176, 0,     # 2: yellow (golden, closer to e-ink appearance)
    200, 0, 0,       # 3: red (deeper, closer to e-ink appearance)
]

EINK_COLOR_NAME_MAP = {
    "black": 0,
    "white": 1,
    "yellow": 2,
    "red": 3,
}

EINK_COLOR_AVAILABILITY = {
    2: frozenset(),
    3: frozenset({"red"}),
    4: frozenset({"red", "yellow"}),
}


# ==================== 天气配置 ====================
# WMO (世界气象组织) 天气代码 → 图标名称映射
# 参考: https://open-meteo.com/en/docs
WEATHER_ICON_MAP = {
    0: "sunny",
    1: "sunny",
    2: "partly_cloudy",
    3: "cloud",
    45: "foggy",
    48: "foggy",
    51: "rainy",
    53: "rainy",
    55: "rainy",
    56: "rainy",
    57: "rainy",
    61: "rainy",
    63: "rainy",
    65: "rainy",
    66: "rainy",
    67: "rainy",
    71: "snow",
    73: "snow",
    75: "snow",
    77: "snow",
    80: "rainy",
    81: "rainy",
    82: "rainy",
    85: "snow",
    86: "snow",
    95: "thunderstorm",
    96: "thunderstorm",
    99: "thunderstorm",
}


# ==================== 字体配置 ====================
FONTS = {
    # 中文字体
    "noto_serif_extralight": "NotoSerifSC-ExtraLight.ttf",
    "noto_serif_light": "NotoSerifSC-Light.ttf",
    "noto_serif_regular": "NotoSerifSC-Regular.ttf",
    "noto_serif_bold": "NotoSerifSC-Bold.ttf",
    "noto_serif_extrabold": "NotoSerifSC-ExtraBold.ttf",
    # 英文字体
    "lora_regular": "Lora-Regular.ttf",
    "lora_bold": "Lora-Bold.ttf",
    "inter_medium": "Inter_24pt-Medium.ttf",
}


# ==================== 日期时间配置 ====================
WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

MONTH_CN = [
    "一月",
    "二月",
    "三月",
    "四月",
    "五月",
    "六月",
    "七月",
    "八月",
    "九月",
    "十月",
    "十一月",
    "十二月",
]

# 公历节日（月, 日）
SOLAR_FESTIVALS = {
    (1, 1): "元旦",
    (2, 14): "情人节",
    (3, 8): "妇女节",
    (4, 1): "愚人节",
    (5, 1): "劳动节",
    (6, 1): "儿童节",
    (10, 1): "国庆节",
    (12, 25): "圣诞节",
}

# 农历节日（月, 日）
LUNAR_FESTIVALS = {
    (1, 1): "春节",
    (1, 15): "元宵节",
    (5, 5): "端午节",
    (7, 7): "七夕节",
    (8, 15): "中秋节",
    (9, 9): "重阳节",
    (12, 8): "腊八节",
}

# 二十四节气 (year, month, day) -> name
# Pre-computed for 2024-2030; solar terms drift by <=1 day across years.
SOLAR_TERMS: dict[tuple[int, int, int], str] = {}
_SOLAR_TERMS_RAW: dict[int, list[tuple[int, int, str]]] = {
    2024: [
        (1,6,"小寒"),(1,20,"大寒"),(2,4,"立春"),(2,19,"雨水"),
        (3,5,"惊蛰"),(3,20,"春分"),(4,4,"清明"),(4,19,"谷雨"),
        (5,5,"立夏"),(5,20,"小满"),(6,5,"芒种"),(6,21,"夏至"),
        (7,6,"小暑"),(7,22,"大暑"),(8,7,"立秋"),(8,22,"处暑"),
        (9,7,"白露"),(9,22,"秋分"),(10,8,"寒露"),(10,23,"霜降"),
        (11,7,"立冬"),(11,22,"小雪"),(12,6,"大雪"),(12,21,"冬至"),
    ],
    2025: [
        (1,5,"小寒"),(1,20,"大寒"),(2,3,"立春"),(2,18,"雨水"),
        (3,5,"惊蛰"),(3,20,"春分"),(4,4,"清明"),(4,20,"谷雨"),
        (5,5,"立夏"),(5,21,"小满"),(6,5,"芒种"),(6,21,"夏至"),
        (7,7,"小暑"),(7,22,"大暑"),(8,7,"立秋"),(8,23,"处暑"),
        (9,7,"白露"),(9,22,"秋分"),(10,8,"寒露"),(10,23,"霜降"),
        (11,7,"立冬"),(11,22,"小雪"),(12,7,"大雪"),(12,21,"冬至"),
    ],
    2026: [
        (1,5,"小寒"),(1,20,"大寒"),(2,4,"立春"),(2,18,"雨水"),
        (3,5,"惊蛰"),(3,20,"春分"),(4,5,"清明"),(4,20,"谷雨"),
        (5,5,"立夏"),(5,21,"小满"),(6,5,"芒种"),(6,21,"夏至"),
        (7,7,"小暑"),(7,23,"大暑"),(8,7,"立秋"),(8,23,"处暑"),
        (9,7,"白露"),(9,23,"秋分"),(10,8,"寒露"),(10,23,"霜降"),
        (11,7,"立冬"),(11,22,"小雪"),(12,7,"大雪"),(12,22,"冬至"),
    ],
    2027: [
        (1,5,"小寒"),(1,20,"大寒"),(2,4,"立春"),(2,19,"雨水"),
        (3,6,"惊蛰"),(3,21,"春分"),(4,5,"清明"),(4,20,"谷雨"),
        (5,6,"立夏"),(5,21,"小满"),(6,6,"芒种"),(6,21,"夏至"),
        (7,7,"小暑"),(7,23,"大暑"),(8,7,"立秋"),(8,23,"处暑"),
        (9,8,"白露"),(9,23,"秋分"),(10,8,"寒露"),(10,23,"霜降"),
        (11,7,"立冬"),(11,22,"小雪"),(12,7,"大雪"),(12,22,"冬至"),
    ],
    2028: [
        (1,6,"小寒"),(1,21,"大寒"),(2,4,"立春"),(2,19,"雨水"),
        (3,5,"惊蛰"),(3,20,"春分"),(4,4,"清明"),(4,19,"谷雨"),
        (5,5,"立夏"),(5,20,"小满"),(6,5,"芒种"),(6,21,"夏至"),
        (7,6,"小暑"),(7,22,"大暑"),(8,7,"立秋"),(8,22,"处暑"),
        (9,7,"白露"),(9,22,"秋分"),(10,8,"寒露"),(10,23,"霜降"),
        (11,7,"立冬"),(11,22,"小雪"),(12,6,"大雪"),(12,21,"冬至"),
    ],
    2029: [
        (1,5,"小寒"),(1,20,"大寒"),(2,3,"立春"),(2,18,"雨水"),
        (3,5,"惊蛰"),(3,20,"春分"),(4,4,"清明"),(4,20,"谷雨"),
        (5,5,"立夏"),(5,21,"小满"),(6,5,"芒种"),(6,21,"夏至"),
        (7,7,"小暑"),(7,22,"大暑"),(8,7,"立秋"),(8,23,"处暑"),
        (9,7,"白露"),(9,22,"秋分"),(10,8,"寒露"),(10,23,"霜降"),
        (11,7,"立冬"),(11,22,"小雪"),(12,7,"大雪"),(12,21,"冬至"),
    ],
    2030: [
        (1,5,"小寒"),(1,20,"大寒"),(2,4,"立春"),(2,18,"雨水"),
        (3,5,"惊蛰"),(3,20,"春分"),(4,5,"清明"),(4,20,"谷雨"),
        (5,5,"立夏"),(5,21,"小满"),(6,5,"芒种"),(6,21,"夏至"),
        (7,7,"小暑"),(7,22,"大暑"),(8,7,"立秋"),(8,23,"处暑"),
        (9,7,"白露"),(9,23,"秋分"),(10,8,"寒露"),(10,23,"霜降"),
        (11,7,"立冬"),(11,22,"小雪"),(12,7,"大雪"),(12,22,"冬至"),
    ],
}
for _yr, _terms in _SOLAR_TERMS_RAW.items():
    for _m, _d, _name in _terms:
        SOLAR_TERMS[(_yr, _m, _d)] = _name


# ==================== 文学素材 ====================
IDIOMS = [
    "一日三秋",
    "春风化雨",
    "秋高气爽",
    "冬日暖阳",
    "夏日炎炎",
    "朝花夕拾",
    "岁月如梭",
    "时光荏苒",
    "白驹过隙",
    "光阴似箭",
    "晨钟暮鼓",
    "日新月异",
    "星移斗转",
    "寒来暑往",
    "花开花落",
    "云卷云舒",
    "潮起潮落",
    "月圆月缺",
    "风起云涌",
    "雨过天晴",
]

POEMS = [
    "春眠不觉晓，处处闻啼鸟",
    "举头望明月，低头思故乡",
    "海上生明月，天涯共此时",
    "明月几时有，把酒问青天",
    "人生若只如初见，何事秋风悲画扇",
    "山重水复疑无路，柳暗花明又一村",
    "采菊东篱下，悠然见南山",
    "行到水穷处，坐看云起时",
    "落霞与孤鹜齐飞，秋水共长天一色",
    "大江东去，浪淘尽，千古风流人物",
]


# ==================== 地理位置配置 ====================
DEFAULT_LATITUDE = 31.23
DEFAULT_LONGITUDE = 121.47

CITY_COORDINATES = {
    "北京": (39.90, 116.40),
    "上海": (31.23, 121.47),
    "广州": (23.13, 113.26),
    "深圳": (22.54, 114.06),
    "杭州": (30.27, 120.15),
    "南京": (32.06, 118.80),
    "成都": (30.57, 104.07),
    "重庆": (29.56, 106.55),
    "武汉": (30.59, 114.31),
    "西安": (34.26, 108.94),
    "苏州": (31.30, 120.62),
    "天津": (39.13, 117.20),
    "长沙": (28.23, 112.94),
    "郑州": (34.75, 113.65),
    "青岛": (36.07, 120.38),
    "大连": (38.91, 121.60),
    "厦门": (24.48, 118.09),
    "昆明": (25.04, 102.68),
    "合肥": (31.82, 117.23),
    "福州": (26.07, 119.30),
    "哈尔滨": (45.75, 126.65),
    "沈阳": (41.80, 123.43),
    "济南": (36.65, 116.99),
    "石家庄": (38.04, 114.51),
    "长春": (43.88, 125.32),
    "南昌": (28.68, 115.86),
    "贵阳": (26.65, 106.63),
    "南宁": (22.82, 108.32),
    "太原": (37.87, 112.55),
    "兰州": (36.06, 103.83),
    "海口": (20.04, 110.35),
    "银川": (38.49, 106.23),
    "西宁": (36.62, 101.78),
    "呼和浩特": (40.84, 111.75),
    "乌鲁木齐": (43.83, 87.62),
    "拉萨": (29.65, 91.13),
    "香港": (22.32, 114.17),
    "澳门": (22.20, 113.55),
    "台北": (25.03, 121.57),
    "东京": (35.68, 139.69),
    "首尔": (37.57, 126.98),
    "新加坡": (1.35, 103.82),
    "纽约": (40.71, -74.01),
    "伦敦": (51.51, -0.13),
    "巴黎": (48.86, 2.35),
    "悉尼": (-33.87, 151.21),
    "温哥华": (49.28, -123.12),
    "旧金山": (37.77, -122.42),
}


# ==================== API 配置 ====================
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
HOLIDAY_WORK_API_URL = "https://date.appworlds.cn/work"
HOLIDAY_NEXT_API_URL = "https://date.appworlds.cn/next"

import os as _os
from pathlib import Path as _Path
from dotenv import load_dotenv as _load_dotenv
_load_dotenv(_Path(__file__).resolve().parent.parent / ".env")

QWEATHER_API_KEY = _os.getenv("QWEATHER_API_KEY", "")
QWEATHER_API_HOST = _os.getenv("QWEATHER_API_HOST", "devapi.qweather.com")
QWEATHER_PRIVATE_KEY = _os.getenv("QWEATHER_PRIVATE_KEY", "").replace("\\n", "\n")
QWEATHER_CREDENTIAL_ID = _os.getenv("QWEATHER_CREDENTIAL_ID", "")
QWEATHER_PROJECT_ID = _os.getenv("QWEATHER_PROJECT_ID", "")

_QWEATHER_ICON_TO_WMO: dict[int, int] = {
    100: 0, 150: 0,
    101: 1, 102: 2, 103: 3, 104: 3, 151: 1, 152: 2, 153: 3,
    300: 61, 301: 63, 302: 95, 303: 95, 304: 99, 305: 51, 306: 61, 307: 65, 308: 65, 309: 51, 310: 82, 311: 82, 312: 65, 313: 51, 314: 51, 315: 51, 316: 65, 317: 65, 318: 65, 350: 61, 351: 61, 399: 61,
    400: 71, 401: 73, 402: 75, 403: 75, 404: 71, 405: 73, 406: 75, 407: 77, 408: 71, 409: 73, 410: 75, 456: 71, 457: 73, 499: 71,
    500: 45, 501: 45, 502: 48, 503: 48, 504: 48, 507: 48, 508: 48, 509: 45, 510: 45, 511: 45, 512: 45, 513: 45, 514: 48, 515: 48,
    900: 0, 901: 0, 999: -1,
}


# ==================== 渲染配置 ====================
# DAILY 模式布局配置
DAILY_LAYOUT = {
    "left_column_width": 116,
    "gaps": {
        "year_to_day": 2,
        "day_to_month": 24,
        "month_to_weekday": 2,
        "weekday_to_progress": 10,
        "bar_to_text": 3,
    },
    "progress_bar_width": 80,
    "right_column_padding": 14,
}

# 字体大小配置 (共用组件 + 仍为 Python 模式的布局)
# STOIC/ROAST/ZEN/FITNESS/POETRY 已迁移到 JSON，字体配置在 modes/builtin/*.json 中
FONT_SIZES = {
    "status_bar": {"cn": 11, "en": 11},
    "footer": {"label": 10, "attribution": 12},
    "daily": {
        "year": 12,
        "day": 53,
        "month": 14,
        "weekday": 12,
        "progress": 10,
        "section_title": 11,
        "quote": 14,
        "author": 12,
        "book_title": 14,
        "book_info": 12,
        "tip": 12,
    },
}

# 图标大小配置
ICON_SIZES = {
    "weather": (16, 16),
    "mode": (12, 12),
}


# ==================== 业务默认值 ====================
DEFAULT_CITY = "杭州"
DEFAULT_LLM_PROVIDER = "aliyun"
DEFAULT_LLM_MODEL = "deepseek-v3.2"
DEFAULT_IMAGE_PROVIDER = "aliyun"
DEFAULT_IMAGE_MODEL = "qwen-image-max"
DEFAULT_LANGUAGE = "zh"
DEFAULT_MODE_LANGUAGE = ""  # empty = follow webapp language setting
DEFAULT_CONTENT_TONE = "neutral"
DEFAULT_MODES = ["STOIC"]
DEFAULT_REFRESH_STRATEGY = "random"
DEFAULT_REFRESH_INTERVAL = 60  # minutes

# 硬编码模式列表仅作为 fallback，运行时应通过 mode_registry 获取
_BUILTIN_MODE_IDS = {
    "STOIC", "ROAST", "ZEN", "DAILY",
    "BRIEFING", "ARTWALL", "RECIPE", "FITNESS",
    "POETRY", "COUNTDOWN",
    "ALMANAC", "LETTER", "THISDAY", "RIDDLE",
    "QUESTION", "BIAS", "STORY", "LIFEBAR", "CHALLENGE",
}


def get_supported_modes() -> set[str]:
    """Get all supported mode IDs from the registry (with fallback)."""
    try:
        from .mode_registry import get_registry
        return get_registry().get_supported_ids()
    except (ImportError, AttributeError, RuntimeError):
        logger.warning("[Config] Falling back to builtin supported modes", exc_info=True)
        return _BUILTIN_MODE_IDS


def get_cacheable_modes() -> set[str]:
    """Get cacheable mode IDs from the registry (with fallback)."""
    try:
        from .mode_registry import get_registry
        return get_registry().get_cacheable_ids()
    except (ImportError, AttributeError, RuntimeError):
        logger.warning("[Config] Falling back to builtin cacheable modes", exc_info=True)
        return {"STOIC", "ROAST", "ZEN", "DAILY"}


from typing import Optional


def get_default_llm_model_for_provider(provider: Optional[str]) -> str:
    """根据服务商返回默认模型名。

    - 百炼(aliyun)：默认 deepseek-v3.2（兼容模式）
    - DeepSeek：默认 deepseek-chat
    - Moonshot：默认 moonshot-v1-8k
    - 其他/未知：回退到 DEFAULT_LLM_MODEL
    """
    p = (provider or "").strip().lower() or DEFAULT_LLM_PROVIDER
    if p == "aliyun":
        return "deepseek-v3.2"
    if p == "deepseek":
        return "deepseek-chat"
    if p == "moonshot":
        return "moonshot-v1-8k"
    return DEFAULT_LLM_MODEL