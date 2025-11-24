# Actions Module Design

> Detailed design specification for the ActionsModule

**Status**: Draft  
**Version**: 1.0  
**Last Updated**: 2024-11-24

---

## 1. Overview

The **ActionsModule** executes automations in response to semantic events (like `occupancy.changed`) from other modules. It provides rule-based trigger/condition/action logic with configurable device state handling.

### Goals

- ✅ React to semantic events from other modules
- ✅ Execute platform actions (lights, climate, etc.) via adapter
- ✅ Support conditions and constraints (time, state, manual overrides)
- ✅ Handle unreliable device states gracefully
- ✅ Provide action history and observability

---

## 2. Responsibilities

The ActionsModule:

- Subscribes to semantic events (`occupancy.changed`, etc.)
- Evaluates rule conditions (time of day, entity states, manual flags)
- Executes actions via platform adapter (HA service calls)
- Emits `action.executed` events for observability
- Maintains action history and statistics

---

## 3. Rule Structure

Each location can have multiple rules. A rule consists of:

```python
@dataclass
class ActionRule:
    id: str                              # Unique rule ID
    enabled: bool                        # Rule on/off
    trigger: TriggerConfig               # What event triggers this
    conditions: List[ConditionConfig]    # Must all be true
    actions: List[ActionConfig]          # What to execute
    mode: str                            # "single" | "restart" | "parallel"
```

### Example Rule

```python
{
    "id": "lights_on_occupied",
    "enabled": True,
    "trigger": {
        "event_type": "occupancy.changed",
        "payload_match": {"occupied": True},
    },
    "conditions": [
        {
            "type": "time_of_day",
            "after": "sunset",
            "before": "sunrise",
        },
        {
            "type": "state",
            "entity_id": "input_boolean.automation_enabled",
            "state": "on",
        },
    ],
    "actions": [
        {
            "service": "light.turn_on",
            "entity_id": "light.kitchen_ceiling",
        },
        {
            "service": "light.turn_on",
            "entity_id": "light.kitchen_under_cabinet",
            "data": {"brightness": 128},
        },
    ],
    "mode": "restart",  # Cancel previous if still running
}
```

---

## 4. Trigger System

### 4.1 Trigger Types

#### Event Trigger
```python
{
    "type": "event",
    "event_type": "occupancy.changed",
    "payload_match": {
        "occupied": True,
        "confidence": {"min": 0.7},  # Optional threshold
    },
}
```

#### State Trigger
```python
{
    "type": "state",
    "entity_id": "binary_sensor.kitchen_motion",
    "from": "off",
    "to": "on",
    "for_seconds": 5,  # Optional delay
}
```

#### Time Trigger
```python
{
    "type": "time",
    "at": "07:00:00",
}
```

### 4.2 Trigger Evaluation

```python
def _evaluate_trigger(self, rule: ActionRule, event: Event) -> bool:
    trigger = rule.trigger
    
    if trigger["type"] == "event":
        if event.type != trigger["event_type"]:
            return False
        
        # Check payload match
        payload_match = trigger.get("payload_match", {})
        for key, expected in payload_match.items():
            if event.payload.get(key) != expected:
                return False
        
        return True
    
    # ... other trigger types
```

---

## 5. Condition System

Conditions must ALL be true for actions to execute.

### 5.1 Condition Types

#### Time of Day
```python
{
    "type": "time_of_day",
    "after": "sunset",
    "before": "sunrise",
}
```

Or specific times:
```python
{
    "type": "time_of_day",
    "after": "22:00:00",
    "before": "06:00:00",
}
```

#### Entity State
```python
{
    "type": "state",
    "entity_id": "input_boolean.guest_mode",
    "state": "on",
}
```

#### Numeric State
```python
{
    "type": "numeric_state",
    "entity_id": "sensor.kitchen_temperature",
    "above": 18.0,
    "below": 26.0,
}
```

#### Location State
```python
{
    "type": "location_occupied",
    "location_id": "bedroom",
    "occupied": False,  # Bedroom must be unoccupied
}
```

#### Day of Week
```python
{
    "type": "day_of_week",
    "days": ["mon", "tue", "wed", "thu", "fri"],
}
```

### 5.2 Condition Evaluation

```python
def _evaluate_conditions(self, rule: ActionRule) -> bool:
    for condition in rule.conditions:
        if not self._evaluate_condition(condition):
            return False  # All must be true
    return True

def _evaluate_condition(self, condition: Dict) -> bool:
    if condition["type"] == "time_of_day":
        return self._check_time_of_day(
            after=condition.get("after"),
            before=condition.get("before"),
        )
    
    elif condition["type"] == "state":
        entity_id = condition["entity_id"]
        expected_state = condition["state"]
        actual_state = self._platform.get_state(entity_id)
        return actual_state == expected_state
    
    # ... other condition types
```

---

## 6. Action Execution

### 6.1 Action Types

#### Service Call
```python
{
    "service": "light.turn_on",
    "entity_id": "light.kitchen_ceiling",
    "data": {
        "brightness": 255,
        "color_temp": 300,
    },
}
```

#### Scene Activation
```python
{
    "service": "scene.turn_on",
    "entity_id": "scene.kitchen_bright",
}
```

#### Script Execution
```python
{
    "service": "script.turn_on",
    "entity_id": "script.goodnight_routine",
}
```

#### Delay
```python
{
    "delay": 5,  # seconds
}
```

### 6.2 Device State Handling

**Design Decision**: State checking is **configurable**.

```python
location.modules["actions"] = {
    "version": 1,
    "trust_device_state": True,  # Check state before sending command
    "mode": "optimistic",        # "optimistic" | "conservative"
    "rules": [...],
}
```

#### Optimistic Mode (`trust_device_state: True`)

Only send command if state differs:

```python
def _execute_action(self, action: Dict):
    if action["service"] == "light.turn_on":
        entity_id = action["entity_id"]
        current_state = self._platform.get_state(entity_id)
        
        if current_state == "on":
            # Already on, skip
            return
        
        self._platform.call_service("light", "turn_on", entity_id, action.get("data"))
```

#### Conservative Mode (`trust_device_state: False`)

Always send command (for flaky devices):

```python
def _execute_action(self, action: Dict):
    # Always execute, don't check state
    self._platform.call_service(
        domain=action["service"].split(".")[0],
        service=action["service"].split(".")[1],
        entity_id=action["entity_id"],
        data=action.get("data"),
    )
```

### 6.3 Execution Modes

**Single** (default): New trigger blocks if already running
```python
if self._is_rule_running(rule.id):
    return  # Skip
```

**Restart**: New trigger cancels previous execution
```python
if self._is_rule_running(rule.id):
    self._cancel_rule_execution(rule.id)
self._execute_rule(rule)
```

**Parallel**: Multiple executions can run simultaneously
```python
self._execute_rule(rule)  # Always run
```

---

## 7. Configuration Example

Per-location configuration:

```python
location.modules["actions"] = {
    "version": 1,
    "enabled": True,
    "trust_device_state": True,
    "mode": "optimistic",
    
    "rules": [
        {
            "id": "lights_on_occupied",
            "enabled": True,
            "trigger": {
                "type": "event",
                "event_type": "occupancy.changed",
                "payload_match": {"occupied": True},
            },
            "conditions": [
                {
                    "type": "time_of_day",
                    "after": "sunset",
                    "before": "sunrise",
                },
                {
                    "type": "state",
                    "entity_id": "input_boolean.kitchen_automation",
                    "state": "on",
                },
            ],
            "actions": [
                {
                    "service": "light.turn_on",
                    "entity_id": "light.kitchen_ceiling",
                    "data": {"brightness_pct": 100},
                },
            ],
            "mode": "restart",
        },
        {
            "id": "lights_off_unoccupied",
            "enabled": True,
            "trigger": {
                "type": "event",
                "event_type": "occupancy.changed",
                "payload_match": {"occupied": False},
            },
            "conditions": [],
            "actions": [
                {
                    "delay": 30,  # Wait 30 seconds
                },
                {
                    "service": "light.turn_off",
                    "entity_id": "light.kitchen_ceiling",
                },
            ],
            "mode": "restart",
        },
    ],
}
```

---

## 8. Event Emissions

Emit `action.executed` for observability:

```python
Event(
    type="action.executed",
    source="actions",
    location_id="kitchen",
    payload={
        "rule_id": "lights_on_occupied",
        "action": {
            "service": "light.turn_on",
            "entity_id": "light.kitchen_ceiling",
        },
        "success": True,
        "duration_ms": 45,
    },
    timestamp=datetime.now(UTC),
)
```

---

## 9. Action History

Track recent actions for debugging and statistics:

```python
@dataclass
class ActionExecution:
    rule_id: str
    location_id: str
    trigger_event: Event
    conditions_met: bool
    actions_executed: List[Dict]
    success: bool
    error: Optional[str]
    timestamp: datetime
    duration_ms: int

# Store in ring buffer (last 100 executions)
self._history: Deque[ActionExecution] = deque(maxlen=100)
```

---

## 10. Configuration Schema

JSON Schema for UI generation:

```python
def location_config_schema(self) -> Dict:
    return {
        "type": "object",
        "properties": {
            "enabled": {
                "type": "boolean",
                "title": "Enable Actions",
                "default": True,
            },
            "trust_device_state": {
                "type": "boolean",
                "title": "Trust Device State",
                "description": "Check state before sending commands",
                "default": True,
            },
            "mode": {
                "type": "string",
                "title": "Execution Mode",
                "enum": ["optimistic", "conservative"],
                "default": "optimistic",
            },
            "rules": {
                "type": "array",
                "title": "Action Rules",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "enabled": {"type": "boolean"},
                        "trigger": {"type": "object"},
                        "conditions": {"type": "array"},
                        "actions": {"type": "array"},
                        "mode": {
                            "type": "string",
                            "enum": ["single", "restart", "parallel"],
                        },
                    },
                },
            },
        },
    }
```

---

## 11. Platform Adapter Interface

Actions module talks to platform (HA) via adapter:

```python
class PlatformAdapter(ABC):
    @abstractmethod
    def call_service(
        self,
        domain: str,
        service: str,
        entity_id: str,
        data: Optional[Dict] = None,
    ) -> bool:
        """Execute a platform service call."""
        pass
    
    @abstractmethod
    def get_state(self, entity_id: str) -> str:
        """Get current state of an entity."""
        pass
    
    @abstractmethod
    def get_sun_position(self) -> Dict:
        """Get sunrise/sunset times."""
        pass

# HA Integration provides concrete implementation
class HAAdapter(PlatformAdapter):
    def call_service(self, domain, service, entity_id, data):
        # Call HA service
        hass.services.call(domain, service, {
            "entity_id": entity_id,
            **data,
        })
        return True
```

---

## 12. Implementation Plan

### Phase 1: Core Rule Engine (v0.1.0)
- [ ] ActionRule dataclass
- [ ] Event trigger handling
- [ ] Basic condition evaluation (time, state)
- [ ] Service call actions
- [ ] Event emission
- [ ] Tests for rule evaluation

### Phase 2: Advanced Conditions (v0.2.0)
- [ ] Numeric state conditions
- [ ] Location occupancy conditions
- [ ] Day of week conditions
- [ ] Condition combinations (AND/OR)
- [ ] Tests for all condition types

### Phase 3: Advanced Actions (v0.3.0)
- [ ] Execution modes (single, restart, parallel)
- [ ] Delay actions
- [ ] Action history
- [ ] Configurable state checking
- [ ] Tests for modes and history

### Phase 4: Polish (v1.0.0)
- [ ] Configuration migration
- [ ] Performance optimization
- [ ] Error handling and recovery
- [ ] Documentation

---

## 13. Testing Strategy

### Unit Tests
- Trigger matching
- Condition evaluation (all types)
- Action execution (with mock adapter)
- Execution mode handling

### Integration Tests
- Occupancy event → actions triggered
- Multiple rules per location
- State checking modes (optimistic vs conservative)
- Action history tracking

### Scenario Tests
- "Turn lights on at sunset if occupied"
- "Turn off after 5 minutes unoccupied"
- "Don't trigger if guest mode enabled"
- "Parallel execution with multiple triggers"

---

## 14. Error Handling

Actions should be **best-effort**:

```python
def _execute_action(self, action: Dict, rule_id: str, location_id: str):
    try:
        # Execute via platform adapter
        success = self._platform.call_service(...)
        
        # Emit success event
        self._emit_action_executed(rule_id, location_id, action, success=True)
        
    except Exception as e:
        # Log error but don't crash
        logger.error(
            f"Action execution failed: {rule_id} / {action}",
            exc_info=True,
        )
        
        # Emit failure event
        self._emit_action_executed(
            rule_id, location_id, action,
            success=False, error=str(e)
        )
```

---

**Status**: Ready for Implementation  
**Dependencies**: Core kernel, OccupancyModule (for testing)  
**Next**: Implement Phase 1

