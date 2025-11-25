# Occupancy Module Design

> Core occupancy tracking for home-topology

**Status**: v2.0 Final  
**Version**: 2.0  
**Last Updated**: 2025-01-27

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

## 3. Event Types

Seven event types, all sent by the integration layer:

### Occupancy Events

| Event | Behavior |
|-------|----------|
| `TRIGGER` | Activity detected. Sets occupied, starts/extends timer. |
| `HOLD` | Presence detected. Sets occupied indefinitely (no timer). |
| `RELEASE` | Presence cleared. Releases hold, starts trailing timer. |
| `VACATE` | Force vacant. Immediately clears occupancy. |

### State Control

| Event | Behavior |
|-------|----------|
| `LOCK` | Add source to `locked_by` set. Frozen when set non-empty. |
| `UNLOCK` | Remove source from `locked_by` set. Unlocked when empty. |
| `UNLOCK_ALL` | Clear `locked_by` set entirely. Force unlock. |

### Event Type Enum

```python
class EventType(Enum):
    TRIGGER = "trigger"
    HOLD = "hold"
    RELEASE = "release"
    VACATE = "vacate"
    LOCK = "lock"
    UNLOCK = "unlock"
    UNLOCK_ALL = "unlock_all"
```

---

## 4. Per-Location State

Each location maintains:

```python
@dataclass(frozen=True)
class LocationRuntimeState:
    is_occupied: bool = False              # Currently occupied?
    occupied_until: datetime | None = None  # Timer expiration (None = indefinite)
    active_holds: set[str] = field(...)    # Source IDs with active holds
    active_occupants: set[str] = field(...) # Identity tracking (optional)
    locked_by: set[str] = field(...)       # WHO locked this (empty = unlocked)
```

### State Semantics

| Condition | Meaning |
|-----------|---------|
| `is_occupied=True`, `occupied_until` set | Occupied with timer |
| `is_occupied=True`, `occupied_until=None` | Occupied indefinitely (hold active) |
| `is_occupied=False` | Vacant |
| `len(locked_by) > 0` | State frozen, ignoring events |

### Lock Tracking

The `locked_by` set tracks WHO has locked this location:

```python
# Check if locked
is_locked = len(state.locked_by) > 0

# See who locked it
print(state.locked_by)  # {"automation_sleep_mode", "automation_dnd"}
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

## 6. Occupancy Event

Events sent by the integration layer:

```python
@dataclass(frozen=True)
class OccupancyEvent:
    location_id: str                # Target location
    event_type: EventType           # TRIGGER, HOLD, RELEASE, VACATE, LOCK, UNLOCK
    source_id: str                  # Device/entity that triggered this
    timestamp: datetime             # When it happened
    timeout: int | None = None      # Override location default (seconds)
    occupant_id: str | None = None  # Optional identity tracking
```

### Timeout Logic

1. If `event.timeout` is set → use it
2. Else → use `location.default_timeout` (for TRIGGER) or `hold_release_timeout` (for RELEASE)

---

## 7. State Transitions

### TRIGGER Event

```
Vacant → Occupied (timer starts)
Occupied → Occupied (timer extends if new time > current)
```

### HOLD Event

```
Any → Occupied (indefinitely, hold registered)
```

### RELEASE Event

```
With active holds → Release one hold
  If no holds remain → Start trailing timer
With no holds → Ignored
```

### VACATE Event

```
Any → Vacant (immediate, clears all timers and holds)
```

### LOCK Event

```
Any → State frozen (current state preserved, events ignored)
```

### UNLOCK Event

```
Frozen → State unfrozen (resume normal processing)
```

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

### While Locked

- Occupancy events (TRIGGER, HOLD, RELEASE, VACATE) are ignored
- Only UNLOCK and UNLOCK_ALL events are processed
- Current state (occupied/vacant) is preserved

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
        "occupied_until": "2025-01-27T15:30:00Z",
        "active_holds": [],
        "locked_by": [],  # WHO has locked this location
    },
    timestamp=datetime.now(UTC),
)
```

---

## 11. Integration Examples

### Motion Sensor

```python
# Motion detected
engine.process_event(OccupancyEvent(
    location_id="kitchen",
    event_type=EventType.TRIGGER,
    source_id="binary_sensor.kitchen_motion",
    timestamp=now,
    timeout=300,  # 5 minutes
))
```

### Presence Sensor (mmWave/Radar)

```python
# Presence detected
engine.process_event(OccupancyEvent(
    location_id="office",
    event_type=EventType.HOLD,
    source_id="binary_sensor.office_presence",
    timestamp=now,
))

# Presence cleared
engine.process_event(OccupancyEvent(
    location_id="office",
    event_type=EventType.RELEASE,
    source_id="binary_sensor.office_presence",
    timestamp=now,
    timeout=120,  # 2 min trailing
))
```

### Light Switch (Force Vacant)

```python
# Light turned off = room vacant
engine.process_event(OccupancyEvent(
    location_id="bedroom",
    event_type=EventType.VACATE,
    source_id="light.bedroom_main",
    timestamp=now,
))
```

### Lock/Unlock (Multiple Sources)

```python
# Sleep mode automation locks bedroom as occupied
engine.process_event(OccupancyEvent(
    location_id="bedroom",
    event_type=EventType.LOCK,
    source_id="automation_sleep_mode",
    timestamp=now,
))
# locked_by = {"automation_sleep_mode"}

# Another automation also needs it locked
engine.process_event(OccupancyEvent(
    location_id="bedroom",
    event_type=EventType.LOCK,
    source_id="automation_do_not_disturb",
    timestamp=now,
))
# locked_by = {"automation_sleep_mode", "automation_do_not_disturb"}

# Sleep mode ends - still locked by do_not_disturb!
engine.process_event(OccupancyEvent(
    location_id="bedroom",
    event_type=EventType.UNLOCK,
    source_id="automation_sleep_mode",
    timestamp=now,
))
# locked_by = {"automation_do_not_disturb"}

# Force unlock everything (user override)
engine.process_event(OccupancyEvent(
    location_id="bedroom",
    event_type=EventType.UNLOCK_ALL,
    source_id="user_override",
    timestamp=now,
))
# locked_by = {}
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

**Status**: v2.0 Final ✅  
**Dependencies**: Core kernel (Location, EventBus, LocationManager)
