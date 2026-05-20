"""GALDR Engine — FastAPI application entry point.

Run with:
    uvicorn galdr.main:app --reload

Or:
    python -m galdr.main
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from galdr.api.middleware import TelemetryMiddleware
from galdr.api.routes import router, set_engine
from galdr.api.websocket import handle_websocket
from galdr.config import settings
from galdr.core.engine import GaldrEngine
from galdr.core.nodes import Scenario
from galdr.services.openai_service import OpenAIService
from galdr.services.azure_service import AzureOpenAIService, AzureSpeechTTSService

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

engine: GaldrEngine | None = None


def load_scenario() -> Scenario:
    """Load the Ekokammaren scenario, or fall back to a minimal demo."""
    scenario_path = Path(__file__).parent.parent / "scenarios" / "ekokammaren.json"
    if scenario_path.exists():
        logger.info(f"Loading scenario: {scenario_path}")
        return Scenario.load_from_file(scenario_path)

    logger.warning("No scenario found — creating minimal demo scenario")
    return _create_minimal_scenario()


def _create_minimal_scenario() -> Scenario:
    """Fallback one-node scenario for testing without the full JSON file."""
    from galdr.core.nodes import (
        Condition,
        Consequence,
        NarrativeNode,
        NodeAction,
        VoiceParams,
    )
    from galdr.core.state import Ability

    return Scenario(
        id="demo",
        title="GALDR Demo",
        description="Minimal demo scenario — forest edge at dusk.",
        global_system_prompt=(
            "You are a narrator in a northern wilderness setting. "
            "Speak with atmosphere and economy. Drive the story forward."
        ),
        start_node="start",
        nodes={
            "start": NarrativeNode(
                id="start",
                title="The Forest Edge",
                description="Player begins at the edge of a dark forest at dusk.",
                system_prompt=(
                    "Player stands at the edge of an ancient forest at dusk. "
                    "Fog moves between the trunks. Describe atmospherically and invite the player in."
                ),
                opening_text=(
                    "You stand at the tree line. Old pines rise like dark pillars "
                    "against the fading sky. Fog creeps around your feet, and somewhere "
                    "deep among the trees you hear something faint — like a whisper."
                ),
                voice=VoiceParams(
                    character_name="Narrator",
                    emotion="mysterious",
                    style="narrator",
                ),
                actions=[
                    NodeAction(
                        id="enter_forest",
                        label="Walk into the forest",
                        description="Follow the whispers in among the trees.",
                        target_node="forest",
                    ),
                    NodeAction(
                        id="listen",
                        label="Listen to the whispers",
                        description="Stay still and try to make out what the whispers are saying.",
                        skill_check=Ability.WISDOM,
                        dc=12,
                        target_node="forest_aware",
                        failure_node="forest",
                        consequences=[
                            Consequence(type="set_flag", key="heard_whispers", value=True),
                        ],
                    ),
                ],
            ),
        },
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    logger.info("=== GALDR Engine starting ===")

    # Service initialization (Dependency Injection)
    if settings.use_azure:
        logger.info("Azure mode: using AzureOpenAIService + AzureSpeechTTSService")
        llm_service = AzureOpenAIService(
            api_key=settings.azure_openai_api_key,
            endpoint=settings.azure_openai_endpoint,
            deployment=settings.azure_openai_deployment,
            api_version=settings.azure_openai_api_version,
        )
        tts_service = AzureSpeechTTSService(
            key=settings.azure_speech_key,
            region=settings.azure_speech_region,
        )
    else:
        logger.info("OpenAI mode: using OpenAIService")
        ai_service = OpenAIService(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
        llm_service = ai_service
        tts_service = ai_service

    scenario = load_scenario()
    engine = GaldrEngine(
        scenario=scenario,
        llm=llm_service,
        tts=tts_service,
    )
    set_engine(engine)

    logger.info(f"Scenario loaded: {scenario.title} ({len(scenario.nodes)} nodes)")
    logger.info(f"API: http://{settings.host}:{settings.port}")
    logger.info(f"Docs: http://{settings.host}:{settings.port}/docs")

    if not settings.use_azure and not settings.openai_api_key:
        logger.warning("No API keys found — running in offline mode (scripted responses, no TTS)")

    yield

    logger.info("=== GALDR Engine shutting down ===")


app = FastAPI(
    title="GALDR Engine",
    description="Voice-based narrative engine for interactive storytelling",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TelemetryMiddleware)

app.include_router(router)

# Serve the browser client from /static if the directory exists
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(str(static_dir / "index.html"))


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    if engine is None:
        await websocket.close(code=1011, reason="Engine not ready")
        return
    await handle_websocket(websocket, session_id, engine)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "galdr.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
