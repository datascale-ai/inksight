"""
Unit tests for the unified generate_and_render pipeline.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from PIL import Image

from core.pipeline import generate_and_render, _generate_content_for_persona


def _make_image() -> Image.Image:
    return Image.new("1", (400, 300), 1)


def _mock_registry(*, json_modes=None, builtin_modes=None):
    """Build a mock ModeRegistry controlling which modes are JSON vs builtin."""
    json_modes = set(json_modes or [])
    builtin_modes = set(builtin_modes or [])

    mock_reg = MagicMock()
    mock_reg.is_json_mode.side_effect = lambda p: p in json_modes
    mock_reg.is_builtin.side_effect = lambda p: p in builtin_modes

    builtin_map = {}
    def _get_builtin(p):
        if p in builtin_modes:
            if p not in builtin_map:
                bm = MagicMock()
                bm.content_fn = AsyncMock()
                bm.render_fn = MagicMock()
                builtin_map[p] = bm
            return builtin_map[p]
        return None

    mock_reg.get_builtin.side_effect = _get_builtin

    def _get_json_mode(p):
        if p in json_modes:
            jm = MagicMock()
            jm.definition = {"mode_id": p, "content": {"type": "llm"}, "layout": {"body": []}}
            return jm
        return None

    mock_reg.get_json_mode.side_effect = _get_json_mode
    return mock_reg


class TestGenerateContentForPersona:
    """Test content generation dispatch."""

    @pytest.mark.asyncio
    async def test_stoic_json_mode_dispatches_to_json_content(self, sample_date_ctx, sample_weather):
        mock_reg = _mock_registry(json_modes=["STOIC"])
        with (
            patch("core.mode_registry.get_registry", return_value=mock_reg),
            patch("core.json_content.generate_json_mode_content", new_callable=AsyncMock) as mock_jc,
        ):
            mock_jc.return_value = {"quote": "Test", "author": "Author"}
            result = await _generate_content_for_persona(
                "STOIC", {}, sample_date_ctx, sample_weather["weather_str"]
            )
            assert result["quote"] == "Test"
            mock_jc.assert_called_once()

    @pytest.mark.asyncio
    async def test_briefing_dispatches_correctly(self, sample_date_ctx, sample_weather):
        mock_reg = _mock_registry(builtin_modes=["BRIEFING"])
        with patch("core.mode_registry.get_registry", return_value=mock_reg):
            bm = mock_reg.get_builtin("BRIEFING")
            bm.content_fn.return_value = {"hn_items": [], "ph_item": {}, "insight": "ok"}
            result = await _generate_content_for_persona(
                "BRIEFING", {}, sample_date_ctx, sample_weather["weather_str"]
            )
            assert result["insight"] == "ok"
            bm.content_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_artwall_dispatches_correctly(self, sample_date_ctx, sample_weather):
        mock_reg = _mock_registry(builtin_modes=["ARTWALL"])
        with patch("core.mode_registry.get_registry", return_value=mock_reg):
            bm = mock_reg.get_builtin("ARTWALL")
            bm.content_fn.return_value = {"artwork_title": "Test", "image_url": ""}
            result = await _generate_content_for_persona(
                "ARTWALL", {}, sample_date_ctx, sample_weather["weather_str"]
            )
            assert result["artwork_title"] == "Test"
            bm.content_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_recipe_dispatches_correctly(self, sample_date_ctx, sample_weather):
        mock_reg = _mock_registry(builtin_modes=["RECIPE"])
        with patch("core.mode_registry.get_registry", return_value=mock_reg):
            bm = mock_reg.get_builtin("RECIPE")
            bm.content_fn.return_value = {"season": "Test", "breakfast": ""}
            await _generate_content_for_persona(
                "RECIPE", {}, sample_date_ctx, sample_weather["weather_str"]
            )
            bm.content_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_fitness_json_mode_dispatches_to_json_content(self, sample_date_ctx, sample_weather):
        mock_reg = _mock_registry(json_modes=["FITNESS"])
        with (
            patch("core.mode_registry.get_registry", return_value=mock_reg),
            patch("core.json_content.generate_json_mode_content", new_callable=AsyncMock) as mock_jc,
        ):
            mock_jc.return_value = {"workout_name": "Test", "exercises": []}
            result = await _generate_content_for_persona(
                "FITNESS", {}, sample_date_ctx, sample_weather["weather_str"]
            )
            mock_jc.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_mode_raises(self, sample_date_ctx, sample_weather):
        mock_reg = _mock_registry()
        with patch("core.mode_registry.get_registry", return_value=mock_reg):
            with pytest.raises(ValueError):
                await _generate_content_for_persona(
                    "UNKNOWN_MODE", {}, sample_date_ctx, sample_weather["weather_str"]
                )


class TestGenerateAndRender:
    """Test the full pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline(self, sample_config, sample_date_ctx, sample_weather):
        mock_img = _make_image()
        mock_reg = _mock_registry(json_modes=["STOIC"])
        with (
            patch("core.mode_registry.get_registry", return_value=mock_reg),
            patch("core.json_content.generate_json_mode_content", new_callable=AsyncMock) as mock_gc,
            patch("core.json_renderer.render_json_mode", return_value=mock_img) as mock_rm,
        ):
            mock_gc.return_value = {"quote": "Test", "author": "Author"}

            result_img, result_content = await generate_and_render(
                "STOIC", sample_config, sample_date_ctx, sample_weather, 85.0
            )
            assert result_img is mock_img
            assert result_content == {"quote": "Test", "author": "Author"}
            mock_gc.assert_called_once()
            mock_rm.assert_called_once()

    @pytest.mark.asyncio
    async def test_none_config_treated_as_empty(self, sample_date_ctx, sample_weather):
        mock_img = _make_image()
        mock_reg = _mock_registry(json_modes=["STOIC"])
        with (
            patch("core.mode_registry.get_registry", return_value=mock_reg),
            patch("core.json_content.generate_json_mode_content", new_callable=AsyncMock) as mock_gc,
            patch("core.json_renderer.render_json_mode", return_value=mock_img) as mock_rm,
        ):
            mock_gc.return_value = {"quote": "Test", "author": "Author"}

            result_img, _ = await generate_and_render(
                "STOIC", None, sample_date_ctx, sample_weather, 85.0
            )
            assert result_img is mock_img
