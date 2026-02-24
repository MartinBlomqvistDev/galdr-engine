"""REST API routes for the GALDR engine."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from galdr.core.engine import GaldrEngine

router = APIRouter(prefix="/api/v1", tags=["galdr"])

# Set by main.py at startup
_engine: GaldrEngine | None = None


def set_engine(engine: GaldrEngine) -> None:
    global _engine
    _engine = engine


def get_engine() -> GaldrEngine:
    if _engine is None:
        raise HTTPException(500, "Engine not initialised")
    return _engine


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    character_name: str = "Äventyrare"


class CreateSessionResponse(BaseModel):
    session_id: str
    character_name: str
    current_node: str


class PlayerInputRequest(BaseModel):
    text: str
    lat: float | None = None
    lon: float | None = None


class EngineResponseModel(BaseModel):
    text: str
    node_id: str
    available_actions: list[dict[str, str]]
    dice_result: dict | None = None
    state_changes: list[str]
    latency_ms: int
    has_audio: bool = False


class SessionStateResponse(BaseModel):
    session_id: str
    character_name: str
    hp: int
    max_hp: int
    current_node: str
    turn_count: int
    inventory: list[str]
    flags: dict


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
async def health():
    return {"status": "ok", "engine": "galdr", "version": "0.1.0"}


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(req: CreateSessionRequest):
    """Create a new game session."""
    engine = get_engine()
    state = engine.create_session(req.character_name)
    return CreateSessionResponse(
        session_id=state.session_id,
        character_name=state.character.name,
        current_node=state.current_node_id,
    )


@router.post("/sessions/{session_id}/enter", response_model=EngineResponseModel)
async def enter_current_node(session_id: str):
    """Trigger the current node's opening text."""
    engine = get_engine()
    response = await engine.enter_node(session_id)
    return EngineResponseModel(
        text=response.text,
        node_id=response.node_id,
        available_actions=response.available_actions,
        dice_result=response.dice_result.model_dump() if response.dice_result else None,
        state_changes=response.state_changes,
        latency_ms=response.latency_ms,
        has_audio=len(response.audio) > 0,
    )


@router.post("/sessions/{session_id}/input", response_model=EngineResponseModel)
async def process_input(session_id: str, req: PlayerInputRequest):
    """Submit player text input and receive the engine response."""
    engine = get_engine()
    response = await engine.process_input(session_id, req.text, req.lat, req.lon)
    return EngineResponseModel(
        text=response.text,
        node_id=response.node_id,
        available_actions=response.available_actions,
        dice_result=response.dice_result.model_dump() if response.dice_result else None,
        state_changes=response.state_changes,
        latency_ms=response.latency_ms,
        has_audio=len(response.audio) > 0,
    )


@router.get("/sessions/{session_id}/state", response_model=SessionStateResponse)
async def get_session_state(session_id: str):
    """Return a snapshot of the current session state."""
    engine = get_engine()
    state = engine.get_session(session_id)
    if not state:
        raise HTTPException(404, "Session not found")
    return SessionStateResponse(
        session_id=state.session_id,
        character_name=state.character.name,
        hp=state.character.hp,
        max_hp=state.character.max_hp,
        current_node=state.current_node_id,
        turn_count=state.turn_count,
        inventory=[i.name for i in state.character.inventory],
        flags=state.narrative_flags.flags,
    )


@router.get("/scenario")
async def get_scenario_info():
    """Return basic metadata about the loaded scenario."""
    engine = get_engine()
    s = engine.scenario
    return {
        "id": s.id,
        "title": s.title,
        "description": s.description,
        "node_count": len(s.nodes),
        "start_node": s.start_node,
    }
