# Presence Module - API Reference

**Status**: v1.0  
**Date**: 2025.01.27  
**Module ID**: `presence`

---

## Overview

The PresenceModule tracks WHO is in each location (person tracking with device trackers).

**Key Features**:
- Person registry (separate from Location topology)
- Device tracker management (add/remove trackers dynamically)
- Location tracking (where is each person)
- Presence events (person entered/left location)

---

## Architecture

```
Device Tracker Updates (sensor.state_changed)
    │
    ▼
PresenceModule
    │
    │  Responsibilities:
    │  - Map device trackers to people
    │  - Track person locations
    │  - Emit presence.changed events
    │
    ▼
Integration Layer (You implement this)
    │
    │  Responsibilities:
    │  - Map platform Person entities to PresenceModule
    │  - Translate device tracker updates
    │  - Handle location mapping
    │
    ▼
Platform (Home Assistant, etc.)
```

---

## Initialization

```python
from home_topology.modules.presence import PresenceModule

presence = PresenceModule()
presence.attach(bus, loc_mgr)
```

---

## Person Management

### Create Person

```python
person = presence.create_person(
    id="mike",
    name="Mike",
    device_trackers=[
        "device_tracker.mike_phone",
        "device_tracker.mike_watch",
    ],
    user_id="ha_user_123",  # Optional platform user ID
    picture="/local/mike.jpg",  # Optional avatar
)

# Person object:
# Person {
#     id: str,
#     name: str,
#     device_trackers: List[str],
#     tracker_priority: Dict[str, int],  # Lower = higher priority
#     primary_tracker: Optional[str],
#     current_location_id: Optional[str],
#     user_id: Optional[str],
#     picture: Optional[str],
# }
```

### Delete Person

```python
presence.delete_person("mike")
```

### Get Person

```python
person = presence.get_person("mike")
# Returns: Person object or None
```

### Get All People

```python
all_people = presence.all_people()
# Returns: List[Person]
```

---

## Device Tracker Management

### Add Device Tracker

```python
presence.add_device_tracker(
    person_id="mike",
    device_tracker="device_tracker.mike_tablet",
    priority=10,  # Optional: lower = higher priority
)
```

### Remove Device Tracker

```python
presence.remove_device_tracker("mike", "device_tracker.mike_phone")
```

### Tracker Priority

- Lower priority = higher priority
- Primary tracker is used for location updates
- If multiple trackers report different locations, highest priority wins

---

## Location Queries

### Get People in Location

```python
people = presence.get_people_in_location("kitchen")
# Returns: List[Person] currently in kitchen
```

### Get Person Location

```python
location_id = presence.get_person_location("mike")
# Returns: "kitchen" or None if away/unknown
```

### Move Person

```python
# Manually move person (typically called from integration layer)
presence.move_person(
    person_id="mike",
    to_location_id="kitchen",
    source_tracker="device_tracker.mike_phone",  # Optional: for logging
)

# Move to away/unknown
presence.move_person("mike", to_location_id=None)
```

---

## Device Tracker Integration

The module subscribes to `sensor.state_changed` events. Your integration layer should:

1. **Map device trackers to people** - Call `add_device_tracker()` when platform Person entities are created
2. **Translate tracker updates** - When device tracker state changes, determine location and call `move_person()`

### Example Integration

```python
@callback
def device_tracker_state_changed(event: Event):
    """Handle device tracker state changes."""
    entity_id = event.entity_id
    new_state = event.payload["new_state"]
    
    # Find person with this tracker
    for person in presence.all_people():
        if entity_id in person.device_trackers:
            # Map platform state to location
            location_id = map_tracker_state_to_location(new_state, entity_id)
            
            # Update person location
            presence.move_person(
                person_id=person.id,
                to_location_id=location_id,
                source_tracker=entity_id,
            )
            break
```

### Location Mapping

Your integration is responsible for mapping device tracker states to location IDs:

```python
def map_tracker_state_to_location(state: str, entity_id: str) -> Optional[str]:
    """
    Map device tracker state to location ID.
    
    Args:
        state: Device tracker state (e.g., "home", "kitchen", "away")
        entity_id: Device tracker entity ID
    
    Returns:
        Location ID or None for away/unknown
    """
    # Example: Map "home" states to locations
    if state == "home":
        # Use entity attributes or other logic to determine location
        return "house"
    elif state.startswith("area_"):
        return state  # If state is already location ID
    else:
        return None  # Away/unknown
```

---

## Events Emitted

### presence.changed

Emitted when a person's location changes:

```python
Event(
    type="presence.changed",
    source="presence",
    location_id="kitchen",  # New location
    payload={
        "person_id": "mike",
        "person_name": "Mike",
        "old_location": "living_room",  # Previous location or None
        "new_location": "kitchen",  # New location or None (away)
        "source_tracker": "device_tracker.mike_phone",
    },
)
```

---

## Events Consumed

- `sensor.state_changed` - Device tracker updates (processed by integration layer)

**Note**: The module subscribes to `sensor.state_changed` but doesn't automatically process them. Your integration layer should handle the translation and call `move_person()`.

---

## Configuration

```python
config = {
    "version": 1,
    "enabled": True,
}

loc_mgr.set_module_config("kitchen", "presence", config)
```

**Note**: Presence module doesn't require per-location config currently. Configuration is primarily for enabling/disabling the module.

### Configuration Schema

```python
{
    "type": "object",
    "properties": {
        "version": {"type": "integer", "default": 1},
        "enabled": {"type": "boolean", "default": True},
    },
}
```

---

## State Persistence

```python
# Dump state
state = presence.dump_state()
# {
#     "version": 1,
#     "people": {
#         "mike": {
#             "id": "mike",
#             "name": "Mike",
#             "device_trackers": ["device_tracker.mike_phone"],
#             "current_location_id": "kitchen",
#             ...
#         },
#     },
# }

# Restore state
presence.restore_state(state)
```

---

## Usage Examples

### Complete Setup

```python
# 1. Initialize module
presence = PresenceModule()
presence.attach(bus, loc_mgr)

# 2. Create people from platform
for ha_person in hass.states.get("person"):
    presence.create_person(
        id=ha_person.entity_id,
        name=ha_person.attributes["friendly_name"],
        device_trackers=ha_person.attributes.get("device_trackers", []),
        user_id=ha_person.attributes.get("user_id"),
    )

# 3. Subscribe to device tracker updates
@callback
def on_tracker_update(event: Event):
    # Translate and update (see integration example above)
    pass

bus.subscribe(
    on_tracker_update,
    EventFilter(event_type="sensor.state_changed")
)
```

### Query Presence

```python
# Who is in the kitchen?
people = presence.get_people_in_location("kitchen")
for person in people:
    print(f"{person.name} is in the kitchen")

# Where is Mike?
location = presence.get_person_location("mike")
if location:
    print(f"Mike is in {location}")
else:
    print("Mike is away")
```

### Use in Automation

```python
# Subscribe to presence changes
@callback
def on_presence_changed(event: Event):
    payload = event.payload
    person_id = payload["person_id"]
    new_location = payload["new_location"]
    
    if new_location == "kitchen":
        print(f"{payload['person_name']} entered kitchen")
    elif payload["old_location"] == "kitchen":
        print(f"{payload['person_name']} left kitchen")

bus.subscribe(
    on_presence_changed,
    EventFilter(event_type="presence.changed")
)
```

---

## Best Practices

1. **Sync with platform** - Create people from platform Person entities on startup
2. **Handle tracker priority** - Set priorities to resolve conflicts
3. **Map states carefully** - Device tracker states vary by platform
4. **Handle away state** - Use `None` for away/unknown locations
5. **Persist state** - Save/restore person registry across restarts

---

## Troubleshooting

### Person Not Tracking

- Verify device trackers are added: `person.device_trackers`
- Check integration layer is calling `move_person()` on tracker updates
- Verify tracker states are being mapped to location IDs

### Wrong Location

- Check tracker priority: lower number = higher priority
- Verify primary tracker is correct
- Check location mapping logic in integration layer

### Events Not Firing

- Verify module is attached: `presence.attach(bus, loc_mgr)`
- Check `move_person()` is being called (not just updating Person object)
- Verify location IDs exist in LocationManager

---

**Document Version**: 1.0  
**Last Updated**: 2025.01.27  
**Status**: Living Document

