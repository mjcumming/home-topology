# Work Tracking - home-topology Project

**Last Updated**: 2025-11-26

---

## 🎯 Current Sprint: Foundation & Occupancy Module

**Sprint Goal**: Establish kernel architecture and working occupancy module  
**Dates**: Started 2025-11-24  
**Status**: 🟢 ON TRACK

---

## 📊 Work Status Dashboard

### ✅ Completed

#### Kernel Architecture (100%)
- [x] Location dataclass with hierarchy
- [x] LocationManager with graph queries
- [x] EventBus with filtering
- [x] LocationModule protocol
- [x] Event model with timestamp
- [x] Error isolation (try/except per handler)
- [x] Alias support (2025.12.09)
- [x] Batch entity operations (2025.12.09)

#### Documentation (100%)
- [x] Architecture spec (v1.6) - Complete
- [x] Coding standards - Complete
- [x] Contributing guide - Complete
- [x] Module design docs (occupancy, automation)
- [x] Project overview
- [x] Integration guide - Complete
- [x] HA sync and services guide (2025.12.09)

#### Development Infrastructure (100%)
- [x] Makefile with dev commands
- [x] pyproject.toml configuration
- [x] .gitignore
- [x] Test framework structure
- [x] Example scripts
- [x] PR template (.github/pull_request_template.md)
- [x] CI/CD pipeline (.github/workflows/ci.yml)
- [x] Date validation script (scripts/check-dates.sh)

#### OccupancyModule (100%)
- [x] Native integration (no adapter)
- [x] Engine ported (453 lines)
- [x] Models ported (182 lines)
- [x] Module wrapper (clean, no threading)
- [x] EventBus integration
- [x] Host-controlled timeout checking (time-agnostic)
- [x] State persistence
- [x] Identity tracking
- [x] Hierarchy propagation
- [x] Working demo with timeout examples
- [x] Comprehensive tests (88 tests passing)
- [x] `get_effective_timeout()` - true timeout considering descendants
- [x] `vacate_area()` - cascading vacate command

#### Testing (100%)
- [x] OccupancyModule integration tests
- [x] Engine timeout expiration tests
- [x] FOLLOW_PARENT strategy tests
- [x] Lock/unlock tests
- [x] Config migration tests
- [x] Effective timeout tests
- [x] Vacate area (cascading) tests

---

### 🔨 In Progress

*None currently - Automation refactor complete*

---

### 📅 Planned (Next Sprint)

#### Automation Engine (100%) ✅ (Refactored from ActionsModule)
- [x] Rule structure implementation (AutomationRule, triggers, conditions, actions)
- [x] Trigger system (event, state, time triggers)
- [x] Condition evaluation (time of day, lux level, entity state, day of week)
- [x] Action execution (service calls, delays)
- [x] Platform adapter interface (with MockPlatformAdapter for testing)
- [x] Renamed from `actions/` to `automation/` (layered architecture)
- [x] Tests (59 tests passing)

#### Lighting Module (100%) ✅ (New - split from ActionsModule)
- [x] Lighting-specific presets moved from actions
- [x] `lights_on_when_occupied()` preset
- [x] `lights_off_when_vacant()` preset
- [x] `scene_when_occupied()` preset
- [x] `adaptive_lighting()` preset (time-based brightness)
- [x] Tests (14 tests passing)

#### Presence Module (100%) ✅ (New - 2025.12.09)
- [x] Person data model
- [x] Person registry (CRUD operations)
- [x] Device tracker management (add/remove dynamically)
- [x] Location queries (who's where, where is who)
- [x] Person movement tracking
- [x] `presence.changed` events
- [x] State persistence (dump/restore)
- [x] Tests (33 tests passing)

#### Module Architecture (100%) ✅
- [x] Layered architecture: domain modules use automation engine
- [x] Backwards compatibility shim for `actions/` imports
- [x] Architecture documentation (`docs/modules/automation-architecture.md`)

#### Home Assistant Integration (0%)
- [ ] Separate repository setup
- [ ] Entity → Event translation
- [ ] Module state → HA entities
- [ ] Discovery/auto-creation
- [ ] Inbox UI for unassigned entities

#### UI Design (10%)
- [x] Initial mockup in Gemini Canvas
- [x] UI design spec document (docs/ui/ui-design.md)
- [ ] Component refinement in Gemini Canvas
- [ ] Finalize interaction patterns
- [ ] HA panel implementation planning

---

### 🚫 Blocked

**None currently**

---

## 🐛 Known Issues

### High Priority
**None**

### Medium Priority
1. **Timeout tests require time mocking** - Need to mock datetime for fast tests
2. **Python 3.11+ syntax** - Models use `str | None` (3.10+ required, document this)

### Low Priority
**None**

---

## 💬 Open Questions (See decisions-pending.md)

High priority questions needing decisions:
1. **License** - MIT, Apache 2.0, or GPL?
2. **CI/CD** - GitHub Actions setup?
3. **Package name** - Keep `home_topology` or change to `location_manager`?

Full list: See [decisions-pending.md](./decisions-pending.md)

---

## 📈 Progress Metrics

### Overall Project
- **Completion**: ~75%
- **Architecture**: 100% ✅
- **Core Kernel**: 100% ✅
- **OccupancyModule**: 100% ✅
- **AutomationEngine**: 100% ✅
- **LightingModule**: 100% ✅
- **PresenceModule**: 100% ✅
- **HA Integration**: 0% ⚪

### Code Stats
- **Total Lines**: ~10,500 (code + docs)
- **Core Kernel**: ~800 lines (with aliases, batch ops)
- **OccupancyModule**: ~1,126 lines
- **AutomationEngine**: ~1,200 lines
- **LightingModule**: ~300 lines
- **PresenceModule**: ~350 lines
- **Tests**: ~5,500 lines (175 tests total)
- **Documentation**: ~3,500 lines

### Test Coverage
- **Core**: ~90% (32 tests with aliases and batch ops)
- **Occupancy**: ~98% (88 tests, comprehensive suite)
- **Automation**: ~95% (59 tests, comprehensive suite)
- **Lighting**: ~95% (14 tests, comprehensive suite)
- **Presence**: ~95% (33 tests, comprehensive suite)

---

## 🔮 Future Features (Designed, Not Implemented)

### Integrity Validation
**Target**: v0.3.0  
**Status**: Designed (2025.12.09)  
**Design Doc**: `docs/integration/integrity-validation.md`

- Automatic topology validation
- Broken reference detection (parent doesn't exist, circular refs)
- Orphaned entity detection
- HA repair system integration
- Auto-repair capabilities
- Services: `validate_integrity`, `auto_repair_topology`

---

## 📝 Decision Log

Track major decisions here with date and rationale.

### 2025-11-24

#### Decision: Host-Controlled Timeout Scheduling
- **Context**: How to handle periodic timeout checks for occupancy
- **Decision**: Module provides get_next_timeout() and check_timeouts(now), host schedules
- **Rationale**: Time-agnostic testing, matches original design, no threading in module
- **Approved By**: Mike
- **Impact**: Medium (affects HA integration design)
- **See**: ADR-006 in adr-log.md

#### Decision: Native Integration (No Adapter)
- **Context**: How to integrate occupancy_manager
- **Decision**: Native integration, no adapter/translation layer
- **Rationale**: Cleaner, faster, fewer layers, easier to maintain
- **Approved By**: Mike
- **Impact**: High (affects all future modules)
- **See**: ADR-004 in adr-log.md

#### Decision: Module-Specific Design Docs
- **Context**: Where to document module implementation details
- **Decision**: Separate docs in `docs/modules/` per module
- **Rationale**: Keep architecture.md focused on architecture, modules can evolve independently
- **Approved By**: Team discussion
- **Impact**: Medium (better organization)

#### Decision: home_topology Package Name
- **Context**: Original spec suggested `location_manager`
- **Decision**: Keep `home_topology` (more descriptive)
- **Rationale**: More marketable, describes full system not just one component
- **Approved By**: Discussion needed (see decisions-pending.md)
- **Impact**: Low (name already established in 25+ files)

### 2025.12.09

#### Decision: Remove Confidence from Occupancy
- **Context**: Occupancy initially had confidence scoring (0.0-1.0)
- **Decision**: Binary only - occupied (True/False), no confidence
- **Rationale**: No clear use case after years of experience - you either act or don't
- **Approved By**: Mike
- **Impact**: Medium (simplifies occupancy logic)
- **See**: ADR-021 in adr-log.md

#### Decision: No Event Coordination Between Modules
- **Context**: Occupancy fires immediately, presence fires 2-5s later
- **Decision**: Modules emit independently, no artificial delays or coordination
- **Rationale**: 90% of automations don't need person ID, user can choose to wait
- **Approved By**: Mike
- **Impact**: High (affects module independence)
- **See**: ADR-022 in adr-log.md
- **Patterns**: Sequential override, optional wait, or ignore presence

#### Decision: PresenceModule as Separate Module
- **Context**: Need "who is where?" tracking in addition to "is occupied?"
- **Decision**: Separate module with Person registry, independent from occupancy
- **Rationale**: Different detection methods, different use cases, optional feature
- **Approved By**: Mike
- **Impact**: Medium (new module)
- **See**: ADR-023 in adr-log.md

#### Decision: Implement PresenceModule Now (v0.2.0)
- **Context**: PresenceModule is simple, architectural clarity needed now
- **Decision**: Build complete implementation immediately rather than wait for v0.4
- **Rationale**: Not complex to implement, helps validate architecture early
- **Approved By**: Mike
- **Impact**: Low (accelerated timeline)
- **Status**: Complete (33 tests passing)

### 2025-11-26

#### Decision: Layered Automation Architecture
- **Context**: Should actions module be split into domain modules (lighting, HVAC, media)?
- **Decision**: Yes - create layered architecture with automation engine + domain modules
- **Rationale**: 
  - Automation engine provides generic rule processing
  - Domain modules (lighting, climate, media) provide domain-specific APIs
  - Simple configuration translates to complex rules internally
  - Future domain modules can be added without changing engine
- **Approved By**: Mike
- **Impact**: Medium (restructured code, backwards-compat maintained)
- **See**: `docs/modules/automation-architecture.md`

#### Decision: Rename actions/ to automation/
- **Context**: The "actions" module is really a generic automation engine
- **Decision**: Rename to `automation/`, keep `actions/` as backwards-compat shim
- **Rationale**: Better describes purpose, aligns with Home Assistant naming
- **Approved By**: Mike
- **Impact**: Low (backwards compatibility maintained via shim)

---

## 🎯 Milestones

### v0.1.0 - Alpha Release (Target: TBD)
- [x] Core kernel working
- [x] OccupancyModule integrated
- [x] OccupancyModule fully tested (88 tests)
- [x] AutomationEngine implementation
- [x] LightingModule implementation
- [x] Module architecture documentation
- [ ] Example scripts for all modules
- [ ] Documentation complete

### v0.2.0 - Beta Release (Target: TBD)
- [ ] HA integration adapter
- [ ] ClimateModule (future)
- [ ] MediaModule (future)
- [ ] UI for location/entity management
- [ ] Config migration support
- [ ] State persistence tested
- [ ] Performance benchmarks

### v1.0.0 - Stable Release (Target: TBD)
- [ ] Production-ready Occupancy, Automation, Lighting
- [ ] Full HA integration
- [ ] Documentation site
- [ ] >90% test coverage
- [ ] CI/CD pipeline

---

## 🔄 Daily Standup Template

### What was completed yesterday?
- 

### What will be done today?
- 

### Any blockers?
- 

---

## 📊 Sprint Planning Template

### Sprint Goal
- 

### Tasks for Sprint
1. [ ] Task 1
2. [ ] Task 2
3. [ ] Task 3

### Definition of Done
- [ ] Code complete
- [ ] Tests pass
- [ ] Documentation updated
- [ ] PR reviewed and merged

---

## 🏷️ Labels for Issues/PRs

Use these labels for GitHub issues:

- `priority:high` - Critical, blocking
- `priority:medium` - Important, not blocking
- `priority:low` - Nice to have
- `type:bug` - Something broken
- `type:feature` - New functionality
- `type:docs` - Documentation only
- `type:refactor` - Code improvement
- `status:blocked` - Cannot proceed
- `status:in-progress` - Being worked on
- `status:review` - Awaiting review
- `help-wanted` - Community can help

---

## 📅 Next Actions (Immediate)

### This Week
1. [x] Complete OccupancyModule tests ✅
2. [x] ActionsModule implementation ✅
3. [x] Decide on license (MIT) ✅
4. [x] Set up CI/CD (GitHub Actions) ✅

### Next Week
1. [ ] Start HA integration planning
2. [ ] Create project roadmap
3. [ ] Set up project board (GitHub Projects)
4. [ ] Create integration tests (Occupancy + Actions together)

---

## 🛠️ How to Use This Document

### For Developers
1. Check "In Progress" before starting new work
2. Move tasks from "Planned" to "In Progress" when starting
3. Add to "Completed" with date when done
4. Log blockers immediately

### For Project Manager
1. Review daily
2. Update sprint status
3. Track metrics
4. Identify blockers early

### For Documentation
1. Keep decision log up to date
2. Link to related docs (architecture.md, etc.)
3. Update progress metrics weekly

---

**Status**: Active  
**Owner**: Mike  
**Next Review**: Daily

