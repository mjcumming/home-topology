"""Advanced tests for occupancy engine/module (v3)."""

from datetime import UTC, datetime, timedelta
from itertools import permutations

import pytest

from home_topology import EventBus, LocationManager
from home_topology.modules.occupancy import OccupancyModule
from home_topology.modules.occupancy.engine import OccupancyEngine
from home_topology.modules.occupancy.models import (
    EventType,
    LocationConfig,
    OccupancyEvent,
    OccupancyStrategy,
    REASON_EVENT_PREFIX,
    REASON_PROPAGATION_CHILD_PREFIX,
    REASON_PROPAGATION_PARENT,
    REASON_TIMEOUT,
)


@pytest.fixture
def base_time() -> datetime:
    return datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)


def test_engine_multiple_locations_different_timeouts(base_time: datetime) -> None:
    engine = OccupancyEngine(
        [
            LocationConfig(id="kitchen", default_timeout=60),
            LocationConfig(id="bedroom", default_timeout=120),
            LocationConfig(id="bathroom", default_timeout=30),
        ]
    )

    for loc_id in ["kitchen", "bedroom", "bathroom"]:
        engine.handle_event(
            OccupancyEvent(
                location_id=loc_id,
                event_type=EventType.TRIGGER,
                source_id="motion",
                timestamp=base_time,
            ),
            base_time,
        )

    assert engine.check_timeouts(base_time).next_expiration == base_time + timedelta(seconds=30)

    engine.check_timeouts(base_time + timedelta(seconds=31))
    assert not engine.state["bathroom"].is_occupied
    assert engine.state["kitchen"].is_occupied
    assert engine.state["bedroom"].is_occupied


def test_follow_parent_ignores_direct_events(base_time: datetime) -> None:
    engine = OccupancyEngine(
        [
            LocationConfig(id="living_room", default_timeout=60),
            LocationConfig(
                id="reading_nook",
                parent_id="living_room",
                occupancy_strategy=OccupancyStrategy.FOLLOW_PARENT,
                contributes_to_parent=False,
            ),
        ]
    )

    engine.handle_event(
        OccupancyEvent(
            location_id="reading_nook",
            event_type=EventType.TRIGGER,
            source_id="nook_motion",
            timestamp=base_time,
            timeout=120,
            timeout_set=True,
        ),
        base_time,
    )

    assert not engine.state["living_room"].is_occupied
    assert not engine.state["reading_nook"].is_occupied


def test_follow_parent_tracks_parent_state(base_time: datetime) -> None:
    engine = OccupancyEngine(
        [
            LocationConfig(id="living_room", default_timeout=60),
            LocationConfig(
                id="reading_nook",
                parent_id="living_room",
                occupancy_strategy=OccupancyStrategy.FOLLOW_PARENT,
                contributes_to_parent=False,
            ),
        ]
    )

    engine.handle_event(
        OccupancyEvent(
            location_id="living_room",
            event_type=EventType.TRIGGER,
            source_id="living_motion",
            timestamp=base_time,
            timeout=60,
            timeout_set=True,
        ),
        base_time,
    )

    assert engine.state["living_room"].is_occupied
    assert engine.state["reading_nook"].is_occupied


def test_parent_child_invariant(base_time: datetime) -> None:
    engine = OccupancyEngine(
        [
            LocationConfig(id="house", default_timeout=60),
            LocationConfig(id="kitchen", parent_id="house", default_timeout=300),
        ]
    )

    engine.handle_event(
        OccupancyEvent("kitchen", EventType.TRIGGER, "motion", base_time, timeout=300, timeout_set=True),
        base_time,
    )

    engine.check_timeouts(base_time + timedelta(seconds=61))
    assert engine.state["kitchen"].is_occupied
    assert engine.state["house"].is_occupied

    engine.check_timeouts(base_time + timedelta(seconds=301))
    assert not engine.state["kitchen"].is_occupied
    assert not engine.state["house"].is_occupied


def test_lock_suspend_resume_preserves_remaining_time(base_time: datetime) -> None:
    engine = OccupancyEngine([LocationConfig(id="kitchen", default_timeout=60)])

    engine.handle_event(
        OccupancyEvent("kitchen", EventType.TRIGGER, "motion", base_time, timeout=60, timeout_set=True),
        base_time,
    )
    engine.handle_event(
        OccupancyEvent("kitchen", EventType.LOCK, "sleep_mode", base_time),
        base_time,
    )

    assert engine.state["kitchen"].is_locked
    assert engine.state["kitchen"].contributions == frozenset()
    assert engine.state["kitchen"].suspended_contributions

    t1 = base_time + timedelta(seconds=30)
    engine.handle_event(
        OccupancyEvent("kitchen", EventType.UNLOCK, "sleep_mode", t1),
        t1,
    )

    assert not engine.state["kitchen"].is_locked
    assert engine.state["kitchen"].contributions


def test_get_effective_timeout_with_descendants(base_time: datetime) -> None:
    engine = OccupancyEngine(
        [
            LocationConfig(id="house", default_timeout=60),
            LocationConfig(id="kitchen", parent_id="house", default_timeout=120),
            LocationConfig(id="bedroom", parent_id="house", default_timeout=180),
        ]
    )

    engine.handle_event(
        OccupancyEvent("kitchen", EventType.TRIGGER, "k_motion", base_time, timeout=120, timeout_set=True),
        base_time,
    )
    engine.handle_event(
        OccupancyEvent("bedroom", EventType.TRIGGER, "b_motion", base_time, timeout=180, timeout_set=True),
        base_time,
    )

    effective = engine.get_effective_timeout("house", base_time)
    assert effective == base_time + timedelta(seconds=180)


def test_restore_state_parses_naive_datetime() -> None:
    engine = OccupancyEngine([LocationConfig(id="kitchen", default_timeout=60)])
    snapshot = {
        "kitchen": {
            "is_occupied": True,
            "locked_by": [],
            "contributions": [
                {"source_id": "motion", "expires_at": "2025-01-15T12:05:00"},
            ],
            "suspended_contributions": [],
        }
    }

    now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
    engine.restore_state(snapshot, now)

    assert engine.state["kitchen"].is_occupied
    contribution = next(iter(engine.state["kitchen"].contributions))
    assert contribution.expires_at is not None
    assert contribution.expires_at.tzinfo is not None


def test_module_vacate_area(base_time: datetime) -> None:
    mgr = LocationManager()
    mgr.create_location(id="house", name="House")
    mgr.create_location(id="kitchen", name="Kitchen", parent_id="house")
    mgr.create_location(id="bedroom", name="Bedroom", parent_id="house")

    for loc_id in ["house", "kitchen", "bedroom"]:
        mgr.set_module_config(
            loc_id,
            "occupancy",
            {
                "version": 1,
                "enabled": True,
                "default_timeout": 300,
                "default_trailing_timeout": 120,
            },
        )

    bus = EventBus()
    module = OccupancyModule()
    bus.set_location_manager(mgr)
    module.attach(bus, mgr)

    module.trigger("kitchen", "motion", now=base_time)
    module.trigger("bedroom", "motion", now=base_time)

    transitions = module.vacate_area("house", "away_mode", now=base_time)
    assert transitions

    for loc_id in ["house", "kitchen", "bedroom"]:
        state = module.get_location_state(loc_id)
        assert state is not None
        assert state["occupied"] is False


def test_transition_reason_contract(base_time: datetime) -> None:
    engine = OccupancyEngine(
        [
            LocationConfig(id="house", default_timeout=60),
            LocationConfig(id="kitchen", parent_id="house", default_timeout=120),
        ]
    )

    result = engine.handle_event(
        OccupancyEvent("kitchen", EventType.TRIGGER, "motion", base_time, timeout=60, timeout_set=True),
        base_time,
    )
    reasons = {transition.reason for transition in result.transitions}
    assert any(reason.startswith(REASON_EVENT_PREFIX) for reason in reasons)
    assert any(reason.startswith(REASON_PROPAGATION_CHILD_PREFIX) for reason in reasons)

    timeout_result = engine.check_timeouts(base_time + timedelta(seconds=61))
    timeout_reasons = {transition.reason for transition in timeout_result.transitions}
    assert REASON_TIMEOUT in timeout_reasons or REASON_PROPAGATION_PARENT in timeout_reasons


def test_parent_child_invariant_across_event_interleavings(base_time: datetime) -> None:
    """Parent and child occupancy stay aligned regardless of event ordering."""
    event_factories = {
        "trigger_motion": lambda t: OccupancyEvent(
            "kitchen",
            EventType.TRIGGER,
            "motion",
            t,
            timeout=60,
            timeout_set=True,
        ),
        "trigger_presence": lambda t: OccupancyEvent(
            "kitchen",
            EventType.TRIGGER,
            "presence",
            t,
            timeout=None,
            timeout_set=True,
        ),
        "clear_motion": lambda t: OccupancyEvent(
            "kitchen",
            EventType.CLEAR,
            "motion",
            t,
            timeout=0,
            timeout_set=True,
        ),
        "clear_presence": lambda t: OccupancyEvent(
            "kitchen",
            EventType.CLEAR,
            "presence",
            t,
            timeout=120,
            timeout_set=True,
        ),
    }

    for order in permutations(event_factories.keys()):
        engine = OccupancyEngine(
            [
                LocationConfig(id="house", default_timeout=60),
                LocationConfig(id="kitchen", parent_id="house", default_timeout=60),
            ]
        )
        now = base_time

        for name in order:
            result = engine.handle_event(event_factories[name](now), now)
            assert engine.state["house"].is_occupied == engine.state["kitchen"].is_occupied
            for transition in result.transitions:
                assert (
                    transition.reason.startswith(REASON_EVENT_PREFIX)
                    or transition.reason.startswith(REASON_PROPAGATION_CHILD_PREFIX)
                    or transition.reason == REASON_TIMEOUT
                    or transition.reason == REASON_PROPAGATION_PARENT
                )
            now += timedelta(seconds=1)


def test_follow_parent_invariant_across_event_interleavings(base_time: datetime) -> None:
    """FOLLOW_PARENT child always mirrors parent, regardless of local event ordering."""
    event_factories = {
        "child_trigger_timed": lambda t: OccupancyEvent(
            "reading_nook",
            EventType.TRIGGER,
            "nook_motion",
            t,
            timeout=60,
            timeout_set=True,
        ),
        "child_clear": lambda t: OccupancyEvent(
            "reading_nook",
            EventType.CLEAR,
            "nook_motion",
            t,
            timeout=0,
            timeout_set=True,
        ),
        "parent_trigger": lambda t: OccupancyEvent(
            "living_room",
            EventType.TRIGGER,
            "living_motion",
            t,
            timeout=60,
            timeout_set=True,
        ),
        "parent_clear": lambda t: OccupancyEvent(
            "living_room",
            EventType.CLEAR,
            "living_motion",
            t,
            timeout=0,
            timeout_set=True,
        ),
    }

    for order in permutations(event_factories.keys()):
        engine = OccupancyEngine(
            [
                LocationConfig(id="living_room", default_timeout=60),
                LocationConfig(
                    id="reading_nook",
                    parent_id="living_room",
                    occupancy_strategy=OccupancyStrategy.FOLLOW_PARENT,
                    contributes_to_parent=False,
                ),
            ]
        )
        now = base_time

        for name in order:
            engine.handle_event(event_factories[name](now), now)
            assert engine.state["reading_nook"].is_occupied == engine.state["living_room"].is_occupied
            now += timedelta(seconds=1)
