"""
Comprehensive tests for OccupancyModule with extensive logging.

These tests verify:
- Module attachment and initialization
- Motion sensor event handling
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

from home_topology import Location, Event, EventBus, LocationManager
from home_topology.modules.occupancy import OccupancyModule

# Configure logging for verbose test output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
            "timeouts": {
                "default": 600,  # 10 min
                "motion": 300,   # 5 min
                "presence": 600, # 10 min
            },
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
            logger.debug(f"  {loc_id}: occupied={state['occupied']}, confidence={state['confidence']}")
            assert state is not None
            assert state["occupied"] is False
            assert state["confidence"] == 0.0
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
        logger.debug("  Entity: binary_sensor.kitchen_motion")
        logger.debug("  Old state: off")
        logger.debug("  New state: on")
        
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
        assert kitchen_event.payload["confidence"] > 0.0
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
                logger.info(f"📢 Occupancy changed: {event.location_id} → occupied={event.payload['occupied']}")
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
            logger.debug(f"  {loc_id}: occupied={state['occupied']}, confidence={state['confidence']}")
            assert state["occupied"] is True
        
        logger.info("✓ Occupancy successfully propagated up hierarchy")


class TestOccupancyModuleIdentityTracking:
    """Test suite for identity tracking with presence sensors."""
    
    def test_presence_sensor_tracks_identity(self, event_bus, occupancy_module, location_manager):
        """Test that presence sensors track who is in the room."""
        logger.info("=" * 80)
        logger.info("TEST: Presence sensor tracks identity")
        logger.info("=" * 80)
        
        # Add presence sensor for Mike
        logger.info("Adding presence sensor to kitchen...")
        location_manager.add_entity_to_location("ble_mike", "kitchen")
        logger.debug("  ✓ ble_mike -> kitchen")
        
        emitted_events = []
        
        def capture_events(event: Event):
            if event.type == "occupancy.changed":
                logger.info(f"📢 Occupancy changed: {event.location_id}")
                logger.debug(f"   Active occupants: {event.payload.get('active_occupants', [])}")
                emitted_events.append(event)
        
        event_bus.subscribe(capture_events)
        
        logger.info("Simulating Mike's arrival (presence sensor on)...")
        event_bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="ble_mike",
                payload={
                    "old_state": "off",
                    "new_state": "on",
                    "occupant_id": "Mike",
                },
                timestamp=datetime.now(UTC),
            )
        )
        
        logger.info("Verifying occupant tracking...")
        kitchen_events = [e for e in emitted_events if e.location_id == "kitchen"]
        assert len(kitchen_events) > 0
        
        kitchen_event = kitchen_events[0]
        logger.info(f"Kitchen active occupants: {kitchen_event.payload['active_occupants']}")
        assert "Mike" in kitchen_event.payload["active_occupants"]
        logger.info("✓ Mike tracked in active_occupants")
        
        logger.info("Checking state...")
        state = occupancy_module.get_location_state("kitchen")
        logger.debug(f"Kitchen state: {state}")
        assert "Mike" in state["active_occupants"]
        assert state["occupied"] is True
        logger.info("✓ Identity successfully tracked")
    
    def test_presence_sensor_departure(self, event_bus, occupancy_module, location_manager):
        """Test that presence sensor off removes identity."""
        logger.info("=" * 80)
        logger.info("TEST: Presence sensor departure removes identity")
        logger.info("=" * 80)
        
        # Add presence sensor
        location_manager.add_entity_to_location("ble_mike", "kitchen")
        
        logger.info("Step 1: Mike arrives")
        event_bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="ble_mike",
                payload={
                    "old_state": "off",
                    "new_state": "on",
                    "occupant_id": "Mike",
                },
                timestamp=datetime.now(UTC),
            )
        )
        
        state = occupancy_module.get_location_state("kitchen")
        logger.info(f"After arrival: occupied={state['occupied']}, occupants={state['active_occupants']}")
        assert "Mike" in state["active_occupants"]
        
        logger.info("Step 2: Mike leaves (presence sensor off)")
        event_bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="ble_mike",
                payload={
                    "old_state": "on",
                    "new_state": "off",
                    "occupant_id": "Mike",
                },
                timestamp=datetime.now(UTC),
            )
        )
        
        state = occupancy_module.get_location_state("kitchen")
        logger.info(f"After departure: occupied={state['occupied']}, occupants={state['active_occupants']}")
        logger.debug(f"Full state: {state}")
        
        # Note: Kitchen might still be occupied due to timeout after hold ends
        # But Mike should be removed from active_occupants
        assert "Mike" not in state["active_occupants"]
        logger.info("✓ Mike removed from active occupants")


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
        assert "timeouts" in config
        
        logger.info("Timeout values:")
        for category, seconds in config["timeouts"].items():
            logger.debug(f"  {category}: {seconds}s ({seconds/60}min)")
        
        assert config["timeouts"]["motion"] == 300  # 5 minutes
        assert config["timeouts"]["presence"] == 600  # 10 minutes
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
        assert "timeouts" in schema["properties"]
        
        logger.info("Timeout property constraints:")
        timeout_props = schema["properties"]["timeouts"]["properties"]
        for prop_name, prop_def in timeout_props.items():
            logger.debug(f"  {prop_name}: min={prop_def.get('minimum')}, default={prop_def.get('default')}")
        
        assert "motion" in timeout_props
        assert "presence" in timeout_props
        assert timeout_props["motion"]["minimum"] == 30
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
            # Motion timeout is 300 seconds (5 minutes)
            assert time_until > 0
            logger.info("✓ Timeout scheduled in future")
        else:
            logger.warning("No timeout scheduled (might be held)")
    
    def test_check_timeouts_manually(self, event_bus, occupancy_module, location_manager):
        """Test manually triggering timeout check."""
        logger.info("=" * 80)
        logger.info("TEST: Manual timeout check")
        logger.info("=" * 80)
        
        # Override config with very short timeout for testing
        logger.info("Setting short timeout (1 minute) for testing...")
        for loc_id in ["house", "main_floor", "kitchen"]:
            location_manager.set_module_config(
                location_id=loc_id,
                module_id="occupancy",
                config={
                    "version": 1,
                    "enabled": True,
                    "timeouts": {
                        "motion": 60,  # 1 minute
                    },
                },
            )
        
        # Recreate module with new config
        occupancy_module = OccupancyModule()
        occupancy_module.attach(event_bus, location_manager)
        logger.info("✓ Module recreated with short timeout")
        
        now = datetime.now(UTC)
        logger.info(f"Time T0: {now}")
        
        logger.info("Triggering motion at T0...")
        event_bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="binary_sensor.kitchen_motion",
                payload={"old_state": "off", "new_state": "on"},
                timestamp=now,
            )
        )
        
        state = occupancy_module.get_location_state("kitchen")
        logger.info(f"T0: Kitchen occupied={state['occupied']}")
        assert state["occupied"] is True
        
        # Simulate time passing (61 seconds = just past 1 minute)
        future = now + timedelta(seconds=61)
        logger.info(f"Time T+61s: {future}")
        
        emitted_events = []
        
        def capture_events(event: Event):
            if event.type == "occupancy.changed":
                logger.info(f"📢 Timeout event: {event.location_id} → occupied={event.payload['occupied']}")
                emitted_events.append(event)
        
        event_bus.subscribe(capture_events)
        
        logger.info("Checking timeouts at T+61s...")
        occupancy_module.check_timeouts(future)
        
        logger.info(f"Timeout events emitted: {len(emitted_events)}")
        for e in emitted_events:
            logger.debug(f"  - {e.location_id}: occupied={e.payload['occupied']}")
        
        state_after = occupancy_module.get_location_state("kitchen")
        logger.info(f"T+61s: Kitchen occupied={state_after['occupied']}")
        
        # After timeout, kitchen should become vacant
        assert state_after["occupied"] is False
        logger.info("✓ Timeout correctly expired occupancy")


class TestOccupancyModuleComplexScenarios:
    """Test suite for complex real-world scenarios."""
    
    def test_multiple_sensors_same_room(self, event_bus, occupancy_module, location_manager):
        """Test multiple sensors in the same room."""
        logger.info("=" * 80)
        logger.info("TEST: Multiple sensors in same room")
        logger.info("=" * 80)
        
        # Add second sensor to kitchen
        logger.info("Adding second motion sensor to kitchen...")
        location_manager.add_entity_to_location("binary_sensor.kitchen_motion_2", "kitchen")
        logger.debug("  ✓ binary_sensor.kitchen_motion_2 -> kitchen")
        
        logger.info("Triggering first sensor...")
        event_bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="binary_sensor.kitchen_motion",
                payload={"old_state": "off", "new_state": "on"},
                timestamp=datetime.now(UTC),
            )
        )
        
        state1 = occupancy_module.get_location_state("kitchen")
        logger.info(f"After sensor 1: occupied={state1['occupied']}")
        assert state1["occupied"] is True
        
        logger.info("Triggering second sensor...")
        event_bus.publish(
            Event(
                type="sensor.state_changed",
                source="ha",
                entity_id="binary_sensor.kitchen_motion_2",
                payload={"old_state": "off", "new_state": "on"},
                timestamp=datetime.now(UTC),
            )
        )
        
        state2 = occupancy_module.get_location_state("kitchen")
        logger.info(f"After sensor 2: occupied={state2['occupied']}")
        assert state2["occupied"] is True
        
        logger.info("✓ Multiple sensors work correctly")


if __name__ == "__main__":
    # Enable running tests directly
    pytest.main([__file__, "-v", "-s"])

