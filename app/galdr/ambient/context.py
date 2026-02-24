"""Slår ihop ambient-data till en promptsträng.

Engine kallar build_ambient_context() – behöver inte veta vilka
API:er som lyckades. Tom sträng = inget att injicera.
"""

from __future__ import annotations

import asyncio
import logging

from galdr.ambient.daylight import fetch_daylight, fetch_daylight_local, describe_daylight
from galdr.ambient.weather import fetch_weather, describe_weather

logger = logging.getLogger(__name__)


async def build_ambient_context(lat: float | None, lon: float | None) -> str:
    """Hämta väder + dagsljus parallellt, returnera som stage direction.

    Utan GPS: hoppar väder, tar dagsljus från klockan.
    Sträng injiceras i prompten som atmosfärisk bakgrund – inte som
    fakta spelaren kan fråga om.
    """
    if lat is not None and lon is not None:
        weather_data, daylight_data = await asyncio.gather(
            fetch_weather(lat, lon),
            fetch_daylight(lat, lon),
        )
    else:
        weather_data = None
        daylight_data = fetch_daylight_local()

    parts: list[str] = []
    if daylight_data:
        parts.append(describe_daylight(daylight_data))
    if weather_data:
        parts.append(describe_weather(weather_data))

    if not parts:
        return ""
    return f"[Ambient: {', '.join(parts)}]"
