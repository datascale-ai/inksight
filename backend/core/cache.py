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

# Experiment switches (controlled via environment variables)
DISABLE_CACHE = os.environ.get("INKSIGHT_DISABLE_CACHE", "").strip().lower() in ("1", "true", "yes")
DISABLE_BATCH_REGEN = os.environ.get("INKSIGHT_DISABLE_BATCH_REGEN", "").strip().lower() in ("1", "true", "yes")

if DISABLE_CACHE:
    logger.warning("[EXP] Cache is DISABLED via INKSIGHT_DISABLE_CACHE")
if DISABLE_BATCH_REGEN:
    logger.warning("[EXP] Batch regeneration is DISABLED via INKSIGHT_DISABLE_BATCH_REGEN")

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
    DEFAULT_MODES,
    get_cacheable_modes,
)
from .context import get_date_context, get_weather, calc_battery_pct, extract_location_settings
from .pipeline import generate_and_render, get_effective_mode_config


class ContentCache:
    def __init__(self):
        self._cache: dict[str, tuple[Image.Image, datetime]] = {}
        self._lock = asyncio.Lock()
        self._regenerating: set[str] = set()
        self._db_failure_count = 0
        self._db_disabled_until: datetime | None = None

    def _get_cache_key(
        self, mac: str, persona: str,
        screen_w: int = SCREEN_WIDTH, screen_h: int = SCREEN_HEIGHT,
    ) -> str:
        persona = (persona or "").upper()
        return f"{mac}:{persona}:{screen_w}x{screen_h}"

    def _persistent_cache_available(self) -> bool:
        if self._db_disabled_until is None:
            return True
        if datetime.now() >= self._db_disabled_until:
            logger.info("[CACHE] Persistent cache DB re-enabled after cooldown")
            self._db_disabled_until = None
            self._db_failure_count = 0
            return True
        return False

    def _record_db_failure(self, operation: str, exc: Exception):
        self._db_failure_count += 1
        logger.warning("[CACHE] Persistent cache %s failed (%s)", operation, exc, exc_info=True)
        if self._db_failure_count >= 3 and self._db_disabled_until is None:
            self._db_disabled_until = datetime.now() + timedelta(minutes=5)
            logger.error(
                "[CACHE] Persistent cache disabled for 5 minutes after %s consecutive failures",
                self._db_failure_count,
            )

    def _record_db_success(self):
        if self._db_failure_count > 0 or self._db_disabled_until is not None:
            logger.info("[CACHE] Persistent cache DB recovered")
        self._db_failure_count = 0
        self._db_disabled_until = None

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
        if DISABLE_CACHE:
            return None
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
            if self._persistent_cache_available():
                try:
                    img = await self._get_from_db(key, ttl_minutes=ttl_minutes)
                    self._record_db_success()
                    if img:
                        self._cache[key] = (img, datetime.now())
                        return img.copy()
                except (aiosqlite.Error, OSError, RuntimeError, ValueError) as exc:
                    self._record_db_failure("load", exc)
            return None

    async def set(
        self, mac: str, persona: str, img: Image.Image,
        screen_w: int = SCREEN_WIDTH, screen_h: int = SCREEN_HEIGHT,
    ):
        """Store image in cache"""
        if DISABLE_CACHE:
            return
        async with self._lock:
            key = self._get_cache_key(mac, persona, screen_w, screen_h)
            img_copy = img.copy()
            self._cache[key] = (img_copy, datetime.now())
            if self._persistent_cache_available():
                try:
                    await self._save_to_db(key, img_copy)
                    self._record_db_success()
                except (aiosqlite.Error, OSError, RuntimeError, ValueError) as exc:
                    self._record_db_failure("save", exc)

    async def check_and_regenerate_all(
        self, mac: str, config: dict, v: float = 3.3,
        screen_w: int = SCREEN_WIDTH, screen_h: int = SCREEN_HEIGHT,
    ) -> bool:
        """Check if all modes are cached, if not, regenerate all modes"""
        if DISABLE_CACHE or DISABLE_BATCH_REGEN:
            return False
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

    async def force_regenerate_all(
        self, mac: str, config: dict, v: float = 3.3,
        screen_w: int = SCREEN_WIDTH, screen_h: int = SCREEN_HEIGHT,
    ) -> bool:
        """Force background regeneration for all cacheable modes."""
        cacheable = get_cacheable_modes()
        modes = [m.upper() for m in config.get("modes", DEFAULT_MODES) if m.upper() in cacheable]
        if not modes:
            return False
        if mac in self._regenerating:
            logger.debug(f"[CACHE] Background regeneration already in progress for {mac}")
            return False
        self._regenerating.add(mac)
        logger.info(f"[CACHE] Force regenerating all {len(modes)} modes for {mac}...")
        asyncio.create_task(
            self._regenerate_background(mac, config, modes, v, screen_w, screen_h)
        )
        return True

    async def _regenerate_background(
        self, mac: str, config: dict, modes: list[str], v: float,
        screen_w: int = SCREEN_WIDTH, screen_h: int = SCREEN_HEIGHT,
    ):
        """Background task that wraps _generate_all_modes with cleanup of _regenerating."""
        try:
            await self._generate_all_modes(mac, config, modes, v, screen_w, screen_h)
        except (OSError, RuntimeError, TypeError, ValueError) as e:
            logger.error(f"[CACHE] Background regeneration failed for {mac}: {e}")
        finally:
            self._regenerating.discard(mac)

    async def _generate_all_modes(
        self, mac: str, config: dict, modes: list[str], v: float,
        screen_w: int = SCREEN_WIDTH, screen_h: int = SCREEN_HEIGHT,
    ):
        """Generate and cache all modes"""
        battery_pct = calc_battery_pct(v)
        date_ctx = await get_date_context()

        tasks = [
            self._render_single_mode_for_batch(
                mac, persona, battery_pct, copy.deepcopy(config), copy.deepcopy(date_ctx),
                screen_w, screen_h,
            )
            for persona in modes
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        generated_entries: list[tuple[str, Image.Image]] = []
        for result in results:
            if isinstance(result, tuple):
                generated_entries.append(result)

        async with self._lock:
            now = datetime.now()
            for persona, img in generated_entries:
                key = self._get_cache_key(mac, persona, screen_w, screen_h)
                self._cache[key] = (img.copy(), now)

        if generated_entries and self._persistent_cache_available():
            try:
                await self._save_many_to_db(
                    [
                        (self._get_cache_key(mac, persona, screen_w, screen_h), img)
                        for persona, img in generated_entries
                    ]
                )
                self._record_db_success()
            except (aiosqlite.Error, OSError, RuntimeError, ValueError) as exc:
                self._record_db_failure("batch-save", exc)

        success_count = len(generated_entries)
        logger.info(f"[CACHE] ✓ Generated {success_count}/{len(modes)} modes for {mac}")

    async def _render_single_mode_for_batch(
        self,
        mac: str,
        persona: str,
        battery_pct: float,
        config: dict,
        date_ctx: dict,
        screen_w: int = SCREEN_WIDTH,
        screen_h: int = SCREEN_HEIGHT,
    ) -> tuple[str, Image.Image] | None:
        try:
            logger.info(f"[CACHE] Generating {mac}:{persona}...")
            effective_cfg = get_effective_mode_config(config, persona)
            weather = await get_weather(**extract_location_settings(effective_cfg))

            img, _content = await generate_and_render(
                persona, config, date_ctx, weather, battery_pct,
                screen_w=screen_w, screen_h=screen_h,
            )
            logger.info(f"[CACHE] ✓ {mac}:{persona}")
            return persona, img
        except (OSError, RuntimeError, TypeError, ValueError) as e:
            logger.error(f"[CACHE] ✗ {mac}:{persona} failed: {e}")
            return None

    async def _generate_single_mode(
        self,
        mac: str,
        persona: str,
        battery_pct: float,
        config: dict,
        date_ctx: dict,
        *args,
        screen_w: int = SCREEN_WIDTH,
        screen_h: int = SCREEN_HEIGHT,
    ) -> bool:
        """Generate and cache a single mode via the unified pipeline."""
        try:
            logger.info(f"[CACHE] Generating {mac}:{persona}...")
            if args:
                if isinstance(args[0], dict):
                    if len(args) >= 2 and isinstance(args[1], int):
                        screen_w = args[1]
                    if len(args) >= 3 and isinstance(args[2], int):
                        screen_h = args[2]
                else:
                    if isinstance(args[0], int):
                        screen_w = args[0]
                    if len(args) >= 2 and isinstance(args[1], int):
                        screen_h = args[1]
            effective_cfg = get_effective_mode_config(config, persona)
            weather = await get_weather(**extract_location_settings(effective_cfg))

            img, _content = await generate_and_render(
                persona, config, date_ctx, weather, battery_pct,
                screen_w=screen_w, screen_h=screen_h,
            )

            await self.set(mac, persona, img, screen_w, screen_h)
            logger.info(f"[CACHE] ✓ {mac}:{persona}")
            return True

        except (OSError, RuntimeError, TypeError, ValueError) as e:
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
        except (OSError, TypeError, ValueError) as exc:
            logger.warning("[CACHE] Failed to decode cached image for %s", key, exc_info=True)
            raise RuntimeError(f"decode failed for cache key {key}") from exc

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
        await db.close()

    async def _save_many_to_db(self, items: list[tuple[str, Image.Image]]):
        if not items:
            return
        rows = []
        now = datetime.now().isoformat()
        for key, img in items:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            data = buf.getvalue()
            rows.append((key, data, now, data, now))
        db = await get_cache_db()
        await db.executemany(
            """INSERT INTO image_cache (cache_key, image_data, created_at)
               VALUES (?, ?, ?)
               ON CONFLICT(cache_key) DO UPDATE SET image_data = ?, created_at = ?""",
            rows,
        )
        await db.commit()
        await db.close()

    async def cleanup_expired(self, max_age_hours: int = 48):
        """Remove cache entries older than max_age_hours."""
        cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
        if not self._persistent_cache_available():
            return
        try:
            db = await get_cache_db()
            await db.execute("DELETE FROM image_cache WHERE created_at < ?", (cutoff,))
            await db.commit()
            await db.close()
            self._record_db_success()
        except (aiosqlite.Error, OSError, ValueError) as exc:
            self._record_db_failure("cleanup", exc)


# Global cache instance
content_cache = ContentCache()
