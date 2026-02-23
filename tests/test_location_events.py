"""Tests for LocationManager domain event emission and ordering."""

from __future__ import annotations

from home_topology.core.bus import EventBus
from home_topology.core.manager import LocationManager


def test_location_manager_emits_rename_and_parent_events() -> None:
    """Updating name/parent should emit corresponding topology events."""
    bus = EventBus()
    mgr = LocationManager()
    bus.set_location_manager(mgr)
    mgr.set_event_bus(bus)

    received: list[str] = []
    payloads: dict[str, dict] = {}

    def on_any(event) -> None:
        received.append(event.type)
        payloads[event.type] = event.payload

    bus.subscribe(on_any)

    mgr.create_location(id="house", name="House", is_explicit_root=True)
    mgr.create_location(id="kitchen", name="Kitchen", parent_id="house")
    mgr.create_location(id="floor2", name="Second Floor", is_explicit_root=True)

    mgr.update_location("kitchen", name="Culinary Space")
    mgr.update_location("kitchen", parent_id="floor2")

    assert "location.renamed" in received
    assert payloads["location.renamed"]["old_name"] == "Kitchen"
    assert payloads["location.renamed"]["new_name"] == "Culinary Space"

    assert "location.parent_changed" in received
    assert payloads["location.parent_changed"]["old_parent_id"] == "house"
    assert payloads["location.parent_changed"]["new_parent_id"] == "floor2"


def test_location_manager_emits_deleted_event_with_metadata() -> None:
    """Delete should emit location.deleted with metadata payload."""
    bus = EventBus()
    mgr = LocationManager()
    bus.set_location_manager(mgr)
    mgr.set_event_bus(bus)

    deleted_payloads: list[dict] = []

    def on_deleted(event) -> None:
        if event.type == "location.deleted":
            deleted_payloads.append(event.payload)

    bus.subscribe(on_deleted)

    mgr.create_location(id="house", name="House", is_explicit_root=True)
    mgr.create_location(id="office", name="Office", parent_id="house")
    mgr.set_module_config("office", "_meta", {"sync_source": "homeassistant", "type": "room"})

    mgr.delete_location("office")

    assert len(deleted_payloads) == 1
    assert deleted_payloads[0]["metadata"]["type"] == "room"


def test_reorder_location_sets_canonical_sibling_order() -> None:
    """Reordering should persist canonical sibling ordering."""
    mgr = LocationManager()
    mgr.create_location(id="house", name="House", is_explicit_root=True)
    mgr.create_location(id="a", name="A", parent_id="house")
    mgr.create_location(id="b", name="B", parent_id="house")
    mgr.create_location(id="c", name="C", parent_id="house")

    mgr.reorder_location("c", "house", 0)

    children = mgr.children_of("house")
    assert [child.id for child in children] == ["c", "a", "b"]
    assert [child.order for child in children] == [0, 1, 2]
