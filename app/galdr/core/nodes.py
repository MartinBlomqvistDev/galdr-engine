"""Graph: the narrative node structure.

A Scenario is a directed graph of NarrativeNode objects. Each node is a
scene — a place, a moment, a confrontation. The player can't leave the
graph; the AI can't invent new locations. Dramatic structure is guaranteed
by topology, not by prompt engineering.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from galdr.core.state import Ability, GameState


# ---------------------------------------------------------------------------
# Conditions — determine if a transition or action is available
# ---------------------------------------------------------------------------

class Condition(BaseModel):
    """A condition evaluated against GameState before exposing an action.

    Types (set via the "type" field in JSON):
    - flag:      check a narrative flag    {"type": "flag", "key": "met_elder", "value": true}
    - stat:      check an ability score    {"type": "stat", "ability": "charisma", "min": 14}
    - item:      check inventory           {"type": "item", "item_name": "nyckel"}
    - visited:   check location history   {"type": "visited", "location": "torget"}
    - turn:      check turn count          {"type": "turn", "min": 5}
    - lo_trust:  check Lo companion trust  {"type": "lo_trust", "min": 2}
    - pressure:  check current pressure    {"type": "pressure", "max": 6}
    - always:    unconditionally true
    """
    type: str
    key: str = ""
    value: Any = True
    ability: str = ""
    min: int | None = None
    max: int | None = None
    item_name: str = ""
    location: str = ""

    def evaluate(self, state: GameState) -> bool:
        match self.type:
            case "flag":
                return state.narrative_flags.check(self.key, self.value)
            case "stat":
                stat_val = getattr(state.character.stats, self.ability, 10)
                if self.min is not None and stat_val < self.min:
                    return False
                if self.max is not None and stat_val > self.max:
                    return False
                return True
            case "item":
                return any(i.name == self.item_name for i in state.character.inventory)
            case "visited":
                loc = state.world.locations.get(self.location)
                return loc is not None and loc.visited
            case "turn":
                if self.min is not None and state.turn_count < self.min:
                    return False
                return True
            case "lo_trust":
                trust = state.character.lo_trust
                if self.min is not None and trust < self.min:
                    return False
                if self.max is not None and trust > self.max:
                    return False
                return True
            case "pressure":
                p = state.character.pressure
                if self.min is not None and p < self.min:
                    return False
                if self.max is not None and p > self.max:
                    return False
                return True
            case "always":
                return True
            case _:
                return True


# ---------------------------------------------------------------------------
# Consequences — atomic state mutations triggered by actions
# ---------------------------------------------------------------------------

class Consequence(BaseModel):
    """A state mutation applied after an action succeeds or fails.

    Types:
    - set_flag:          write a narrative flag
    - add_item:          add to inventory
    - remove_item:       remove from inventory
    - modify_hp:         change HP by amount (positive or negative)
    - modify_pressure:   change physiological pressure 0-10
    - modify_lo_trust:   change Lo companion trust 0-5
    - set_weather:       update world weather string
    - set_time:          update time_of_day string
    - visit_location:    mark a location as visited
    """
    type: str
    key: str = ""
    value: Any = None
    amount: int = 0
    item_name: str = ""
    item_description: str = ""
    location: str = ""
    location_name: str = ""

    def apply(self, state: GameState) -> str:
        """Apply the consequence and return a human-readable description."""
        match self.type:
            case "set_flag":
                state.narrative_flags.set_flag(self.key, self.value)
                return f"Flagga '{self.key}' satt till {self.value}"
            case "add_item":
                from galdr.core.state import InventoryItem
                state.character.inventory.append(
                    InventoryItem(name=self.item_name, description=self.item_description)
                )
                return f"Du fick: {self.item_name}"
            case "remove_item":
                state.character.inventory = [
                    i for i in state.character.inventory if i.name != self.item_name
                ]
                return f"Du förlorade: {self.item_name}"
            case "modify_hp":
                state.character.hp = max(0, min(
                    state.character.max_hp,
                    state.character.hp + self.amount,
                ))
                verb = "fick" if self.amount > 0 else "förlorade"
                return f"Du {verb} {abs(self.amount)} HP (nu: {state.character.hp})"
            case "modify_pressure":
                state.character.pressure = max(0, min(10, state.character.pressure + self.amount))
                direction = "höjdes" if self.amount > 0 else "sänktes"
                return f"Pressure {direction} till {state.character.pressure}"
            case "modify_lo_trust":
                state.character.lo_trust = max(0, min(5, state.character.lo_trust + self.amount))
                direction = "stärktes" if self.amount > 0 else "försvagades"
                return f"Lo trust {direction} till {state.character.lo_trust}"
            case "set_weather":
                state.world.weather = str(self.value)
                return f"Vädret ändrades till {self.value}"
            case "set_time":
                state.world.time_of_day = str(self.value)
                return f"Tiden är nu {self.value}"
            case "visit_location":
                state.visit_location(self.location, self.location_name)
                return f"Du besökte {self.location_name or self.location}"
            case _:
                return ""


# ---------------------------------------------------------------------------
# Actions — what the player can do in a node
# ---------------------------------------------------------------------------

class NodeAction(BaseModel):
    """One player action available in a node."""
    id: str
    label: str        # short display text: "Öppna dörren", "Tala med älvan"
    description: str = ""  # longer description fed to the AI as stage direction

    # All conditions must pass for this action to appear
    conditions: list[Condition] = Field(default_factory=list)

    # Optional skill check
    skill_check: Ability | None = None
    dc: int = 10

    # Where does this lead?
    target_node: str = ""   # on success (or when no skill check)
    failure_node: str = ""  # on failure (skill check only)

    consequences: list[Consequence] = Field(default_factory=list)
    failure_consequences: list[Consequence] = Field(default_factory=list)

    def is_available(self, state: GameState) -> bool:
        return all(c.evaluate(state) for c in self.conditions)


# ---------------------------------------------------------------------------
# Biome context — ambient layer injected into the Director
# ---------------------------------------------------------------------------

class BiomeContext(BaseModel):
    """Environmental atmosphere for a node's location.

    Injected between scenario context and node-specific direction in the
    system prompt. Gives the LLM a sense of place and possible threats
    without prescribing specific events.

    Fields:
    - name:            display name ("Glass Crater Basin")
    - description:     one or two sentences injected verbatim into the prompt
    - pressure_base:   ambient pressure contribution from this environment
    - ambient_tags:    flavor words the narrator can draw from ("dust", "UV")
    - encounter_hints: possible threats/events the narrator can reference
    - lore_hints:      system truths the Director can reveal through narration
    - loot_hints:      functional item categories available in this zone
    """
    name: str
    description: str
    pressure_base: int = 0
    ambient_tags: list[str] = Field(default_factory=list)
    encounter_hints: list[str] = Field(default_factory=list)
    lore_hints: list[str] = Field(default_factory=list)
    loot_hints: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Voice parameters — per-node voice morphing
# ---------------------------------------------------------------------------

class VoiceParams(BaseModel):
    """Voice character and acoustic settings for a node."""
    character_name: str = "Narrator"
    pitch_shift: float = 0.0   # -1.0 (deep) to 1.0 (high)
    tempo: float = 1.0          # 0.5 (slow) to 2.0 (fast)
    emotion: str = "neutral"    # neutral, whisper, authoritative, warm, threatening, mysterious
    reverb: float = 0.0         # 0.0 (dry) to 1.0 (heavy echo)
    style: str = "narrator"     # narrator, character, whisper, dramatic


# ---------------------------------------------------------------------------
# Narrative node — the core of node direction
# ---------------------------------------------------------------------------

class NarrativeNode(BaseModel):
    """A single node in the narrative graph.

    Combines the Graph (structure, mechanics, branching) with the Director
    (prompt layers). The author controls what can happen; the AI controls
    how it sounds.
    """
    id: str
    title: str
    description: str  # internal note, never shown to the player

    # Director: instructions to the LLM for this scene
    system_prompt: str = ""    # how the AI should behave here
    opening_text: str = ""     # fixed text shown on node entry
    context_hint: str = ""     # extra context (genre, tone, mood)
    biome: BiomeContext | None = None  # ambient environment layer

    voice: VoiceParams = Field(default_factory=VoiceParams)
    actions: list[NodeAction] = Field(default_factory=list)

    # Auto-transition: skip directly to next node without player input
    auto_next: str | None = None
    auto_delay_seconds: float = 0.0

    # Geofencing (Ekokammaren GPS walk)
    geo_lat: float | None = None
    geo_lon: float | None = None
    geo_radius_meters: float = 50.0

    entry_conditions: list[Condition] = Field(default_factory=list)
    on_enter: list[Consequence] = Field(default_factory=list)  # run when node is first entered

    # Checkpoint — saves GameState to disk on entry (Neural Sync)
    is_checkpoint: bool = False

    # Guardrails
    forbidden_topics: list[str] = Field(default_factory=list)
    max_response_length: int = 300  # max words in AI response

    def get_available_actions(self, state: GameState) -> list[NodeAction]:
        return [a for a in self.actions if a.is_available(state)]

    def can_enter(self, state: GameState) -> bool:
        return all(c.evaluate(state) for c in self.entry_conditions)


# ---------------------------------------------------------------------------
# Scenario — a complete story
# ---------------------------------------------------------------------------

class Scenario(BaseModel):
    """A complete scenario: all nodes, start point, end points, global prompt."""
    id: str
    title: str
    description: str
    author: str = ""
    version: str = "1.0"

    nodes: dict[str, NarrativeNode] = Field(default_factory=dict)
    start_node: str = "start"
    end_nodes: list[str] = Field(default_factory=list)
    calibration_enabled: bool = False  # run Tribal Service stat generation before game starts (pre-loop)
    calibration_node: str | None = None  # node that triggers diegetic mid-game calibration

    global_system_prompt: str = ""  # applied to every node as the base layer
    default_voice: VoiceParams = Field(default_factory=VoiceParams)

    def get_node(self, node_id: str) -> NarrativeNode | None:
        return self.nodes.get(node_id)

    @classmethod
    def load_from_file(cls, path: str | Path) -> "Scenario":
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.model_validate(data)

    def save_to_file(self, path: str | Path) -> None:
        path = Path(path)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
