# Occupancy Rule Engine Design - Review Summary

**Date**: 2025.01.XX  
**Status**: Design Review Complete

---

## What I've Done

I've reviewed your Occupancy Module Design Specification (the rule-based engine you've been working on with Google Gemini) in the context of the entire home-topology project. Here's what I've created:

### 1. Comprehensive Design Document
**File**: `docs/modules/occupancy-rule-engine-design.md`

This document:
- ✅ Preserves your original specification
- ✅ Compares it with the current implementation
- ✅ Identifies 10 critical gaps that need addressing
- ✅ Provides recommendations for each gap
- ✅ Includes implementation considerations

### 2. Critical Gaps Analysis
**File**: `docs/modules/occupancy-rule-engine-gaps.md`

A focused document highlighting:
- **6 Critical Gaps** (must address before implementation)
- **4 Important Gaps** (should address during implementation)
- Prioritized action items
- Comparison table: Current vs Proposed

### 3. Updated Documentation Index
**File**: `README.md`

Added references to the new design documents in the Modules section.

---

## Key Findings

### ✅ What's Great About Your Design

1. **Flexibility**: Rule-based approach is much more flexible than current category-based system
2. **User Control**: Users can configure behavior without code changes
3. **Extensibility**: Easy to add new triggers/actions
4. **Clarity**: Rules are self-documenting

### ⚠️ Critical Gaps to Address

**Before Implementation**, you need to define:

1. **Event Translation** (HIGH PRIORITY)
   - How do platform events map to rule triggers?
   - Current: Hardcoded pattern matching
   - Needed: Explicit mapping mechanism

2. **State Machine Semantics** (HIGH PRIORITY)
   - How do actions interact with timers?
   - What happens when `set_occupied` called while already occupied?
   - How does `maintain` work exactly?

3. **Rule Conflict Resolution** (HIGH PRIORITY)
   - What if multiple rules match same event?
   - Need validation and priority rules

4. **Wasp-in-a-Box Logic** (MEDIUM PRIORITY)
   - Boolean flag mentioned but implementation not explained
   - Need to choose: rules-based or engine-level feature

5. **Hierarchy Interaction** (MEDIUM PRIORITY)
   - How do rules interact with parent/child propagation?
   - Document behavior clearly

6. **Migration Path** (MEDIUM PRIORITY)
   - How to migrate from current category-based config?
   - Need auto-migration tool

---

## Current vs Proposed Architecture

### Current Implementation
- **Event Types**: `MOMENTARY`, `HOLD_START`, `HOLD_END`, `MANUAL`, `LOCK_CHANGE`
- **Categories**: `motion`, `presence`, `door`, `media` (for timeout lookup)
- **Translation**: Hardcoded entity ID pattern matching
- **Config**: Simple timeout dictionary

### Your Proposed Design
- **Triggers**: `motion`, `clear`, `on`, `off`, `open`, `closed` (user-defined)
- **Actions**: `set_occupied`, `set_clear`, `maintain` (explicit state machine ops)
- **Rules**: Per-device, multiple rules per device
- **Config**: Device-centric with rule arrays

**Verdict**: Your approach is **architecturally superior** but needs the gaps filled in.

---

## Recommended Next Steps

### Phase 1: Design Refinement (1-2 weeks)

1. **Define Event Translation**
   - Create mapping table: entity types → triggers
   - Design override mechanism
   - Document entity naming conventions

2. **Specify State Machine**
   - Create state machine diagram
   - Document all state transitions
   - Define edge case behaviors

3. **Design Conflict Resolution**
   - Create validation schema
   - Define rule priority system
   - Document resolution strategy

4. **Document Wasp Logic**
   - Choose implementation approach
   - Document logic flow
   - Add to examples

### Phase 2: Migration Planning (1 week)

5. **Design Migration Strategy**
   - Create migration algorithm
   - Build migration function
   - Write migration guide

6. **Plan Hierarchy Integration**
   - Document hierarchy behavior
   - Add hierarchy examples
   - Test propagation scenarios

### Phase 3: Implementation (4-6 weeks)

7. Build rule engine core
8. Implement event translation layer
9. Create migration tool
10. Add validation & error handling
11. Write comprehensive tests

---

## Documents Created

1. **`docs/modules/occupancy-rule-engine-design.md`**
   - Complete design specification
   - Comparison with current implementation
   - All gaps identified with recommendations

2. **`docs/modules/occupancy-rule-engine-gaps.md`**
   - Focused gap analysis
   - Prioritized action items
   - Quick reference for implementation

3. **`README.md`** (updated)
   - Added references to new design docs

---

## What You Should Review

### Immediate Review (Before Implementation)

1. **Read**: `occupancy-rule-engine-gaps.md`
   - Focus on Critical Gaps (1-6)
   - Review recommendations
   - Decide on approaches

2. **Review**: `occupancy-rule-engine-design.md`
   - Section 8 (Gaps & Open Questions) - most important
   - Section 7 (Comparison) - understand differences
   - Section 9 (Implementation Considerations) - plan ahead

3. **Decide**:
   - Event translation approach (auto-detect vs explicit)
   - State machine semantics (exact behavior)
   - Conflict resolution strategy
   - Wasp-in-a-Box implementation

### Follow-up Actions

1. **Fill in the gaps** in your original spec
2. **Create state machine diagram** (visual representation)
3. **Design event translation mechanism** (mapping table)
4. **Write migration guide** (for existing users)

---

## Questions to Answer

Before implementation, you need to decide:

1. **Event Translation**: How exactly do platform events become rule triggers?
   - Auto-detect based on entity type?
   - Explicit mapping in config?
   - Hybrid approach?

2. **State Machine**: What's the exact behavior of each action?
   - `set_occupied` while already occupied → reset timer?
   - `maintain` → creates hold, clears timer?
   - `set_clear` with delay → sets separate timer?

3. **Conflicts**: How to handle multiple matching rules?
   - Validation error?
   - Rule order?
   - Action priority?

4. **Wasp Logic**: Rules-based or engine feature?
   - Can be implemented as special rules
   - Or as engine-level feature

5. **Migration**: How to convert existing configs?
   - Auto-migration tool?
   - Manual migration guide?
   - Support both formats?

---

## Summary

Your rule-based occupancy design is **excellent** and represents a significant improvement over the current implementation. However, there are **6 critical gaps** that need to be addressed before implementation:

1. Event translation mechanism
2. State machine semantics
3. Rule conflict resolution
4. Wasp-in-a-Box implementation
5. Hierarchy interaction
6. Migration path

I've documented all of these in detail with recommendations. The next step is to **review the gap analysis** and **fill in the missing details** in your original specification.

---

**Status**: Ready for Design Refinement  
**Priority**: Address gaps 1-3 before implementation begins  
**Estimated Timeline**: 2-3 weeks for design refinement, 4-6 weeks for implementation

