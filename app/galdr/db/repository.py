"""Persistence layer — in-memory for the PoC, PostgreSQL-ready.

InMemoryRepository holds sessions in a dict; fine for a single process.
FileRepository serialises to JSON per session; useful for development and
demos where you want state to survive a server restart.
PostgreSQL via SQLAlchemy is the production target but hasn't been added
yet — scenario content needs to stabilise before the schema is worth committing to.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from galdr.core.state import GameState

logger = logging.getLogger(__name__)


class InMemoryRepository:
    """Session store backed by a plain dict."""

    def __init__(self):
        self._sessions: dict[str, GameState] = {}

    async def save(self, state: GameState) -> None:
        self._sessions[state.session_id] = state

    async def load(self, session_id: str) -> GameState | None:
        return self._sessions.get(session_id)

    async def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    async def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())


class FileRepository:
    """Session store backed by JSON files — one file per session."""

    def __init__(self, storage_dir: str = "./data/sessions"):
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    async def save(self, state: GameState) -> None:
        path = self._dir / f"{state.session_id}.json"
        path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        logger.debug(f"Session saved: {path}")

    async def load(self, session_id: str) -> GameState | None:
        path = self._dir / f"{session_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return GameState.model_validate(data)

    async def delete(self, session_id: str) -> None:
        path = self._dir / f"{session_id}.json"
        if path.exists():
            path.unlink()

    async def list_sessions(self) -> list[str]:
        return [p.stem for p in self._dir.glob("*.json")]
