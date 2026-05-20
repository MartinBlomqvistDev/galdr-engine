"""Checkpoint persistence — Neural Sync save/load."""

from __future__ import annotations

import logging
from pathlib import Path

from galdr.core.state import GameState

logger = logging.getLogger(__name__)

_SAVES_DIR = Path(__file__).parent.parent.parent / "saves"


def _save_path(scenario_id: str) -> Path:
    return _SAVES_DIR / f"{scenario_id}.json"


def save_checkpoint(state: GameState, scenario_id: str) -> None:
    _SAVES_DIR.mkdir(parents=True, exist_ok=True)
    path = _save_path(scenario_id)
    path.write_text(state.model_dump_json(), encoding="utf-8")
    logger.info("[CHECKPOINT] Saved to %s (node=%s)", path.name, state.current_node_id)


def load_checkpoint(scenario_id: str) -> GameState | None:
    path = _save_path(scenario_id)
    if not path.exists():
        return None
    try:
        state = GameState.model_validate_json(path.read_text(encoding="utf-8"))
        logger.info("[CHECKPOINT] Loaded from %s (node=%s)", path.name, state.current_node_id)
        return state
    except Exception as e:
        logger.warning("[CHECKPOINT] Failed to load %s: %s", path.name, e)
        return None


def delete_checkpoint(scenario_id: str) -> None:
    path = _save_path(scenario_id)
    if path.exists():
        path.unlink()
        logger.info("[CHECKPOINT] Deleted %s", path.name)


def checkpoint_exists(scenario_id: str) -> bool:
    return _save_path(scenario_id).exists()
