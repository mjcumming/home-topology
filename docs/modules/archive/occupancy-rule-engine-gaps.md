# Occupancy Rule Engine - Critical Gaps & Recommendations

**Status**: Analysis Complete  
**Date**: 2025.01.XX

---

## Executive Summary

Your rule-based occupancy design is a **significant architectural improvement** over the current category-based approach. It provides flexibility, user control, and extensibility. However, there are **10 critical gaps** that need to be addressed before implementation.

---

## Critical Gaps (Must Address)

### 1. ✅ Event Translation Mechanism (RESOLVED)

**Gap**: How do platform events map to rule triggers?

**Resolution**: Event normalization is an **integration layer responsibility**.

The core library expects normalized events with sensor types and event names. It does NOT know about Home Assistant entity patterns.

**Normalized Event Format**:

| Sensor Type | Events |
|-------------|--------|
| `motion_sensor` | `motion`, `clear` |
| `contact_sensor` | `open`, `closed` |
| `switch` | `on`, `off` |
| `light` | `on`, `off`, `brightness_changed` |
| `media_player` | `playing`, `paused`, `idle`, `off`, `volume_changed` |
| `person` | `home`, `away` |
| `power_sensor` | `consuming`, `idle` |

**Integration Responsibility**: The HA integration translates HA-specific events to this format. For example:
- `binary_sensor.kitchen_motion` state `on` → `{sensor_type: "motion_sensor", event: "motion"}`
- `light.kitchen` state `on` → `{sensor_type: "light", event: "on"}`

**Action Items**:
- [x] Define normalized event format
- [x] Document that translation is integration responsibility
- [x] Core library stays platform-agnostic

---

### 2. ⚠️ State Machine Semantics (HIGH PRIORITY)

**Gap**: Unclear how actions interact with timers and each other

**User Clarification**:
- **Motion events**: Give X minutes of occupancy (e.g., 10 min). Room stays occupied, timer just resets. Not creating new state, just extending.
- **Maintain**: Overrides everything (like a perfect presence sensor). When maintain is active, timers/events don't matter. Maintain will have a delay once the event goes away (e.g., door closes, media stops).
- **Question**: What does "set_clear with delay" mean? (Needs clarification)

**Recommendation**: Define explicit state machine based on user vision:

```
State: {
  occupied: bool,
  timer: datetime | null,
  holds: Set[str]  // Device IDs with active "maintain"
}

Actions:
- set_occupied(timeout):
  → Set occupied = true
  → Reset timer = now + timeout (even if already occupied)
  → Do NOT clear holds (maintain takes precedence)
  → If already occupied, this just extends the timer
  
- set_clear(delay):
  → If delay > 0: Set timer = now + delay, keep occupied = true (grace period)
    Example: Light turns off → wait 2 min before clearing (in case person is still there)
  → If delay == 0: Set occupied = false, clear timer, clear holds (immediate clear)
  → Note: If maintain is active, this may be ignored or queued
  → **Clarification Needed**: Is this the intended behavior, or should it work differently?
  
- maintain(device_id):
  → Add device_id to holds
  → Set occupied = true
  → Clear timer (no timeout while maintained - timers don't matter)
  → When maintain condition ends (e.g., door opens, media stops):
    → Remove device_id from holds
    → If no other holds: Apply delay (if configured), then allow timer to resume
    → If other holds remain: Keep occupied, keep timer cleared
```

**Key Behaviors**:
- **Timer Reset on Motion**: `set_occupied` always resets timer, even if already occupied
- **Maintain Override**: When any hold is active, timer is cleared and doesn't count down
- **Maintain Delay**: When maintain ends, there may be a delay before clearing (e.g., 2 min after door opens)
- **State Persistence**: Room stays occupied until timer expires (if no holds) or `set_clear(0)` is called

**Action Items**:
- [ ] Create state machine diagram
- [ ] Document all state transitions
- [ ] Define maintain delay behavior (how is delay configured?)
- [ ] Clarify `set_clear` with delay semantics

---

### 3. ⚠️ Rule Conflict Resolution (HIGH PRIORITY)

**Gap**: What if multiple rules match the same event?

**Example Conflict**:
```json
{
  "entity_id": "light.kitchen",
  "rules": [
    {"trigger": "on", "action": "set_occupied", "parameter": 60},
    {"trigger": "on", "action": "set_clear", "parameter": 0}  // Conflict!
  ]
}
```

**User Question**: Not sure if the UI would allow conflicting rules to be created. Need to determine if this is a real problem or prevented by UI design.

**Recommendation**: 
- **UI Prevention**: If possible, prevent conflicting rules in the UI (e.g., only allow one rule per trigger per device)
- **Validation**: If UI allows it, validate and prevent conflicting rules at config time
- **Tiebreaker** (if conflicts still possible): 
  - Use rule order (first wins)
  - Action Priority as secondary: `maintain` > `set_occupied` > `set_clear`
- **Alternative**: Allow multiple rules but combine actions logically (e.g., both `set_occupied` and `set_clear` → use higher priority)

**Action Items**:
- [ ] Determine if UI will prevent conflicts
- [ ] Design validation schema (if needed)
- [ ] Implement conflict detection (if needed)
- [ ] Document resolution strategy

---

### 4. ⚠️ Wasp-in-a-Box Implementation (MEDIUM PRIORITY)

**Gap**: Boolean flag mentioned but logic not explained

**Current Spec**: "waspInABox: true" but no implementation details

**User Note**: More details to come in next response

**Recommendation**: Implement as special rules OR as engine-level feature

**Option A - Rules-Based**:
```json
{
  "entity_id": "binary_sensor.kitchen_door",
  "rules": [
    {"trigger": "open", "action": "set_occupied", "parameter": 5},
    {"trigger": "closed", "action": "maintain", "parameter": null}
  ]
}
```

**Option B - Engine Feature**:
- Special "wasp" mode that creates holds on door close
- Requires both door sensor AND motion sensor configured

**Action Items**:
- [ ] Wait for user clarification on wasp-in-a-box requirements
- [ ] Choose implementation approach
- [ ] Document wasp logic flow
- [ ] Add to examples/recipes

---

### 5. ⚠️ Hierarchy Interaction (MEDIUM PRIORITY)

**Gap**: How do rules interact with parent/child propagation?

**Questions**:
- Do child rules affect parent occupancy?
- Can parent rules override child rules?
- How does `maintain` propagate?

**Recommendation**: 
- Rules operate on target location only
- Propagation happens after rule evaluation (same as current)
- Document: Child occupancy → parent (if `contributes_to_parent`)
- Document: Parent rules don't affect children

**Action Items**:
- [ ] Document hierarchy behavior
- [ ] Add hierarchy examples
- [ ] Test propagation scenarios

---

### 6. ⚠️ Configuration Migration (MEDIUM PRIORITY)

**Gap**: No migration path from current category-based config

**Current Config**:
```json
{
  "timeouts": {"motion": 300, "door": 120}
}
```

**Proposed Config**:
```json
{
  "devices": [{
    "entity_id": "*motion*",
    "rules": [{"trigger": "motion", "action": "set_occupied", "parameter": 5}]
  }]
}
```

**Recommendation**: 
- Auto-migration tool that converts category config → rules
- Support both formats during transition
- Provide migration script/function

**Action Items**:
- [ ] Design migration algorithm
- [ ] Implement migration function
- [ ] Create migration guide

---

## Important Gaps (Should Address)

### 7. UI/UX Design

**Gap**: No specification for rule configuration interface

**Needs**:
- Visual rule builder (if-then interface)
- Device selector with search/filter
- Trigger/action dropdowns
- Parameter inputs
- Rule templates/recipes
- Testing/preview mode

**Action Items**:
- [ ] Create UI mockups
- [ ] Design rule builder interface
- [ ] Document UX flows

---

### 8. Performance & Scalability

**Gap**: No performance characteristics defined

**Questions**:
- How many rules per location?
- Rule evaluation performance?
- Caching strategies?

**Recommendation**:
- Index rules by `device_id` for O(1) lookup
- Limit rules per device (e.g., max 10)
- Cache compiled rule evaluators
- Benchmark with realistic scenarios

**Action Items**:
- [ ] Define performance targets
- [ ] Design indexing strategy
- [ ] Create performance tests

---

### 9. Error Handling & Validation

**Gap**: Missing error scenarios and handling

**Needs**:
- Schema validation (JSON schema)
- Semantic validation (conflicting rules)
- Runtime error handling
- Logging/alerting

**Action Items**:
- [ ] Define error types
- [ ] Design validation schema
- [ ] Document error handling

---

### 10. Examples & Recipes

**Gap**: Need more real-world examples

**Missing**:
- Complex multi-device scenarios
- Edge cases
- Common patterns beyond the 4 provided

**Action Items**:
- [ ] Add 5-10 more recipe examples
- [ ] Document edge cases
- [ ] Create troubleshooting guide

---

## Recommendations Summary

### Immediate (Before Implementation)

1. ✅ **Define Event Translation** - How platform events → triggers
2. ✅ **Specify State Machine** - Complete state transition logic
3. ✅ **Design Conflict Resolution** - Rule priority and validation
4. ✅ **Document Wasp Logic** - Implementation details
5. ✅ **Plan Migration** - Category-based → rule-based path

### Short-term (During Implementation)

6. Design UI/UX for rule configuration
7. Implement performance optimizations
8. Add comprehensive error handling
9. Create migration tool

### Long-term (Polish)

10. Build rule templates/recipes library
11. Add rule testing/preview mode
12. Performance benchmarking
13. User documentation

---

## Comparison: Current vs Proposed

| Aspect | Current (Category-Based) | Proposed (Rule-Based) |
|--------|---------------------------|----------------------|
| **Flexibility** | Limited (hardcoded patterns) | High (user-defined rules) |
| **Complexity** | Low (simple config) | Medium (more config) |
| **User Control** | Low (code changes needed) | High (fully configurable) |
| **Migration** | N/A | Required (from current) |
| **Performance** | Fast (O(1) category lookup) | Fast (O(1) device lookup) |
| **Extensibility** | Low (code changes) | High (new triggers/actions) |

**Verdict**: Rule-based approach is **worth the migration** for long-term flexibility and user control.

---

## Next Steps

1. **Review this analysis** with team
2. **Address Critical Gaps** (1-6) before implementation
3. **Create detailed design** for state machine and event translation
4. **Build prototype** to validate approach
5. **Document migration path** for existing users

---

**Status**: Ready for Design Refinement  
**Priority**: Address gaps 1-3 before implementation begins

