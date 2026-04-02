"""
Unit tests for content generation helpers (no real LLM calls).
"""
import json
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from core.content import (
    _clean_json_response,
    _build_context_str,
    _build_style_instructions,
    _fallback_content,
    generate_countdown_content,
    generate_artwall_content,
    generate_recipe_content,
    generate_content,
    fetch_hn_top_stories,
    fetch_ph_top_product,
    summarize_briefing_content,
    generate_briefing_content,
)
from core.errors import LLMKeyMissingError


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

    def test_english_filters_cjk_holiday_context(self):
        result = _build_context_str(
            "Apr 4",
            "15°C",
            festival="清明节",
            daily_word="春和景明",
            upcoming_holiday="清明节",
            days_until=3,
            language="en",
        )
        assert "Qingming" not in result
        assert "清明" not in result
        assert "春和景明" not in result
        assert "Date: Apr 4" in result
        assert "Weather: 15°C" in result


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
        assert "English" in result

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
            mock_llm.side_effect = LLMKeyMissingError("missing key")
            result = await generate_content(
                persona="DAILY",
                date_str="2月16日",
                weather_str="12°C",
            )
            # Should return fallback content
            assert "quote" in result
            assert "author" in result


class TestGenerateCountdownContent:
    @pytest.mark.asyncio
    async def test_generates_message_from_event_and_tone(self):
        result = await generate_countdown_content(
            config={
                "countdownEvents": [
                    {"name": "项目截止", "date": "2099-01-01", "type": "countdown"},
                ],
                "content_tone": "positive",
            }
        )

        assert result["events"][0]["name"] == "项目截止"
        assert "项目截止" in result["message"]
        assert "加油" in result["message"]

    @pytest.mark.asyncio
    async def test_generates_english_message(self):
        result = await generate_countdown_content(
            config={
                "countdownEvents": [
                    {"name": "Demo Day", "date": "2099-01-01", "type": "countdown"},
                ],
                "mode_language": "en",
                "content_tone": "humor",
            }
        )

        assert result["events"][0]["name"] == "Demo Day"
        assert "Demo Day" in result["message"]
        assert "plan" in result["message"]


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
            instance.get = AsyncMock(side_effect=httpx.ReadTimeout("Network error"))
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            stories = await fetch_hn_top_stories()
            assert stories == []

    @pytest.mark.asyncio
    async def test_product_hunt_parse_failure_returns_empty(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<rss><broken"

        with patch("core.content.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            product = await fetch_ph_top_product()
            assert product == {}


class TestGenerateBriefingContent:
    """Test full briefing pipeline with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_all_sources_fail_returns_fallback(self):
        with (
            patch("core.content.fetch_hn_top_stories", new_callable=AsyncMock) as mock_hn,
            patch("core.content.fetch_ph_top_product", new_callable=AsyncMock) as mock_ph,
            patch("core.content.fetch_v2ex_hot", new_callable=AsyncMock) as mock_v2ex,
        ):
            mock_hn.return_value = []
            mock_ph.return_value = {}
            mock_v2ex.return_value = []

            result = await generate_briefing_content()
            assert "hn_items" in result
            assert "insight" in result

    @pytest.mark.asyncio
    async def test_all_sources_fail_returns_english_fallback(self):
        ctx = MagicMock()
        ctx.llm_provider = "deepseek"
        ctx.llm_model = "deepseek-chat"
        ctx.api_key = None
        ctx.language = "en"
        with (
            patch("core.content.fetch_hn_top_stories", new_callable=AsyncMock) as mock_hn,
            patch("core.content.fetch_ph_top_product", new_callable=AsyncMock) as mock_ph,
            patch("core.content.fetch_v2ex_hot", new_callable=AsyncMock) as mock_v2ex,
        ):
            mock_hn.return_value = []
            mock_ph.return_value = {}
            mock_v2ex.return_value = []

            result = await generate_briefing_content(ctx=ctx)
            assert result["hn_items"][0]["title"] == "Hacker News API unavailable"
            assert "Unable to fetch" in result["insight"]

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


class TestBriefingSummaries:
    @pytest.mark.asyncio
    async def test_summarize_briefing_content_invalid_json_returns_originals(self):
        stories = [{"title": "A very long story title that should be summarized", "score": 10}]
        ph = {"name": "CoolApp", "tagline": "A long English tagline that should also be summarized"}

        with patch("core.content._call_llm", new_callable=AsyncMock, return_value="not-json"):
            summarized_stories, summarized_ph = await summarize_briefing_content(stories, ph)

        # 当 JSON 解析失败时，应该返回 None, None 表示失败
        assert summarized_stories is None
        assert summarized_ph is None

    @pytest.mark.asyncio
    async def test_summarize_briefing_content_english_prompt(self):
        stories = [{"title": "A very long story title that should be summarized", "score": 10}]
        ph = {"name": "CoolApp", "tagline": "A long English tagline that should also be summarized"}

        with patch(
            "core.content._call_llm",
            new_callable=AsyncMock,
            return_value='{"hn_summaries":["Short summary"],"ph_summary":"English intro"}',
        ) as mock_call:
            summarized_stories, summarized_ph = await summarize_briefing_content(stories, ph, language="en")

        prompt = mock_call.await_args.args[2]
        assert "concise English" in prompt
        assert "中文" not in prompt
        assert summarized_stories[0]["summary"] == "Short summary"
        assert summarized_ph["tagline"] == "English intro"


class TestRecipeAndArtwallFallbacks:
    @pytest.mark.asyncio
    async def test_recipe_invalid_json_uses_fallback(self):
        with patch("core.content._call_llm", new_callable=AsyncMock, return_value="broken json"):
            result = await generate_recipe_content()

        assert "breakfast" in result
        assert result["lunch"]["meat"]
        assert result["nutrition"]

    @pytest.mark.asyncio
    async def test_artwall_title_failure_keeps_image_prompt_fallback(self):
        with patch("core.content._call_llm", new_callable=AsyncMock, side_effect=LLMKeyMissingError("missing key")):
            result = await generate_artwall_content(
                date_str="2月14日",
                weather_str="晴 15°C",
                festival="情人节",
                image_api_key="",
                fallback_title="墨韵天成",
            )

        assert result["artwork_title"] == "墨韵天成"
        assert result["image_url"] == ""
        assert result["prompt"]

    @pytest.mark.asyncio
    async def test_artwall_color_device_uses_color_prompt(self):
        with patch("core.content._call_llm", new_callable=AsyncMock, side_effect=LLMKeyMissingError("missing key")):
            result = await generate_artwall_content(
                date_str="2月14日",
                weather_str="晴 15°C",
                festival="情人节",
                colors=4,
                image_api_key="",
                fallback_title="墨韵天成",
            )

        assert result["image_url"] == ""
        assert "黑、白、红、黄" in result["prompt"]
        assert result["description"] == "彩色极简插画"
