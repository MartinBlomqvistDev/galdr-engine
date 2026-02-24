"""Dagsljusfas via Sunrise-Sunset API och lokal systemtid.

API: https://sunrise-sunset.org/api – gratis, ingen nyckel.
Utan GPS används bara klockan, vilket är grovt men räcker för atmosfär.
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
_GOLDEN = timedelta(minutes=45)  # gryning/skymning-fönster


@dataclass
class DaylightData:
    phase: str   # "natt" | "gryning" | "förmiddag" | "middag" | "eftermiddag" | "skymning"
    hour: int


async def fetch_daylight(lat: float, lon: float) -> DaylightData:
    """Hämta soluppgång/nedgång och räkna ut fas. Faller tillbaka på klockan vid fel."""
    now_utc = datetime.now(timezone.utc)
    sunrise = sunset = None

    try:
        # Using built-in urllib for zero dependencies in the showcase engine
        params = urllib.parse.urlencode({"lat": round(lat, 4), "lng": round(lon, 4), "formatted": 0})
        url = f"{_API_URL}?{params}"
        
        # Run the blocking urllib call in a thread pool to keep it async-friendly
        loop = asyncio.get_event_loop()
        def _fetch():
            with urllib.request.urlopen(url, timeout=_TIMEOUT) as response:
                return json.loads(response.read().decode())
        
        data = await loop.run_in_executor(None, _fetch)
        
        if data.get("status") == "OK":
            r = data["results"]
            # Handle possible varied ISO formats
            sunrise = datetime.fromisoformat(r["sunrise"].replace('Z', '+00:00'))
            sunset = datetime.fromisoformat(r["sunset"].replace('Z', '+00:00'))
    except Exception as e:
        logger.debug(f"Sunrise-Sunset API error: {e}")

    return DaylightData(
        phase=_phase(now_utc, sunrise, sunset),
        hour=datetime.now().hour,
    )


def fetch_daylight_local() -> DaylightData:
    """Fas från systemtid – används när GPS saknas."""
    hour = datetime.now().hour
    return DaylightData(phase=_hour_phase(hour), hour=hour)


def _phase(now: datetime, sunrise: datetime | None, sunset: datetime | None) -> str:
    if sunrise is None or sunset is None:
        return _hour_phase(datetime.now().hour)
    if now < sunrise - _GOLDEN:
        return "natt"
    if now < sunrise + _GOLDEN:
        return "gryning"
    if now < sunrise + timedelta(hours=4):
        return "förmiddag"
    if now < sunset - timedelta(hours=2):
        return "middag"
    if now < sunset - _GOLDEN:
        return "eftermiddag"
    if now < sunset + _GOLDEN:
        return "skymning"
    return "natt"


def _hour_phase(h: int) -> str:
    if h < 5:   return "natt"
    if h < 7:   return "gryning"
    if h < 12:  return "förmiddag"
    if h < 15:  return "middag"
    if h < 18:  return "eftermiddag"
    if h < 21:  return "skymning"
    return "natt"


def describe_daylight(d: DaylightData) -> str:
    return {
        "natt":        "det är natt",
        "gryning":     "gryningen breder ut sig",
        "förmiddag":   "förmiddagsljuset är klart",
        "middag":      "solen står högt",
        "eftermiddag": "eftermiddagen är ljus",
        "skymning":    "skymningen faller",
    }.get(d.phase, f"klockan är {d.hour:02d}")
