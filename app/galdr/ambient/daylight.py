"""Daylight phase via Sunrise-Sunset API and local system time.

API: https://sunrise-sunset.org/api -- free, no key required.
Without GPS, falls back to system clock (coarse but sufficient for atmosphere).
"""

from __future__ import annotations

import logging
import json
import asyncio
import urllib.request
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

_API_URL = "https://api.sunrise-sunset.org/json"
_TIMEOUT = 3.0
_GOLDEN = timedelta(minutes=45)


@dataclass
class DaylightData:
    phase: str   # "night" | "dawn" | "morning" | "midday" | "afternoon" | "dusk"
    hour: int


async def fetch_daylight(lat: float, lon: float) -> DaylightData:
    """Fetch sunrise/sunset and compute phase. Falls back to system clock on error."""
    now_utc = datetime.now(timezone.utc)
    sunrise = sunset = None

    try:
        params = urllib.parse.urlencode({"lat": round(lat, 4), "lng": round(lon, 4), "formatted": 0})
        url = f"{_API_URL}?{params}"

        loop = asyncio.get_event_loop()
        def _fetch():
            with urllib.request.urlopen(url, timeout=_TIMEOUT) as response:
                return json.loads(response.read().decode())

        data = await loop.run_in_executor(None, _fetch)

        if data.get("status") == "OK":
            r = data["results"]
            sunrise = datetime.fromisoformat(r["sunrise"].replace('Z', '+00:00'))
            sunset = datetime.fromisoformat(r["sunset"].replace('Z', '+00:00'))
    except Exception as e:
        logger.debug(f"Sunrise-Sunset API error: {e}")

    return DaylightData(
        phase=_phase(now_utc, sunrise, sunset),
        hour=datetime.now().hour,
    )


def fetch_daylight_local() -> DaylightData:
    """Phase from system time -- used when GPS is unavailable."""
    hour = datetime.now().hour
    return DaylightData(phase=_hour_phase(hour), hour=hour)


def _phase(now: datetime, sunrise: datetime | None, sunset: datetime | None) -> str:
    if sunrise is None or sunset is None:
        return _hour_phase(datetime.now().hour)
    if now < sunrise - _GOLDEN:
        return "night"
    if now < sunrise + _GOLDEN:
        return "dawn"
    if now < sunrise + timedelta(hours=4):
        return "morning"
    if now < sunset - timedelta(hours=2):
        return "midday"
    if now < sunset - _GOLDEN:
        return "afternoon"
    if now < sunset + _GOLDEN:
        return "dusk"
    return "night"


def _hour_phase(h: int) -> str:
    if h < 5:   return "night"
    if h < 7:   return "dawn"
    if h < 12:  return "morning"
    if h < 15:  return "midday"
    if h < 18:  return "afternoon"
    if h < 21:  return "dusk"
    return "night"


def describe_daylight(d: DaylightData) -> str:
    return {
        "night":     "it is night",
        "dawn":      "dawn is breaking",
        "morning":   "morning light, clear",
        "midday":    "the sun is high",
        "afternoon": "the afternoon is bright",
        "dusk":      "dusk is falling",
    }.get(d.phase, f"the hour is {d.hour:02d}")
