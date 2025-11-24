"""
Integration tests for OccupancyModule.

Tests the native integration of the occupancy engine with home-topology.
"""

import pytest
from datetime import datetime, UTC, timedelta

from home_topology import Location, Event, EventBus, LocationManager
from home_topology.modules.occupancy import OccupancyModule


@pytest.fixture
def location_manager():
    """Create a LocationManager with a simple hierarchy."""
    mgr = LocationManager()
    
    # Create hierarchy: house -> main_floor -> kitchen
    mgr.create_location(id="house", name="House")
    mgr.create_location(id="main_floor", name="Main Floor", parent_id="house")
    mgr.create_location(id="kitchen", name="Kitchen", parent_id="main_floor")
    
    # Configure occupancy module for each location
    for loc_id in ["house", "main_floor", "kitchen"]:
        mgr.set_module_config(
            location_id=loc_id,
            module_id="occupancy",
            config={
                "version": 1,
                "enabled": True,
                "timeouts": {
                    "default": 600,  # 10 min
                    "motion": 300,   # 5 min
                    "presence": 600,
                },
            },
        )
    
    # Map motion sensor to kitchen
    mgr.add_entity_to_location("binary_sensor.kitchen_motion", "kitchen")
    
    return mgr


@pytest.fixture
def event_bus():
    """Create an EventBus."""
    return EventBus()


@pytest.fixture
def occupancy_module(event_bus, location_manager):
    """Create and attach OccupancyModule."""
    module = OccupancyModule()
    event_bus.set_location_manager(location_manager)
    module.attach(event_bus, location_manager)
    return module


def test_module_attachment(occupancy_module, location_manager):
    """Test that module attaches and initializes engine."""
    assert occupancy_module._engine is not None
    assert len(occupancy_module._engine.state) == 3  # house, main_floor, kitchen
    
    # All should start vacant
    for loc_id in ["house", "main_floor", "kitchen"]:
        state = occupancy_module.get_location_state(loc_id)
        assert state is not None
        assert state["occupied"] is False
        assert state["confidence"] == 0.0


def test_motion_sensor_triggers_occupancy(event_bus, occupancy_module, location_manager):
    """Test that motion sensor triggers occupancy."""
    # Track emitted events
    emitted_events = []
    
    def capture_occupancy_events(event: Event):
        emitted_events.append(event)
    
    event_bus.subscribe(
        capture_occupancy_events,
        event_filter=None  # Capture all events
    )
    
    # Send motion sensor event (off → on)
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
    
    # Should emit occupancy.changed event
    occ_events = [e for e in emitted_events if e.type == "occupancy.changed"]
    assert len(occ_events) > 0
    
    # Kitchen should be occupied
    occ_event = next(e for e in occ_events if e.location_id == "kitchen")
    assert occ_event.payload["occupied"] is True
    assert occ_event.payload["confidence"] > 0.0
    assert occ_event.payload["previous_occupied"] is False
    
    # Check state directly
    state = occupancy_module.get_location_state("kitchen")
    assert state["occupied"] is True


def test_hierarchy_propagation(event_bus, occupancy_module, location_manager):
    """Test that child occupancy propagates to parent."""
    emitted_events = []
    
    def capture_events(event: Event):
        if event.type == "occupancy.changed":
            emitted_events.append(event)
    
    event_bus.subscribe(capture_events)
    
    # Trigger kitchen motion
    event_bus.publish(
        Event(
            type="sensor.state_changed",
            source="ha",
            entity_id="binary_sensor.kitchen_motion",
            payload={"old_state": "off", "new_state": "on"},
            timestamp=datetime.now(UTC),
        )
    )
    
    # Should have occupancy events for: kitchen, main_floor, house
    location_ids = {e.location_id for e in emitted_events}
    assert "kitchen" in location_ids
    assert "main_floor" in location_ids
    assert "house" in location_ids
    
    # All should be occupied
    for loc_id in ["kitchen", "main_floor", "house"]:
        state = occupancy_module.get_location_state(loc_id)
        assert state["occupied"] is True


def test_identity_tracking(event_bus, occupancy_module, location_manager):
    """Test identity tracking with presence sensors."""
    # Add presence sensor
    location_manager.add_entity_to_location("ble_mike", "kitchen")
    
    emitted_events = []
    
    def capture_events(event: Event):
        if event.type == "occupancy.changed":
            emitted_events.append(event)
    
    event_bus.subscribe(capture_events)
    
    # Mike arrives (presence sensor on)
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
    
    # Check emitted event has occupant
    kitchen_event = next(e for e in emitted_events if e.location_id == "kitchen")
    assert "Mike" in kitchen_event.payload["active_occupants"]
    
    # Check state
    state = occupancy_module.get_location_state("kitchen")
    assert "Mike" in state["active_occupants"]
    assert state["occupied"] is True


def test_state_persistence(event_bus, occupancy_module, location_manager):
    """Test state dump and restore."""
    # Trigger occupancy
    event_bus.publish(
        Event(
            type="sensor.state_changed",
            source="ha",
            entity_id="binary_sensor.kitchen_motion",
            payload={"old_state": "off", "new_state": "on"},
            timestamp=datetime.now(UTC),
        )
    )
    
    # Kitchen should be occupied
    assert occupancy_module.get_location_state("kitchen")["occupied"] is True
    
    # Dump state
    state_dump = occupancy_module.dump_state()
    assert "kitchen" in state_dump
    assert state_dump["kitchen"]["is_occupied"] is True
    
    # Create new module and restore
    new_module = OccupancyModule()
    new_module.attach(event_bus, location_manager)
    new_module.restore_state(state_dump)
    
    # Should have restored occupied state
    restored_state = new_module.get_location_state("kitchen")
    assert restored_state["occupied"] is True


def test_timeout_expiration(event_bus, occupancy_module, location_manager):
    """Test that occupancy expires after timeout."""
    import time
    
    # Set very short timeout for testing (1 second)
    location_manager.set_module_config(
        location_id="kitchen",
        module_id="occupancy",
        config={
            "version": 1,
            "enabled": True,
            "timeouts": {
                "motion": 1,  # 1 second (converted to minutes in engine)
            },
        },
    )
    
    # Recreate module with new config
    occupancy_module = OccupancyModule()
    occupancy_module.attach(event_bus, location_manager)
    
    emitted_events = []
    
    def capture_events(event: Event):
        if event.type == "occupancy.changed":
            emitted_events.append(event)
    
    event_bus.subscribe(capture_events)
    
    # Trigger motion
    event_bus.publish(
        Event(
            type="sensor.state_changed",
            source="ha",
            entity_id="binary_sensor.kitchen_motion",
            payload={"old_state": "off", "new_state": "on"},
            timestamp=datetime.now(UTC),
        )
    )
    
    # Should be occupied
    assert occupancy_module.get_location_state("kitchen")["occupied"] is True
    emitted_events.clear()
    
    # Wait for timeout (note: engine uses minutes, so 1 min = 60 seconds)
    # For real testing we'd need to mock time or use shorter intervals
    # This is a placeholder showing the test structure


def test_default_config(occupancy_module):
    """Test default configuration."""
    config = occupancy_module.default_config()
    
    assert config["version"] == 1
    assert config["enabled"] is True
    assert "timeouts" in config
    assert config["timeouts"]["motion"] == 300  # seconds
    assert config["timeouts"]["presence"] == 600


def test_config_schema(occupancy_module):
    """Test configuration schema."""
    schema = occupancy_module.location_config_schema()
    
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "enabled" in schema["properties"]
    assert "timeouts" in schema["properties"]
    
    # Check timeout properties
    timeout_props = schema["properties"]["timeouts"]["properties"]
    assert "motion" in timeout_props
    assert "presence" in timeout_props
    assert timeout_props["motion"]["minimum"] == 30

