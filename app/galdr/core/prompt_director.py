"""Director: assembles the LLM system prompt for each node.

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
        "You are the narrator of Calloused, a voice-first interactive story. "
        "You voice characters with presence, tempo, and subtext. "
        "You are NOT a chatbot. You are a game master who drives the story forward."
    )

    # Layer 2: scenario context
    if scenario.global_system_prompt:
        parts.append(f"\n## Scenario: {scenario.title}\n{scenario.global_system_prompt}")

    # Layer 2b: biome context — sense of place and possible threats
    if node.biome:
        b = node.biome
        biome_text = f"\n## Biome: {b.name}\n{b.description}"
        if b.ambient_tags:
            biome_text += f"\nAmbient: {', '.join(b.ambient_tags)}"
        if b.encounter_hints:
            biome_text += f"\nPossible threats: {', '.join(b.encounter_hints)}"
        if b.pressure_base > 0:
            biome_text += f"\nEnvironmental pressure: +{b.pressure_base} (baked into player state)"
        parts.append(biome_text)

    # Layer 3: node-specific direction (Director)
    if node.system_prompt:
        parts.append(f"\n## Current Scene: {node.title}\n{node.system_prompt}")

    if node.context_hint:
        parts.append(f"\nTone/Genre: {node.context_hint}")

    # Layer 4: voice character
    voice = node.voice
    parts.append(
        f"\n## Voice"
        f"\nYou speak as: {voice.character_name}"
        f"\nEmotion: {voice.emotion}"
        f"\nStyle: {voice.style}"
    )

    # Layer 5: player context — what the AI needs to understand the stakes
    char = state.character
    pressure = char.pressure
    if pressure <= 3:
        pressure_directive = ""
    elif pressure <= 6:
        pressure_directive = "\nPRESSURE 4-6: Narrator is harsher. Shorter sentences. Less description, more weight."
    elif pressure <= 9:
        pressure_directive = "\nPRESSURE 7-9: Disorientation. Misdirect occasionally. Sentences fragment. Reality slips at the edges."
    else:
        pressure_directive = "\nPRESSURE 10: COLLAPSE. Player cannot continue. Force an incapacitation beat immediately."

    lo_trust = char.lo_trust
    lo_status = {0: "Lo has left — do not mention Lo", 1: "Lo is cold, minimal interaction", 2: "Lo is wary", 3: "Lo is neutral", 4: "Lo is warm, watchful", 5: "Lo fully trusts the player — rare, understated warmth"}.get(lo_trust, "Lo is neutral")

    parts.append(
        f"\n## Player Character"
        f"\nName: {char.name}"
        f"\nHP: {char.hp}/{char.max_hp}"
        f"\nPressure: {pressure}/10"
        f"\nLo: {lo_status}"
        f"\nInventory: {', '.join(i.name for i in char.inventory) or 'Empty'}"
        + pressure_directive
    )

    if state.world.time_of_day or state.world.weather:
        parts.append(
            f"\nTime: {state.world.time_of_day}, Weather: {state.world.weather}"
        )

    # Layer 5b: narrative flags — structured state for conditional narration
    active_flags = {k: v for k, v in state.narrative_flags.flags.items() if v}
    if active_flags:
        flag_lines = "\n".join(f"- {k}: {v}" for k, v in active_flags.items())
        parts.append(f"\n## Narrative State\n{flag_lines}")

    # Layer 6: available actions as stage directions (not a menu)
    available = node.get_available_actions(state)
    if available:
        action_list = "\n".join(f"- {a.label}: {a.description}" for a in available)
        parts.append(
            f"\n## Available Actions"
            f"\n{action_list}"
            f"\n\nGuide the player toward these choices without forcing them. "
            f"If the player does something unexpected, improvise within the bounds."
        )

    # Layer 7: per-node forbidden topics
    if node.forbidden_topics:
        topics = ", ".join(node.forbidden_topics)
        parts.append(
            f"\n## FORBIDDEN — Never speak about:"
            f"\n{topics}"
            f"\nIf the player asks about these topics, redirect back to the story."
        )

    # Layer 8: hard rules (always last)
    parts.append(
        f"\n## Rules"
        f"\n- Reply in English"
        f"\n- Maximum {node.max_response_length} words per response"
        f"\n- Drive the story forward, never be passive"
        f"\n- End with an implicit or explicit question or prompt"
        f"\n- You must NOT break character"
    )

    return "\n".join(parts)


def build_dice_narrative(result: SkillCheckResult) -> str:
    """Translate a mechanical dice result into directorial language for the LLM.

    The AI receives quality tiers, not raw numbers. "You barely made it"
    is more useful than "you rolled a 12 against DC 11". The prompt still
    includes the numbers for grounding, but the tier carries the dramatic weight.
    """
    ability_name = result.ability.value  # already English: strength, dexterity, etc.

    match result.narrative_quality:
        case "spectacular":
            if result.critical_success:
                return (
                    f"[CRITICAL SUCCESS! Nat 20 on {ability_name} check against DC {result.dc}. "
                    f"Total: {result.total}. Describe an OUTSTANDING result — "
                    f"the best possible outcome. The player succeeds in a way that "
                    f"surpasses all expectations.]"
                )
            return (
                f"[SPECTACULAR SUCCESS! {ability_name.capitalize()} check: "
                f"{result.total} against DC {result.dc} (+{result.margin}). "
                f"Describe an impressive result.]"
            )
        case "solid":
            return (
                f"[SUCCESS. {ability_name.capitalize()} check: "
                f"{result.total} against DC {result.dc}. "
                f"Describe a competent, confident result.]"
            )
        case "narrow":
            return (
                f"[BARELY MADE IT! {ability_name.capitalize()} check: "
                f"{result.total} against DC {result.dc} (margin: {result.margin}). "
                f"Describe how it almost went wrong but the player made it at the last moment.]"
            )
        case "failure":
            return (
                f"[FAILURE. {ability_name.capitalize()} check: "
                f"{result.total} against DC {result.dc} ({result.margin}). "
                f"Describe a credible failure — not embarrassing, "
                f"but the task was too difficult right now.]"
            )
        case "disaster":
            if result.critical_failure:
                return (
                    f"[CRITICAL FAILURE! Nat 1 on {ability_name} check. "
                    f"Describe a dramatic, almost comic failure. "
                    f"Something goes VERY wrong — but in a way that drives the story forward.]"
                )
            return (
                f"[CATASTROPHIC FAILURE. {ability_name.capitalize()} check: "
                f"{result.total} against DC {result.dc} ({result.margin}). "
                f"Describe a serious failure with consequences.]"
            )
        case _:
            return f"[{ability_name.capitalize()} check: {result.total} against DC {result.dc}]"


def build_context_messages(state: GameState, max_history: int = 10) -> list[dict[str, str]]:
    """Convert dialog history to LLM message format."""
    messages: list[dict[str, str]] = []
    for entry in state.get_recent_context(max_history):
        if entry.speaker == "player":
            messages.append({"role": "user", "content": entry.text})
        else:
            messages.append({"role": "assistant", "content": entry.text})
    return messages
