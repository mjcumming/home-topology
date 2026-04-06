"""Integration tests for OccupancyModule (v3)."""

from datetime import UTC, datetime

import pytest

from home_topology import Event, EventBus, LocationManager
from home_topology.modules.occupancy import OccupancyModule


def publish_signal(
    event_bus: EventBus,
    location_id: str,
    source_id: str,
    event_type: str,
    timeout: int | None = None,
    include_timeout_key: bool = False,
) -> None:
    """Publish a normalized occupancy signal event."""
    payload = {
        "event_type": event_type,
        "source_id": source_id,
    }
    if include_timeout_key or timeout is not None:
        payload["timeout"] = timeout

    event_bus.publish(
        Event(
            type="occupancy.signal",
            source="test.integration",
            location_id=location_id,
            entity_id=source_id,
            payload=payload,
            timestamp=datetime.now(UTC),
        )
    )


@pytest.fixture
def location_manager() -> LocationManager:
    """Create a LocationManager with a simple hierarchy."""
    mgr = LocationManager()
    mgr.create_location(id="house", name="House")
    mgr.create_location(id="main_floor", name="Main Floor", parent_id="house")
    mgr.create_location(id="kitchen", name="Kitchen", parent_id="main_floor")

    for loc_id in ["house", "main_floor", "kitchen"]:
        mgr.set_module_config(
            location_id=loc_id,
            module_id="occupancy",
            config={
                "version": 1,
                "enabled": True,
                "default_timeout": 300,
                "default_trailing_timeout": 120,
            },
        )

    mgr.add_entity_to_location("binary_sensor.kitchen_motion", "kitchen")
    return mgr


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def occupancy_module(event_bus: EventBus, location_manager: LocationManager) -> OccupancyModule:
    module = OccupancyModule()
    event_bus.set_location_manager(location_manager)
    module.attach(event_bus, location_manager)
    return module


def test_module_attachment(occupancy_module: OccupancyModule) -> None:
    assert occupancy_module._engine is not None
    assert len(occupancy_module._engine.state) == 3

    for loc_id in ["house", "main_floor", "kitchen"]:
        state = occupancy_module.get_location_state(loc_id)
        assert state is not None
        assert state["occupied"] is False
        assert state["contributions"] == []


def test_motion_signal_triggers_and_propagates(
    event_bus: EventBus,
    occupancy_module: OccupancyModule,
) -> None:
    emitted: list[Event] = []

    def capture(event: Event) -> None:
        if event.type == "occupancy.changed":
            emitted.append(event)

    event_bus.subscribe(capture)

    publish_signal(event_bus, "kitchen", "binary_sensor.kitchen_motion", "trigger")

    occ_events = [e for e in emitted if e.type == "occupancy.changed"]
    assert occ_events

    location_ids = {e.location_id for e in occ_events}
    assert {"kitchen", "main_floor", "house"}.issubset(location_ids)

    kitchen_state = occupancy_module.get_location_state("kitchen")
    assert kitchen_state is not None
    assert kitchen_state["occupied"] is True
    assert any(
        c["source_id"] == "binary_sensor.kitchen_motion" for c in kitchen_state["contributions"]
    )


def test_clear_signal_with_trailing_timeout(
    occupancy_module: OccupancyModule,
) -> None:
    now = datetime.now(UTC)
    occupancy_module.trigger("kitchen", "presence", timeout=None, now=now)

    state_before = occupancy_module.get_location_state("kitchen")
    assert state_before is not None
    indefinite = next(c for c in state_before["contributions"] if c["source_id"] == "presence")
    assert indefinite["expires_at"] is None

    occupancy_module.clear("kitchen", "presence", trailing_timeout=60, now=now)

    state_after = occupancy_module.get_location_state("kitchen")
    assert state_after is not None
    trailing = next(c for c in state_after["contributions"] if c["source_id"] == "presence")
    assert trailing["expires_at"] is not None


@pytest.mark.parametrize("event_type", ["vacate", "vacant", "unoccupied"])
def test_vacate_aliases_clear_occupancy(
    event_bus: EventBus,
    occupancy_module: OccupancyModule,
    event_type: str,
) -> None:
    """vacant/unoccupied aliases should map to authoritative vacate behavior."""
    publish_signal(event_bus, "kitchen", "binary_sensor.kitchen_motion", "trigger")
    occupied = occupancy_module.get_location_state("kitchen")
    assert occupied is not None
    assert occupied["occupied"] is True

    publish_signal(event_bus, "kitchen", "binary_sensor.kitchen_motion", event_type)
    state = occupancy_module.get_location_state("kitchen")
    assert state is not None
    assert state["occupied"] is False
    assert state["contributions"] == []


def test_state_persistence(
    occupancy_module: OccupancyModule, location_manager: LocationManager, event_bus: EventBus
) -> None:
    now = datetime.now(UTC)
    occupancy_module.trigger("kitchen", "binary_sensor.kitchen_motion", now=now)
    dumped = occupancy_module.dump_state()

    new_module = OccupancyModule()
    new_module.attach(event_bus, location_manager)
    new_module.restore_state(dumped)

    restored = new_module.get_location_state("kitchen")
    assert restored is not None
    assert restored["occupied"] is True
    assert restored["contributions"]


def test_default_config_and_schema(occupancy_module: OccupancyModule) -> None:
    config = occupancy_module.default_config()
    assert config["default_timeout"] == 300
    assert config["default_trailing_timeout"] == 120
    assert "occupancy_group_id" in config

    schema = occupancy_module.location_config_schema()
    assert "default_timeout" in schema["properties"]
    assert "default_trailing_timeout" in schema["properties"]
    assert "occupancy_group_id" in schema["properties"]


def test_lock_state_tracking(occupancy_module: OccupancyModule) -> None:
    now = datetime.now(UTC)
    occupancy_module.trigger("kitchen", "motion", now=now)
    occupancy_module.lock("kitchen", "automation_a", now=now)
    occupancy_module.lock("kitchen", "automation_b", now=now)

    state = occupancy_module.get_location_state("kitchen")
    assert state is not None
    assert state["is_locked"] is True
    assert {"automation_a", "automation_b"}.issubset(set(state["locked_by"]))

    occupancy_module.unlock("kitchen", "automation_a", now=now)
    state2 = occupancy_module.get_location_state("kitchen")
    assert state2 is not None
    assert state2["is_locked"] is True
    assert "automation_a" not in state2["locked_by"]

    occupancy_module.unlock_all("kitchen", now=now)
    state3 = occupancy_module.get_location_state("kitchen")
    assert state3 is not None
    assert state3["is_locked"] is False
    assert state3["locked_by"] == []
