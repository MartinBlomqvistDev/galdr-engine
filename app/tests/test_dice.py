"""Tester för RPG-mekanik."""

from galdr.core.dice import (
    DiceType,
    DifficultyClass,
    contested_check,
    damage_roll,
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


def _roll_sequence(seed: int | None) -> list[int]:
    state = GameState(rng_seed=seed)
    totals = [skill_check(state, Ability.WISDOM, dc=12).roll.rolls[0] for _ in range(20)]
    contest = contested_check(state, Ability.STRENGTH, opponent_modifier=2)
    totals += [contest["player_roll"].rolls[0], contest["opponent_roll"].rolls[0]]
    totals += damage_roll(DiceType.D6, count=4, rng=state.rng).rolls
    return totals


def test_same_seed_same_sequence():
    assert _roll_sequence(42) == _roll_sequence(42)


def test_different_seeds_differ():
    assert _roll_sequence(42) != _roll_sequence(43)


def test_seed_survives_serialisation():
    state = GameState(rng_seed=7)
    restored = GameState.model_validate_json(state.model_dump_json())
    assert restored.rng_seed == 7
    assert restored.rng.random() == GameState(rng_seed=7).rng.random()


def test_roll_dice_uses_given_rng():
    import random
    a = roll_dice(DiceType.D20, count=5, rng=random.Random(1))
    b = roll_dice(DiceType.D20, count=5, rng=random.Random(1))
    assert a.rolls == b.rolls
