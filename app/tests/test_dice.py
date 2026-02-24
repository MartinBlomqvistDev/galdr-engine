"""Tester för RPG-mekanik."""

from galdr.core.dice import (
    DiceType,
    DifficultyClass,
    roll_dice,
    skill_check,
)
from galdr.core.state import Ability, GameState


def test_roll_d20():
    result = roll_dice(DiceType.D20)
    assert 1 <= result.total <= 20
    assert len(result.rolls) == 1


def test_roll_multiple_dice():
    result = roll_dice(DiceType.D6, count=3)
    assert 3 <= result.total <= 18
    assert len(result.rolls) == 3


def test_roll_with_modifier():
    result = roll_dice(DiceType.D20, modifier=5)
    assert 6 <= result.total <= 25


def test_natural_20():
    # Kör tillräckligt många gånger för att statistiskt träffa nat 20
    found_nat20 = False
    for _ in range(1000):
        result = roll_dice(DiceType.D20)
        if result.natural_20:
            found_nat20 = True
            assert result.rolls[0] == 20
            break
    assert found_nat20, "Ingen nat 20 på 1000 slag"


def test_skill_check_success():
    state = GameState()
    state.character.stats.charisma = 20  # +5 modifier
    # Med +5 och d20 (1-20) → total 6-25 mot DC 5 → alltid framgång
    result = skill_check(state, Ability.CHARISMA, dc=5)
    assert result.success is True


def test_skill_check_modifiers():
    state = GameState()
    state.character.stats.strength = 16  # +3 modifier
    result = skill_check(state, Ability.STRENGTH, dc=10)
    assert result.ability_modifier == 3
    assert result.total == result.roll.rolls[0] + 3


def test_skill_check_narrative_quality():
    """Kontrollera att narrative_quality sätts korrekt."""
    state = GameState()
    qualities = set()
    for _ in range(200):
        result = skill_check(state, Ability.WISDOM, dc=12)
        qualities.add(result.narrative_quality)
    # Vi borde se åtminstone några olika kvaliteter
    assert len(qualities) >= 2


def test_difficulty_class_values():
    assert DifficultyClass.EASY == 10
    assert DifficultyClass.MEDIUM == 15
    assert DifficultyClass.HARD == 20
