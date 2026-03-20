"""
Unit tests for context helpers (battery, city, weather).
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from core.context import calc_battery_pct, _resolve_city, get_weather, search_locations, _generate_weather_advice
from core.config import DEFAULT_LATITUDE, DEFAULT_LONGITUDE


class TestCalcBatteryPct:
    def test_full_charge(self):
        assert calc_battery_pct(3.3) == 100

    def test_half_charge(self):
        assert calc_battery_pct(1.65) == 50

    def test_empty(self):
        assert calc_battery_pct(0.0) == 0

    def test_over_voltage(self):
        assert calc_battery_pct(4.2) == 100


class TestResolveCity:
    def test_known_city(self):
        lat, lon = _resolve_city("北京")
        assert lat == pytest.approx(39.90, abs=0.1)
        assert lon == pytest.approx(116.40, abs=0.1)

    def test_normalized_match(self):
        lat, lon = _resolve_city("杭州市")
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
    async def test_prefers_coordinates_when_provided(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "current": {
                "temperature_2m": 21.1,
                "weather_code": 1,
            }
        }

        with patch("core.context.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get = AsyncMock(return_value=mock_resp)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            result = await get_weather(city="杭州", lat=27.66, lon=120.56)
            assert result["temp"] == 21
            called_params = instance.get.await_args.kwargs["params"]
            assert called_params["latitude"] == pytest.approx(27.66)
            assert called_params["longitude"] == pytest.approx(120.56)

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


class TestSearchLocations:
    @pytest.mark.asyncio
    async def test_search_locations_prefers_administrative_match_from_nominatim(self):
        async def _mock_nominatim(query, *, count=8, country_codes="cn"):
            if query == "平阳":
                return [
                    {
                        "name": "平阳",
                        "lat": "27.575",
                        "lon": "120.565",
                        "display_name": "平阳, 车站大道, 平阳县, 温州市, 浙江省, 中国",
                        "category": "railway",
                        "type": "station",
                        "addresstype": "station",
                        "importance": 0.65,
                        "place_rank": 30,
                        "address": {
                            "county": "平阳县",
                            "state_district": "温州市",
                            "state": "浙江省",
                            "country": "中国",
                            "country_code": "cn",
                        },
                    }
                ]
            if query == "平阳县":
                return [
                    {
                        "name": "平阳县",
                        "lat": "27.662",
                        "lon": "120.565",
                        "display_name": "平阳县, 温州市, 浙江省, 中国",
                        "category": "boundary",
                        "type": "administrative",
                        "addresstype": "county",
                        "importance": 0.72,
                        "place_rank": 18,
                        "address": {
                            "county": "平阳县",
                            "state_district": "温州市",
                            "state": "浙江省",
                            "country": "中国",
                            "country_code": "cn",
                        },
                    }
                ]
            return []

        with (
            patch("core.context._fetch_nominatim", new=AsyncMock(side_effect=_mock_nominatim)),
            patch("core.context._fetch_geocoding", new_callable=AsyncMock) as mock_fetch,
        ):
            mock_fetch.return_value = {"results": []}
            items = await search_locations("平阳", limit=5)

            assert items
            assert items[0]["city"] == "平阳县"
            assert "浙江省" in items[0]["display_name"]
            assert "温州市" in items[0]["display_name"]

    @pytest.mark.asyncio
    async def test_search_locations_falls_back_to_open_meteo(self):
        with (
            patch("core.context._fetch_nominatim", new_callable=AsyncMock) as mock_nominatim,
            patch("core.context._fetch_geocoding", new_callable=AsyncMock) as mock_fetch,
        ):
            mock_nominatim.return_value = []
            mock_fetch.return_value = {
                "results": [
                    {
                        "name": "平阳县",
                        "admin1": "浙江省",
                        "country": "中国",
                        "latitude": 27.66,
                        "longitude": 120.56,
                        "timezone": "Asia/Shanghai",
                        "population": 100,
                    }
                ]
            }

            items = await search_locations("平阳", limit=5)

            assert items
            assert items[0]["city"] == "平阳县"

    @pytest.mark.asyncio
    async def test_search_locations_supports_global_results(self):
        async def _mock_nominatim(query, *, count=8, country_codes="cn"):
            if country_codes == "cn":
                return []
            return []

        with (
            patch("core.context._fetch_nominatim", new=AsyncMock(side_effect=_mock_nominatim)),
            patch("core.context._fetch_geocoding", new_callable=AsyncMock) as mock_fetch,
        ):
            mock_fetch.return_value = {
                "results": [
                    {
                        "name": "巴黎",
                        "admin1": "Île-de-France",
                        "country": "France",
                        "latitude": 48.85341,
                        "longitude": 2.3488,
                        "timezone": "Europe/Paris",
                        "population": 2138551,
                        "admin2": "Paris",
                        "admin3": "Paris",
                    }
                ]
            }
            items = await search_locations("Paris", limit=5, scope="global")

            assert items
            assert items[0]["city"] == "巴黎"
            assert items[0]["country"] == "France"
            assert items[0]["timezone"] == "Europe/Paris"

    @pytest.mark.asyncio
    async def test_search_locations_filters_irrelevant_candidates(self):
        async def _mock_nominatim(query, *, count=8, country_codes="cn"):
            if query == "杭州":
                return [
                    {
                        "name": "杭州市",
                        "lat": "30.274084",
                        "lon": "120.15507",
                        "display_name": "杭州市, 浙江省, 中国",
                        "category": "boundary",
                        "type": "administrative",
                        "addresstype": "city",
                        "importance": 0.82,
                        "place_rank": 16,
                        "address": {
                            "city": "杭州市",
                            "state": "浙江省",
                            "country": "中国",
                            "country_code": "cn",
                        },
                    },
                    {
                        "name": "杭州萧山国际机场",
                        "lat": "30.2368729",
                        "lon": "120.4291244",
                        "display_name": "杭州萧山国际机场, 萧山区, 浙江省, 中国",
                        "category": "aeroway",
                        "type": "aerodrome",
                        "addresstype": "aerodrome",
                        "importance": 0.78,
                        "place_rank": 18,
                        "address": {
                            "county": "萧山区",
                            "state": "浙江省",
                            "country": "中国",
                            "country_code": "cn",
                        },
                    },
                ]
            return []

        with (
            patch("core.context._fetch_nominatim", new=AsyncMock(side_effect=_mock_nominatim)),
            patch("core.context._fetch_geocoding", new_callable=AsyncMock) as mock_fetch,
        ):
            mock_fetch.return_value = {"results": []}
            items = await search_locations("杭州", limit=5)

            assert items
            assert items[0]["city"] == "杭州市"
            assert all("国际机场" not in item["display_name"] for item in items)

    @pytest.mark.asyncio
    async def test_search_locations_dedupes_same_display_name(self):
        async def _mock_nominatim(query, *, count=8, country_codes="cn"):
            if query == "北京":
                return [
                    {
                        "name": "北京市",
                        "lat": "39.9057136",
                        "lon": "116.3912972",
                        "display_name": "北京市, 中国",
                        "category": "boundary",
                        "type": "administrative",
                        "addresstype": "city",
                        "importance": 0.91,
                        "place_rank": 16,
                        "address": {
                            "city": "北京市",
                            "country": "中国",
                            "country_code": "cn",
                        },
                    },
                    {
                        "name": "北京市",
                        "lat": "40.190632",
                        "lon": "116.412144",
                        "display_name": "北京市, 北京市, 中国",
                        "category": "boundary",
                        "type": "administrative",
                        "addresstype": "province",
                        "importance": 0.83,
                        "place_rank": 12,
                        "address": {
                            "state": "北京市",
                            "city": "北京市",
                            "country": "中国",
                            "country_code": "cn",
                        },
                    },
                ]
            return []

        with (
            patch("core.context._fetch_nominatim", new=AsyncMock(side_effect=_mock_nominatim)),
            patch("core.context._fetch_geocoding", new_callable=AsyncMock) as mock_fetch,
        ):
            mock_fetch.return_value = {"results": []}
            items = await search_locations("北京", limit=8)

            display_names = [item["display_name"] for item in items]
            assert display_names.count("北京市 · 中国") == 1


class TestWeatherAdvice:
    def test_generates_rain_advice_without_llm(self):
        advice = _generate_weather_advice(
            today_desc="小雨",
            today_low=18,
            today_high=25,
            today_humidity=88,
            today_wind_level="3级",
        )

        assert "雨" in advice

    def test_generates_cold_morning_advice_without_llm(self):
        advice = _generate_weather_advice(
            today_desc="晴",
            today_low=3,
            today_high=11,
            today_humidity=45,
            today_wind_level="2级",
        )

        assert any(keyword in advice for keyword in ("保暖", "外套", "添衣"))
