# Work Tracking - home-topology Project

**Last Updated**: 2026-02-23

---

## Current Scope

`home-topology` is the **core, platform-agnostic library**.

- In scope: topology kernel, modules (occupancy/automation/lighting/presence/ambient), tests, and core docs
- Out of scope: Home Assistant adapter implementation and HA UI/panel code
- Integration work should live in a separate repository/package

---

## Status Dashboard

### Completed

#### Core Kernel
- [x] Location dataclass with hierarchy
- [x] LocationManager with graph queries
- [x] EventBus with filtering and error isolation
- [x] Module protocol and event model
- [x] Alias support
- [x] Batch entity operations
- [x] Topology mutation events from `LocationManager`
- [x] Canonical sibling ordering support

#### Occupancy Module (v3)
- [x] Canonical v3 model (`TRIGGER` + `CLEAR`, per-source contributions)
- [x] Commands (`VACATE`, `LOCK`, `UNLOCK`, `UNLOCK_ALL`)
- [x] Strict `FOLLOW_PARENT` behavior
- [x] Parent/child propagation invariant fixed
- [x] Host-controlled timeout checking (time-agnostic)
- [x] Stable transition reason contract
- [x] State export/restore robustness improvements

#### Other Modules
- [x] Automation engine and layered module architecture
- [x] Lighting module presets
- [x] Presence module (registry, movement, events, persistence)
- [x] Ambient light module (hierarchical lookup)

#### Documentation and ADRs
- [x] v3 occupancy docs aligned with implementation
- [x] ADR updates for occupancy v3 canonical model and topology-mutation rebuild behavior
- [x] Documentation scope policy defined (keep library integration guides; move adapter-implementation docs)
- [x] HA adapter implementation docs removed from core repo integration folder
- [x] Integration folder now limited to library-usage guides + scope README

### In Progress

None currently

### Planned (Core Library)

- [x] Full repo test run in clean CI-like environment (2026-02-23)
- [x] Additional invariant/property-style tests for occupancy event interleavings (2026-02-23)
- [x] Performance sanity checks for typical home-scale trees (2026-02-23)

---

## Known Issues

### High Priority
- None

### Medium Priority
- None

### Low Priority
- None

---

## Progress Snapshot

- Architecture: complete
- Core kernel: complete
- Occupancy: v3 complete (targeted suite green: 28 tests)
- Automation: complete
- Lighting: complete
- Presence: complete
- Ambient: complete
- HA adapter in this repo: intentionally out of scope

### Validation Snapshot (2026-02-23)

- Full test suite (clean plugin mode): `259 passed, 1 warning`
- Occupancy interleaving invariants added and passing:
  - parent/child occupancy invariant across event-order permutations
  - strict `FOLLOW_PARENT` invariant across event-order permutations
- Occupancy performance sanity (engine micro-benchmark):
  - 25 locations, 10,000 events: `35.84 us/event` (total `358.42 ms`)
  - 75 locations, 20,000 events: `151.49 us/event` (total `3029.76 ms`)
  - 200 locations, 40,000 events: `518.99 us/event` (total `20759.78 ms`)

---

## Key Decisions (Recent)

- Occupancy v3 is canonical; no v2 compatibility layer in core (pre-alpha)
- Occupancy reasons use a stable contract
- Occupancy rebuilds from topology mutation events while preserving runtime state
- `LocationManager` is the canonical source for topology mutation events
- Documentation boundary is explicit: keep library integration guides in core, move HA implementation docs to adapter repo

See: `docs/adr-log.md` (ADR-011, ADR-012, ADR-025, ADR-026, ADR-027)

---

**Status**: Active
**Owner**: Mike
