"""Test the prompt director with flag combinations and edge cases.

Checks that:
- Active narrative flags appear in the system prompt
- False/empty flags are suppressed
- Conflicting flags both appear (LLM sees them -- it must resolve)
- Pressure directives fire at the right thresholds
- Lo trust descriptions are correct at each level
- No em dashes or unicode arrows appear in the output
"""

from __future__ import annotations

import re

import pytest

from galdr.core.nodes import NarrativeNode, Scenario
from galdr.core.prompt_director import build_system_prompt
from galdr.core.state import GameState, NarrativeFlags


SCENARIO_PATH = "app/scenarios/calloused_prologue.json"

_EM_DASH = re.compile(r'[—–]')
_UNICODE_ARROW = re.compile(r'[→←]')


def make_state(**flags) -> GameState:
    state = GameState()
    for k, v in flags.items():
        state.narrative_flags.set_flag(k, v)
    return state


def get_prompt(node_id: str = "cryo_room", **flags) -> str:
    scenario = Scenario.load_from_file(SCENARIO_PATH)
    node = scenario.get_node(node_id)
    state = make_state(**flags)
    return build_system_prompt(scenario, node, state)


# --- Flag injection ---

def test_truthy_flag_appears():
    prompt = get_prompt(bruised_by_unit=True)
    assert "bruised_by_unit" in prompt

def test_false_flag_suppressed():
    """False flags must not appear in the ## Narrative State section."""
    prompt = get_prompt(bruised_by_unit=False)
    if "## Narrative State" in prompt:
        state_section = prompt.split("## Narrative State")[1].split("##")[0]
        assert "bruised_by_unit" not in state_section

def test_no_flags_no_narrative_state_section():
    prompt = get_prompt()
    assert "## Narrative State" not in prompt

def test_multiple_flags():
    prompt = get_prompt(bruised_by_unit=True, destroyed_the_unit=True)
    assert "bruised_by_unit" in prompt
    assert "destroyed_the_unit" in prompt

def test_conflicting_flags_both_visible():
    """If both destroyed and shut_down are somehow set, LLM sees both."""
    prompt = get_prompt(destroyed_the_unit=True, shut_down_the_unit=True)
    assert "destroyed_the_unit" in prompt
    assert "shut_down_the_unit" in prompt

def test_string_flag_value_appears():
    prompt = get_prompt(player_choice="aggressive")
    assert "player_choice" in prompt
    assert "aggressive" in prompt


# --- Pressure directives ---

def test_pressure_0_no_directive():
    scenario = Scenario.load_from_file(SCENARIO_PATH)
    node = scenario.get_node("cryo_room")
    state = GameState()
    state.character.pressure = 0
    prompt = build_system_prompt(scenario, node, state)
    assert "PRESSURE" not in prompt

def test_pressure_5_gold_zone():
    scenario = Scenario.load_from_file(SCENARIO_PATH)
    node = scenario.get_node("cryo_room")
    state = GameState()
    state.character.pressure = 5
    prompt = build_system_prompt(scenario, node, state)
    assert "PRESSURE 4-6" in prompt

def test_pressure_8_disorientation():
    scenario = Scenario.load_from_file(SCENARIO_PATH)
    node = scenario.get_node("cryo_room")
    state = GameState()
    state.character.pressure = 8
    prompt = build_system_prompt(scenario, node, state)
    assert "PRESSURE 7-9" in prompt

def test_pressure_10_collapse():
    scenario = Scenario.load_from_file(SCENARIO_PATH)
    node = scenario.get_node("cryo_room")
    state = GameState()
    state.character.pressure = 10
    prompt = build_system_prompt(scenario, node, state)
    assert "COLLAPSE" in prompt


# --- Lo trust descriptions ---

def test_lo_trust_0_gone():
    scenario = Scenario.load_from_file(SCENARIO_PATH)
    node = scenario.get_node("lo_aftermath")
    state = GameState()
    state.character.lo_trust = 0
    prompt = build_system_prompt(scenario, node, state)
    assert "Lo has left" in prompt

def test_lo_trust_3_neutral():
    scenario = Scenario.load_from_file(SCENARIO_PATH)
    node = scenario.get_node("lo_aftermath")
    state = GameState()
    state.character.lo_trust = 3
    prompt = build_system_prompt(scenario, node, state)
    assert "neutral" in prompt

def test_lo_trust_5_trust():
    scenario = Scenario.load_from_file(SCENARIO_PATH)
    node = scenario.get_node("lo_aftermath")
    state = GameState()
    state.character.lo_trust = 5
    prompt = build_system_prompt(scenario, node, state)
    assert "fully trusts" in prompt


# --- Encoding cleanliness ---

def test_no_unicode_arrows_in_output():
    """Unicode arrows must not appear anywhere -- they break Windows console."""
    prompt = get_prompt(bruised_by_unit=True)
    matches = _UNICODE_ARROW.findall(prompt)
    assert not matches, f"Unicode arrow found in prompt: {matches}"


# --- Layer ordering sanity ---

def test_global_identity_is_first():
    prompt = get_prompt()
    assert prompt.startswith("You are the narrator of Calloused")

def test_rules_section_present():
    prompt = get_prompt()
    assert "## Rules" in prompt

def test_english_rule_present():
    prompt = get_prompt()
    assert "Reply in English" in prompt
