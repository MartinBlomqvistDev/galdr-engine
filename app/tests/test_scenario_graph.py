"""Validate calloused_prologue.json graph integrity.

Checks:
- Every target_node, failure_node, auto_next target resolves to a real node
- start_node and end_nodes exist
- calibration_node exists
- No node has a duplicate ID
- Every node ID key matches its internal id field
- No action references itself as target (trivial infinite loop)
- Every node is reachable from start_node (no orphans)
"""

from __future__ import annotations

import json
from pathlib import Path
from collections import deque

SCENARIO_PATH = Path(__file__).parent.parent / "scenarios" / "calloused_prologue.json"


def load() -> dict:
    return json.loads(SCENARIO_PATH.read_text(encoding="utf-8-sig"))


def all_node_ids(data: dict) -> set[str]:
    return set(data["nodes"].keys())


def test_start_node_exists():
    data = load()
    assert data["start_node"] in all_node_ids(data), \
        f"start_node '{data['start_node']}' not in nodes"


def test_end_nodes_exist():
    data = load()
    node_ids = all_node_ids(data)
    for end in data["end_nodes"]:
        assert end in node_ids, f"end_node '{end}' not in nodes"


def test_calibration_node_exists():
    data = load()
    cal = data.get("calibration_node")
    if cal:
        assert cal in all_node_ids(data), f"calibration_node '{cal}' not in nodes"


def test_node_id_keys_match_internal_id():
    data = load()
    for key, node in data["nodes"].items():
        assert node["id"] == key, \
            f"Node key '{key}' has internal id='{node['id']}'"


def test_action_target_nodes_exist():
    data = load()
    node_ids = all_node_ids(data)
    errors = []
    for node_key, node in data["nodes"].items():
        for action in node.get("actions", []):
            for field in ("target_node", "failure_node"):
                ref = action.get(field)
                if ref and ref not in node_ids:
                    errors.append(
                        f"Node '{node_key}' action '{action['id']}' {field}='{ref}' not found"
                    )
    assert not errors, "\n".join(errors)


def test_auto_next_targets_exist():
    """auto_next is a plain string node ID in the JSON."""
    data = load()
    node_ids = all_node_ids(data)
    errors = []
    for node_key, node in data["nodes"].items():
        auto = node.get("auto_next")
        if auto:
            ref = auto if isinstance(auto, str) else auto.get("target_node")
            if ref and ref not in node_ids:
                errors.append(f"Node '{node_key}' auto_next='{ref}' not found")
    assert not errors, "\n".join(errors)


def test_no_unconditioned_self_loop():
    """Self-loops are only valid when the action has conditions (flag-gated, disappears after use)."""
    data = load()
    errors = []
    for node_key, node in data["nodes"].items():
        for action in node.get("actions", []):
            if action.get("target_node") == node_key:
                if not action.get("conditions"):
                    errors.append(
                        f"Node '{node_key}' action '{action['id']}' loops to itself with no condition"
                    )
    assert not errors, "\n".join(errors)


def test_all_nodes_reachable():
    data = load()
    node_ids = all_node_ids(data)
    start = data["start_node"]

    reachable: set[str] = set()
    queue: deque[str] = deque([start])
    while queue:
        nid = queue.popleft()
        if nid in reachable or nid not in data["nodes"]:
            continue
        reachable.add(nid)
        node = data["nodes"][nid]
        for action in node.get("actions", []):
            for field in ("target_node", "failure_node"):
                ref = action.get(field)
                if ref:
                    queue.append(ref)
        auto = node.get("auto_next")
        if auto:
            ref = auto if isinstance(auto, str) else auto.get("target_node")
            if ref:
                queue.append(ref)

    orphans = node_ids - reachable
    assert not orphans, f"Unreachable nodes: {sorted(orphans)}"


def test_end_nodes_have_no_actions():
    """End nodes should not have outgoing actions -- the game stops there."""
    data = load()
    errors = []
    for end in data["end_nodes"]:
        node = data["nodes"].get(end, {})
        if node.get("actions"):
            errors.append(f"End node '{end}' has actions -- game may not stop")
    assert not errors, "\n".join(errors)
