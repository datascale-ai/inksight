"""适配 core.context：取 date_ctx + weather。

单用户：城市取自 config（或经纬度），直接调 core 的缓存版本。
"""
from __future__ import annotations

from typing import Any

from core.context import get_date_context_cached, get_weather_cached


async def build_context(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """返回 (date_ctx, weather)。失败降级到空 dict / 默认天气。"""
    date_ctx = await get_date_context_cached()

    city = config.get("city") or ""
    lat = config.get("latitude")
    lon = config.get("longitude")
    weather: dict[str, Any]
    try:
        if lat is not None and lon is not None:
            from core.context import get_weather
            weather = await get_weather(lat=float(lat), lon=float(lon))
        else:
            weather = await get_weather_cached(city=city or None)
    except Exception:
        weather = {"temp": 0, "weather_code": -1, "weather_str": "--°C"}
    return date_ctx, weather