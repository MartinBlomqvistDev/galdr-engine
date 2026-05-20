"""Tribal Service calibration — voice-driven stat generation for CALLOUSED.

The player answers 4 thematic questions. An LLM interprets the answers and
assigns the D&D 5e standard array (15, 14, 13, 12, 10, 8) to the six abilities.
Returns a CharacterStats object ready to slot into GameState.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable

from galdr.core.state import CharacterStats
from galdr.services.interfaces import LLMService

logger = logging.getLogger(__name__)

_QUESTIONS = [
    "OPERATOR DESIGNATION. State sector. State assigned function.",
    "LOAD CAPACITY. State maximum recorded output. Kilograms or equivalent.",
    "COMMAND INDEX. State number of personnel under direct control.",
    "UNAUTHORIZED MEMORY. Declare any knowledge of surface conditions or external systems absent from your official briefings.",
]

_SYSTEM_PROMPT = """\
You are a 50,000-year-old facility registry system. You ran a Maintenance Caste intake protocol \
on an unregistered surface descendant. The system asked questions designed for MC workers. \
The respondent answered in surface-dweller terms — no sector designations, no formal ranks, \
no briefing references. Map their answers to D&D 5e ability scores regardless.

Rules:
- Use the standard array exactly: 15, 14, 13, 12, 10, 8. Each value used once.
- Abilities: strength, dexterity, constitution, intelligence, wisdom, charisma.
- Map what the respondent described to the stat that best fits:
    physical labor, carrying, fighting, building → strength
    speed, precision, stealth, threading gaps → dexterity
    endurance, illness survived, outlasting others → constitution
    technical knowledge, reading, problem-solving → intelligence
    pattern recognition, patience, reading situations → wisdom
    leadership, persuasion, commanding a room, trade → charisma
- Weight toward what they actually said, not what sounds impressive.
- Return ONLY valid JSON with exactly these six keys. No explanation.

Example:
{"strength": 15, "dexterity": 10, "constitution": 14, "intelligence": 8, "wisdom": 12, "charisma": 13}
"""

_STAT_KEYS = {"strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"}
_STANDARD_ARRAY = {15, 14, 13, 12, 10, 8}


async def run_calibration(
    llm: LLMService,
    speak: Callable[[str], Awaitable[None]],
    listen: Callable[[], Awaitable[str]],
) -> CharacterStats:
    """Ask Tribal Service questions and return calibrated CharacterStats."""
    answers: list[str] = []

    for question in _QUESTIONS:
        await speak(question)
        answer = await listen()
        stripped = answer.strip()
        if stripped:
            answers.append(stripped)
            logger.info("[CALIBRATION] Q: %s... | A: %s", question[:40], stripped[:60])
        else:
            logger.warning("[CALIBRATION] No answer for question: %s", question[:40])

    if not answers:
        logger.warning("[CALIBRATION] No answers captured — using default stats")
        return CharacterStats()

    combined = "\n".join(f"- {a}" for a in answers)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"Tribal Service answers:\n{combined}"},
    ]

    try:
        raw = await llm.generate_text(messages=messages, max_tokens=80, temperature=0.2)
        match = re.search(r"\{[^}]+\}", raw, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON in LLM response: {raw!r}")

        data = json.loads(match.group())
        if not _STAT_KEYS.issubset(data.keys()):
            raise ValueError(f"Missing stat keys in response: {data}")

        parsed = {k: int(data[k]) for k in _STAT_KEYS}
        values = set(parsed.values())
        if values != _STANDARD_ARRAY:
            logger.warning("[CALIBRATION] LLM did not return standard array (%s) — clamping", values)
            parsed = _enforce_standard_array(parsed)

        stats = CharacterStats(**parsed)
        logger.info("[CALIBRATION] Final stats: %s", stats.model_dump())
        return stats

    except Exception as e:
        logger.error("[CALIBRATION] Stat parsing failed (%s) — using defaults", e)
        return CharacterStats()


def _enforce_standard_array(parsed: dict[str, int]) -> dict[str, int]:
    """Sort parsed values by descending score, then re-map to standard array in the same rank order."""
    standard = sorted(_STANDARD_ARRAY, reverse=True)
    ranked = sorted(parsed.items(), key=lambda x: x[1], reverse=True)
    return {k: standard[i] for i, (k, _) in enumerate(ranked)}
