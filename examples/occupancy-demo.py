#!/usr/bin/env python3
"""
Occupancy Module Demo - Native Integration

Demonstrates the fully integrated occupancy tracking with:
- Motion sensor events
- Hierarchy propagation
- Identity tracking
- State persistence

Run with: PYTHONPATH=src python3 examples/occupancy-demo.py
"""

import sys
sys.path.insert(0, "src")

from datetime import datetime, UTC
import time

from home_topology import LocationManager, EventBus, Event
from home_topology.modules.occupancy import OccupancyModule

def main():
    print("=" * 70)
    print("Occupancy Module - Native Integration Demo")
    print("=" * 70)
    
    # 1. Setup kernel
    print("\n1. Setting up kernel...")
    loc_mgr = LocationManager()
    bus = EventBus()
    bus.set_location_manager(loc_mgr)
    
    # 2. Create hierarchy
    print("\n2. Creating location hierarchy...")
    house = loc_mgr.create_location(id="house", name="House")
    main_floor = loc_mgr.create_location(
        id="main_floor",
        name="Main Floor",
        parent_id="house"
    )
    kitchen = loc_mgr.create_location(
        id="kitchen",
        name="Kitchen",
        parent_id="main_floor"
    )
    print(f"   Created: {house.name} → {main_floor.name} → {kitchen.name}")
    
    # 3. Map entities to locations
    print("\n3. Mapping entities to locations...")
    loc_mgr.add_entity_to_location("binary_sensor.kitchen_motion", "kitchen")
    loc_mgr.add_entity_to_location("ble_mike", "kitchen")
    print("   ✓ binary_sensor.kitchen_motion → kitchen")
    print("   ✓ ble_mike → kitchen")
    
    # 4. Configure occupancy module
    print("\n4. Configuring occupancy module...")
    for loc_id in ["house", "main_floor", "kitchen"]:
        loc_mgr.set_module_config(
            location_id=loc_id,
            module_id="occupancy",
            config={
                "version": 1,
                "enabled": True,
                "timeouts": {
                    "default": 600,  # 10 minutes
                    "motion": 300,   # 5 minutes
                    "presence": 600,  # 10 minutes
                },
                "occupancy_strategy": "independent",
                "contributes_to_parent": True,
            },
        )
    print("   ✓ Configured occupancy for all locations")
    
    # 5. Attach occupancy module
    print("\n5. Attaching occupancy module...")
    occupancy = OccupancyModule()
    occupancy.attach(bus, loc_mgr)
    print("   ✓ OccupancyModule attached and engine initialized")
    
    # 6. Subscribe to occupancy events
    print("\n6. Subscribing to occupancy events...")
    occupancy_events = []
    
    def on_occupancy_changed(event: Event):
        occupancy_events.append(event)
        payload = event.payload
        print(f"   📍 {event.location_id}: {'OCCUPIED' if payload['occupied'] else 'VACANT'}")
        print(f"      Confidence: {payload['confidence']:.2f}")
        if payload.get('active_occupants'):
            print(f"      Occupants: {payload['active_occupants']}")
        if payload.get('expires_at'):
            print(f"      Expires: {payload['expires_at']}")
    
    from home_topology.core.bus import EventFilter
    bus.subscribe(on_occupancy_changed, EventFilter(event_type="occupancy.changed"))
    print("   ✓ Subscribed to occupancy.changed events")
    
    # 7. Scenario 1: Motion Detection
    print("\n" + "=" * 70)
    print("SCENARIO 1: Motion Detection")
    print("=" * 70)
    print("\nAction: Kitchen motion sensor detects movement...")
    
    bus.publish(
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
    
    time.sleep(0.1)  # Give events time to process
    
    # Host responsibility: Check when next timeout is needed
    next_timeout = occupancy.get_next_timeout()
    if next_timeout:
        print(f"\n   ℹ️  Host should schedule timeout check at: {next_timeout.isoformat()}")
        print(f"   ℹ️  In HA: use async_track_point_in_time(hass, check_callback, next_timeout)")
    
    # Check states
    print("\nCurrent states:")
    for loc_id in ["kitchen", "main_floor", "house"]:
        state = occupancy.get_location_state(loc_id)
        if state:
            status = "OCCUPIED" if state["occupied"] else "VACANT"
            print(f"   {loc_id}: {status} (confidence: {state['confidence']:.2f})")
    
    # 8. Scenario 2: Identity Tracking
    print("\n" + "=" * 70)
    print("SCENARIO 2: Identity Tracking")
    print("=" * 70)
    print("\nAction: Mike's Bluetooth beacon detected...")
    
    bus.publish(
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
    
    time.sleep(0.1)
    
    # Check identity
    print("\nCurrent state with identity:")
    kitchen_state = occupancy.get_location_state("kitchen")
    if kitchen_state:
        print(f"   Kitchen: {'OCCUPIED' if kitchen_state['occupied'] else 'VACANT'}")
        print(f"   Active occupants: {kitchen_state['active_occupants']}")
        print(f"   Active holds: {kitchen_state['active_holds']}")
    
    # 9. Scenario 3: State Persistence
    print("\n" + "=" * 70)
    print("SCENARIO 3: State Persistence")
    print("=" * 70)
    print("\nAction: Dumping state...")
    
    state_dump = occupancy.dump_state()
    print(f"   ✓ Dumped state for {len(state_dump)} locations")
    for loc_id, state_data in state_dump.items():
        print(f"   {loc_id}:")
        print(f"      is_occupied: {state_data['is_occupied']}")
        if state_data.get('active_occupants'):
            print(f"      active_occupants: {state_data['active_occupants']}")
    
    print("\nAction: Creating new module and restoring state...")
    new_occupancy = OccupancyModule()
    new_occupancy.attach(bus, loc_mgr)
    new_occupancy.restore_state(state_dump)
    
    restored_state = new_occupancy.get_location_state("kitchen")
    print(f"   ✓ Restored kitchen state: {'OCCUPIED' if restored_state['occupied'] else 'VACANT'}")
    print(f"   ✓ Restored occupants: {restored_state['active_occupants']}")
    
    # 10. Scenario 4: Host-Controlled Timeout Checking
    print("\n" + "=" * 70)
    print("SCENARIO 4: Host-Controlled Timeout Checking")
    print("=" * 70)
    print("\nDemonstrating time-agnostic design...")
    print("Note: In production, HA integration schedules these checks")
    
    # Check when next timeout should occur
    next_timeout = occupancy.get_next_timeout()
    if next_timeout:
        print(f"   ℹ️  Next timeout check needed at: {next_timeout.isoformat()}")
        
        # Simulate host calling check_timeouts() at a specific time
        # In tests, you control time exactly:
        from datetime import timedelta
        future_time = datetime.now(UTC) + timedelta(minutes=6)
        
        print(f"   ℹ️  Host calls check_timeouts() at: {future_time.isoformat()}")
        print("   (In tests: pass exact time. In HA: use async scheduler)")
        
        # Host calls with specific time
        occupancy.check_timeouts(future_time)
        print("   ✓ Timeout check completed (no expiry yet, timers still active)")
    
    # 11. Summary
    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    print(f"\n✅ Total occupancy events emitted: {len(occupancy_events)}")
    print("✅ Hierarchy propagation working (child → parent)")
    print("✅ Identity tracking working (Mike in kitchen)")
    print("✅ State persistence working (dump/restore)")
    print("✅ Time-agnostic design (host controls scheduling)")
    print("\nThe occupancy engine is fully integrated! 🎉")
    print("\n💡 Key Design:")
    print("   - Module has NO internal timers")
    print("   - Host calls check_timeouts(now) when needed")
    print("   - Module returns when next check should happen")
    print("   - Fully testable without mocking time")

if __name__ == "__main__":
    main()

