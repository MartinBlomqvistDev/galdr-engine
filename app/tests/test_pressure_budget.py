"""Pressure budget simulation for calloused_prologue.

Walks every possible path through the prologue graph and tracks pressure.
Design target: worst-case pressure at lo_aftermath is 4 (Gold Zone 4-6).
COLLAPSE condition (pressure >= 10) must be unreachable in the prologue.

Pressure sources (from scenario JSON):
  crater_investigation -> the_fall: +1 (fell_through consequence)
  the_dark charge_at_it FAIL -> dark_wounded: pressure in dark_wounded node
  the_dark find_the_panel FAIL -> dark_wounded: same
  cryo_room catalog_the_pods FAIL: +1 (overwhelm consequence)
  proximity_auth on_enter: +1

Dark_wounded itself may add pressure -- check on_enter consequences.
"""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, field

SCENARIO_PATH = Path(__file__).parent.parent / "scenarios" / "calloused_prologue.json"


def load():
    return json.loads(SCENARIO_PATH.read_text(encoding="utf-8-sig"))


def get_pressure_delta(node: dict) -> int:
    """Sum all modify_pressure consequences in on_enter for a node."""
    delta = 0
    for effect in node.get("on_enter", []):
        if effect.get("type") == "modify_pressure":
            delta += effect.get("amount", effect.get("value", 0))
    return delta


def get_action_pressure(action: dict, success: bool) -> int:
    """Sum modify_pressure consequences for an action outcome."""
    delta = 0
    key = "consequences" if success else "failure_consequences"
    for c in action.get(key, []):
        if c.get("type") == "modify_pressure":
            delta += c.get("amount", c.get("value", 0))
    return delta


@dataclass
class Path_:
    nodes: list[str] = field(default_factory=list)
    pressure: int = 0


def walk_paths(data: dict, start: str, end_nodes: set[str], max_depth: int = 30) -> list[Path_]:
    """BFS over all action outcomes. Returns completed paths."""
    completed = []
    queue: list[Path_] = [Path_(nodes=[start], pressure=0)]

    while queue:
        current = queue.pop()
        node_id = current.nodes[-1]

        if node_id not in data["nodes"]:
            continue
        node = data["nodes"][node_id]

        # Apply on_enter pressure for this node
        entry_pressure = get_pressure_delta(node)
        pressure = current.pressure + entry_pressure

        if node_id in end_nodes:
            completed.append(Path_(nodes=current.nodes[:], pressure=pressure))
            continue

        if len(current.nodes) > max_depth:
            # Guard against cycles
            continue

        actions = node.get("actions", [])
        auto = node.get("auto_next")

        if auto:
            target = auto if isinstance(auto, str) else auto.get("target_node")
            if target:
                queue.append(Path_(
                    nodes=current.nodes + [target],
                    pressure=pressure,
                ))
            continue

        if not actions:
            # Dead end (not an end node) -- flag this
            completed.append(Path_(nodes=current.nodes + ["[DEAD_END]"], pressure=pressure))
            continue

        for action in actions:
            # Success path
            success_target = action.get("target_node")
            if success_target:
                p_delta = get_action_pressure(action, success=True)
                queue.append(Path_(
                    nodes=current.nodes + [success_target],
                    pressure=pressure + p_delta,
                ))

            # Failure path (skill check actions)
            if action.get("skill_check") and action.get("failure_node"):
                fail_target = action["failure_node"]
                p_delta = get_action_pressure(action, success=False)
                queue.append(Path_(
                    nodes=current.nodes + [fail_target],
                    pressure=pressure + p_delta,
                ))

    return completed


def test_pressure_budget():
    data = load()
    end_nodes = set(data["end_nodes"])
    paths = walk_paths(data, data["start_node"], end_nodes)

    assert paths, "No completed paths found -- graph may be broken"

    pressures = [p.pressure for p in paths if "[DEAD_END]" not in p.nodes]
    dead_ends = [p for p in paths if "[DEAD_END]" in p.nodes]

    print(f"\n  Completed paths: {len(paths)}")
    print(f"  Dead ends: {len(dead_ends)}")
    print(f"  Pressure range: {min(pressures)} - {max(pressures)}")
    print(f"  Pressure values: {sorted(set(pressures))}")

    for p in dead_ends:
        print(f"  DEAD END path: {' -> '.join(p.nodes)}")

    assert not dead_ends, f"Dead end nodes found: {[p.nodes[-2] for p in dead_ends]}"
    assert max(pressures) < 10, f"Pressure can reach COLLAPSE ({max(pressures)}) in the prologue"
    assert max(pressures) <= 6, f"Pressure exceeds Gold Zone max of 6 ({max(pressures)})"

    # Check pressure at lo_aftermath specifically
    lo_aftermath_pressures = [
        p.pressure for p in paths
        if "lo_aftermath" in p.nodes
        and "[DEAD_END]" not in p.nodes
    ]
    if lo_aftermath_pressures:
        print(f"  Pressure at lo_aftermath: {sorted(set(lo_aftermath_pressures))}")
        assert max(lo_aftermath_pressures) <= 6, \
            f"Pressure at lo_aftermath exceeds Gold Zone ({max(lo_aftermath_pressures)})"
        assert min(lo_aftermath_pressures) >= 1, \
            f"Pressure at lo_aftermath can be 0 -- no tension"


def test_no_dead_end_nodes():
    """Every non-end node must have at least one outgoing path."""
    data = load()
    end_nodes = set(data["end_nodes"])
    errors = []
    for node_id, node in data["nodes"].items():
        if node_id in end_nodes:
            continue
        has_actions = bool(node.get("actions"))
        auto = node.get("auto_next")
        has_auto = bool(auto if isinstance(auto, str) else (auto or {}).get("target_node"))
        if not has_actions and not has_auto:
            errors.append(node_id)
    assert not errors, f"Nodes with no exit path: {errors}"


def test_collapse_unreachable():
    """Pressure 10 (COLLAPSE) must not be reachable in the prologue."""
    data = load()
    end_nodes = set(data["end_nodes"])
    paths = walk_paths(data, data["start_node"], end_nodes)
    collapse_paths = [p for p in paths if p.pressure >= 10]
    assert not collapse_paths, \
        f"COLLAPSE reachable via: {[p.nodes for p in collapse_paths[:3]]}"
