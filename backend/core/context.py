from __future__ import annotations

import asyncio
import logging
import re
import time
import httpx
import random
from json import JSONDecodeError
from datetime import datetime
from typing import Any, Literal

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
    OPEN_METEO_GEOCODING_URL,
    HOLIDAY_WORK_API_URL,
    HOLIDAY_NEXT_API_URL,
    DEFAULT_CITY,
)

_context_cache: dict[str, tuple[Any, float]] = {}

logger = logging.getLogger(__name__)

_NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_USER_AGENT = "InkSight/1.0 (weather location search)"
_CN_TIMEZONE = "Asia/Shanghai"
_CN_SEARCH_COUNTRY_CODE = "cn"
_NOMINATIM_QUERY_SUFFIXES = ("市", "县", "区")
_NOMINATIM_ADMIN_TYPES = {
    "administrative",
    "city",
    "county",
    "district",
    "municipality",
    "province",
    "region",
    "state",
    "suburb",
    "town",
    "village",
}
_NOMINATIM_POI_CATEGORIES = {
    "aerialway",
    "aeroway",
    "amenity",
    "building",
    "highway",
    "historic",
    "landuse",
    "leisure",
    "man_made",
    "office",
    "railway",
    "shop",
    "tourism",
}
_NOMINATIM_POI_TYPES = {
    "bus_stop",
    "halt",
    "platform",
    "station",
    "tram_stop",
}
LocationSearchScope = Literal["auto", "cn", "global"]

_LOCATION_SUFFIXES = (
    "特别行政区",
    "自治区",
    "自治州",
    "自治县",
    "地区",
    "盟",
    "省",
    "市",
    "区",
    "县",
)

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


def _normalize_place_name(name: str | None) -> str:
    if not isinstance(name, str):
        return ""
    normalized = name.strip().replace(" ", "")
    for token in ("中国", "中华人民共和国"):
        if normalized.startswith(token):
            normalized = normalized[len(token):]
    normalized = normalized.strip("·,-_/，、 ")
    for suffix in _LOCATION_SUFFIXES:
        if normalized.endswith(suffix) and len(normalized) > len(suffix):
            normalized = normalized[: -len(suffix)]
            break
    return normalized


def _clean_location_text(value: Any, max_length: int = 64) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]


def _clean_float(value: Any) -> float | None:
    try:
        if value in ("", None):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_location_settings(config: dict | None, *, fallback_city: str | None = None) -> dict[str, Any]:
    if not isinstance(config, dict):
        return {"city": fallback_city} if fallback_city else {}

    city = _clean_location_text(config.get("city"), max_length=40)
    latitude = _clean_float(config.get("latitude"))
    longitude = _clean_float(config.get("longitude"))

    location: dict[str, Any] = {}
    if city:
        location["city"] = city
    elif fallback_city:
        location["city"] = fallback_city
    if latitude is not None and longitude is not None:
        location["lat"] = latitude
        location["lon"] = longitude
    return location


def _resolve_city(city: str | None) -> tuple[float, float]:
    if not city:
        return DEFAULT_LATITUDE, DEFAULT_LONGITUDE
    coords = CITY_COORDINATES.get(city)
    if coords:
        return coords
    normalized = _normalize_place_name(city)
    for name, c in CITY_COORDINATES.items():
        if _normalize_place_name(name) == normalized:
            return c
    return DEFAULT_LATITUDE, DEFAULT_LONGITUDE


@_api_retry
async def _fetch_geocoding(name: str, *, count: int = 1, country_code: str | None = None) -> dict:
    params = {
        "name": name,
        "count": count,
        "language": "zh",
        "format": "json",
    }
    if country_code:
        params["countryCode"] = country_code
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(
            OPEN_METEO_GEOCODING_URL,
            params=params,
        )
        resp.raise_for_status()
        return resp.json()


def _format_location_label(name: str, admin1: str = "", country: str = "") -> str:
    parts = [part for part in (name, admin1, country) if part]
    return " · ".join(parts)


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _contains_latin_letters(text: str) -> bool:
    return any(ch.isascii() and ch.isalpha() for ch in text)


def _looks_like_china_country(country: str) -> bool:
    normalized = _clean_location_text(country, max_length=80)
    return "中国" in normalized or "中國" in normalized or normalized.lower() in {"china", "cn"}


def _search_country_code_sequence(query: str, scope: LocationSearchScope) -> list[str | None]:
    if scope == "cn":
        return [_CN_SEARCH_COUNTRY_CODE]
    if scope == "global":
        return [None]
    if _contains_latin_letters(query):
        return [None, _CN_SEARCH_COUNTRY_CODE]
    return [_CN_SEARCH_COUNTRY_CODE, None]


def _build_location_queries(query: str) -> list[str]:
    query = _clean_location_text(query, max_length=60)
    normalized = _normalize_place_name(query)
    if not query:
        return []

    variants: list[str] = [query]
    if normalized and normalized != query:
        variants.append(normalized)

    if normalized and _contains_cjk(normalized):
        has_suffix = any(query.endswith(suffix) for suffix in _LOCATION_SUFFIXES)
        if not has_suffix:
            for suffix in _NOMINATIM_QUERY_SUFFIXES:
                variants.append(f"{normalized}{suffix}")

    deduped: list[str] = []
    seen: set[str] = set()
    for item in variants:
        cleaned = _clean_location_text(item, max_length=60)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            deduped.append(cleaned)
    return deduped[:4]


def _builtin_location_items(query: str, limit: int) -> list[dict]:
    normalized_query = _normalize_place_name(query)
    if not normalized_query:
        return []

    results: list[dict] = []
    for name, (lat, lon) in CITY_COORDINATES.items():
        normalized_name = _normalize_place_name(name)
        if normalized_query not in normalized_name:
            continue
        results.append(
            {
                "city": name,
                "display_name": name,
                "admin1": "",
                "country": "",
                "latitude": lat,
                "longitude": lon,
                "timezone": "Asia/Shanghai",
                "_score": 100 if normalized_name == normalized_query else 80,
            }
        )

    results.sort(key=lambda item: (-int(item.get("_score", 0)), item.get("city", "")))
    return results[:limit]


def _parse_geocoding_item(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    name = _clean_location_text(item.get("name"), max_length=40)
    if not name:
        return None

    latitude = _clean_float(item.get("latitude"))
    longitude = _clean_float(item.get("longitude"))
    if latitude is None or longitude is None:
        return None

    admin1 = _clean_location_text(item.get("admin1"))
    country = _clean_location_text(item.get("country"))
    timezone = _clean_location_text(item.get("timezone")) or "Asia/Shanghai"
    population = 0
    try:
        population = int(item.get("population") or 0)
    except (TypeError, ValueError):
        population = 0

    aliases: list[str] = []
    for value in (
        item.get("name"),
        item.get("admin2"),
        item.get("admin3"),
        item.get("admin4"),
    ):
        alias = _clean_location_text(value, max_length=80)
        if alias and alias not in aliases:
            aliases.append(alias)

    return {
        "city": name,
        "display_name": _format_location_label(name, admin1, country),
        "admin1": admin1,
        "country": country,
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone,
        "_score": population,
        "_aliases": aliases,
    }


@_api_retry
async def _fetch_nominatim(
    query: str,
    *,
    count: int = 8,
    country_codes: str | None = _CN_SEARCH_COUNTRY_CODE,
) -> list[dict]:
    params = {
        "q": query,
        "format": "jsonv2",
        "addressdetails": 1,
        "accept-language": "zh-CN",
        "limit": count,
    }
    if country_codes:
        params["countrycodes"] = country_codes

    async with httpx.AsyncClient(
        timeout=5.0,
        headers={"User-Agent": _NOMINATIM_USER_AGENT},
    ) as client:
        resp = await client.get(_NOMINATIM_SEARCH_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []


def _pick_first_text(values: list[Any], *, max_length: int = 40) -> str:
    for value in values:
        cleaned = _clean_location_text(value, max_length=max_length)
        if cleaned:
            return cleaned
    return ""


def _normalize_match_text(text: str) -> str:
    cleaned = _clean_location_text(text, max_length=160).lower()
    return re.sub(r"[\s·,.;:，。；：/()（）\-_]+", " ", cleaned).strip()


def _location_matches_query(item: dict, query: str) -> bool:
    normalized_query = _normalize_place_name(query)
    if not normalized_query:
        return True

    candidates = [
        _clean_location_text(str(item.get("city", "")), max_length=80),
        _clean_location_text(str(item.get("display_name", "")), max_length=160),
    ]
    aliases = item.get("_aliases")
    if isinstance(aliases, list):
        candidates.extend(
            _clean_location_text(str(alias), max_length=80)
            for alias in aliases
            if alias
        )

    if _contains_cjk(normalized_query):
        return any(
            normalized_query in _normalize_place_name(candidate)
            for candidate in candidates
            if candidate
        )

    normalized_candidates = [_normalize_match_text(candidate) for candidate in candidates if candidate]
    normalized_query_text = _normalize_match_text(query)
    if not normalized_query_text:
        return True

    query_tokens = [token for token in normalized_query_text.split(" ") if token]
    if not query_tokens:
        return any(normalized_query_text in candidate for candidate in normalized_candidates)

    for candidate in normalized_candidates:
        candidate_tokens = [token for token in candidate.split(" ") if token]
        if not candidate_tokens:
            continue
        if all(any(token == candidate_token or candidate_token.startswith(token) for candidate_token in candidate_tokens) for token in query_tokens):
            return True
    return False


def _is_poi_like(item: dict) -> bool:
    category = _clean_location_text(str(item.get("_category", "")), max_length=32).lower()
    addresstype = _clean_location_text(str(item.get("_addresstype", "")), max_length=32).lower()
    item_type = _clean_location_text(str(item.get("_item_type", "")), max_length=32).lower()
    city = _clean_location_text(str(item.get("city", "")), max_length=80)

    if category in _NOMINATIM_POI_CATEGORIES:
        return True
    if addresstype in _NOMINATIM_POI_TYPES or item_type in _NOMINATIM_POI_TYPES:
        return True
    return any(token in city for token in ("机场", "大桥", "公司", "配餐部", "食品有限公司"))


def _is_admin_like(item: dict) -> bool:
    category = _clean_location_text(str(item.get("_category", "")), max_length=32).lower()
    addresstype = _clean_location_text(str(item.get("_addresstype", "")), max_length=32).lower()
    item_type = _clean_location_text(str(item.get("_item_type", "")), max_length=32).lower()
    city = _clean_location_text(str(item.get("city", "")), max_length=80)

    if category == "boundary" and item_type == "administrative":
        return True
    if addresstype in _NOMINATIM_ADMIN_TYPES or item_type in _NOMINATIM_ADMIN_TYPES:
        return True
    return city.endswith(("市", "区", "县", "镇", "州", "省"))


def _location_starts_with_query(item: dict, query: str) -> bool:
    normalized_query = _normalize_place_name(query)
    city = _normalize_place_name(str(item.get("city", "")))
    return bool(normalized_query and city.startswith(normalized_query))


def _refine_location_items(items: list[dict], query: str) -> list[dict]:
    matched = [item for item in items if _location_matches_query(item, query)]
    normalized_query = _normalize_place_name(query)
    if not normalized_query or not _contains_cjk(normalized_query):
        return matched

    has_admin_anchor = any(
        _is_admin_like(item) and _location_starts_with_query(item, query)
        for item in matched
    )
    if not has_admin_anchor:
        return matched

    refined = [item for item in matched if not _is_poi_like(item)]
    return refined or matched


def _extract_nominatim_name(item: dict) -> str:
    address = item.get("address") if isinstance(item.get("address"), dict) else {}
    return _pick_first_text(
        [
            item.get("name"),
            address.get("city"),
            address.get("county"),
            address.get("district"),
            address.get("town"),
            address.get("municipality"),
            address.get("state_district"),
            address.get("province"),
            address.get("state"),
            address.get("village"),
            address.get("hamlet"),
        ]
    )


def _nominatim_timezone(item: dict) -> str:
    address = item.get("address") if isinstance(item.get("address"), dict) else {}
    country_code = _clean_location_text(address.get("country_code"), max_length=8).lower()
    if country_code == "cn":
        return _CN_TIMEZONE
    return _clean_location_text(item.get("timezone"), max_length=64)


def _score_nominatim_item(item: dict, query: str) -> int:
    normalized_query = _normalize_place_name(query)
    best_name = _extract_nominatim_name(item)
    normalized_name = _normalize_place_name(best_name)
    display_name = _normalize_place_name(_clean_location_text(item.get("display_name"), max_length=160))
    addresstype = _clean_location_text(item.get("addresstype"), max_length=32).lower()
    category = _clean_location_text(item.get("category"), max_length=32).lower()
    item_type = _clean_location_text(item.get("type"), max_length=32).lower()

    score = 0

    try:
        score += int(float(item.get("importance") or 0) * 1000)
    except (TypeError, ValueError):
        pass

    try:
        score += int(item.get("place_rank") or 0)
    except (TypeError, ValueError):
        pass

    if normalized_query and normalized_name == normalized_query:
        score += 1200
    elif normalized_query and normalized_query in normalized_name:
        score += 800
    elif normalized_query and normalized_query in display_name:
        score += 500

    if category == "boundary" and item_type == "administrative":
        score += 900
    if category == "place":
        score += 550
    if addresstype in _NOMINATIM_ADMIN_TYPES:
        score += 450
    if item_type in _NOMINATIM_ADMIN_TYPES:
        score += 220

    if category in _NOMINATIM_POI_CATEGORIES:
        score -= 800
    if addresstype in _NOMINATIM_POI_TYPES:
        score -= 800
    if item_type in _NOMINATIM_POI_TYPES:
        score -= 900

    return score


def _parse_nominatim_item(item: dict, query: str) -> dict | None:
    if not isinstance(item, dict):
        return None

    latitude = _clean_float(item.get("lat"))
    longitude = _clean_float(item.get("lon"))
    if latitude is None or longitude is None:
        return None

    address = item.get("address") if isinstance(item.get("address"), dict) else {}
    city = _extract_nominatim_name(item)
    if not city:
        return None

    admin2 = _pick_first_text(
        [
            address.get("city"),
            address.get("municipality"),
            address.get("state_district"),
            address.get("county"),
            address.get("district"),
        ]
    )
    admin1 = _pick_first_text([address.get("state"), address.get("province")])
    country = _pick_first_text([address.get("country")])

    display_parts: list[str] = [city]
    if admin2 and admin2 != city:
        display_parts.append(admin2)
    if admin1 and admin1 not in display_parts:
        display_parts.append(admin1)
    if country and country not in display_parts:
        display_parts.append(country)

    return {
        "city": city,
        "display_name": " · ".join(display_parts),
        "admin1": admin1,
        "country": country,
        "latitude": latitude,
        "longitude": longitude,
        "timezone": _nominatim_timezone(item),
        "_score": _score_nominatim_item(item, query),
        "_category": _clean_location_text(item.get("category"), max_length=32).lower(),
        "_addresstype": _clean_location_text(item.get("addresstype"), max_length=32).lower(),
        "_item_type": _clean_location_text(item.get("type"), max_length=32).lower(),
    }


async def _search_nominatim_locations(
    query: str,
    limit: int,
    *,
    scope: LocationSearchScope = "auto",
) -> list[dict]:
    variants = _build_location_queries(query)
    if not variants:
        return []

    count = max(limit * 2, 6)
    results: list[dict] = []
    country_sequences = _search_country_code_sequence(query, scope)

    async def _fetch_variant(variant: str, country_codes: str | None) -> list[dict]:
        try:
            return await _fetch_nominatim(variant, count=count, country_codes=country_codes)
        except (httpx.HTTPError, TypeError, ValueError, JSONDecodeError):
            logger.warning(
                "[Context] Failed to search Nominatim for query=%s variant=%s",
                query,
                variant,
                exc_info=True,
            )
            return []

    for country_codes in country_sequences:
        batches = await asyncio.gather(
            *[_fetch_variant(variant, country_codes) for variant in variants]
        )
        for variant, batch in zip(variants, batches):
            for item in batch:
                parsed = _parse_nominatim_item(item, variant)
                if not parsed:
                    continue
                if country_codes == _CN_SEARCH_COUNTRY_CODE and scope != "global":
                    parsed["_score"] = int(parsed.get("_score", 0)) + 150
                results.append(parsed)
    return results


def _dedupe_location_items(items: list[dict], limit: int) -> list[dict]:
    deduped: list[dict] = []
    seen: set[tuple[Any, ...]] = set()
    seen_labels: set[str] = set()
    sorted_items = sorted(
        items,
        key=lambda item: (
            -int(item.get("_score", 0)),
            item.get("country", ""),
            item.get("admin1", ""),
            item.get("city", ""),
        ),
    )
    for item in sorted_items:
        display_name = _clean_location_text(item.get("display_name"), max_length=160)
        label_key = _normalize_place_name(display_name or item.get("city", ""))
        if label_key and label_key in seen_labels:
            continue
        key = (
            item.get("city", ""),
            item.get("admin1", ""),
            item.get("country", ""),
            round(float(item.get("latitude", 0.0)), 4),
            round(float(item.get("longitude", 0.0)), 4),
        )
        if key in seen:
            continue
        if label_key:
            seen_labels.add(label_key)
        seen.add(key)
        cleaned = {k: v for k, v in item.items() if not k.startswith("_")}
        deduped.append(cleaned)
        if len(deduped) >= limit:
            break
    return deduped


async def search_locations(
    query: str,
    limit: int = 8,
    scope: LocationSearchScope = "auto",
) -> list[dict]:
    query = _clean_location_text(query, max_length=60)
    if not query:
        return []

    if scope not in {"auto", "cn", "global"}:
        scope = "auto"

    cache_key = f"location-search:{query}:{limit}:{scope}"
    cached = _cache_get(cache_key, ttl=3600)
    if isinstance(cached, list):
        return cached

    items = _builtin_location_items(query, limit)

    items.extend(await _search_nominatim_locations(query, limit, scope=scope))

    geocode_results: list[dict] = []
    should_merge_geocoding = (
        (not items)
        or scope == "global"
        or _contains_latin_letters(query)
        or any(
            not _looks_like_china_country(str(item.get("country", ""))) and not item.get("timezone")
            for item in items[:3]
        )
    )
    if should_merge_geocoding:
        geocode_count = max(limit * 2, 8)
        if scope in {"auto", "cn"}:
            try:
                data = await _fetch_geocoding(query, count=geocode_count, country_code="CN")
                results = data.get("results") if isinstance(data, dict) else None
                if isinstance(results, list):
                    geocode_results.extend(results)
            except (httpx.HTTPError, TypeError, ValueError, JSONDecodeError):
                logger.warning("[Context] Failed to search CN locations for query=%s", query, exc_info=True)

        if not geocode_results and scope in {"auto", "global"}:
            try:
                data = await _fetch_geocoding(query, count=geocode_count)
                results = data.get("results") if isinstance(data, dict) else None
                if isinstance(results, list):
                    geocode_results.extend(results)
            except (httpx.HTTPError, TypeError, ValueError, JSONDecodeError):
                logger.warning("[Context] Failed to search global locations for query=%s", query, exc_info=True)

        for raw in geocode_results:
            parsed = _parse_geocoding_item(raw)
            if parsed and _location_matches_query(parsed, query):
                items.append(parsed)

    filtered_items = _refine_location_items(items, query)
    deduped = _dedupe_location_items(filtered_items, limit)
    _cache_set(cache_key, deduped)
    return deduped


async def _resolve_city_coords(city: str | None) -> tuple[float, float]:
    """Resolve city name to (lat, lon).

    Priority:
    1) CITY_COORDINATES exact match / fuzzy contains match
    2) Open-Meteo Geocoding API (cached)
    3) DEFAULT_LATITUDE/DEFAULT_LONGITUDE fallback
    """
    if not city:
        return DEFAULT_LATITUDE, DEFAULT_LONGITUDE

    coords = CITY_COORDINATES.get(city)
    if coords:
        return coords

    normalized = _normalize_place_name(city)
    for name, c in CITY_COORDINATES.items():
        if _normalize_place_name(name) == normalized:
            return c

    cache_key = f"geocode:{city}"
    cached = _cache_get(cache_key, ttl=86400)
    if cached is not None and isinstance(cached, (tuple, list)) and len(cached) == 2:
        try:
            return float(cached[0]), float(cached[1])
        except (TypeError, ValueError):
            pass

    try:
        results = await search_locations(city, limit=1)
        if results:
            lat_f = float(results[0]["latitude"])
            lon_f = float(results[0]["longitude"])
            _cache_set(cache_key, (lat_f, lon_f))
            return lat_f, lon_f
    except (httpx.HTTPError, TypeError, ValueError, JSONDecodeError, Exception):
        logger.warning("[Context] Failed to geocode city=%s, fallback to default", city, exc_info=True)

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
    except (httpx.HTTPError, JSONDecodeError, TypeError, ValueError):
        logger.warning("[Context] Failed to fetch holiday info for %s", date_str, exc_info=True)
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
    except (httpx.HTTPError, JSONDecodeError, TypeError, ValueError):
        logger.warning("[Context] Failed to fetch upcoming holiday", exc_info=True)

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
    except ValueError:
        logger.warning("[Context] Failed to resolve lunar date for %s", now.isoformat(), exc_info=True)
    
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
        lat, lon = await _resolve_city_coords(city)

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
    except (httpx.HTTPError, KeyError, TypeError, ValueError, Exception):
        logger.warning("[Context] Failed to fetch weather for city=%s lat=%s lon=%s", city, lat, lon, exc_info=True)
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


def _safe_int(value: Any) -> int | None:
    try:
        if value in ("", None):
            return None
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _wind_level_number(wind_level: str) -> int | None:
    match = re.search(r"(\d+)", wind_level or "")
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _generate_weather_advice(
    *,
    today_desc: str,
    today_low: str | int | None,
    today_high: str | int | None,
    today_humidity: str | int | None,
    today_wind_level: str,
) -> str:
    desc = _clean_location_text(today_desc, max_length=32)
    low = _safe_int(today_low)
    high = _safe_int(today_high)
    humidity = _safe_int(today_humidity)
    wind_level_num = _wind_level_number(today_wind_level)

    if "雷" in desc:
        return "有雷雨，尽量减少外出"
    if "雪" in desc:
        return "有雪天冷，注意保暖防滑"
    if "雨" in desc:
        return "有雨记得带伞，注意路滑"
    if "雾" in desc:
        return "有雾能见度低，出行留意"
    if high is not None and high >= 32:
        return "天气炎热，注意防晒补水"
    if low is not None and low <= 5:
        return "气温较低，外出注意保暖"
    if low is not None and high is not None and high - low >= 8:
        return "早晚温差大，记得带外套"
    if wind_level_num is not None and wind_level_num >= 5:
        return "风力较大，出门注意防风"
    if humidity is not None and humidity >= 85:
        return "空气潮湿，注意防潮添衣"
    if high is not None and high >= 26:
        return "气温偏高，穿着轻薄透气"
    return "气温适宜，轻装出行"


async def get_weather_forecast(
    city: str | None = None, days: int = 3, lat: float | None = None, lon: float | None = None
) -> dict:
    """Get multi-day weather forecast from Open-Meteo."""
    # city 为空时，既要使用默认经纬度，也要在返回数据里给出一个可展示的城市名
    display_city = city or DEFAULT_CITY
    if lat is None or lon is None:
        lat, lon = await _resolve_city_coords(display_city)
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
            except (TypeError, ValueError):
                logger.warning("[Context] Invalid wind direction value: %s", deg, exc_info=True)
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

        advice = _generate_weather_advice(
            today_desc=today_desc,
            today_low=today_low,
            today_high=today_high,
            today_humidity=today_humidity,
            today_wind_level=today_wind_level,
        )

        # 日出日落时间（取今天）
        sunrise_str = ""
        sunset_str = ""
        if sunrises:
            try:
                sr = datetime.fromisoformat(sunrises[0])
                sunrise_str = sr.strftime("%H:%M")
            except (TypeError, ValueError):
                logger.warning("[Context] Failed to parse sunrise value: %s", sunrises[0], exc_info=True)
                sunrise_str = ""
        if sunsets:
            try:
                ss = datetime.fromisoformat(sunsets[0])
                sunset_str = ss.strftime("%H:%M")
            except (TypeError, ValueError):
                logger.warning("[Context] Failed to parse sunset value: %s", sunsets[0], exc_info=True)
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
            "advice": advice,
            # 仅返回“未来 4 天”的预报（不含今天）
            "forecast": full_forecast[1:5] if len(full_forecast) > 1 else [],
        }
    except (httpx.HTTPError, KeyError, TypeError, ValueError, JSONDecodeError) as e:
        logger.warning(f"[WeatherForecast] Failed to get weather forecast: {e}", exc_info=True)
        return {
            "city": city or DEFAULT_CITY,
            "today_temp": "--",
            "today_desc": "暂无数据",
            "today_code": -1,
            "today_low": "--",
            "today_high": "--",
            "today_range": "-- / --",
            "advice": "注意根据天气添减衣物",
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
