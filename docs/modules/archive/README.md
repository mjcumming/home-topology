# Archived Documentation

This folder contains documentation for approaches that were considered but **not implemented**.

## Archived Documents

### Rule-Based Engine (Not Implemented)

The following documents describe a rule-based event translation system that was proposed but not adopted:

- `occupancy-rule-engine-design.md` - Full rule engine design
- `occupancy-rule-engine-decisions.md` - Decision gaps and resolutions
- `occupancy-rule-engine-gaps.md` - Identified gaps in original design
- `occupancy-rule-engine-review.md` - Review of rule engine approach

### Why Not Implemented?

The v2.0 design chose a simpler approach:

1. **Integration-layer classification**: Signal classification happens in the integration layer, not the core library
2. **Six simple event types**: TRIGGER, HOLD, RELEASE, VACATE, LOCK, UNLOCK
3. **No confidence scoring**: Binary occupied/vacant is sufficient
4. **No secondary signals**: All signals treated equally

See `occupancy-design-decisions.md` for the full rationale.

---

**Archived**: 2025-01-27  
**Reason**: v2.0 design adopted simpler integration-layer approach

