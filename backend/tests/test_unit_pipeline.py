"""
Unit tests for the unified generate_and_render pipeline.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from PIL import Image

from core.pipeline import generate_and_render, _generate_content_for_persona


def _make_image() -> Image.Image:
    return Image.new("1", (400, 300), 1)


class TestGenerateContentForPersona:
    """Test content generation dispatch."""

    @pytest.mark.asyncio
    async def test_stoic_dispatches_to_generate_content(self, sample_date_ctx, sample_weather):
        with patch("core.pipeline.generate_content", new_callable=AsyncMock) as mock_gc:
            mock_gc.return_value = {"quote": "Test", "author": "Author"}
            result = await _generate_content_for_persona(
                "STOIC", {}, sample_date_ctx, sample_weather["weather_str"]
            )
            assert result["quote"] == "Test"
            mock_gc.assert_called_once()

    @pytest.mark.asyncio
    async def test_briefing_dispatches_correctly(self, sample_date_ctx, sample_weather):
        with patch("core.pipeline.generate_briefing_content", new_callable=AsyncMock) as mock_bc:
            mock_bc.return_value = {"hn_items": [], "ph_item": {}, "insight": "ok"}
            result = await _generate_content_for_persona(
                "BRIEFING", {}, sample_date_ctx, sample_weather["weather_str"]
            )
            assert result["insight"] == "ok"
            mock_bc.assert_called_once()

    @pytest.mark.asyncio
    async def test_artwall_dispatches_correctly(self, sample_date_ctx, sample_weather):
        with patch("core.pipeline.generate_artwall_content", new_callable=AsyncMock) as mock_ac:
            mock_ac.return_value = {"artwork_title": "Test", "image_url": ""}
            result = await _generate_content_for_persona(
                "ARTWALL", {}, sample_date_ctx, sample_weather["weather_str"]
            )
            assert result["artwork_title"] == "Test"
            mock_ac.assert_called_once()

    @pytest.mark.asyncio
    async def test_recipe_dispatches_correctly(self, sample_date_ctx, sample_weather):
        with patch("core.pipeline.generate_recipe_content", new_callable=AsyncMock) as mock_rc:
            mock_rc.return_value = {"season": "Test", "breakfast": ""}
            result = await _generate_content_for_persona(
                "RECIPE", {}, sample_date_ctx, sample_weather["weather_str"]
            )
            mock_rc.assert_called_once()

    @pytest.mark.asyncio
    async def test_fitness_dispatches_correctly(self, sample_date_ctx, sample_weather):
        with patch("core.pipeline.generate_fitness_content", new_callable=AsyncMock) as mock_fc:
            mock_fc.return_value = {"workout_name": "Test", "exercises": []}
            result = await _generate_content_for_persona(
                "FITNESS", {}, sample_date_ctx, sample_weather["weather_str"]
            )
            mock_fc.assert_called_once()


class TestGenerateAndRender:
    """Test the full pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline(self, sample_config, sample_date_ctx, sample_weather):
        mock_img = _make_image()
        with (
            patch("core.pipeline.generate_content", new_callable=AsyncMock) as mock_gc,
            patch("core.pipeline.render_mode") as mock_rm,
        ):
            mock_gc.return_value = {"quote": "Test", "author": "Author"}
            mock_rm.return_value = mock_img

            result = await generate_and_render(
                "STOIC", sample_config, sample_date_ctx, sample_weather, 85.0
            )
            assert result is mock_img
            mock_gc.assert_called_once()
            mock_rm.assert_called_once()

    @pytest.mark.asyncio
    async def test_none_config_treated_as_empty(self, sample_date_ctx, sample_weather):
        mock_img = _make_image()
        with (
            patch("core.pipeline.generate_content", new_callable=AsyncMock) as mock_gc,
            patch("core.pipeline.render_mode") as mock_rm,
        ):
            mock_gc.return_value = {"quote": "Test", "author": "Author"}
            mock_rm.return_value = mock_img

            result = await generate_and_render(
                "STOIC", None, sample_date_ctx, sample_weather, 85.0
            )
            assert result is mock_img
