"""All game state in a single Pydantic model.

Every change in the game world — consequences, flags, inventory — goes
through here. Nothing is mutated directly in raw dicts.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# Ability scores (D&D 5e-inspired)
# ---------------------------------------------------------------------------

class Ability(str, Enum):
    STRENGTH = "strength"
    DEXTERITY = "dexterity"
    CONSTITUTION = "constitution"
    INTELLIGENCE = "intelligence"
    WISDOM = "wisdom"
    CHARISMA = "charisma"


class CharacterStats(BaseModel):
    """D&D 5e ability scores, capped at 1–20."""
    strength: int = Field(default=10, ge=1, le=20)
    dexterity: int = Field(default=10, ge=1, le=20)
    constitution: int = Field(default=10, ge=1, le=20)
    intelligence: int = Field(default=10, ge=1, le=20)
    wisdom: int = Field(default=10, ge=1, le=20)
    charisma: int = Field(default=10, ge=1, le=20)

    def modifier(self, ability: Ability) -> int:
        """Standard D&D modifier formula: (score - 10) // 2."""
        value = getattr(self, ability.value)
        return (value - 10) // 2


class InventoryItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    description: str = ""
    quantity: int = 1
    properties: dict[str, Any] = Field(default_factory=dict)


class Character(BaseModel):
    """Player character: stats, inventory, backstory."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Traveler"
    stats: CharacterStats = Field(default_factory=CharacterStats)
    hp: int = Field(default=20, ge=0)
    max_hp: int = 20
    level: int = 1
    inventory: list[InventoryItem] = Field(default_factory=list)
    personality_traits: list[str] = Field(default_factory=list)
    backstory: str = ""
    # Physiological stress — tracks cumulative heat, noise, fatigue, injury shock.
    # Range 0–10. Injected into the system prompt to shift narrator register.
    # 0-3: normal. 4-6: narrator harsher, shorter. 7-9: disorientation.
    # 10: forced node (blackout / collapse) — engine enforces this.
    pressure: int = Field(default=0, ge=0, le=10)
    # Lo companion trust — 0 = Lo has left or is hostile, 5 = full bond.
    # Default 3 (neutral). Falls to 0 triggers Lo's silent departure.
    lo_trust: int = Field(default=3, ge=0, le=5)


# ---------------------------------------------------------------------------
# World state
# ---------------------------------------------------------------------------

class LocationState(BaseModel):
    id: str
    name: str
    visited: bool = False
    visit_count: int = 0
    discovered_secrets: list[str] = Field(default_factory=list)
    npcs_met: list[str] = Field(default_factory=list)


class WorldState(BaseModel):
    locations: dict[str, LocationState] = Field(default_factory=dict)
    global_flags: dict[str, Any] = Field(default_factory=dict)
    quest_log: list[str] = Field(default_factory=list)
    time_of_day: str = "morning"
    weather: str = "clear"


# ---------------------------------------------------------------------------
# Dialog history
# ---------------------------------------------------------------------------

class DialogEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    speaker: str  # "player" | NPC name
    text: str
    node_id: str = ""
    emotion: str = "neutral"


# ---------------------------------------------------------------------------
# Narrative flags — branching logic lives here
# ---------------------------------------------------------------------------

class NarrativeFlags(BaseModel):
    flags: dict[str, Any] = Field(default_factory=dict)

    def set_flag(self, key: str, value: Any) -> None:
        self.flags[key] = value

    def get_flag(self, key: str, default: Any = None) -> Any:
        return self.flags.get(key, default)

    def check(self, key: str, expected: Any) -> bool:
        return self.flags.get(key) == expected


# ---------------------------------------------------------------------------
# Full session state
# ---------------------------------------------------------------------------

class GameState(BaseModel):
    """Complete session state, validated by Pydantic on every mutation.

    Nothing happens in the game without passing through this model —
    that's the point. Invalid state is caught at write time, not read time,
    and the whole thing serialises to JSON at any moment.
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    character: Character = Field(default_factory=Character)
    world: WorldState = Field(default_factory=WorldState)

    current_node_id: str = "start"
    narrative_flags: NarrativeFlags = Field(default_factory=NarrativeFlags)
    dialog_history: list[DialogEntry] = Field(default_factory=list)

    # GPS — only set when the player is physically on location
    player_lat: float | None = None
    player_lon: float | None = None

    turn_count: int = 0

    def record_dialog(self, speaker: str, text: str, node_id: str = "", emotion: str = "neutral"):
        self.dialog_history.append(
            DialogEntry(speaker=speaker, text=text, node_id=node_id, emotion=emotion)
        )
        self.updated_at = datetime.now()
        self.turn_count += 1

    def visit_location(self, location_id: str, location_name: str = ""):
        if location_id not in self.world.locations:
            self.world.locations[location_id] = LocationState(
                id=location_id, name=location_name or location_id
            )
        loc = self.world.locations[location_id]
        loc.visited = True
        loc.visit_count += 1

    def get_recent_context(self, n: int = 10) -> list[DialogEntry]:
        """Last N dialog entries — fed into LLM context window."""
        return self.dialog_history[-n:]
