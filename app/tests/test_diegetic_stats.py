"""Comprehensive tests for the diegetic character building system.

Covers every layer of the stat accumulation pipeline:
  1. Character.crystallize_stats()          -- ranking, standard array, tie-breaking, reset
  2. Consequence type "crystallize_stats"   -- integration with the consequence system
  3. NodeAction.stat_weights field          -- model validation, serialization
  4. Engine process_input                   -- accumulation on match (sync path)
  5. Engine process_input_stream            -- accumulation on match (stream path)
  6. Skill check invariant                  -- weights apply regardless of dice outcome
  7. End-to-end flow                        -- actions -> accumulate -> crystallize
  8. calloused_prologue.json                -- JSON content and scenario-level invariants
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from galdr.core.nodes import Consequence, NarrativeNode, NodeAction, Scenario
from galdr.core.state import Ability, Character, CharacterStats, GameState

SCENARIO_PATH = Path(__file__).parent.parent / "scenarios" / "calloused_prologue.json"

VALID_STATS = {"strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"}
STANDARD_ARRAY = {15, 14, 13, 12, 10, 8}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stat_set(char: Character) -> set[int]:
    return {
        char.stats.strength,
        char.stats.dexterity,
        char.stats.constitution,
        char.stats.intelligence,
        char.stats.wisdom,
        char.stats.charisma,
    }


def _scenario(stat_weights=None, loop_back=False) -> Scenario:
    """Minimal two-node (or looping) scenario with one action."""
    target = "start" if loop_back else "end"
    nodes: dict = {
        "start": NarrativeNode(
            id="start", title="Start", description="Start node",
            actions=[
                NodeAction(
                    id="act", label="Act",
                    target_node=target,
                    stat_weights=stat_weights or {},
                )
            ],
        ),
    }
    if not loop_back:
        nodes["end"] = NarrativeNode(id="end", title="End", description="End node")
    return Scenario(id="t", title="T", description="T", start_node="start", nodes=nodes)


def _engine(scenario=None, stat_weights=None):
    from galdr.core.engine import GaldrEngine
    from galdr.services.mock_service import MockAIService
    s = scenario or _scenario(stat_weights=stat_weights)
    ai = MockAIService()
    return GaldrEngine(s, ai, ai), ai


def _forced_skill_check(success: bool):
    from galdr.core.dice import DiceRoll, DiceType, SkillCheckResult
    roll = DiceRoll(
        dice_type=DiceType.D20, count=1,
        rolls=[15 if success else 2], modifier=0,
        total=15 if success else 2,
    )
    return SkillCheckResult(
        ability=Ability.STRENGTH, dc=10, roll=roll,
        ability_modifier=0, total=roll.total,
        success=success, critical_success=False, critical_failure=False,
        margin=5 if success else -8,
        narrative_quality="solid" if success else "failure",
    )


def _load_prologue() -> dict:
    return json.loads(SCENARIO_PATH.read_text(encoding="utf-8-sig"))


# ---------------------------------------------------------------------------
# 1. Character.crystallize_stats() — pure unit tests
# ---------------------------------------------------------------------------

class TestCrystallizeStats:

    def test_standard_array_values_exactly(self):
        char = Character()
        char.stat_accumulator = {s: float(i) for i, s in enumerate(VALID_STATS)}
        char.crystallize_stats()
        assert _stat_set(char) == STANDARD_ARRAY

    def test_clear_winner_gets_15(self):
        char = Character()
        char.stat_accumulator = {"wisdom": 99.0}
        char.crystallize_stats()
        assert char.stats.wisdom == 15

    def test_ranking_matches_weight_order(self):
        char = Character()
        char.stat_accumulator = {
            "strength": 6.0,
            "dexterity": 5.0,
            "constitution": 4.0,
            "intelligence": 3.0,
            "wisdom": 2.0,
            "charisma": 1.0,
        }
        char.crystallize_stats()
        assert char.stats.strength == 15
        assert char.stats.dexterity == 14
        assert char.stats.constitution == 13
        assert char.stats.intelligence == 12
        assert char.stats.wisdom == 10
        assert char.stats.charisma == 8

    def test_reverse_ranking(self):
        char = Character()
        char.stat_accumulator = {
            "strength": 1.0,
            "dexterity": 2.0,
            "constitution": 3.0,
            "intelligence": 4.0,
            "wisdom": 5.0,
            "charisma": 6.0,
        }
        char.crystallize_stats()
        assert char.stats.charisma == 15
        assert char.stats.wisdom == 14
        assert char.stats.intelligence == 13
        assert char.stats.constitution == 12
        assert char.stats.dexterity == 10
        assert char.stats.strength == 8

    def test_accumulator_cleared_after_crystallization(self):
        char = Character()
        char.stat_accumulator = {"wisdom": 3.0, "strength": 1.0}
        char.crystallize_stats()
        assert char.stat_accumulator == {}

    def test_empty_accumulator_still_assigns_standard_array(self):
        char = Character()
        assert char.stat_accumulator == {}
        char.crystallize_stats()
        assert _stat_set(char) == STANDARD_ARRAY

    def test_empty_accumulator_is_deterministic(self):
        c1, c2 = Character(), Character()
        c1.crystallize_stats()
        c2.crystallize_stats()
        assert c1.stats.model_dump() == c2.stats.model_dump()

    def test_single_weighted_stat_gets_15(self):
        for stat in VALID_STATS:
            char = Character()
            char.stat_accumulator = {stat: 5.0}
            char.crystallize_stats()
            assert getattr(char.stats, stat) == 15, f"{stat} should be 15"

    def test_partial_accumulator_all_six_stats_still_assigned(self):
        char = Character()
        char.stat_accumulator = {"intelligence": 3.0, "charisma": 1.0}
        char.crystallize_stats()
        assert char.stats.intelligence == 15
        assert char.stats.charisma == 14
        assert _stat_set(char) == STANDARD_ARRAY

    def test_stats_stay_within_pydantic_bounds(self):
        char = Character()
        char.stat_accumulator = {"strength": 9999.0}
        char.crystallize_stats()
        for attr in VALID_STATS:
            val = getattr(char.stats, attr)
            assert 1 <= val <= 20, f"{attr}={val} out of CharacterStats bounds"

    def test_fractional_weights_preserve_order(self):
        char = Character()
        char.stat_accumulator = {"dexterity": 2.5, "wisdom": 2.4, "charisma": 2.3}
        char.crystallize_stats()
        assert char.stats.dexterity == 15
        assert char.stats.wisdom == 14
        assert char.stats.charisma == 13

    def test_accumulation_adds_correctly(self):
        """Simulate two separate actions both contributing to wisdom."""
        char = Character()
        char.stat_accumulator["wisdom"] = char.stat_accumulator.get("wisdom", 0.0) + 2.0
        char.stat_accumulator["wisdom"] = char.stat_accumulator.get("wisdom", 0.0) + 1.5
        char.crystallize_stats()
        assert char.stats.wisdom == 15  # 3.5 total — highest

    def test_tie_breaking_is_deterministic(self):
        """Equal weights always produce the same ranking."""
        c1 = Character()
        c1.stat_accumulator = {"strength": 2.0, "wisdom": 2.0, "charisma": 2.0}
        c1.crystallize_stats()

        c2 = Character()
        c2.stat_accumulator = {"strength": 2.0, "wisdom": 2.0, "charisma": 2.0}
        c2.crystallize_stats()

        assert c1.stats.model_dump() == c2.stats.model_dump()

    def test_all_equal_weights_deterministic(self):
        c1 = Character()
        c1.stat_accumulator = {s: 1.0 for s in VALID_STATS}
        c1.crystallize_stats()

        c2 = Character()
        c2.stat_accumulator = {s: 1.0 for s in VALID_STATS}
        c2.crystallize_stats()

        assert c1.stats.model_dump() == c2.stats.model_dump()
        assert _stat_set(c1) == STANDARD_ARRAY

    def test_no_duplicate_stat_values(self):
        """Each of the six standard array values appears exactly once."""
        char = Character()
        char.stat_accumulator = {"intelligence": 5.0, "charisma": 4.0}
        char.crystallize_stats()
        vals = [
            char.stats.strength, char.stats.dexterity, char.stats.constitution,
            char.stats.intelligence, char.stats.wisdom, char.stats.charisma,
        ]
        assert len(vals) == len(set(vals)), f"Duplicate stat values: {vals}"

    def test_crystallize_after_crystallize_still_valid(self):
        """Second call (on cleared accumulator) still produces valid standard array."""
        char = Character()
        char.stat_accumulator = {"wisdom": 5.0}
        char.crystallize_stats()
        assert char.stats.wisdom == 15

        char.crystallize_stats()  # accumulator is now empty
        assert _stat_set(char) == STANDARD_ARRAY

    def test_negative_weight_still_produces_valid_array(self):
        """Negative weight shouldn't crash — wisdom still wins with positive weight."""
        char = Character()
        char.stat_accumulator = {"strength": -5.0, "wisdom": 2.0}
        char.crystallize_stats()
        assert char.stats.wisdom == 15
        assert char.stats.strength == 8  # lowest weight → lowest stat
        assert _stat_set(char) == STANDARD_ARRAY

    def test_unknown_key_in_accumulator_is_ignored(self):
        """An invalid stat name in the accumulator should not break crystallization."""
        char = Character()
        char.stat_accumulator = {"wisdom": 3.0, "luck": 99.0}  # 'luck' is not a real stat
        char.crystallize_stats()
        assert char.stats.wisdom == 15
        assert _stat_set(char) == STANDARD_ARRAY


# ---------------------------------------------------------------------------
# 2. Consequence type "crystallize_stats"
# ---------------------------------------------------------------------------

class TestCrystallizeConsequence:

    def test_consequence_triggers_crystallize(self):
        state = GameState()
        state.character.stat_accumulator = {"charisma": 5.0}
        cons = Consequence(type="crystallize_stats")
        result = cons.apply(state)
        assert result == "Stats crystallized from prologue actions"
        assert state.character.stats.charisma == 15

    def test_consequence_clears_accumulator(self):
        state = GameState()
        state.character.stat_accumulator = {"strength": 3.0}
        Consequence(type="crystallize_stats").apply(state)
        assert state.character.stat_accumulator == {}

    def test_consequence_on_empty_accumulator(self):
        state = GameState()
        Consequence(type="crystallize_stats").apply(state)
        assert _stat_set(state.character) == STANDARD_ARRAY

    def test_consequence_return_string_is_constant(self):
        for _ in range(3):
            state = GameState()
            result = Consequence(type="crystallize_stats").apply(state)
            assert result == "Stats crystallized from prologue actions"

    def test_consequence_mutates_state_character_stats(self):
        state = GameState()
        state.character.stat_accumulator = {"intelligence": 10.0}
        before = state.character.stats.intelligence
        Consequence(type="crystallize_stats").apply(state)
        after = state.character.stats.intelligence
        assert after == 15
        assert after != before or before == 15  # before was default 10

    def test_consequence_chained_with_set_flag(self):
        state = GameState()
        state.character.stat_accumulator = {"wisdom": 2.0}
        Consequence(type="set_flag", key="prologue_done", value=True).apply(state)
        Consequence(type="crystallize_stats").apply(state)
        assert state.narrative_flags.check("prologue_done", True)
        assert state.character.stats.wisdom == 15


# ---------------------------------------------------------------------------
# 3. NodeAction.stat_weights field
# ---------------------------------------------------------------------------

class TestNodeActionStatWeights:

    def test_default_is_empty_dict(self):
        action = NodeAction(id="x", label="X")
        assert action.stat_weights == {}

    def test_single_stat(self):
        action = NodeAction(id="x", label="X", stat_weights={"wisdom": 2.0})
        assert action.stat_weights["wisdom"] == 2.0

    def test_multiple_stats(self):
        action = NodeAction(
            id="x", label="X",
            stat_weights={"wisdom": 1.5, "charisma": 0.5, "constitution": 1.0},
        )
        assert len(action.stat_weights) == 3
        assert action.stat_weights["wisdom"] == 1.5
        assert action.stat_weights["charisma"] == 0.5
        assert action.stat_weights["constitution"] == 1.0

    def test_survives_model_dump_and_validate(self):
        action = NodeAction(
            id="x", label="X",
            stat_weights={"intelligence": 2.5, "strength": 0.5},
        )
        restored = NodeAction.model_validate(action.model_dump())
        assert restored.stat_weights == {"intelligence": 2.5, "strength": 0.5}

    def test_survives_json_round_trip(self):
        action = NodeAction(id="x", label="X", stat_weights={"dexterity": 2.0})
        j = action.model_dump_json()
        restored = NodeAction.model_validate_json(j)
        assert restored.stat_weights == {"dexterity": 2.0}

    def test_zero_weight_stored(self):
        action = NodeAction(id="x", label="X", stat_weights={"wisdom": 0.0})
        assert action.stat_weights["wisdom"] == 0.0

    def test_stat_weights_independent_across_instances(self):
        a1 = NodeAction(id="a", label="A", stat_weights={"wisdom": 1.0})
        a2 = NodeAction(id="b", label="B", stat_weights={"strength": 2.0})
        assert "wisdom" not in a2.stat_weights
        assert "strength" not in a1.stat_weights


# ---------------------------------------------------------------------------
# 4 & 5. Engine stat accumulation — sync and stream paths
# ---------------------------------------------------------------------------

class TestEngineStatAccumulation:

    def test_weights_applied_on_action_match(self):
        engine, _ = _engine(stat_weights={"wisdom": 2.0})
        state = engine.create_session()
        asyncio.run(engine.process_input(state.session_id, "act"))
        assert state.character.stat_accumulator.get("wisdom") == 2.0

    def test_weights_accumulate_over_multiple_turns(self):
        engine, _ = _engine(scenario=_scenario(stat_weights={"wisdom": 1.5}, loop_back=True))
        state = engine.create_session()
        asyncio.run(engine.process_input(state.session_id, "act"))
        asyncio.run(engine.process_input(state.session_id, "act"))
        asyncio.run(engine.process_input(state.session_id, "act"))
        assert pytest.approx(state.character.stat_accumulator["wisdom"]) == 4.5

    def test_no_weights_when_action_has_none(self):
        engine, _ = _engine()  # stat_weights={}
        state = engine.create_session()
        asyncio.run(engine.process_input(state.session_id, "act"))
        assert state.character.stat_accumulator == {}

    def test_no_weights_when_no_action_matched(self):
        engine, _ = _engine(stat_weights={"strength": 3.0})
        state = engine.create_session()
        asyncio.run(engine.process_input(state.session_id, "zzz"))  # won't match "act"
        assert state.character.stat_accumulator.get("strength", 0.0) == 0.0

    def test_multi_stat_weights_all_applied(self):
        engine, _ = _engine(stat_weights={"wisdom": 1.5, "constitution": 0.5})
        state = engine.create_session()
        asyncio.run(engine.process_input(state.session_id, "act"))
        assert pytest.approx(state.character.stat_accumulator["wisdom"]) == 1.5
        assert pytest.approx(state.character.stat_accumulator["constitution"]) == 0.5

    def test_weights_applied_on_skill_check_success(self):
        """Choice reveals tendency; dice determine outcome. Weight must apply on success."""
        scenario = Scenario(
            id="t", title="T", description="T", start_node="start",
            nodes={
                "start": NarrativeNode(
                    id="start", title="Start", description="d",
                    actions=[
                        NodeAction(
                            id="charge", label="Charge at it",
                            target_node="end", failure_node="start",
                            skill_check=Ability.STRENGTH, dc=10,
                            stat_weights={"strength": 2.5},
                        )
                    ],
                ),
                "end": NarrativeNode(id="end", title="End", description="d"),
            },
        )
        engine, _ = _engine(scenario=scenario)
        state = engine.create_session()

        forced = _forced_skill_check(success=True)
        with patch("galdr.core.engine.skill_check", return_value=forced):
            asyncio.run(engine.process_input(state.session_id, "charge"))

        assert state.character.stat_accumulator.get("strength") == 2.5
        assert state.current_node_id == "end"

    def test_weights_applied_on_skill_check_failure(self):
        """Choice reveals tendency even when the dice say no."""
        scenario = Scenario(
            id="t", title="T", description="T", start_node="start",
            nodes={
                "start": NarrativeNode(
                    id="start", title="Start", description="d",
                    actions=[
                        NodeAction(
                            id="charge", label="Charge at it",
                            target_node="end", failure_node="start",
                            skill_check=Ability.STRENGTH, dc=10,
                            stat_weights={"strength": 2.5},
                        )
                    ],
                ),
                "end": NarrativeNode(id="end", title="End", description="d"),
            },
        )
        engine, _ = _engine(scenario=scenario)
        state = engine.create_session()

        forced = _forced_skill_check(success=False)
        with patch("galdr.core.engine.skill_check", return_value=forced):
            asyncio.run(engine.process_input(state.session_id, "charge"))

        # Weight still accumulated even though the roll failed
        assert state.character.stat_accumulator.get("strength") == 2.5
        assert state.current_node_id == "start"  # stayed in place (failure_node=start)

    def test_weights_do_not_bleed_across_sessions(self):
        """Two sessions from the same engine must not share accumulator state."""
        engine, _ = _engine(stat_weights={"wisdom": 2.0})
        s1 = engine.create_session()
        s2 = engine.create_session()
        asyncio.run(engine.process_input(s1.session_id, "act"))
        assert s2.character.stat_accumulator.get("wisdom", 0.0) == 0.0

    def test_accumulator_persists_after_node_transition(self):
        """Accumulator carries over between nodes (it is on Character, not on GameState root)."""
        engine, _ = _engine(stat_weights={"charisma": 1.0})
        state = engine.create_session()
        asyncio.run(engine.process_input(state.session_id, "act"))
        assert state.current_node_id == "end"
        assert state.character.stat_accumulator.get("charisma") == 1.0


class TestEngineStreamStatAccumulation:

    def _run_stream(self, engine, session_id, user_input):
        async def _inner():
            partial, stream = await engine.process_input_stream(session_id, user_input)
            async for _ in stream:
                pass
            return partial
        return asyncio.run(_inner())

    def test_stream_weights_applied_on_match(self):
        engine, _ = _engine(stat_weights={"charisma": 2.0})
        state = engine.create_session()
        self._run_stream(engine, state.session_id, "act")
        assert state.character.stat_accumulator.get("charisma") == 2.0

    def test_stream_no_weights_when_no_match(self):
        engine, _ = _engine(stat_weights={"intelligence": 1.0})
        state = engine.create_session()
        self._run_stream(engine, state.session_id, "zzz")
        assert state.character.stat_accumulator.get("intelligence", 0.0) == 0.0

    def test_stream_multi_stat_weights(self):
        engine, _ = _engine(stat_weights={"dexterity": 2.0, "wisdom": 0.5})
        state = engine.create_session()
        self._run_stream(engine, state.session_id, "act")
        assert pytest.approx(state.character.stat_accumulator["dexterity"]) == 2.0
        assert pytest.approx(state.character.stat_accumulator["wisdom"]) == 0.5

    def test_stream_weights_accumulate_across_turns(self):
        engine, _ = _engine(scenario=_scenario(stat_weights={"wisdom": 1.0}, loop_back=True))
        state = engine.create_session()
        self._run_stream(engine, state.session_id, "act")
        self._run_stream(engine, state.session_id, "act")
        assert pytest.approx(state.character.stat_accumulator["wisdom"]) == 2.0

    def test_stream_weights_on_skill_check_match(self):
        scenario = Scenario(
            id="t", title="T", description="T", start_node="start",
            nodes={
                "start": NarrativeNode(
                    id="start", title="Start", description="d",
                    actions=[
                        NodeAction(
                            id="charge", label="Charge at it",
                            target_node="end", failure_node="start",
                            skill_check=Ability.STRENGTH, dc=10,
                            stat_weights={"strength": 1.5},
                        )
                    ],
                ),
                "end": NarrativeNode(id="end", title="End", description="d"),
            },
        )
        engine, _ = _engine(scenario=scenario)
        state = engine.create_session()

        forced = _forced_skill_check(success=True)
        with patch("galdr.core.engine.skill_check", return_value=forced):
            self._run_stream(engine, state.session_id, "charge")

        assert state.character.stat_accumulator.get("strength") == 1.5


# ---------------------------------------------------------------------------
# 6. End-to-end: actions accumulate, crystallize fires on node entry
# ---------------------------------------------------------------------------

class TestCrystallizeEndToEnd:

    def test_crystallize_fires_on_transition(self):
        scenario = Scenario(
            id="t", title="T", description="T", start_node="start",
            nodes={
                "start": NarrativeNode(
                    id="start", title="Start", description="d",
                    actions=[
                        NodeAction(
                            id="go", label="Go",
                            target_node="end",
                            stat_weights={"charisma": 3.0},
                        )
                    ],
                ),
                "end": NarrativeNode(
                    id="end", title="End", description="d",
                    on_enter=[Consequence(type="crystallize_stats")],
                ),
            },
        )
        engine, _ = _engine(scenario=scenario)
        state = engine.create_session()
        asyncio.run(engine.process_input(state.session_id, "go"))

        assert state.character.stats.charisma == 15
        assert state.character.stat_accumulator == {}

    def test_multi_node_prologue_then_crystallize(self):
        """Two nodes each contribute a stat; crystallize on the third."""
        scenario = Scenario(
            id="t", title="T", description="T", start_node="n1",
            nodes={
                "n1": NarrativeNode(
                    id="n1", title="N1", description="d",
                    actions=[NodeAction(id="sneak", label="Sneak", target_node="n2",
                                       stat_weights={"dexterity": 2.0})],
                ),
                "n2": NarrativeNode(
                    id="n2", title="N2", description="d",
                    actions=[NodeAction(id="study", label="Study", target_node="close",
                                       stat_weights={"intelligence": 3.0})],
                ),
                "close": NarrativeNode(
                    id="close", title="Close", description="d",
                    on_enter=[Consequence(type="crystallize_stats")],
                    actions=[],
                ),
            },
        )
        engine, _ = _engine(scenario=scenario)
        state = engine.create_session()

        asyncio.run(engine.process_input(state.session_id, "sneak"))
        asyncio.run(engine.process_input(state.session_id, "study"))

        assert state.character.stats.intelligence == 15  # 3.0 — top
        assert state.character.stats.dexterity == 14    # 2.0 — second
        assert state.character.stat_accumulator == {}

    def test_all_stats_accumulate_across_six_nodes(self):
        """Each action contributes a different stat; crystallize assigns standard array."""
        nodes: dict = {}
        stats_order = list(VALID_STATS)
        for i, stat in enumerate(stats_order):
            nid = f"n{i}"
            nxt = f"n{i+1}" if i < len(stats_order) - 1 else "close"
            nodes[nid] = NarrativeNode(
                id=nid, title=nid, description="d",
                actions=[NodeAction(
                    id="go", label="Go", target_node=nxt,
                    stat_weights={stat: float(len(stats_order) - i)},
                )],
            )
        nodes["close"] = NarrativeNode(
            id="close", title="Close", description="d",
            on_enter=[Consequence(type="crystallize_stats")],
            actions=[],
        )
        scenario = Scenario(
            id="t", title="T", description="T",
            start_node="n0", nodes=nodes,
        )
        engine, _ = _engine(scenario=scenario)
        state = engine.create_session()

        for _ in stats_order:
            asyncio.run(engine.process_input(state.session_id, "go"))

        # All 6 stats must be assigned and use the standard array values
        assert _stat_set(state.character) == STANDARD_ARRAY
        assert state.character.stat_accumulator == {}

    def test_crystallize_does_not_double_fire(self):
        """If crystallize consequence runs twice (authoring bug), stats must still be valid."""
        scenario = Scenario(
            id="t", title="T", description="T", start_node="start",
            nodes={
                "start": NarrativeNode(
                    id="start", title="Start", description="d",
                    actions=[NodeAction(id="go", label="Go", target_node="end",
                                       stat_weights={"wisdom": 5.0})],
                ),
                "end": NarrativeNode(
                    id="end", title="End", description="d",
                    on_enter=[
                        Consequence(type="crystallize_stats"),
                        Consequence(type="crystallize_stats"),  # duplicated by mistake
                    ],
                ),
            },
        )
        engine, _ = _engine(scenario=scenario)
        state = engine.create_session()
        asyncio.run(engine.process_input(state.session_id, "go"))

        # First call crystallizes correctly; second call runs on empty accumulator
        assert _stat_set(state.character) == STANDARD_ARRAY
        assert state.character.stat_accumulator == {}

    def test_game_state_serializes_after_crystallize(self):
        """Crystallized state must survive JSON round-trip (checkpoint/load path)."""
        char = Character()
        char.stat_accumulator = {"wisdom": 5.0, "charisma": 3.0}
        char.crystallize_stats()

        state = GameState()
        state.character = char

        json_str = state.model_dump_json()
        restored = GameState.model_validate_json(json_str)

        assert restored.character.stats.wisdom == 15
        assert restored.character.stats.charisma == 14
        assert restored.character.stat_accumulator == {}


# ---------------------------------------------------------------------------
# 7. calloused_prologue.json — scenario-level invariants
# ---------------------------------------------------------------------------

class TestPrologueScenarioJSON:

    def test_scenario_version_is_3_2_0(self):
        data = _load_prologue()
        assert data["version"] == "3.2.0"

    def test_calibration_node_is_null(self):
        data = _load_prologue()
        assert data.get("calibration_node") is None

    def test_scenario_parses_via_pydantic(self):
        scenario = Scenario.load_from_file(SCENARIO_PATH)
        assert scenario.id == "calloused_prologue"
        assert scenario.version == "3.2.0"
        assert scenario.calibration_node is None

    def test_prologue_close_has_crystallize_on_enter(self):
        data = _load_prologue()
        on_enter = data["nodes"]["prologue_close"].get("on_enter", [])
        types = [c["type"] for c in on_enter]
        assert "crystallize_stats" in types

    def test_crystallize_is_last_on_enter_consequence(self):
        """Flags must be set before stats crystallize."""
        data = _load_prologue()
        on_enter = data["nodes"]["prologue_close"]["on_enter"]
        assert on_enter[-1]["type"] == "crystallize_stats"

    def test_all_stat_weight_keys_are_valid_stats(self):
        data = _load_prologue()
        errors = []
        for node_key, node in data["nodes"].items():
            for action in node.get("actions", []):
                for stat in action.get("stat_weights", {}).keys():
                    if stat not in VALID_STATS:
                        errors.append(
                            f"Node '{node_key}' action '{action['id']}' "
                            f"invalid stat_weight key '{stat}'"
                        )
        assert not errors, "\n".join(errors)

    def test_all_stat_weights_are_positive(self):
        data = _load_prologue()
        errors = []
        for node_key, node in data["nodes"].items():
            for action in node.get("actions", []):
                for stat, weight in action.get("stat_weights", {}).items():
                    if not isinstance(weight, (int, float)) or weight <= 0:
                        errors.append(
                            f"Node '{node_key}' action '{action['id']}' "
                            f"stat '{stat}' has non-positive weight {weight!r}"
                        )
        assert not errors, "\n".join(errors)

    def test_all_six_stats_appear_in_weights(self):
        """Every ability score must be weighted somewhere — no dead stat."""
        data = _load_prologue()
        covered: set[str] = set()
        for node in data["nodes"].values():
            for action in node.get("actions", []):
                covered.update(action.get("stat_weights", {}).keys())
        missing = VALID_STATS - covered
        assert not missing, f"Stats never weighted in any action: {missing}"

    def test_charisma_on_at_least_two_social_actions(self):
        data = _load_prologue()
        hits = [
            (nk, a["id"])
            for nk, n in data["nodes"].items()
            for a in n.get("actions", [])
            if "charisma" in a.get("stat_weights", {})
        ]
        assert len(hits) >= 2, f"charisma only on: {hits}"

    def test_strength_on_at_least_one_physical_action(self):
        data = _load_prologue()
        hits = [
            (nk, a["id"])
            for nk, n in data["nodes"].items()
            for a in n.get("actions", [])
            if "strength" in a.get("stat_weights", {})
        ]
        assert len(hits) >= 1, "strength never weighted"

    def test_wisdom_on_multiple_actions(self):
        data = _load_prologue()
        hits = [
            (nk, a["id"])
            for nk, n in data["nodes"].items()
            for a in n.get("actions", [])
            if "wisdom" in a.get("stat_weights", {})
        ]
        assert len(hits) >= 4, f"expected wisdom on many actions, found: {hits}"

    def test_stat_weights_survive_pydantic_round_trip(self):
        scenario = Scenario.load_from_file(SCENARIO_PATH)
        errors = []
        for node_id, node in scenario.nodes.items():
            for action in node.actions:
                for stat in action.stat_weights:
                    if stat not in VALID_STATS:
                        errors.append(f"Node '{node_id}' action '{action.id}' invalid stat '{stat}'")
        assert not errors, "\n".join(errors)

    def test_prologue_close_crystallize_via_pydantic(self):
        scenario = Scenario.load_from_file(SCENARIO_PATH)
        node = scenario.nodes["prologue_close"]
        types = [c.type for c in node.on_enter]
        assert "crystallize_stats" in types

    def test_specific_actions_have_expected_weights(self):
        """Spot-check a representative sample of authored stat_weights."""
        data = _load_prologue()

        def get_weight(node_id, action_id, stat):
            node = data["nodes"][node_id]
            for a in node["actions"]:
                if a["id"] == action_id:
                    return a.get("stat_weights", {}).get(stat)
            return None

        cases = [
            # (node, action, stat, expected_weight)
            ("crater_investigation", "read_the_ground", "wisdom", 2.0),
            ("crater_investigation", "call_to_lo", "charisma", 1.5),
            ("the_dark", "charge_at_it", "strength", 2.5),
            ("the_dark", "go_still", "wisdom", 2.5),
            ("the_dark", "slip_through", "dexterity", 2.0),
            ("the_dark", "find_the_panel", "intelligence", 2.5),
            ("the_dark", "probe_with_sound", "wisdom", 1.5),
            ("console_chamber", "study_the_terminal", "intelligence", 2.0),
            ("console_chamber", "speak_to_the_system", "charisma", 1.5),
            ("terminal_resistance", "take_fragment", "dexterity", 0.5),
            ("terminal_resistance", "leave", "constitution", 0.5),
            ("the_ascent", "surface", "constitution", 1.0),
            ("the_ascent", "look_back_down", "wisdom", 1.0),
            ("lo_aftermath", "tell_lo_what_you_found", "charisma", 2.0),
            ("lo_aftermath", "say_nothing", "wisdom", 0.5),
            ("lo_aftermath", "stand_alone", "constitution", 0.5),
            ("lo_aftermath", "watch_lo", "wisdom", 1.0),
            ("lo_face", "tell_what_you_found", "charisma", 2.0),
            ("lo_face", "say_nothing", "wisdom", 0.5),
        ]
        errors = []
        for node_id, action_id, stat, expected in cases:
            actual = get_weight(node_id, action_id, stat)
            if actual != expected:
                errors.append(
                    f"{node_id}.{action_id}[{stat}]: expected {expected}, got {actual}"
                )
        assert not errors, "\n".join(errors)

    def test_lo_aftermath_tell_has_higher_charisma_weight_than_say_nothing(self):
        data = _load_prologue()

        def get_weight(node_id, action_id, stat):
            for a in data["nodes"][node_id]["actions"]:
                if a["id"] == action_id:
                    return a.get("stat_weights", {}).get(stat, 0.0)
            return 0.0

        tell_cha = get_weight("lo_aftermath", "tell_lo_what_you_found", "charisma")
        say_wis = get_weight("lo_aftermath", "say_nothing", "wisdom")
        assert tell_cha > say_wis  # telling is a stronger charisma signal than silence is wisdom

    def test_lo_face_and_lo_aftermath_mirror_charisma_weights(self):
        """lo_face is a detour from lo_aftermath; both paths to prologue_close
        should give equal charisma weight for choosing to tell the truth."""
        data = _load_prologue()

        def get_weight(node_id, action_id, stat):
            for a in data["nodes"][node_id]["actions"]:
                if a["id"] == action_id:
                    return a.get("stat_weights", {}).get(stat, 0.0)
            return 0.0

        aftermath_tell = get_weight("lo_aftermath", "tell_lo_what_you_found", "charisma")
        face_tell = get_weight("lo_face", "tell_what_you_found", "charisma")
        assert aftermath_tell == face_tell == 2.0
