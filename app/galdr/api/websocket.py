"""WebSocket handler for real-time communication.

Protocol (both sides use JSON):

  Client → Server:
    {"type": "text",       "text": "...", "lat": 55.6, "lon": 13.0}
    {"type": "audio",      "data": "<base64 opus>", "lat": ..., "lon": ...}
    {"type": "enter_node"}
    {"type": "state"}

  Server → Client:
    {"type": "response",   "text": "...", "node_id": "...", "actions": [...]}
    {"type": "audio",      "data": "<base64 opus>", "format": "opus"}
    {"type": "dice_roll",  "ability": "...", "roll": N, "dc": N, ...}
    {"type": "state",      "character": "...", "hp": N, ...}
    {"type": "error",      "message": "..."}
"""

from __future__ import annotations

import base64
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from galdr.core.engine import GaldrEngine
from galdr.voice.stt import STTEngine

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Tracks active WebSocket connections keyed by session_id."""

    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active[session_id] = websocket
        logger.info(f"WebSocket connected: {session_id}")

    def disconnect(self, session_id: str):
        self.active.pop(session_id, None)
        logger.info(f"WebSocket disconnected: {session_id}")

    async def send_json(self, session_id: str, data: dict):
        ws = self.active.get(session_id)
        if ws:
            await ws.send_json(data)


manager = ConnectionManager()


async def handle_websocket(
    websocket: WebSocket,
    session_id: str,
    engine: GaldrEngine,
):
    """Handle one WebSocket session — one connection per game session."""
    # Use the engine's STT service (injected at startup)
    # We cast it to STTService because GaldrEngine might use a multi-service
    from galdr.services.interfaces import STTService
    stt: STTService = engine.llm # OpenAIService implements both LLM and STT

    state = engine.get_session(session_id)
    if not state:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": "Session not found"})
        await websocket.close()
        return

    await manager.connect(websocket, session_id)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = msg.get("type", "text")

            if msg_type == "enter_node":
                response = await engine.enter_node(session_id)
                await _send_response(websocket, response)

            elif msg_type == "text":
                text = msg.get("text", "")
                lat = msg.get("lat")
                lon = msg.get("lon")
                response = await engine.process_input(session_id, text, lat, lon)
                await _send_response(websocket, response)

            elif msg_type == "audio":
                # Voice input — transcribe first, then process as text
                audio_b64 = msg.get("data", "")
                try:
                    audio_bytes = base64.b64decode(audio_b64)
                    text = await stt.transcribe(audio_bytes)
                    if text:
                        lat = msg.get("lat")
                        lon = msg.get("lon")
                        response = await engine.process_input(session_id, text, lat, lon)
                        await _send_response(websocket, response)
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Kunde inte transkribera ljudet",
                        })
                except Exception as e:
                    logger.error(f"Audio processing error: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Ljudbearbetning misslyckades",
                    })

            elif msg_type == "state":
                state = engine.get_session(session_id)
                if state:
                    await websocket.send_json({
                        "type": "state",
                        "character": state.character.name,
                        "hp": state.character.hp,
                        "node": state.current_node_id,
                        "turn": state.turn_count,
                    })

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(session_id)


async def _send_response(websocket: WebSocket, response) -> None:
    """Send engine response over the WebSocket — text first, audio separately."""
    payload: dict = {
        "type": "response",
        "text": response.text,
        "node_id": response.node_id,
        "actions": response.available_actions,
        "state_changes": response.state_changes,
        "latency_ms": response.latency_ms,
    }

    if response.dice_result:
        payload["dice_result"] = {
            "ability": response.dice_result.ability.value,
            "roll": response.dice_result.roll.total,
            "dc": response.dice_result.dc,
            "success": response.dice_result.success,
            "quality": response.dice_result.narrative_quality,
        }

    await websocket.send_json(payload)

    # Audio is sent as a separate message (keeps the JSON payload small)
    if response.audio:
        await websocket.send_json({
            "type": "audio",
            "data": base64.b64encode(response.audio).decode(),
            "format": "opus",
        })
