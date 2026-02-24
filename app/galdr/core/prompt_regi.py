"""Prompt-regi: assembles the LLM system prompt for each node.

The director writes instructions ("the character is frightened and hiding it"),
not a script. The AI fills in the words. This module stacks those instruction
layers into a single prompt in a deliberate order: broadest constraints first,
most specific last. Later instructions narrow the space without contradicting
earlier ones.
"""

from __future__ import annotations

from galdr.core.dice import SkillCheckResult
from galdr.core.nodes import NarrativeNode, Scenario
from galdr.core.state import GameState


def build_system_prompt(
    scenario: Scenario,
    node: NarrativeNode,
    state: GameState,
) -> str:
    """Stack all instruction layers into one system prompt.

    Order matters — it's a funnel:
    1. Global character identity (who GALDR is, what it never does)
    2. Scenario context (genre, world, tone)
    3. Node-specific direction (this scene's emotional register)
    4. Voice character (how to speak)
    5. Player context (inventory, HP — the AI needs to know the stakes)
    6. Available actions (implicit stage directions toward valid choices)
    7. Forbidden topics (per-node guardrails)
    8. Hard rules (response length, language, never break character)
    """
    parts: list[str] = []

    # Layer 1: global identity
    parts.append(
        "Du är GALDR – en AI-berättare för interaktiv storytelling. "
        "Du agerar karaktärer med röst, tempo och undertext. "
        "Du är INTE en chatbot. Du är en spelledare som driver berättelsen framåt."
    )

    # Layer 2: scenario context
    if scenario.global_system_prompt:
        parts.append(f"\n## Scenario: {scenario.title}\n{scenario.global_system_prompt}")

    # Layer 3: node-specific direction (prompt-regi)
    if node.system_prompt:
        parts.append(f"\n## Aktuell scen: {node.title}\n{node.system_prompt}")

    if node.context_hint:
        parts.append(f"\nTonalitet/Genre: {node.context_hint}")

    # Layer 4: voice character
    voice = node.voice
    parts.append(
        f"\n## Röstgestaltning"
        f"\nDu talar som: {voice.character_name}"
        f"\nKänsla: {voice.emotion}"
        f"\nStil: {voice.style}"
    )

    # Layer 5: player context — what the AI needs to understand the stakes
    char = state.character
    parts.append(
        f"\n## Spelarkaraktär"
        f"\nNamn: {char.name}"
        f"\nHP: {char.hp}/{char.max_hp}"
        f"\nInventory: {', '.join(i.name for i in char.inventory) or 'Tom'}"
    )

    if state.world.time_of_day or state.world.weather:
        parts.append(
            f"\nTid: {state.world.time_of_day}, Väder: {state.world.weather}"
        )

    # Layer 6: available actions as stage directions (not a menu)
    available = node.get_available_actions(state)
    if available:
        action_list = "\n".join(f"- {a.label}: {a.description}" for a in available)
        parts.append(
            f"\n## Handlingar spelaren kan välja"
            f"\n{action_list}"
            f"\n\nLed spelaren mot dessa val utan att tvinga dem. "
            f"Om spelaren gör något oväntat, improvisera inom ramarna."
        )

    # Layer 7: per-node forbidden topics
    if node.forbidden_topics:
        topics = ", ".join(node.forbidden_topics)
        parts.append(
            f"\n## FÖRBJUDET – Tala ALDRIG om:"
            f"\n{topics}"
            f"\nOm spelaren frågar om dessa ämnen, styr tillbaka till berättelsen."
        )

    # Layer 8: hard rules (always last)
    parts.append(
        f"\n## Regler"
        f"\n- Svara på svenska"
        f"\n- Max {node.max_response_length} ord per svar"
        f"\n- Driv berättelsen framåt, var aldrig passiv"
        f"\n- Avsluta med en implicit eller explicit fråga/uppmaning"
        f"\n- Du får INTE bryta karaktär"
    )

    return "\n".join(parts)


def build_dice_narrative(result: SkillCheckResult) -> str:
    """Translate a mechanical dice result into directorial language for the LLM.

    The AI receives quality tiers, not raw numbers. "You barely made it"
    is more useful than "you rolled a 12 against DC 11". The prompt still
    includes the numbers for grounding, but the tier carries the dramatic weight.
    """
    # Swedish ability names for the in-prompt stage direction
    ability_sv = {
        "strength": "styrka",
        "dexterity": "smidighet",
        "constitution": "uthållighet",
        "intelligence": "intelligens",
        "wisdom": "visdom",
        "charisma": "karisma",
    }
    ability_name = ability_sv.get(result.ability.value, result.ability.value)

    match result.narrative_quality:
        case "spectacular":
            if result.critical_success:
                return (
                    f"[KRITISK FRAMGÅNG! Nat 20 på {ability_name}-check mot DC {result.dc}. "
                    f"Totalt: {result.total}. Beskriv ett ENASTÅENDE resultat – "
                    f"det bästa tänkbara utfallet. Spelaren lyckas på ett sätt som "
                    f"överträffar alla förväntningar.]"
                )
            return (
                f"[SPEKTAKULÄR FRAMGÅNG! {ability_name.capitalize()}-check: "
                f"{result.total} mot DC {result.dc} (+{result.margin}). "
                f"Beskriv ett imponerande resultat.]"
            )
        case "solid":
            return (
                f"[FRAMGÅNG. {ability_name.capitalize()}-check: "
                f"{result.total} mot DC {result.dc}. "
                f"Beskriv ett kompetent, självsäkert resultat.]"
            )
        case "narrow":
            return (
                f"[PRECIS KLARAT! {ability_name.capitalize()}-check: "
                f"{result.total} mot DC {result.dc} (med {result.margin} marginal). "
                f"Beskriv hur det nästan gick fel men spelaren klarade det i sista stund.]"
            )
        case "failure":
            return (
                f"[MISSLYCKANDE. {ability_name.capitalize()}-check: "
                f"{result.total} mot DC {result.dc} ({result.margin}). "
                f"Beskriv ett trovärdigt misslyckande – inte pinsamt, "
                f"men uppgiften var för svår just nu.]"
            )
        case "disaster":
            if result.critical_failure:
                return (
                    f"[KRITISKT MISSLYCKANDE! Nat 1 på {ability_name}-check. "
                    f"Beskriv ett dramatiskt, nästan komiskt misslyckande. "
                    f"Något går VÄLDIGT fel – men på ett sätt som driver berättelsen framåt.]"
                )
            return (
                f"[KATASTROFALT MISSLYCKANDE. {ability_name.capitalize()}-check: "
                f"{result.total} mot DC {result.dc} ({result.margin}). "
                f"Beskriv ett allvarligt misslyckande med konsekvenser.]"
            )
        case _:
            return f"[{ability_name.capitalize()}-check: {result.total} mot DC {result.dc}]"


def build_context_messages(state: GameState, max_history: int = 10) -> list[dict[str, str]]:
    """Convert dialog history to LLM message format."""
    messages: list[dict[str, str]] = []
    for entry in state.get_recent_context(max_history):
        if entry.speaker == "player":
            messages.append({"role": "user", "content": entry.text})
        else:
            messages.append({"role": "assistant", "content": entry.text})
    return messages
