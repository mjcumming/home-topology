#!/usr/bin/env python3
"""
Example: PresenceModule - Track WHO is WHERE

This example demonstrates:
1. Creating people with device trackers
2. Moving people between locations
3. Querying who is in a location
4. Listening to presence.changed events
5. Combining with occupancy for smart automations
"""

from datetime import datetime, UTC

from home_topology import LocationManager, EventBus, Event
from home_topology.modules.occupancy import OccupancyModule
from home_topology.modules.presence import PresenceModule
from home_topology.core.bus import EventFilter


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main():
    print_section("home-topology: PresenceModule Example")
    
    # 1. Create kernel
    print("\n1. Setting up kernel...")
    loc_mgr = LocationManager()
    bus = EventBus()
    bus.set_location_manager(loc_mgr)
    
    # 2. Build topology
    print("2. Building topology...")
    house = loc_mgr.create_location(id="house", name="House", is_explicit_root=True)
    kitchen = loc_mgr.create_location(
        id="kitchen",
        name="Kitchen",
        parent_id="house",
        aliases=["Cooking Area", "Breakfast Nook"]
    )
    office = loc_mgr.create_location(
        id="office",
        name="Office",
        parent_id="house",
        aliases=["Work Room", "Study"]
    )
    bedroom = loc_mgr.create_location(
        id="bedroom",
        name="Bedroom",
        parent_id="house"
    )
    
    print(f"  ✓ Created {len(loc_mgr.all_locations())} locations")
    
    # 3. Initialize modules
    print("3. Initializing modules...")
    occupancy = OccupancyModule()
    occupancy.attach(bus, loc_mgr)
    
    presence = PresenceModule()
    presence.attach(bus, loc_mgr)
    
    print("  ✓ OccupancyModule attached")
    print("  ✓ PresenceModule attached")
    
    # 4. Create people
    print_section("Creating People")
    
    mike = presence.create_person(
        id="mike",
        name="Mike",
        device_trackers=["device_tracker.mike_phone", "device_tracker.mike_watch"],
        user_id="ha_user_mike"
    )
    print(f"  ✓ Created person: {mike.name}")
    print(f"    - Trackers: {', '.join(mike.device_trackers)}")
    
    sarah = presence.create_person(
        id="sarah",
        name="Sarah",
        device_trackers=["device_tracker.sarah_phone"]
    )
    print(f"  ✓ Created person: {sarah.name}")
    print(f"    - Trackers: {', '.join(sarah.device_trackers)}")
    
    # 5. Subscribe to presence events
    print_section("Setting Up Event Listeners")
    
    def on_presence_changed(event: Event):
        """Handle presence changes."""
        payload = event.payload
        person = payload["person_name"]
        from_loc = payload["from_location"] or "away"
        to_loc = payload["to_location"] or "away"
        
        print(f"  🚶 {person}: {from_loc} → {to_loc}")
        
        if to_loc != "away":
            people = presence.get_people_in_location(to_loc)
            names = [p.name for p in people]
            print(f"     Now in {to_loc}: {', '.join(names)}")
    
    bus.subscribe(
        handler=on_presence_changed,
        event_filter=EventFilter(event_type="presence.changed")
    )
    print("  ✓ Subscribed to presence.changed events")
    
    # 6. Move people around
    print_section("Moving People Through House")
    
    print("\nMike's morning routine:")
    presence.move_person("mike", "bedroom")
    presence.move_person("mike", "kitchen")
    presence.move_person("mike", "office")
    
    print("\nSarah's morning routine:")
    presence.move_person("sarah", "bedroom")
    presence.move_person("sarah", "kitchen")  # Both in kitchen now!
    
    # 7. Query who is where
    print_section("Location Queries")
    
    print("\nWho is in the kitchen?")
    people_in_kitchen = presence.get_people_in_location("kitchen")
    for person in people_in_kitchen:
        print(f"  - {person.name} (tracker: {person.primary_tracker})")
    
    print("\nWhere is Mike?")
    mike_location = presence.get_person_location("mike")
    if mike_location:
        location = loc_mgr.get_location(mike_location)
        print(f"  Mike is in: {location.name}")
    
    print("\nWhere is Sarah?")
    sarah_location = presence.get_person_location("sarah")
    if sarah_location:
        location = loc_mgr.get_location(sarah_location)
        print(f"  Sarah is in: {location.name}")
    
    # 8. Dynamic tracker management
    print_section("Dynamic Device Tracker Management")
    
    print("\nMike takes the car...")
    presence.add_device_tracker("mike", "device_tracker.car_1", priority=3)
    mike_updated = presence.get_person("mike")
    print(f"  ✓ Mike now has {len(mike_updated.device_trackers)} trackers:")
    for tracker in mike_updated.device_trackers:
        priority = mike_updated.tracker_priority.get(tracker, "default")
        print(f"    - {tracker} (priority: {priority})")
    
    print("\nMike arrives home, remove car tracker...")
    presence.remove_device_tracker("mike", "device_tracker.car_1")
    mike_final = presence.get_person("mike")
    print(f"  ✓ Mike now has {len(mike_final.device_trackers)} trackers")
    
    # 9. State persistence
    print_section("State Persistence")
    
    print("\nDumping state...")
    state = presence.dump_state()
    print(f"  ✓ State version: {state['version']}")
    print(f"  ✓ People tracked: {len(state['people'])}")
    for person_id, person_data in state["people"].items():
        loc = person_data["current_location_id"] or "away"
        print(f"    - {person_data['name']}: {loc}")
    
    # 10. Summary
    print_section("Summary")
    
    all_people = presence.all_people()
    print(f"\n  Total people tracked: {len(all_people)}")
    
    for location in loc_mgr.all_locations():
        if location.id == "house":
            continue  # Skip root
        people = presence.get_people_in_location(location.id)
        if people:
            names = [p.name for p in people]
            print(f"  📍 {location.name}: {', '.join(names)}")
        else:
            print(f"  📍 {location.name}: (empty)")
    
    print("\n" + "=" * 70)
    print("  PresenceModule example complete!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()

