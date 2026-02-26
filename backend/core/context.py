from __future__ import annotations

import time
import httpx
import random
from datetime import datetime
from typing import Any

from zhdate import ZhDate

from .config import (
    WEEKDAY_CN,
    MONTH_CN,
    SOLAR_FESTIVALS,
    LUNAR_FESTIVALS,
    IDIOMS,
    POEMS,
    CITY_COORDINATES,
    DEFAULT_LATITUDE,
    DEFAULT_LONGITUDE,
    OPEN_METEO_URL,
    HOLIDAY_WORK_API_URL,
    HOLIDAY_NEXT_API_URL,
)

_context_cache: dict[str, tuple[Any, float]] = {}


def _cache_get(key: str, ttl: float) -> Any | None:
    if key in _context_cache:
        val, ts = _context_cache[key]
        if time.time() - ts < ttl:
            return val
        del _context_cache[key]
    return None


def _cache_set(key: str, val: Any):
    _context_cache[key] = (val, time.time())


def _resolve_city(city: str | None) -> tuple[float, float]:
    if not city:
        return DEFAULT_LATITUDE, DEFAULT_LONGITUDE
    coords = CITY_COORDINATES.get(city)
    if coords:
        return coords
    for name, c in CITY_COORDINATES.items():
        if name in city or city in name:
            return c
    return DEFAULT_LATITUDE, DEFAULT_LONGITUDE


async def get_holiday_info(date: datetime) -> dict:
    date_str = date.strftime("%Y-%m-%d")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(HOLIDAY_WORK_API_URL, params={"date": date_str})
            resp.raise_for_status()
            result = resp.json()

            if result.get("code") == 200 and result.get("data"):
                data = result["data"]
                is_work = data.get("work", True)
                return {
                        "is_holiday": not is_work,
                        "holiday_name": "",
                        "is_workday": is_work,
                    }
            else:
                return {"is_holiday": False, "holiday_name": "", "is_workday": False}
    except Exception:
        return {"is_holiday": False, "holiday_name": "", "is_workday": False}


async def get_upcoming_holiday(now: datetime) -> dict:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(HOLIDAY_NEXT_API_URL)
            resp.raise_for_status()
            result = resp.json()

            if result.get("code") == 200 and result.get("data"):
                data = result["data"]
                holiday_date_str = data.get("date", "")

                if holiday_date_str:
                    from datetime import datetime as dt

                    holiday_date = dt.strptime(holiday_date_str, "%Y-%m-%d")
                    days_until = (holiday_date.date() - now.date()).days

                    return {
                        "days_until": days_until if days_until > 0 else 0,
                        "holiday_name": data.get("name", ""),
                        "date": holiday_date.strftime("%m月%d日"),
                        "holiday_duration": data.get("days", 0),
                    }
    except Exception:
        pass
    
    return {"days_until": 0, "holiday_name": "", "date": "", "holiday_duration": 0}


async def get_date_context() -> dict:
    now = datetime.now()
    day_of_year = now.timetuple().tm_yday
    days_in_year = (
        366
        if (now.year % 4 == 0 and (now.year % 100 != 0 or now.year % 400 == 0))
        else 365
    )
    
    festival = SOLAR_FESTIVALS.get((now.month, now.day), "")
    
    try:
        lunar = ZhDate.from_datetime(now)
        lunar_festival = LUNAR_FESTIVALS.get((lunar.lunar_month, lunar.lunar_day), "")
        if lunar_festival and not festival:
            festival = lunar_festival
    except Exception:
        pass
    
    holiday_info = await get_holiday_info(now)
    if holiday_info["holiday_name"] and not festival:
        festival = holiday_info["holiday_name"]
    
    upcoming = await get_upcoming_holiday(now)
    
    daily_word = random.choice(IDIOMS + POEMS)
    
    return {
        "date_str": f"{now.month}月{now.day}日 {WEEKDAY_CN[now.weekday()]}",
        "time_str": f"{now.hour:02d}:{now.minute:02d}:{now.second:02d}",
        "weekday": now.weekday(),
        "hour": now.hour,
        "is_weekend": now.weekday() >= 5,
        "year": now.year,
        "day": now.day,
        "month_cn": MONTH_CN[now.month - 1],
        "weekday_cn": WEEKDAY_CN[now.weekday()],
        "day_of_year": day_of_year,
        "days_in_year": days_in_year,
        "festival": festival,
        "is_holiday": holiday_info["is_holiday"],
        "is_workday": holiday_info["is_workday"],
        "upcoming_holiday": upcoming["holiday_name"],
        "days_until_holiday": upcoming["days_until"],
        "holiday_date": upcoming["date"],
        "daily_word": daily_word,
    }


async def get_date_context_cached(ttl: float = 900) -> dict:
    """Cached version of get_date_context (15min default TTL)."""
    cached = _cache_get("date_context", ttl)
    if cached is not None:
        return cached
    result = await get_date_context()
    _cache_set("date_context", result)
    return result


async def get_weather(
    lat: float | None = None, lon: float | None = None, city: str | None = None
) -> dict:
    if lat is None or lon is None:
        lat, lon = _resolve_city(city)

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,weather_code",
        "timezone": "auto",
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(OPEN_METEO_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            current = data["current"]
            return {
                "temp": round(current["temperature_2m"]),
                "weather_code": current["weather_code"],
                "weather_str": f"{round(current['temperature_2m'])}°C",
            }
    except Exception:
        return {"temp": 0, "weather_code": -1, "weather_str": "--°C"}


async def get_weather_cached(city: str | None = None, ttl: float = 1800) -> dict:
    """Cached version of get_weather (30min default TTL)."""
    cache_key = f"weather:{city or 'default'}"
    cached = _cache_get(cache_key, ttl)
    if cached is not None:
        return cached
    result = await get_weather(city=city)
    _cache_set(cache_key, result)
    return result


def _weather_code_to_desc(code: int) -> str:
    """Convert WMO weather code to Chinese description."""
    mapping = {
        0: "晴", 1: "多云", 2: "多云", 3: "阴",
        45: "雾", 48: "雾凇",
        51: "小雨", 53: "中雨", 55: "大雨",
        61: "小雨", 63: "中雨", 65: "大雨",
        71: "小雪", 73: "中雪", 75: "大雪",
        80: "阵雨", 81: "阵雨", 82: "暴雨",
        95: "雷阵雨", 96: "冰雹", 99: "冰雹",
    }
    return mapping.get(code, "未知")


async def get_weather_forecast(
    city: str | None = None, days: int = 3
) -> dict:
    """Get multi-day weather forecast from Open-Meteo."""
    lat, lon = _resolve_city(city)
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,weather_code",
        "timezone": "auto",
        "forecast_days": days + 1,  # include today
    }
    try:
        forecast_url = (
            OPEN_METEO_URL.replace("/current", "/forecast")
            if "/current" in OPEN_METEO_URL
            else OPEN_METEO_URL
        )
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(forecast_url, params=params)
            resp.raise_for_status()
            data = resp.json()
            daily = data.get("daily", {})
            dates = daily.get("time", [])
            t_max = daily.get("temperature_2m_max", [])
            t_min = daily.get("temperature_2m_min", [])
            codes = daily.get("weather_code", [])

            WEEKDAY_SHORT = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            forecast = []
            for i in range(min(len(dates), days + 1)):
                d = datetime.strptime(dates[i], "%Y-%m-%d")
                day_label = "今天" if i == 0 else ("明天" if i == 1 else WEEKDAY_SHORT[d.weekday()])
                wcode = codes[i] if i < len(codes) else -1
                desc = _weather_code_to_desc(wcode)
                forecast.append({
                    "day": day_label,
                    "temp_range": f"{round(t_min[i])}~{round(t_max[i])}°C"
                    if i < len(t_min) and i < len(t_max)
                    else "--",
                    "desc": desc,
                    "code": wcode,
                })

            today = forecast[0] if forecast else {}
            return {
                "today_temp": str(round(t_max[0])) if t_max else "--",
                "today_desc": today.get("desc", ""),
                "forecast": forecast[1:] if len(forecast) > 1 else [],
            }
    except Exception:
        return {"today_temp": "--", "today_desc": "暂无数据", "forecast": []}


def calc_battery_pct(voltage: float) -> int:
    pct = int(voltage / 3.30 * 100)
    if pct < 0:
        return 0
    if pct > 100:
        return 100
    return pct


def choose_persona(weekday: int, hour: int) -> str:
    import random

    return random.choice(["STOIC", "ROAST", "ZEN", "DAILY"])
