"""Stress test the offline intent matcher against the_dark node actions.

Tests adversarial, creative, and edge-case inputs to find where matching
breaks down. The offline matcher is the fallback when the LLM fails --
these tests define its actual coverage boundary.

the_dark actions:
  slip_through  -- DEX DC 14 -- "Slip through while it passes"
  go_still      -- WIS DC 12 -- "Go completely still"
  charge_at_it  -- STR DC 12 -- "Charge at it"
  find_the_panel -- INT DC 13 -- "Find the maintenance panel"
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SCENARIO_PATH = Path(__file__).parent.parent / "scenarios" / "calloused_prologue.json"


def load_dark_actions():
    data = json.loads(SCENARIO_PATH.read_text(encoding="utf-8-sig"))
    node = data["nodes"]["the_dark"]
    # Minimal NodeAction-like objects for the offline matcher
    class _Action:
        def __init__(self, d):
            self.id = d["id"]
            self.label = d.get("label", "")
            self.description = d.get("description", "")
    return [_Action(a) for a in node["actions"]]


from galdr.core.engine import GaldrEngine

def _match(text: str):
    actions = load_dark_actions()
    return GaldrEngine._match_action_offline(text, actions)


def _id(text: str) -> str | None:
    result = _match(text)
    return result.id if result else None


# --- Exact matches ---

def test_exact_id_slip():
    assert _id("slip_through") == "slip_through"

def test_exact_id_charge():
    assert _id("charge_at_it") == "charge_at_it"

def test_exact_id_panel():
    assert _id("find_the_panel") == "find_the_panel"

def test_exact_id_still():
    assert _id("go_still") == "go_still"

# --- Digit index ---

def test_digit_1():
    assert _id("1") == load_dark_actions()[0].id

def test_digit_4():
    assert _id("4") == load_dark_actions()[3].id

def test_digit_out_of_range():
    assert _id("9") is None

# --- Keyword matches (should hit) ---

def test_slip_keyword():
    assert _id("I slip past it") == "slip_through"

def test_still_keyword():
    assert _id("go still") == "go_still"

def test_charge_keyword():
    assert _id("charge") == "charge_at_it"

def test_panel_keyword():
    assert _id("find the panel") == "find_the_panel"

def test_panel_partial():
    """'panel' alone returns None because find_the_panel's label is
    'Search the wall -- there must be a shutoff' (no word 'panel' in label).
    Action ID is not split by underscore in the offline matcher.
    LLM path is required for single-word-from-ID matching -- coverage boundary.
    """
    result = _id("panel")
    print(f"\n  'panel' -> {result}  (None expected -- LLM needed for ID-word matching)")

# --- Creative / adversarial (offline will likely miss these -- document boundary) ---

def test_headbutt_offline():
    """Headbutt = charge. Offline matcher likely misses this -- needs LLM."""
    result = _id("headbutt it")
    # Document result, don't assert correctness -- this is the coverage boundary
    print(f"\n  'headbutt it' -> {result}")

def test_freeze_offline():
    """Freeze = go_still. Offline may or may not catch it."""
    result = _id("I freeze completely")
    print(f"\n  'I freeze completely' -> {result}")

def test_tackle_offline():
    result = _id("tackle the thing")
    print(f"\n  'tackle the thing' -> {result}")

def test_rush_offline():
    result = _id("I rush it")
    print(f"\n  'I rush it' -> {result}")

def test_maintenance_offline():
    result = _id("look for a maintenance access")
    print(f"\n  'look for a maintenance access' -> {result}")

def test_completely_offscript():
    """Scream at it -- no match expected."""
    result = _id("I scream at the top of my lungs")
    print(f"\n  'I scream at the top of my lungs' -> {result}")
    # Offline should not match this to anything specific
    # (any match here is suspicious -- could be false positive)

def test_empty_input():
    assert _id("") is None

def test_whitespace_only():
    assert _id("   ") is None

def test_yes_heuristic():
    result = _id("yes")
    assert result is not None  # Should match first action

def test_no_heuristic():
    result = _id("no")
    assert result is not None  # Should match last or refusal action

def test_ambiguous_multi_word():
    """'find slip' -- matches two actions. Which wins?"""
    result = _id("find slip")
    print(f"\n  'find slip' -> {result}")
    # Both slip_through and find_the_panel contain matching words.
    # Document which one wins for highest score.
