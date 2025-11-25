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

### ADR-005: Integration-Driven Event Classification (2025-11-25)

**Status**: ✅ APPROVED (Supersedes original primary/secondary design)

**Context**:
- Need to prevent feedback loops (Actions → lights → Occupancy → Actions)
- Original design had primary/secondary signals with weighted confidence
- Simplified design dropped confidence scoring

**Decision**:
The **integration layer** (not the core library) decides which entities send occupancy events. Core library simply processes events it receives. Loop prevention is achieved by not configuring "output" devices (lights, switches) to send events.

**Consequences**:
- ✅ Simpler - no confidence scoring or event weights
- ✅ Prevents loops by integration configuration
- ✅ Core library stays platform-agnostic
- ✅ Integration has full control over what affects occupancy
- ℹ️ Requires integration to be thoughtfully configured

**Supersedes**: Original primary/secondary signal design (see `docs/modules/occupancy-design-decisions.md` Decision 4)

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
- `docs/architecture.md` - Architecture only (~590 lines)
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

### ADR-008: Module Enable/Disable Granularity (2025-11-24)

**Status**: ✅ APPROVED

**Context**:
- Need to decide if modules can be enabled/disabled per-location or globally
- Options: per-location enable vs global enable

**Decision**:
Modules are enabled **globally**, not per-location. When Occupancy is on, it processes all locations. Per-location *configuration* (timeouts, sensor rules) still exists.

**Consequences**:
- ✅ Simpler mental model ("Occupancy is on" means everywhere)
- ✅ Users configure behavior per-location, not existence
- ✅ Less UI complexity
- ℹ️ Can't disable occupancy for just one room

---

### ADR-009: "Unassigned" is UI Concept (2025-11-24)

**Status**: ✅ APPROVED

**Context**:
- Need to handle locations/areas without parents
- Options: special Location object vs virtual UI concept

**Decision**:
"Unassigned" is NOT a real Location in the kernel. The UI/integration queries "locations with no parent" and displays them under a virtual "Unassigned" header.

**Consequences**:
- ✅ Keeps kernel clean
- ✅ Presentation logic stays in UI
- ✅ No special cases in core
- ℹ️ UI must implement the virtual grouping

---

### ADR-010: Event Normalization in Integration Layer (2025-11-24)

**Status**: ✅ APPROVED

**Context**:
- Core library needs events but shouldn't know about HA entity patterns
- Need platform-agnostic approach

**Decision**:
Event normalization happens in the integration layer. Core library expects normalized events (sensor_type + event name). Integration translates platform-specific events (e.g., `binary_sensor.kitchen_motion` state change) into normalized format.

**Consequences**:
- ✅ Core stays platform-agnostic
- ✅ Consistent event handling
- ✅ Easy to add new platforms
- ⚠️ Integration layer has more work

---

### ADR-011: Actions Module "Generator" Pattern (2025-11-24)

**Status**: ✅ APPROVED

**Context**:
- Need to execute automations when occupancy changes
- Options: build our own automation engine vs generate native platform automations

**Decision**:
Actions module generates rule definitions. Integration takes those definitions and creates native platform automations (e.g., HA automation entities). We don't build a secondary automation engine.

**Consequences**:
- ✅ Users can debug with standard platform tools (HA Traces)
- ✅ Don't reinvent trigger/condition/action logic
- ✅ Prevents infinite loops (separation of concerns)
- ⚠️ Requires integration to implement automation creation

**Status**: Placeholder - detailed design pending.

---

### ADR-012: Continuous Sync via Integration (2025-11-24)

**Status**: ✅ APPROVED

**Context**:
- Platform may add new areas/rooms/entities
- Need to keep our topology updated

**Decision**:
Integration maintains continuous synchronization. Inbound: platform changes → integration updates our topology. Outbound: our changes → integration emits events, decides whether to update platform.

**Consequences**:
- ✅ New platform areas appear in our system
- ✅ Core library stays clean
- ✅ Integration controls sync logic
- ⚠️ Potential for divergence if sync isn't handled well

---

### ADR-013: MIT License (2025-11-24)

**Status**: ✅ APPROVED

**Context**:
- Need to choose an open source license
- Options: MIT, Apache 2.0, GPL v3

**Decision**:
MIT License - simple, permissive, widely accepted.

**Consequences**:
- ✅ Maximum adoption potential
- ✅ Simple to understand
- ✅ Compatible with most other licenses
- ℹ️ No patent protection (acceptable for this project)

---

### ADR-014: Package Name `home-topology` (2025-11-24)

**Status**: ✅ APPROVED

**Context**:
- Original spec suggested `location_manager`
- Current implementation uses `home_topology`

**Decision**:
Keep `home-topology` as the package name.

**Consequences**:
- ✅ More descriptive of full system
- ✅ Marketable name
- ✅ Already established in 25+ files
- ℹ️ Python package is `home_topology` (underscore required)

---

### ADR-015: GitHub Actions for CI/CD (2025-11-24)

**Status**: ✅ APPROVED

**Context**:
- Need CI/CD for automated testing and releases
- Options: GitHub Actions, GitLab CI, CircleCI

**Decision**:
Use GitHub Actions with workflows for CI (`ci.yml`) and releases (`release.yml`).

**Consequences**:
- ✅ Integrated with GitHub (no extra service)
- ✅ Free for open source
- ✅ Well documented
- ✅ Already implemented

---

### ADR-016: Skip LocationType - Hierarchy IS the Semantic Structure (2025-11-25)

**Status**: ✅ APPROVED

**Context**:
- Considered adding `LocationType` enum (BUILDING, FLOOR, ROOM, ZONE, etc.)
- Could provide semantic richness for defaults and validation
- Magic Areas uses minimal typing (just interior/exterior)

**Decision**:
**Do not add LocationType to the kernel.** The location hierarchy itself provides semantic structure.

**Rationale**:
1. **Hierarchy IS the grouping mechanism**: User creates "Upstairs" → all children aggregate to it
2. **Platform-agnostic**: "room" and "floor" are HA concepts; other platforms may differ
3. **User-specific**: Some users think in floors, others in wings, others in functional zones
4. **Module-specific**: If occupancy cares about "zone vs room", it can have its own config
5. **No validation nightmare**: Don't need to enforce "floor can't be under room" (lofts exist!)
6. **Magic Areas validates this**: They get by with just interior/exterior, not a rich taxonomy

**Consequences**:
- ✅ Kernel stays simple (just the tree)
- ✅ Users aren't forced into our ontology
- ✅ Modules can define their own type semantics if needed
- ℹ️ No "get all rooms" query in kernel (use hierarchy instead)

**Alternatives Considered**:
- LocationType enum: Too prescriptive, kernel doesn't use it
- Tags/labels: Could add later if needed, but not required now

---

### ADR-017: Root vs Unassigned Disambiguation (2025-11-25)

**Status**: ✅ APPROVED

**Context**:
- `parent_id = None` is ambiguous:
  - Could mean "intentional top-level" (House, Garage)
  - Could mean "discovered, needs organizing" (Inbox)
- Options: `is_root` flag vs integration tracking vs LocationType

**Decision**:
Add `is_explicit_root: bool` to Location model.

```python
@dataclass
class Location:
    parent_id: Optional[str] = None
    is_explicit_root: bool = False  # True = intentional root
```

**Semantics**:
| `parent_id` | `is_explicit_root` | Meaning |
|-------------|-------------------|---------|
| `None` | `True` | Intentional root (House, Garage) |
| `None` | `False` | Unassigned/discovered (Inbox) |
| `some_id` | `False` | Normal nested location |
| `some_id` | `True` | Invalid (has parent, can't be root) |

**Consequences**:
- ✅ Kernel is self-describing (can query roots vs unassigned)
- ✅ Simple boolean, minimal API change
- ✅ Integration imports HA areas as `is_explicit_root=False`
- ✅ User creates roots as `is_explicit_root=True`
- ✅ User can promote discovered location to root

**Alternatives Considered**:
- Integration tracks discovered IDs: Two sources of truth, more complex
- LocationType.DISCOVERED: Conflates "what it is" with "where it came from"

---

### ADR-018: Remove LocationKind from Occupancy Module (2025-11-25)

**Status**: ✅ APPROVED

**Context**:
- Occupancy module had `LocationKind` enum (AREA, VIRTUAL)
- Was leftover from earlier design, never used in logic
- Always defaulted to `AREA`

**Decision**:
Remove `LocationKind` entirely from the occupancy module.

**Rationale**:
1. Never used to change behavior
2. Behavioral distinctions already captured by:
   - `OccupancyStrategy` (independent vs follow_parent)
   - `contributes_to_parent` (whether occupancy bubbles up)
3. If a location needs "virtual" behavior, configure it via module settings

**Consequences**:
- ✅ Cleaner model
- ✅ Less confusion about unused fields
- ✅ Behavior is expressed through config, not type

---

### ADR-019: Integration Layer Responsibilities (2025-11-25)

**Status**: ✅ APPROVED

**Context**:
- Need clear division between kernel and integration layer
- Discussion around sync, conflict handling, entity creation

**Decision**:
Define explicit integration layer responsibilities:

**Integration Layer Owns**:
1. **Sync**: Bidirectional sync between platform (HA) and kernel
2. **Discovery**: Import platform floors/areas as locations
3. **Conflict Handling**: When platform and kernel disagree, integration decides
4. **Entity Creation**: Create platform entities for kernel state (e.g., `binary_sensor.kitchen_occupied`)
5. **Event Classification**: Map platform events to normalized kernel events
6. **Timeout Scheduling**: Call `check_timeouts()` at appropriate times

**Kernel Owns**:
1. **Tree Structure**: Store and query location hierarchy
2. **Module State**: Occupancy, actions, etc.
3. **Event Processing**: Handle normalized events
4. **State Export/Import**: `dump_state()` / `restore_state()`

**Sync Model**:
- HA creates area → Integration creates Location (`is_explicit_root=False`)
- User organizes in our UI → Integration can sync back to HA (optional)
- Conflicts handled by integration (e.g., "we win" or "show user")

**Consequences**:
- ✅ Clear boundaries
- ✅ Kernel stays platform-agnostic
- ✅ Integration has flexibility
- ℹ️ Integration layer has more responsibility

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
**Location**: `/docs/adr-log.md`

