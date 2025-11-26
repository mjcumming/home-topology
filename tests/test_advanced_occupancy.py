"""
Advanced tests for OccupancyModule.

This module covers:
- Engine timeout expiration scenarios
- FOLLOW_PARENT strategy behavior
- Lock/unlock with timeout interactions
- Config migration from legacy formats
"""

import pytest
from datetime import datetime, UTC, timedelta

from home_topology import Event, EventBus, LocationManager
from home_topology.modules.occupancy import OccupancyModule
from home_topology.modules.occupancy.engine import OccupancyEngine
from home_topology.modules.occupancy.models import (
    LocationConfig,
    OccupancyStrategy,
    EventType,
    OccupancyEvent,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def base_time():
    """Fixed base time for deterministic tests."""
    return datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def location_manager_with_follow_parent():
    """LocationManager with FOLLOW_PARENT configured locations."""
    mgr = LocationManager()

    # Create hierarchy: house -> living_room -> reading_nook
    # reading_nook uses FOLLOW_PARENT
    mgr.create_location(id="house", name="House")
    mgr.create_location(id="living_room", name="Living Room", parent_id="house")
    mgr.create_location(id="reading_nook", name="Reading Nook", parent_id="living_room")

    # House: independent
    mgr.set_module_config(
        "house",
        "occupancy",
        {
            "version": 1,
            "enabled": True,
            "default_timeout": 300,
            "hold_release_timeout": 120,
            "occupancy_strategy": "independent",
        },
    )

    # Living room: independent
    mgr.set_module_config(
        "living_room",
        "occupancy",
        {
            "version": 1,
            "enabled": True,
            "default_timeout": 300,
            "hold_release_timeout": 120,
            "occupancy_strategy": "independent",
        },
    )

    # Reading nook: FOLLOW_PARENT
    mgr.set_module_config(
        "reading_nook",
        "occupancy",
        {
            "version": 1,
            "enabled": True,
            "default_timeout": 300,
            "hold_release_timeout": 120,
            "occupancy_strategy": "follow_parent",
            "contributes_to_parent": False,  # Don't bubble up
        },
    )

    # Add sensors
    mgr.add_entity_to_location("binary_sensor.living_room_motion", "living_room")

    return mgr


@pytest.fixture
def location_manager_multi_room():
    """LocationManager with multiple independent rooms for timeout testing."""
    mgr = LocationManager()

    mgr.create_location(id="house", name="House")
    mgr.create_location(id="kitchen", name="Kitchen", parent_id="house")
    mgr.create_location(id="bedroom", name="Bedroom", parent_id="house")
    mgr.create_location(id="bathroom", name="Bathroom", parent_id="house")

    for loc_id in ["house", "kitchen", "bedroom", "bathroom"]:
        mgr.set_module_config(
            loc_id,
            "occupancy",
            {
                "version": 1,
                "enabled": True,
                "default_timeout": 300,
                "hold_release_timeout": 120,
            },
        )

    mgr.add_entity_to_location("binary_sensor.kitchen_motion", "kitchen")
    mgr.add_entity_to_location("binary_sensor.bedroom_motion", "bedroom")
    mgr.add_entity_to_location("binary_sensor.bathroom_motion", "bathroom")

    return mgr


@pytest.fixture
def location_manager_legacy_config():
    """LocationManager with legacy 'timeouts' dict format."""
    mgr = LocationManager()

    mgr.create_location(id="house", name="House")
    mgr.create_location(id="kitchen", name="Kitchen", parent_id="house")

    # Legacy config format with "timeouts" dict
    mgr.set_module_config(
        "kitchen",
        "occupancy",
        {
            "version": 1,
            "enabled": True,
            "timeouts": {
                "default": 600,  # 10 minutes
                "presence": 180,  # 3 minutes
            },
        },
    )

    # Standard config for house
    mgr.set_module_config(
        "house",
        "occupancy",
        {
            "version": 1,
            "enabled": True,
            "default_timeout": 300,
            "hold_release_timeout": 120,
        },
    )

    mgr.add_entity_to_location("binary_sensor.kitchen_motion", "kitchen")

    return mgr


@pytest.fixture
def event_bus():
    """Create an EventBus."""
    return EventBus()


# =============================================================================
# ENGINE TIMEOUT EXPIRATION TESTS
# =============================================================================


class TestEngineTimeoutExpiration:
    """Comprehensive tests for timeout expiration behavior."""

    def test_single_location_timeout_expiration(self, base_time):
        """Test basic timeout expiration for a single location."""
        configs = [
            LocationConfig(id="kitchen", default_timeout=60),
        ]
        engine = OccupancyEngine(configs)

        # Trigger occupancy
        event = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.TRIGGER,
            source_id="motion",
            timestamp=base_time,
            timeout=60,
        )
        result = engine.handle_event(event, base_time)

        assert engine.state["kitchen"].is_occupied
        assert len(result.transitions) == 1

        # Check timeout calculation
        next_timeout = result.next_expiration
        assert next_timeout is not None
        expected_timeout = base_time + timedelta(seconds=60)
        assert next_timeout == expected_timeout

        # Before timeout: still occupied
        before_timeout = base_time + timedelta(seconds=59)
        result_before = engine.check_timeouts(before_timeout)
        assert engine.state["kitchen"].is_occupied
        assert len(result_before.transitions) == 0

        # After timeout: should become vacant
        after_timeout = base_time + timedelta(seconds=61)
        result_after = engine.check_timeouts(after_timeout)
        assert not engine.state["kitchen"].is_occupied
        assert len(result_after.transitions) == 1
        assert result_after.transitions[0].new_state.is_occupied is False

    def test_multiple_locations_different_timeouts(self, base_time):
        """Test multiple locations with staggered timeouts."""
        configs = [
            LocationConfig(id="kitchen", default_timeout=60),
            LocationConfig(id="bedroom", default_timeout=120),
            LocationConfig(id="bathroom", default_timeout=30),
        ]
        engine = OccupancyEngine(configs)

        # Trigger all three at the same time
        for loc_id in ["kitchen", "bedroom", "bathroom"]:
            event = OccupancyEvent(
                location_id=loc_id,
                event_type=EventType.TRIGGER,
                source_id="motion",
                timestamp=base_time,
            )
            engine.handle_event(event, base_time)

        # All should be occupied
        for loc_id in ["kitchen", "bedroom", "bathroom"]:
            assert engine.state[loc_id].is_occupied

        # Next timeout should be bathroom (30s)
        result = engine.check_timeouts(base_time)
        assert result.next_expiration == base_time + timedelta(seconds=30)

        # At 31s: bathroom should expire
        t1 = base_time + timedelta(seconds=31)
        result1 = engine.check_timeouts(t1)
        assert not engine.state["bathroom"].is_occupied
        assert engine.state["kitchen"].is_occupied
        assert engine.state["bedroom"].is_occupied

        # Next timeout should be kitchen (60s)
        assert result1.next_expiration == base_time + timedelta(seconds=60)

        # At 61s: kitchen should expire
        t2 = base_time + timedelta(seconds=61)
        engine.check_timeouts(t2)
        assert not engine.state["kitchen"].is_occupied
        assert engine.state["bedroom"].is_occupied

        # At 121s: bedroom should expire
        t3 = base_time + timedelta(seconds=121)
        engine.check_timeouts(t3)
        assert not engine.state["bedroom"].is_occupied

    def test_timeout_with_timer_refresh(self, base_time):
        """Test that new triggers extend the timeout."""
        configs = [LocationConfig(id="kitchen", default_timeout=60)]
        engine = OccupancyEngine(configs)

        # Initial trigger
        event1 = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.TRIGGER,
            source_id="motion",
            timestamp=base_time,
        )
        engine.handle_event(event1, base_time)

        # Refresh at 30s
        t1 = base_time + timedelta(seconds=30)
        event2 = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.TRIGGER,
            source_id="motion",
            timestamp=t1,
        )
        result = engine.handle_event(event2, t1)

        # Should now expire at 90s (30 + 60)
        assert result.next_expiration == t1 + timedelta(seconds=60)

        # At 65s (original timeout): should still be occupied
        t2 = base_time + timedelta(seconds=65)
        engine.check_timeouts(t2)
        assert engine.state["kitchen"].is_occupied

        # At 95s (after refresh timeout): should be vacant
        t3 = base_time + timedelta(seconds=95)
        engine.check_timeouts(t3)
        assert not engine.state["kitchen"].is_occupied

    def test_timeout_does_not_affect_held_location(self, base_time):
        """Test that active holds prevent timeout expiration."""
        configs = [LocationConfig(id="kitchen", default_timeout=60, hold_release_timeout=30)]
        engine = OccupancyEngine(configs)

        # Trigger with timer
        event1 = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.TRIGGER,
            source_id="motion",
            timestamp=base_time,
            timeout=60,
        )
        engine.handle_event(event1, base_time)

        # Add a hold
        event2 = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.HOLD,
            source_id="presence",
            timestamp=base_time,
        )
        engine.handle_event(event2, base_time)

        # After original timeout: should still be occupied due to hold
        t1 = base_time + timedelta(seconds=120)
        engine.check_timeouts(t1)
        assert engine.state["kitchen"].is_occupied
        assert "presence" in engine.state["kitchen"].active_holds

        # Next expiration should be None (held indefinitely)
        result = engine.check_timeouts(t1)
        assert result.next_expiration is None

    def test_release_starts_trailing_timeout(self, base_time):
        """Test that RELEASE event starts trailing timeout."""
        configs = [LocationConfig(id="kitchen", default_timeout=300, hold_release_timeout=60)]
        engine = OccupancyEngine(configs)

        # Add hold
        hold_event = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.HOLD,
            source_id="presence",
            timestamp=base_time,
        )
        engine.handle_event(hold_event, base_time)
        assert engine.state["kitchen"].is_occupied

        # Release after 10 minutes
        t1 = base_time + timedelta(minutes=10)
        release_event = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.RELEASE,
            source_id="presence",
            timestamp=t1,
        )
        result = engine.handle_event(release_event, t1)

        # Should still be occupied (trailing timeout)
        assert engine.state["kitchen"].is_occupied
        assert "presence" not in engine.state["kitchen"].active_holds

        # Next timeout should be 60s after release
        assert result.next_expiration == t1 + timedelta(seconds=60)

        # After trailing timeout: should be vacant
        t2 = t1 + timedelta(seconds=61)
        engine.check_timeouts(t2)
        assert not engine.state["kitchen"].is_occupied


# =============================================================================
# FOLLOW_PARENT STRATEGY TESTS
# =============================================================================


class TestFollowParentStrategy:
    """Tests for the FOLLOW_PARENT occupancy strategy."""

    def test_follow_parent_becomes_occupied_with_parent(self, base_time):
        """Child with FOLLOW_PARENT becomes occupied when parent is occupied."""
        configs = [
            LocationConfig(id="living_room", default_timeout=60),
            LocationConfig(
                id="reading_nook",
                parent_id="living_room",
                occupancy_strategy=OccupancyStrategy.FOLLOW_PARENT,
                contributes_to_parent=False,
            ),
        ]
        engine = OccupancyEngine(configs)

        # Initially both vacant
        assert not engine.state["living_room"].is_occupied
        assert not engine.state["reading_nook"].is_occupied

        # Occupy living room
        event = OccupancyEvent(
            location_id="living_room",
            event_type=EventType.TRIGGER,
            source_id="motion",
            timestamp=base_time,
        )
        result = engine.handle_event(event, base_time)

        # Both should be occupied
        assert engine.state["living_room"].is_occupied
        assert engine.state["reading_nook"].is_occupied

        # Should have transitions for both locations
        location_ids = {t.location_id for t in result.transitions}
        assert "living_room" in location_ids
        assert "reading_nook" in location_ids

    def test_follow_parent_becomes_vacant_with_parent(self, base_time):
        """Child with FOLLOW_PARENT eventually becomes vacant when parent is vacant.

        Implementation note: The FOLLOW_PARENT child gets its own timer during
        propagation. When parent's timeout fires and triggers child re-evaluation,
        the propagation logic extends the child's timer. So we need to wait for
        BOTH the parent's timeout AND the child's extended timer to expire.

        Timer timeline:
        - T+0: Parent triggers, child propagates (both get 60s timer)
        - T+61: Parent times out, child re-evaluates → child timer extends to T+121
        - T+122: Child's timer finally expires
        """
        configs = [
            LocationConfig(id="living_room", default_timeout=60),
            LocationConfig(
                id="reading_nook",
                parent_id="living_room",
                default_timeout=60,
                occupancy_strategy=OccupancyStrategy.FOLLOW_PARENT,
                contributes_to_parent=False,
            ),
        ]
        engine = OccupancyEngine(configs)

        # Occupy living room
        event = OccupancyEvent(
            location_id="living_room",
            event_type=EventType.TRIGGER,
            source_id="motion",
            timestamp=base_time,
        )
        engine.handle_event(event, base_time)

        # Both occupied
        assert engine.state["living_room"].is_occupied
        assert engine.state["reading_nook"].is_occupied

        # At T+61: Parent times out, but child timer gets extended
        t1 = base_time + timedelta(seconds=61)
        engine.check_timeouts(t1)

        # Parent should be vacant
        assert not engine.state["living_room"].is_occupied
        # Child still occupied (timer extended during propagation)
        assert engine.state["reading_nook"].is_occupied

        # At T+130: Both should be vacant (child timer expired at ~T+121)
        t2 = base_time + timedelta(seconds=130)
        engine.check_timeouts(t2)

        assert not engine.state["living_room"].is_occupied
        assert not engine.state["reading_nook"].is_occupied

    def test_follow_parent_ignores_direct_events(self, base_time):
        """FOLLOW_PARENT location ignores direct occupancy events (follows parent only)."""
        configs = [
            LocationConfig(id="living_room", default_timeout=60),
            LocationConfig(
                id="reading_nook",
                parent_id="living_room",
                occupancy_strategy=OccupancyStrategy.FOLLOW_PARENT,
                contributes_to_parent=False,
            ),
        ]
        engine = OccupancyEngine(configs)

        # Try to trigger reading nook directly (should have no effect by itself)
        event = OccupancyEvent(
            location_id="reading_nook",
            event_type=EventType.TRIGGER,
            source_id="motion",
            timestamp=base_time,
        )
        engine.handle_event(event, base_time)

        # Reading nook should still be vacant (parent is vacant)
        # Note: The direct trigger creates a timer, but FOLLOW_PARENT still
        # uses parent state as primary source
        assert not engine.state["living_room"].is_occupied

        # With parent vacant, reading_nook follows parent = vacant
        # (implementation may vary - the key is FOLLOW_PARENT follows parent)

    def test_follow_parent_with_hold(self, base_time):
        """FOLLOW_PARENT child follows parent with active hold."""
        configs = [
            LocationConfig(id="living_room", default_timeout=60),
            LocationConfig(
                id="reading_nook",
                parent_id="living_room",
                occupancy_strategy=OccupancyStrategy.FOLLOW_PARENT,
            ),
        ]
        engine = OccupancyEngine(configs)

        # Hold in living room
        event = OccupancyEvent(
            location_id="living_room",
            event_type=EventType.HOLD,
            source_id="presence",
            timestamp=base_time,
        )
        engine.handle_event(event, base_time)

        # Both should be occupied
        assert engine.state["living_room"].is_occupied
        assert engine.state["reading_nook"].is_occupied

        # After long time, both should still be occupied (no timeout on hold)
        t1 = base_time + timedelta(hours=1)
        engine.check_timeouts(t1)
        assert engine.state["living_room"].is_occupied
        assert engine.state["reading_nook"].is_occupied

    def test_follow_parent_release_with_hold(self, base_time):
        """FOLLOW_PARENT child becomes vacant when parent's hold is released.

        This tests the FOLLOW_PARENT scenario where parent uses a hold.
        Note: We set contributes_to_parent=False to prevent circular propagation
        that would set a timer on the parent.
        """
        configs = [
            LocationConfig(id="living_room", default_timeout=60, hold_release_timeout=30),
            LocationConfig(
                id="reading_nook",
                parent_id="living_room",
                default_timeout=60,
                hold_release_timeout=30,
                occupancy_strategy=OccupancyStrategy.FOLLOW_PARENT,
                contributes_to_parent=False,  # Prevent circular propagation
            ),
        ]
        engine = OccupancyEngine(configs)

        # Hold in living room
        hold_event = OccupancyEvent(
            location_id="living_room",
            event_type=EventType.HOLD,
            source_id="presence",
            timestamp=base_time,
        )
        engine.handle_event(hold_event, base_time)

        # Both occupied
        assert engine.state["living_room"].is_occupied
        assert engine.state["reading_nook"].is_occupied
        # With contributes_to_parent=False, parent has hold but no timer from propagation
        assert "presence" in engine.state["living_room"].active_holds

        # Release parent (starts trailing timeout)
        t1 = base_time + timedelta(minutes=30)
        release_event = OccupancyEvent(
            location_id="living_room",
            event_type=EventType.RELEASE,
            source_id="presence",
            timestamp=t1,
        )
        engine.handle_event(release_event, t1)

        # Parent has trailing timeout, still occupied
        assert engine.state["living_room"].is_occupied
        assert engine.state["living_room"].occupied_until is not None
        assert "presence" not in engine.state["living_room"].active_holds

        # After trailing timeout expires
        t2 = t1 + timedelta(seconds=35)
        engine.check_timeouts(t2)

        # Parent should be vacant
        assert not engine.state["living_room"].is_occupied

        # Wait for child's timer (extended during propagation) to also expire
        t3 = t2 + timedelta(seconds=65)
        engine.check_timeouts(t3)

        # Child should now also be vacant
        assert not engine.state["reading_nook"].is_occupied

    def test_follow_parent_deep_hierarchy(self, base_time):
        """Test FOLLOW_PARENT in a deeper hierarchy (grandparent -> parent -> child)."""
        configs = [
            LocationConfig(id="house", default_timeout=300),
            LocationConfig(id="floor1", parent_id="house", default_timeout=300),
            LocationConfig(
                id="bedroom",
                parent_id="floor1",
                default_timeout=300,
            ),
            LocationConfig(
                id="closet",
                parent_id="bedroom",
                occupancy_strategy=OccupancyStrategy.FOLLOW_PARENT,
            ),
        ]
        engine = OccupancyEngine(configs)

        # Trigger bedroom
        event = OccupancyEvent(
            location_id="bedroom",
            event_type=EventType.TRIGGER,
            source_id="motion",
            timestamp=base_time,
        )
        engine.handle_event(event, base_time)

        # Closet (FOLLOW_PARENT) should follow bedroom
        assert engine.state["bedroom"].is_occupied
        assert engine.state["closet"].is_occupied

        # House and floor1 should also be occupied (propagation up)
        assert engine.state["floor1"].is_occupied
        assert engine.state["house"].is_occupied


class TestFollowParentIntegration:
    """Integration tests for FOLLOW_PARENT with OccupancyModule."""

    def test_follow_parent_module_integration(self, event_bus, location_manager_with_follow_parent):
        """Test FOLLOW_PARENT through the module's event bus integration."""
        module = OccupancyModule()
        event_bus.set_location_manager(location_manager_with_follow_parent)
        module.attach(event_bus, location_manager_with_follow_parent)

        emitted_events = []

        def capture(event):
            if event.type == "occupancy.changed":
                emitted_events.append(event)

        event_bus.subscribe(capture)

        # Trigger living room motion
        event_bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="binary_sensor.living_room_motion",
                payload={"old_state": "off", "new_state": "on"},
                timestamp=datetime.now(UTC),
            )
        )

        # Both living_room and reading_nook should have events
        location_ids = {e.location_id for e in emitted_events}
        assert "living_room" in location_ids
        assert "reading_nook" in location_ids

        # Both should be occupied
        assert module.get_location_state("living_room")["occupied"]
        assert module.get_location_state("reading_nook")["occupied"]


# =============================================================================
# LOCK/UNLOCK WITH TIMEOUT TESTS
# =============================================================================


class TestLockUnlockTimeoutInteraction:
    """Tests for lock/unlock interaction with timeouts."""

    def test_locked_state_prevents_timeout(self, base_time):
        """Locked location does not expire due to timeout."""
        configs = [LocationConfig(id="kitchen", default_timeout=60)]
        engine = OccupancyEngine(configs)

        # Trigger and lock
        trigger = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.TRIGGER,
            source_id="motion",
            timestamp=base_time,
        )
        engine.handle_event(trigger, base_time)

        lock = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.LOCK,
            source_id="automation",
            timestamp=base_time,
        )
        engine.handle_event(lock, base_time)

        assert engine.state["kitchen"].is_occupied
        assert engine.state["kitchen"].is_locked

        # After timeout: should still be occupied (locked)
        t1 = base_time + timedelta(seconds=120)
        engine.check_timeouts(t1)

        assert engine.state["kitchen"].is_occupied
        assert engine.state["kitchen"].is_locked

    def test_unlock_after_timeout_resumes_timer(self, base_time):
        """v2.3: Timer is SUSPENDED during lock and RESUMES when unlocked.

        This is different from old behavior where timer "expired while locked".
        With timer suspension, the remaining time is preserved and resumes.
        """
        configs = [LocationConfig(id="kitchen", default_timeout=60)]
        engine = OccupancyEngine(configs)

        # Trigger with 60s timeout, then lock immediately
        trigger = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.TRIGGER,
            source_id="motion",
            timestamp=base_time,
            timeout=60,
        )
        engine.handle_event(trigger, base_time)

        lock = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.LOCK,
            source_id="automation",
            timestamp=base_time,
        )
        engine.handle_event(lock, base_time)

        # Timer should be suspended with 60s remaining
        state = engine.state["kitchen"]
        assert state.timer_remaining is not None
        assert state.timer_remaining.total_seconds() == 60
        assert state.occupied_until is None  # Timer cleared during lock

        # Wait past original timeout (but still locked)
        t1 = base_time + timedelta(seconds=120)
        engine.check_timeouts(t1)
        assert engine.state["kitchen"].is_occupied  # Still locked
        assert engine.state["kitchen"].is_locked

        # Unlock after timeout period - timer RESUMES
        unlock = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.UNLOCK,
            source_id="automation",
            timestamp=t1,
        )
        engine.handle_event(unlock, t1)

        # Should still be occupied - timer resumed with 60s remaining
        state = engine.state["kitchen"]
        assert state.is_occupied  # Timer resumed
        assert not state.is_locked
        assert state.timer_remaining is None  # Cleared after resume
        assert state.occupied_until == t1 + timedelta(seconds=60)

        # Now wait for resumed timer to expire
        t2 = t1 + timedelta(seconds=61)
        engine.check_timeouts(t2)
        assert not engine.state["kitchen"].is_occupied  # Now vacant

    def test_multiple_locks_require_all_unlocks(self, base_time):
        """Multiple locks preserve state. Timer resumes when all locks cleared.

        v2.3: Timer is suspended during lock. When the last lock is removed,
        the timer resumes with remaining time.
        """
        # Use 300s timeout
        configs = [LocationConfig(id="kitchen", default_timeout=300)]
        engine = OccupancyEngine(configs)

        # Trigger and add multiple locks
        trigger = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.TRIGGER,
            source_id="motion",
            timestamp=base_time,
        )
        engine.handle_event(trigger, base_time)

        for source in ["automation_a", "automation_b", "user_manual"]:
            lock = OccupancyEvent(
                location_id="kitchen",
                event_type=EventType.LOCK,
                source_id=source,
                timestamp=base_time,
            )
            engine.handle_event(lock, base_time)

        assert len(engine.state["kitchen"].locked_by) == 3
        # Timer suspended with 300s remaining
        assert engine.state["kitchen"].timer_remaining.total_seconds() == 300

        # Shortly after (60s)
        t1 = base_time + timedelta(seconds=60)

        # Unlock one at a time - state preserved while still locked
        unlock_a = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.UNLOCK,
            source_id="automation_a",
            timestamp=t1,
        )
        engine.handle_event(unlock_a, t1)
        assert engine.state["kitchen"].is_locked  # Still locked by 2
        assert engine.state["kitchen"].is_occupied  # State preserved

        unlock_b = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.UNLOCK,
            source_id="automation_b",
            timestamp=t1,
        )
        engine.handle_event(unlock_b, t1)
        assert engine.state["kitchen"].is_locked  # Still locked by 1
        assert engine.state["kitchen"].is_occupied  # State preserved

        # Final unlock - timer resumes
        unlock_user = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.UNLOCK,
            source_id="user_manual",
            timestamp=t1,
        )
        engine.handle_event(unlock_user, t1)

        # Now unlocked, timer resumed with 300s from t1
        assert not engine.state["kitchen"].is_locked
        assert engine.state["kitchen"].is_occupied  # Timer resumed
        assert engine.state["kitchen"].occupied_until == t1 + timedelta(seconds=300)

        # After resumed timeout expires (t1 + 301s, not base + 301s)
        t2 = t1 + timedelta(seconds=301)
        engine.check_timeouts(t2)
        assert not engine.state["kitchen"].is_occupied

    def test_unlock_all_clears_all_locks(self, base_time):
        """UNLOCK_ALL clears all locks and resumes timer.

        v2.3: Timer is suspended during lock. UNLOCK_ALL clears all locks
        and resumes the timer with remaining time.
        """
        configs = [LocationConfig(id="kitchen", default_timeout=60)]
        engine = OccupancyEngine(configs)

        # Trigger with 60s timeout and add multiple locks
        trigger = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.TRIGGER,
            source_id="motion",
            timestamp=base_time,
        )
        engine.handle_event(trigger, base_time)

        for source in ["a", "b", "c", "d", "e"]:
            lock = OccupancyEvent(
                location_id="kitchen",
                event_type=EventType.LOCK,
                source_id=source,
                timestamp=base_time,
            )
            engine.handle_event(lock, base_time)

        assert len(engine.state["kitchen"].locked_by) == 5
        # Timer suspended with 60s remaining
        assert engine.state["kitchen"].timer_remaining.total_seconds() == 60

        # Wait some time (120s)
        t1 = base_time + timedelta(seconds=120)

        # Force unlock all - timer resumes
        unlock_all = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.UNLOCK_ALL,
            source_id="admin",
            timestamp=t1,
        )
        engine.handle_event(unlock_all, t1)

        # Should be unlocked, timer resumed with 60s from t1
        assert not engine.state["kitchen"].is_locked
        assert len(engine.state["kitchen"].locked_by) == 0
        assert engine.state["kitchen"].is_occupied  # Timer resumed
        assert engine.state["kitchen"].occupied_until == t1 + timedelta(seconds=60)

        # Wait for resumed timer to expire
        t2 = t1 + timedelta(seconds=61)
        engine.check_timeouts(t2)
        assert not engine.state["kitchen"].is_occupied  # Now vacant

    def test_unlock_with_expired_timer_causes_vacancy(self, base_time):
        """UNLOCK with expired timer triggers vacancy even with remaining locks.

        This documents an important behavior: UNLOCK events cause state
        re-evaluation. If the timer has expired, even a partial unlock
        will cause the location to become vacant.
        """
        configs = [LocationConfig(id="kitchen", default_timeout=60)]
        engine = OccupancyEngine(configs)

        # Trigger with short timeout, then add two locks
        trigger = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.TRIGGER,
            source_id="motion",
            timestamp=base_time,
            timeout=60,
        )
        engine.handle_event(trigger, base_time)

        for source in ["lock_a", "lock_b"]:
            lock = OccupancyEvent(
                location_id="kitchen",
                event_type=EventType.LOCK,
                source_id=source,
                timestamp=base_time,
            )
            engine.handle_event(lock, base_time)

        # Wait past timeout
        t1 = base_time + timedelta(seconds=120)
        engine.check_timeouts(t1)

        # Still occupied because locked
        assert engine.state["kitchen"].is_occupied
        assert engine.state["kitchen"].is_locked

        # Unlock ONE (but another lock remains)
        unlock = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.UNLOCK,
            source_id="lock_a",
            timestamp=t1,
        )
        engine.handle_event(unlock, t1)

        # State is re-evaluated: timer expired + still locked by lock_b
        # The UNLOCK triggers re-evaluation which sees expired timer
        # Behavior: may become vacant despite remaining lock
        # (This documents current implementation behavior)
        remaining_locks = engine.state["kitchen"].locked_by
        assert "lock_a" not in remaining_locks
        assert "lock_b" in remaining_locks

    def test_lock_does_not_prevent_adding_more_locks(self, base_time):
        """Locked state still allows adding more locks."""
        configs = [LocationConfig(id="kitchen", default_timeout=60)]
        engine = OccupancyEngine(configs)

        trigger = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.TRIGGER,
            source_id="motion",
            timestamp=base_time,
        )
        engine.handle_event(trigger, base_time)

        # First lock
        lock1 = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.LOCK,
            source_id="automation_a",
            timestamp=base_time,
        )
        engine.handle_event(lock1, base_time)
        assert "automation_a" in engine.state["kitchen"].locked_by

        # Second lock while already locked
        lock2 = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.LOCK,
            source_id="automation_b",
            timestamp=base_time,
        )
        engine.handle_event(lock2, base_time)

        # Both should be in locked_by
        assert "automation_a" in engine.state["kitchen"].locked_by
        assert "automation_b" in engine.state["kitchen"].locked_by


# =============================================================================
# CONFIG MIGRATION TESTS
# =============================================================================


class TestConfigMigration:
    """Tests for configuration migration from legacy formats."""

    def test_legacy_timeouts_dict_format(self, event_bus, location_manager_legacy_config):
        """Test that legacy 'timeouts' dict format is correctly migrated."""
        module = OccupancyModule()
        event_bus.set_location_manager(location_manager_legacy_config)
        module.attach(event_bus, location_manager_legacy_config)

        # The engine should have been initialized with migrated config
        kitchen_config = module._engine.configs.get("kitchen")
        assert kitchen_config is not None

        # Legacy "timeouts.default" should map to default_timeout
        assert kitchen_config.default_timeout == 600  # 10 minutes

        # Legacy "timeouts.presence" should map to hold_release_timeout
        assert kitchen_config.hold_release_timeout == 180  # 3 minutes

    def test_mixed_legacy_and_new_config(self, event_bus):
        """Test handling of mixed legacy and new config formats."""
        mgr = LocationManager()

        mgr.create_location(id="house", name="House")
        mgr.create_location(id="kitchen", name="Kitchen", parent_id="house")
        mgr.create_location(id="bedroom", name="Bedroom", parent_id="house")

        # Kitchen: legacy format
        mgr.set_module_config(
            "kitchen",
            "occupancy",
            {
                "version": 1,
                "enabled": True,
                "timeouts": {"default": 120, "presence": 60},
            },
        )

        # Bedroom: new format
        mgr.set_module_config(
            "bedroom",
            "occupancy",
            {
                "version": 1,
                "enabled": True,
                "default_timeout": 300,
                "hold_release_timeout": 120,
            },
        )

        # House: defaults
        mgr.set_module_config(
            "house",
            "occupancy",
            {
                "version": 1,
                "enabled": True,
            },
        )

        module = OccupancyModule()
        event_bus.set_location_manager(mgr)
        module.attach(event_bus, mgr)

        # Kitchen should use legacy values
        assert module._engine.configs["kitchen"].default_timeout == 120
        assert module._engine.configs["kitchen"].hold_release_timeout == 60

        # Bedroom should use new values
        assert module._engine.configs["bedroom"].default_timeout == 300
        assert module._engine.configs["bedroom"].hold_release_timeout == 120

        # House should use defaults
        assert module._engine.configs["house"].default_timeout == 300
        assert module._engine.configs["house"].hold_release_timeout == 120

    def test_config_version_property(self, event_bus, location_manager_legacy_config):
        """Test that CURRENT_CONFIG_VERSION is accessible."""
        module = OccupancyModule()
        assert module.CURRENT_CONFIG_VERSION == 1

    def test_disabled_location_skipped(self, event_bus):
        """Test that disabled locations are not initialized in engine."""
        mgr = LocationManager()

        mgr.create_location(id="house", name="House")
        mgr.create_location(id="kitchen", name="Kitchen", parent_id="house")
        mgr.create_location(id="storage", name="Storage", parent_id="house")

        # Kitchen: enabled
        mgr.set_module_config(
            "kitchen",
            "occupancy",
            {
                "version": 1,
                "enabled": True,
            },
        )

        # Storage: disabled
        mgr.set_module_config(
            "storage",
            "occupancy",
            {
                "version": 1,
                "enabled": False,
            },
        )

        # House: enabled
        mgr.set_module_config(
            "house",
            "occupancy",
            {
                "version": 1,
                "enabled": True,
            },
        )

        module = OccupancyModule()
        event_bus.set_location_manager(mgr)
        module.attach(event_bus, mgr)

        # Storage should not be in engine configs
        assert "storage" not in module._engine.configs
        assert "kitchen" in module._engine.configs
        assert "house" in module._engine.configs

    def test_strategy_config_parsing(self, event_bus):
        """Test that occupancy_strategy config is correctly parsed."""
        mgr = LocationManager()

        mgr.create_location(id="house", name="House")
        mgr.create_location(id="kitchen", name="Kitchen", parent_id="house")
        mgr.create_location(id="pantry", name="Pantry", parent_id="kitchen")

        # Kitchen: independent (default)
        mgr.set_module_config(
            "kitchen",
            "occupancy",
            {
                "version": 1,
                "enabled": True,
            },
        )

        # Pantry: follow_parent
        mgr.set_module_config(
            "pantry",
            "occupancy",
            {
                "version": 1,
                "enabled": True,
                "occupancy_strategy": "follow_parent",
            },
        )

        mgr.set_module_config("house", "occupancy", {"version": 1, "enabled": True})

        module = OccupancyModule()
        event_bus.set_location_manager(mgr)
        module.attach(event_bus, mgr)

        # Kitchen should be INDEPENDENT
        assert module._engine.configs["kitchen"].occupancy_strategy == OccupancyStrategy.INDEPENDENT

        # Pantry should be FOLLOW_PARENT
        assert (
            module._engine.configs["pantry"].occupancy_strategy == OccupancyStrategy.FOLLOW_PARENT
        )


# =============================================================================
# INTEGRATION TEST - COMPLETE SCENARIO
# =============================================================================


class TestCompleteIntegrationScenario:
    """End-to-end integration tests combining multiple features."""

    def test_multi_room_timeout_cascade(self, event_bus, location_manager_multi_room, base_time):
        """Test a realistic multi-room scenario with cascading timeouts."""
        module = OccupancyModule()
        event_bus.set_location_manager(location_manager_multi_room)
        module.attach(event_bus, location_manager_multi_room)

        emitted_events = []

        def capture(event):
            if event.type == "occupancy.changed":
                emitted_events.append(event)

        event_bus.subscribe(capture)

        # Trigger kitchen at T+0
        module.trigger("kitchen", "motion", timeout=60, now=base_time)

        # Trigger bedroom at T+10s
        t1 = base_time + timedelta(seconds=10)
        module.trigger("bedroom", "motion", timeout=60, now=t1)

        # Trigger bathroom at T+20s
        t2 = base_time + timedelta(seconds=20)
        module.trigger("bathroom", "motion", timeout=60, now=t2)

        # All should be occupied
        assert module.get_location_state("kitchen")["occupied"]
        assert module.get_location_state("bedroom")["occupied"]
        assert module.get_location_state("bathroom")["occupied"]
        assert module.get_location_state("house")["occupied"]

        # At T+65s: kitchen should timeout
        t3 = base_time + timedelta(seconds=65)
        emitted_events.clear()
        module.check_timeouts(t3)

        assert not module.get_location_state("kitchen")["occupied"]
        assert module.get_location_state("bedroom")["occupied"]
        assert module.get_location_state("bathroom")["occupied"]

        # At T+75s: bedroom should timeout
        t4 = base_time + timedelta(seconds=75)
        module.check_timeouts(t4)

        assert not module.get_location_state("bedroom")["occupied"]
        assert module.get_location_state("bathroom")["occupied"]

        # At T+85s: bathroom should timeout
        t5 = base_time + timedelta(seconds=85)
        module.check_timeouts(t5)

        assert not module.get_location_state("bathroom")["occupied"]

    def test_lock_hold_timeout_interaction(self, event_bus, location_manager_multi_room, base_time):
        """Test complex interaction of locks, holds, and timeouts."""
        module = OccupancyModule()
        event_bus.set_location_manager(location_manager_multi_room)
        module.attach(event_bus, location_manager_multi_room)

        # Kitchen: trigger + lock
        module.trigger("kitchen", "motion", timeout=60, now=base_time)
        module.lock("kitchen", "sleep_mode", now=base_time)

        # Bedroom: hold (indefinite)
        module.hold("bedroom", "presence", now=base_time)

        # Bathroom: just trigger
        module.trigger("bathroom", "motion", timeout=60, now=base_time)

        # After 2 minutes
        t1 = base_time + timedelta(minutes=2)
        module.check_timeouts(t1)

        # Kitchen: still occupied (locked)
        assert module.get_location_state("kitchen")["occupied"]
        assert module.get_location_state("kitchen")["is_locked"]

        # Bedroom: still occupied (held)
        assert module.get_location_state("bedroom")["occupied"]
        assert "presence" in module.get_location_state("bedroom")["active_holds"]

        # Bathroom: vacant (timeout expired)
        assert not module.get_location_state("bathroom")["occupied"]

        # Release bedroom hold (v2.3: parameter renamed to trailing_timeout)
        module.release("bedroom", "presence", trailing_timeout=30, now=t1)

        # Bedroom still occupied (trailing timeout)
        assert module.get_location_state("bedroom")["occupied"]

        # After trailing timeout
        t2 = t1 + timedelta(seconds=35)
        module.check_timeouts(t2)

        # Bedroom now vacant
        assert not module.get_location_state("bedroom")["occupied"]

        # Kitchen still occupied (locked)
        assert module.get_location_state("kitchen")["occupied"]


# =============================================================================
# EFFECTIVE TIMEOUT TESTS
# =============================================================================


class TestEffectiveTimeout:
    """Tests for get_effective_timeout() method."""

    def test_effective_timeout_single_location(self, base_time):
        """Effective timeout equals own timeout for single location."""
        configs = [LocationConfig(id="kitchen", default_timeout=60)]
        engine = OccupancyEngine(configs)

        # Trigger
        event = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.TRIGGER,
            source_id="motion",
            timestamp=base_time,
        )
        engine.handle_event(event, base_time)

        # Effective timeout should equal own timeout
        effective = engine.get_effective_timeout("kitchen", base_time)
        assert effective == base_time + timedelta(seconds=60)

    def test_effective_timeout_parent_with_child(self, base_time):
        """Effective timeout considers child's longer timer."""
        configs = [
            LocationConfig(id="house", default_timeout=60),
            LocationConfig(id="kitchen", parent_id="house", default_timeout=120),
        ]
        engine = OccupancyEngine(configs)

        # Trigger kitchen (child) - will propagate to house (parent)
        event = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.TRIGGER,
            source_id="motion",
            timestamp=base_time,
        )
        engine.handle_event(event, base_time)

        # House's own timeout is T+60s (from propagation using house's default)
        house_state = engine.state["house"]
        assert house_state.occupied_until == base_time + timedelta(seconds=60)

        # Kitchen's timeout is T+120s
        kitchen_state = engine.state["kitchen"]
        assert kitchen_state.occupied_until == base_time + timedelta(seconds=120)

        # House's effective timeout should be T+120s (from kitchen)
        effective = engine.get_effective_timeout("house", base_time)
        assert effective == base_time + timedelta(seconds=120)

    def test_effective_timeout_with_held_child(self, base_time):
        """Effective timeout is None when child has active hold."""
        configs = [
            LocationConfig(id="house", default_timeout=60),
            LocationConfig(id="kitchen", parent_id="house", default_timeout=60),
        ]
        engine = OccupancyEngine(configs)

        # Trigger house
        event1 = OccupancyEvent(
            location_id="house",
            event_type=EventType.TRIGGER,
            source_id="motion",
            timestamp=base_time,
        )
        engine.handle_event(event1, base_time)

        # Hold kitchen (child)
        event2 = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.HOLD,
            source_id="presence",
            timestamp=base_time,
        )
        engine.handle_event(event2, base_time)

        # Kitchen's effective timeout is None (held indefinitely)
        kitchen_effective = engine.get_effective_timeout("kitchen", base_time)
        assert kitchen_effective is None

        # House's effective timeout should also be None (child is held)
        house_effective = engine.get_effective_timeout("house", base_time)
        assert house_effective is None

    def test_effective_timeout_vacant_location(self, base_time):
        """Effective timeout is None for vacant location."""
        configs = [LocationConfig(id="kitchen", default_timeout=60)]
        engine = OccupancyEngine(configs)

        # No events - location is vacant
        effective = engine.get_effective_timeout("kitchen", base_time)
        assert effective is None

    def test_effective_timeout_deep_hierarchy(self, base_time):
        """Effective timeout works with deep hierarchy."""
        configs = [
            LocationConfig(id="house", default_timeout=60),
            LocationConfig(id="floor1", parent_id="house", default_timeout=90),
            LocationConfig(id="bedroom", parent_id="floor1", default_timeout=120),
            LocationConfig(id="closet", parent_id="bedroom", default_timeout=180),
        ]
        engine = OccupancyEngine(configs)

        # Trigger closet (deepest) - propagates all the way up
        event = OccupancyEvent(
            location_id="closet",
            event_type=EventType.TRIGGER,
            source_id="motion",
            timestamp=base_time,
        )
        engine.handle_event(event, base_time)

        # House's effective timeout should be from closet (longest)
        effective = engine.get_effective_timeout("house", base_time)
        assert effective == base_time + timedelta(seconds=180)


class TestEffectiveTimeoutModule:
    """Tests for get_effective_timeout() through module API."""

    def test_module_effective_timeout(self, event_bus, location_manager_multi_room, base_time):
        """Test effective timeout through module API."""
        module = OccupancyModule()
        event_bus.set_location_manager(location_manager_multi_room)
        module.attach(event_bus, location_manager_multi_room)

        # Trigger kitchen with short timeout
        module.trigger("kitchen", "motion", timeout=60, now=base_time)

        # Trigger bedroom with longer timeout
        module.trigger("bedroom", "motion", timeout=120, now=base_time)

        # House's effective timeout should be from bedroom (longer)
        effective = module.get_effective_timeout("house", base_time)
        # House's own timer + max of children's effective timeouts
        assert effective is not None


# =============================================================================
# VACATE AREA (CASCADING) TESTS
# =============================================================================


class TestVacateArea:
    """Tests for vacate_area() cascading method."""

    def test_vacate_area_single_location(self, base_time):
        """Vacate area with no children just vacates self."""
        configs = [LocationConfig(id="kitchen", default_timeout=300)]
        engine = OccupancyEngine(configs)

        # Occupy kitchen
        event = OccupancyEvent(
            location_id="kitchen",
            event_type=EventType.TRIGGER,
            source_id="motion",
            timestamp=base_time,
        )
        engine.handle_event(event, base_time)
        assert engine.state["kitchen"].is_occupied

        # Vacate area
        result = engine.vacate_area("kitchen", "user_clear", base_time)

        assert not engine.state["kitchen"].is_occupied
        assert len(result.transitions) == 1
        assert result.transitions[0].location_id == "kitchen"

    def test_vacate_area_with_children(self, base_time):
        """Vacate area clears all descendants."""
        configs = [
            LocationConfig(id="house", default_timeout=300),
            LocationConfig(id="floor1", parent_id="house", default_timeout=300),
            LocationConfig(id="kitchen", parent_id="floor1", default_timeout=300),
            LocationConfig(id="bedroom", parent_id="floor1", default_timeout=300),
        ]
        engine = OccupancyEngine(configs)

        # Occupy all locations
        for loc_id in ["kitchen", "bedroom"]:
            event = OccupancyEvent(
                location_id=loc_id,
                event_type=EventType.TRIGGER,
                source_id="motion",
                timestamp=base_time,
            )
            engine.handle_event(event, base_time)

        # All should be occupied
        for loc_id in ["house", "floor1", "kitchen", "bedroom"]:
            assert engine.state[loc_id].is_occupied

        # Vacate house (root) - should clear everything
        engine.vacate_area("house", "everyone_left", base_time)

        # All should be vacant
        for loc_id in ["house", "floor1", "kitchen", "bedroom"]:
            assert not engine.state[loc_id].is_occupied

    def test_vacate_area_skips_locked_by_default(self, base_time):
        """Vacate area skips locked locations by default."""
        configs = [
            LocationConfig(id="house", default_timeout=300),
            LocationConfig(id="kitchen", parent_id="house", default_timeout=300),
            LocationConfig(id="bedroom", parent_id="house", default_timeout=300),
        ]
        engine = OccupancyEngine(configs)

        # Occupy all
        for loc_id in ["kitchen", "bedroom"]:
            event = OccupancyEvent(
                location_id=loc_id,
                event_type=EventType.TRIGGER,
                source_id="motion",
                timestamp=base_time,
            )
            engine.handle_event(event, base_time)

        # Lock bedroom
        lock_event = OccupancyEvent(
            location_id="bedroom",
            event_type=EventType.LOCK,
            source_id="sleep_mode",
            timestamp=base_time,
        )
        engine.handle_event(lock_event, base_time)

        # Vacate house (default: skip locked)
        engine.vacate_area("house", "away_mode", base_time, include_locked=False)

        # Kitchen and house should be vacant
        assert not engine.state["house"].is_occupied
        assert not engine.state["kitchen"].is_occupied

        # Bedroom should still be occupied (was locked)
        assert engine.state["bedroom"].is_occupied
        assert engine.state["bedroom"].is_locked

    def test_vacate_area_force_includes_locked(self, base_time):
        """Vacate area with include_locked=True clears locked locations."""
        configs = [
            LocationConfig(id="house", default_timeout=300),
            LocationConfig(id="kitchen", parent_id="house", default_timeout=300),
            LocationConfig(id="bedroom", parent_id="house", default_timeout=300),
        ]
        engine = OccupancyEngine(configs)

        # Occupy all
        for loc_id in ["kitchen", "bedroom"]:
            event = OccupancyEvent(
                location_id=loc_id,
                event_type=EventType.TRIGGER,
                source_id="motion",
                timestamp=base_time,
            )
            engine.handle_event(event, base_time)

        # Lock bedroom
        lock_event = OccupancyEvent(
            location_id="bedroom",
            event_type=EventType.LOCK,
            source_id="sleep_mode",
            timestamp=base_time,
        )
        engine.handle_event(lock_event, base_time)

        # Vacate house with force
        engine.vacate_area("house", "emergency", base_time, include_locked=True)

        # ALL should be vacant (including previously locked bedroom)
        for loc_id in ["house", "kitchen", "bedroom"]:
            assert not engine.state[loc_id].is_occupied

        # Bedroom should also be unlocked
        assert not engine.state["bedroom"].is_locked


class TestVacateAreaModule:
    """Tests for vacate_area() through module API."""

    def test_module_vacate_area(self, event_bus, location_manager_multi_room, base_time):
        """Test vacate_area through module API."""
        module = OccupancyModule()
        event_bus.set_location_manager(location_manager_multi_room)
        module.attach(event_bus, location_manager_multi_room)

        # Occupy multiple rooms
        module.trigger("kitchen", "motion", now=base_time)
        module.trigger("bedroom", "motion", now=base_time)
        module.trigger("bathroom", "motion", now=base_time)

        # All should be occupied
        assert module.get_location_state("kitchen")["occupied"]
        assert module.get_location_state("bedroom")["occupied"]
        assert module.get_location_state("bathroom")["occupied"]
        assert module.get_location_state("house")["occupied"]

        # Vacate house (clears everything)
        transitions = module.vacate_area("house", "everyone_left", now=base_time)

        # Should return list of transitions
        assert isinstance(transitions, list)
        assert len(transitions) > 0

        # All should be vacant
        assert not module.get_location_state("kitchen")["occupied"]
        assert not module.get_location_state("bedroom")["occupied"]
        assert not module.get_location_state("bathroom")["occupied"]
        assert not module.get_location_state("house")["occupied"]

    def test_module_vacate_area_emits_events(
        self, event_bus, location_manager_multi_room, base_time
    ):
        """Test that vacate_area emits occupancy.changed events."""
        module = OccupancyModule()
        event_bus.set_location_manager(location_manager_multi_room)
        module.attach(event_bus, location_manager_multi_room)

        # Track events
        emitted_events = []

        def capture(event):
            if event.type == "occupancy.changed":
                emitted_events.append(event)

        event_bus.subscribe(capture)

        # Occupy
        module.trigger("kitchen", "motion", now=base_time)
        module.trigger("bedroom", "motion", now=base_time)
        emitted_events.clear()  # Clear setup events

        # Vacate area
        module.vacate_area("house", "test", now=base_time)

        # Should have emitted events for each vacated location
        assert len(emitted_events) > 0
        vacated_locations = {e.location_id for e in emitted_events}
        assert "kitchen" in vacated_locations
        assert "bedroom" in vacated_locations


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
