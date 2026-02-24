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
        description="Minimalt demo-scenario",
        global_system_prompt=(
            "Du är en mystisk berättare i en nordisk fantasivärld. "
            "Tala poetiskt men tydligt. Driv berättelsen framåt."
        ),
        start_node="start",
        nodes={
            "start": NarrativeNode(
                id="start",
                title="Skogens kant",
                description="Spelaren börjar vid kanten av en mörk skog",
                system_prompt=(
                    "Spelaren står vid kanten av en urgammal skog. "
                    "Det är skymning. Dimma kryper mellan stammarna. "
                    "Beskriv scenen atmosfäriskt och bjud in spelaren."
                ),
                opening_text=(
                    "Du står vid skogens gräns. Gamla tallar reser sig som "
                    "mörka pelare mot den bleknade himlen. Dimman kryper långsamt "
                    "runt dina fötter, och någonstans djupt bland träden hör du "
                    "ett svagt ljud... som en viskning."
                ),
                voice=VoiceParams(
                    character_name="Berättaren",
                    emotion="mystisk",
                    style="narrator",
                ),
                actions=[
                    NodeAction(
                        id="enter_forest",
                        label="Gå in i skogen",
                        description="Följ viskningarna in bland träden",
                        target_node="forest",
                    ),
                    NodeAction(
                        id="listen",
                        label="Lyssna på viskningarna",
                        description="Stanna och försök urskilja vad viskningarna säger",
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
    ai_service = OpenAIService(
        api_key=settings.openai_api_key, 
        model=settings.openai_model
    )

    scenario = load_scenario()
    engine = GaldrEngine(
        scenario=scenario,
        llm=ai_service,
        tts=ai_service
    )
    set_engine(engine)

    logger.info(f"Scenario loaded: {scenario.title} ({len(scenario.nodes)} nodes)")
    logger.info(f"API: http://{settings.host}:{settings.port}")
    logger.info(f"Docs: http://{settings.host}:{settings.port}/docs")

    if not settings.openai_api_key:
        logger.warning("No OPENAI_API_KEY — running in offline mode (scripted responses, no TTS)")

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
