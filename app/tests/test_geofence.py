"""Tester för geofencing."""

from galdr.core.nodes import NarrativeNode
from galdr.geo.geofence import (
    GeoPoint,
    calculate_reverb,
    check_proximity,
    find_nearest_nodes,
    haversine_distance,
)


def test_haversine_same_point():
    p = GeoPoint(lat=55.6059, lon=13.0007)
    assert haversine_distance(p, p) == 0.0


def test_haversine_known_distance():
    # Stortorget till Lilla Torg i Malmö (~100m)
    p1 = GeoPoint(lat=55.6059, lon=13.0007)
    p2 = GeoPoint(lat=55.6049, lon=13.0000)
    distance = haversine_distance(p1, p2)
    assert 80 < distance < 200  # Rimligt avstånd


def test_check_proximity_within():
    node = NarrativeNode(
        id="torget",
        title="Stortorget",
        description="Test",
        geo_lat=55.6059,
        geo_lon=13.0007,
        geo_radius_meters=50,
    )
    # Spelare vid samma plats
    player = GeoPoint(lat=55.6059, lon=13.0007)
    result = check_proximity(player, node)
    assert result is not None
    assert result.within_radius is True
    assert result.distance_meters < 1


def test_check_proximity_outside():
    node = NarrativeNode(
        id="torget",
        title="Stortorget",
        description="Test",
        geo_lat=55.6059,
        geo_lon=13.0007,
        geo_radius_meters=30,
    )
    # Spelare 200m bort
    player = GeoPoint(lat=55.608, lon=13.003)
    result = check_proximity(player, node)
    assert result is not None
    assert result.within_radius is False


def test_check_proximity_no_geo():
    node = NarrativeNode(id="test", title="Test", description="Ingen GPS")
    player = GeoPoint(lat=55.6, lon=13.0)
    result = check_proximity(player, node)
    assert result is None


def test_signal_strength():
    node = NarrativeNode(
        id="test", title="Test", description="Test",
        geo_lat=55.6059, geo_lon=13.0007, geo_radius_meters=50,
    )
    # Vid noden
    player_at = GeoPoint(lat=55.6059, lon=13.0007)
    result = check_proximity(player_at, node)
    assert result.signal_strength > 0.9

    # Långt bort
    player_far = GeoPoint(lat=55.610, lon=13.005)
    result_far = check_proximity(player_far, node)
    assert result_far.signal_strength < 0.5


def test_calculate_reverb():
    assert calculate_reverb(0, 50) == 0.05  # Vid noden
    assert calculate_reverb(100, 50) == 0.8  # Utanför
    # Mitt emellan
    mid = calculate_reverb(50, 50)
    assert 0.3 < mid < 0.6


def test_find_nearest_nodes():
    nodes = [
        NarrativeNode(
            id="near", title="Nära", description="",
            geo_lat=55.6059, geo_lon=13.0007, geo_radius_meters=50,
        ),
        NarrativeNode(
            id="far", title="Långt bort", description="",
            geo_lat=55.700, geo_lon=13.100, geo_radius_meters=50,
        ),
        NarrativeNode(
            id="no_geo", title="Ingen GPS", description="",
        ),
    ]
    player = GeoPoint(lat=55.606, lon=13.001)
    results = find_nearest_nodes(player, nodes, max_distance=500)
    assert len(results) == 1
    assert results[0].node_id == "near"
