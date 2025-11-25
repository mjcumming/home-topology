# Occupancy Module - Rule-Based Engine Design Specification

**Status**: Draft  
**Version**: 1.0  
**Date**: 2025.01.XX  
**Context**: home-topology Kernel Module

---

## 1. Overview

The Occupancy Module is responsible for determining the binary state (occupied / clear) of a Location based on sensor inputs.

Unlike traditional occupancy managers that assign static "Roles" to sensors (e.g., "Motion Sensor is a Trigger"), this module uses a **Granular Event-Based Rule Engine**. This allows a single device to behave differently based on which event it emits (e.g., a Light Switch turning ON might force occupancy, while turning OFF might start a short clearing timer).

---

## 2. Core Architecture

### 2.1. The Location State Machine

Each Location maintains a state machine with the following properties:

- **State**: `Occupied` | `Clear`
- **Timer**: A countdown timer that, when expired, transitions state to `Clear`
- **Locks**: Boolean flags (e.g., "Wasp-in-a-Box") that prevent state transitions even if the timer expires

### 2.2. The Rule Engine

Instead of hardcoded logic, the module processes a list of user-defined rules attached to devices.

**The Logic Flow:**

1. **Event Received**: The Kernel receives an event (e.g., `binary_sensor.kitchen_motion -> on`)
2. **Rule Lookup**: The module looks up configured rules for that specific device ID
3. **Rule Evaluation**: If the event matches a rule's trigger, the rule's action is executed

---

## 3. Rule Specification

A Rule consists of three components: **Trigger**, **Action**, and **Parameter**.

### 3.1. Triggers (The "When")

Events that initiate logic, organized by sensor type.

> **Note**: Event normalization happens in the integration layer. The core library expects normalized events in this format.

#### Sensor Types and Their Events

| Sensor Type | Event | Description |
|-------------|-------|-------------|
| `motion_sensor` | `motion` | Presence detected (PIR, mmWave, presence sensor) |
| `motion_sensor` | `clear` | Presence cleared (motion/presence sensor off) |
| `contact_sensor` | `open` | Contact opened (door, window) |
| `contact_sensor` | `closed` | Contact closed (door, window) |
| `switch` | `on` | Switch turned on |
| `switch` | `off` | Switch turned off |
| `light` | `on` | Light turned on |
| `light` | `off` | Light turned off |
| `light` | `brightness_changed` | Dimmer level changed (implies presence) |
| `media_player` | `playing` | Media started playing |
| `media_player` | `paused` | Media paused |
| `media_player` | `idle` | Media player idle |
| `media_player` | `off` | Media player off |
| `media_player` | `volume_changed` | Volume adjusted (implies presence) |
| `person` | `home` | Person/device tracker detected home |
| `person` | `away` | Person/device tracker detected away |
| `power_sensor` | `consuming` | Power consumption above threshold |
| `power_sensor` | `idle` | Power consumption below threshold |

#### Rule Trigger Format

Rules reference triggers using the sensor type and event:

```json
{
  "sensor_type": "contact_sensor",
  "event": "closed",
  "action": "maintain"
}
```

Or in flattened format:
```json
{
  "trigger": "contact_sensor.closed",
  "action": "maintain"
}
```

### 3.2. Actions (The "Then")

The effect on the Location's state machine.

| Action | Description | Parameter Logic |
|--------|-------------|-----------------|
| `set_occupied` | Transitions state to Occupied. Resets the countdown timer. | **Timeout (min)**: Sets the countdown duration. If `null`, uses Room Default. |
| `set_clear` | Transitions state to Clear (usually after a delay). | **Delay (min)**: Waits this long before clearing. If `0`, clears immediately. |
| `maintain` | Forces Occupied state as long as the device is in this state. | None |

### 3.3. Parameters

- **Timeout**: The "Damping" time. How long the room stays occupied after this event.
- **Delay**: A "Grace Period" before clearing.

---

## 4. Common Logic Patterns (Recipes)

### 4.1. Standard Motion (The Default)

**Device**: PIR Sensor

**Rule 1**: 
- When: `motion` 
- Then: `set_occupied` 
- Param: Default

### 4.2. "Wasp in a Box" (Strict)

Uses two devices to create a latch.

**Device A (Door)**:
- When: `open` → Then: `set_occupied` (Param: 5 min - Entry grace period)
- When: `closed` → Then: `maintain` (Logic: "If occupied + door closed, lock state")

**Device B (Interior Motion)**:
- When: `motion` → Then: `set_occupied` (Param: Default)

### 4.3. Manual Override (Light Switch)

**Device**: Wall Switch

**Rule 1**: 
- When: `on` → Then: `set_occupied` (Param: 60 min)
- Assumes if you turned the light on, you are there.

**Rule 2**: 
- When: `off` → Then: `set_clear` (Param: 2 min)
- Assumes if you turned the light off, you left.

### 4.4. Media Mode

**Device**: Apple TV / Plex

**Rule 1**: 
- When: `playing` → Then: `maintain`
- Prevents lights from turning off during a movie even if no motion is detected.

---

## 5. Configuration Schema

This schema represents the data structure expected by the Occupancy Module for a given Location.

```json
{
  "module": "occupancy",
  "enabled": true,
  "config": {
    "defaultTimeout": 10,
    "waspInABox": true, 
    "devices": [
      {
        "entity_id": "binary_sensor.kitchen_motion",
        "rules": [
          {
            "trigger": "motion",
            "action": "set_occupied",
            "parameter": null
          }
        ]
      },
      {
        "entity_id": "light.kitchen_main",
        "rules": [
          {
            "trigger": "on",
            "action": "set_occupied",
            "parameter": 60
          },
          {
            "trigger": "off",
            "action": "set_clear",
            "parameter": 2
          }
        ]
      }
    ]
  }
}
```

---

## 6. Inheritance & Hierarchy

- **Default Timeout**: If a Location does not specify a `defaultTimeout`, it traverses up the tree (Room → Floor → Root) to find the nearest value.

- **Wasp Logic**: The `waspInABox` boolean is a strategy flag. If enabled on a Parent, children can inherit it, but it requires specific device rules (Entry/Motion) to actually function in a specific room.

---

## 7. Comparison with Current Implementation

### Current Approach (Category-Based)

The current implementation uses:
- **Event Types**: `MOMENTARY`, `HOLD_START`, `HOLD_END`, `MANUAL`, `LOCK_CHANGE`
- **Categories**: `motion`, `presence`, `door`, `media` (used for timeout lookup)
- **Hardcoded Translation**: Entity ID pattern matching in `_determine_event_type()`

**Example Current Config**:
```python
{
  "timeouts": {
    "motion": 300,  # seconds
    "presence": 600,
    "door": 120,
    "media": 300
  }
}
```

**Translation Logic**:
```python
if "motion" in entity_id.lower():
    if old_state == "off" and new_state == "on":
        return EventType.MOMENTARY, "motion"
```

### Proposed Approach (Rule-Based)

- **Triggers**: User-defined event patterns (`motion`, `on`, `off`, `open`, `closed`)
- **Actions**: Explicit state machine operations (`set_occupied`, `set_clear`, `maintain`)
- **Per-Device Rules**: Each device can have multiple rules with different behaviors

**Key Advantages**:
1. ✅ **Flexibility**: Same device can behave differently for different events
2. ✅ **User Control**: No hardcoded logic, fully configurable
3. ✅ **Clarity**: Rules are explicit and self-documenting
4. ✅ **Extensibility**: Easy to add new triggers/actions without code changes

**Key Challenges**:
1. ⚠️ **Migration**: Need to migrate existing category-based configs
2. ⚠️ **Complexity**: More configuration for users
3. ⚠️ **Validation**: Need to ensure rules don't conflict

---

## 8. Gaps & Open Questions

> **Note**: All critical gaps have been resolved. See [occupancy-rule-engine-decisions.md](./occupancy-rule-engine-decisions.md) for complete decisions.

### 8.1. Event Translation ✅ RESOLVED

**Decision**: Hybrid auto-detection with explicit override

**Implementation**: 
- Auto-detect trigger from entity domain/type and state change
- Allow explicit `trigger_mapping` in device config for edge cases
- See [Decisions Document](./occupancy-rule-engine-decisions.md#gap-1-event-translation-mechanism--resolved) for complete mapping table

### 8.2. Action Semantics ✅ RESOLVED

**Decision**: Explicit state machine with holds

**Implementation**:
- `set_occupied(timeout)`: Sets occupied, resets timer, clears holds
- `set_clear(delay)`: Grace period if delay>0, immediate clear if delay=0
- `maintain(device_id)`: Creates hold, sets occupied, clears timer (no timeout while maintained)
- See [Decisions Document](./occupancy-rule-engine-decisions.md#gap-2-state-machine-semantics--resolved) for complete state machine

### 8.3. Rule Priority & Conflict Resolution ✅ RESOLVED

**Decision**: Validation + Order-Based Resolution

**Implementation**:
- Validate rules at config time to prevent conflicts
- If multiple rules match: Use rule order (first wins)
- Action priority as tiebreaker: `maintain` > `set_occupied` > `set_clear`
- See [Decisions Document](./occupancy-rule-engine-decisions.md#gap-3-rule-conflict-resolution--resolved) for validation logic

### 8.4. State Machine Details

**Missing from Spec**:
- How does `set_clear` with delay work? (Does it set a separate timer?)
- What happens if `set_occupied` is called while already occupied? (Reset timer?)
- How does `maintain` interact with existing timers?

**Proposed State Machine**:
```
State: {occupied: bool, timer: datetime | null, holds: Set[str]}

Actions:
- set_occupied(timeout): 
  - Set occupied = true
  - Set timer = now + timeout
  - Clear holds (if not maintain-based)
  
- set_clear(delay):
  - If delay > 0: Set timer = now + delay, keep occupied = true
  - If delay == 0: Set occupied = false, clear timer, clear holds
  
- maintain(device_id):
  - Add device_id to holds
  - Set occupied = true
  - Clear timer (no timeout while maintained)
```

### 8.5. Wasp-in-a-Box Implementation ✅ RESOLVED

**Decision**: Location-Level Feature + Device Rules

**Implementation**:
- `waspInABox` is a location-level boolean flag
- Requires door sensor with `open` → `set_occupied` and `closed` → `maintain` rules
- Requires motion sensor with `motion` → `set_occupied` rule
- See [Decisions Document](./occupancy-rule-engine-decisions.md#gap-4-wasp-in-a-box-implementation--resolved) for complete logic flow

### 8.6. Hierarchy & Propagation ✅ RESOLVED

**Decision**: Rules Operate on Target Location, Propagation After

**Implementation**:
- Rules evaluate on the location where device is assigned
- State update happens based on rule action
- Existing hierarchy propagation runs after rule evaluation
- See [Decisions Document](./occupancy-rule-engine-decisions.md#gap-5-hierarchy-interaction--resolved) for behavior details

### 8.7. Configuration Migration ✅ RESOLVED

**Decision**: Auto-Migration with Manual Override

**Implementation**:
- Automatically convert category-based configs to rule-based on first load
- Keep original as backup
- Support both formats during transition period
- See [Decisions Document](./occupancy-rule-engine-decisions.md#gap-6-configuration-migration--resolved) for migration algorithm

### 8.8. UI/UX Considerations

**Missing**: How will users configure rules?

**Needs**:
- Visual rule builder (if-then interface)
- Device selector
- Trigger selector (dropdown)
- Action selector (dropdown)
- Parameter input (number input)
- Rule testing/preview
- Common patterns/recipes (templates)

### 8.9. Performance & Scalability

**Questions**:
- How many rules per location is reasonable?
- Rule evaluation performance (O(n) per event?)
- Caching strategies?

**Proposed**:
- Index rules by device_id for O(1) lookup
- Limit rules per device (e.g., max 10)
- Cache compiled rule evaluators

### 8.10. Error Handling & Validation

**Missing**: What happens when rules are invalid?

**Needs**:
- Schema validation (JSON schema)
- Semantic validation (conflicting rules)
- Runtime error handling (invalid device, missing location)
- Logging/alerting for rule failures

---

## 9. Implementation Considerations

### 9.1. Backward Compatibility

**Challenge**: Current implementation uses category-based timeouts

**Options**:
1. **Breaking Change**: Require migration to rule-based
2. **Dual Mode**: Support both formats
3. **Auto-Migration**: Convert category config to rules on load

**Recommendation**: Option 3 (Auto-Migration) with Option 2 (Dual Mode) as fallback

### 9.2. Integration with Existing Engine

**Current Engine**: Uses `EventType` (MOMENTARY, HOLD_START, etc.) and `category` for timeout lookup

**Proposed**: Rule engine could:
- **Option A**: Replace engine entirely (new implementation)
- **Option B**: Translate rules → EventType/category (adapter layer)
- **Option C**: Extend engine to support both (hybrid)

**Recommendation**: Option B (Adapter) for gradual migration

### 9.3. Testing Strategy

**Needs**:
- Unit tests for rule evaluation
- Integration tests for state machine transitions
- Migration tests (category → rules)
- Performance tests (many rules, many events)

---

## 10. Documentation Gaps

### 10.1. Missing Sections

1. **Event Translation Details**: How platform events → rule triggers
2. **State Machine Diagram**: Visual representation of state transitions
3. **Rule Evaluation Algorithm**: Step-by-step processing logic
4. **Error Scenarios**: What happens when things go wrong
5. **Performance Characteristics**: Expected behavior under load
6. **Migration Guide**: Step-by-step migration from category-based
7. **API Reference**: Programmatic interface for rule management
8. **UI/UX Mockups**: How users will configure rules

### 10.2. Examples Needed

1. **Complex Scenarios**:
   - Multiple devices with overlapping rules
   - Conflicting rules resolution
   - Hierarchy with rules at different levels

2. **Edge Cases**:
   - Device removed while rule active
   - Location deleted with active rules
   - Invalid rule parameters

3. **Real-World Recipes**:
   - Home office (motion + light + computer power)
   - Bathroom (motion + door + exhaust fan)
   - Garage (door + motion + car presence)

---

## 11. Next Steps

### Immediate (Design Phase)

1. ✅ **DONE**: Core rule specification
2. [ ] **TODO**: Define event translation mechanism
3. [ ] **TODO**: Specify state machine in detail
4. [ ] **TODO**: Design rule validation logic
5. [ ] **TODO**: Create migration strategy document

### Short-term (Implementation Phase)

1. [ ] Implement rule engine core
2. [ ] Build event translation layer
3. [ ] Create migration tool
4. [ ] Add validation & error handling
5. [ ] Write comprehensive tests

### Long-term (Polish Phase)

1. [ ] Build UI for rule configuration
2. [ ] Add rule templates/recipes
3. [ ] Performance optimization
4. [ ] Documentation & examples

---

## 12. References

- **Current Implementation**: `src/home_topology/modules/occupancy/`
- **Existing Design**: `docs/modules/occupancy-design.md`
- **Integration Guide**: `docs/integration-guide.md`
- **Engine Specification**: `occypancy_manager/SPEC.md`

---

**Status**: Design Complete - All Critical Gaps Resolved  
**Last Updated**: 2025.01.XX  
**Decisions Document**: [occupancy-rule-engine-decisions.md](./occupancy-rule-engine-decisions.md)

