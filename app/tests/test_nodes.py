"""Tests for the narrative node system."""

import json

from galdr.core.nodes import (
    Condition,
    Consequence,
    NarrativeNode,
    NodeAction,
    Scenario,
    VoiceParams,
)
from galdr.core.state import Ability, GameState, InventoryItem


def test_condition_flag():
    state = GameState()
    state.narrative_flags.set_flag("met_elder", True)

    cond = Condition(type="flag", key="met_elder", value=True)
    assert cond.evaluate(state) is True

    cond_false = Condition(type="flag", key="met_elder", value=False)
    assert cond_false.evaluate(state) is False


def test_condition_stat():
    state = GameState()
    state.character.stats.charisma = 14

    cond = Condition(type="stat", ability="charisma", min=12)
    assert cond.evaluate(state) is True

    cond_high = Condition(type="stat", ability="charisma", min=16)
    assert cond_high.evaluate(state) is False


def test_condition_item():
    state = GameState()
    state.character.inventory.append(InventoryItem(name="Nyckel"))

    cond = Condition(type="item", item_name="Nyckel")
    assert cond.evaluate(state) is True

    cond_no = Condition(type="item", item_name="Svärd")
    assert cond_no.evaluate(state) is False


def test_condition_visited():
    state = GameState()
    state.visit_location("torget", "Stortorget")

    cond = Condition(type="visited", location="torget")
    assert cond.evaluate(state) is True

    cond_no = Condition(type="visited", location="hamnen")
    assert cond_no.evaluate(state) is False


def test_consequence_set_flag():
    state = GameState()
    cons = Consequence(type="set_flag", key="quest_done", value=True)
    cons.apply(state)
    assert state.narrative_flags.check("quest_done", True)


def test_consequence_add_item():
    state = GameState()
    cons = Consequence(type="add_item", item_name="Svärd", item_description="Rostigt")
    cons.apply(state)
    assert len(state.character.inventory) == 1
    assert state.character.inventory[0].name == "Svärd"


def test_consequence_modify_hp():
    state = GameState()
    state.character.hp = 20

    cons_damage = Consequence(type="modify_hp", amount=-5)
    cons_damage.apply(state)
    assert state.character.hp == 15

    cons_heal = Consequence(type="modify_hp", amount=3)
    cons_heal.apply(state)
    assert state.character.hp == 18


def test_consequence_hp_clamp():
    state = GameState()
    state.character.hp = 2

    cons = Consequence(type="modify_hp", amount=-10)
    cons.apply(state)
    assert state.character.hp == 0  # Ej negativt


def test_node_available_actions():
    state = GameState()

    node = NarrativeNode(
        id="test",
        title="Test",
        description="Test node",
        actions=[
            NodeAction(
                id="open_door",
                label="Öppna dörren",
                conditions=[Condition(type="item", item_name="Nyckel")],
                target_node="next",
            ),
            NodeAction(
                id="knock",
                label="Knacka på",
                target_node="next",
            ),
        ],
    )

    # Utan nyckel: bara "knacka" tillgänglig
    available = node.get_available_actions(state)
    assert len(available) == 1
    assert available[0].id == "knock"

    # Med nyckel: båda tillgängliga
    state.character.inventory.append(InventoryItem(name="Nyckel"))
    available = node.get_available_actions(state)
    assert len(available) == 2


def test_scenario_load_save(tmp_path):
    scenario = Scenario(
        id="test",
        title="Test Scenario",
        description="Ett test",
        start_node="start",
        nodes={
            "start": NarrativeNode(
                id="start",
                title="Start",
                description="Startnod",
                opening_text="Välkommen!",
            ),
        },
    )

    path = tmp_path / "test.json"
    scenario.save_to_file(path)

    loaded = Scenario.load_from_file(path)
    assert loaded.id == "test"
    assert loaded.title == "Test Scenario"
    assert "start" in loaded.nodes
    assert loaded.nodes["start"].opening_text == "Välkommen!"
