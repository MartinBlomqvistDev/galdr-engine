"""D&D 5e mechanics: dice rolls, skill checks, DC resolution.

Rolls happen server-side so sessions are fully reproducible — we can log
and replay exactly what happened, which matters for debugging and auditing.
"""

from __future__ import annotations

import random
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from galdr.core.state import Ability, GameState


class DifficultyClass(int, Enum):
    """Standard DC tiers from the 5e SRD."""
    VERY_EASY = 5
    EASY = 10
    MEDIUM = 15
    HARD = 20
    VERY_HARD = 25
    NEARLY_IMPOSSIBLE = 30


class DiceType(str, Enum):
    D4 = "d4"
    D6 = "d6"
    D8 = "d8"
    D10 = "d10"
    D12 = "d12"
    D20 = "d20"
    D100 = "d100"


DICE_SIDES = {
    DiceType.D4: 4,
    DiceType.D6: 6,
    DiceType.D8: 8,
    DiceType.D10: 10,
    DiceType.D12: 12,
    DiceType.D20: 20,
    DiceType.D100: 100,
}


class DiceRoll(BaseModel):
    dice_type: DiceType
    count: int = 1
    rolls: list[int] = Field(default_factory=list)
    modifier: int = 0
    total: int = 0
    natural_20: bool = False
    natural_1: bool = False


class SkillCheckResult(BaseModel):
    ability: Ability
    dc: int
    roll: DiceRoll
    ability_modifier: int = 0
    total: int = 0
    success: bool = False
    critical_success: bool = False
    critical_failure: bool = False
    margin: int = 0  # how far above or below DC
    narrative_quality: str = "neutral"  # spectacular | solid | narrow | failure | disaster


def roll_dice(dice_type: DiceType = DiceType.D20, count: int = 1, modifier: int = 0) -> DiceRoll:
    """Roll dice server-side for consistency."""
    sides = DICE_SIDES[dice_type]
    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + modifier

    return DiceRoll(
        dice_type=dice_type,
        count=count,
        rolls=rolls,
        modifier=modifier,
        total=total,
        natural_20=(dice_type == DiceType.D20 and count == 1 and rolls[0] == 20),
        natural_1=(dice_type == DiceType.D20 and count == 1 and rolls[0] == 1),
    )


def skill_check(state: GameState, ability: Ability, dc: int) -> SkillCheckResult:
    """d20 + ability modifier vs DC, with five narrative quality tiers.

    The quality tier is what actually goes into the LLM prompt — the AI
    narrates an outcome, not a raw number. Nat 20 and nat 1 override the
    margin calculation entirely; the dice gods trump modifiers.

    Tiers:
    - spectacular: nat 20 OR 10+ above DC
    - solid:       5–9 above DC
    - narrow:      0–4 above DC (barely made it)
    - failure:     below DC
    - disaster:    nat 1 OR 10+ below DC
    """
    mod = state.character.stats.modifier(ability)
    die = roll_dice(DiceType.D20, modifier=mod)
    margin = die.total - dc

    if die.natural_20:
        quality, success = "spectacular", True
    elif die.natural_1:
        quality, success = "disaster", False
    elif margin >= 10:
        quality, success = "spectacular", True
    elif margin >= 5:
        quality, success = "solid", True
    elif margin >= 0:
        quality, success = "narrow", True
    elif margin >= -10:
        quality, success = "failure", False
    else:
        quality, success = "disaster", False

    return SkillCheckResult(
        ability=ability,
        dc=dc,
        roll=die,
        ability_modifier=mod,
        total=die.total,
        success=success,
        critical_success=die.natural_20,
        critical_failure=die.natural_1,
        margin=margin,
        narrative_quality=quality,
    )


def damage_roll(dice_type: DiceType, count: int = 1, modifier: int = 0) -> DiceRoll:
    """Damage roll for combat."""
    return roll_dice(dice_type, count, modifier)


def contested_check(
    state: GameState,
    player_ability: Ability,
    opponent_modifier: int,
) -> dict[str, Any]:
    """Player roll vs NPC roll — both sides use the same dice function."""
    player_roll = roll_dice(DiceType.D20, modifier=state.character.stats.modifier(player_ability))
    opponent_roll = roll_dice(DiceType.D20, modifier=opponent_modifier)

    return {
        "player_roll": player_roll,
        "opponent_roll": opponent_roll,
        "player_wins": player_roll.total >= opponent_roll.total,
        "margin": player_roll.total - opponent_roll.total,
    }
