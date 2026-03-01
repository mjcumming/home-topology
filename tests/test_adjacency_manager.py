"""Tests for topology adjacency edge management in LocationManager."""

from __future__ import annotations

import pytest

from home_topology import EventBus, LocationManager


def _seed_locations(mgr: LocationManager) -> None:
    mgr.create_location(id="living", name="Living Room")
    mgr.create_location(id="hall", name="Hallway")
    mgr.create_location(id="kitchen", name="Kitchen")


def test_create_and_list_adjacency_edges() -> None:
    """Manager should persist and return created adjacency edges."""
    mgr = LocationManager()
    _seed_locations(mgr)

    edge = mgr.create_adjacency_edge(
        edge_id="edge_living_hall",
        from_location_id="living",
        to_location_id="hall",
        boundary_type="door",
        crossing_sources=["binary_sensor.living_hall_door"],
        handoff_window_sec=15,
        priority=70,
    )

    assert edge.edge_id == "edge_living_hall"
    assert edge.directionality == "bidirectional"
    assert edge.boundary_type == "door"
    assert edge.crossing_sources == ["binary_sensor.living_hall_door"]
    assert edge.handoff_window_sec == 15
    assert edge.priority == 70

    all_edges = mgr.all_adjacency_edges()
    assert len(all_edges) == 1
    assert all_edges[0].edge_id == "edge_living_hall"


def test_directional_neighbor_queries() -> None:
    """Neighbor resolution should honor edge directionality."""
    mgr = LocationManager()
    _seed_locations(mgr)

    mgr.create_adjacency_edge(
        edge_id="edge_hall_to_kitchen",
        from_location_id="hall",
        to_location_id="kitchen",
        directionality="a_to_b",
    )

    assert mgr.neighboring_location_ids("hall", direction="outbound") == ["kitchen"]
    assert mgr.neighboring_location_ids("hall", direction="inbound") == []
    assert mgr.neighboring_location_ids("kitchen", direction="inbound") == ["hall"]
    assert mgr.neighboring_location_ids("kitchen", direction="outbound") == []


def test_adjacency_validation_errors() -> None:
    """Invalid adjacency edge definitions should be rejected."""
    mgr = LocationManager()
    _seed_locations(mgr)

    with pytest.raises(ValueError, match="does not exist"):
        mgr.create_adjacency_edge(
            edge_id="bad_missing",
            from_location_id="living",
            to_location_id="missing",
        )

    with pytest.raises(ValueError, match="cannot connect a location to itself"):
        mgr.create_adjacency_edge(
            edge_id="bad_self",
            from_location_id="living",
            to_location_id="living",
        )

    with pytest.raises(ValueError, match="Invalid directionality"):
        mgr.create_adjacency_edge(
            edge_id="bad_dir",
            from_location_id="living",
            to_location_id="hall",
            directionality="one_way",
        )

    with pytest.raises(ValueError, match="must be >= 0"):
        mgr.create_adjacency_edge(
            edge_id="bad_window",
            from_location_id="living",
            to_location_id="hall",
            handoff_window_sec=-1,
        )


def test_delete_location_removes_connected_edges() -> None:
    """Deleting a location should remove all connected adjacency edges."""
    mgr = LocationManager()
    _seed_locations(mgr)

    mgr.create_adjacency_edge(
        edge_id="edge_living_hall",
        from_location_id="living",
        to_location_id="hall",
    )
    mgr.create_adjacency_edge(
        edge_id="edge_hall_kitchen",
        from_location_id="hall",
        to_location_id="kitchen",
    )

    mgr.delete_location("hall")

    assert mgr.get_location("hall") is None
    assert mgr.all_adjacency_edges() == []


def test_adjacency_event_emission() -> None:
    """Adjacency edge mutations should emit topology events when bus is set."""
    bus = EventBus()
    mgr = LocationManager()
    bus.set_location_manager(mgr)
    mgr.set_event_bus(bus)

    _seed_locations(mgr)

    received: list[str] = []

    def on_any(event) -> None:
        received.append(event.type)

    bus.subscribe(on_any)

    mgr.create_adjacency_edge(
        edge_id="edge_living_hall",
        from_location_id="living",
        to_location_id="hall",
    )
    mgr.update_adjacency_edge("edge_living_hall", handoff_window_sec=20)
    mgr.delete_adjacency_edge("edge_living_hall")

    assert "adjacency.created" in received
    assert "adjacency.updated" in received
    assert "adjacency.deleted" in received
