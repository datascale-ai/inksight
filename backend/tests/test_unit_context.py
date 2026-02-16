"""
Unit tests for context helpers (battery, city, weather).
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from core.context import calc_battery_pct, _resolve_city, get_weather
from core.config import DEFAULT_LATITUDE, DEFAULT_LONGITUDE


class TestCalcBatteryPct:
    def test_full_charge(self):
        assert calc_battery_pct(3.3) == 100

    def test_half_charge(self):
        assert calc_battery_pct(1.65) == 50

    def test_empty(self):
        assert calc_battery_pct(0.0) == 0

    def test_over_voltage(self):
        assert calc_battery_pct(4.2) > 100


class TestResolveCity:
    def test_known_city(self):
        lat, lon = _resolve_city("北京")
        assert lat == pytest.approx(39.90, abs=0.1)
        assert lon == pytest.approx(116.40, abs=0.1)

    def test_partial_match(self):
        lat, lon = _resolve_city("杭")
        assert lat == pytest.approx(30.27, abs=0.1)

    def test_none_returns_default(self):
        lat, lon = _resolve_city(None)
        assert lat == DEFAULT_LATITUDE
        assert lon == DEFAULT_LONGITUDE

    def test_unknown_city_returns_default(self):
        lat, lon = _resolve_city("阿特兰蒂斯")
        assert lat == DEFAULT_LATITUDE
        assert lon == DEFAULT_LONGITUDE


class TestGetWeather:
    @pytest.mark.asyncio
    async def test_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "current": {
                "temperature_2m": 15.3,
                "weather_code": 2,
            }
        }

        with patch("core.context.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=mock_resp)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            result = await get_weather(city="杭州")
            assert result["temp"] == 15
            assert result["weather_code"] == 2
            assert "15°C" in result["weather_str"]

    @pytest.mark.asyncio
    async def test_failure_returns_default(self):
        with patch("core.context.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(side_effect=Exception("timeout"))
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            result = await get_weather(city="杭州")
            assert result["temp"] == 0
            assert result["weather_str"] == "--°C"
