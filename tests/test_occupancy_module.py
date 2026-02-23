"""Core module tests for OccupancyModule (v3)."""

from datetime import UTC, datetime, timedelta

import pytest

from home_topology import Event, EventBus, LocationManager
from home_topology.modules.occupancy import OccupancyModule


@pytest.fixture
def location_manager() -> LocationManager:
    mgr = LocationManager()
    mgr.create_location(id="house", name="House")
    mgr.create_location(id="main_floor", name="Main Floor", parent_id="house")
    mgr.create_location(id="kitchen", name="Kitchen", parent_id="main_floor")
    mgr.create_location(id="reading_nook", name="Reading Nook", parent_id="main_floor")

    for loc_id in ["house", "main_floor", "kitchen"]:
        mgr.set_module_config(
            location_id=loc_id,
            module_id="occupancy",
            config={
                "version": 1,
                "enabled": True,
                "default_timeout": 300,
                "default_trailing_timeout": 120,
                "occupancy_strategy": "independent",
            },
        )

    mgr.set_module_config(
        location_id="reading_nook",
        module_id="occupancy",
        config={
            "version": 1,
            "enabled": True,
            "default_timeout": 300,
            "default_trailing_timeout": 120,
            "occupancy_strategy": "follow_parent",
            "contributes_to_parent": False,
        },
    )

    return mgr


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def occupancy_module(event_bus: EventBus, location_manager: LocationManager) -> OccupancyModule:
    module = OccupancyModule()
    event_bus.set_location_manager(location_manager)
    location_manager.set_event_bus(event_bus)
    module.attach(event_bus, location_manager)
    return module


def test_trigger_and_clear_layering(occupancy_module: OccupancyModule) -> None:
    now = datetime.now(UTC)

    occupancy_module.trigger("kitchen", "motion", timeout=600, now=now)
    occupancy_module.trigger("kitchen", "presence", timeout=None, now=now)

    state = occupancy_module.get_location_state("kitchen")
    assert state is not None
    assert state["occupied"] is True
    assert len(state["contributions"]) == 2

    occupancy_module.clear("kitchen", "presence", trailing_timeout=120, now=now)

    state_after = occupancy_module.get_location_state("kitchen")
    assert state_after is not None
    assert state_after["occupied"] is True
    assert len(state_after["contributions"]) == 2


def test_timeout_expiration_via_check_timeouts(occupancy_module: OccupancyModule) -> None:
    t0 = datetime(2025, 1, 1, tzinfo=UTC)
    occupancy_module.trigger("kitchen", "motion", timeout=60, now=t0)

    occupancy_module.check_timeouts(t0 + timedelta(seconds=59))
    state_before = occupancy_module.get_location_state("kitchen")
    assert state_before is not None and state_before["occupied"] is True

    occupancy_module.check_timeouts(t0 + timedelta(seconds=61))
    state_after = occupancy_module.get_location_state("kitchen")
    assert state_after is not None and state_after["occupied"] is False


def test_parent_stays_occupied_while_child_occupied(occupancy_module: OccupancyModule) -> None:
    t0 = datetime(2025, 1, 1, tzinfo=UTC)
    occupancy_module.trigger("kitchen", "motion", timeout=300, now=t0)

    # Parent should still be occupied after 61s if child is still occupied.
    occupancy_module.check_timeouts(t0 + timedelta(seconds=61))

    kitchen = occupancy_module.get_location_state("kitchen")
    house = occupancy_module.get_location_state("house")
    assert kitchen is not None and house is not None
    assert kitchen["occupied"] is True
    assert house["occupied"] is True


def test_follow_parent_is_strict_mirror(occupancy_module: OccupancyModule) -> None:
    t0 = datetime(2025, 1, 1, tzinfo=UTC)

    # Direct trigger should be ignored on follow_parent location.
    occupancy_module.trigger("reading_nook", "nook_sensor", timeout=60, now=t0)
    nook = occupancy_module.get_location_state("reading_nook")
    assert nook is not None
    assert nook["occupied"] is False

    # Parent occupancy should make follow_parent child occupied.
    occupancy_module.trigger("main_floor", "main_floor_sensor", timeout=60, now=t0)
    nook_after = occupancy_module.get_location_state("reading_nook")
    assert nook_after is not None
    assert nook_after["occupied"] is True


def test_lock_suspends_and_resume_contributions(occupancy_module: OccupancyModule) -> None:
    t0 = datetime(2025, 1, 1, tzinfo=UTC)
    occupancy_module.trigger("kitchen", "motion", timeout=60, now=t0)
    occupancy_module.lock("kitchen", "sleep_mode", now=t0)

    locked = occupancy_module.get_location_state("kitchen")
    assert locked is not None
    assert locked["is_locked"] is True
    assert locked["contributions"] == []
    assert locked["suspended_contributions"]

    t1 = t0 + timedelta(seconds=30)
    occupancy_module.unlock("kitchen", "sleep_mode", now=t1)

    resumed = occupancy_module.get_location_state("kitchen")
    assert resumed is not None
    assert resumed["is_locked"] is False
    assert resumed["contributions"]


def test_vacate_area_cascades(occupancy_module: OccupancyModule) -> None:
    now = datetime.now(UTC)
    occupancy_module.trigger("kitchen", "motion", now=now)
    occupancy_module.trigger("main_floor", "manual", now=now)

    transitions = occupancy_module.vacate_area("house", "away_mode", now=now)
    assert transitions

    for loc_id in ["house", "main_floor", "kitchen"]:
        state = occupancy_module.get_location_state(loc_id)
        assert state is not None
        assert state["occupied"] is False


def test_occupancy_changed_payload_contains_contributions(
    event_bus: EventBus,
    occupancy_module: OccupancyModule,
) -> None:
    emitted: list[Event] = []

    def capture(event: Event) -> None:
        if event.type == "occupancy.changed":
            emitted.append(event)

    event_bus.subscribe(capture)

    now = datetime.now(UTC)
    occupancy_module.trigger("kitchen", "motion", timeout=60, now=now)

    assert emitted
    payload = emitted[-1].payload
    assert payload is not None
    assert "contributions" in payload
    assert "active_holds" not in payload


def test_public_api_rejects_negative_timeout(occupancy_module: OccupancyModule) -> None:
    with pytest.raises(ValueError):
        occupancy_module.trigger("kitchen", "motion", timeout=-1)

    with pytest.raises(ValueError):
        occupancy_module.clear("kitchen", "motion", trailing_timeout=-10)


def test_public_api_rejects_non_integer_timeout(occupancy_module: OccupancyModule) -> None:
    with pytest.raises(ValueError):
        occupancy_module.trigger("kitchen", "motion", timeout="60")  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        occupancy_module.clear("kitchen", "motion", trailing_timeout=1.5)  # type: ignore[arg-type]


def test_naive_datetime_is_normalized(occupancy_module: OccupancyModule) -> None:
    naive_now = datetime(2025, 1, 1, 0, 0, 0)  # naive by design
    occupancy_module.trigger("kitchen", "motion", timeout=60, now=naive_now)
    occupancy_module.check_timeouts(datetime(2025, 1, 1, 0, 0, 59))

    state = occupancy_module.get_location_state("kitchen")
    assert state is not None
    assert state["occupied"] is True


def test_topology_mutation_rebuild_preserves_existing_state(
    occupancy_module: OccupancyModule,
    location_manager: LocationManager,
) -> None:
    now = datetime.now(UTC)
    occupancy_module.trigger("kitchen", "motion", timeout=120, now=now)

    # Create new location and trigger topology mutation event through manager.
    location_manager.create_location(id="pantry", name="Pantry", parent_id="main_floor")
    location_manager.set_module_config(
        "pantry",
        "occupancy",
        {
            "version": 1,
            "enabled": True,
            "default_timeout": 300,
            "default_trailing_timeout": 120,
            "occupancy_strategy": "independent",
        },
    )

    kitchen = occupancy_module.get_location_state("kitchen")
    pantry = occupancy_module.get_location_state("pantry")
    assert kitchen is not None and kitchen["occupied"] is True
    assert pantry is not None and pantry["occupied"] is False
