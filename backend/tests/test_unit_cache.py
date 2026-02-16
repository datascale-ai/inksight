"""
Unit tests for the ContentCache module.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from PIL import Image

from core.cache import ContentCache


def _make_image() -> Image.Image:
    """Create a small 1-bit test image."""
    return Image.new("1", (400, 300), 1)


class TestContentCache:
    """Tests for cache get/set/TTL logic."""

    @pytest.fixture
    def cache(self):
        return ContentCache()

    @pytest.fixture
    def config(self):
        return {
            "modes": ["STOIC", "ROAST"],
            "refresh_interval": 60,
        }

    @pytest.mark.asyncio
    async def test_get_returns_none_when_empty(self, cache, config):
        result = await cache.get("AA:BB:CC:DD:EE:FF", "STOIC", config)
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache, config):
        img = _make_image()
        await cache.set("AA:BB:CC:DD:EE:FF", "STOIC", img)
        result = await cache.get("AA:BB:CC:DD:EE:FF", "STOIC", config)
        assert result is not None
        assert result.size == (400, 300)

    @pytest.mark.asyncio
    async def test_get_expired(self, cache, config):
        img = _make_image()
        await cache.set("AA:BB:CC:DD:EE:FF", "STOIC", img)

        # Manually expire the entry
        key = cache._get_cache_key("AA:BB:CC:DD:EE:FF", "STOIC")
        cache._cache[key] = (img, datetime.now() - timedelta(hours=10))

        result = await cache.get("AA:BB:CC:DD:EE:FF", "STOIC", config)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_with_explicit_ttl(self, cache, config):
        img = _make_image()
        await cache.set("AA:BB:CC:DD:EE:FF", "STOIC", img)

        # Should be cached within 1000 minutes
        result = await cache.get("AA:BB:CC:DD:EE:FF", "STOIC", config, ttl_minutes=1000)
        assert result is not None

        # Should be expired with 0 minutes TTL
        result = await cache.get("AA:BB:CC:DD:EE:FF", "STOIC", config, ttl_minutes=0)
        assert result is None

    def test_cache_key_format(self, cache):
        assert cache._get_cache_key("AA:BB", "STOIC") == "AA:BB:STOIC"

    def test_ttl_minutes_calculation(self, cache, config):
        ttl = cache._get_ttl_minutes(config)
        # 60 min * 2 modes * 1.1 = 132
        assert ttl == 132

    def test_ttl_with_non_cacheable_modes(self, cache):
        config = {
            "modes": ["STOIC", "BRIEFING", "ZEN"],
            "refresh_interval": 30,
        }
        ttl = cache._get_ttl_minutes(config)
        # BRIEFING is not in CACHEABLE_MODES, so only STOIC and ZEN count
        # 30 * 2 * 1.1 = 66
        assert ttl == 66

    @pytest.mark.asyncio
    async def test_check_and_regenerate_all_skips_when_cached(self, cache, config):
        img = _make_image()
        await cache.set("AA:BB:CC:DD:EE:FF", "STOIC", img)
        await cache.set("AA:BB:CC:DD:EE:FF", "ROAST", img)

        with patch.object(cache, "_generate_all_modes", new_callable=AsyncMock) as mock_gen:
            result = await cache.check_and_regenerate_all(
                "AA:BB:CC:DD:EE:FF", config, 3.3
            )
            assert result is True
            mock_gen.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_and_regenerate_all_triggers_on_miss(self, cache, config):
        with patch.object(cache, "_generate_all_modes", new_callable=AsyncMock) as mock_gen:
            result = await cache.check_and_regenerate_all(
                "AA:BB:CC:DD:EE:FF", config, 3.3
            )
            assert result is True
            mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_and_regenerate_returns_false_for_no_cacheable_modes(self, cache):
        config = {"modes": ["BRIEFING", "ARTWALL"], "refresh_interval": 60}
        result = await cache.check_and_regenerate_all("AA:BB:CC:DD:EE:FF", config, 3.3)
        assert result is False


class TestGenerateSingleMode:
    """Test the single-mode generation wrapper."""

    @pytest.fixture
    def cache(self):
        return ContentCache()

    @pytest.mark.asyncio
    async def test_success(self, cache, sample_config, sample_date_ctx, sample_weather):
        mock_img = _make_image()
        with patch("core.cache.generate_and_render", new_callable=AsyncMock) as mock_gar:
            mock_gar.return_value = mock_img
            result = await cache._generate_single_mode(
                "AA:BB:CC:DD:EE:FF", "STOIC", 85.0,
                sample_config, sample_date_ctx, sample_weather,
            )
            assert result is True
            cached = await cache.get("AA:BB:CC:DD:EE:FF", "STOIC", sample_config)
            assert cached is not None

    @pytest.mark.asyncio
    async def test_failure_returns_false(self, cache, sample_config, sample_date_ctx, sample_weather):
        with patch("core.cache.generate_and_render", new_callable=AsyncMock) as mock_gar:
            mock_gar.side_effect = RuntimeError("Render failed")
            result = await cache._generate_single_mode(
                "AA:BB:CC:DD:EE:FF", "STOIC", 85.0,
                sample_config, sample_date_ctx, sample_weather,
            )
            assert result is False
