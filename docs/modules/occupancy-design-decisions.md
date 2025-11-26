# Occupancy Module - Design Decisions

**Status**: Approved  
**Date**: 2025-11-26  
**Version**: 2.3

---

## Overview

This document captures the key design decisions for the Occupancy Module, which simplifies the architecture by moving signal classification to the integration layer and streamlining the event type system.

**v2.3 Changes** (2025-11-26):
- Decision 11: Events vs Commands - Separate API surfaces
- Decision 12: Timer suspension during lock
- Decision 13: Holds and timers coexist
- Decision 14: Remove identity tracking (defer to PresenceModule)

**v2.2 Changes** (2025-11-25): Removed `LocationKind` enum (was unused cruft from earlier design).

---

## Decision 1: Signal Classification at Integration Layer

### Context

Originally, the occupancy module was designed to handle signal classification internally, with categories like "motion", "presence", "door", "media", etc., and weighted confidence scoring from primary/secondary signals.

### Decision

**Move all signal classification to the integration layer** (e.g., Home Assistant).

### Rationale

1. **Separation of concerns**: Core library handles occupancy logic; integrations handle platform-specific entity knowledge
2. **Platform-agnostic core**: Library doesn't need to know about platform-specific entity types.
3. **Simpler core API**: Events are self-describing with all needed information
4. **Integration flexibility**: Each platform can leverage its native entity metadata
5. **Better testability**: Core library tests don't need mock entities

### Implementation

The integration layer is responsible for:
- Detecting entity state changes
- Mapping entities to locations
- Determining event type (TRIGGER vs HOLD vs RELEASE)
- Setting appropriate timeouts
- Sending complete events to the core library

The core library receives events that already contain:
- `location_id`: Where
- `event_type`: What behavior
- `source_id`: What triggered it
- `timeout`: How long (optional, uses location default if not provided)

---

## Decision 2: Seven Event Types

### Context

The original design had event types that were tied to sensor categories, with PROPAGATED as an internal event type exposed in the API.

### Decision

**Seven clean event types**, with PROPAGATED handled as internal logic:

```python
class EventType(Enum):
    # Occupancy signals (sent by integrations)
    TRIGGER = "trigger"      # Activity detected → occupied + timer
    HOLD = "hold"            # Presence started → occupied indefinitely
    RELEASE = "release"      # Presence ended → trailing timer starts
    VACATE = "vacate"        # Force vacant immediately
    
    # State control (sent by integrations)
    LOCK = "lock"            # Add source to locked_by set
    UNLOCK = "unlock"        # Remove source from locked_by set
    UNLOCK_ALL = "unlock_all"  # Clear all locks
```

### Rationale

| Event | Purpose |
|-------|---------|
| **TRIGGER** | Activity detection (motion, door, light, any change). Sets occupied + starts/extends timer. |
| **HOLD** | Presence detection (radar, BLE). Sets occupied indefinitely until released. |
| **RELEASE** | Presence cleared. Releases hold, starts trailing timer. |
| **VACATE** | Force vacant. Used when integration determines vacancy (e.g., light off = vacant). |
| **LOCK** | Freezes state. Adds source to `locked_by` set. |
| **UNLOCK** | Removes source from `locked_by`. Unfrozen when set empty. |
| **UNLOCK_ALL** | Clears `locked_by` entirely. Force unlock. |

### Why Not PROPAGATED?

Propagation is internal logic, not an external event. When a child location becomes occupied, the engine internally propagates to parents. Integrations never send PROPAGATED events.

### Why Split LOCK/UNLOCK?

Explicit commands are clearer than a toggle. `LOCK_CHANGE` was ambiguous about desired state.

---

## Decision 3: Drop Confidence Scoring

### Context

The original design included weighted confidence scoring from primary (1.0) and secondary signals (+0.2 to +0.4), allowing nuanced automation decisions.

### Decision

**Remove confidence scoring entirely.** Binary occupied/vacant is sufficient.

### Rationale

1. **Modern sensors are accurate**: Presence sensors (mmWave, radar) are reliable enough that weighted confidence adds little value
2. **Complexity vs benefit**: Weighted scoring adds configuration burden with minimal practical benefit
3. **Binary is clear**: Automations are simpler when occupancy is yes/no
4. **KISS principle**: Start simple, add complexity only if proven necessary

### What Replaces It?

- **Timeouts provide implicit confidence**: Short timeout = less confident, long timeout = more confident
- **HOLD events provide certainty**: Active holds indicate definite presence
- **Integration can filter**: If an integration wants confidence, it can implement filtering before sending events

---

## Decision 4: Drop Secondary Signals

### Context

Secondary signals (lights, switches, power, climate) were designed to boost confidence without directly triggering occupancy.

### Decision

**Remove secondary signal concept.** All signals are treated equally based on how the integration classifies them.

### Rationale

1. **No confidence = no need for boosters**: Without weighted confidence, secondary signals lose their purpose
2. **Integration decides importance**: If a light switch should trigger occupancy, the integration sends TRIGGER
3. **If light OFF = vacant**: Integration sends VACATE
4. **Simpler mental model**: Every signal either triggers occupancy or doesn't

### Example: Light Switch

**Old approach**:
- Light ON → boost confidence +0.3
- Light OFF → decrease confidence

**New approach**:
- Light ON → Integration sends TRIGGER with timeout (if configured to indicate occupancy)
- Light OFF → Integration sends VACATE (if configured to indicate vacancy)
- Or: Integration ignores light entirely (if it shouldn't affect occupancy)

---

## Decision 5: Simplified Location Configuration

### Context

Location config included category-based timeouts, secondary signal weights, and complex signal hierarchies.

### Decision

**Minimal location configuration:**

```python
{
    "default_timeout": 300,           # For TRIGGER events without explicit timeout
    "hold_release_timeout": 120,      # Trailing time after HOLD ends (RELEASE)
    "occupancy_strategy": "independent",  # or "follow_parent"
    "contributes_to_parent": True,
}
```

### Rationale

1. **Two timeouts cover all cases**: Default for triggers, trailing for holds
2. **Event-level overrides**: Integrations can pass explicit timeouts per event
3. **No signal categories**: Classification happens at integration layer
4. **Hierarchy config stays**: Still need strategy and propagation settings

---

## Decision 6: Event-Level Timeout Override

### Context

Timeouts were configured per category (motion: 300s, door: 120s, etc.).

### Decision

**Events can carry explicit timeout override:**

```python
OccupancyEvent(
    location_id="kitchen",
    event_type=EventType.TRIGGER,
    source_id="binary_sensor.kitchen_motion",
    timeout=180,  # Override location default
)
```

### Rationale

1. **Integration knows best**: HA integration knows a motion sensor should use 5 min, door sensor 2 min
2. **Location defaults work**: If no timeout specified, use `default_timeout`
3. **Maximum flexibility**: Any signal can have any timeout
4. **No category mapping**: No need for "motion" → 300, "door" → 120 mappings in core

---

## Decision 7: Lock System with Source Tracking

### Context

An alternative approach uses "lock levels" - an integer counter where LOCK increments, UNLOCK decrements, and the location is locked when level > 0. This allows multiple systems to lock independently.

### Decision

**Track WHO locked, not just a count.** Use `locked_by: set[str]` instead of `lock_level: int`.

```python
@dataclass(frozen=True)
class LocationRuntimeState:
    # ... other fields ...
    locked_by: set[str] = field(default_factory=set)  # WHO locked this
```

### Event Types for Locking

| Event | Behavior |
|-------|----------|
| `LOCK` | Add `source_id` to `locked_by` set |
| `UNLOCK` | Remove `source_id` from `locked_by` set |
| `UNLOCK_ALL` | Clear `locked_by` set entirely |

### Lock State

```python
is_locked = len(state.locked_by) > 0
```

### Rationale

1. **Better debugging**: You can see WHO locked it, not just that it's locked
2. **Independence**: Multiple systems can lock/unlock without stepping on each other
3. **Safety**: `UNLOCK_ALL` for "reset everything" scenarios
4. **Same functionality**: Achieves same result as lock levels, but more informative

### Example

```python
# Sleep mode automation locks bedroom
LOCK(source_id="automation_sleep_mode")
# locked_by = {"automation_sleep_mode"}

# Do-not-disturb also locks
LOCK(source_id="automation_dnd")
# locked_by = {"automation_sleep_mode", "automation_dnd"}

# Sleep mode ends
UNLOCK(source_id="automation_sleep_mode")
# locked_by = {"automation_dnd"}  ← Still locked!

# DND ends
UNLOCK(source_id="automation_dnd")
# locked_by = {}  ← Now unlocked

# Or: Force clear all
UNLOCK_ALL(source_id="user_override")
# locked_by = {}
```

### No Lock Propagation

- Locks are **local** to each location
- No auto-propagate up or down
- Integration can send LOCK to multiple locations if cascade is desired
- Parent-child occupancy relationships are handled by normal hierarchy propagation (not locks)

---

## Summary: Before vs After

| Aspect | Before (v1) | After (v2) |
|--------|-------------|------------|
| **Event Types** | MOMENTARY, HOLD_START, HOLD_END, MANUAL, LOCK_CHANGE, PROPAGATED | TRIGGER, HOLD, RELEASE, VACATE, LOCK, UNLOCK, UNLOCK_ALL |
| **Signal Classification** | Core library (pattern matching) | Integration layer |
| **Confidence** | Weighted 0.0-1.0 | None (binary) |
| **Secondary Signals** | Lights, switches, power (boost confidence) | None (all signals equal) |
| **Timeouts** | Per-category dictionary | Location default + event override |
| **Propagation** | PROPAGATED event type | Internal logic |
| **Configuration** | Complex (categories, weights, signals) | Minimal (two timeouts, strategy) |
| **Lock State** | `lock_state: LockState` enum | `locked_by: set[str]` with source tracking |

---

## Migration Path

### For Core Library

1. Update `EventType` enum with new values
2. Remove confidence scoring from state/events
3. Simplify `OccupancyEvent` (remove category, add timeout)
4. Update engine to handle new event types
5. Move propagation to internal logic

### For Integrations

1. Update event type mapping (MOMENTARY → TRIGGER, etc.)
2. Set timeout per event based on entity type
3. Remove confidence handling from event processing
4. Add VACATE events where appropriate

---

## References

- **Implementation Status**: `occupancy-implementation-status.md`
- **Integration Guide**: `occupancy-integration.md`
- **Original Design**: `occupancy-design.md` (historical reference)

---

## Decision 8: Remove LocationKind (2025-11-25)

### Context

The occupancy module had a `LocationKind` enum with values `AREA` and `VIRTUAL`. This was intended to distinguish physical areas from logical groupings.

### Decision

**Remove `LocationKind` entirely.** It was never used to change behavior.

### Rationale

1. **Never used**: The engine never checked `kind` to change behavior
2. **Always defaulted**: Every location was created with `kind=AREA`
3. **Redundant**: Behavioral distinctions are already captured by:
   - `OccupancyStrategy` (independent vs follow_parent)
   - `contributes_to_parent` (whether occupancy bubbles up)
4. **Config-driven**: If a location needs "virtual" behavior, configure it via module settings

### What Replaces It?

Nothing. Use existing configuration options:
- For "virtual" locations that derive state from children: use hierarchy + `OccupancyStrategy.FOLLOW_PARENT`
- For locations that shouldn't contribute to parent: set `contributes_to_parent=False`

---

## Decision 9: Two Timeout Concepts (Effective vs Own)

### Context

A parent location tracks its own `occupied_until` timer, which gets set/extended during propagation from child locations. However, the parent may remain occupied beyond its own timer because children are still occupied.

Consider:
- Kitchen triggers at T+0, timer set to T+60s
- House (parent) gets propagation, timer set to T+300s (house's default_timeout)
- At T+61s, kitchen goes vacant, house still occupied until T+300s
- BUT: If bedroom has timer until T+400s, house is "effectively" occupied until T+400s

### Decision

**Expose two timeout concepts:**

1. **`occupied_until`** (existing) - The location's own timer. What the location itself calculated.

2. **`get_effective_timeout(location_id, now)`** (new method) - When the location will TRULY become vacant, considering all descendants. Recursively calculates `max(self.occupied_until, max(child.effective_timeout for each child))`.

### Rationale

1. **Integration choice**: Integration can decide which to display or use for automations
2. **Accurate prediction**: "House will be truly vacant in 45s" is more useful than "House timer expires in 5min but kitchen is still occupied"
3. **Scheduling**: Automations can schedule based on "truly vacant" time
4. **Debugging**: Understand why parent is still occupied

### API

```python
# Location's own timer
state = module.get_location_state("house")
own_timeout = state["occupied_until"]

# When truly vacant (considers descendants)
effective = module.get_effective_timeout("house", now)
```

### Implementation Notes

- Returns `None` if location is vacant or has indefinite hold
- Recursively checks all descendants
- Active holds or occupants mean "indefinite" (returns `None`)
- Cached or calculated on-demand (implementation choice)

---

## Decision 10: Cascading Vacate Method

### Context

The `VACATE` event only affects a single location. When a user or automation wants to "clear the first floor", they need to send VACATE to every room individually.

### Decision

**Add `vacate_area()` method** (not a new event type) that recursively vacates a location and all its descendants.

### Rationale

1. **Method, not event**: This is a command from the integration, not a sensor signal
2. **Integration presents UI**: Integration decides how to expose (button, service, automation action)
3. **Clear intent**: Separate from single-location VACATE
4. **Atomic operation**: All locations vacated together

### API

```python
def vacate_area(
    self, 
    location_id: str, 
    source_id: str,
    include_locked: bool = False,  # Skip locked by default
    now: Optional[datetime] = None,
) -> List[StateTransition]:
    """Vacate location and ALL descendants.
    
    Args:
        location_id: Root of subtree to vacate
        source_id: What initiated the vacate (for logging/debugging)
        include_locked: If True, also unlocks and vacates locked locations
        now: Current time (defaults to datetime.now(UTC))
    
    Returns:
        List of all state transitions that occurred
    """
```

### Behavior

1. Gets all descendants of location (using LocationManager.descendants_of())
2. For each location (including root):
   - If locked and `include_locked=False`: Skip
   - If locked and `include_locked=True`: UNLOCK_ALL first, then VACATE
   - Otherwise: Send VACATE event
3. Process in order (children first? parent first? - implementation detail)
4. Return all transitions

### Use Cases

- "Everyone left" button in UI
- Away mode activation
- Testing/debugging
- Panic/emergency clear

### Lock Handling

| `include_locked` | Locked Location Behavior |
|------------------|--------------------------|
| `False` (default) | Skip - respects the lock |
| `True` | Force unlock + vacate |

Default `False` is safer - if someone locked a room, they probably had a reason.

---

## Decision 11: Events vs Commands - Separate API Surfaces

### Context

The original design treated all 7 signal types uniformly as "events" processed through the same code path. However, there's a conceptual distinction between device-originated signals and imperative commands.

### Decision

**Separate occupancy signals into Events and Commands:**

| Category | Signal Types | Origin | API |
|----------|-------------|--------|-----|
| **Events** | TRIGGER, HOLD, RELEASE | Device state changes via integration | `trigger()`, `hold()`, `release()` methods |
| **Commands** | VACATE, LOCK, UNLOCK, UNLOCK_ALL | Automations, UI, direct calls | `vacate()`, `lock()`, `unlock()`, `unlock_all()` methods |

### Rationale

1. **Conceptual clarity**: Events are "things that happened", commands are "do this now"
2. **Different origins**: Events come from device mappings, commands from automations/UI
3. **Simpler signatures**: Commands don't need `timeout` or device-related fields
4. **Testing**: Commands can be tested independently from event processing
5. **Integration design**: Natural separation - device mappings produce events, services expose commands

### API

```python
class OccupancyModule:
    # EVENTS (from device mappings)
    def trigger(self, location_id, source_id, timeout=None): ...
    def hold(self, location_id, source_id): ...
    def release(self, location_id, source_id, trailing_timeout=None): ...
    
    # COMMANDS (from automations/UI)
    def vacate(self, location_id): ...
    def lock(self, location_id, source_id): ...
    def unlock(self, location_id, source_id): ...
    def unlock_all(self, location_id): ...
```

### Impact

- Core library API changes (method signatures)
- Integration layer uses events for device mappings, commands for services
- Documentation updated to reflect distinction

---

## Decision 12: Timer Behavior While Locked - Suspend and Resume

### Context

When a location is locked, occupancy events are ignored. The question: what happens to an active timer?

### Decision

**Timer is suspended while locked and resumes when unlocked.**

### State Addition

```python
@dataclass
class LocationRuntimeState:
    # ... existing fields ...
    timer_remaining: timedelta | None = None  # Stored when locked
```

### Behavior

```
LOCK received (while timer active):
  timer_remaining = occupied_until - now
  occupied_until = None  # Timer paused

UNLOCK received (when lock clears):
  if timer_remaining is not None:
    occupied_until = now + timer_remaining
    timer_remaining = None  # Timer resumed
```

### Rationale

1. **Expectation**: User locks at 5min remaining, unlocks later, expects 5min left
2. **Fairness**: Lock shouldn't consume timer
3. **Predictability**: State is truly "frozen"

### Example

```
T+0:00  TRIGGER(10min)      → occupied_until = T+10:00
T+3:00  LOCK                → timer_remaining = 7min, occupied_until = None
T+8:00  UNLOCK              → occupied_until = T+15:00 (7min from now)
T+15:00 Timer expires       → vacant
```

---

## Decision 13: Holds and Timers Coexist

### Context

What happens when TRIGGER and HOLD events interact? Originally proposed that holds would "supersede" (clear) timers, but this loses contributions from motion sensors during presence holds.

### Decision

**Timers continue to be tracked during holds. When all holds release, the existing timer (if still valid) is used; otherwise trailing timer starts.**

### Behavior

```
TRIGGER received:
  occupied_until = max(occupied_until, now + timeout)  # Always extend
  is_occupied = True

HOLD received:
  active_holds.add(source_id)
  is_occupied = True
  # occupied_until unchanged - timers keep running

RELEASE received (last hold):
  active_holds.remove(source_id)
  if active_holds is empty:
    if occupied_until is None or occupied_until <= now:
      # No valid timer - start trailing timer
      occupied_until = now + trailing_timeout
    # else: keep existing timer from TRIGGERs
```

### Rationale

1. **Real-world scenario**: Presence sensors have coverage gaps, motion sensors fill them
2. **User expectation**: All sensors should contribute to occupancy
3. **Simple implementation**: Just don't clear the timer on HOLD
4. **Intuitive**: TRIGGER always extends, RELEASE checks what's left

### Example

```
T+0:00  TRIGGER(10min)   → occupied until T+10:00
T+1:00  HOLD             → occupied indefinitely, timer preserved at T+10:00
T+2:00  TRIGGER(10min)   → occupied until T+12:00 (extended!)
T+3:00  RELEASE          → occupied until T+12:00 (motion's timer kicks in)
T+12:00 Expires          → vacant
```

If no TRIGGERs during hold:

```
T+0:00  HOLD             → occupied indefinitely
T+5:00  RELEASE(2min)    → occupied until T+7:00 (trailing timer)
T+7:00  Expires          → vacant
```

---

## Decision 14: Remove Identity Tracking (Defer to PresenceModule)

### Context

The module included optional identity tracking via `occupant_id` on events and `active_occupants` in state, intended to answer "WHO is in this location?"

### Decision

**Remove identity tracking from OccupancyModule. Defer to a future PresenceModule.**

### Removed

- `occupant_id: str | None` from event methods
- `active_occupants: set[str]` from `LocationRuntimeState`

### Rationale

1. **No supporting events**: No events populate this data meaningfully
2. **No logic uses it**: Engine never checks `active_occupants`
3. **Different concern**: Identity is person-centric; occupancy is location-centric
4. **Separation of concerns**: Cleaner module with single responsibility
5. **Future flexibility**: PresenceModule can track identity properly with dedicated design

### PresenceModule (Future)

A separate module for identity/person tracking:
- Tracks WHO is where (person-centric)
- Subscribes to `occupancy.changed` events
- Maintains person entities with preferences
- Answers "Where is Mike?"
- Handles confidence/probability
- Out of scope for occupancy module

### Migration

- Remove `occupant_id` parameter from event methods
- Remove `active_occupants` from state model
- Update tests that reference these fields
- Document PresenceModule as future work

---

**Approved**: 2025-11-26  
**Status**: Implementation Ready

