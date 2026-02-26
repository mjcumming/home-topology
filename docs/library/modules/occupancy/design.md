# Occupancy Module Design

> Core occupancy tracking for home-topology

**Status**: v3.0 Final  
**Version**: 3.0  
**Last Updated**: 2025-11-26

---

## 1. Overview

The **OccupancyModule** tracks occupancy state per location in the home topology. It provides a binary occupied/vacant state with hierarchical propagation.

### Design Principles

1. **Simple**: Binary state (occupied/vacant), no weighted confidence
2. **Platform-agnostic**: Core library has no knowledge of platform-specific details
3. **Integration-driven**: Event classification happens in the integration layer
4. **Testable**: Time-agnostic design, all time passed as parameters
5. **Hierarchical**: Automatic propagation up the location tree
6. **Per-source tracking**: Each source's contribution tracked independently

---

## 2. Responsibilities

### Core Library (This Module)

- Track occupancy state per location
- Track per-source contributions
- Process occupancy events
- Manage timeout timers per source
- Handle hierarchical propagation
- Persist and restore state
- Emit `occupancy.changed` events

### Integration Layer

- Map platform entities to locations
- Classify events (motion → TRIGGER, presence → TRIGGER with indefinite timeout, etc.)
- Determine appropriate timeouts
- Send well-formed events to the core library

---

## 3. Events and Commands

The occupancy module uses a simplified two-event model for device signals, plus commands for imperative actions.

### Events (From Entities via Integration)

Events are signals from entities, processed through the integration's "Occupancy Sources" configuration:

| Event | Behavior |
|-------|----------|
| `TRIGGER` | Source is contributing to occupancy. Sets occupied, with optional timeout (None = indefinite). |
| `CLEAR` | Source stops contributing. Optionally starts a trailing timer before fully clearing. |

### Commands (From Automations/UI)

Commands are imperative actions, called directly by automations, services, or UI:

| Command | Behavior |
|---------|----------|
| `VACATE` | Force vacant. Immediately clears all source contributions. |
| `LOCK` | Add/update source lock directive (`mode` + `scope`). |
| `UNLOCK` | Remove source lock directive from the target location. |
| `UNLOCK_ALL` | Clear all direct lock directives on the target location. |

### API Methods

```python
class OccupancyModule:
    # EVENTS (from entity state changes via integration)
    def trigger(self, location_id, source_id, timeout=None): ...
    def clear(self, location_id, source_id, trailing_timeout=0): ...
    
    # COMMANDS (from automations/UI)
    def vacate(self, location_id): ...
    def lock(self, location_id, source_id, mode="freeze", scope="self"): ...
    def unlock(self, location_id, source_id): ...
    def unlock_all(self, location_id): ...
```

### Why Two Events Instead of Three?

The v2.x model had TRIGGER, HOLD, and RELEASE:
- TRIGGER: activity with timeout
- HOLD: indefinite presence
- RELEASE: end of hold with trailing timeout

The v3.0 model unifies this:
- TRIGGER: source is contributing (with timeout, or `None` for indefinite)
- CLEAR: source stops contributing (with optional trailing timeout)

This is conceptually simpler: a source either IS or ISN'T contributing to occupancy.

---

## 4. Per-Source State Model

Each location tracks which sources are actively contributing to occupancy.

### Source Contribution

```python
@dataclass(frozen=True)
class SourceContribution:
    """A source's active contribution to occupancy."""
    source_id: str
    expires_at: datetime | None  # None = indefinite until CLEAR
```

### Location Runtime State

```python
@dataclass(frozen=True)
class LocationRuntimeState:
    contributions: FrozenSet[SourceContribution]  # Active contributors
    locked_by: FrozenSet[str]                     # WHO locked this
    timer_remaining: timedelta | None = None       # Stored when locked (for resume)
    
    @property
    def is_occupied(self) -> bool:
        """Location is occupied if any source is contributing."""
        return len(self.contributions) > 0
    
    @property
    def is_locked(self) -> bool:
        """Check if this location is locked (frozen)."""
        return len(self.locked_by) > 0
```

### State Semantics

| Condition | Meaning |
|-----------|---------|
| Any active contribution | Occupied |
| No active contributions | Vacant |
| Contribution with `expires_at` set | Timed contribution (will auto-expire) |
| Contribution with `expires_at=None` | Indefinite contribution (until CLEAR) |
| `len(locked_by) > 0` | State frozen, events ignored |

### Why Per-Source Tracking?

This enables proper layering of sensors:
- Motion sensor: contributes for 5 min
- Presence sensor: contributes indefinitely
- If presence clears but motion timer still running → still occupied

Without per-source tracking, sensor contributions would overwrite each other.

---

## 5. Location Configuration

Minimal per-location configuration:

```python
{
    "default_timeout": 300,           # Seconds for TRIGGER events (if not specified)
    "default_trailing_timeout": 120,  # Seconds for CLEAR events (if not specified)
    "occupancy_strategy": "independent",  # or "follow_parent"
    "contributes_to_parent": True,    # Propagate to parent?
}
```

### Configuration Fields

| Field | Purpose |
|-------|---------|
| `default_timeout` | Timer duration for TRIGGER events (if not specified in event) |
| `default_trailing_timeout` | Timer duration for CLEAR events (if not specified in event) |
| `occupancy_strategy` | INDEPENDENT or FOLLOW_PARENT |
| `contributes_to_parent` | Whether this location's occupancy propagates up |

### Timeout Inheritance

Timeouts are determined in this order:
1. **Event-level override**: If `timeout` parameter is provided, use it
2. **Entity-level configuration**: Integration can configure per-entity timeouts
3. **Location default**: Use `default_timeout` or `default_trailing_timeout`

---

## 6. Event Parameters

Events are sent via method calls. Each event method has specific parameters:

### TRIGGER

```python
def trigger(
    self,
    location_id: str,      # Target location
    source_id: str,        # Entity that triggered
    timeout: int | None = None,  # Seconds until expires (None = indefinite)
) -> None:
    """Source is contributing to occupancy.
    
    Args:
        location_id: Target location ID
        source_id: Entity ID (e.g., "binary_sensor.kitchen_motion")
        timeout: Seconds until contribution expires.
                 None = indefinite (until clear() called).
                 If not provided, uses location's default_timeout.
    """
```

### CLEAR

```python
def clear(
    self,
    location_id: str,           # Target location
    source_id: str,             # Entity that triggered
    trailing_timeout: int = 0,  # Seconds of trailing time (0 = immediate)
) -> None:
    """Source stops contributing to occupancy.
    
    Args:
        location_id: Target location ID
        source_id: Entity ID
        trailing_timeout: Seconds of trailing occupancy before fully clearing.
                         0 = clear immediately.
                         If not provided, uses location's default_trailing_timeout.
    """
```

---

## 7. State Transitions

### TRIGGER Event

```
Source not contributing → Add contribution (with timeout or indefinite)
Source already contributing → Update expiration (extend if new time > current)
```

TRIGGER sets or extends a source's contribution. If the source already has an active contribution, the expiration is extended (takes the later time).

### CLEAR Event

```
Source contributing → Remove contribution (or set trailing timer)
  If trailing_timeout > 0:
    Contribution expires_at = now + trailing_timeout
  Else:
    Remove contribution immediately
Source not contributing → Ignored
```

CLEAR removes a source's contribution, optionally with a trailing period.

### VACATE Command

```
Any → Clear all contributions immediately
Locked → Ignored (cannot vacate while locked)
```

### LOCK Command

```
Any → State frozen
Contributions → Suspended (remaining times stored)
Events → Ignored until unlocked
```

When locked, contribution timers are **suspended**. The remaining times are stored for resume.

### UNLOCK Command

```
Locked → Remove source from locked_by
If locked_by empty:
  Contributions → Resume (expires_at recalculated)
  Resume normal processing
```

When unlocked, contribution timers **resume** from where they were suspended.

---

## 8. Hierarchical Propagation

### Upward Propagation (Child → Parent)

When a child location becomes occupied, the parent automatically becomes occupied:

```
Kitchen occupied → Main Floor occupied → House occupied
```

**Rules**:
- Only propagates if `contributes_to_parent = True`
- Parent gets a synthetic contribution tracking the child
- Parent becomes vacant only when ALL contributing children are vacant

### FOLLOW_PARENT Strategy

Locations can follow their parent's state:

```python
occupancy_strategy: "follow_parent"
```

**Behavior**: Location mirrors parent's occupied state, ignores direct events.

---

## 9. Lock Policies (Mode + Scope)

Locks are source-tracked policy directives. A lock has:

- `mode`: `freeze`, `block_occupied`, or `block_vacant`
- `scope`: `self` or `subtree`

Multiple sources can set directives independently.

### Lock Behavior (source tracking)

```
LOCK(source="vacation_mode", mode="block_occupied", scope="subtree")
LOCK(source="cleaning_mode", mode="freeze", scope="self")
UNLOCK(source="vacation_mode")  # cleaning_mode still active
UNLOCK_ALL()                    # clear all direct lock sources at this location
```

### Timer Suspension

When `mode=freeze` is active, contribution timers are **suspended**, not cleared:

```
T+0:00  TRIGGER(10min)      → contribution expires T+10:00
T+3:00  LOCK                → timer suspended (7min remaining stored)
T+8:00  UNLOCK              → contribution expires T+15:00 (7min from now)
T+15:00 Timer expires       → contribution removed, check if still occupied
```

### While Locked

- `freeze`: ignores occupancy-changing events and preserves current occupied/vacant state
- `block_occupied`: prevents transitions to occupied (away/security intent)
- `block_vacant`: prevents transitions to vacant (party/manual hold intent)

### Scope Semantics

- `scope=self`: applies only to the target location
- `scope=subtree`: applies to target + descendants via inherited evaluation
- No lock-copy fanout is performed; descendants evaluate ancestor subtree directives at runtime

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
        "reason": "event:trigger",
        "contributions": [
            {"source_id": "binary_sensor.kitchen_motion", "expires_at": "2025-11-26T15:35:00Z"},
            {"source_id": "binary_sensor.kitchen_presence", "expires_at": None},
        ],
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
| `reason` | str | Stable reason string: `event:<event_type>`, `propagation:child:<location_id>`, `propagation:parent`, or `timeout` |
| `contributions` | list[dict] | Active source contributions with expirations |
| `locked_by` | list[str] | Source IDs currently locking |

---

## 11. Integration Examples

### Motion Sensor (TRIGGER Event with Timeout)

```python
# Motion detected - integration calls trigger()
module.trigger(
    location_id="kitchen",
    source_id="binary_sensor.kitchen_motion",
    timeout=300,  # 5 minutes
)
# Contribution added: expires in 5 min
# Motion OFF is ignored (timer handles expiration)
```

### Presence Sensor (TRIGGER Indefinite + CLEAR)

```python
# Presence detected - integration calls trigger() with no timeout
module.trigger(
    location_id="office",
    source_id="binary_sensor.office_presence",
    timeout=None,  # Indefinite until cleared
)
# Contribution added: expires_at = None (indefinite)

# Presence cleared - integration calls clear()
module.clear(
    location_id="office",
    source_id="binary_sensor.office_presence",
    trailing_timeout=120,  # 2 min trailing
)
# Contribution updated: expires in 2 min
```

### Door Sensors (Two Patterns)

#### Pattern 1: Entry Door (Default)

Door opening indicates someone entered:

```python
# Door opened - integration calls trigger()
module.trigger(
    location_id="entryway",
    source_id="binary_sensor.front_door",
    timeout=120,  # 2 minutes
)
# Door closed is ignored (timer handles expiration)
```

**Use cases**: Front door, entryway, room doors

#### Pattern 2: State Door

Door state directly indicates occupancy:

```python
# Garage door opened
module.trigger(
    location_id="garage",
    source_id="binary_sensor.garage_door",
    timeout=None,  # Indefinite - door state is the signal
)

# Garage door closed
module.clear(
    location_id="garage",
    source_id="binary_sensor.garage_door",
    trailing_timeout=0,  # Immediate - door closed = vacant
)
```

**Use cases**: Garage door, storage room, closet - door state = occupancy state

**Key insight**: `timeout=None` means "indefinite until CLEAR is called". The door closing triggers CLEAR, so no timeout is needed.

### Light Switch (VACATE Command)

```python
# Light turned off = room vacant - integration calls vacate()
module.vacate(location_id="bedroom")
# All contributions cleared immediately
```

### Lock/Unlock Commands

```python
# Away mode blocks occupancy from turning on anywhere under house
module.lock(
    location_id="house",
    source_id="automation_away",
    mode="block_occupied",
    scope="subtree",
)

# Party mode holds occupancy active on main floor
module.lock(
    location_id="main_floor",
    source_id="automation_party_mode",
    mode="block_vacant",
    scope="subtree",
)

# Party mode ends
module.unlock(location_id="main_floor", source_id="automation_party_mode")

# Emergency reset
module.unlock_all(location_id="house")
```

### Combined Scenario: Presence + Motion (Coverage Gap)

Demonstrates per-source tracking handling mixed sensor coverage:

```python
# Presence sensor sees user at desk
module.trigger("office", "presence_sensor", timeout=None)  # indefinite
# contributions: [presence: indefinite]

# User walks to corner (presence loses them, motion sees them)
module.trigger("office", "motion_sensor", timeout=600)  # 10 min
# contributions: [presence: indefinite, motion: T+10min]

# Presence clears (user not in presence sensor view)
module.clear("office", "presence_sensor", trailing_timeout=120)
# contributions: [presence: T+2min, motion: T+10min]

# Presence trailing expires (T+2min)
# contributions: [motion: T+8min remaining] - STILL OCCUPIED!

# Motion expires (T+10min total)
# contributions: [] - now vacant
```

This is why per-source tracking matters: the motion sensor's contribution is preserved even when the presence sensor clears.

---

## 12. Testing Strategy

### Unit Tests

- State transitions for each event type
- Per-source contribution tracking
- Timer behavior (add, extend, expire)
- CLEAR with and without trailing timeout
- Lock/unlock behavior

### Integration Tests

- Hierarchical propagation
- FOLLOW_PARENT strategy
- State persistence/restore
- Event emission

### Scenario Tests

- "Office work session" (presence + motion coverage gap)
- "Quick bathroom visit" (motion trigger → timeout)
- "State freeze" (lock during events, sleep, vacation)
- "Family at home" (multiple locations, hierarchy)

---

## 13. References

- **Architecture**: `../../architecture.md`
- **Design Decisions**: `design-decisions.md`
- **Implementation Status**: `implementation-status.md`
- **API Reference**: `api.md`

---

**Status**: v3.0 Final ✅  
**Dependencies**: Core kernel (Location, EventBus, LocationManager)

---

## Appendix: Version History

### v3.0 Changes (2025-11-26)

| Change | Description |
|--------|-------------|
| Simplified Event Model | TRIGGER + CLEAR replaces TRIGGER/HOLD/RELEASE |
| Per-Source Tracking | Each source tracked independently with its own expiration |
| Unified Timeout Concept | All contributions have expiration (or None for indefinite) |
| State Model | `contributions: Set[SourceContribution]` replaces `active_holds` + `occupied_until` |
| Clearer Mental Model | Source either IS or ISN'T contributing |

See `design-decisions.md` Decision 15 for full rationale.

### v2.3 Changes (2025-11-26)

| Change | Description |
|--------|-------------|
| Events vs Commands | Separated API into events (trigger/hold/release) and commands (vacate/lock/unlock) |
| Timer Suspension | Timers pause during lock and resume when unlocked |
| Holds + Timers | Timers continue during holds, used when holds release |
| Identity Tracking | Removed `active_occupants` and `occupant_id` (deferred to PresenceModule) |

### v2.2 Changes (2025-11-25)

| Change | Description |
|--------|-------------|
| Removed LocationKind | Unused enum removed from design |
