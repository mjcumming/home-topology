# Occupancy Module - Integration Guide

**Status**: v2.0  
**Date**: 2025-01-27  
**Approach**: Integration-Layer Event Classification

---

## Overview

This guide explains how to integrate the OccupancyModule with a home automation platform.

**Key Concept**: The integration layer is responsible for event classification. The core library only processes events.

---

## Architecture

```
Platform (e.g., Home Assistant)
    │
    ▼
Integration Layer ◄── You implement this
    │
    │  Responsibilities:
    │  - Map entities to locations
    │  - Classify events (motion → TRIGGER, etc.)
    │  - Set appropriate timeouts
    │  - Send OccupancyEvents
    │
    ▼
OccupancyModule (Core Library)
    │
    │  Responsibilities:
    │  - Process events
    │  - Manage state & timers
    │  - Handle hierarchy
    │  - Emit occupancy.changed
    │
    ▼
Actions/Automations
```

---

## Event Types

Your integration sends these events to the core:

| Event | When to Send |
|-------|--------------|
| `TRIGGER` | Activity detected (motion, door open, light on, etc.) |
| `HOLD` | Continuous presence starts (presence sensor, media playing) |
| `RELEASE` | Continuous presence ends (presence sensor clears) |
| `VACATE` | Force vacant (light off, manual clear, exit door) |
| `LOCK` | Freeze state, add source to `locked_by` set |
| `UNLOCK` | Remove source from `locked_by`, unfreezes when empty |
| `UNLOCK_ALL` | Clear all locks (force unlock regardless of sources) |

---

## Event Classification Examples

### Motion Sensors

```python
# entity: binary_sensor.kitchen_motion
# state: off → on

event = OccupancyEvent(
    location_id="kitchen",
    event_type=EventType.TRIGGER,
    source_id="binary_sensor.kitchen_motion",
    timestamp=now,
    timeout=300,  # 5 minutes
)
```

**Note**: Motion OFF is typically ignored (timer handles timeout).

### Presence Sensors (mmWave, Radar, BLE)

```python
# entity: binary_sensor.office_presence
# state: off → on

event = OccupancyEvent(
    location_id="office",
    event_type=EventType.HOLD,
    source_id="binary_sensor.office_presence",
    timestamp=now,
)

# state: on → off

event = OccupancyEvent(
    location_id="office",
    event_type=EventType.RELEASE,
    source_id="binary_sensor.office_presence",
    timestamp=now,
    timeout=120,  # 2 min trailing
)
```

### Door Sensors

**Entry door (momentary)**:
```python
# Front door opened
event = OccupancyEvent(
    location_id="entryway",
    event_type=EventType.TRIGGER,
    source_id="binary_sensor.front_door",
    timestamp=now,
    timeout=120,  # 2 minutes
)
```

**Exit door (force vacant)** - optional configuration:
```python
# Garage door closed (everyone left)
event = OccupancyEvent(
    location_id="house",
    event_type=EventType.VACATE,
    source_id="binary_sensor.garage_door",
    timestamp=now,
)
```

### Media Players

```python
# media_player.living_room_tv → playing
event = OccupancyEvent(
    location_id="living_room",
    event_type=EventType.HOLD,
    source_id="media_player.living_room_tv",
    timestamp=now,
)

# media_player.living_room_tv → idle/off
event = OccupancyEvent(
    location_id="living_room",
    event_type=EventType.RELEASE,
    source_id="media_player.living_room_tv",
    timestamp=now,
    timeout=300,  # 5 min after TV off
)
```

### Light Switches (Optional - Force Vacant)

If configured to indicate vacancy:

```python
# light.bedroom_main → off
event = OccupancyEvent(
    location_id="bedroom",
    event_type=EventType.VACATE,
    source_id="light.bedroom_main",
    timestamp=now,
)
```

### Lock/Unlock (State Freeze)

Freezes occupancy state. Multiple sources can lock independently.

**Use Cases**: Sleep mode, vacation mode, manual override, cleaning mode, etc.

```python
# Vacation mode - lock house as vacant
event = OccupancyEvent(
    location_id="house",
    event_type=EventType.LOCK,
    source_id="automation_vacation",
    timestamp=now,
)
# locked_by = {"automation_vacation"}

# Another automation also locks
event = OccupancyEvent(
    location_id="house",
    event_type=EventType.LOCK,
    source_id="automation_away",
    timestamp=now,
)
# locked_by = {"automation_vacation", "automation_away"}

# Away mode ends - still locked by vacation!
event = OccupancyEvent(
    location_id="house",
    event_type=EventType.UNLOCK,
    source_id="automation_away",
    timestamp=now,
)
# locked_by = {"automation_vacation"}

# Force unlock everything (user returns early)
event = OccupancyEvent(
    location_id="house",
    event_type=EventType.UNLOCK_ALL,
    source_id="user_override",
    timestamp=now,
)
# locked_by = {}
```

---

## Integration Implementation

### Basic Structure

```python
class MyPlatformOccupancyIntegration:
    def __init__(self, occupancy_module, location_manager):
        self.module = occupancy_module
        self.loc_manager = location_manager
        
    def on_entity_state_change(self, entity_id, old_state, new_state):
        """Platform calls this when entity state changes."""
        
        # 1. Find which location this entity belongs to
        location_id = self.loc_manager.get_location_for_entity(entity_id)
        if not location_id:
            return  # Entity not mapped to a location
            
        # 2. Classify and create event
        event = self._classify_event(entity_id, old_state, new_state, location_id)
        if not event:
            return  # State change doesn't indicate occupancy
            
        # 3. Send to occupancy module
        self.module.process_event(event)
        
    def _classify_event(self, entity_id, old_state, new_state, location_id):
        """Map entity state change to OccupancyEvent."""
        now = datetime.now(UTC)
        
        # Motion sensor: off → on = TRIGGER
        if "motion" in entity_id and old_state == "off" and new_state == "on":
            return OccupancyEvent(
                location_id=location_id,
                event_type=EventType.TRIGGER,
                source_id=entity_id,
                timestamp=now,
                timeout=300,
            )
            
        # Presence sensor: off → on = HOLD
        if "presence" in entity_id and old_state == "off" and new_state == "on":
            return OccupancyEvent(
                location_id=location_id,
                event_type=EventType.HOLD,
                source_id=entity_id,
                timestamp=now,
            )
            
        # Presence sensor: on → off = RELEASE
        if "presence" in entity_id and old_state == "on" and new_state == "off":
            return OccupancyEvent(
                location_id=location_id,
                event_type=EventType.RELEASE,
                source_id=entity_id,
                timestamp=now,
                timeout=120,
            )
            
        return None  # Unhandled
```

### Configuration-Driven Classification

More flexible approach using configuration:

```python
EVENT_CONFIG = {
    "binary_sensor.*_motion": {
        "on": {"event_type": "TRIGGER", "timeout": 300},
    },
    "binary_sensor.*_presence": {
        "on": {"event_type": "HOLD"},
        "off": {"event_type": "RELEASE", "timeout": 120},
    },
    "binary_sensor.*_door": {
        "on": {"event_type": "TRIGGER", "timeout": 120},
    },
    "media_player.*": {
        "playing": {"event_type": "HOLD"},
        "idle": {"event_type": "RELEASE", "timeout": 300},
        "off": {"event_type": "RELEASE", "timeout": 300},
    },
}
```

---

## Location Configuration

Set per-location defaults:

```python
location_config = {
    "occupancy": {
        "enabled": True,
        "default_timeout": 300,           # 5 min for TRIGGER events
        "hold_release_timeout": 120,      # 2 min after RELEASE
        "occupancy_strategy": "independent",
        "contributes_to_parent": True,
    }
}

loc_manager.set_module_config("kitchen", "occupancy", location_config)
```

### Strategy Options

| Strategy | Behavior |
|----------|----------|
| `independent` | Location determines its own state |
| `follow_parent` | Location mirrors parent's state |

---

## Handling Timeouts

The integration should periodically call `check_timeouts()`:

```python
# Get when next timeout expires
next_timeout = module.get_next_timeout(now)

if next_timeout:
    # Schedule wake at next_timeout
    schedule_callback(next_timeout, lambda: module.check_timeouts(datetime.now(UTC)))
```

Or use periodic checking:

```python
# Check every 30 seconds
while True:
    module.check_timeouts(datetime.now(UTC))
    await asyncio.sleep(30)
```

### Two Timeout Concepts

The module exposes two different timeout concepts:

| Concept | Method | Description |
|---------|--------|-------------|
| **Own Timeout** | `get_location_state()["occupied_until"]` | The location's own timer |
| **Effective Timeout** | `get_effective_timeout(location_id, now)` | When location will TRULY be vacant (considers all descendants) |

**Example:**

```python
now = datetime.now(UTC)

# Location's own timer
state = module.get_location_state("house")
own_timeout = state["occupied_until"]  # e.g., T+300s

# When truly vacant (considers children)
effective = module.get_effective_timeout("house", now)  # e.g., T+400s (kitchen has longer timer)

# Display to user
if effective:
    remaining = (effective - now).total_seconds()
    print(f"House will be truly vacant in {remaining}s")
```

**Use Cases:**
- **Own timeout**: Display location's individual timer
- **Effective timeout**: Schedule actions for when area is truly empty

---

## State Persistence

### Save State

```python
state_snapshot = module.dump_state()
save_to_storage(state_snapshot)
```

### Restore State

```python
state_snapshot = load_from_storage()
module.restore_state(state_snapshot, now=datetime.now(UTC), max_age_minutes=15)
```

**Stale Protection**: States older than `max_age_minutes` are ignored (except locked states).

---

## Event Handling

Listen for `occupancy.changed` events:

```python
def on_occupancy_changed(event):
    location_id = event.location_id
    occupied = event.payload["occupied"]
    
    if occupied:
        # Turn on lights, adjust climate, etc.
        turn_on_lights(location_id)
    else:
        # Turn off lights, reduce climate, etc.
        turn_off_lights(location_id)

event_bus.subscribe("occupancy.changed", on_occupancy_changed)
```

---

## Common Patterns

### "Any Activity" Pattern

For devices that just indicate "something happened":

```python
# Any state change = TRIGGER
event = OccupancyEvent(
    location_id=location_id,
    event_type=EventType.TRIGGER,
    source_id=entity_id,
    timestamp=now,
    timeout=600,  # 10 min default
)
```

### "Definitive Vacant" Pattern

For devices that indicate "definitely empty":

```python
# Exit detected or manual clear
event = OccupancyEvent(
    location_id=location_id,
    event_type=EventType.VACATE,
    source_id=entity_id,
    timestamp=now,
)
```

### "Vacate Area" Pattern (Cascading)

To vacate a location AND all its descendants:

```python
# User clicks "Everyone Left" button for first floor
transitions = module.vacate_area(
    location_id="first_floor",
    source_id="user_button_everyone_left",
)

# Returns list of all state transitions that occurred
for t in transitions:
    print(f"{t.location_id}: {t.previous_state.is_occupied} → {t.new_state.is_occupied}")
```

**Options:**

```python
# Default: Skip locked locations (respects locks)
module.vacate_area("house", "away_mode")

# Force: Also unlock and vacate locked locations
module.vacate_area("house", "emergency_clear", include_locked=True)
```

**Use Cases:**
- "Everyone left" button in UI
- Away mode activation
- Testing/debugging
- Emergency clear

### Identity Tracking

Track who is in which location:

```python
# BLE beacon detected
event = OccupancyEvent(
    location_id="kitchen",
    event_type=EventType.HOLD,
    source_id="ble_beacon_mike",
    timestamp=now,
    occupant_id="mike",  # Track identity
)
```

---

## Testing Your Integration

```python
def test_motion_triggers_occupancy():
    # Arrange
    integration = MyIntegration(module, loc_manager)
    now = datetime(2025, 1, 27, 12, 0, 0)
    
    # Act
    integration.on_entity_state_change(
        "binary_sensor.kitchen_motion",
        old_state="off",
        new_state="on",
    )
    
    # Assert
    state = module.get_state("kitchen")
    assert state.is_occupied == True
    assert state.occupied_until == now + timedelta(seconds=300)
```

---

## Location Hierarchy Management

### Creating Locations from Platform

When the integration discovers areas from the platform (e.g., Home Assistant):

```python
# HA area discovered → create as unassigned (shows in Inbox)
loc_manager.create_location(
    id="ha_area_kitchen",
    name="Kitchen",
    parent_id=None,
    is_explicit_root=False,  # Unassigned, shows in Inbox
    ha_area_id="kitchen",
)

# User creates a root location explicitly
loc_manager.create_location(
    id="house",
    name="House",
    parent_id=None,
    is_explicit_root=True,  # Intentional root
)

# User promotes discovered location to root (e.g., "Garage is standalone")
loc_manager.set_as_root("ha_area_garage")
```

### Querying Locations

```python
# Get intentional roots (top-level hierarchy)
roots = loc_manager.get_root_locations()

# Get unassigned locations (Inbox)
inbox = loc_manager.get_unassigned_locations()

# Get all locations with no parent (both roots and unassigned)
all_top_level = [loc for loc in loc_manager.all_locations() if loc.parent_id is None]
```

### Sync Model

**Inbound (Platform → Kernel)**:

```python
def on_platform_area_created(area_id, area_name, floor_id=None):
    """Handle new area created in platform."""
    # Create as unassigned
    location = loc_manager.create_location(
        id=f"ha_area_{area_id}",
        name=area_name,
        parent_id=floor_id,  # If floor exists, use it as parent
        is_explicit_root=False,
        ha_area_id=area_id,
    )
    
def on_platform_area_moved(area_id, new_floor_id):
    """Handle area moved to different floor in platform."""
    location = loc_manager.get_location(f"ha_area_{area_id}")
    if location:
        # Update parent (integration decides conflict handling)
        location.parent_id = new_floor_id
```

**Outbound (Kernel → Platform)** - Optional:

```python
def on_kernel_location_moved(location_id, new_parent_id):
    """User reorganized hierarchy in our UI."""
    location = loc_manager.get_location(location_id)
    if location and location.ha_area_id:
        # Sync back to platform (if desired)
        platform.move_area(location.ha_area_id, new_parent_id)
```

### Conflict Handling

When platform and kernel hierarchy disagree:

```python
def handle_sync_conflict(location_id, platform_parent, kernel_parent):
    """Handle hierarchy conflict between platform and kernel."""
    
    # Option 1: Kernel wins (recommended)
    # User's organization takes precedence
    pass  # Don't update kernel
    
    # Option 2: Platform wins (not recommended)
    # location.parent_id = platform_parent
    
    # Option 3: User decides
    # show_conflict_dialog(location_id, platform_parent, kernel_parent)
```

---

## Integration Responsibilities Summary

| Responsibility | Implementation |
|----------------|----------------|
| **Discovery** | Create Locations from platform areas (`is_explicit_root=False`) |
| **Sync** | Handle platform ↔ kernel hierarchy updates |
| **Conflict Handling** | Decide resolution strategy |
| **Event Classification** | Map platform events → `OccupancyEvent` |
| **Entity Creation** | Create `binary_sensor.*_occupied` entities |
| **Timeout Scheduling** | Call `check_timeouts()` at scheduled times |
| **State Persistence** | Call `dump_state()` / `restore_state()` |
| **Timeout Display** | Choose `occupied_until` vs `get_effective_timeout()` |
| **Area Commands** | Expose `vacate_area()` as service/button |

---

## References

- **Architecture**: `../architecture.md`
- **Design Document**: `occupancy-design.md`
- **Design Decisions**: `occupancy-design-decisions.md`
- **Implementation Status**: `occupancy-implementation-status.md`
- **ADR Log**: `../adr-log.md` (see ADR-016 through ADR-019)

---

**Status**: v2.2 ✅  
**Last Updated**: 2025-11-25
