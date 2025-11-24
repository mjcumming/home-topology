# Occupancy Module Design

> Detailed design specification for the OccupancyModule

**Status**: Draft  
**Version**: 1.0  
**Last Updated**: 2024-11-24

---

## 1. Overview

The **OccupancyModule** tracks occupancy state per Location in the home topology. It synthesizes multiple signal types (motion, presence, lights, power, etc.) into a unified occupancy state with confidence scoring.

### Goals

- ✅ Provide accurate, real-time occupancy state per location
- ✅ Use all available signals intelligently (motion, lights, power, media)
- ✅ Prevent feedback loops while maximizing signal usage
- ✅ Support hierarchy propagation (child → parent, parent → child)
- ✅ Provide confidence scores for nuanced automation decisions

---

## 2. Responsibilities

The OccupancyModule:

- Tracks occupancy state per Location (`occupied: bool`, `confidence: float`)
- Processes sensor inputs and computes state transitions
- Handles motion timeout logic (simple, adaptive, hierarchy modes)
- Propagates occupancy up/down the location hierarchy
- Emits `occupancy.changed` semantic events when state changes

---

## 3. Per-Location State

Each location tracked by OccupancyModule maintains:

```python
@dataclass
class OccupancyState:
    occupied: bool                      # Currently occupied?
    confidence: float                   # 0.0 - 1.0 confidence score
    last_motion: datetime               # Last motion sensor trigger
    last_state_change: datetime         # Last occupied ↔ unoccupied transition
    reason: str                         # Why this state? "motion", "timeout", "propagated_up"
    primary_signals_active: List[str]   # Which primary signals are ON
    secondary_signals_active: List[str] # Which secondary signals are ON
```

---

## 4. Signal System

The module uses a **two-tier signal system** to prevent feedback loops while maximizing available data.

### 4.1 Primary Signals (Direct Triggers)

These **directly indicate presence** and can trigger "occupied" state:

#### Motion Sensors
- **Entity Type**: `binary_sensor.*.motion`
- **Behavior**: 
  - `ON` → Set `occupied = True` immediately, `confidence = 1.0`
  - `OFF` → Start timeout timer
- **Use Case**: Primary occupancy indicator for most rooms

#### Presence Sensors  
- **Entity Type**: `binary_sensor.*.presence`, device trackers
- **Technologies**: Bluetooth, WiFi, BLE beacons, mmWave
- **Behavior**:
  - `ON` → Set `occupied = True` immediately, `confidence = 0.95`
  - `OFF` → Start timeout timer (longer than motion)
- **Use Case**: Rooms with stationary occupancy (reading, working)

#### Door/Window Sensors (Optional)
- **Entity Type**: `binary_sensor.*.door`, `binary_sensor.*.window`
- **Behavior**: Configurable per location
  - Entry door `OPEN` → Assume entry, set occupied
  - Exit door `OPEN` → Potentially clear occupied (if no other signals)
- **Use Case**: Entrance zones, tracking entry/exit patterns

### 4.2 Secondary Signals (Confidence Boosters)

These **provide context** and adjust confidence, but **do not directly trigger** state changes.

**Why?** This prevents loops: Actions turn light ON → Light boosts confidence (not directly occupied) → No loop

#### Lights
- **Entity Type**: `light.*`
- **Behavior**:
  - `ON` → Boost confidence by configured weight (default: +0.3)
  - `OFF` → Decrease confidence by weight
  - Multiple lights can compound
- **Configuration**:
  ```python
  "lights": {
      "enabled": True,
      "entity_ids": ["light.kitchen_ceiling", "light.kitchen_under_cabinet"],
      "weight": 0.3,
      "ignore_dim": False,  # Treat dim lights as OFF?
  }
  ```
- **Use Case**: Someone turned lights on → likely occupied

#### Switches
- **Entity Type**: `switch.*`
- **Examples**: Coffee maker, fans, space heaters
- **Behavior**:
  - `ON` → Boost confidence by weight (default: +0.2)
  - `OFF` → No change (or slight decrease)
- **Configuration**:
  ```python
  "switches": {
      "enabled": True,
      "entity_ids": ["switch.coffee_maker", "switch.desk_fan"],
      "weight": 0.2,
  }
  ```

#### Media Players
- **Entity Type**: `media_player.*`
- **Behavior**:
  - `playing` → Strong confidence boost (+0.4)
  - `paused` → Neutral
  - `off` → Confidence decrease
- **Configuration**:
  ```python
  "media_players": {
      "enabled": True,
      "entity_ids": ["media_player.kitchen_speaker"],
      "weight": 0.4,
  }
  ```

#### Power Consumption
- **Entity Type**: `sensor.*.power`
- **Behavior**:
  - Power > threshold → Strong confidence boost (+0.4)
  - Spike above baseline → Moderate boost (+0.2)
  - Power < threshold → Neutral or slight decrease
- **Configuration**:
  ```python
  "power": {
      "enabled": True,
      "entity_ids": ["sensor.kitchen_power"],
      "threshold_watts": 50,
      "weight": 0.4,
  }
  ```
- **Use Case**: Kitchen (stove), office (computer), laundry (washer/dryer)

#### Climate Control
- **Entity Type**: `climate.*`
- **Behavior**:
  - Recently adjusted → Confidence boost (+0.2)
  - Mode change → Moderate boost
- **Use Case**: Manual climate adjustment suggests presence

---

## 5. Configuration Example

Per-location configuration structure:

```python
location.modules["occupancy"] = {
    "version": 1,
    "enabled": True,
    
    "primary_signals": {
        "motion_sensors": [
            "binary_sensor.kitchen_motion_1",
            "binary_sensor.kitchen_motion_2",
        ],
        "presence_sensors": [],
        "door_sensors": {
            "enabled": False,
            "entry_doors": [],
            "exit_doors": [],
        },
    },
    
    "secondary_signals": {
        "lights": {
            "enabled": True,
            "entity_ids": ["light.kitchen_ceiling", "light.kitchen_under_cabinet"],
            "weight": 0.3,
        },
        "switches": {
            "enabled": True,
            "entity_ids": ["switch.coffee_maker"],
            "weight": 0.2,
        },
        "media_players": {
            "enabled": True,
            "entity_ids": ["media_player.kitchen_speaker"],
            "weight": 0.4,
        },
        "power": {
            "enabled": True,
            "entity_ids": ["sensor.kitchen_power"],
            "threshold_watts": 50,
            "weight": 0.4,
        },
    },
    
    "timeout": {
        "mode": "simple",  # "simple" | "adaptive" | "hierarchy"
        "timeout_seconds": 300,
    },
    
    "hierarchy": {
        "propagate_up": True,     # Child occupied → parent occupied
        "propagate_down": True,   # Parent occupied → child confidence boost
        "down_weight": 0.2,
    },
}
```

---

## 6. Timeout Logic

### 6.1 Simple Mode (Default)

Fixed timeout after last primary signal:

```python
if no_primary_signals_for(timeout_seconds):
    occupied = False
    confidence = 0.0
    reason = "timeout"
```

### 6.2 Adaptive Mode

Learns typical occupancy patterns and adjusts timeout:

```python
# Learn from history
typical_duration = learn_from_past_occupancy(location_id, time_of_day)

# Adjust timeout dynamically
adjusted_timeout = base_timeout * typical_duration_factor

if no_primary_signals_for(adjusted_timeout):
    occupied = False
```

**Learning inputs**:
- Time of day (morning kitchen vs midnight kitchen)
- Day of week (weekday office vs weekend office)
- Historical occupancy duration

### 6.3 Hierarchy Mode

Children occupied → parent timeout paused:

```python
if any_child_occupied(location_id):
    # Don't timeout parent location
    reset_timeout_timer()
```

---

## 7. State Transition Logic

### 7.1 Unoccupied → Occupied

**Trigger**: Any primary signal becomes active

```python
def on_primary_signal_active(location_id, signal_id):
    state = self._state[location_id]
    
    # Update state
    state.occupied = True
    state.confidence = 1.0
    state.last_motion = now()
    state.reason = f"primary:{signal_id}"
    
    # Cancel timeout timer
    self._cancel_timeout_timer(location_id)
    
    # Emit event
    self._emit_occupancy_changed(location_id, state)
    
    # Propagate up hierarchy
    if config["hierarchy"]["propagate_up"]:
        self._propagate_up(location_id)
```

### 7.2 Occupied → Unoccupied

**Trigger**: Timeout expires, no primary signals, low confidence

```python
def on_timeout(location_id):
    state = self._state[location_id]
    
    # Check if still any primary signals
    if self._has_active_primary_signals(location_id):
        return  # False alarm, reschedule
    
    # Check confidence from secondary signals
    confidence = self._calculate_confidence(location_id)
    
    if confidence < 0.3:  # Threshold
        state.occupied = False
        state.confidence = 0.0
        state.reason = "timeout"
        self._emit_occupancy_changed(location_id, state)
    else:
        # Still some secondary signals, extend timeout
        self._reschedule_timeout(location_id, extended=True)
```

### 7.3 Confidence Adjustment

Continuously adjust confidence based on secondary signals:

```python
def _calculate_confidence(location_id) -> float:
    config = self._get_config(location_id)
    confidence = 0.0
    
    # Primary signals always give full confidence
    if self._has_active_primary_signals(location_id):
        confidence = 1.0
    
    # Add secondary signal contributions
    for signal_type in ["lights", "switches", "media_players", "power"]:
        if config["secondary_signals"][signal_type]["enabled"]:
            active = self._get_active_signals(location_id, signal_type)
            weight = config["secondary_signals"][signal_type]["weight"]
            confidence += len(active) * weight
    
    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, confidence))
```

---

## 8. Hierarchy Propagation

### 8.1 Upward Propagation

If any child is occupied → parent is occupied:

```python
def _propagate_up(location_id):
    parent_id = self._loc_manager.parent_of(location_id)
    if not parent_id:
        return
    
    parent_state = self._state[parent_id]
    
    # Any child occupied → parent occupied
    if not parent_state.occupied:
        parent_state.occupied = True
        parent_state.confidence = 0.8  # Slightly lower confidence
        parent_state.reason = f"propagated_from:{location_id}"
        self._emit_occupancy_changed(parent_id, parent_state)
        
        # Recursively propagate
        self._propagate_up(parent_id)
```

### 8.2 Downward Confidence Boost

Parent occupied → children get confidence boost:

```python
def _propagate_down(location_id):
    children = self._loc_manager.children_of(location_id)
    config = self._get_config(location_id)
    weight = config["hierarchy"]["down_weight"]
    
    for child in children:
        child_state = self._state[child.id]
        
        # Boost child confidence
        child_state.confidence = min(1.0, child_state.confidence + weight)
```

---

## 9. Event Emissions

Emit `occupancy.changed` when:
- Occupied state changes: `False → True` or `True → False`
- Confidence changes significantly (threshold: ±0.2)

Event structure:

```python
Event(
    type="occupancy.changed",
    source="occupancy",
    location_id="kitchen",
    payload={
        "occupied": True,
        "confidence": 0.95,
        "previous_occupied": False,
        "previous_confidence": 0.0,
        "reason": "primary:binary_sensor.kitchen_motion",
        "active_signals": {
            "primary": ["binary_sensor.kitchen_motion"],
            "secondary": ["light.kitchen_ceiling", "switch.coffee_maker"],
        },
    },
    timestamp=datetime.now(UTC),
)
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
                "title": "Enable Occupancy Tracking",
                "default": True,
            },
            "primary_signals": {
                "type": "object",
                "title": "Primary Signals",
                "properties": {
                    "motion_sensors": {
                        "type": "array",
                        "title": "Motion Sensors",
                        "items": {"type": "string"},
                    },
                    # ... more
                },
            },
            "secondary_signals": {
                "type": "object",
                "title": "Secondary Signals",
                "properties": {
                    "lights": {
                        "type": "object",
                        "properties": {
                            "enabled": {"type": "boolean"},
                            "entity_ids": {"type": "array", "items": {"type": "string"}},
                            "weight": {"type": "number", "minimum": 0, "maximum": 1},
                        },
                    },
                    # ... more
                },
            },
            "timeout": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["simple", "adaptive", "hierarchy"],
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "minimum": 30,
                        "default": 300,
                    },
                },
            },
        },
    }
```

---

## 11. Implementation Plan

### Phase 1: Core State Machine (v0.1.0)
- [ ] OccupancyState dataclass
- [ ] Primary signal handling (motion, presence)
- [ ] Simple timeout mode
- [ ] Basic event emission
- [ ] Tests for state transitions

### Phase 2: Secondary Signals (v0.2.0)
- [ ] Light state integration
- [ ] Switch state integration
- [ ] Confidence calculation
- [ ] Tests for confidence scoring

### Phase 3: Advanced Features (v0.3.0)
- [ ] Media player support
- [ ] Power consumption support
- [ ] Hierarchy propagation (up/down)
- [ ] Adaptive timeout mode
- [ ] Tests for hierarchy and learning

### Phase 4: Polish (v1.0.0)
- [ ] Configuration migration
- [ ] State persistence
- [ ] Performance optimization
- [ ] Documentation

---

## 12. Testing Strategy

### Unit Tests
- State transitions (unoccupied ↔ occupied)
- Confidence calculation with various signal combinations
- Timeout logic (simple mode)
- Event emission on state change

### Integration Tests
- Primary + secondary signal interaction
- Hierarchy propagation (parent/child)
- Timeout with secondary signals active
- Config migration

### Scenario Tests
- "Sitting still in office" (no motion, but lights + power)
- "Quick bathroom visit" (motion → timeout)
- "Family in living room" (multiple signals, hierarchy)

---

**Status**: Ready for Implementation  
**Dependencies**: Core kernel (Location, EventBus, LocationManager)  
**Next**: Implement Phase 1

