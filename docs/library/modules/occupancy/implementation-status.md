# Occupancy Module - Implementation Status

**Status**: v2.3 Design Approved  
**Last Updated**: 2025-11-26  
**Version**: 2.3.0

---

## Overview

This document tracks the implementation status of the Occupancy Module. The module has evolved through several design iterations:

- **v1**: Complex with confidence scoring (deprecated)
- **v2.0**: Simplified with integration-layer classification
- **v2.3**: Events vs Commands separation, timer improvements

**Key Design Changes (v2.3)**:
- Separated Events (trigger/hold/release) from Commands (vacate/lock/unlock)
- Timer suspension during lock (suspend/resume)
- Holds and timers coexist (timers preserved during holds)
- Removed identity tracking (deferred to PresenceModule)

See `design-decisions.md` for full rationale (Decisions 11-14).

---

## v2.3 Architecture (Current Design)

### Events vs Commands

| Category | Signals | Origin | API |
|----------|---------|--------|-----|
| **Events** | TRIGGER, HOLD, RELEASE | Device mappings | `trigger()`, `hold()`, `release()` |
| **Commands** | VACATE, LOCK, UNLOCK, UNLOCK_ALL | Automations/UI | `vacate()`, `lock()`, `unlock()`, `unlock_all()` |

### State Structure

```python
@dataclass(frozen=True)
class LocationRuntimeState:
    is_occupied: bool = False
    occupied_until: datetime | None = None
    timer_remaining: timedelta | None = None  # NEW: for lock suspension
    active_holds: set[str] = field(default_factory=set)
    locked_by: set[str] = field(default_factory=set)
    # REMOVED: active_occupants (deferred to PresenceModule)
```

### Location Configuration

```python
{
    "default_timeout": 300,           # For TRIGGER events
    "hold_release_timeout": 120,      # After RELEASE (hold ends)
    "occupancy_strategy": "independent",  # or "follow_parent"
    "contributes_to_parent": True,
}
```

---

## Implementation Phases

### Phase 1: Core State Machine ✅ COMPLETE

- ✅ State machine with occupied, holds, locks
- ✅ Hierarchical propagation (child → parent)
- ✅ FOLLOW_PARENT strategy
- ✅ Lock state (state freeze)
- ✅ State persistence with stale protection
- ✅ Time-agnostic design
- ✅ Seconds-based time units

### Phase 2: v2.3 Migration 🔄 IN PROGRESS

**Documentation** ✅
- [x] Update design decisions (Decisions 11-14)
- [x] Update design document (design.md)
- [x] Update implementation status (this document)
- [ ] Update API reference (api.md)

**Code Changes** (Pending)
- [ ] `models.py` - Remove `active_occupants` field
- [ ] `models.py` - Add `timer_remaining` field
- [ ] `models.py` - Remove `occupant_id` from event parameters
- [ ] `module.py` - Separate events vs commands API
- [ ] `module.py` - Remove `occupant_id` parameter
- [ ] `engine.py` - Timer suspension during lock
- [ ] `engine.py` - Holds and timers coexistence logic
- [ ] `engine.py` - RELEASE checks existing timer before trailing
- [ ] Tests - Timer suspension tests
- [ ] Tests - Hold + timer coexistence tests
- [ ] Tests - Remove identity tracking tests

### Phase 3: Advanced Features ❌ DEFERRED

- ❌ Adaptive timeout mode
- ❌ Rule-based engine
- ❌ Multi-modal sensor fusion
- ❌ Activity recognition
- ❌ Identity/Person tracking (future PresenceModule)

---

## v2.3 Behavior Changes

### Timer During Lock (NEW)

**Before (v2.0)**: Timer behavior during lock was undefined.

**After (v2.3)**: Timer is suspended and resumes when unlocked.

```
T+0:00  TRIGGER(10min)  → occupied_until = T+10:00
T+3:00  LOCK            → timer_remaining = 7min, occupied_until = None
T+8:00  UNLOCK          → occupied_until = T+15:00 (7min from now)
```

### Holds and Timers (NEW)

**Before (v2.0)**: Unclear if timers were cleared during holds.

**After (v2.3)**: Timers continue during holds. When holds release, existing timer is used if still valid.

```
T+0:00  TRIGGER(10min)  → occupied_until = T+10:00
T+1:00  HOLD            → occupied indefinitely, timer preserved
T+2:00  TRIGGER(10min)  → timer extended to T+12:00
T+3:00  RELEASE         → occupied_until = T+12:00 (not trailing timer)
```

### Identity Tracking (REMOVED)

**Before (v2.0)**: `active_occupants` and `occupant_id` were optional.

**After (v2.3)**: Removed entirely. Identity tracking deferred to future PresenceModule.

---

## Code Migration Checklist

### models.py

```python
# REMOVE
active_occupants: set[str] = field(default_factory=set)
occupant_id: str | None = None

# ADD
timer_remaining: timedelta | None = None
```

### module.py

```python
# CHANGE: Separate event methods from command methods

# Events (from device mappings)
def trigger(self, location_id, source_id, timeout=None): ...
def hold(self, location_id, source_id): ...
def release(self, location_id, source_id, trailing_timeout=None): ...

# Commands (from automations/UI)
def vacate(self, location_id): ...
def lock(self, location_id, source_id): ...
def unlock(self, location_id, source_id): ...
def unlock_all(self, location_id): ...

# REMOVE: occupant_id parameter from all methods
```

### engine.py

```python
# ADD: Timer suspension logic in lock/unlock
# ADD: Timer preservation logic in hold
# ADD: Timer check in release (use existing timer if valid)
```

---

## Testing Checklist

### New Tests Needed

- [ ] Timer suspension during lock
- [ ] Timer resume after unlock
- [ ] TRIGGER during active hold extends timer
- [ ] RELEASE uses existing timer if > trailing timeout
- [ ] RELEASE uses trailing timeout if no existing timer
- [ ] Multiple TRIGGERs during hold accumulate correctly

### Tests to Update

- [ ] Remove `active_occupants` assertions
- [ ] Remove `occupant_id` from event construction
- [ ] Update API calls to use new method signatures

### Tests to Remove

- [ ] Any identity tracking tests

---

## References

- **Design Decisions**: `design-decisions.md` (Decisions 1-14)
- **Design Document**: `design.md` (v2.3)
- **API Reference**: `api.md` (needs update)
- **Future**: PresenceModule for identity tracking

---

**Current Status**: v2.3 Design Approved ✅  
**Next Step**: Implement code changes (models.py, module.py, engine.py)

