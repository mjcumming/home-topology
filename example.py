#!/usr/bin/env python3
"""
Quick example demonstrating home-topology basic usage.

Run with: python3 -c "import sys; sys.path.insert(0, 'src'); exec(open('example.py').read())"
Or set PYTHONPATH: PYTHONPATH=src python3 example.py
"""

from datetime import datetime, UTC
from home_topology.core.manager import LocationManager
from home_topology.core.bus import EventBus, Event
from home_topology.modules.occupancy.module import OccupancyModule

print("=" * 60)
print("home-topology Example")
print("=" * 60)

# 1. Kernel components
print("\n1. Creating kernel components...")
loc_mgr = LocationManager()
bus = EventBus()
bus.set_location_manager(loc_mgr)
print("   ✓ LocationManager and EventBus created")

# 2. Create a simple topology
print("\n2. Building topology...")
house = loc_mgr.create_location(
    id="house",
    name="House",
)
print(f"   ✓ Created: {house.name} (id={house.id})")

main_floor = loc_mgr.create_location(
    id="main_floor",
    name="Main Floor",
    parent_id="house",
)
print(f"   ✓ Created: {main_floor.name} (id={main_floor.id})")

kitchen = loc_mgr.create_location(
    id="kitchen",
    name="Kitchen",
    parent_id="main_floor",
    ha_area_id="area.kitchen",
)
print(f"   ✓ Created: {kitchen.name} (id={kitchen.id})")

# Map a motion sensor entity to the kitchen
loc_mgr.add_entity_to_location("binary_sensor.kitchen_motion", "kitchen")
print("   ✓ Mapped binary_sensor.kitchen_motion → kitchen")

# 3. Attach the Occupancy module
print("\n3. Attaching Occupancy module...")
occupancy = OccupancyModule()
occupancy.attach(bus, loc_mgr)
print(f"   ✓ Module '{occupancy.id}' attached")

# Configure the module for kitchen
loc_mgr.set_module_config(
    location_id="kitchen",
    module_id="occupancy",
    config={
        "version": occupancy.CURRENT_CONFIG_VERSION,
        "motion_sensors": ["binary_sensor.kitchen_motion"],
        "timeout_seconds": 300,
        "enabled": True,
    },
)
print("   ✓ Configuration set for kitchen")

# 4. Demonstrate hierarchy queries
print("\n4. Querying topology...")
ancestors = loc_mgr.ancestors_of("kitchen")
print(f"   ✓ Ancestors of kitchen: {[a.name for a in ancestors]}")

descendants = loc_mgr.descendants_of("house")
print(f"   ✓ Descendants of house: {[d.name for d in descendants]}")

children = loc_mgr.children_of("main_floor")
print(f"   ✓ Children of main_floor: {[c.name for c in children]}")

# 5. Publish a test event
print("\n5. Publishing test event...")
event = Event(
    type="sensor.state_changed",
    source="example",
    location_id="kitchen",
    entity_id="binary_sensor.kitchen_motion",
    payload={"old_state": "off", "new_state": "on"},
    timestamp=datetime.now(UTC),
)
bus.publish(event)
print(f"   ✓ Published: {event.type} for {event.entity_id}")

# 6. Query occupancy state (placeholder implementation)
print("\n6. Querying occupancy state...")
state = occupancy.get_location_state("kitchen")
print(f"   ✓ Kitchen occupancy: occupied={state['occupied']}, confidence={state['confidence']}")

print("\n" + "=" * 60)
print("Example complete! The kernel is ready for development.")
print("=" * 60)
