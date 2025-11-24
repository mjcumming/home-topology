"""
Basic smoke tests for home-topology core components.
"""

from home_topology import Location, Event, EventBus, LocationManager


def test_location_creation():
    """Test basic Location dataclass creation."""
    loc = Location(
        id="kitchen",
        name="Kitchen",
        parent_id="main_floor",
    )
    assert loc.id == "kitchen"
    assert loc.name == "Kitchen"
    assert loc.parent_id == "main_floor"
    assert loc.entity_ids == []
    assert loc.modules == {}


def test_location_manager_create():
    """Test LocationManager location creation."""
    mgr = LocationManager()

    # Create root location
    house = mgr.create_location(id="house", name="House")
    assert house.id == "house"
    assert house.parent_id is None

    # Create child location
    floor = mgr.create_location(
        id="main_floor",
        name="Main Floor",
        parent_id="house",
    )
    assert floor.parent_id == "house"

    # Verify retrieval
    assert mgr.get_location("house") == house
    assert mgr.get_location("main_floor") == floor


def test_location_manager_hierarchy():
    """Test LocationManager hierarchy queries."""
    mgr = LocationManager()

    # Build hierarchy: house -> main_floor -> kitchen
    mgr.create_location(id="house", name="House")
    mgr.create_location(id="main_floor", name="Main Floor", parent_id="house")
    mgr.create_location(id="kitchen", name="Kitchen", parent_id="main_floor")

    # Test parent_of
    assert mgr.parent_of("kitchen").id == "main_floor"
    assert mgr.parent_of("main_floor").id == "house"
    assert mgr.parent_of("house") is None

    # Test children_of
    children = mgr.children_of("main_floor")
    assert len(children) == 1
    assert children[0].id == "kitchen"

    # Test ancestors_of
    ancestors = mgr.ancestors_of("kitchen")
    assert len(ancestors) == 2
    assert ancestors[0].id == "main_floor"
    assert ancestors[1].id == "house"

    # Test descendants_of
    descendants = mgr.descendants_of("house")
    assert len(descendants) == 2
    assert {d.id for d in descendants} == {"main_floor", "kitchen"}


def test_location_manager_entities():
    """Test entity-to-location mapping."""
    mgr = LocationManager()
    mgr.create_location(id="kitchen", name="Kitchen")

    # Map entity
    mgr.add_entity_to_location("binary_sensor.kitchen_motion", "kitchen")

    # Verify mapping
    assert mgr.get_entity_location("binary_sensor.kitchen_motion") == "kitchen"

    # Verify entity appears in location
    kitchen = mgr.get_location("kitchen")
    assert "binary_sensor.kitchen_motion" in kitchen.entity_ids


def test_event_bus_publish_subscribe():
    """Test basic event publishing and subscription."""
    bus = EventBus()

    # Track received events
    received = []

    def handler(event: Event):
        received.append(event)

    # Subscribe
    bus.subscribe(handler)

    # Publish event
    event = Event(
        type="test.event",
        source="test",
        payload={"data": "value"},
    )
    bus.publish(event)

    # Verify received
    assert len(received) == 1
    assert received[0].type == "test.event"
    assert received[0].payload["data"] == "value"


def test_event_bus_filtering():
    """Test event filtering by type."""
    from home_topology.core.bus import EventFilter

    bus = EventBus()

    # Track specific event types
    motion_events = []
    occupancy_events = []

    def motion_handler(event: Event):
        motion_events.append(event)

    def occupancy_handler(event: Event):
        occupancy_events.append(event)

    # Subscribe with filters
    bus.subscribe(motion_handler, EventFilter(event_type="sensor.state_changed"))
    bus.subscribe(occupancy_handler, EventFilter(event_type="occupancy.changed"))

    # Publish different events
    bus.publish(Event(type="sensor.state_changed", source="test"))
    bus.publish(Event(type="occupancy.changed", source="test"))
    bus.publish(Event(type="other.event", source="test"))

    # Verify filtering
    assert len(motion_events) == 1
    assert len(occupancy_events) == 1


def test_module_config():
    """Test module configuration storage."""
    mgr = LocationManager()
    mgr.create_location(id="kitchen", name="Kitchen")

    # Set module config
    config = {
        "version": 1,
        "motion_sensors": ["binary_sensor.kitchen_motion"],
        "timeout_seconds": 300,
    }
    mgr.set_module_config("kitchen", "occupancy", config)

    # Retrieve config
    retrieved = mgr.get_module_config("kitchen", "occupancy")
    assert retrieved == config
    assert retrieved["timeout_seconds"] == 300
