"""
Shared pytest fixtures for InkSight unit tests.
"""
import os
import sys
import pytest

# Ensure backend root is on sys.path so `core.*` imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set dummy env vars so modules can import without real keys
os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-dummy-key-000")
os.environ.setdefault("DASHSCOPE_API_KEY", "sk-test-dummy-key-001")
os.environ.setdefault("MOONSHOT_API_KEY", "sk-test-dummy-key-002")


@pytest.fixture
def sample_config():
    """A typical device configuration dict."""
    return {
        "mac": "AA:BB:CC:DD:EE:FF",
        "nickname": "TestDevice",
        "modes": ["STOIC", "ROAST", "ZEN"],
        "refresh_strategy": "cycle",
        "refresh_interval": 60,
        "character_tones": [],
        "language": "zh",
        "content_tone": "neutral",
        "city": "杭州",
        "llm_provider": "deepseek",
        "llm_model": "deepseek-chat",
    }


@pytest.fixture
def sample_date_ctx():
    """A typical date context dict."""
    return {
        "date_str": "2月16日 周一",
        "time_str": "09:30:00",
        "weekday": 0,
        "hour": 9,
        "is_weekend": False,
        "year": 2026,
        "day": 16,
        "month_cn": "二月",
        "weekday_cn": "周一",
        "day_of_year": 47,
        "days_in_year": 365,
        "festival": "",
        "is_holiday": False,
        "is_workday": True,
        "upcoming_holiday": "清明节",
        "days_until_holiday": 48,
        "holiday_date": "04月05日",
        "daily_word": "春风化雨",
    }


@pytest.fixture
def sample_weather():
    """A typical weather dict."""
    return {
        "temp": 12,
        "weather_code": 1,
        "weather_str": "12°C",
    }
