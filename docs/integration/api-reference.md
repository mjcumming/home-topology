# home-topology API Reference

**Version**: 1.0  
**Date**: 2025.01.27  
**Audience**: Platform developers integrating home-topology

> **Quick Links**:  
> - [Integration Guide](./integration-guide.md) - Complete integration walkthrough
> - [API Cheat Sheet](./api-cheat-sheet.md) - Quick reference
> - [Module APIs](./library/modules/) - Detailed module documentation

---

## Table of Contents

1. [Core Components](#core-components)
2. [Module APIs](#module-apis)
3. [Event System](#event-system)
4. [Common Patterns](#common-patterns)

---

## Core Components

### LocationManager

Manages the location topology and per-location module configuration.

#### Topology Management

```python
# Create locations
location = loc_mgr.create_location(
    id="kitchen",
    name="Kitchen",
    parent_id="main_floor",
    is_explicit_root=False,
    ha_area_id="area_kitchen",  # Optional platform link
    aliases=["cooking area"]    # Optional voice assistant aliases
)

# Update locations
location = loc_mgr.update_location(
    location_id="kitchen",
    name="Updated Kitchen Name",  # Optional: None to keep current
    parent_id="new_parent",       # Optional: None to keep, "" to clear
    aliases=["new alias"]          # Optional: None to keep current
)

# Delete locations
deleted_ids = loc_mgr.delete_location(
    location_id="kitchen",
    cascade=False,        # If True, delete all descendants
    orphan_children=False # If True, move children to Inbox
)
# Returns: List of deleted location IDs

# Query hierarchy
parent = loc_mgr.parent_of("kitchen")
children = loc_mgr.children_of("main_floor")
ancestors = loc_mgr.ancestors_of("kitchen")  # [main_floor, house]
descendants = loc_mgr.descendants_of("house")  # All locations under house

# Get locations
location = loc_mgr.get_location("kitchen")
all_locations = loc_mgr.all_locations()
roots = loc_mgr.get_root_locations()
unassigned = loc_mgr.get_unassigned_locations()  # Inbox items

# Entity mapping
loc_mgr.add_entity_to_location("binary_sensor.kitchen_motion", "kitchen")
location_id = loc_mgr.get_entity_location("binary_sensor.kitchen_motion")
entities = loc_mgr.get_entities_in_location("kitchen")
```

#### Configuration Management

```python
# Store module config
loc_mgr.set_module_config(
    location_id="kitchen",
    module_id="occupancy",
    config={"version": 1, "enabled": True, "default_timeout": 300}
)

# Retrieve config
config = loc_mgr.get_module_config("kitchen", "occupancy")

# Remove config
loc_mgr.remove_module_config("kitchen", "occupancy")
```

---

### EventBus

Synchronous event dispatcher with location-aware filtering.

#### Publishing Events

```python
from home_topology.core.bus import Event
from datetime import datetime, UTC

bus.publish(Event(
    type="sensor.state_changed",
    source="ha",
    entity_id="binary_sensor.kitchen_motion",
    location_id="kitchen",
    payload={"old_state": "off", "new_state": "on"},
    timestamp=datetime.now(UTC)
))
```

#### Subscribing to Events

```python
from home_topology.core.bus import EventFilter

# Subscribe to all events
bus.subscribe(handler_function)

# Subscribe with filter
bus.subscribe(
    handler_function,
    EventFilter(
        event_type="occupancy.changed",
        location_id="kitchen",
        include_ancestors=True,  # Also receive events from parent locations
        include_descendants=False
    )
)

# Unsubscribe
bus.unsubscribe(handler_function)
```

#### Event Filter Options

- `event_type`: Filter by event type (e.g., `"occupancy.changed"`)
- `location_id`: Filter by specific location
- `include_ancestors`: Include events from parent locations
- `include_descendants`: Include events from child locations

---

## Module APIs

### LocationModule Base Interface

All modules implement this interface:

```python
class LocationModule:
    @property
    def id(self) -> str:
        """Unique module identifier (e.g., 'occupancy')."""
    
    @property
    def CURRENT_CONFIG_VERSION(self) -> int:
        """Current configuration version."""
    
    def attach(bus: EventBus, loc_manager: LocationManager) -> None:
        """Attach module to kernel."""
    
    def default_config() -> Dict:
        """Get default configuration."""
    
    def location_config_schema() -> Dict:
        """Get JSON schema for UI configuration."""
    
    def migrate_config(config: Dict) -> Dict:
        """Migrate config from older versions."""
    
    def on_location_config_changed(location_id: str, config: Dict) -> None:
        """Handle config updates."""
    
    def dump_state() -> Dict:
        """Export runtime state for persistence."""
    
    def restore_state(state: Dict) -> None:
        """Restore runtime state from persistence."""
```

---

### OccupancyModule

Tracks binary occupancy state per location.

#### Public API

```python
from home_topology.modules.occupancy import OccupancyModule

occupancy = OccupancyModule()
occupancy.attach(bus, loc_mgr)

# Event methods (from device mappings)
occupancy.trigger(location_id, source_id, timeout)
occupancy.hold(location_id, source_id)
occupancy.release(location_id, source_id, trailing_timeout)

# Command methods (from automations/UI)
occupancy.vacate(location_id)
occupancy.lock(location_id, source_id)
occupancy.unlock(location_id, source_id)
occupancy.unlock_all(location_id)
occupancy.vacate_area(location_id)  # Vacate location and all descendants

# State queries
state = occupancy.get_location_state(location_id)
# Returns: {
#     "occupied": bool,
#     "active_holds": List[str],
#     "locked_by": List[str],
#     "is_locked": bool,
#     "occupied_until": Optional[str],  # ISO datetime
#     "timer_remaining": Optional[float]  # seconds
# }

# Timeout management (host responsibility)
next_timeout = occupancy.get_next_timeout(now)
occupancy.check_timeouts(now)

# State persistence
state_dump = occupancy.dump_state()
occupancy.restore_state(state_dump)
```

#### Events Emitted

- `occupancy.changed` - When occupancy state changes
  - Payload: `{"occupied": bool, "active_holds": List[str], "locked_by": List[str], ...}`

#### Events Consumed

- `sensor.state_changed` - Platform sensor updates (translated internally)

---

### AutomationModule

Rule-based automation processor.

#### Public API

```python
from home_topology.modules.automation import AutomationModule
from home_topology.modules.automation.adapter import PlatformAdapter

# Requires platform adapter for service calls
automation = AutomationModule(platform=platform_adapter)
automation.set_occupancy_module(occupancy)  # Optional, for LocationOccupiedCondition
automation.attach(bus, loc_mgr)

# Rules are configured via LocationManager config
# See automation module docs for rule format
```

#### Events Emitted

- `automation.triggered` - When a rule is triggered
- `automation.executed` - When a rule action executes

#### Events Consumed

- `occupancy.changed` - Triggers rules based on occupancy
- `sensor.state_changed` - Triggers rules based on sensor changes

---

### AmbientLightModule

Intelligent ambient light detection with hierarchical sensor lookup.

#### Public API

```python
from home_topology.modules.ambient import AmbientLightModule

ambient = AmbientLightModule(platform_adapter=platform)
ambient.attach(bus, loc_mgr)

# Get current light reading
reading = ambient.get_light_reading(location_id)
# Returns: AmbientLightReading {
#     lux: float,
#     is_dark: bool,
#     is_bright: bool,
#     source: str,  # "sensor", "parent", "sun", "fallback"
#     sensor_id: Optional[str],
#     timestamp: datetime
# }

# Check if location is dark/bright
is_dark = ambient.is_dark(location_id)
is_bright = ambient.is_bright(location_id)

# Force refresh (re-discover sensors)
ambient.refresh_sensor_cache(location_id)
```

#### Events Emitted

- `ambient.light_changed` - When light level changes significantly

#### Events Consumed

- `sensor.state_changed` - Illuminance sensor updates

---

### PresenceModule

Tracks WHO is in each location (person tracking).

#### Public API

```python
from home_topology.modules.presence import PresenceModule

presence = PresenceModule()
presence.attach(bus, loc_mgr)

# Person management
person = presence.create_person(
    id="mike",
    name="Mike",
    device_trackers=["device_tracker.mike_phone", "device_tracker.mike_watch"],
    user_id="ha_user_123",  # Optional platform user ID
    picture="/local/mike.jpg"  # Optional
)

presence.delete_person("mike")

# Device tracker management
presence.add_device_tracker("mike", "device_tracker.mike_tablet")
presence.remove_device_tracker("mike", "device_tracker.mike_phone")

# Query presence
people = presence.get_people_in_location("kitchen")
# Returns: List[Person]

current_location = presence.get_person_location("mike")
# Returns: Optional[str] (location_id)

all_people = presence.get_all_people()
# Returns: List[Person]
```

#### Events Emitted

- `presence.changed` - When a person's location changes
  - Payload: `{"person_id": str, "old_location": Optional[str], "new_location": Optional[str]}`

#### Events Consumed

- `sensor.state_changed` - Device tracker updates

---

## Event System

### Standard Event Types

| Event Type | Source | When | Payload |
|------------|--------|------|---------|
| `sensor.state_changed` | Platform | Entity state changes | `{"old_state": str, "new_state": str, "attributes": dict}` |
| `occupancy.changed` | `occupancy` | Occupancy state changes | `{"occupied": bool, "active_holds": List[str], ...}` |
| `presence.changed` | `presence` | Person location changes | `{"person_id": str, "old_location": str, "new_location": str}` |
| `ambient.light_changed` | `ambient` | Light level changes | `{"lux": float, "is_dark": bool, ...}` |
| `automation.triggered` | `automation` | Rule triggered | `{"rule_id": str, "location_id": str, ...}` |
| `automation.executed` | `automation` | Action executed | `{"rule_id": str, "action": str, ...}` |

### Event Payload Guidelines

- Keep payloads **JSON-serializable** (no platform-specific objects)
- Include timestamps in ISO format
- Use consistent naming (snake_case)
- Document event schemas in module docs

---

## Common Patterns

### Initialization Pattern

```python
# 1. Create kernel
loc_mgr = LocationManager()
bus = EventBus()
bus.set_location_manager(loc_mgr)

# 2. Build topology
build_topology_from_platform(platform, loc_mgr)

# 3. Initialize modules
modules = {
    "occupancy": OccupancyModule(),
    "automation": AutomationModule(platform_adapter),
    "presence": PresenceModule(),
    "ambient": AmbientLightModule(platform_adapter),
}

# 4. Attach modules
for module in modules.values():
    module.attach(bus, loc_mgr)

# 5. Set up cross-module dependencies
modules["automation"].set_occupancy_module(modules["occupancy"])

# 6. Restore state
for module_id, module in modules.items():
    if state_data.get(module_id):
        module.restore_state(state_data[module_id])
```

### Event Translation Pattern

```python
@callback
def platform_state_changed(platform_event):
    """Translate platform event to kernel event."""
    entity_id = platform_event.data["entity_id"]
    location_id = loc_mgr.get_entity_location(entity_id)
    
    kernel_event = Event(
        type="sensor.state_changed",
        source="ha",
        entity_id=entity_id,
        location_id=location_id,
        payload={
            "old_state": platform_event.data["old_state"].state,
            "new_state": platform_event.data["new_state"].state,
            "attributes": dict(platform_event.data["new_state"].attributes),
        },
        timestamp=platform_event.data["new_state"].last_changed,
    )
    
    bus.publish(kernel_event)
```

### State Exposure Pattern

```python
def setup_state_exposure(bus, modules):
    """Expose module state as platform entities."""
    
    @callback
    def on_occupancy_changed(event: Event):
        location_id = event.location_id
        payload = event.payload
        
        # Update platform entity
        platform.states.set(
            f"binary_sensor.occupancy_{location_id}",
            "on" if payload["occupied"] else "off",
            attributes={
                "confidence": payload.get("confidence"),
                "active_holds": payload.get("active_holds", []),
            }
        )
    
    bus.subscribe(
        on_occupancy_changed,
        EventFilter(event_type="occupancy.changed")
    )
```

### Timeout Scheduling Pattern

```python
class TimeoutCoordinator:
    def __init__(self, modules):
        self.modules = modules
        self._cancel = None
    
    def schedule_next_timeout(self):
        """Schedule next timeout check."""
        if self._cancel:
            self._cancel()
        
        # Find earliest timeout
        next_timeout = None
        for module in self.modules.values():
            if hasattr(module, "get_next_timeout"):
                module_timeout = module.get_next_timeout()
                if module_timeout and (not next_timeout or module_timeout < next_timeout):
                    next_timeout = module_timeout
        
        # Schedule callback
        if next_timeout:
            self._cancel = platform.schedule_at(next_timeout, self._handle_timeout)
    
    def _handle_timeout(self, now):
        """Handle timeout check."""
        for module in self.modules.values():
            if hasattr(module, "check_timeouts"):
                module.check_timeouts(now)
        
        self.schedule_next_timeout()
```

---

## Error Handling

### Module Errors

Modules wrap event handlers in try/except. Errors are logged but don't crash the kernel:

```python
# In EventBus.publish()
try:
    handler(event)
except Exception as e:
    logger.error(f"Error in handler {handler.__name__}: {e}", exc_info=True)
```

### Validation Errors

- `ValueError`: Invalid parameters (location doesn't exist, etc.)
- `KeyError`: Missing required config keys
- Always validate before calling module methods

---

## Best Practices

1. **Keep handlers fast** - Event handlers should be < 10ms
2. **Use EventFilter** - Reduce unnecessary handler calls
3. **Validate config** - Check config before applying
4. **Handle missing state** - Gracefully handle None/empty state
5. **Log errors** - Include context (location_id, entity_id, etc.)
6. **Version configs** - Always version module configs
7. **Test time-agnostic** - Pass explicit `now` parameter in tests

---

**Document Version**: 1.0  
**Last Updated**: 2025.01.27  
**Status**: Living Document

