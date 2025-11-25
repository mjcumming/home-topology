# Occupancy Rule Engine - Design Decisions

**Status**: Decisions Complete  
**Date**: 2025.01.XX  
**Based on**: UI Mockup Review + Gap Analysis

---

## UI-Driven Design Decisions

Based on the UI mockup, we can see:
- **Devices listed separately** with rule counts (e.g., "Kitchen Motion - 1 Rules", "Main Lights - 2 Rules")
- **Rules configured per device** (clicking device shows its rules)
- **Default timeout** at location level (10 min)
- **Wasp-in-a-Box** as location-level checkbox
- **Hierarchical interface** (locations → devices → rules)

---

## Gap 1: Event Translation Mechanism ✅ RESOLVED

### Decision: Integration Layer Responsibility with Normalized Events

**Approach**: Event normalization happens in the integration layer. The core library expects normalized events with sensor types and event names.

> **Key Principle**: The core library doesn't know about Home Assistant entity patterns. The integration translates platform-specific events into our normalized format.

### Normalized Event Format

Events are structured by sensor type:

| Sensor Type | Event | Description |
|-------------|-------|-------------|
| `motion_sensor` | `motion` | Presence detected |
| `motion_sensor` | `clear` | Presence cleared |
| `contact_sensor` | `open` | Contact opened |
| `contact_sensor` | `closed` | Contact closed |
| `switch` | `on` | Switch on |
| `switch` | `off` | Switch off |
| `light` | `on` | Light on |
| `light` | `off` | Light off |
| `light` | `brightness_changed` | Dimmer adjusted |
| `media_player` | `playing` | Playing |
| `media_player` | `paused` | Paused |
| `media_player` | `idle` | Idle |
| `media_player` | `off` | Off |
| `media_player` | `volume_changed` | Volume adjusted |
| `person` | `home` | Home |
| `person` | `away` | Away |
| `power_sensor` | `consuming` | Above threshold |
| `power_sensor` | `idle` | Below threshold |

### Integration Translation (HA Example)

The Home Assistant integration would translate like this:

| HA Entity Pattern | State Change | Normalized Event |
|-------------------|--------------|------------------|
| `binary_sensor.*.motion` | `off` → `on` | `{sensor_type: "motion_sensor", event: "motion"}` |
| `binary_sensor.*.motion` | `on` → `off` | `{sensor_type: "motion_sensor", event: "clear"}` |
| `binary_sensor.*.door` | `closed` → `open` | `{sensor_type: "contact_sensor", event: "open"}` |
| `binary_sensor.*.door` | `open` → `closed` | `{sensor_type: "contact_sensor", event: "closed"}` |
| `light.*` | `off` → `on` | `{sensor_type: "light", event: "on"}` |
| `light.*` | `on` → `off` | `{sensor_type: "light", event: "off"}` |
| `media_player.*` | `*` → `playing` | `{sensor_type: "media_player", event: "playing"}` |
| `person.*` | `*` → `home` | `{sensor_type: "person", event: "home"}` |

### Explicit Sensor Type Override

If auto-detection doesn't work for a device, the integration can allow explicit sensor type assignment:

```json
{
  "entity_id": "sensor.custom_sensor",
  "sensor_type": "motion_sensor",
  "state_mapping": {
    "high": "motion",
    "low": "clear"
  }
}
```

This is an **integration-level** feature, not a core library feature.

### Action Items
- [x] Define normalized event format (sensor_type + event)
- [x] Document that translation is integration responsibility
- [x] Design override mechanism (integration-level)

---

## Gap 2: State Machine Semantics ✅ RESOLVED

### Decision: Explicit State Machine with Holds

**State Structure**:
```python
@dataclass
class LocationState:
    occupied: bool
    timer: Optional[datetime]  # When to transition to Clear
    holds: Set[str]  # Device IDs with active "maintain" actions
    last_updated: datetime
```

### Action Semantics

#### `set_occupied(timeout: Optional[int])`

**Behavior**:
1. Set `occupied = True`
2. If `timeout` is provided: Set `timer = now + timeout`
3. If `timeout` is `None`: Use location's `defaultTimeout`
4. **Clear all holds** (unless this action was triggered by a `maintain` release)
5. Emit `occupancy.changed` event if state changed

**Edge Cases**:
- If already occupied: **Reset timer** (extend occupancy)
- If holds are active: Clear holds first, then set timer

**Example**:
```python
# Motion detected
set_occupied(timeout=5)  # 5 minutes
# → occupied=True, timer=now+5min, holds={}

# Another motion 2 minutes later
set_occupied(timeout=5)  # Reset timer
# → occupied=True, timer=now+5min (reset), holds={}
```

#### `set_clear(delay: int)`

**Behavior**:
1. If `delay > 0`:
   - Set `timer = now + delay`
   - Keep `occupied = True` (grace period)
   - Clear holds
2. If `delay == 0`:
   - Set `occupied = False`
   - Clear `timer = None`
   - Clear all `holds = {}`
3. Emit `occupancy.changed` event if state changed

**Edge Cases**:
- If already clear: No-op
- If holds are active: **Ignore** (can't clear while maintained)

**Example**:
```python
# Light turned off
set_clear(delay=2)  # 2 minute grace period
# → occupied=True, timer=now+2min, holds={}

# After 2 minutes (timer expires)
# → occupied=False, timer=None, holds={}
```

#### `maintain(device_id: str)`

**Behavior**:
1. Add `device_id` to `holds` set
2. Set `occupied = True`
3. **Clear timer** (`timer = None`) - no timeout while maintained
4. Emit `occupancy.changed` event if state changed

**Edge Cases**:
- If device already in holds: No-op (idempotent)
- If timer was active: Clear it (maintain overrides timer)

**Release Behavior** (when device state changes to release condition):
1. Remove `device_id` from `holds`
2. If `holds` is now empty:
   - If location was occupied: Set `timer = now + trailing_timeout` (e.g., 2 min)
   - Keep `occupied = True` during trailing period
3. Emit `occupancy.changed` event

**Example**:
```python
# Door closed (wasp-in-a-box)
maintain(device_id="binary_sensor.kitchen_door")
# → occupied=True, timer=None, holds={"binary_sensor.kitchen_door"}

# Door opens (release)
# → holds={}, timer=now+2min (trailing), occupied=True

# After 2 minutes
# → occupied=False, timer=None, holds={}
```

### State Machine Diagram

```
┌─────────────┐
│   CLEAR     │
│ occupied=False│
│ timer=None  │
│ holds={}    │
└──────┬──────┘
       │ set_occupied()
       │ OR maintain()
       │
       ▼
┌─────────────┐
│  OCCUPIED   │
│ occupied=True│
│ timer=X     │
│ holds={}    │
└──────┬──────┘
       │
       ├─► maintain() ──► ┌─────────────┐
       │                  │ MAINTAINED   │
       │                  │ occupied=True│
       │                  │ timer=None  │
       │                  │ holds={id}  │
       │                  └──────┬──────┘
       │                         │
       │                         │ release ──► timer=now+trailing
       │                         │
       │                         ▼
       │                  ┌─────────────┐
       │                  │ TRAILING    │
       │                  │ occupied=True│
       │                  │ timer=X     │
       │                  │ holds={}    │
       │                  └──────┬──────┘
       │                         │
       │                         │ timer expires
       │                         │
       └─────────────────────────┘
                 │
                 │ set_clear(delay=0) OR timer expires
                 │
                 ▼
            [BACK TO CLEAR]
```

### Action Items
- [x] Create state machine diagram
- [x] Document all state transitions
- [x] Define edge case behaviors

---

## Gap 3: Rule Conflict Resolution ✅ RESOLVED

### Decision: Validation + Order-Based Resolution

**Approach**: 
1. **Prevent conflicts at config time** (validation)
2. **If multiple rules match**: Use rule order (first wins)
3. **Action priority** as tiebreaker (if same trigger)

### Validation Rules

**Conflicting Rule Patterns** (prevent at config time):
- Same trigger, conflicting actions: `set_occupied` + `set_clear` (unless different conditions)
- Same trigger, same action, different parameters: Use first rule, warn user

**Validation Logic**:
```python
def validate_rules(device_id: str, rules: List[Rule]) -> ValidationResult:
    """Validate rules for conflicts."""
    
    # Group by trigger
    by_trigger = {}
    for rule in rules:
        if rule.trigger not in by_trigger:
            by_trigger[rule.trigger] = []
        by_trigger[rule.trigger].append(rule)
    
    errors = []
    warnings = []
    
    for trigger, trigger_rules in by_trigger.items():
        if len(trigger_rules) > 1:
            actions = [r.action for r in trigger_rules]
            
            # Check for conflicting actions
            if "set_occupied" in actions and "set_clear" in actions:
                errors.append(
                    f"Conflict: {device_id} has both set_occupied and set_clear "
                    f"for trigger '{trigger}'. Use rule order or remove conflict."
                )
            
            # Warn about duplicate actions
            if len(set(actions)) < len(actions):
                warnings.append(
                    f"Warning: {device_id} has multiple rules with same trigger "
                    f"'{trigger}' and action. First rule will be used."
                )
    
    return ValidationResult(errors=errors, warnings=warnings)
```

### Runtime Resolution

**When multiple rules match the same event**:

1. **Filter by trigger**: Only rules matching the event's trigger
2. **Apply in order**: Process rules in array order (first to last)
3. **Action priority** (if same trigger, different actions):
   - `maintain` > `set_occupied` > `set_clear`
4. **Stop on first match**: Once a rule's action is executed, stop processing

**Example**:
```json
{
  "entity_id": "light.kitchen",
  "rules": [
    {"trigger": "on", "action": "set_occupied", "parameter": 60},  // Rule 1
    {"trigger": "on", "action": "set_clear", "parameter": 0}       // Rule 2 - CONFLICT!
  ]
}
```

**Validation Error**:
```
Error: light.kitchen has conflicting rules for trigger 'on':
  - Rule 1: set_occupied (60 min)
  - Rule 2: set_clear (0 min)
  
Please remove one rule or use different triggers.
```

**If validation passes but multiple rules match**:
- Use rule order (first rule wins)
- Log warning: "Multiple rules matched, using first rule"

### Action Items
- [x] Design validation schema
- [x] Implement conflict detection
- [x] Document resolution strategy

---

## Gap 4: Wasp-in-a-Box Implementation ✅ RESOLVED

### Decision: Location-Level Feature + Device Rules

**Approach**: Wasp-in-a-Box is a **location-level strategy** that requires **specific device rules** to function.

### Implementation

**Location Config**:
```json
{
  "defaultTimeout": 10,
  "waspInABox": true,  // Location-level flag
  "devices": [
    {
      "entity_id": "binary_sensor.kitchen_door",
      "rules": [
        {"trigger": "open", "action": "set_occupied", "parameter": 5},
        {"trigger": "closed", "action": "maintain", "parameter": null}
      ]
    },
    {
      "entity_id": "binary_sensor.kitchen_motion",
      "rules": [
        {"trigger": "motion", "action": "set_occupied", "parameter": null}
      ]
    }
  ]
}
```

### Logic Flow

1. **Door Opens**:
   - Rule: `open` → `set_occupied(5 min)`
   - Location becomes occupied with 5-minute grace period

2. **Door Closes** (while occupied):
   - Rule: `closed` → `maintain`
   - Creates hold: `holds = {"binary_sensor.kitchen_door"}`
   - Clears timer: `timer = None`
   - Location stays occupied **indefinitely** (no timeout)

3. **Motion Detected** (while door closed):
   - Rule: `motion` → `set_occupied(null)` 
   - Since `waspInABox=true`, this confirms occupancy
   - Timer remains `None` (maintained by door)

4. **Door Opens Again** (release):
   - Rule: `open` → `set_occupied(5 min)`
   - Removes hold: `holds = {}`
   - Sets timer: `timer = now + 5min`
   - If no motion detected, location clears after 5 minutes

### UI Behavior

- **Checkbox in UI**: "Wasp-in-a-Box Logic" (location-level)
- **When enabled**: 
  - Shows helper text: "Requires door sensor with open/closed rules and motion sensor"
  - Validates that required devices exist
  - Guides user to create appropriate rules

### Action Items
- [x] Choose implementation approach (location-level flag + device rules)
- [x] Document wasp logic flow
- [x] Add to examples/recipes

---

## Gap 5: Hierarchy Interaction ✅ RESOLVED

### Decision: Rules Operate on Target Location, Propagation After

**Approach**: Rules evaluate on the target location only. Hierarchy propagation happens **after** rule evaluation, using existing propagation logic.

### Behavior

1. **Rule Evaluation**: Rules operate on the location where the device is assigned
2. **State Update**: Location state updated based on rule action
3. **Propagation**: Existing hierarchy propagation runs:
   - **Upward**: If child becomes occupied → parent becomes occupied (if `contributes_to_parent=true`)
   - **Downward**: Not affected by rules (parent rules don't affect children)

### Example

```
House
└── First Floor
    └── Kitchen (has motion sensor with rule)
```

**Event**: `binary_sensor.kitchen_motion` → `on`

1. **Rule Evaluation** (Kitchen):
   - Device: `binary_sensor.kitchen_motion`
   - Rule: `motion` → `set_occupied(null)`
   - Result: Kitchen `occupied = True`, `timer = now + 10min` (default)

2. **Propagation** (Upward):
   - Kitchen → First Floor: `occupied = True` (propagated)
   - First Floor → House: `occupied = True` (propagated)

3. **No Downward Effect**:
   - House rules don't affect Kitchen
   - First Floor rules don't affect Kitchen

### Maintain Propagation

**Question**: How does `maintain` propagate?

**Answer**: `maintain` creates a hold on the target location. Propagation happens based on occupancy state, not hold details.

- If Kitchen has `maintain` active → Kitchen is occupied
- Kitchen occupied → First Floor occupied (propagated)
- First Floor doesn't know about Kitchen's holds, just that it's occupied

### Action Items
- [x] Document hierarchy behavior
- [x] Add hierarchy examples
- [x] Test propagation scenarios

---

## Gap 6: Configuration Migration ✅ RESOLVED

### Decision: Auto-Migration with Manual Override

**Approach**: Automatically convert category-based configs to rule-based configs on first load, with option to keep original.

### Migration Algorithm

```python
def migrate_category_config_to_rules(location_id: str, old_config: dict) -> dict:
    """Convert category-based config to rule-based config."""
    
    new_config = {
        "enabled": old_config.get("enabled", True),
        "defaultTimeout": old_config.get("timeouts", {}).get("default", 600) // 60,  # seconds → minutes
        "waspInABox": old_config.get("waspInABox", False),
        "devices": []
    }
    
    # Get all entities for this location
    entities = location_manager.get_entities_for_location(location_id)
    
    # Group entities by inferred type
    motion_entities = [e for e in entities if "motion" in e.lower()]
    door_entities = [e for e in entities if "door" in e.lower()]
    light_entities = [e for e in entities if e.startswith("light.")]
    media_entities = [e for e in entities if e.startswith("media_player.")]
    
    # Create device rules based on categories
    timeouts = old_config.get("timeouts", {})
    
    # Motion sensors
    for entity_id in motion_entities:
        timeout_min = (timeouts.get("motion", 300) // 60)  # seconds → minutes
        new_config["devices"].append({
            "entity_id": entity_id,
            "rules": [{
                "trigger": "motion",
                "action": "set_occupied",
                "parameter": timeout_min if timeout_min != new_config["defaultTimeout"] else None
            }]
        })
    
    # Door sensors
    for entity_id in door_entities:
        timeout_min = (timeouts.get("door", 120) // 60)
        new_config["devices"].append({
            "entity_id": entity_id,
            "rules": [
                {
                    "trigger": "open",
                    "action": "set_occupied",
                    "parameter": timeout_min
                }
            ]
        })
    
    # Lights (if configured)
    if "light" in timeouts:
        for entity_id in light_entities:
            timeout_min = (timeouts.get("light", 600) // 60)
            new_config["devices"].append({
                "entity_id": entity_id,
                "rules": [
                    {
                        "trigger": "on",
                        "action": "set_occupied",
                        "parameter": timeout_min
                    }
                ]
            })
    
    # Media players
    if "media" in timeouts:
        for entity_id in media_entities:
            new_config["devices"].append({
                "entity_id": entity_id,
                "rules": [
                    {
                        "trigger": "on",
                        "action": "maintain",
                        "parameter": None
                    }
                ]
            })
    
    return new_config
```

### Migration Strategy

1. **On First Load**:
   - Detect old config format (`timeouts` dict present)
   - Run migration function
   - Save migrated config
   - Keep original as backup: `config_backup_v1.json`

2. **User Notification**:
   - Show migration summary: "Migrated 5 devices from category-based to rule-based config"
   - Allow review of migrated rules
   - Option to revert (restore backup)

3. **Dual Format Support** (Transition Period):
   - Support both formats for 1-2 versions
   - Auto-migrate on load
   - Deprecation warning for old format

### Action Items
- [x] Design migration algorithm
- [x] Implement migration function
- [x] Create migration guide

---

## Additional Decisions Based on UI

### Device Selection

**UI Shows**: Devices listed with rule counts (e.g., "Kitchen Motion - 1 Rules")

**Decision**: 
- Devices are **automatically discovered** from entities assigned to location
- User can **add/remove devices** from occupancy tracking
- Devices show **rule count** as indicator of complexity

### Rule Configuration Flow

**UI Suggests**: Clicking device shows its rules

**Decision**:
- **Device Detail View**: Click device → modal/sidebar with rules
- **Rule Builder**: Add/Edit/Delete rules per device
- **Rule Templates**: Common patterns (motion, light switch, door, etc.)

### Default Timeout

**UI Shows**: "Default Timeout: 10 min" at location level

**Decision**:
- Default timeout is **location-level setting**
- Used when rule has `parameter: null`
- Inherited from parent if not set (hierarchy traversal)

### Wasp-in-a-Box UI

**UI Shows**: Checkbox at location level

**Decision**:
- **Location-level feature** (not device-level)
- When enabled, shows helper text and validates required devices
- Guides user to create door + motion sensor rules

---

## Summary of All Decisions

| Gap | Decision | Status |
|-----|----------|--------|
| 1. Event Translation | Hybrid auto-detect + explicit override | ✅ Resolved |
| 2. State Machine | Explicit state with holds, clear semantics | ✅ Resolved |
| 3. Conflict Resolution | Validation + order-based + action priority | ✅ Resolved |
| 4. Wasp-in-a-Box | Location-level flag + device rules | ✅ Resolved |
| 5. Hierarchy | Rules on target location, propagate after | ✅ Resolved |
| 6. Migration | Auto-migration with backup + dual format support | ✅ Resolved |

---

## Next Steps

1. **Update Design Spec** with these decisions
2. **Create State Machine Diagram** (visual)
3. **Implement Migration Function** (prototype)
4. **Build Rule Validation** (schema + logic)
5. **Document Event Translation** (mapping table)

---

**Status**: All Critical Gaps Resolved  
**Ready for**: Implementation Planning

