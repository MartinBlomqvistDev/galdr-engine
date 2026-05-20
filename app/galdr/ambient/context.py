"""Assembles ambient data into a prompt string.

Engine calls build_ambient_context() -- does not need to know which APIs succeeded.
Empty string means nothing to inject.
"""

from __future__ import annotations

import asyncio
import logging

from galdr.ambient.daylight import fetch_daylight, fetch_daylight_local, describe_daylight
from galdr.ambient.weather import fetch_weather, describe_weather

logger = logging.getLogger(__name__)


async def build_ambient_context(lat: float | None, lon: float | None) -> str:
    """Fetch weather and daylight in parallel, return as a stage direction.

    Without GPS: skips weather, takes daylight from system clock.
    String is injected into the prompt as atmospheric background -- not as
    facts the player can ask about.
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
