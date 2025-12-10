# home-topology API Cheat Sheet

**Quick Reference** for platform developers integrating home-topology.

> **Full Docs**: [Integration Guide](./integration-guide.md) | [API Reference](./api-reference.md)

---

## Core Setup

```python
from home_topology import LocationManager, EventBus, Event
from home_topology.modules.occupancy import OccupancyModule
from home_topology.modules.automation import AutomationModule
from home_topology.modules.presence import PresenceModule
from home_topology.modules.ambient import AmbientLightModule

# 1. Create kernel
loc_mgr = LocationManager()
bus = EventBus()
bus.set_location_manager(loc_mgr)

# 2. Initialize modules
occupancy = OccupancyModule()
automation = AutomationModule(platform_adapter)
presence = PresenceModule()
ambient = AmbientLightModule(platform_adapter)

# 3. Attach modules
for module in [occupancy, automation, presence, ambient]:
    module.attach(bus, loc_mgr)

# 4. Set cross-module dependencies
automation.set_occupancy_module(occupancy)
```

---

## LocationManager

### Topology

```python
# Create
loc = loc_mgr.create_location(id="kitchen", name="Kitchen", parent_id="main_floor")

# Update
loc = loc_mgr.update_location(
    "kitchen",
    name="Updated Name",  # Optional
    parent_id="new_parent",  # Optional
    aliases=["new alias"]  # Optional
)

# Delete
deleted_ids = loc_mgr.delete_location(
    "kitchen",
    cascade=False,        # Delete descendants
    orphan_children=False # Move children to Inbox
)

# Query
parent = loc_mgr.parent_of("kitchen")
children = loc_mgr.children_of("main_floor")
ancestors = loc_mgr.ancestors_of("kitchen")
descendants = loc_mgr.descendants_of("house")

# Get
location = loc_mgr.get_location("kitchen")
all_locations = loc_mgr.all_locations()
roots = loc_mgr.get_root_locations()
unassigned = loc_mgr.get_unassigned_locations()
```

### Entity Mapping

```python
loc_mgr.add_entity_to_location("binary_sensor.motion", "kitchen")
location_id = loc_mgr.get_entity_location("binary_sensor.motion")
entities = loc_mgr.get_entities_in_location("kitchen")
```

### Configuration

```python
loc_mgr.set_module_config("kitchen", "occupancy", {"version": 1, "enabled": True})
config = loc_mgr.get_module_config("kitchen", "occupancy")
loc_mgr.remove_module_config("kitchen", "occupancy")
```

---

## EventBus

### Publish

```python
bus.publish(Event(
    type="sensor.state_changed",
    source="ha",
    entity_id="binary_sensor.motion",
    location_id="kitchen",
    payload={"old_state": "off", "new_state": "on"},
    timestamp=datetime.now(UTC)
))
```

### Subscribe

```python
from home_topology.core.bus import EventFilter

# All events
bus.subscribe(handler)

# Filtered
bus.subscribe(handler, EventFilter(
    event_type="occupancy.changed",
    location_id="kitchen",
    include_ancestors=True
))

# Unsubscribe
bus.unsubscribe(handler)
```

---

## OccupancyModule

### Events (from device mappings)

```python
occupancy.trigger("kitchen", "binary_sensor.motion", timeout=300)
occupancy.hold("kitchen", "binary_sensor.presence")
occupancy.release("kitchen", "binary_sensor.presence", trailing_timeout=120)
```

### Commands (from automations/UI)

```python
occupancy.vacate("kitchen")
occupancy.lock("kitchen", "automation_123")
occupancy.unlock("kitchen", "automation_123")
occupancy.unlock_all("kitchen")
occupancy.vacate_area("kitchen")  # Vacate + all descendants
```

### State & Timeouts

```python
state = occupancy.get_location_state("kitchen")
# {"occupied": bool, "active_holds": List[str], "locked_by": List[str], ...}

next_timeout = occupancy.get_next_timeout(now)
occupancy.check_timeouts(now)  # Host responsibility
```

### Events

- **Emitted**: `occupancy.changed` - `{"occupied": bool, "active_holds": List[str], ...}`
- **Consumed**: `sensor.state_changed` (translated internally)

---

## AutomationModule

### Setup

```python
automation = AutomationModule(platform_adapter)
automation.set_occupancy_module(occupancy)  # Optional
automation.attach(bus, loc_mgr)
```

### Rules

```python
from home_topology.modules.automation.models import (
    AutomationRule, EventTriggerConfig, TimeOfDayCondition,
    LuxLevelCondition, ServiceCallAction
)

rule = AutomationRule(
    id="lights_on",
    trigger=EventTriggerConfig(event_type="occupancy.changed"),
    conditions=[
        TimeOfDayCondition(after="sunset", before="sunrise"),
        LuxLevelCondition(location_id="kitchen", below=50.0),
    ],
    actions=[
        ServiceCallAction(domain="light", service="turn_on", entity_id="light.kitchen"),
    ],
)

automation.add_rule("kitchen", rule)
automation.remove_rule("kitchen", "lights_on")
rules = automation.get_rules("kitchen")
```

### History

```python
history = automation.get_history(location_id="kitchen", limit=20)
```

### Events

- **Emitted**: `automation.executed` - `{"rules_triggered": int, "actions_executed": int, ...}`
- **Consumed**: `occupancy.changed`, `sensor.state_changed`, `presence.changed`, `ambient.light_changed`

---

## AmbientLightModule

### Queries

```python
reading = ambient.get_ambient_light("kitchen")
# AmbientLightReading {lux: float, is_dark: bool, is_bright: bool, ...}

is_dark = ambient.is_dark("kitchen", threshold=50.0)
is_bright = ambient.is_bright("kitchen", threshold=500.0)
```

### Sensor Config

```python
ambient.set_lux_sensor("kitchen", "sensor.kitchen_lux")
sensor = ambient.get_lux_sensor("kitchen", inherit=True)
ambient.refresh_sensor_cache("kitchen")
```

### Events

- **Emitted**: `ambient.light_changed` - `{"lux": float, "is_dark": bool, ...}`
- **Consumed**: `sensor.state_changed` (illuminance sensors)

---

## PresenceModule

### People

```python
person = presence.create_person(
    id="mike",
    name="Mike",
    device_trackers=["device_tracker.mike_phone"],
    user_id="ha_user_123"
)

presence.delete_person("mike")
person = presence.get_person("mike")
all_people = presence.all_people()
```

### Trackers

```python
presence.add_device_tracker("mike", "device_tracker.mike_watch", priority=10)
presence.remove_device_tracker("mike", "device_tracker.mike_phone")
```

### Location

```python
people = presence.get_people_in_location("kitchen")
location_id = presence.get_person_location("mike")
presence.move_person("mike", to_location_id="kitchen", source_tracker="...")
```

### Events

- **Emitted**: `presence.changed` - `{"person_id": str, "old_location": str, "new_location": str}`
- **Consumed**: `sensor.state_changed` (device trackers, processed by integration)

---

## Standard Event Types

| Event Type | Source | Payload |
|------------|--------|---------|
| `sensor.state_changed` | Platform | `{"old_state": str, "new_state": str, "attributes": dict}` |
| `occupancy.changed` | `occupancy` | `{"occupied": bool, "active_holds": List[str], ...}` |
| `presence.changed` | `presence` | `{"person_id": str, "old_location": str, "new_location": str}` |
| `ambient.light_changed` | `ambient` | `{"lux": float, "is_dark": bool, ...}` |
| `automation.executed` | `automation` | `{"rules_triggered": int, "actions_executed": int, ...}` |

---

## Common Patterns

### Event Translation

```python
@callback
def platform_state_changed(platform_event):
    entity_id = platform_event.data["entity_id"]
    location_id = loc_mgr.get_entity_location(entity_id)
    
    bus.publish(Event(
        type="sensor.state_changed",
        source="ha",
        entity_id=entity_id,
        location_id=location_id,
        payload={
            "old_state": platform_event.data["old_state"].state,
            "new_state": platform_event.data["new_state"].state,
        },
        timestamp=platform_event.data["new_state"].last_changed,
    ))
```

### State Exposure

```python
@callback
def on_occupancy_changed(event: Event):
    platform.states.set(
        f"binary_sensor.occupancy_{event.location_id}",
        "on" if event.payload["occupied"] else "off",
        attributes=event.payload
    )

bus.subscribe(on_occupancy_changed, EventFilter(event_type="occupancy.changed"))
```

### Timeout Scheduling

```python
def schedule_timeouts():
    next_timeout = None
    for module in modules.values():
        if hasattr(module, "get_next_timeout"):
            timeout = module.get_next_timeout()
            if timeout and (not next_timeout or timeout < next_timeout):
                next_timeout = timeout
    
    if next_timeout:
        platform.schedule_at(next_timeout, check_timeouts)

def check_timeouts(now):
    for module in modules.values():
        if hasattr(module, "check_timeouts"):
            module.check_timeouts(now)
    schedule_timeouts()
```

### State Persistence

```python
# Save
state_data = {
    module_id: module.dump_state()
    for module_id, module in modules.items()
}
platform.save_to_store("home_topology_state.json", state_data)

# Restore
state_data = platform.load_from_store("home_topology_state.json")
for module_id, module in modules.items():
    if state_data.get(module_id):
        module.restore_state(state_data[module_id])
```

---

## Module Config Schemas

### Occupancy

```python
{
    "version": 1,
    "enabled": True,
    "default_timeout": 300,
    "hold_release_timeout": 120,
    "occupancy_strategy": "independent",  # or "follow_parent"
    "contributes_to_parent": True,
}
```

### Automation

```python
{
    "version": 1,
    "enabled": True,
    "trust_device_state": True,
    "rules": [...],  # Array of AutomationRule dicts
}
```

### Ambient

```python
{
    "version": 1,
    "enabled": True,
    "lux_sensor": "sensor.kitchen_lux",  # Optional
    "auto_discover": True,
    "inherit_from_parent": True,
    "dark_threshold": 50.0,
    "bright_threshold": 500.0,
    "fallback_to_sun": True,
    "assume_dark_on_error": True,
}
```

### Presence

```python
{
    "version": 1,
    "enabled": True,
}
```

---

## Error Handling

```python
# Modules wrap handlers in try/except automatically
# Errors are logged, don't crash kernel

# Validation errors
try:
    occupancy.trigger("nonexistent", "sensor", 300)
except ValueError as e:
    # Location doesn't exist
    pass
```

---

## Quick Tips

- ✅ Keep event handlers fast (< 10ms)
- ✅ Use `EventFilter` to reduce handler calls
- ✅ Pass explicit `now` parameter in tests
- ✅ Version all configs
- ✅ Handle missing state gracefully
- ❌ Don't pass platform objects in event payloads
- ❌ Don't use `time.sleep()` in tests
- ❌ Don't store mutable platform objects in module state

---

**Document Version**: 1.0  
**Last Updated**: 2025.01.27  
**Status**: Quick Reference

