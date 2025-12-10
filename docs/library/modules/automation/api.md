# Automation Module - API Reference

**Status**: v1.0  
**Date**: 2025.01.27  
**Module ID**: `automation`

---

## Overview

The AutomationModule provides rule-based automation processing. It responds to semantic events (like occupancy changes) and executes platform-specific actions via a platform adapter.

**Key Features**:
- Rule-based automation (trigger → condition → action)
- Time-of-day and lux-level conditions
- Device state checking (avoid redundant commands)
- Execution history for debugging
- Pre-built presets for common patterns

---

## Architecture

```
Platform Events (occupancy.changed, sensor.state_changed)
    │
    ▼
AutomationModule
    │
    │  Responsibilities:
    │  - Evaluate rules against events
    │  - Check conditions (time, lux, state)
    │  - Execute actions via PlatformAdapter
    │  - Track execution history
    │
    ▼
PlatformAdapter (You implement this)
    │
    │  Responsibilities:
    │  - Service calls (light.turn_on, etc.)
    │  - State queries (get entity state)
    │
    ▼
Platform (Home Assistant, etc.)
```

---

## Initialization

```python
from home_topology.modules.automation import AutomationModule
from home_topology.modules.automation.adapter import PlatformAdapter

# Create platform adapter (you implement this)
class MyPlatformAdapter(PlatformAdapter):
    def call_service(self, domain, service, entity_id, **kwargs):
        # Call platform service
        pass
    
    def get_state(self, entity_id):
        # Get entity state
        pass

# Initialize module
platform_adapter = MyPlatformAdapter()
automation = AutomationModule(platform=platform_adapter)

# Optional: Set occupancy module for LocationOccupiedCondition
automation.set_occupancy_module(occupancy_module)

# Attach to kernel
automation.attach(bus, loc_mgr)
```

---

## Rule Management

### Adding Rules

```python
from home_topology.modules.automation.models import (
    AutomationRule,
    EventTriggerConfig,
    TimeOfDayCondition,
    LuxLevelCondition,
    ServiceCallAction,
)

# Create a rule
rule = AutomationRule(
    id="lights_on_occupied",
    name="Turn on lights when occupied",
    trigger=EventTriggerConfig(
        event_type="occupancy.changed",
        location_id="kitchen",
    ),
    conditions=[
        TimeOfDayCondition(
            after="sunset",
            before="sunrise",
        ),
        LuxLevelCondition(
            location_id="kitchen",
            below=50.0,  # Only if dark
        ),
    ],
    actions=[
        ServiceCallAction(
            domain="light",
            service="turn_on",
            entity_id="light.kitchen",
            service_data={"brightness": 128},
        ),
    ],
)

# Add rule to location
automation.add_rule("kitchen", rule)
```

### Removing Rules

```python
# Remove by rule ID
removed = automation.remove_rule("kitchen", "lights_on_occupied")
```

### Querying Rules

```python
# Get all rules for a location
rules = automation.get_rules("kitchen")
```

---

## Rule Configuration

Rules are typically stored in LocationManager config:

```python
config = {
    "version": 1,
    "enabled": True,
    "trust_device_state": True,  # Skip state checks before actions
    "rules": [
        {
            "id": "lights_on_occupied",
            "name": "Turn on lights when occupied",
            "trigger": {
                "event_type": "occupancy.changed",
                "location_id": "kitchen",
            },
            "conditions": [
                {
                    "type": "time_of_day",
                    "after": "sunset",
                    "before": "sunrise",
                },
                {
                    "type": "lux_level",
                    "location_id": "kitchen",
                    "below": 50.0,
                },
            ],
            "actions": [
                {
                    "type": "service_call",
                    "domain": "light",
                    "service": "turn_on",
                    "entity_id": "light.kitchen",
                    "service_data": {"brightness": 128},
                },
            ],
        },
    ],
}

loc_mgr.set_module_config("kitchen", "automation", config)
```

---

## Trigger Types

### EventTriggerConfig

Triggers on semantic events:

```python
EventTriggerConfig(
    event_type="occupancy.changed",  # or "sensor.state_changed", etc.
    location_id="kitchen",  # Optional: filter by location
)
```

### Supported Event Types

- `occupancy.changed` - Occupancy state changes
- `sensor.state_changed` - Sensor state changes
- `presence.changed` - Person location changes
- `ambient.light_changed` - Light level changes

---

## Condition Types

### TimeOfDayCondition

```python
TimeOfDayCondition(
    after="sunset",  # or datetime, or "HH:MM"
    before="sunrise",  # or datetime, or "HH:MM"
)
```

### LuxLevelCondition

```python
LuxLevelCondition(
    location_id="kitchen",
    below=50.0,  # Only if lux < 50
    # OR
    above=500.0,  # Only if lux > 500
)
```

### StateCondition

```python
StateCondition(
    entity_id="light.kitchen",
    state="off",  # Only if current state is "off"
)
```

### LocationOccupiedCondition

```python
LocationOccupiedCondition(
    location_id="kitchen",
    occupied=True,  # Only if location is occupied
)
```

**Note**: Requires `set_occupancy_module()` to be called.

---

## Action Types

### ServiceCallAction

```python
ServiceCallAction(
    domain="light",
    service="turn_on",
    entity_id="light.kitchen",
    service_data={"brightness": 128, "color_temp": 370},
)
```

### DelayAction

```python
DelayAction(
    delay_seconds=5.0,
)
```

### Action Sequences

Actions execute in order. If any action fails, remaining actions are skipped.

---

## Execution History

```python
# Get execution history
history = automation.get_history(
    location_id="kitchen",  # Optional filter
    rule_id="lights_on_occupied",  # Optional filter
    limit=20,  # Max entries
)

# History entry format:
{
    "rule_id": "lights_on_occupied",
    "location_id": "kitchen",
    "trigger_event_type": "occupancy.changed",
    "conditions_met": True,
    "actions_executed": 1,
    "success": True,
    "error": None,
    "timestamp": "2025-01-27T14:30:00Z",
    "duration_ms": 45,
}
```

---

## Events Emitted

### automation.executed

Emitted when automation actions execute:

```python
Event(
    type="automation.executed",
    source="automation",
    location_id="kitchen",
    payload={
        "trigger_event": "occupancy.changed",
        "rules_evaluated": 2,
        "rules_triggered": 1,
        "actions_executed": 1,
        "errors": [],
    },
)
```

---

## Events Consumed

- `occupancy.changed` - Triggers rules based on occupancy
- `sensor.state_changed` - Triggers rules based on sensor changes
- `presence.changed` - Triggers rules based on person movement
- `ambient.light_changed` - Triggers rules based on light changes

---

## PlatformAdapter Interface

You must implement this interface:

```python
from home_topology.modules.automation.adapter import PlatformAdapter

class MyPlatformAdapter(PlatformAdapter):
    def call_service(
        self,
        domain: str,
        service: str,
        entity_id: Optional[str] = None,
        **service_data
    ) -> bool:
        """
        Call a platform service.
        
        Args:
            domain: Service domain (e.g., "light")
            service: Service name (e.g., "turn_on")
            entity_id: Optional entity ID
            **service_data: Additional service parameters
        
        Returns:
            True if service call succeeded
        """
        # Your implementation
        pass
    
    def get_state(self, entity_id: str) -> Optional[Dict]:
        """
        Get entity state.
        
        Args:
            entity_id: Entity ID
        
        Returns:
            State dict with "state" and "attributes" keys, or None
        """
        # Your implementation
        pass
```

---

## Configuration Schema

```python
{
    "type": "object",
    "properties": {
        "version": {"type": "integer", "default": 1},
        "enabled": {"type": "boolean", "default": True},
        "trust_device_state": {
            "type": "boolean",
            "default": True,
            "description": "Skip state checks before actions (faster, less safe)",
        },
        "rules": {
            "type": "array",
            "items": {
                # Rule schema (see rule configuration above)
            },
        },
    },
}
```

---

## Best Practices

1. **Use conditions wisely** - Too many conditions slow execution
2. **Trust device state** - Set `trust_device_state=True` if you trust platform state
3. **Test rules** - Use execution history to debug rule behavior
4. **Keep rules simple** - One rule per behavior is easier to debug
5. **Use presets** - Check `home_topology.modules.lighting.presets` for common patterns

---

## Example: Complete Rule

```python
from home_topology.modules.automation.models import (
    AutomationRule,
    EventTriggerConfig,
    TimeOfDayCondition,
    LuxLevelCondition,
    ServiceCallAction,
    DelayAction,
)

rule = AutomationRule(
    id="kitchen_lights_auto",
    name="Kitchen Lights Automation",
    trigger=EventTriggerConfig(
        event_type="occupancy.changed",
        location_id="kitchen",
    ),
    conditions=[
        # Only at night
        TimeOfDayCondition(
            after="sunset",
            before="sunrise",
        ),
        # Only if dark
        LuxLevelCondition(
            location_id="kitchen",
            below=50.0,
        ),
        # Only if lights are off
        StateCondition(
            entity_id="light.kitchen",
            state="off",
        ),
    ],
    actions=[
        # Turn on lights
        ServiceCallAction(
            domain="light",
            service="turn_on",
            entity_id="light.kitchen",
            service_data={"brightness": 128},
        ),
        # Wait 5 seconds
        DelayAction(delay_seconds=5.0),
        # Turn on under-cabinet lights
        ServiceCallAction(
            domain="light",
            service="turn_on",
            entity_id="light.kitchen_under_cabinet",
        ),
    ],
    execution_mode="single",  # Only one instance at a time
)

automation.add_rule("kitchen", rule)
```

---

**Document Version**: 1.0  
**Last Updated**: 2025.01.27  
**Status**: Living Document

