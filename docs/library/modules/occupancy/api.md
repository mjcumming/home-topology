# Occupancy Module - API Reference

**Status**: v3.0  
**Date**: 2025-11-26  
**Approach**: Integration-Layer Event Classification with Per-Source Tracking

---

## Overview

This guide explains how to integrate the OccupancyModule with a home automation platform.

**Key Concepts**:
- The integration layer is responsible for event classification
- The core library tracks per-source contributions
- Each entity either IS or ISN'T contributing to occupancy

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
    │  - Call trigger() / clear() methods
    │
    ▼
OccupancyModule (Core Library)
    │
    │  Responsibilities:
    │  - Track per-source contributions
    │  - Manage contribution expirations
    │  - Handle hierarchy
    │  - Emit occupancy.changed
    │
    ▼
Actions/Automations
```

---

## Event Types

Your integration sends these events to the core:

### Events (From Entity State Changes)

| Event | When to Send | Method |
|-------|--------------|--------|
| `TRIGGER` | Entity indicates activity/presence | `trigger(location_id, source_id, timeout)` |
| `CLEAR` | Entity indicates activity/presence ended | `clear(location_id, source_id, trailing_timeout)` |

### Commands (From Automations/UI)

| Command | When to Send | Method |
|---------|--------------|--------|
| `VACATE` | Force vacant (light off, manual clear) | `vacate(location_id)` |
| `LOCK` | Freeze state | `lock(location_id, source_id)` |
| `UNLOCK` | Unfreeze state | `unlock(location_id, source_id)` |
| `UNLOCK_ALL` | Force unlock all | `unlock_all(location_id)` |

---

## Event Classification Examples

### Motion Sensors

```python
# entity: binary_sensor.kitchen_motion
# state: off → on

module.trigger(
    location_id="kitchen",
    source_id="binary_sensor.kitchen_motion",
    timeout=300,  # 5 minutes
)
```

**Note**: Motion OFF is typically ignored (timer handles timeout).

### Presence Sensors (mmWave, Radar, BLE)

```python
# entity: binary_sensor.office_presence
# state: off → on

module.trigger(
    location_id="office",
    source_id="binary_sensor.office_presence",
    timeout=None,  # Indefinite until cleared
)

# state: on → off

module.clear(
    location_id="office",
    source_id="binary_sensor.office_presence",
    trailing_timeout=120,  # 2 min trailing
)
```

### Door Sensors

**Entry door (momentary)**:
```python
# Front door opened
module.trigger(
    location_id="entryway",
    source_id="binary_sensor.front_door",
    timeout=120,  # 2 minutes
)
```

**Exit door (force vacant)** - optional configuration:
```python
# Garage door closed (everyone left)
module.vacate(location_id="house")
```

### Media Players

```python
# media_player.living_room_tv → playing
module.trigger(
    location_id="living_room",
    source_id="media_player.living_room_tv",
    timeout=None,  # Indefinite while playing
)

# media_player.living_room_tv → idle/off
module.clear(
    location_id="living_room",
    source_id="media_player.living_room_tv",
    trailing_timeout=300,  # 5 min after TV off
)
```

### Light Switches (Optional - Force Vacant)

If configured to indicate vacancy:

```python
# light.bedroom_main → off
module.vacate(location_id="bedroom")
```

### Lock/Unlock (State Freeze)

Freezes occupancy state. Multiple sources can lock independently.

**Use Cases**: Sleep mode, vacation mode, manual override, cleaning mode, etc.

```python
# Vacation mode - lock house as vacant
module.lock(location_id="house", source_id="automation_vacation")
# locked_by = {"automation_vacation"}

# Another automation also locks
module.lock(location_id="house", source_id="automation_away")
# locked_by = {"automation_vacation", "automation_away"}

# Away mode ends - still locked by vacation!
module.unlock(location_id="house", source_id="automation_away")
# locked_by = {"automation_vacation"}

# Force unlock everything (user returns early)
module.unlock_all(location_id="house")
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
        
        # 2. Get entity configuration
        config = self.get_entity_config(entity_id)
        if not config:
            return  # Entity not configured as occupancy source
            
        # 3. Classify and send event
        self._process_state_change(entity_id, old_state, new_state, location_id, config)
        
    def _process_state_change(self, entity_id, old_state, new_state, location_id, config):
        """Map entity state change to occupancy event."""
        
        # Motion sensor: off → on = TRIGGER with timeout
        if config["type"] == "motion" and new_state == "on":
            self.module.trigger(
                location_id=location_id,
                source_id=entity_id,
                timeout=config.get("timeout", 300),
            )
            
        # Presence sensor: off → on = TRIGGER indefinite
        elif config["type"] == "presence" and new_state == "on":
            self.module.trigger(
                location_id=location_id,
                source_id=entity_id,
                timeout=None,  # Indefinite
            )
            
        # Presence sensor: on → off = CLEAR with trailing
        elif config["type"] == "presence" and new_state == "off":
            self.module.clear(
                location_id=location_id,
                source_id=entity_id,
                trailing_timeout=config.get("trailing_timeout", 120),
            )
```

### Configuration-Driven Classification

More flexible approach using configuration:

```python
# Per-entity configuration stored in location's module config
ENTITY_CONFIG = {
    "binary_sensor.kitchen_motion": {
        "type": "motion",
        "timeout": 300,
    },
    "binary_sensor.office_presence": {
        "type": "presence",
        "trailing_timeout": 120,
    },
    "binary_sensor.front_door": {
        "type": "door",
        "timeout": 120,
    },
    "media_player.living_room_tv": {
        "type": "media",
        "trailing_timeout": 300,
    },
}

# Entity type behaviors
ENTITY_BEHAVIORS = {
    "motion": {
        "on": lambda cfg: ("trigger", {"timeout": cfg.get("timeout", 300)}),
        "off": None,  # Ignored
    },
    "presence": {
        "on": lambda cfg: ("trigger", {"timeout": None}),
        "off": lambda cfg: ("clear", {"trailing_timeout": cfg.get("trailing_timeout", 120)}),
    },
    "door": {
        "on": lambda cfg: ("trigger", {"timeout": cfg.get("timeout", 120)}),
        "off": None,  # Ignored
    },
    "media": {
        "playing": lambda cfg: ("trigger", {"timeout": None}),
        "idle": lambda cfg: ("clear", {"trailing_timeout": cfg.get("trailing_timeout", 300)}),
        "off": lambda cfg: ("clear", {"trailing_timeout": cfg.get("trailing_timeout", 300)}),
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
        "default_trailing_timeout": 120,  # 2 min for CLEAR events
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
# Get when next contribution expires
next_expiration = module.get_next_expiration(now)

if next_expiration:
    # Schedule wake at next_expiration
    schedule_callback(next_expiration, lambda: module.check_timeouts(datetime.now(UTC)))
```

Or use periodic checking:

```python
# Check every 30 seconds
while True:
    module.check_timeouts(datetime.now(UTC))
    await asyncio.sleep(30)
```

### Effective Timeout

The module exposes when a location will truly become vacant:

```python
now = datetime.now(UTC)

# Get all contributions for a location
state = module.get_location_state("kitchen")
contributions = state["contributions"]
# e.g., [{"source_id": "motion", "expires_at": "T+5min"}, {"source_id": "presence", "expires_at": None}]

# When truly vacant (considering all contributions)
next_vacant = module.get_next_vacant_time("kitchen", now)
# Returns None if any contribution is indefinite
```

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
    contributions = event.payload["contributions"]
    
    if occupied:
        # Turn on lights, adjust climate, etc.
        turn_on_lights(location_id)
        
        # Log what's keeping it occupied
        for c in contributions:
            print(f"  {c['source_id']}: expires {c['expires_at'] or 'indefinite'}")
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
module.trigger(
    location_id=location_id,
    source_id=entity_id,
    timeout=600,  # 10 min default
)
```

### "Definitive Vacant" Pattern

For devices that indicate "definitely empty":

```python
# Exit detected or manual clear
module.vacate(location_id=location_id)
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

---

## UI Integration: Occupancy Sources

The UI presents "Occupancy Sources" - entities configured to generate occupancy events for a location.

### Data Model

```python
# Per-location occupancy sources configuration
{
    "occupancy_sources": [
        {
            "entity_id": "binary_sensor.kitchen_motion",
            "type": "motion",          # Used for UI display and defaults
            "timeout": 300,            # Override, or use location default
            "enabled": True,
        },
        {
            "entity_id": "binary_sensor.kitchen_presence",
            "type": "presence",
            "trailing_timeout": 120,
            "enabled": True,
        },
    ]
}
```

### UI Display

The UI shows:
1. Which entities are configured as occupancy sources
2. Their current contribution status (contributing / not contributing)
3. When contributions expire
4. Entity type (for icon selection)

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
    assert len(state.contributions) == 1
    assert state.contributions[0].source_id == "binary_sensor.kitchen_motion"
    assert state.contributions[0].expires_at == now + timedelta(seconds=300)


def test_presence_with_motion_coverage_gap():
    """Test that motion sensor contribution survives presence sensor clearing."""
    now = datetime(2025, 1, 27, 12, 0, 0)
    
    # Presence sensor ON (indefinite)
    module.trigger("office", "presence", timeout=None)
    
    # Motion sensor triggers (10 min)
    module.trigger("office", "motion", timeout=600)
    
    # Presence clears with 2 min trailing
    module.clear("office", "presence", trailing_timeout=120)
    
    # After 3 minutes, presence has expired but motion still active
    module.check_timeouts(now + timedelta(minutes=3))
    
    state = module.get_state("office")
    assert state.is_occupied == True  # Motion still contributing!
    assert len(state.contributions) == 1
    assert state.contributions[0].source_id == "motion"
```

---

## Integration Responsibilities Summary

| Responsibility | Implementation |
|----------------|----------------|
| **Discovery** | Create Locations from platform areas |
| **Entity Mapping** | Configure which entities → which locations |
| **Occupancy Sources** | Configure entity types, timeouts, trailing timeouts |
| **Event Classification** | Map entity state changes → `trigger()` / `clear()` |
| **Timeout Scheduling** | Call `check_timeouts()` at scheduled times |
| **State Persistence** | Call `dump_state()` / `restore_state()` |
| **UI** | Display Occupancy Sources, contributions, configuration |
| **Commands** | Expose `vacate()`, `lock()`, `unlock()` as services |

---

## References

- **Architecture**: `../../architecture.md`
- **Design Document**: `design.md`
- **Design Decisions**: `design-decisions.md`
- **Implementation Status**: `implementation-status.md`
- **UI Design**: `../../../integration/ui-design.md`

---

**Status**: v3.0 ✅  
**Last Updated**: 2025-11-26

