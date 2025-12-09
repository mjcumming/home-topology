# Presence Module - Design Spec

**Status**: ✅ Implemented  
**Date**: 2025.12.09  
**Version**: 1.0

---

## Overview

The Presence Module tracks **who is where** in your home, extending occupancy tracking from "is the room occupied?" to "who is in the room?".

### Key Concepts

1. **People are NOT locations** - They are tracked entities that have a relationship to locations
2. **People are IN locations** - Each Person has a `current_location_id` field
3. **Device trackers determine location** - Person's location updates based on their device tracker states
4. **PresenceModule manages people** - Separate registry from LocationManager's spatial structure

### Mental Model

```
Locations (spatial structure):
  house
    ├─ main_floor
    │   ├─ kitchen
    │   └─ living_room
    └─ upper_floor
        └─ bedroom

People (tracked entities):
  Mike (currently_in: kitchen)
    ├─ device_tracker.phone
    └─ device_tracker.watch
  
  Sarah (currently_in: bedroom)
    └─ device_tracker.phone_sarah

Query: "Who's in kitchen?"
  → Look up all Person objects where current_location_id = "kitchen"
  → Answer: [Mike]

Query: "Where is Mike?"
  → Look up Person("mike").current_location_id
  → Answer: "kitchen"
```

This keeps spatial structure (LocationManager) separate from entity tracking (PresenceModule).

---

## Design Principles

### 1. Person Data Model

A person is a **tracked entity** with a current location:

```python
@dataclass
class Person:
    """Represents a person being tracked through the home."""
    
    id: str                                    # Unique identifier (e.g., "mike")
    name: str                                  # Display name
    current_location_id: Optional[str]         # Where they are now
    device_trackers: List[str]                 # Trackers that determine location
    user_id: Optional[str] = None              # HA user account (optional)
    picture: Optional[str] = None              # Avatar image path
    
    # Tracker management
    primary_tracker: Optional[str] = None      # Most reliable tracker
    tracker_priority: Dict[str, int] = field(default_factory=dict)
```

**Why separate from Location?**
- ✅ Conceptually clear: People ARE IN locations
- ✅ Simpler queries: Direct lookup instead of filtering
- ✅ Different data: People have trackers, pictures, user accounts
- ✅ No confusion: Locations are spatial, people are entities

### 2. PresenceModule Responsibilities

The PresenceModule manages the Person registry and tracks their locations:

```python
class PresenceModule(LocationModule):
    def __init__(self):
        self._people: Dict[str, Person] = {}  # Person registry
        self._location_manager: Optional[LocationManager] = None
        self._bus: Optional[EventBus] = None
    
    def create_person(
        self,
        id: str,
        name: str,
        device_trackers: List[str],
        **kwargs
    ) -> Person:
        """Create a new person to track."""
        person = Person(
            id=id,
            name=name,
            device_trackers=device_trackers,
            **kwargs
        )
        self._people[id] = person
        return person
    
    def get_people_in_location(self, location_id: str) -> List[Person]:
        """Get all people currently in a specific location."""
        return [
            person for person in self._people.values()
            if person.current_location_id == location_id
        ]
    
    def get_person_location(self, person_id: str) -> Optional[str]:
        """Get current location ID of a person."""
        person = self._people.get(person_id)
        return person.current_location_id if person else None
```

**Key differences from Location model**:
- People stored in module's `_people` dict, not in `LocationManager`
- Each Person has `current_location_id` (relationship to Location)
- Clear separation: LocationManager handles spatial structure, PresenceModule handles people

### 3. Device Tracker Management

Inspired by Person integration's dynamic tracker management:

```python
# Add device tracker to person (temporary association)
presence_module.add_device_tracker(
    person_id="mike",
    device_tracker="device_tracker.car_1",
    temporary=True
)

# Remove when person exits car
presence_module.remove_device_tracker(
    person_id="mike",
    device_tracker="device_tracker.car_1"
)
```

**Use Cases**:
- Person takes the car → attach car tracker
- Person returns home → detach car tracker
- Guest arrives → create temporary person
- Pet tracking with collar tracker

---

## PresenceModule Implementation

### Module Responsibilities

1. **Person Registry**: Maintain list of people being tracked
2. **Location Tracking**: Update person's current location based on device trackers
3. **Event Emission**: Publish `presence.changed` events when people move
4. **Query Interface**: Answer "who is where?" questions
5. **Persistence**: Save/restore person registry and current locations

### Complete API

```python
class PresenceModule(LocationModule):
    @property
    def id(self) -> str:
        return "presence"
    
    # Person Management
    
    def create_person(
        self,
        id: str,
        name: str,
        device_trackers: List[str],
        user_id: Optional[str] = None,
        picture: Optional[str] = None
    ) -> Person:
        """Create a new person to track."""
        person = Person(
            id=id,
            name=name,
            device_trackers=device_trackers,
            user_id=user_id,
            picture=picture
        )
        self._people[id] = person
        return person
    
    def delete_person(self, person_id: str) -> None:
        """Remove a person from tracking."""
        if person_id in self._people:
            del self._people[person_id]
    
    def get_person(self, person_id: str) -> Optional[Person]:
        """Get a person by ID."""
        return self._people.get(person_id)
    
    def all_people(self) -> List[Person]:
        """Get all tracked people."""
        return list(self._people.values())
    
    # Device Tracker Management
    
    def add_device_tracker(
        self,
        person_id: str,
        device_tracker: str,
        temporary: bool = False,
        priority: Optional[int] = None
    ) -> None:
        """Add a device tracker to a person."""
        person = self._people.get(person_id)
        if not person:
            raise ValueError(f"Person '{person_id}' not found")
        
        if device_tracker not in person.device_trackers:
            person.device_trackers.append(device_tracker)
        
        if priority is not None:
            person.tracker_priority[device_tracker] = priority
        
        # Mark as primary if it's the only tracker
        if len(person.device_trackers) == 1:
            person.primary_tracker = device_tracker
    
    def remove_device_tracker(
        self,
        person_id: str,
        device_tracker: str
    ) -> None:
        """Remove a device tracker from a person."""
        person = self._people.get(person_id)
        if not person:
            raise ValueError(f"Person '{person_id}' not found")
        
        if device_tracker in person.device_trackers:
            person.device_trackers.remove(device_tracker)
        
        if device_tracker in person.tracker_priority:
            del person.tracker_priority[device_tracker]
        
        # Clear primary if removed
        if person.primary_tracker == device_tracker:
            person.primary_tracker = (
                person.device_trackers[0] if person.device_trackers else None
            )
    
    # Location Queries
    
    def get_people_in_location(self, location_id: str) -> List[Person]:
        """Get all people currently in this location."""
        return [
            person for person in self._people.values()
            if person.current_location_id == location_id
        ]
    
    def get_person_location(self, person_id: str) -> Optional[str]:
        """Get current location ID of a person."""
        person = self._people.get(person_id)
        return person.current_location_id if person else None
    
    def move_person(
        self,
        person_id: str,
        to_location_id: str,
        source_tracker: Optional[str] = None
    ) -> None:
        """Move person to a new location."""
        person = self._people.get(person_id)
        if not person:
            raise ValueError(f"Person '{person_id}' not found")
        
        # Validate location exists
        if not self._location_manager.get_location(to_location_id):
            raise ValueError(f"Location '{to_location_id}' not found")
        
        old_location = person.current_location_id
        person.current_location_id = to_location_id
        
        # Emit presence event
        self._bus.publish(Event(
            type="presence.changed",
            source=self.id,
            location_id=to_location_id,
            payload={
                "person_id": person_id,
                "person_name": person.name,
                "from_location": old_location,
                "to_location": to_location_id,
                "source_tracker": source_tracker,
                "timestamp": datetime.now(UTC),
            }
        ))

### Event Handling

```python
def attach(self, bus: EventBus, loc_manager: LocationManager):
    """Attach to kernel."""
    self._bus = bus
    self._location_manager = loc_manager
    
    # Subscribe to device tracker events
    bus.subscribe(
        handler=self._on_device_tracker_changed,
        event_filter=EventFilter(event_type="sensor.state_changed")
    )

def _on_device_tracker_changed(self, event: Event):
    """Handle device tracker state change."""
    
    # Find which person owns this tracker
    person = self._find_person_for_tracker(event.entity_id)
    if not person:
        return  # Not a person tracker
    
    # Determine new location from tracker state
    new_location = self._resolve_location_from_tracker_state(
        event.payload["new_state"]
    )
    
    # Move person if location changed
    if person.current_location_id != new_location:
        self.move_person(person.id, new_location, source_tracker=event.entity_id)

def _find_person_for_tracker(self, tracker_id: str) -> Optional[Person]:
    """Find which person owns a device tracker."""
    for person in self._people.values():
        if tracker_id in person.device_trackers:
            return person
    return None
```

---

## Integration with Occupancy

### Occupancy + Presence

Occupancy knows **that** someone is there.  
Presence knows **who** is there.

**Combined Example**:

```python
# Kitchen is occupied
occupancy_state = occupancy_module.get_location_state("kitchen")
# { "occupied": True, "confidence": 0.95 }

# Who's in the kitchen?
people = presence_module.get_people_in_location("kitchen")
# ["person_mike", "person_sarah"]
```

### Presence-Enhanced Occupancy Events

```python
# occupancy.changed event includes presence info
{
    "type": "occupancy.changed",
    "location_id": "kitchen",
    "payload": {
        "occupied": True,
        "confidence": 0.95,
        "people_present": ["person_mike", "person_sarah"],  # From PresenceModule
        "person_count": 2,
    }
}
```

---

## HA Integration Patterns

### Service: Add Device Tracker to Person

Mimics Person integration's `person.add_device_tracker`:

```yaml
service: home_topology.add_device_tracker_to_person
data:
  person_id: person_mike
  device_tracker: device_tracker.car_1
  temporary: true  # Remove when person leaves car
```

**Implementation**:

```python
async def handle_add_device_tracker_to_person(call):
    """Add device tracker to person location."""
    person_id = call.data["person_id"]
    tracker = call.data["device_tracker"]
    temporary = call.data.get("temporary", False)
    
    # Add to person's entities
    loc_mgr.add_entity_to_location(tracker, person_id)
    
    # Mark as temporary if specified
    if temporary:
        config = loc_mgr.get_module_config(person_id, "presence") or {}
        config.setdefault("temporary_trackers", []).append(tracker)
        loc_mgr.set_module_config(person_id, "presence", config)
```

### Service: Remove Device Tracker from Person

```yaml
service: home_topology.remove_device_tracker_from_person
data:
  person_id: person_mike
  device_tracker: device_tracker.car_1
```

---

## Automation Examples

### Example 1: Attach Car Tracker

```yaml
automation:
  - alias: "Attach car tracker when Mike uses car"
    trigger:
      - platform: state
        entity_id: binary_sensor.car_door_driver
        to: "on"
    condition:
      - condition: state
        entity_id: person.mike
        state: "home"
    action:
      - service: home_topology.add_device_tracker_to_person
        data:
          person_id: person_mike
          device_tracker: device_tracker.car_1
          temporary: true
```

### Example 2: Detach Car Tracker

```yaml
automation:
  - alias: "Detach car tracker when Mike arrives home"
    trigger:
      - platform: state
        entity_id: person.mike
        to: "home"
    action:
      - service: home_topology.remove_device_tracker_from_person
        data:
          person_id: person_mike
          device_tracker: device_tracker.car_1
```

### Example 3: Room-Specific Actions

```yaml
automation:
  - alias: "Turn on office lights when Mike enters"
    trigger:
      - platform: event
        event_type: home_topology.presence_changed
        event_data:
          to_location: office
          person_id: person_mike
    action:
      - service: light.turn_on
        target:
          entity_id: light.office
```

### Example 4: Multi-Person Scenarios

```yaml
automation:
  - alias: "Movie mode when both in living room"
    trigger:
      - platform: event
        event_type: home_topology.presence_changed
    condition:
      - condition: template
        value_template: >
          {{ 'person_mike' in 
             state_attr('sensor.living_room_presence', 'people') 
             and 'person_sarah' in 
             state_attr('sensor.living_room_presence', 'people') }}
    action:
      - service: scene.turn_on
        target:
          entity_id: scene.movie_mode
```

---

## Query Patterns

### Who is in location X?

```python
people = presence_module.get_people_in_location("kitchen")
# Returns: [Person(id="mike", name="Mike", ...), Person(id="sarah", name="Sarah", ...)]

# Just the names
names = [p.name for p in people]
# Returns: ["Mike", "Sarah"]

# Just the IDs
ids = [p.id for p in people]
# Returns: ["mike", "sarah"]
```

### Where is person X?

```python
location_id = presence_module.get_person_location("mike")
# Returns: "kitchen"

# Get full location object
location = loc_mgr.get_location(location_id)
# Returns: Location(id="kitchen", name="Kitchen", ...)
```

### How many people in location X?

```python
people = presence_module.get_people_in_location("kitchen")
count = len(people)
# Returns: 2
```

### Is person X in location Y (or its descendants)?

```python
mike_location = presence_module.get_person_location("mike")

# Check if in specific location
is_in_kitchen = mike_location == "kitchen"

# Check if in location or its descendants
main_floor_locations = {
    loc.id for loc in loc_mgr.descendants_of("main_floor")
}
main_floor_locations.add("main_floor")

is_on_main_floor = mike_location in main_floor_locations
```

### Get all people in a location and its descendants

```python
def get_people_in_area(location_id: str) -> List[Person]:
    """Get all people in a location and all its child locations."""
    # Get location and all descendants
    locations = {location_id}
    locations.update(
        loc.id for loc in loc_mgr.descendants_of(location_id)
    )
    
    # Find people in any of these locations
    people = []
    for person in presence_module.all_people():
        if person.current_location_id in locations:
            people.append(person)
    
    return people

# Example: Get everyone on main floor
people_on_main_floor = get_people_in_area("main_floor")
```

---

## State Schema

### Presence State per Location

```python
{
    "location_id": "kitchen",
    "people_present": [
        {
            "person_id": "person_mike",
            "person_name": "Mike",
            "entered_at": "2025-12-09T10:30:00Z",
            "primary_tracker": "device_tracker.phone",
            "all_trackers": ["device_tracker.phone", "device_tracker.watch"]
        },
        {
            "person_id": "person_sarah",
            "person_name": "Sarah",
            "entered_at": "2025-12-09T10:35:00Z",
            "primary_tracker": "device_tracker.phone_sarah",
            "all_trackers": ["device_tracker.phone_sarah"]
        }
    ],
    "person_count": 2,
    "last_updated": "2025-12-09T10:35:00Z"
}
```

### Presence State per Person

```python
{
    "person_id": "person_mike",
    "person_name": "Mike",
    "current_location": "kitchen",
    "previous_location": "bedroom",
    "location_changed_at": "2025-12-09T10:30:00Z",
    "device_trackers": {
        "primary": "device_tracker.phone",
        "all": ["device_tracker.phone", "device_tracker.watch"],
        "active": "device_tracker.phone",  # Which tracker determined current location
    },
    "history": [
        {"location": "bedroom", "from": "2025-12-09T07:00:00Z", "to": "2025-12-09T10:30:00Z"},
        {"location": "kitchen", "from": "2025-12-09T10:30:00Z", "to": null},  # Current
    ]
}
```

---

## Future Enhancements

### 1. Presence Zones

Group locations into presence zones:

```python
# Define zones
"work_zone": ["office", "desk_area", "conference_room"]
"relax_zone": ["living_room", "bedroom", "patio"]

# Query: Is Mike in work zone?
is_working = mike_location in work_zones["work_zone"]
```

### 2. Presence History

Track where people have been:

```python
history = presence_module.get_presence_history(
    person_id="person_mike",
    start=datetime.now() - timedelta(days=1)
)
# Returns timeline of locations
```

### 3. Presence-Based Automations

```yaml
# Trigger when Mike has been in office for > 2 hours
trigger:
  - platform: state
    entity_id: sensor.person_mike_location
    to: "office"
    for:
      hours: 2
```

### 4. Guest Management

Temporary person locations:

```python
# Create guest
guest = loc_mgr.create_location(
    id="person_guest_john",
    name="Guest: John",
    parent_id="guest_bedroom"
)

# Auto-delete after departure
# (scheduled automation or manual cleanup)
```

---

## Implementation Status

### ✅ Phase 1: Complete (v0.2.0 - 2025.12.09)

**Implemented**:
- ✅ Person data model (`Person` dataclass)
- ✅ Person registry (create, delete, get, all)
- ✅ Device tracker management (add, remove)
- ✅ Tracker priority support
- ✅ Location queries (who's where, where is who)
- ✅ Person movement tracking
- ✅ `presence.changed` events
- ✅ State persistence (dump/restore)
- ✅ 33 comprehensive tests (all passing)

**Files**:
- `src/home_topology/modules/presence/models.py` - Person, PresenceChange
- `src/home_topology/modules/presence/module.py` - PresenceModule implementation
- `tests/modules/test_presence_module.py` - 33 tests

### 📅 Phase 2: HA Integration (v0.3.0 - Planned)

**To Implement**:
- [ ] Map HA Person entities → PresenceModule
- [ ] Sync HA Person device trackers
- [ ] HA services: `add_device_tracker_to_person`, `remove_device_tracker_from_person`
- [ ] Zone → Location mapping
- [ ] UI for person management

### 🔮 Phase 3: Advanced Features (v1.x - Future)

**To Design**:
- [ ] Presence zones (work zone, relax zone, etc.)
- [ ] History tracking (where has person been)
- [ ] Guest management (temporary people)
- [ ] Pet tracking
- [ ] Multi-home support

---

## Design Decisions

### Why Separate Person Model?

**Decision**: People are stored in PresenceModule's registry, NOT as Location objects.

**Rationale**:
- ✅ **Conceptually clear**: People ARE IN locations, not locations themselves
- ✅ **Natural queries**: `person.current_location_id` is obvious
- ✅ **Different data**: People have trackers, pictures, user accounts - different from spatial locations
- ✅ **Clear separation**: LocationManager handles spatial structure, PresenceModule handles people
- ✅ **Type safety**: Person and Location are distinct types with different purposes

**Alternative Considered: People as Locations**

We initially considered making people Location objects with `parent_id` = current location:

```python
# REJECTED approach
person_mike = Location(
    id="person_mike",
    name="Mike",
    parent_id="kitchen",  # Currently in kitchen
    is_mobile=True
)
```

**Why rejected**:
- ❌ Confusing: "People are locations" doesn't match mental model
- ❌ Mixed concerns: Locations are spatial, people are entities
- ❌ Query complexity: Need to filter all locations to find people
- ❌ Wrong abstraction: `parent_id` implies containment, not "is currently in"
- ❌ Data mismatch: People have device trackers, pictures - doesn't fit Location model

### Why Dynamic Device Trackers?

**Decision**: Support add/remove device trackers at runtime.

**Rationale**:
- ✅ Flexibility for temporary situations (car tracker when person uses car)
- ✅ Guest management (add/remove guest trackers)
- ✅ Automation-driven associations

**Trade-offs**:
- ⚠️ User must manage associations (but integration can automate this)
- ✅ More flexible than fixed tracker list

### Event Coordination with OccupancyModule

**Decision**: NO coordination - modules emit events independently and immediately.

**Rationale**:
- **90% of automations don't care WHO is there** - just turn lights on/off
- **Real-world timing**: Sensors (instant) vs trackers (2-5 seconds delay)
- **User control**: User can choose to wait (DelayAction) or accept sequential overrides
- **Simpler**: No coupling between modules

**Pattern - Sequential Override** (Recommended):
```
T+0.0s: Motion sensor → occupancy.changed → Lights ON (generic)
T+3.0s: Camera detects Mike → presence.changed → Mike's scene (overrides)

Result: Instant response, personalized later ✅
```

**Pattern - Optional Wait** (User's choice):
```yaml
# User chooses to wait for person detection
rule:
  trigger: occupancy.changed
  action:
    - delay: 5  # Wait 5 seconds
    - if presence detected: person-specific scene
    - else: generic lights
```

**Pattern - Ignore Presence** (Most common):
```yaml
# Don't even use presence
rule:
  trigger: occupancy.changed
  action: lights.turn_on  # Done.
```

---

## Summary

Presence Module extends occupancy tracking to answer **"who is where?"**

**Key Features**:
- People as mobile locations
- Dynamic device tracker management
- Integration with occupancy
- HA services for automation
- Presence history tracking

**Benefits**:
- Person-aware automations
- Multi-person scenarios
- Flexible tracker management
- Works with existing architecture

---

**Document Status**: Future Design  
**Last Updated**: 2025.12.09  
**Implementation**: Planned for v0.4.0+

