"""GALDR Engine — the main orchestration loop.

Coordinates all subsystems in a fixed 8-step order. The ordering is
not arbitrary; each step depends on the result of the previous one.
See process_input() for the reasoning behind each step's position.

Target: <2s end-to-end latency (p95) from player input to voice response.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import BaseModel, Field

from galdr.config import settings
from galdr.core.dice import skill_check, SkillCheckResult
from galdr.core.nodes import NarrativeNode, NodeAction, Scenario
from galdr.core.prompt_regi import (
    build_context_messages,
    build_dice_narrative,
    build_system_prompt,
)
from galdr.core.state import Ability, GameState
from galdr.ambient.context import build_ambient_context
from galdr.geo.geofence import GeoPoint, check_proximity, calculate_reverb
from galdr.guardrails.filter import ContentFilter
from galdr.services.interfaces import LLMService, TTSService, VoiceParams

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Engine Response
# ---------------------------------------------------------------------------

class EngineResponse(BaseModel):
    """Komplett respons från motorn tillbaka till spelaren."""
    text: str = ""
    audio: bytes = b""
    node_id: str = ""
    available_actions: list[dict[str, str]] = Field(default_factory=list)
    dice_result: SkillCheckResult | None = None
    state_changes: list[str] = Field(default_factory=list)
    latency_ms: int = 0
    step_latencies: dict[str, float] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# GALDR Engine
# ---------------------------------------------------------------------------

class GaldrEngine:
    """Core narrative engine — orchestrates state, mechanics, and AI generation.
    
    Implements Dependency Injection for AI services to support modular 
    backending and deterministic test mocking.
    """

    def __init__(
        self, 
        scenario: Scenario,
        llm: LLMService,
        tts: TTSService,
    ):
        self.scenario = scenario
        self.sessions: dict[str, GameState] = {}
        self.llm = llm
        self.tts = tts

    # ----- Session management -----

    def create_session(self, character_name: str = "Äventyrare") -> GameState:
        state = GameState()
        state.character.name = character_name
        state.current_node_id = self.scenario.start_node
        self.sessions[state.session_id] = state
        logger.info(f"New session: {state.session_id} ({character_name})")
        return state

    def get_session(self, session_id: str) -> GameState | None:
        return self.sessions.get(session_id)

    # ----- Main loop -----

    async def process_input(
        self,
        session_id: str,
        player_input: str,
        player_lat: float | None = None,
        player_lon: float | None = None,
    ) -> EngineResponse:
        """Process player input and return a complete engine response."""
        start_time = time.perf_counter()
        step_times: dict[str, float] = {}

        state = self.get_session(session_id)
        if not state:
            return EngineResponse(text="Session hittades inte.", latency_ms=0)

        if player_lat is not None:
            state.player_lat = player_lat
            state.player_lon = player_lon

        node = self.scenario.get_node(state.current_node_id)
        if not node:
            return EngineResponse(
                text=f"Node '{state.current_node_id}' not found in scenario.",
                latency_ms=0,
            )

        state.record_dialog("player", player_input, node_id=node.id)

        # Step 1: GPS proximity + ambient context
        t0 = time.perf_counter()
        geo_context = await self._check_geofence(state, node)
        ambient_context = await build_ambient_context(state.player_lat, state.player_lon)
        step_times["gps_ambient"] = (time.perf_counter() - t0) * 1000

        # Step 2: Intent matching
        t0 = time.perf_counter()
        matched_action = await self._match_action(player_input, node, state)
        step_times["intent_match"] = (time.perf_counter() - t0) * 1000

        # Step 3: Mechanics
        t0 = time.perf_counter()
        dice_result = None
        state_changes: list[str] = []
        next_node_id = state.current_node_id

        if matched_action:
            if matched_action.skill_check:
                dice_result = skill_check(
                    state, matched_action.skill_check, matched_action.dc
                )
                if dice_result.success:
                    next_node_id = matched_action.target_node or state.current_node_id
                    for c in matched_action.consequences:
                        state_changes.append(c.apply(state))
                else:
                    next_node_id = matched_action.failure_node or state.current_node_id
                    for c in matched_action.failure_consequences:
                        state_changes.append(c.apply(state))
            else:
                next_node_id = matched_action.target_node or state.current_node_id
                for c in matched_action.consequences:
                    state_changes.append(c.apply(state))
        step_times["mechanics"] = (time.perf_counter() - t0) * 1000

        # Step 4: Node transition
        t0 = time.perf_counter()
        if next_node_id != state.current_node_id:
            new_node = self.scenario.get_node(next_node_id)
            if new_node and new_node.can_enter(state):
                state.current_node_id = next_node_id
                node = new_node
                for c in node.on_enter:
                    state_changes.append(c.apply(state))
                state.visit_location(node.id, node.title)
        step_times["transition"] = (time.perf_counter() - t0) * 1000

        # Step 5: LLM generation
        t0 = time.perf_counter()
        combined_context = "\n".join(filter(None, [geo_context, ambient_context]))
        ai_response = await self._generate_response(
            state, node, player_input, dice_result, combined_context
        )
        step_times["llm_gen"] = (time.perf_counter() - t0) * 1000

        # Step 6: Content filter
        t0 = time.perf_counter()
        content_filter = ContentFilter(node.forbidden_topics)
        filter_result = content_filter.check(ai_response)
        final_text = filter_result.text
        step_times["content_filter"] = (time.perf_counter() - t0) * 1000

        state.record_dialog(
            node.voice.character_name, final_text,
            node_id=node.id, emotion=node.voice.emotion,
        )

        # Step 7: TTS
        t0 = time.perf_counter()
        audio = b""
        voice_params = VoiceParams(
            character_name=node.voice.character_name,
            emotion=node.voice.emotion,
            style=node.voice.style,
        )
        
        if state.player_lat and node.geo_lat:
            player_point = GeoPoint(state.player_lat, state.player_lon or 0)
            prox = check_proximity(player_point, node)
            if prox:
                voice_params.reverb = calculate_reverb(
                    prox.distance_meters, node.geo_radius_meters
                )
        
        audio = await self.tts.synthesize(final_text, voice_params)
        step_times["tts"] = (time.perf_counter() - t0) * 1000

        available = node.get_available_actions(state)
        action_list = [{"id": a.id, "label": a.label} for a in available]

        latency = int((time.perf_counter() - start_time) * 1000)
        logger.info(f"Response generated in {latency}ms (session: {session_id})")

        return EngineResponse(
            text=final_text,
            audio=audio,
            node_id=node.id,
            available_actions=action_list,
            dice_result=dice_result,
            state_changes=[s for s in state_changes if s],
            latency_ms=latency,
            step_latencies=step_times
        )

    # ----- Node entry -----

    async def enter_node(self, session_id: str) -> EngineResponse:
        """Trigger a node's opening text — called on first visit or after a transition."""
        start_time = time.perf_counter()
        step_times: dict[str, float] = {}

        state = self.get_session(session_id)
        if not state:
            return EngineResponse(text="Session not found.")

        node = self.scenario.get_node(state.current_node_id)
        if not node:
            return EngineResponse(text="Node not found.")

        t0 = time.perf_counter()
        state_changes: list[str] = []
        for c in node.on_enter:
            state_changes.append(c.apply(state))
        state.visit_location(node.id, node.title)
        step_times["mechanics"] = (time.perf_counter() - t0) * 1000

        # Use the scripted opening text if one exists; otherwise generate
        t0 = time.perf_counter()
        if node.opening_text:
            text = node.opening_text
        else:
            text = await self._generate_response(
                state, node,
                "[Spelaren anländer till denna plats. Beskriv scenen och bjud in till interaktion.]",
                None, "",
            )
        step_times["llm_gen"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        content_filter = ContentFilter(node.forbidden_topics)
        filter_result = content_filter.check(text)
        final_text = filter_result.text
        step_times["content_filter"] = (time.perf_counter() - t0) * 1000

        state.record_dialog(
            node.voice.character_name, final_text,
            node_id=node.id, emotion=node.voice.emotion,
        )

        t0 = time.perf_counter()
        audio = b""
        voice_params = VoiceParams(
            character_name=node.voice.character_name,
            emotion=node.voice.emotion,
            style=node.voice.style,
        )
        audio = await self.tts.synthesize(final_text, voice_params)
        step_times["tts"] = (time.perf_counter() - t0) * 1000

        available = node.get_available_actions(state)
        latency = int((time.perf_counter() - start_time) * 1000)

        return EngineResponse(
            text=final_text,
            audio=audio,
            node_id=node.id,
            available_actions=[{"id": a.id, "label": a.label} for a in available],
            state_changes=[s for s in state_changes if s],
            latency_ms=latency,
            step_latencies=step_times
        )

    # ----- Internal helpers -----

    async def _match_action(
        self,
        player_input: str,
        node: NarrativeNode,
        state: GameState,
    ) -> NodeAction | None:
        """Try LLM intent matching, fall back to offline if no API key or LLM fails."""
        available = node.get_available_actions(state)
        if not available:
            return None

        if not settings.openai_api_key:
            return self._match_action_offline(player_input, available)

        # Try LLM first, fall back to offline matching
        result = await self._match_action_llm(player_input, available)
        return result if result else self._match_action_offline(player_input, available)

    @staticmethod
    def _match_action_offline(
        player_input: str,
        available: list[NodeAction],
    ) -> NodeAction | None:
        """Offline matching — no LLM required. Priority order:
        1. Exact digit → 1-based list index
        2. Exact action ID
        3. Starts-with fuzzy keyword (handles Swedish inflections like lyssna/lyssnar)
        4. yes/no heuristics
        """
        text = player_input.lower().strip()

        if text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(available):
                return available[idx]

        for action in available:
            if action.id.lower() == text:
                return action

        input_words = set(text.split())
        best_score = 0
        best_action = None
        for action in available:
            label_words = set(action.label.lower().split())
            desc_words = set(action.description.lower().split())
            all_words = label_words | desc_words | {action.id.lower()}

            score = 0
            for iw in input_words:
                for aw in all_words:
                    if iw == aw or aw.startswith(iw) or iw.startswith(aw):
                        score += 1
                        break
            if score > best_score:
                best_score = score
                best_action = action

        if best_score > 0:
            return best_action

        if text in ("ja", "okej", "ok", "sure", "yes", "visst", "absolut"):
            return available[0]
        if text in ("nej", "nope", "no", "inte"):
            # Try to find a refusal/exit action
            for action in available:
                label_l = action.label.lower()
                if any(w in label_l for w in ("nej", "vägra", "gå", "lämna", "inte")):
                    return action
            return available[-1] if len(available) > 1 else None

        return None

    async def _match_action_llm(
        self,
        player_input: str,
        available: list[NodeAction],
    ) -> NodeAction | None:
        """Identifies player intent using a constrained LLM prompt."""
        action_descriptions = "\n".join(
            f"- ID: {a.id} | Label: {a.label} | Beskrivning: {a.description}"
            for a in available
        )

        prompt = (
            f"Spelaren sa: \"{player_input}\"\n\n"
            f"Tillgängliga handlingar:\n{action_descriptions}\n\n"
            f"Vilken handling matchar bäst spelarens intention? "
            f"Svara BARA med handlingens ID, eller 'none' om ingen matchar.\n"
            f"Svar:"
        )

        try:
            intent = await self.llm.generate_text(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=20,
                temperature=0,
            )
            intent = intent.strip().lower()

            for action in available:
                if action.id.lower() == intent:
                    return action
        except Exception as e:
            logger.error(f"Intent recognition failed: {e}")

        return None

    async def _generate_response(
        self,
        state: GameState,
        node: NarrativeNode,
        player_input: str,
        dice_result: SkillCheckResult | None,
        context: str,
    ) -> str:
        """Orchestrates LLM generation with current narrative and mechanical context."""
        system_prompt = build_system_prompt(self.scenario, node, state)

        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        messages.extend(build_context_messages(state, max_history=8))

        # Append dice result and geo/ambient context as stage directions
        extra: list[str] = []
        if dice_result:
            extra.append(build_dice_narrative(dice_result))
        if context:
            extra.append(context)

        user_content = player_input
        if extra:
            user_content = player_input + "\n\n" + "\n".join(extra)

        messages.append({"role": "user", "content": user_content})

        try:
            return await self.llm.generate_text(messages=messages)
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return self._generate_fallback(node, player_input, dice_result)

    def _generate_fallback(
        self,
        node: NarrativeNode,
        player_input: str,
        dice_result: SkillCheckResult | None,
    ) -> str:
        """Offline fallback — uses the node's scripted text directly."""
        parts: list[str] = []

        if dice_result:
            ability_sv = {
                "strength": "styrka", "dexterity": "smidighet",
                "constitution": "uthållighet", "intelligence": "intelligens",
                "wisdom": "visdom", "charisma": "karisma",
            }
            ability = ability_sv.get(dice_result.ability.value, dice_result.ability.value)

            if dice_result.critical_success:
                parts.append(
                    f"[Tärningsslag: {dice_result.roll.rolls[0]} + {dice_result.ability_modifier} "
                    f"= {dice_result.total} mot DC {dice_result.dc}]"
                    f"\nNaturlig 20! Ett enastående resultat!"
                )
            elif dice_result.critical_failure:
                parts.append(
                    f"[Tärningsslag: 1 + {dice_result.ability_modifier} "
                    f"= {dice_result.total} mot DC {dice_result.dc}]"
                    f"\nNaturlig 1... Det går fruktansvärt fel."
                )
            elif dice_result.success:
                parts.append(
                    f"[{ability.capitalize()}-check: {dice_result.total} mot DC {dice_result.dc} – Lyckat!]"
                )
            else:
                parts.append(
                    f"[{ability.capitalize()}-check: {dice_result.total} mot DC {dice_result.dc} – Misslyckat]"
                )
        elif node.opening_text:
            parts.append(node.opening_text)

        return "\n".join(parts) if parts else node.system_prompt[:200]

    async def _check_geofence(self, state: GameState, node: NarrativeNode) -> str:
        """Build a geofence context string to inject into the prompt, if GPS is available."""
        if state.player_lat is None or node.geo_lat is None:
            return ""

        player = GeoPoint(state.player_lat, state.player_lon or 0)
        result = check_proximity(player, node)
        if not result:
            return ""

        if result.within_radius:
            return (
                f"[Spelaren är {result.distance_meters:.0f}m från målpunkten. "
                f"De har anlänt! Välkomna dem till platsen.]"
            )
        elif result.signal_strength > 0.3:
            return (
                f"[Spelaren är {result.distance_meters:.0f}m bort. "
                f"Signalen stärks – de närmar sig. Bygg spänning.]"
            )
        return ""
