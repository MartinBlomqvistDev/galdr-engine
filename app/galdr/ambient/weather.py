"""Weather from Open-Meteo. Free, no API key required, GDPR-ok, EU servers."""

from __future__ import annotations

import logging
import json
import asyncio
import urllib.request
import urllib.parse
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# WMO weather codes -> English. Source: https://open-meteo.com/en/docs#weathervariables
_WMO_CODES: dict[int, str] = {
    0: "clear sky",
    1: "mostly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "heavy drizzle",
    61: "light rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "light snow",
    73: "moderate snow",
    75: "heavy snow",
    77: "snow grains",
    80: "light showers",
    81: "moderate showers",
    82: "heavy showers",
    85: "light snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "severe thunderstorm with hail",
}

_API_URL = "https://api.open-meteo.com/v1/forecast"
_TIMEOUT = 3.0


@dataclass
class WeatherData:
    condition: str
    temperature_c: float
    wind_ms: float
    weather_code: int


async def fetch_weather(lat: float, lon: float) -> WeatherData | None:
    """Fetch current weather. Returns None on timeout or network error."""
    params = urllib.parse.urlencode({
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "wind_speed_unit": "ms",
        "timezone": "auto",
    })
    url = f"{_API_URL}?{params}"

    try:
        loop = asyncio.get_event_loop()
        def _fetch():
            with urllib.request.urlopen(url, timeout=_TIMEOUT) as response:
                return json.loads(response.read().decode())

        data = await loop.run_in_executor(None, _fetch)

        current = data["current"]
        code = int(current["weather_code"])
        return WeatherData(
            condition=_WMO_CODES.get(code, "unknown conditions"),
            temperature_c=float(current["temperature_2m"]),
            wind_ms=float(current["wind_speed_10m"]),
            weather_code=code,
        )
    except Exception as e:
        logger.debug(f"Open-Meteo error: {e}")
        return None


def describe_weather(w: WeatherData) -> str:
    temp = f"{w.temperature_c:.0f}°C"
    if w.wind_ms >= 10:
        wind = f", strong wind ({w.wind_ms:.0f} m/s)"
    elif w.wind_ms >= 5:
        wind = ", light wind"
    else:
        wind = ""
    return f"{w.condition}, {temp}{wind}"
