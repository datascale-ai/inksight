from __future__ import annotations

import asyncio
import copy
import io
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import aiosqlite
from PIL import Image

logger = logging.getLogger(__name__)

from .db import get_cache_db

_CACHE_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "cache.db")


async def init_cache_db():
    """Initialize the cache database."""
    async with aiosqlite.connect(_CACHE_DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS image_cache (
                cache_key TEXT PRIMARY KEY,
                image_data BLOB NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()

from .config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    DEFAULT_CITY,
    DEFAULT_MODES,
    get_cacheable_modes,
)
from .context import get_date_context, get_weather, calc_battery_pct
from .pipeline import generate_and_render


class ContentCache:
    def __init__(self):
        self._cache: dict[str, tuple[Image.Image, datetime]] = {}
        self._lock = asyncio.Lock()
        self._regenerating: set[str] = set()

    def _get_cache_key(
        self, mac: str, persona: str,
        screen_w: int = SCREEN_WIDTH, screen_h: int = SCREEN_HEIGHT,
    ) -> str:
        persona = (persona or "").upper()
        if screen_w == SCREEN_WIDTH and screen_h == SCREEN_HEIGHT:
            return f"{mac}:{persona}"
        return f"{mac}:{persona}:{screen_w}x{screen_h}"

    def _get_ttl_minutes(self, config: dict) -> int:
        """Calculate cache TTL based on refresh interval and number of modes"""
        refresh_interval = config.get("refresh_interval", 60)
        modes = config.get("modes", DEFAULT_MODES)
        cacheable = get_cacheable_modes()
        mode_count = len([m for m in modes if m in cacheable])

        ttl_minutes = int(refresh_interval * mode_count * 1.1)
        return ttl_minutes

    async def get(
        self, mac: str, persona: str, config: dict,
        ttl_minutes: int | None = None,
        screen_w: int = SCREEN_WIDTH, screen_h: int = SCREEN_HEIGHT,
    ) -> Optional[Image.Image]:
        """Get cached image if available and not expired"""
        async with self._lock:
            key = self._get_cache_key(mac, persona, screen_w, screen_h)
            if key in self._cache:
                img, timestamp = self._cache[key]
                if ttl_minutes is None:
                    ttl_minutes = self._get_ttl_minutes(config)
                if datetime.now() - timestamp < timedelta(minutes=ttl_minutes):
                    return img.copy()
                else:
                    logger.debug(f"[CACHE] {key} expired (TTL={ttl_minutes}min)")
                    del self._cache[key]
            # Try SQLite persistent cache
            try:
                img = await self._get_from_db(key, ttl_minutes=ttl_minutes)
                if img:
                    self._cache[key] = (img, datetime.now())
                    return img.copy()
            except Exception:
                pass
            return None

    async def set(
        self, mac: str, persona: str, img: Image.Image,
        screen_w: int = SCREEN_WIDTH, screen_h: int = SCREEN_HEIGHT,
    ):
        """Store image in cache"""
        async with self._lock:
            key = self._get_cache_key(mac, persona, screen_w, screen_h)
            img_copy = img.copy()
            self._cache[key] = (img_copy, datetime.now())
            try:
                await self._save_to_db(key, img_copy)
            except Exception:
                pass

    async def check_and_regenerate_all(
        self, mac: str, config: dict, v: float = 3.3,
        screen_w: int = SCREEN_WIDTH, screen_h: int = SCREEN_HEIGHT,
    ) -> bool:
        """Check if all modes are cached, if not, regenerate all modes"""
        cacheable = get_cacheable_modes()
        modes = [m.upper() for m in config.get("modes", DEFAULT_MODES) if m.upper() in cacheable]

        if not modes:
            return False

        ttl_minutes = self._get_ttl_minutes(config)
        refresh_interval = config.get("refresh_interval", 60)
        mode_count = len(modes)
        logger.debug(
            f"[CACHE] TTL: {refresh_interval}min × {mode_count} modes × 1.1 = {ttl_minutes}min"
        )

        needs_regeneration = False
        for persona in modes:
            cached = await self.get(mac, persona, config, ttl_minutes, screen_w, screen_h)
            if not cached:
                needs_regeneration = True
                logger.debug(f"[CACHE] {mac}:{persona} missing or expired")
                break

        if not needs_regeneration:
            logger.debug(f"[CACHE] All {len(modes)} modes cached for {mac}")
            return True

        if mac not in self._regenerating:
            self._regenerating.add(mac)
            logger.info(f"[CACHE] Spawning background regeneration of all {len(modes)} modes for {mac}...")
            asyncio.create_task(
                self._regenerate_background(mac, config, modes, v, screen_w, screen_h)
            )
        else:
            logger.debug(f"[CACHE] Background regeneration already in progress for {mac}")

        return False

    async def _regenerate_background(
        self, mac: str, config: dict, modes: list[str], v: float,
        screen_w: int = SCREEN_WIDTH, screen_h: int = SCREEN_HEIGHT,
    ):
        """Background task that wraps _generate_all_modes with cleanup of _regenerating."""
        try:
            await self._generate_all_modes(mac, config, modes, v, screen_w, screen_h)
        except Exception as e:
            logger.error(f"[CACHE] Background regeneration failed for {mac}: {e}")
        finally:
            self._regenerating.discard(mac)

    async def _generate_all_modes(
        self, mac: str, config: dict, modes: list[str], v: float,
        screen_w: int = SCREEN_WIDTH, screen_h: int = SCREEN_HEIGHT,
    ):
        """Generate and cache all modes"""
        battery_pct = calc_battery_pct(v)
        city = config.get("city", DEFAULT_CITY)

        date_ctx, weather = await asyncio.gather(
            get_date_context(),
            get_weather(city=city),
        )

        tasks = [
            self._generate_single_mode(
                mac, persona, battery_pct, copy.deepcopy(config), copy.deepcopy(date_ctx), copy.deepcopy(weather),
                screen_w, screen_h,
            )
            for persona in modes
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if r is True)
        logger.info(f"[CACHE] ✓ Generated {success_count}/{len(modes)} modes for {mac}")

    async def _generate_single_mode(
        self,
        mac: str,
        persona: str,
        battery_pct: float,
        config: dict,
        date_ctx: dict,
        weather: dict,
        screen_w: int = SCREEN_WIDTH,
        screen_h: int = SCREEN_HEIGHT,
    ) -> bool:
        """Generate and cache a single mode via the unified pipeline."""
        try:
            logger.info(f"[CACHE] Generating {mac}:{persona}...")

            img, _content = await generate_and_render(
                persona, config, date_ctx, weather, battery_pct,
                screen_w=screen_w, screen_h=screen_h,
            )

            await self.set(mac, persona, img, screen_w, screen_h)
            logger.info(f"[CACHE] ✓ {mac}:{persona}")
            return True

        except Exception as e:
            logger.error(f"[CACHE] ✗ {mac}:{persona} failed: {e}")
            return False

    async def _get_from_db(self, key: str, ttl_minutes: int | None = None) -> Image.Image | None:
        db = await get_cache_db()
        cursor = await db.execute(
            "SELECT image_data, created_at FROM image_cache WHERE cache_key = ?",
            (key,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        try:
            if ttl_minutes is not None and row[1]:
                created_at = datetime.fromisoformat(row[1])
                if datetime.now() - created_at >= timedelta(minutes=ttl_minutes):
                    logger.debug(f"[CACHE] DB entry {key} expired (TTL={ttl_minutes}min)")
                    return None
            img = Image.open(io.BytesIO(row[0]))
            img.load()
            return img
        except Exception:
            return None

    async def _save_to_db(self, key: str, img: Image.Image):
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data = buf.getvalue()
        db = await get_cache_db()
        await db.execute(
            """INSERT INTO image_cache (cache_key, image_data, created_at)
               VALUES (?, ?, ?)
               ON CONFLICT(cache_key) DO UPDATE SET image_data = ?, created_at = ?""",
            (key, data, datetime.now().isoformat(), data, datetime.now().isoformat()),
        )
        await db.commit()

    async def cleanup_expired(self, max_age_hours: int = 48):
        """Remove cache entries older than max_age_hours."""
        cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
        try:
            db = await get_cache_db()
            await db.execute("DELETE FROM image_cache WHERE created_at < ?", (cutoff,))
            await db.commit()
        except Exception:
            pass


# Global cache instance
content_cache = ContentCache()
