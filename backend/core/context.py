from __future__ import annotations

import logging
import time
import httpx
import random
from datetime import datetime
from typing import Any

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
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
    DEFAULT_CITY,
)

_context_cache: dict[str, tuple[Any, float]] = {}

logger = logging.getLogger(__name__)

# Reusable retry decorator for external API calls
_api_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type((
        httpx.ConnectError,
        httpx.ReadTimeout,
        httpx.ConnectTimeout,
    )),
    reraise=True,
)


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


@_api_retry
async def _fetch_holiday_info(date_str: str) -> dict:
    """Fetch holiday info with retry."""
    async with httpx.AsyncClient(timeout=3.0) as client:
        resp = await client.get(HOLIDAY_WORK_API_URL, params={"date": date_str})
        resp.raise_for_status()
        return resp.json()


async def get_holiday_info(date: datetime) -> dict:
    date_str = date.strftime("%Y-%m-%d")
    try:
        result = await _fetch_holiday_info(date_str)
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


@_api_retry
async def _fetch_upcoming_holiday() -> dict:
    """Fetch upcoming holiday info with retry."""
    async with httpx.AsyncClient(timeout=3.0) as client:
        resp = await client.get(HOLIDAY_NEXT_API_URL)
        resp.raise_for_status()
        return resp.json()


async def get_upcoming_holiday(now: datetime) -> dict:
    try:
        result = await _fetch_upcoming_holiday()
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


@_api_retry
async def _fetch_weather_data(url: str, params: dict) -> dict:
    """Fetch weather data with retry."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


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
        data = await _fetch_weather_data(OPEN_METEO_URL, params)
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
    # city 为空时，既要使用默认经纬度，也要在返回数据里给出一个可展示的城市名
    display_city = city or DEFAULT_CITY
    lat, lon = _resolve_city(display_city)
    params = {
        "latitude": lat,
        "longitude": lon,
        # 预报字段：温度、天气代码、湿度、主导风向、风速、日出日落时间
        "daily": ",".join(
            [
                "temperature_2m_max",
                "temperature_2m_min",
                "weather_code",
                "relative_humidity_2m_mean",
                "winddirection_10m_dominant",
                "windspeed_10m_max",
                "sunrise",
                "sunset",
            ]
        ),
        "timezone": "auto",
        "forecast_days": days + 1,  # include today
    }
    try:
        forecast_url = (
            OPEN_METEO_URL.replace("/current", "/forecast")
            if "/current" in OPEN_METEO_URL
            else OPEN_METEO_URL
        )
        data = await _fetch_weather_data(forecast_url, params)
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        t_max = daily.get("temperature_2m_max", [])
        t_min = daily.get("temperature_2m_min", [])
        codes = daily.get("weather_code", [])
        humidities = daily.get("relative_humidity_2m_mean", [])
        wind_dirs = daily.get("winddirection_10m_dominant", [])
        wind_speeds = daily.get("windspeed_10m_max", [])
        sunrises = daily.get("sunrise", [])
        sunsets = daily.get("sunset", [])

        WEEKDAY_SHORT = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        now = datetime.now()
        today_date = now.date()
        
        # 构建完整的预报列表，包括昨天、今天、明天、后天等
        full_forecast = []
        for i in range(min(len(dates), days + 1)):
            d = datetime.strptime(dates[i], "%Y-%m-%d")
            date_obj = d.date()
            date_str = d.strftime("%m/%d")
            
            # 判断是昨天、今天、明天还是其他
            delta = (date_obj - today_date).days
            if delta == -1:
                day_label = "昨天"
            elif delta == 0:
                day_label = "今天"
            elif delta == 1:
                day_label = "明天"
            else:
                day_label = WEEKDAY_SHORT[d.weekday()]
            
            wcode = codes[i] if i < len(codes) else -1
            desc = _weather_code_to_desc(wcode)
            
            temp_min = round(t_min[i]) if i < len(t_min) else None
            temp_max = round(t_max[i]) if i < len(t_max) else None
            
            if temp_min is not None and temp_max is not None:
                temp_range = f"{temp_min}℃ / {temp_max}℃"
            else:
                temp_range = "--"
            
            full_forecast.append(
                {
                    "day": day_label,
                    "date": date_str,
                    "temp_range": temp_range,
                    "temp_min": str(temp_min) if temp_min is not None else "--",
                    "temp_max": str(temp_max) if temp_max is not None else "--",
                    "desc": desc,
                    "code": wcode,
                }
            )

        # 今天的天气信息
        today = full_forecast[0] if full_forecast else {}
        today_high = today.get("temp_max", "--")
        today_low = today.get("temp_min", "--")
        today_temp = today_high  # 大号数字使用最高温
        today_desc = today.get("desc", "")
        today_code = today.get("code", -1)

        if today_low != "--" and today_high != "--":
            today_range = f"{today_low}°C / {today_high}°C"
        else:
            today_range = "-- / --"

        # 今天的湿度
        today_humidity = "--"
        if humidities:
            try:
                today_humidity = str(int(round(humidities[0])))
            except (TypeError, ValueError):
                today_humidity = "--"

        # 今天的风向和风力（等级粗略按风速估计）
        def _deg_to_wind_dir(deg: float) -> str:
            dirs = ["北风", "东北风", "东风", "东南风", "南风", "西南风", "西风", "西北风"]
            try:
                idx = int((deg % 360) / 45 + 0.5) % 8
                return dirs[idx]
            except Exception:
                return ""

        today_wind_dir = ""
        if wind_dirs:
            try:
                today_wind_dir = _deg_to_wind_dir(float(wind_dirs[0]))
            except (TypeError, ValueError):
                today_wind_dir = ""

        today_wind_level = ""
        if wind_speeds:
            try:
                # 这里使用风速近似为等级（粗略）：m/s 四舍五入作为“几级”
                level = max(1, min(12, int(round(float(wind_speeds[0]) / 2))))  # 简单映射
                today_wind_level = f"{level}级"
            except (TypeError, ValueError):
                today_wind_level = ""

        # 日出日落时间（取今天）
        sunrise_str = ""
        sunset_str = ""
        if sunrises:
            try:
                sr = datetime.fromisoformat(sunrises[0])
                sunrise_str = sr.strftime("%H:%M")
            except Exception:
                sunrise_str = ""
        if sunsets:
            try:
                ss = datetime.fromisoformat(sunsets[0])
                sunset_str = ss.strftime("%H:%M")
            except Exception:
                sunset_str = ""

        return {
            "city": display_city,
            "today_temp": today_temp,
            "today_desc": today_desc,
            "today_code": today_code,
            "today_low": today_low,
            "today_high": today_high,
            "today_range": today_range,
            "today_humidity": today_humidity,
            "today_wind_dir": today_wind_dir,
            "today_wind_level": today_wind_level,
            "sunrise": sunrise_str,
            "sunset": sunset_str,
            # 返回完整预报列表（包括昨天、今天、明天等）
            "forecast": full_forecast,
        }
    except Exception as e:
        logger.warning(f"[WeatherForecast] Failed to get weather forecast: {e}")
        return {
            "city": city or DEFAULT_CITY,
            "today_temp": "--",
            "today_desc": "暂无数据",
            "today_code": -1,
            "today_low": "--",
            "today_high": "--",
            "today_range": "-- / --",
            "forecast": [],
        }


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
