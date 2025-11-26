# Occupancy Module Design

> Core occupancy tracking for home-topology

**Status**: v2.3 Final  
**Version**: 2.3  
**Last Updated**: 2025-11-26

---

## 1. Overview

The **OccupancyModule** tracks occupancy state per location in the home topology. It provides a binary occupied/vacant state with hierarchical propagation.

### Design Principles

1. **Simple**: Binary state (occupied/vacant), no weighted confidence
2. **Platform-agnostic**: Core library has no knowledge of platform-specific details.
3. **Integration-driven**: Event classification happens in the integration layer
4. **Testable**: Time-agnostic design, all time passed as parameters
5. **Hierarchical**: Automatic propagation up the location tree

---

## 2. Responsibilities

### Core Library (This Module)

- Track occupancy state per location
- Process occupancy events
- Manage timeout timers
- Handle hierarchical propagation
- Persist and restore state
- Emit `occupancy.changed` events

### Integration Layer

- Map platform entities to locations
- Classify events (motion → TRIGGER, presence → HOLD, etc.)
- Determine appropriate timeouts
- Send well-formed events to the core library

---

## 3. Events and Commands

The occupancy module distinguishes between **Events** (from device state changes) and **Commands** (imperative actions from automations/UI).

### Events (From Device Mappings)

Events are signals from devices, processed through the integration's device mapping configuration:

| Event | Behavior |
|-------|----------|
| `TRIGGER` | Activity detected. Sets occupied, starts/extends timer. |
| `HOLD` | Presence detected. Sets occupied indefinitely. |
| `RELEASE` | Presence cleared. Releases hold, uses existing timer or starts trailing timer. |

### Commands (From Automations/UI)

Commands are imperative actions, called directly by automations, services, or UI:

| Command | Behavior |
|---------|----------|
| `VACATE` | Force vacant. Immediately clears occupancy (timers and holds). |
| `LOCK` | Add source to `locked_by` set. State frozen when set non-empty. |
| `UNLOCK` | Remove source from `locked_by` set. Unfrozen when empty. |
| `UNLOCK_ALL` | Clear `locked_by` set entirely. Force unlock. |

### API Methods

```python
class OccupancyModule:
    # EVENTS (from device mappings via integration)
    def trigger(self, location_id, source_id, timeout=None): ...
    def hold(self, location_id, source_id): ...
    def release(self, location_id, source_id, trailing_timeout=None): ...
    
    # COMMANDS (from automations/UI)
    def vacate(self, location_id): ...
    def lock(self, location_id, source_id): ...
    def unlock(self, location_id, source_id): ...
    def unlock_all(self, location_id): ...
```

### Why Separate?

1. **Conceptual clarity**: Events are "things that happened", commands are "do this now"
2. **Different origins**: Events from device mappings, commands from automations/UI
3. **API design**: Commands have simpler signatures (no timeout/source for vacate)

---

## 4. Per-Location State

Each location maintains:

```python
@dataclass(frozen=True)
class LocationRuntimeState:
    is_occupied: bool = False               # Currently occupied?
    occupied_until: datetime | None = None  # Timer expiration (None = indefinite or vacant)
    timer_remaining: timedelta | None = None  # Stored when locked (for resume)
    active_holds: set[str] = field(...)     # Source IDs with active holds
    locked_by: set[str] = field(...)        # WHO locked this (empty = unlocked)
```

### State Semantics

| Condition | Meaning |
|-----------|---------|
| `is_occupied=True`, `occupied_until` set | Occupied with timer |
| `is_occupied=True`, `occupied_until=None`, holds active | Occupied indefinitely |
| `is_occupied=False` | Vacant |
| `len(locked_by) > 0` | State frozen, events ignored |
| `timer_remaining` set | Timer was paused by lock |

### Lock Tracking

The `locked_by` set tracks WHO has locked this location:

```python
# Check if locked
is_locked = len(state.locked_by) > 0

# See who locked it
print(state.locked_by)  # {"automation_sleep_mode", "automation_dnd"}
```

### Timer Suspension

When locked, the timer is suspended (not cleared):

```python
# Timer remaining is stored when locked
if state.timer_remaining is not None:
    print(f"Timer paused with {state.timer_remaining} remaining")
```

---

## 5. Location Configuration

Minimal per-location configuration:

```python
{
    "default_timeout": 300,           # Seconds for TRIGGER events
    "hold_release_timeout": 120,      # Trailing seconds after RELEASE
    "occupancy_strategy": "independent",  # or "follow_parent"
    "contributes_to_parent": True,    # Propagate to parent?
}
```

### Configuration Fields

| Field | Purpose |
|-------|---------|
| `default_timeout` | Timer duration for TRIGGER events (if not specified in event) |
| `hold_release_timeout` | Timer duration after RELEASE (hold ends) |
| `occupancy_strategy` | INDEPENDENT or FOLLOW_PARENT |
| `contributes_to_parent` | Whether this location's occupancy propagates up |

---

## 6. Event Parameters

Events are sent via method calls, not a unified event object. Each event method has specific parameters:

### TRIGGER

```python
def trigger(
    self,
    location_id: str,      # Target location
    source_id: str,        # Device that triggered
    timeout: int | None,   # Override location default (seconds)
) -> None
```

### HOLD

```python
def hold(
    self,
    location_id: str,      # Target location
    source_id: str,        # Device that triggered
) -> None
```

### RELEASE

```python
def release(
    self,
    location_id: str,           # Target location
    source_id: str,             # Device that triggered
    trailing_timeout: int | None,  # Override location default (seconds)
) -> None
```

### Timeout Logic

1. If `timeout` parameter is set → use it
2. Else → use `location.default_timeout` (for TRIGGER) or `hold_release_timeout` (for RELEASE)

---

## 7. State Transitions

### TRIGGER Event

```
Vacant → Occupied (timer starts)
Occupied → Occupied (timer extends if new time > current)
During Hold → Timer extended (preserved for after hold ends)
```

TRIGGER always extends the timer, even during active holds. This ensures motion sensors contribute even when presence sensors are active.

### HOLD Event

```
Any → Occupied (indefinitely, hold registered)
Timer → Preserved (not cleared)
```

Holds do NOT clear timers. Timers continue to be tracked and are used when all holds release.

### RELEASE Event

```
With active holds → Release one hold
  If no holds remain:
    If occupied_until > now → Keep existing timer
    Else → Start trailing timer
With no holds → Ignored
```

When the last hold releases, existing TRIGGER timers take precedence over trailing timers.

### VACATE Command

```
Any → Vacant (immediate, clears all timers and holds)
Locked → Ignored (cannot vacate while locked)
```

### LOCK Command

```
Any → State frozen
Timer active → Timer suspended (remaining time stored)
Events → Ignored until unlocked
```

When locked, the timer is **suspended** (not cleared). The remaining time is stored in `timer_remaining`.

### UNLOCK Command

```
Locked → Remove source from locked_by
If locked_by empty:
  Timer was suspended → Resume timer (occupied_until = now + timer_remaining)
  No suspended timer → State unfrozen, resume normal processing
```

When unlocked, the timer **resumes** from where it was suspended.

---

## 8. Hierarchical Propagation

### Upward Propagation (Child → Parent)

When a child location becomes occupied, the parent automatically becomes occupied:

```
Kitchen occupied → Main Floor occupied → House occupied
```

**Rules**:
- Only propagates if `contributes_to_parent = True`
- Parent timer extends to match child
- Parent becomes vacant only when ALL children are vacant

### FOLLOW_PARENT Strategy

Locations can follow their parent's state:

```python
occupancy_strategy: "follow_parent"
```

**Behavior**: Location mirrors parent's occupied state, ignores direct events.

---

## 9. Lock State (State Freeze)

Lock freezes the current occupancy state. Multiple sources can lock independently.

### Lock Behavior

```
LOCK(source="vacation_mode") → locked_by = {"vacation_mode"}
LOCK(source="cleaning_mode") → locked_by = {"vacation_mode", "cleaning_mode"}
UNLOCK(source="vacation_mode") → locked_by = {"cleaning_mode"}  (still locked!)
UNLOCK(source="cleaning_mode") → locked_by = {}  (unlocked)
UNLOCK_ALL → locked_by = {}  (force unlock)
```

### Timer Suspension

When locked with an active timer, the timer is **suspended**, not cleared:

```
T+0:00  TRIGGER(10min)      → occupied_until = T+10:00
T+3:00  LOCK                → timer_remaining = 7min, occupied_until = None
T+8:00  UNLOCK              → occupied_until = T+15:00 (7min from now)
T+15:00 Timer expires       → vacant
```

This ensures the lock truly "freezes" time - users get back the time they had left.

### While Locked

- Occupancy events (TRIGGER, HOLD, RELEASE) are ignored
- Commands (VACATE) are ignored
- Only UNLOCK and UNLOCK_ALL commands are processed
- Current state (occupied/vacant) is preserved
- Timer is suspended (remaining time stored)

### No Lock Propagation

- Locks are local to each location
- No auto-propagate up or down the hierarchy
- Integration can send LOCK to multiple locations if cascade desired

### Use Cases

- **Party mode**: Keep lights on regardless of motion timeout
- **Vacation mode**: Force all locations vacant, ignore sensors
- **Cleaning mode**: Prevent state changes during maintenance
- **Sleep mode**: Lock bedroom as occupied overnight
- **Manual override**: User wants explicit control

---

## 10. Event Emission

Module emits `occupancy.changed` when state changes:

```python
Event(
    type="occupancy.changed",
    source="occupancy",
    location_id="kitchen",
    payload={
        "occupied": True,
        "previous_occupied": False,
        "reason": "trigger:binary_sensor.kitchen_motion",
        "occupied_until": "2025-11-26T15:30:00Z",
        "active_holds": [],
        "locked_by": [],
    },
    timestamp=datetime.now(UTC),
)
```

### Payload Fields

| Field | Type | Description |
|-------|------|-------------|
| `occupied` | bool | Current occupancy state |
| `previous_occupied` | bool | Previous occupancy state |
| `reason` | str | What caused the change (e.g., "trigger:sensor_id") |
| `occupied_until` | str \| None | ISO timestamp when timer expires, or None |
| `active_holds` | list[str] | Source IDs currently holding |
| `locked_by` | list[str] | Source IDs currently locking |

---

## 11. Integration Examples

### Motion Sensor (TRIGGER Event)

```python
# Motion detected - integration calls trigger()
module.trigger(
    location_id="kitchen",
    source_id="binary_sensor.kitchen_motion",
    timeout=300,  # 5 minutes
)
```

### Presence Sensor (HOLD/RELEASE Events)

```python
# Presence detected - integration calls hold()
module.hold(
    location_id="office",
    source_id="binary_sensor.office_presence",
)

# Presence cleared - integration calls release()
module.release(
    location_id="office",
    source_id="binary_sensor.office_presence",
    trailing_timeout=120,  # 2 min trailing
)
```

### Light Switch (VACATE Command)

```python
# Light turned off = room vacant - integration calls vacate()
module.vacate(location_id="bedroom")
```

### Lock/Unlock Commands

```python
# Sleep mode automation locks bedroom as occupied
module.lock(location_id="bedroom", source_id="automation_sleep_mode")
# locked_by = {"automation_sleep_mode"}

# Another automation also needs it locked
module.lock(location_id="bedroom", source_id="automation_do_not_disturb")
# locked_by = {"automation_sleep_mode", "automation_do_not_disturb"}

# Sleep mode ends - still locked by do_not_disturb!
module.unlock(location_id="bedroom", source_id="automation_sleep_mode")
# locked_by = {"automation_do_not_disturb"}

# Force unlock everything (user override)
module.unlock_all(location_id="bedroom")
# locked_by = {}
```

### Combined Scenario: Presence + Motion

Demonstrates how timers and holds coexist:

```python
# Motion detected first
module.trigger("office", "motion_sensor", timeout=600)  # 10 min
# occupied_until = now + 10 min

# Presence sensor activates (user at desk)
module.hold("office", "presence_sensor")
# occupied indefinitely, but timer preserved at now + 10 min

# Motion in corner (presence doesn't see)
module.trigger("office", "motion_sensor", timeout=600)  # extends timer
# timer now at now + 10 min (extended)

# Presence clears (user left desk area)
module.release("office", "presence_sensor", trailing_timeout=120)
# existing timer is now + 8 min, which is > trailing 2 min
# so occupied_until = now + 8 min (motion's contribution preserved)
```

---

## 12. Testing Strategy

### Unit Tests

- State transitions for each event type
- Timer behavior (extend, expire)
- Hold logic (multiple holds, release)
- Lock/unlock behavior

### Integration Tests

- Hierarchical propagation
- FOLLOW_PARENT strategy
- State persistence/restore
- Event emission

### Scenario Tests

- "Office work session" (presence hold + motion triggers)
- "Quick bathroom visit" (motion trigger → timeout)
- "State freeze" (lock during events, sleep, vacation)
- "Family at home" (multiple locations, hierarchy)

---

## 13. References

- **Design Decisions**: `occupancy-design-decisions.md`
- **Implementation Status**: `occupancy-implementation-status.md`
- **Integration Guide**: `occupancy-integration.md`

---

**Status**: v2.3 Final ✅  
**Dependencies**: Core kernel (Location, EventBus, LocationManager)

---

## Appendix: v2.3 Changes Summary

| Change | Description |
|--------|-------------|
| Events vs Commands | Separated API into events (trigger/hold/release) and commands (vacate/lock/unlock) |
| Timer Suspension | Timers pause during lock and resume when unlocked |
| Holds + Timers | Timers continue during holds, used when holds release |
| Identity Tracking | Removed `active_occupants` and `occupant_id` (deferred to PresenceModule) |
| State Model | Added `timer_remaining` field for lock suspension |

See `occupancy-design-decisions.md` for full rationale (Decisions 11-14).
