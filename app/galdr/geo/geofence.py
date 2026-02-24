"""Geofencing and acoustic distance calculation for Ekokammaren.

The backend computes the distance between the player's GPS position and each
narrative node's anchor point. When the player enters a node's radius, the
story advances. When they approach, the AI builds tension — it knows they're
close even before they arrive.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from galdr.core.nodes import NarrativeNode


@dataclass
class GeoPoint:
    lat: float
    lon: float


@dataclass
class ProximityResult:
    node_id: str
    distance_meters: float
    within_radius: bool
    signal_strength: float  # 0.0 (far away) to 1.0 (at the node)


def haversine_distance(p1: GeoPoint, p2: GeoPoint) -> float:
    """Great-circle distance in metres between two GPS coordinates."""
    R = 6_371_000  # Earth radius in metres

    lat1, lat2 = math.radians(p1.lat), math.radians(p2.lat)
    dlat = math.radians(p2.lat - p1.lat)
    dlon = math.radians(p2.lon - p1.lon)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def check_proximity(player: GeoPoint, node: NarrativeNode) -> ProximityResult | None:
    """Distance from player to a node's geofence anchor.

    Returns None if the node has no GPS coordinates — the engine never
    blocks on missing GPS, it simply skips the geofence context.
    """
    if node.geo_lat is None or node.geo_lon is None:
        return None

    node_point = GeoPoint(lat=node.geo_lat, lon=node.geo_lon)
    distance = haversine_distance(player, node_point)
    within = distance <= node.geo_radius_meters

    # Signal: 1.0 at the node, 0.0 at double the radius
    max_range = node.geo_radius_meters * 2
    signal = max(0.0, 1.0 - (distance / max_range))

    return ProximityResult(
        node_id=node.id,
        distance_meters=round(distance, 1),
        within_radius=within,
        signal_strength=round(signal, 2),
    )


def find_nearest_nodes(
    player: GeoPoint,
    nodes: list[NarrativeNode],
    max_distance: float = 500.0,
) -> list[ProximityResult]:
    """All nodes within max_distance metres, sorted by proximity."""
    results: list[ProximityResult] = []
    for node in nodes:
        result = check_proximity(player, node)
        if result and result.distance_meters <= max_distance:
            results.append(result)
    results.sort(key=lambda r: r.distance_meters)
    return results


def calculate_reverb(distance: float, radius: float) -> float:
    """Reverb level based on player distance from the node.

    Linear falloff chosen over exponential: outdoor conditions during field
    testing are unpredictable, and linear is easier to tune by ear without
    acoustic measurements on site.

    Bounds:
    - 0.05 at the node (minimal reverb — voice sounds close and stable)
    - 0.80 at double the radius (heavy reverb — voice sounds distant, diffuse)
    - 0.75 is the slope that spans that range: 0.05 + 0.75 * ratio

    Reverb is capped at 0.80 beyond double the radius rather than continuing
    to climb — otherwise a player who wanders far off course gets total noise.
    """
    if distance <= 0:
        return 0.05
    if distance >= radius * 2:
        return 0.80
    ratio = distance / (radius * 2)
    return 0.05 + (0.75 * ratio)
