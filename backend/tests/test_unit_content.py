"""
Unit tests for content generation helpers (no real LLM calls).
"""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from core.content import (
    _clean_json_response,
    _build_context_str,
    _build_style_instructions,
    _fallback_content,
    generate_content,
    fetch_hn_top_stories,
    fetch_ph_top_product,
    generate_briefing_content,
)


class TestCleanJsonResponse:
    def test_plain_json(self):
        assert _clean_json_response('{"a":1}') == '{"a":1}'

    def test_fenced_json(self):
        text = '```json\n{"a":1}\n```'
        assert _clean_json_response(text) == '{"a":1}'

    def test_fenced_no_lang(self):
        text = '```\n{"a":1}\n```'
        assert _clean_json_response(text) == '{"a":1}'

    def test_whitespace_preserved(self):
        assert _clean_json_response("  hello  ") == "hello"


class TestBuildContextStr:
    def test_basic(self):
        result = _build_context_str("2月16日", "12°C")
        assert "日期: 2月16日" in result
        assert "天气: 12°C" in result

    def test_with_festival(self):
        result = _build_context_str("1月1日", "5°C", festival="元旦")
        assert "节日: 元旦" in result

    def test_with_holiday(self):
        result = _build_context_str(
            "3月1日", "10°C", upcoming_holiday="清明节", days_until=35
        )
        assert "35天后是清明节" in result

    def test_with_daily_word(self):
        result = _build_context_str("2月16日", "12°C", daily_word="春风化雨")
        assert "每日一词: 春风化雨" in result


class TestBuildStyleInstructions:
    def test_empty(self):
        assert _build_style_instructions(None, None, None) == ""
        assert _build_style_instructions([], "zh", "neutral") == ""

    def test_character_tones(self):
        result = _build_style_instructions(["鲁迅", "莫言"], None, None)
        assert "鲁迅" in result
        assert "莫言" in result

    def test_language_en(self):
        result = _build_style_instructions(None, "en", None)
        assert "英文" in result

    def test_content_tone_humor(self):
        result = _build_style_instructions(None, None, "humor")
        assert "幽默" in result


class TestFallbackContent:
    def test_daily_fallback(self):
        c = _fallback_content("DAILY")
        assert "quote" in c
        assert "book_title" in c
        assert "tip" in c

    def test_briefing_fallback(self):
        c = _fallback_content("BRIEFING")
        assert "hn_items" in c
        assert "ph_item" in c
        assert "insight" in c

    def test_unknown_fallback(self):
        c = _fallback_content("UNKNOWN")
        assert "quote" in c


class TestGenerateContent:
    """Test generate_content with mocked LLM calls."""

    @pytest.mark.asyncio
    async def test_unknown_persona_uses_fallback(self):
        with patch("core.content._call_llm", new_callable=AsyncMock) as mock_llm:
            result = await generate_content(
                persona="STOIC",
                date_str="2月16日",
                weather_str="12°C",
            )
            mock_llm.assert_not_called()
            assert "quote" in result

    @pytest.mark.asyncio
    async def test_daily_mode(self):
        daily_json = json.dumps({
            "quote": "学而不思则罔",
            "author": "孔子",
            "book_title": "《论语》",
            "book_author": "孔子 著",
            "book_desc": "中国古典哲学的基础之作。",
            "tip": "多读书多思考。",
            "season_text": "立春已过",
        })
        with patch("core.content._call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = daily_json
            result = await generate_content(
                persona="DAILY",
                date_str="2月16日",
                weather_str="12°C",
            )
            assert result["quote"] == "学而不思则罔"
            assert result["book_title"] == "《论语》"

    @pytest.mark.asyncio
    async def test_llm_failure_returns_fallback(self):
        with patch("core.content._call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("API timeout")
            result = await generate_content(
                persona="DAILY",
                date_str="2月16日",
                weather_str="12°C",
            )
            # Should return fallback content
            assert "quote" in result
            assert "author" in result


class TestFetchHNStories:
    """Test HN fetcher with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_success(self):
        mock_response_ids = MagicMock()
        mock_response_ids.status_code = 200
        mock_response_ids.json.return_value = [100, 200, 300]

        def make_story_response(sid):
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "title": f"Story {sid}",
                "score": sid,
                "url": f"https://example.com/{sid}",
            }
            return resp

        async def mock_get(url, **kwargs):
            if "topstories" in url:
                return mock_response_ids
            for sid in [100, 200, 300]:
                if str(sid) in url:
                    return make_story_response(sid)
            return MagicMock(status_code=404)

        with patch("core.content.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = mock_get
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            stories = await fetch_hn_top_stories(limit=3)
            assert len(stories) == 3
            assert stories[0]["title"] == "Story 100"

    @pytest.mark.asyncio
    async def test_failure_returns_empty(self):
        with patch("core.content.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(side_effect=Exception("Network error"))
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            stories = await fetch_hn_top_stories()
            assert stories == []


class TestGenerateBriefingContent:
    """Test full briefing pipeline with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_all_sources_fail_returns_fallback(self):
        with (
            patch("core.content.fetch_hn_top_stories", new_callable=AsyncMock) as mock_hn,
            patch("core.content.fetch_ph_top_product", new_callable=AsyncMock) as mock_ph,
        ):
            mock_hn.return_value = []
            mock_ph.return_value = {}

            result = await generate_briefing_content()
            assert "hn_items" in result
            assert "insight" in result

    @pytest.mark.asyncio
    async def test_success_path(self):
        mock_stories = [
            {"title": "Story A", "score": 100, "url": ""},
            {"title": "Story B is a very long title that needs summarizing", "score": 50, "url": ""},
        ]
        mock_ph = {"name": "CoolApp", "tagline": "Short"}

        with (
            patch("core.content.fetch_hn_top_stories", new_callable=AsyncMock) as m_hn,
            patch("core.content.fetch_ph_top_product", new_callable=AsyncMock) as m_ph,
            patch("core.content.summarize_briefing_content", new_callable=AsyncMock) as m_sum,
            patch("core.content.generate_briefing_insight", new_callable=AsyncMock) as m_ins,
        ):
            m_hn.return_value = mock_stories
            m_ph.return_value = mock_ph
            m_sum.return_value = (mock_stories, mock_ph)
            m_ins.return_value = "AI 行业持续创新。"

            result = await generate_briefing_content()
            assert len(result["hn_items"]) == 2
            assert result["insight"] == "AI 行业持续创新。"
