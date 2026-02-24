"""Väder från Open-Meteo. Gratis, ingen nyckel, GDPR-ok, EU-servrar."""

from __future__ import annotations

import logging
import json
import asyncio
import urllib.request
import urllib.parse
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# WMO-koder → svenska. Källa: https://open-meteo.com/en/docs#weathervariables
_WMO_CODES: dict[int, str] = {
    0: "klar himmel",
    1: "mestadels klart",
    2: "delvis molnigt",
    3: "mulet",
    45: "dimma",
    48: "rimfrost",
    51: "lätt duggregn",
    53: "måttligt duggregn",
    55: "kraftigt duggregn",
    61: "lätt regn",
    63: "måttligt regn",
    65: "kraftigt regn",
    71: "lätt snöfall",
    73: "måttligt snöfall",
    75: "kraftigt snöfall",
    77: "snöhagel",
    80: "lätta regnskurar",
    81: "måttliga regnskurar",
    82: "kraftiga regnskurar",
    85: "lätta snöbyar",
    86: "kraftiga snöbyar",
    95: "åskväder",
    96: "åskväder med hagel",
    99: "kraftigt åskväder med hagel",
}

_API_URL = "https://api.open-meteo.com/v1/forecast"
_TIMEOUT = 3.0  # narrativ latens > väderdata


@dataclass
class WeatherData:
    condition: str
    temperature_c: float
    wind_ms: float
    weather_code: int


async def fetch_weather(lat: float, lon: float) -> WeatherData | None:
    """Hämta aktuellt väder. Returnerar None vid timeout eller nätverksfel."""
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
            condition=_WMO_CODES.get(code, "okänt väder"),
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
        wind = f", blåsigt ({w.wind_ms:.0f} m/s)"
    elif w.wind_ms >= 5:
        wind = ", lätt vind"
    else:
        wind = ""
    return f"{w.condition}, {temp}{wind}"
