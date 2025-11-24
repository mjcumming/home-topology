# Architecture Decision Records (ADR)

> Lightweight decision tracking for home-topology

**Purpose**: Track significant architectural and design decisions with context and rationale.

**Format**: Keep it simple, date-stamped, one decision per entry.

---

## Active Decisions

### ADR-001: Synchronous EventBus (2025-11-24)

**Status**: ✅ APPROVED

**Context**: 
- Need event routing between modules
- Options: sync vs async
- Expected load: 10-100 events/sec

**Decision**: 
EventBus is synchronous by default. Handlers are fast, CPU-bound. For I/O-heavy work, use `run_in_background()` helper.

**Consequences**:
- ✅ Simple, predictable execution
- ✅ Easy to debug
- ✅ No asyncio complexity
- ⚠️ Blocking handlers will stall bus (mitigated by try/except per handler)

**Alternatives Considered**:
- Async EventBus: Too complex for current needs
- Queue-based: Overkill for current scale

---

### ADR-002: Platform Independence (2025-11-24)

**Status**: ✅ APPROVED

**Context**:
- Core library should work without Home Assistant
- HA integration should be thin adapter layer

**Decision**:
Zero HA dependencies in `src/home_topology/`. HA integration lives in separate repo/package.

**Consequences**:
- ✅ Fully testable without HA
- ✅ Portable to other platforms
- ✅ Clean architecture
- ⚠️ Requires translation layer in HA integration

---

### ADR-003: Module Config Versioning (2025-11-24)

**Status**: ✅ APPROVED

**Context**:
- Modules will evolve over time
- Config schemas will change
- Need backward compatibility

**Decision**:
Each module has `CURRENT_CONFIG_VERSION` and `migrate_config()` method. Modules handle their own migrations.

**Consequences**:
- ✅ Modules can evolve independently
- ✅ Old configs remain loadable
- ✅ Migration logic lives with the module
- ⚠️ Developers must implement migration code

---

### ADR-004: Native Occupancy Integration (2025-11-24)

**Status**: ✅ APPROVED

**Context**:
- Have working occupancy_manager codebase
- Options: adapter layer vs native integration

**Decision**:
Native integration. Copy engine/models directly, wrap in LocationModule interface. No adapter/translation layer.

**Consequences**:
- ✅ Cleaner code
- ✅ Faster execution
- ✅ Easier to maintain
- ✅ Preserves all original features
- ⚠️ More initial refactoring work

**Alternatives Considered**:
- Adapter layer: Rejected (too much indirection)
- Rewrite from scratch: Rejected (proven code exists)

---

### ADR-005: Signal Role Separation (2025-11-24)

**Status**: ✅ APPROVED

**Context**:
- Need to prevent feedback loops (Actions → lights → Occupancy → Actions)
- Want to use lights as occupancy signal

**Decision**:
Separate signals into **primary** (direct triggers: motion, presence) and **secondary** (confidence boosters: lights, switches). Secondary signals adjust confidence but don't directly trigger occupancy.

**Consequences**:
- ✅ Prevents loops naturally
- ✅ Uses all available signals
- ✅ Nuanced confidence scoring
- ℹ️ Requires clear documentation for users

---

### ADR-006: Host-Controlled Timeout Scheduling (2025-11-24)

**Status**: ✅ APPROVED

**Context**:
- Occupancy engine needs periodic timeout checks
- Options: internal threading vs host-controlled
- Original occupancy_manager design is time-agnostic

**Decision**:
Module provides `get_next_timeout()` and `check_timeouts(now)` methods. Host integration (HA, test suite) is responsible for scheduling when to call them.

**Rationale**:
- ✅ Time-agnostic (fully testable - pass any `now` value)
- ✅ Host uses its own scheduler (HA async, test clock)
- ✅ No threading in module (simpler, cleaner)
- ✅ Matches original occupancy_manager design pattern

**Consequences**:
- ✅ Tests can control time exactly
- ✅ HA integration uses async_track_point_in_time()
- ✅ No background threads to manage
- ℹ️ Host must implement scheduling (documented in integration guide)

**Implementation**:
```python
# Module provides
def get_next_timeout(self, now=None) -> Optional[datetime]:
    """Returns when host should schedule next check."""
    
def check_timeouts(self, now=None) -> None:
    """Host calls this at scheduled time."""

# HA Integration uses
next_check = occupancy.get_next_timeout()
if next_check:
    async_track_point_in_time(hass, check_callback, next_check)
```

---

### ADR-007: Module-Specific Design Docs (2025-11-24)

**Status**: ✅ APPROVED

**Context**:
- DESIGN.md getting too long (680 lines)
- Mixing architecture with implementation details

**Decision**:
Split docs:
- `DESIGN.md` - Architecture only (~590 lines)
- `docs/modules/occupancy-design.md` - Occupancy implementation
- `docs/modules/actions-design.md` - Actions implementation

**Consequences**:
- ✅ Easier to navigate
- ✅ Modules can evolve docs independently
- ✅ Clear separation of concerns
- ⚠️ More files to maintain

---

### ADR-007: Entities Don't Require Areas (2025-11-24)

**Status**: ✅ APPROVED

**Context**:
- Some users have HA Areas, some don't
- Advanced setups have entities without Areas
- Need flexibility

**Decision**:
Entities can be assigned to Locations with or without HA Areas. `ha_area_id` is optional and used for convenience/discovery only.

**Consequences**:
- ✅ Works with "Areas done right" setups
- ✅ Doesn't punish advanced setups
- ✅ Provides "Inbox" workflow
- ℹ️ Integration must handle both cases

---

## Pending Decisions

### PENDING: License Selection

**Status**: 🟡 NEEDS DECISION

**Options**:
1. MIT - Very permissive, simple
2. Apache 2.0 - Patent protection, corporate-friendly
3. GPL v3 - Copyleft, requires derivatives be open

**Recommendation**: MIT (simple, widely accepted)

**Next Steps**: Discuss and decide

---

### PENDING: Package Name

**Status**: 🟡 NEEDS DISCUSSION

**Context**:
- Original spec: `location_manager`
- Current implementation: `home_topology`

**Options**:
1. Keep `home_topology` (more descriptive)
2. Change to `location_manager` (matches original spec)

**Recommendation**: Keep `home_topology`

**Next Steps**: Review and confirm

---

### PENDING: CI/CD Platform

**Status**: 🟡 NEEDS DECISION

**Options**:
1. GitHub Actions (integrated)
2. GitLab CI (if using GitLab)
3. CircleCI (powerful but extra service)

**Recommendation**: GitHub Actions

**Next Steps**: Create `.github/workflows/ci.yml`

---

## Rejected Decisions

### REJECTED: Adapter Layer for Occupancy

**Status**: ❌ REJECTED

**Context**: How to integrate occupancy_manager

**Decision**: Use native integration instead

**Reason**: Too much indirection, no real benefit

**Date**: 2025-11-24

---

## How to Use This Log

### When to Create an ADR
- Significant architectural decision
- Affects multiple components
- Has long-term implications
- Non-obvious trade-offs

### When NOT to Create an ADR
- Implementation details
- Temporary workarounds
- Obvious choices

### ADR Template

```markdown
### ADR-XXX: Title (YYYY-MM-DD)

**Status**: 🟡 PROPOSED | ✅ APPROVED | ❌ REJECTED

**Context**:
What's the situation? What problem are we solving?

**Decision**:
What did we decide to do?

**Consequences**:
- ✅ Positive outcomes
- ⚠️ Risks or downsides
- ℹ️ Neutral facts

**Alternatives Considered**:
- Option A: Why not?
- Option B: Why not?
```

---

**Maintainer**: Project team  
**Review Frequency**: As decisions are made  
**Location**: `/ADR-LOG.md` (root of project)

