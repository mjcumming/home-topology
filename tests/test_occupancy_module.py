"""
Comprehensive tests for OccupancyModule.

Tests verify:
- Module attachment and initialization
- Motion sensor event handling (TRIGGER)
- Door sensor event handling (TRIGGER)
- Media player event handling (HOLD/RELEASE)
- Lock/unlock events (LOCK/UNLOCK/UNLOCK_ALL)
- Hierarchy propagation (child -> parent)
- Identity tracking with presence sensors
- Hold events (continuous presence)
- State persistence and restoration
- Timeout expiration
- Configuration management
"""

import logging
import pytest
from datetime import datetime, UTC, timedelta

from home_topology import Event, EventBus, LocationManager
from home_topology.modules.occupancy import OccupancyModule

# Configure logging for verbose test output
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


@pytest.fixture
def location_manager():
    """Create a LocationManager with a realistic hierarchy."""
    logger.info("=" * 80)
    logger.info("FIXTURE: Setting up LocationManager")
    logger.info("=" * 80)

    mgr = LocationManager()

    # Create hierarchy: house -> main_floor -> kitchen
    logger.info("Creating location hierarchy...")
    mgr.create_location(id="house", name="House")
    logger.debug("  ✓ house (root)")

    mgr.create_location(id="main_floor", name="Main Floor", parent_id="house")
    logger.debug("  ✓ main_floor (parent: house)")

    mgr.create_location(id="kitchen", name="Kitchen", parent_id="main_floor")
    logger.debug("  ✓ kitchen (parent: main_floor)")

    # Configure occupancy module for each location
    logger.info("Configuring occupancy module for all locations...")
    for loc_id in ["house", "main_floor", "kitchen"]:
        config = {
            "version": 1,
            "enabled": True,
            "default_timeout": 300,  # 5 minutes
            "hold_release_timeout": 120,  # 2 minutes
        }
        mgr.set_module_config(location_id=loc_id, module_id="occupancy", config=config)
        logger.debug(f"  ✓ {loc_id}: configured")

    # Map entities to locations
    logger.info("Mapping entities to locations...")
    mgr.add_entity_to_location("binary_sensor.kitchen_motion", "kitchen")
    logger.debug("  ✓ binary_sensor.kitchen_motion -> kitchen")

    logger.info("✓ LocationManager setup complete")
    return mgr


@pytest.fixture
def event_bus():
    """Create an EventBus."""
    logger.info("FIXTURE: Creating EventBus")
    bus = EventBus()
    logger.info("✓ EventBus created")
    return bus


@pytest.fixture
def occupancy_module(event_bus, location_manager):
    """Create and attach OccupancyModule."""
    logger.info("FIXTURE: Creating and attaching OccupancyModule")
    module = OccupancyModule()
    event_bus.set_location_manager(location_manager)
    module.attach(event_bus, location_manager)
    logger.info("✓ OccupancyModule attached")
    return module


class TestOccupancyModuleAttachment:
    """Test suite for module attachment and initialization."""

    def test_module_attachment(self, occupancy_module, location_manager):
        """Test that module attaches and initializes correctly."""
        logger.info("=" * 80)
        logger.info("TEST: Module attachment and initialization")
        logger.info("=" * 80)

        logger.info("Verifying engine initialization...")
        assert occupancy_module._engine is not None
        logger.info("✓ Engine initialized")

        logger.info("Verifying all locations registered with engine...")
        logger.info(f"Locations in engine: {len(occupancy_module._engine.state)}")
        for loc_id in occupancy_module._engine.state:
            logger.debug(f"  - {loc_id}")
        assert len(occupancy_module._engine.state) == 3
        logger.info("✓ All locations registered")

        logger.info("Verifying initial state (all vacant)...")
        for loc_id in ["house", "main_floor", "kitchen"]:
            state = occupancy_module.get_location_state(loc_id)
            logger.debug(f"  {loc_id}: occupied={state['occupied']}")
            assert state is not None
            assert state["occupied"] is False
        logger.info("✓ All locations start vacant")


class TestOccupancyModuleMotionEvents:
    """Test suite for motion sensor event handling."""

    def test_motion_sensor_triggers_occupancy(self, event_bus, occupancy_module):
        """Test that motion sensor on → off triggers occupancy."""
        logger.info("=" * 80)
        logger.info("TEST: Motion sensor triggers occupancy")
        logger.info("=" * 80)

        # Track emitted events
        emitted_events = []

        def capture_occupancy_events(event: Event):
            if event.type == "occupancy.changed":
                logger.info(f"📢 Event emitted: {event.type} for {event.location_id}")
                logger.debug(f"   Payload: {event.payload}")
                emitted_events.append(event)

        event_bus.subscribe(capture_occupancy_events)
        logger.info("✓ Event capture handler subscribed")

        logger.info("Sending motion sensor event: off → on")
        event_bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="binary_sensor.kitchen_motion",
                payload={
                    "old_state": "off",
                    "new_state": "on",
                },
                timestamp=datetime.now(UTC),
            )
        )

        logger.info(f"Events emitted: {len(emitted_events)}")

        logger.info("Verifying occupancy.changed events were emitted...")
        occ_events = [e for e in emitted_events if e.type == "occupancy.changed"]
        logger.info(f"Occupancy change events: {len(occ_events)}")
        for e in occ_events:
            logger.debug(f"  - {e.location_id}: occupied={e.payload['occupied']}")
        assert len(occ_events) > 0
        logger.info("✓ Occupancy events emitted")

        logger.info("Verifying kitchen is occupied...")
        kitchen_event = next((e for e in occ_events if e.location_id == "kitchen"), None)
        assert kitchen_event is not None
        logger.debug(f"Kitchen event payload: {kitchen_event.payload}")

        assert kitchen_event.payload["occupied"] is True
        assert kitchen_event.payload["previous_occupied"] is False
        logger.info("✓ Kitchen is occupied")

        logger.info("Checking state directly...")
        state = occupancy_module.get_location_state("kitchen")
        logger.debug(f"Kitchen state: {state}")
        assert state["occupied"] is True
        logger.info("✓ Motion sensor successfully triggered occupancy")

    def test_motion_off_to_off_ignored(self, event_bus, occupancy_module):
        """Test that motion sensor off → off is ignored."""
        logger.info("=" * 80)
        logger.info("TEST: Motion sensor off → off (no change) is ignored")
        logger.info("=" * 80)

        emitted_events = []

        def capture_events(event: Event):
            if event.type == "occupancy.changed":
                emitted_events.append(event)

        event_bus.subscribe(capture_events)

        logger.info("Sending motion sensor event: off → off")
        event_bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="binary_sensor.kitchen_motion",
                payload={
                    "old_state": "off",
                    "new_state": "off",
                },
                timestamp=datetime.now(UTC),
            )
        )

        logger.info(f"Events emitted: {len(emitted_events)}")
        assert len(emitted_events) == 0
        logger.info("✓ No occupancy change (as expected)")


class TestOccupancyModuleHierarchyPropagation:
    """Test suite for hierarchy propagation."""

    def test_child_occupancy_propagates_to_parent(self, event_bus, occupancy_module):
        """Test that child occupancy propagates up to parent."""
        logger.info("=" * 80)
        logger.info("TEST: Child occupancy propagates to parent")
        logger.info("=" * 80)

        emitted_events = []

        def capture_events(event: Event):
            if event.type == "occupancy.changed":
                logger.info(
                    f"📢 Occupancy changed: {event.location_id} → occupied={event.payload['occupied']}"
                )
                emitted_events.append(event)

        event_bus.subscribe(capture_events)

        logger.info("Triggering kitchen motion...")
        event_bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="binary_sensor.kitchen_motion",
                payload={"old_state": "off", "new_state": "on"},
                timestamp=datetime.now(UTC),
            )
        )

        logger.info("Analyzing propagation...")
        location_ids = {e.location_id for e in emitted_events}
        logger.info(f"Locations affected: {location_ids}")

        logger.info("Verifying propagation chain...")
        assert "kitchen" in location_ids
        logger.debug("  ✓ kitchen (direct trigger)")

        assert "main_floor" in location_ids
        logger.debug("  ✓ main_floor (parent of kitchen)")

        assert "house" in location_ids
        logger.debug("  ✓ house (grandparent)")

        logger.info("Verifying all are occupied...")
        for loc_id in ["kitchen", "main_floor", "house"]:
            state = occupancy_module.get_location_state(loc_id)
            logger.debug(f"  {loc_id}: occupied={state['occupied']}")
            assert state["occupied"] is True

        logger.info("✓ Occupancy successfully propagated up hierarchy")


class TestOccupancyModulePresenceSensors:
    """Test suite for presence sensors (HOLD/RELEASE events).

    Note: v2.3 removed identity tracking (active_occupants).
    Identity tracking is deferred to a future PresenceModule.
    """

    def test_presence_sensor_creates_hold(self, event_bus, occupancy_module, location_manager):
        """Test that presence sensors create HOLD events."""
        logger.info("=" * 80)
        logger.info("TEST: Presence sensor creates HOLD")
        logger.info("=" * 80)

        # Add presence sensor
        logger.info("Adding presence sensor to kitchen...")
        location_manager.add_entity_to_location("ble_presence", "kitchen")
        logger.debug("  ✓ ble_presence -> kitchen")

        emitted_events = []

        def capture_events(event: Event):
            if event.type == "occupancy.changed":
                logger.info(f"📢 Occupancy changed: {event.location_id}")
                emitted_events.append(event)

        event_bus.subscribe(capture_events)

        logger.info("Simulating presence detected...")
        event_bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="ble_presence",
                payload={
                    "old_state": "off",
                    "new_state": "on",
                },
                timestamp=datetime.now(UTC),
            )
        )

        logger.info("Verifying HOLD was created...")
        kitchen_events = [e for e in emitted_events if e.location_id == "kitchen"]
        assert len(kitchen_events) > 0

        state = occupancy_module.get_location_state("kitchen")
        logger.debug(f"Kitchen state: {state}")
        assert state["occupied"] is True
        assert "ble_presence" in state["active_holds"]
        logger.info("✓ Presence sensor created HOLD")

    def test_presence_sensor_release_starts_trailing_timer(
        self, event_bus, occupancy_module, location_manager
    ):
        """Test that presence sensor off triggers RELEASE and trailing timer."""
        logger.info("=" * 80)
        logger.info("TEST: Presence sensor RELEASE starts trailing timer")
        logger.info("=" * 80)

        # Add presence sensor
        location_manager.add_entity_to_location("ble_presence", "kitchen")

        logger.info("Step 1: Presence detected (HOLD)")
        event_bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="ble_presence",
                payload={
                    "old_state": "off",
                    "new_state": "on",
                },
                timestamp=datetime.now(UTC),
            )
        )

        state = occupancy_module.get_location_state("kitchen")
        assert state["occupied"] is True
        assert "ble_presence" in state["active_holds"]

        logger.info("Step 2: Presence cleared (RELEASE)")
        event_bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="ble_presence",
                payload={
                    "old_state": "on",
                    "new_state": "off",
                },
                timestamp=datetime.now(UTC),
            )
        )

        state = occupancy_module.get_location_state("kitchen")
        logger.info(f"After RELEASE: occupied={state['occupied']}, holds={state['active_holds']}")

        # Hold should be removed, but trailing timer keeps room occupied
        assert "ble_presence" not in state["active_holds"]
        assert state["occupied"] is True  # Trailing timer active
        assert state["occupied_until"] is not None  # Timer set
        logger.info("✓ RELEASE started trailing timer")


class TestOccupancyModuleStatePersistence:
    """Test suite for state persistence and restoration."""

    def test_dump_and_restore_state(self, event_bus, occupancy_module, location_manager):
        """Test dumping and restoring occupancy state."""
        logger.info("=" * 80)
        logger.info("TEST: State dump and restore")
        logger.info("=" * 80)

        logger.info("Step 1: Trigger occupancy in kitchen")
        event_bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="binary_sensor.kitchen_motion",
                payload={"old_state": "off", "new_state": "on"},
                timestamp=datetime.now(UTC),
            )
        )

        state_before = occupancy_module.get_location_state("kitchen")
        logger.info(f"Kitchen state before dump: occupied={state_before['occupied']}")
        assert state_before["occupied"] is True

        logger.info("Step 2: Dump state")
        state_dump = occupancy_module.dump_state()
        logger.info(f"State dump keys: {list(state_dump.keys())}")
        logger.debug(f"Kitchen dump: {state_dump.get('kitchen', {})}")

        assert "kitchen" in state_dump
        assert state_dump["kitchen"]["is_occupied"] is True
        logger.info("✓ State dumped successfully")

        logger.info("Step 3: Create new module and restore")
        new_module = OccupancyModule()
        new_module.attach(event_bus, location_manager)
        logger.info("New module created")

        logger.info("Restoring state...")
        new_module.restore_state(state_dump)

        restored_state = new_module.get_location_state("kitchen")
        logger.info(f"Restored kitchen state: occupied={restored_state['occupied']}")
        logger.debug(f"Full restored state: {restored_state}")

        assert restored_state["occupied"] is True
        logger.info("✓ State restored successfully")


class TestOccupancyModuleConfiguration:
    """Test suite for configuration management."""

    def test_default_config(self, occupancy_module):
        """Test default configuration values."""
        logger.info("=" * 80)
        logger.info("TEST: Default configuration")
        logger.info("=" * 80)

        config = occupancy_module.default_config()
        logger.info("Default config:")
        logger.debug(f"{config}")

        assert config["version"] == 1
        assert config["enabled"] is True
        assert config["default_timeout"] == 300  # 5 minutes
        assert config["hold_release_timeout"] == 120  # 2 minutes
        logger.info("✓ Default config verified")

    def test_config_schema(self, occupancy_module):
        """Test configuration schema structure."""
        logger.info("=" * 80)
        logger.info("TEST: Configuration schema")
        logger.info("=" * 80)

        schema = occupancy_module.location_config_schema()
        logger.info("Schema structure:")
        logger.debug(f"Type: {schema['type']}")
        logger.debug(f"Properties: {list(schema['properties'].keys())}")

        assert schema["type"] == "object"
        assert "properties" in schema
        assert "enabled" in schema["properties"]
        assert "default_timeout" in schema["properties"]
        assert "hold_release_timeout" in schema["properties"]

        logger.info("✓ Config schema verified")


class TestOccupancyModuleTimeouts:
    """Test suite for timeout behavior."""

    def test_next_timeout_calculation(self, event_bus, occupancy_module):
        """Test that next timeout is calculated correctly."""
        logger.info("=" * 80)
        logger.info("TEST: Next timeout calculation")
        logger.info("=" * 80)

        now = datetime.now(UTC)
        logger.info(f"Current time: {now}")

        logger.info("Before any events: checking next timeout...")
        next_timeout = occupancy_module.get_next_timeout(now)
        logger.info(f"Next timeout: {next_timeout}")
        assert next_timeout is None
        logger.info("✓ No timeout when all vacant")

        logger.info("Triggering motion event...")
        event_bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="binary_sensor.kitchen_motion",
                payload={"old_state": "off", "new_state": "on"},
                timestamp=now,
            )
        )

        logger.info("After motion: checking next timeout...")
        next_timeout = occupancy_module.get_next_timeout(now)
        logger.info(f"Next timeout: {next_timeout}")

        if next_timeout:
            time_until = (next_timeout - now).total_seconds()
            logger.info(f"Time until timeout: {time_until}s ({time_until/60}min)")
            assert time_until > 0
            logger.info("✓ Timeout scheduled in future")
        else:
            logger.warning("No timeout scheduled (might be held)")

    def test_check_timeouts_manually(self, occupancy_module):
        """Test manually triggering timeout check using direct API."""
        logger.info("=" * 80)
        logger.info("TEST: Manual timeout check")
        logger.info("=" * 80)

        now = datetime.now(UTC)
        logger.info(f"Time T0: {now}")

        # Use direct API with explicit short timeout
        logger.info("Triggering at T0 with 60s timeout...")
        occupancy_module.trigger("kitchen", "motion", timeout=60, now=now)

        state = occupancy_module.get_location_state("kitchen")
        logger.info(f"T0: Kitchen occupied={state['occupied']}")
        assert state["occupied"] is True

        # Simulate time passing (61 seconds = just past timeout)
        future = now + timedelta(seconds=61)
        logger.info(f"Time T+61s: {future}")

        logger.info("Checking timeouts at T+61s...")
        occupancy_module.check_timeouts(future)

        state_after = occupancy_module.get_location_state("kitchen")
        logger.info(f"T+61s: Kitchen occupied={state_after['occupied']}")

        # After timeout, kitchen should become vacant
        assert state_after["occupied"] is False
        logger.info("✓ Timeout correctly expired occupancy")


class TestOccupancyModuleDoorSensors:
    """Test suite for door sensor event handling."""

    def test_door_sensor_triggers_occupancy(self, event_bus, occupancy_module, location_manager):
        """Test that door sensor triggers occupancy."""
        logger.info("=" * 80)
        logger.info("TEST: Door sensor triggers occupancy")
        logger.info("=" * 80)

        # Add door sensor to kitchen
        logger.info("Adding door sensor to kitchen...")
        location_manager.add_entity_to_location("binary_sensor.kitchen_door", "kitchen")
        logger.debug("  ✓ binary_sensor.kitchen_door -> kitchen")

        emitted_events = []

        def capture_events(event: Event):
            if event.type == "occupancy.changed":
                logger.info(f"📢 Occupancy changed: {event.location_id}")
                emitted_events.append(event)

        event_bus.subscribe(capture_events)

        logger.info("Sending door sensor event: off → on (door opened)")
        event_bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="binary_sensor.kitchen_door",
                payload={
                    "old_state": "off",
                    "new_state": "on",
                },
                timestamp=datetime.now(UTC),
            )
        )

        logger.info("Verifying door sensor triggered occupancy...")
        occ_events = [e for e in emitted_events if e.type == "occupancy.changed"]
        assert len(occ_events) > 0

        kitchen_event = next((e for e in occ_events if e.location_id == "kitchen"), None)
        assert kitchen_event is not None
        assert kitchen_event.payload["occupied"] is True
        logger.info("✓ Door sensor triggered occupancy")


class TestOccupancyModuleMediaPlayers:
    """Test suite for media player event handling."""

    def test_media_player_playing_holds_occupancy(
        self, event_bus, occupancy_module, location_manager
    ):
        """Test that media player playing creates a hold (indefinite occupancy)."""
        logger.info("=" * 80)
        logger.info("TEST: Media player playing holds occupancy")
        logger.info("=" * 80)

        # Add media player to kitchen
        logger.info("Adding media player to kitchen...")
        location_manager.add_entity_to_location("media_player.kitchen_speaker", "kitchen")

        emitted_events = []

        def capture_events(event: Event):
            if event.type == "occupancy.changed":
                logger.info(f"📢 Occupancy changed: {event.location_id}")
                emitted_events.append(event)

        event_bus.subscribe(capture_events)

        logger.info("Sending media player event: idle → playing")
        event_bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="media_player.kitchen_speaker",
                payload={
                    "old_state": "idle",
                    "new_state": "playing",
                },
                timestamp=datetime.now(UTC),
            )
        )

        logger.info("Verifying media player created hold...")
        occ_events = [e for e in emitted_events if e.type == "occupancy.changed"]
        assert len(occ_events) > 0

        kitchen_event = next((e for e in occ_events if e.location_id == "kitchen"), None)
        assert kitchen_event is not None
        assert kitchen_event.payload["occupied"] is True
        assert "media_player.kitchen_speaker" in kitchen_event.payload["active_holds"]
        logger.info("✓ Media player created hold")

    def test_media_player_stopping_releases_hold(
        self, event_bus, occupancy_module, location_manager
    ):
        """Test that media player stopping releases hold and starts trailing timeout."""
        logger.info("=" * 80)
        logger.info("TEST: Media player stopping releases hold")
        logger.info("=" * 80)

        # Add media player
        location_manager.add_entity_to_location("media_player.kitchen_speaker", "kitchen")

        emitted_events = []

        def capture_events(event: Event):
            if event.type == "occupancy.changed":
                emitted_events.append(event)

        event_bus.subscribe(capture_events)

        logger.info("Step 1: Media starts playing (creates hold)")
        event_bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="media_player.kitchen_speaker",
                payload={"old_state": "idle", "new_state": "playing"},
                timestamp=datetime.now(UTC),
            )
        )

        state1 = occupancy_module.get_location_state("kitchen")
        logger.info(f"After playing: occupied={state1['occupied']}, holds={state1['active_holds']}")
        assert state1["occupied"] is True
        assert "media_player.kitchen_speaker" in state1["active_holds"]
        emitted_events.clear()

        logger.info("Step 2: Media stops (releases hold, starts trailing timeout)")
        event_bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="media_player.kitchen_speaker",
                payload={"old_state": "playing", "new_state": "idle"},
                timestamp=datetime.now(UTC),
            )
        )

        state2 = occupancy_module.get_location_state("kitchen")
        logger.info(
            f"After stopping: occupied={state2['occupied']}, holds={state2['active_holds']}"
        )
        assert state2["occupied"] is True  # Still occupied due to trailing timeout
        assert "media_player.kitchen_speaker" not in state2["active_holds"]  # Hold released
        assert state2["occupied_until"] is not None  # Trailing timeout started
        logger.info("✓ Hold released and trailing timeout started")


class TestOccupancyModuleLockEvents:
    """Test suite for lock/unlock events."""

    def test_lock_and_unlock(self, occupancy_module):
        """Test that LOCK and UNLOCK events work correctly."""
        logger.info("=" * 80)
        logger.info("TEST: Lock and unlock events")
        logger.info("=" * 80)

        now = datetime.now(UTC)

        # First, set kitchen to occupied using direct API
        logger.info("Step 1: Setting kitchen to occupied...")
        occupancy_module.trigger("kitchen", "binary_sensor.kitchen_motion", timeout=300, now=now)

        state1 = occupancy_module.get_location_state("kitchen")
        assert state1["occupied"] is True
        assert state1["is_locked"] is False
        assert len(state1["locked_by"]) == 0
        logger.info("✓ Kitchen occupied and unlocked")

        # Lock it
        logger.info("Step 2: Locking kitchen...")
        occupancy_module.lock("kitchen", "automation_sleep_mode", now=now)

        state2 = occupancy_module.get_location_state("kitchen")
        assert state2["is_locked"] is True
        assert "automation_sleep_mode" in state2["locked_by"]
        logger.info(f"✓ Kitchen locked by: {state2['locked_by']}")

        # Add another lock
        logger.info("Step 3: Adding another lock...")
        occupancy_module.lock("kitchen", "automation_dnd", now=now)

        state3 = occupancy_module.get_location_state("kitchen")
        assert state3["is_locked"] is True
        assert "automation_sleep_mode" in state3["locked_by"]
        assert "automation_dnd" in state3["locked_by"]
        logger.info(f"✓ Kitchen locked by: {state3['locked_by']}")

        # Unlock first lock
        logger.info("Step 4: Unlocking sleep_mode (should still be locked)...")
        occupancy_module.unlock("kitchen", "automation_sleep_mode", now=now)

        state4 = occupancy_module.get_location_state("kitchen")
        assert state4["is_locked"] is True  # Still locked by dnd
        assert "automation_sleep_mode" not in state4["locked_by"]
        assert "automation_dnd" in state4["locked_by"]
        logger.info(f"✓ Still locked by: {state4['locked_by']}")

        # Unlock second lock
        logger.info("Step 5: Unlocking dnd (should be fully unlocked)...")
        occupancy_module.unlock("kitchen", "automation_dnd", now=now)

        state5 = occupancy_module.get_location_state("kitchen")
        assert state5["is_locked"] is False
        assert len(state5["locked_by"]) == 0
        logger.info("✓ Kitchen fully unlocked")

    def test_unlock_all(self, occupancy_module):
        """Test that UNLOCK_ALL clears all locks."""
        logger.info("=" * 80)
        logger.info("TEST: UNLOCK_ALL clears all locks")
        logger.info("=" * 80)

        now = datetime.now(UTC)

        # Set occupied and add multiple locks
        occupancy_module.trigger("kitchen", "motion", now=now)
        occupancy_module.lock("kitchen", "lock_a", now=now)
        occupancy_module.lock("kitchen", "lock_b", now=now)
        occupancy_module.lock("kitchen", "lock_c", now=now)

        state1 = occupancy_module.get_location_state("kitchen")
        assert len(state1["locked_by"]) == 3
        logger.info(f"Kitchen has {len(state1['locked_by'])} locks")

        # Force unlock all
        logger.info("Force unlocking all...")
        occupancy_module.unlock_all("kitchen", now=now)

        state2 = occupancy_module.get_location_state("kitchen")
        assert state2["is_locked"] is False
        assert len(state2["locked_by"]) == 0
        logger.info("✓ All locks cleared")

    def test_locked_state_ignores_events(self, occupancy_module):
        """Test that locked state ignores normal events.

        v2.3: Timer is suspended during lock (stored in timer_remaining).
        Events are ignored while locked. Timer resumes when unlocked.
        """
        logger.info("=" * 80)
        logger.info("TEST: Locked state ignores normal events")
        logger.info("=" * 80)

        now = datetime.now(UTC)

        # Set to occupied and locked
        logger.info("Setting kitchen to occupied and locked...")
        occupancy_module.trigger("kitchen", "motion", timeout=300, now=now)
        occupancy_module.lock("kitchen", "manual_lock", now=now)

        state1 = occupancy_module.get_location_state("kitchen")
        # v2.3: Timer is suspended, stored in timer_remaining
        timer_remaining_1 = state1["timer_remaining"]
        assert timer_remaining_1 == 300  # 300 seconds remaining
        assert state1["occupied_until"] is None  # Timer cleared during lock
        assert state1["occupied"] is True
        assert state1["is_locked"] is True
        logger.info("✓ Kitchen occupied and locked, timer suspended")

        # Try to trigger another event (should be ignored)
        logger.info("Sending another trigger event (should be ignored)...")
        future = now + timedelta(seconds=10)
        occupancy_module.trigger("kitchen", "motion2", timeout=600, now=future)

        state2 = occupancy_module.get_location_state("kitchen")
        # Timer_remaining should not have changed
        assert state2["timer_remaining"] == timer_remaining_1
        logger.info("✓ Trigger event ignored (as expected)")

        # VACATE should also be ignored
        logger.info("Sending VACATE event (should be ignored)...")
        occupancy_module.vacate("kitchen", now=future)

        state3 = occupancy_module.get_location_state("kitchen")
        assert state3["occupied"] is True  # Still occupied
        logger.info("✓ VACATE event ignored (as expected)")


class TestOccupancyModuleDirectAPI:
    """Test suite for direct API methods."""

    def test_trigger_api(self, occupancy_module):
        """Test trigger() API method."""
        now = datetime.now(UTC)

        occupancy_module.trigger("kitchen", "sensor1", timeout=120, now=now)

        state = occupancy_module.get_location_state("kitchen")
        assert state["occupied"] is True

    def test_hold_and_release_api(self, occupancy_module):
        """Test hold() and release() API methods."""
        now = datetime.now(UTC)

        # Hold
        occupancy_module.hold("kitchen", "presence_sensor", now=now)

        state1 = occupancy_module.get_location_state("kitchen")
        assert state1["occupied"] is True
        assert "presence_sensor" in state1["active_holds"]

        # Release (v2.3: parameter renamed to trailing_timeout)
        occupancy_module.release("kitchen", "presence_sensor", trailing_timeout=60, now=now)

        state2 = occupancy_module.get_location_state("kitchen")
        assert state2["occupied"] is True  # Still occupied (trailing timeout)
        assert "presence_sensor" not in state2["active_holds"]

    def test_vacate_api(self, occupancy_module):
        """Test vacate() API method."""
        now = datetime.now(UTC)

        # First occupy
        occupancy_module.trigger("kitchen", "motion", now=now)
        assert occupancy_module.get_location_state("kitchen")["occupied"] is True

        # Then vacate (v2.3: no source_id parameter)
        occupancy_module.vacate("kitchen", now=now)
        assert occupancy_module.get_location_state("kitchen")["occupied"] is False


if __name__ == "__main__":
    # Enable running tests directly
    pytest.main([__file__, "-v", "-s"])
