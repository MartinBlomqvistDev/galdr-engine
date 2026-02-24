"""Tester för state management."""

from galdr.core.state import (
    Ability,
    Character,
    CharacterStats,
    GameState,
    InventoryItem,
)


def test_ability_modifier():
    stats = CharacterStats(strength=16, dexterity=8)
    assert stats.modifier(Ability.STRENGTH) == 3   # (16-10)//2
    assert stats.modifier(Ability.DEXTERITY) == -1  # (8-10)//2


def test_ability_modifier_ten():
    stats = CharacterStats()
    assert stats.modifier(Ability.STRENGTH) == 0  # (10-10)//2


def test_character_defaults():
    char = Character()
    assert char.name == "Äventyrare"
    assert char.hp == 20
    assert char.level == 1
    assert len(char.inventory) == 0


def test_game_state_record_dialog():
    state = GameState()
    state.record_dialog("player", "Hej!")
    state.record_dialog("Ekot", "Välkommen, vandrare.")
    assert len(state.dialog_history) == 2
    assert state.turn_count == 2
    assert state.dialog_history[0].speaker == "player"


def test_game_state_visit_location():
    state = GameState()
    state.visit_location("torget", "Stortorget")
    assert "torget" in state.world.locations
    assert state.world.locations["torget"].visited is True
    assert state.world.locations["torget"].visit_count == 1

    state.visit_location("torget", "Stortorget")
    assert state.world.locations["torget"].visit_count == 2


def test_narrative_flags():
    state = GameState()
    state.narrative_flags.set_flag("met_elder", True)
    assert state.narrative_flags.check("met_elder", True) is True
    assert state.narrative_flags.check("met_elder", False) is False
    assert state.narrative_flags.get_flag("nonexistent", "default") == "default"


def test_get_recent_context():
    state = GameState()
    for i in range(15):
        state.record_dialog("player", f"Message {i}")
    recent = state.get_recent_context(5)
    assert len(recent) == 5
    assert recent[0].text == "Message 10"


def test_state_serialization():
    state = GameState()
    state.character.name = "Sigurd"
    state.character.inventory.append(InventoryItem(name="Svärd", description="Gammalt"))
    state.narrative_flags.set_flag("quest_started", True)

    # Serialisera och deserialisera
    json_str = state.model_dump_json()
    restored = GameState.model_validate_json(json_str)

    assert restored.character.name == "Sigurd"
    assert len(restored.character.inventory) == 1
    assert restored.narrative_flags.check("quest_started", True)
