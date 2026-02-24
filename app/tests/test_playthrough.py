"""End-to-end playthrough av Ekokammaren utan GPS och utan API-nyckel."""

import asyncio
from pathlib import Path

import pytest

from galdr.core.engine import GaldrEngine
from galdr.core.nodes import Scenario


@pytest.fixture
def engine():
    scenario_path = Path(__file__).parent.parent / "scenarios" / "ekokammaren.json"
    scenario = Scenario.load_from_file(scenario_path)
    return GaldrEngine(scenario)


@pytest.mark.asyncio
async def test_full_playthrough_light_ending(engine):
    """Spela igenom hela scenariot till ljust slut."""
    state = engine.create_session("Testare")
    sid = state.session_id

    # 1. Stortorget – enter
    r = await engine.enter_node(sid)
    assert "stortorget" in r.node_id
    assert r.text  # Ska ha opening text
    assert len(r.available_actions) >= 2

    # 2. Acceptera uppdraget (action 1 = "Ja, jag lyssnar")
    r = await engine.process_input(sid, "1")
    state = engine.get_session(sid)
    assert state.narrative_flags.check("accepted_quest", True)
    assert any(i.name == "Ekots fragment" for i in state.character.inventory)

    # Borde ha bytt till radhuset
    assert state.current_node_id == "radhuset"

    # 3. Rådhuset – enter
    r = await engine.enter_node(sid)
    assert r.text
    assert len(r.available_actions) >= 1

    # 4. Fråga Ekot (action 2 – wisdom check DC 10)
    r = await engine.process_input(sid, "2")
    state = engine.get_session(sid)
    # Oavsett dice-resultat ska vi hamna på lilla_torg
    assert state.current_node_id == "lilla_torg"

    # 5. Lilla Torg – enter
    r = await engine.enter_node(sid)
    assert r.text
    assert len(r.available_actions) >= 2

    # 6. Följ den sjungande kvinnan (action 1)
    r = await engine.process_input(sid, "1")
    state = engine.get_session(sid)
    assert state.narrative_flags.check("followed_singer", True)
    assert state.current_node_id == "kanalen"

    # 7. Kanalen – enter
    r = await engine.enter_node(sid)
    assert r.text
    assert len(r.available_actions) == 2  # Två slutval

    # 8. Släpp minnena (ljust slut)
    r = await engine.process_input(sid, "1")
    state = engine.get_session(sid)
    assert state.narrative_flags.check("ending", "ljus")
    assert state.current_node_id == "slutet_ljus"


@pytest.mark.asyncio
async def test_full_playthrough_dark_ending(engine):
    """Spela igenom till mörkt slut (vägra hjälpa)."""
    state = engine.create_session("Skeptikern")
    sid = state.session_id

    # 1. Enter Stortorget
    await engine.enter_node(sid)

    # 2. Vägra hjälpa (action 3)
    r = await engine.process_input(sid, "3")
    state = engine.get_session(sid)
    # Ska hamna på stortorget_night
    assert state.current_node_id == "stortorget_night"

    # 3. Enter stortorget_night
    r = await engine.enter_node(sid)
    assert len(r.available_actions) == 2

    # 4. Gå därifrån (action 2)
    r = await engine.process_input(sid, "2")
    state = engine.get_session(sid)
    assert state.current_node_id == "slutet_mörker"
    assert state.narrative_flags.check("ending", "mörker")


@pytest.mark.asyncio
async def test_skill_check_path(engine):
    """Testa stigen med skill check."""
    state = engine.create_session("Sökaren")
    sid = state.session_id

    await engine.enter_node(sid)

    # Charisma check ("Vem är du egentligen?", DC 10)
    r = await engine.process_input(sid, "2")
    state = engine.get_session(sid)

    # Oavsett resultat ska vi ha gått vidare
    assert r.dice_result is not None
    assert r.dice_result.ability.value == "charisma"
    assert r.dice_result.dc == 10

    # Vid framgång → radhuset, vid misslyckande → stortorget_night
    assert state.current_node_id in ("radhuset", "stortorget_night")


@pytest.mark.asyncio
async def test_natural_language_input(engine):
    """Testa att naturligt språk matchas till actions."""
    state = engine.create_session("Vandrare")
    sid = state.session_id

    await engine.enter_node(sid)

    # "ja" ska matcha första actionen
    r = await engine.process_input(sid, "ja")
    state = engine.get_session(sid)
    assert state.narrative_flags.check("accepted_quest", True)


@pytest.mark.asyncio
async def test_keyword_matching(engine):
    """Testa keyword-baserad matching."""
    state = engine.create_session("Test")
    sid = state.session_id

    await engine.enter_node(sid)

    # "lyssna" matchar "Ja, jag lyssnar" (accept_quest) via starts-with
    r = await engine.process_input(sid, "lyssna")
    state = engine.get_session(sid)
    assert state.narrative_flags.check("accepted_quest", True)

    # "vem" matchar "Vem är du egentligen?" i en ny session
    state2 = engine.create_session("Test2")
    await engine.enter_node(state2.session_id)
    r2 = await engine.process_input(state2.session_id, "vem")
    assert r2.dice_result is not None  # Charisma check


@pytest.mark.asyncio
async def test_inventory_accumulation(engine):
    """Testa att föremål samlas korrekt."""
    state = engine.create_session("Samlaren")
    sid = state.session_id

    await engine.enter_node(sid)

    # Acceptera → får Ekots fragment
    await engine.process_input(sid, "1")
    state = engine.get_session(sid)
    assert len(state.character.inventory) == 1

    # Gå till Lilla Torg (via Rådhuset)
    await engine.enter_node(sid)
    await engine.process_input(sid, "2")  # Fråga Ekot

    await engine.enter_node(sid)
    await engine.process_input(sid, "1")  # Följ sångerskan → Melodifragment
    state = engine.get_session(sid)
    assert any(i.name == "Melodifragment" for i in state.character.inventory)


@pytest.mark.asyncio
async def test_no_gps_required(engine):
    """Bekräfta att hela flödet fungerar utan GPS-koordinater."""
    state = engine.create_session("Hemma")
    sid = state.session_id

    assert state.player_lat is None
    assert state.player_lon is None

    # Hela flödet utan GPS
    await engine.enter_node(sid)
    await engine.process_input(sid, "1")
    await engine.enter_node(sid)
    await engine.process_input(sid, "2")
    await engine.enter_node(sid)
    await engine.process_input(sid, "1")
    await engine.enter_node(sid)
    r = await engine.process_input(sid, "1")

    state = engine.get_session(sid)
    assert state.current_node_id == "slutet_ljus"
    assert state.player_lat is None  # Aldrig satt GPS
