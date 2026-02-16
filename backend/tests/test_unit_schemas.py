"""
Unit tests for Pydantic input validation schemas.
"""
import pytest
from pydantic import ValidationError
from core.schemas import ConfigRequest


class TestConfigRequest:
    """Tests for the ConfigRequest Pydantic model."""

    def test_valid_config(self):
        body = ConfigRequest(
            mac="AA:BB:CC:DD:EE:FF",
            nickname="MyDevice",
            modes=["STOIC", "ZEN"],
            refreshStrategy="cycle",
            refreshInterval=30,
            language="zh",
            contentTone="neutral",
            city="北京",
            llmProvider="deepseek",
            llmModel="deepseek-chat",
        )
        assert body.mac == "AA:BB:CC:DD:EE:FF"
        assert body.modes == ["STOIC", "ZEN"]
        assert body.refreshInterval == 30

    def test_invalid_mac_format(self):
        with pytest.raises(ValidationError, match="MAC"):
            ConfigRequest(mac="invalid-mac")

    def test_invalid_mac_too_short(self):
        with pytest.raises(ValidationError):
            ConfigRequest(mac="AA:BB")

    def test_unsupported_mode(self):
        with pytest.raises(ValidationError, match="不支持的模式"):
            ConfigRequest(mac="AA:BB:CC:DD:EE:FF", modes=["INVALID_MODE"])

    def test_modes_uppercased(self):
        body = ConfigRequest(mac="AA:BB:CC:DD:EE:FF", modes=["stoic", "zen"])
        assert body.modes == ["STOIC", "ZEN"]

    def test_empty_modes_rejected(self):
        with pytest.raises(ValidationError):
            ConfigRequest(mac="AA:BB:CC:DD:EE:FF", modes=[])

    def test_refresh_interval_min(self):
        with pytest.raises(ValidationError):
            ConfigRequest(mac="AA:BB:CC:DD:EE:FF", refreshInterval=5)

    def test_refresh_interval_max(self):
        with pytest.raises(ValidationError):
            ConfigRequest(mac="AA:BB:CC:DD:EE:FF", refreshInterval=2000)

    def test_invalid_language(self):
        with pytest.raises(ValidationError, match="无效语言"):
            ConfigRequest(mac="AA:BB:CC:DD:EE:FF", language="fr")

    def test_invalid_tone(self):
        with pytest.raises(ValidationError, match="无效调性"):
            ConfigRequest(mac="AA:BB:CC:DD:EE:FF", contentTone="angry")

    def test_invalid_provider(self):
        with pytest.raises(ValidationError, match="无效 LLM 提供商"):
            ConfigRequest(mac="AA:BB:CC:DD:EE:FF", llmProvider="openai")

    def test_invalid_strategy(self):
        with pytest.raises(ValidationError, match="无效刷新策略"):
            ConfigRequest(mac="AA:BB:CC:DD:EE:FF", refreshStrategy="sequential")

    def test_nickname_max_length(self):
        with pytest.raises(ValidationError):
            ConfigRequest(mac="AA:BB:CC:DD:EE:FF", nickname="a" * 50)

    def test_defaults(self):
        body = ConfigRequest(mac="AA:BB:CC:DD:EE:FF")
        assert body.nickname == ""
        assert body.modes == ["STOIC"]
        assert body.refreshStrategy == "random"
        assert body.refreshInterval == 60
        assert body.language == "zh"
        assert body.contentTone == "neutral"
        assert body.city == "杭州"
        assert body.llmProvider == "deepseek"

    def test_model_dump(self):
        body = ConfigRequest(mac="AA:BB:CC:DD:EE:FF", modes=["DAILY"])
        d = body.model_dump()
        assert isinstance(d, dict)
        assert d["mac"] == "AA:BB:CC:DD:EE:FF"
        assert d["modes"] == ["DAILY"]

    def test_character_tones_cleaned(self):
        body = ConfigRequest(
            mac="AA:BB:CC:DD:EE:FF",
            characterTones=["  鲁迅 ", "", "  莫言  "],
        )
        assert body.characterTones == ["鲁迅", "莫言"]
