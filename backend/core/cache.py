from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from PIL import Image

logger = logging.getLogger(__name__)

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

    def _get_cache_key(
        self, mac: str, persona: str,
        screen_w: int = SCREEN_WIDTH, screen_h: int = SCREEN_HEIGHT,
    ) -> str:
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
                    return img
                else:
                    logger.debug(f"[CACHE] {key} expired (TTL={ttl_minutes}min)")
                    del self._cache[key]
            return None

    async def set(
        self, mac: str, persona: str, img: Image.Image,
        screen_w: int = SCREEN_WIDTH, screen_h: int = SCREEN_HEIGHT,
    ):
        """Store image in cache"""
        async with self._lock:
            key = self._get_cache_key(mac, persona, screen_w, screen_h)
            self._cache[key] = (img, datetime.now())

    async def check_and_regenerate_all(
        self, mac: str, config: dict, v: float = 3.3,
        screen_w: int = SCREEN_WIDTH, screen_h: int = SCREEN_HEIGHT,
    ) -> bool:
        """Check if all modes are cached, if not, regenerate all modes"""
        cacheable = get_cacheable_modes()
        modes = [m for m in config.get("modes", DEFAULT_MODES) if m in cacheable]

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

        logger.info(f"[CACHE] Regenerating all {len(modes)} modes for {mac}...")
        await self._generate_all_modes(mac, config, modes, v, screen_w, screen_h)
        return True

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
                mac, persona, battery_pct, config, date_ctx, weather,
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

            img = await generate_and_render(
                persona, config, date_ctx, weather, battery_pct,
                screen_w=screen_w, screen_h=screen_h,
            )

            await self.set(mac, persona, img, screen_w, screen_h)
            logger.info(f"[CACHE] ✓ {mac}:{persona}")
            return True

        except Exception as e:
            logger.error(f"[CACHE] ✗ {mac}:{persona} failed: {e}")
            return False


# Global cache instance
content_cache = ContentCache()
