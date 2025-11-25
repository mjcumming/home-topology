# Occupancy Module - Implementation Status

**Status**: v2.0 Design Approved  
**Last Updated**: 2025-01-27  
**Version**: 2.0.0

---

## Overview

This document tracks the implementation status of the Occupancy Module. The module is transitioning from v1 (complex with confidence scoring) to v2 (simplified with integration-layer classification).

**Key Design Change**: Event classification moved to integration layer. See `occupancy-design-decisions.md` for full rationale.

---

## v2.0 Architecture (Current Design)

### Event Types (7 total)

| Event | Purpose | Status |
|-------|---------|--------|
| `TRIGGER` | Activity detected → occupied + timer | 🔄 Rename from MOMENTARY |
| `HOLD` | Presence started → occupied indefinitely | 🔄 Rename from HOLD_START |
| `RELEASE` | Presence ended → trailing timer | 🔄 Rename from HOLD_END |
| `VACATE` | Force vacant immediately | ✨ New |
| `LOCK` | Add source to `locked_by` set | 🔄 Split from LOCK_CHANGE |
| `UNLOCK` | Remove source from `locked_by` set | 🔄 Split from LOCK_CHANGE |
| `UNLOCK_ALL` | Clear all locks (force unlock) | ✨ New |

### Removed Features

| Feature | Why Removed |
|---------|-------------|
| **Confidence Scoring** | Binary occupied/vacant is sufficient with modern sensors |
| **Secondary Signals** | No confidence = no need for boosters |
| **Category-based Timeouts** | Integration sets timeout per event |
| **PROPAGATED Event** | Moved to internal logic |
| **MANUAL Event** | Replaced by TRIGGER with explicit timeout |
| **LockState Enum** | Replaced by `locked_by: set[str]` for source tracking |

### New Features

| Feature | Purpose |
|---------|---------|
| **Lock Source Tracking** | `locked_by: set[str]` shows WHO locked the location |
| **UNLOCK_ALL Event** | Force clear all locks regardless of who locked |
| **Independent Locks** | Multiple automations can lock without stepping on each other |

### Location Configuration (Simplified)

```python
{
    "default_timeout": 300,           # For TRIGGER events
    "hold_release_timeout": 120,      # After RELEASE (hold ends)
    "occupancy_strategy": "independent",  # or "follow_parent"
    "contributes_to_parent": True,
}
```

### State Structure (Simplified)

```python
@dataclass(frozen=True)
class LocationRuntimeState:
    is_occupied: bool = False
    occupied_until: datetime | None = None
    active_holds: set[str] = field(default_factory=set)
    active_occupants: set[str] = field(default_factory=set)
    locked_by: set[str] = field(default_factory=set)  # WHO locked this
```

---

## Implementation Phases

### Phase 1: Core State Machine ✅ COMPLETE (v1)

**Status**: Working, needs migration to v2 event types

- ✅ State machine with occupied, holds, locks
- ✅ Hierarchical propagation (child → parent)
- ✅ FOLLOW_PARENT strategy
- ✅ Lock state (state freeze)
- ✅ State persistence with stale protection
- ✅ Time-agnostic design
- ✅ Seconds-based time units

### Phase 2: v2 Migration 🔄 IN PROGRESS

**Status**: Design approved, implementation pending

- [ ] Update EventType enum (6 new types)
- [ ] Remove confidence scoring from state/events
- [ ] Simplify OccupancyEvent (remove category, add timeout)
- [ ] Move propagation to internal logic
- [ ] Update engine for new event types
- [ ] Update module event translation
- [ ] Update tests for new event types

### Phase 3: Advanced Features ❌ DEFERRED

**Status**: Not planned for v2.0

- ❌ Adaptive timeout mode
- ❌ Rule-based engine
- ❌ Multi-modal sensor fusion
- ❌ Activity recognition

---

## Design vs Implementation Comparison

### v1 → v2 Changes

| Aspect | v1 (Current Code) | v2 (Target) |
|--------|-------------------|-------------|
| **Event Types** | MOMENTARY, HOLD_START, HOLD_END, MANUAL, LOCK_CHANGE, PROPAGATED | TRIGGER, HOLD, RELEASE, VACATE, LOCK, UNLOCK, UNLOCK_ALL |
| **Event Classification** | Core library (pattern matching) | Integration layer |
| **Confidence** | 3 levels (1.0, 0.8, 0.0) | None (binary) |
| **Timeouts** | Per-category dictionary | Location default + event override |
| **OccupancyEvent.category** | Required | Removed |
| **OccupancyEvent.timeout** | Via duration field | Explicit timeout field |
| **Lock State** | `lock_state: LockState` enum | `locked_by: set[str]` (source tracking) |

### What Stays the Same

| Feature | Status |
|---------|--------|
| LocationRuntimeState structure | ✅ Keep (is_occupied, occupied_until, active_holds, lock_state) |
| Hierarchical propagation | ✅ Keep (internal logic) |
| FOLLOW_PARENT strategy | ✅ Keep |
| Lock/unlock behavior | ✅ Keep (split into explicit events) |
| State persistence | ✅ Keep |
| Time-agnostic design | ✅ Keep |

---

## Testing Status

### Event Type Coverage (v1)

| v1 Event Type | Tested | v2 Mapping |
|---------------|--------|------------|
| MOMENTARY | ✅ | → TRIGGER |
| HOLD_START | ✅ | → HOLD |
| HOLD_END | ✅ | → RELEASE |
| MANUAL | ✅ | → TRIGGER (with timeout) |
| LOCK_CHANGE | ✅ | → LOCK / UNLOCK |
| PROPAGATED | ✅ (indirect) | → Internal logic |

### Tests to Update for v2

- [ ] Rename test methods for new event names
- [ ] Add VACATE event tests
- [ ] Split LOCK/UNLOCK tests
- [ ] Remove confidence assertions
- [ ] Update event construction (remove category)

---

## Migration Checklist

### Documentation ✅

- [x] Create design decisions document (`occupancy-design-decisions.md`)
- [x] Update implementation status (this document)
- [ ] Update design document (`occupancy-design.md`)
- [ ] Update integration guide (`occupancy-integration.md`)
- [ ] Archive rule-engine documents

### Code Changes (Pending)

- [ ] `models.py` - New EventType enum
- [ ] `models.py` - Simplify OccupancyEvent
- [ ] `engine.py` - Handle new event types
- [ ] `engine.py` - Remove confidence
- [ ] `engine.py` - Internal propagation
- [ ] `module.py` - Update event translation
- [ ] `module.py` - Remove confidence emission
- [ ] Tests - Update for v2

---

## Known Limitations

### Current (v1)

- Category-based pattern matching is hardcoded
- Confidence scoring is overly simple
- LOCK_CHANGE is a toggle (ambiguous)

### After v2

- **Integration burden**: Integrations must classify events
- **No confidence**: Can't express "maybe occupied"
- **Binary state**: No nuanced occupancy levels

---

## References

- **Design Decisions**: `occupancy-design-decisions.md` (v2 rationale)
- **Original Design**: `occupancy-design.md` (historical, needs update)
- **Integration Guide**: `occupancy-integration.md` (needs update)
- **Rule Engine Docs**: Archived (approach not used)

---

**Current Status**: v2 Design Approved ✅  
**Next Step**: Update remaining documentation, then implement code changes
