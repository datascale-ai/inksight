"""
InkSight 配置文件
包含所有常量、映射表和配置项
"""

# ==================== 屏幕配置 ====================
SCREEN_WIDTH = 400   # Default; overridable per-request via w/h query params
SCREEN_HEIGHT = 300  # Default; overridable per-request via w/h query params

# 墨水屏颜色（1-bit 黑白）
EINK_BACKGROUND = 1  # 白色
EINK_FOREGROUND = 0  # 黑色


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


# ==================== 模式图标映射 ====================
MODE_ICON_MAP = {
    "STOIC": "book",
    "ROAST": "electric_bolt",
    "ZEN": "zen",
    "DAILY": "sunny",
    "BRIEFING": "global",
    "ARTWALL": "art",
    "RECIPE": "food",
    "FITNESS": "exercise",
    "POETRY": "star",
    "COUNTDOWN": "flag",
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
HOLIDAY_WORK_API_URL = "https://date.appworlds.cn/work"
HOLIDAY_NEXT_API_URL = "https://date.appworlds.cn/next"


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

# 字体大小配置
FONT_SIZES = {
    "status_bar": {"cn": 11, "en": 11},
    "footer": {"label": 10, "attribution": 12},
    "stoic": {"quote": 16},
    "roast": {"quote": 15},
    "zen": {"word": 48},
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
DEFAULT_LLM_PROVIDER = "deepseek"
DEFAULT_LLM_MODEL = "deepseek-chat"
DEFAULT_LANGUAGE = "zh"
DEFAULT_CONTENT_TONE = "neutral"
DEFAULT_MODES = ["STOIC"]
DEFAULT_REFRESH_STRATEGY = "random"
DEFAULT_REFRESH_INTERVAL = 60  # minutes

# 硬编码模式列表仅作为 fallback，运行时应通过 mode_registry 获取
_BUILTIN_MODE_IDS = {
    "STOIC", "ROAST", "ZEN", "DAILY",
    "BRIEFING", "ARTWALL", "RECIPE", "FITNESS",
    "POETRY", "COUNTDOWN",
}


def get_supported_modes() -> set[str]:
    """Get all supported mode IDs from the registry (with fallback)."""
    try:
        from .mode_registry import get_registry
        return get_registry().get_supported_ids()
    except Exception:
        return _BUILTIN_MODE_IDS


def get_cacheable_modes() -> set[str]:
    """Get cacheable mode IDs from the registry (with fallback)."""
    try:
        from .mode_registry import get_registry
        return get_registry().get_cacheable_ids()
    except Exception:
        return {"STOIC", "ROAST", "ZEN", "DAILY"}


# Keep legacy names for backward compat (lazy evaluation via property-like access is not
# possible at module level, so callers that import the set directly will get the fallback.
# Prefer calling get_supported_modes() / get_cacheable_modes() instead.)
SUPPORTED_MODES = _BUILTIN_MODE_IDS
CACHEABLE_MODES = {"STOIC", "ROAST", "ZEN", "DAILY"}
