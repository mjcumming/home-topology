# Changelog

All notable changes to `home-topology` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

#### AmbientLightModule (2025.12.09)
- **NEW MODULE**: AmbientLightModule for intelligent ambient light detection
- **Hierarchical sensor lookup**: Automatically inherit lux sensors from parent locations
  - Check location → parent → grandparent → sun.sun
  - Full provenance tracking (know which sensor provided reading)
- **Automatic sensor discovery**: Detects lux sensors by pattern, device_class, and unit
- **Location-based conditions**: `LuxLevelCondition` now supports `location_id` parameter
  - Backward compatible: `entity_id` still works
  - New mode: `location_id="kitchen"` with automatic sensor lookup and inheritance
- **Per-location thresholds**: Configure `dark_threshold` and `bright_threshold` per location
- **Multiple fallback strategies**: lux sensor → parent lux → sun.sun → assume dark/bright
- **Convenience methods**: `is_dark(location_id)`, `is_bright(location_id)`
- **Data model**: `AmbientLightReading` with lux value, source tracking, and boolean flags
- **Configuration schema**: Full JSON schema for UI generation
- **State persistence**: Sensor cache and configuration persistence
- **Comprehensive tests**: 60+ tests covering all scenarios
- **Lighting preset updates**: `lights_on_when_occupied()` and `adaptive_lighting()` now support `location_id`

#### Automation Engine Updates (2025.12.09)
- **Enhanced LuxLevelCondition**: Two modes of operation
  - Explicit sensor: `LuxLevelCondition(entity_id="sensor.kitchen_lux", below=50)`
  - Location-based: `LuxLevelCondition(location_id="kitchen", inherit_from_parent=True, below=50)`
- **ConditionEvaluator** now accepts optional `ambient_module` parameter
- **Integration ready**: HA integration can pass AmbientLightModule to automation engine

### Documentation

#### New Documents
- `docs/modules/ambient-module-design.md` (900+ lines) - Complete AmbientLightModule specification

#### Updated Documents
- `docs/adr-log.md` → Added ADR-024 (Hierarchical Ambient Light Sensor Lookup)
- `docs/architecture.md` → Added AmbientLightModule to built-in modules list

#### Architecture Decisions
- **ADR-024**: Hierarchical Ambient Light Sensor Lookup (automatic inheritance from parent locations)

---

## [0.2.0-alpha] - 2025-12-09

### Added

#### Core Library Enhancements (2025.12.09)
- **Alias support**: `Location` dataclass now has `aliases: List[str]` field for voice assistant integration
- **Alias management methods** in `LocationManager`:
  - `add_alias(location_id, alias)` - Add single alias
  - `add_aliases(location_id, aliases)` - Add multiple aliases
  - `remove_alias(location_id, alias)` - Remove specific alias
  - `set_aliases(location_id, aliases)` - Replace all aliases
  - `find_by_alias(alias)` - Find location by alias
  - `get_location_by_name(name)` - Find location by exact name
- **Batch entity operations** in `LocationManager`:
  - `add_entities_to_location(entity_ids, location_id)` - Add multiple entities at once
  - `remove_entities_from_location(entity_ids)` - Remove multiple entities
  - `move_entities(entity_ids, to_location_id)` - Move entities between locations

#### PresenceModule (2025.12.09)
- **NEW MODULE**: PresenceModule for tracking WHO is in each location
- **Person data model**: `Person` dataclass with device trackers and current location
- **Person registry**: Create, delete, query people
- **Device tracker management**: Add/remove trackers dynamically (supports temporary associations)
- **Location queries**: `get_people_in_location()`, `get_person_location()`
- **Person movement**: `move_person()` with `presence.changed` events
- **State persistence**: Full dump/restore support
- **Tests**: 33 comprehensive tests (all passing)
- **Example**: `examples/presence-example.py` demonstrating usage

### Changed
- **Python 3.12+ required**: Bumped minimum Python version to 3.12 to align with Home Assistant requirements
- Use `datetime.UTC` instead of `datetime.timezone.utc` throughout codebase
- Updated `LocationManager.create_location()` to accept optional `aliases` parameter

### Removed
- **Confidence scoring**: Removed from occupancy design (never implemented)
  - Occupancy is binary (True/False) only
  - Based on years of real-world experience showing no value
  - Simpler implementation and configuration

### Documentation

#### New Documents
- `docs/integration/ha-sync-services.md` (812 lines) - Complete HA sync and service guide
- `docs/integration/integrity-validation.md` (676 lines) - Validation system design (future v0.3)
- `docs/modules/presence-module-design.md` (784 lines) - Complete PresenceModule spec
- `docs/modules/occupancy-presence-interaction.md` (450 lines) - How modules work together

#### Updated Documents
- `docs/architecture.md` → v1.7 with alias support, batch operations, PresenceModule
- `docs/adr-log.md` → Added ADR-020 (Aliases), ADR-021 (No Confidence), ADR-022 (No Event Coordination), ADR-023 (PresenceModule)
- `docs/decisions-pending.md` → Added decisions 18-22
- `docs/project-status.md` → Updated with PresenceModule completion, 75% overall progress

#### Architecture Decisions
- **ADR-020**: Alias support and batch operations in core library
- **ADR-021**: Remove confidence scoring from occupancy (binary only)
- **ADR-022**: No event coordination between modules (independent emission)
- **ADR-023**: PresenceModule as separate module from OccupancyModule

---

## [0.2.0-alpha] - 2025-11-26

OccupancyModule v2.3 - Major API improvements and simplified state model.

### ⚠️ BREAKING CHANGES
- **Removed `active_occupants`**: Identity tracking removed from OccupancyModule (deferred to future PresenceModule)
- **Removed `occupant_id` parameter**: No longer accepted by trigger(), hold(), release()
- **Renamed `timeout` to `trailing_timeout`**: In release() method for clarity
- **Removed `source_id` from commands**: vacate() and unlock_all() no longer require source_id
- **Timer suspension during lock**: Timers now pause when locked and resume when unlocked (behavior change)

### Added
- `timer_remaining` field in LocationRuntimeState for lock suspension/resume
- Device Type Presets documentation for UI device mapping
- Events vs Commands API documentation

### Changed
- **Events API** (from device mappings): trigger(), hold(), release()
- **Commands API** (from automations/UI): vacate(), lock(), unlock(), unlock_all()
- Timer suspension: Timers pause during lock and resume with remaining time on unlock
- Holds and timers coexist: TRIGGER events during holds extend the background timer
- RELEASE checks existing timer before starting trailing timer
- Updated all tests for new v2.3 behavior (88 tests passing)

### Documentation
- Moved integration-guide.md to docs/integration/
- Updated ui-design.md with Device Mapping section
- Added Decisions 11-14 to occupancy-design-decisions.md
- Updated occupancy-design.md with v2.3 state model
- Updated integration-guide.md for v2.3 API

---

## [0.1.1-alpha] - 2025-11-25

Quality improvements and comprehensive test coverage.

### Added
- Advanced occupancy tests (88 tests total, comprehensive suite)
- `get_effective_timeout()` - returns true timeout considering all descendants
- `vacate_area()` - cascading vacate command for location subtrees
- Effective timeout tests
- Vacate area (cascading) tests

### Changed
- Replaced `datetime.UTC` with `datetime.timezone.utc` for Python 3.10+ compatibility
- Added type annotations throughout codebase
- Fixed all mypy type errors (22 issues resolved)
- Fixed all ruff linting issues (13 issues resolved)
- Removed unused imports and variables

### Documentation
- Added UI design specification (`docs/ui/ui-design.md`)
- Added project status tracking (`docs/project-status.md`)
- Added architecture documentation (`docs/architecture.md`)
- Added testing guides (`docs/testing/`)
- Added occupancy design decisions (`docs/modules/occupancy-design-decisions.md`)
- Reorganized documentation structure

---

## [0.1.0] - 2025-11-24

First stable release - Foundation complete with comprehensive documentation.

### Added
- Complete integration guide for platform integrators
- Comprehensive test documentation (TESTING-GUIDE.md, TEST-COMMANDS.md)
- LocationManager test suite (test-location-manager.py)
- OccupancyModule test suite (test-occupancy-module.py)

### Documentation
- Added integration guide references in README.md
- Updated project overview with integration guide links

---

## [0.1.0-alpha] - 2025-11-24

Initial alpha release - Foundation complete.

### Core Kernel (Complete ✅)
- `Location` dataclass with hierarchy support
- `LocationManager` for topology and config management
  - Graph queries: parent, children, ancestors, descendants
  - Entity-to-location mapping
  - Per-location module configuration storage
- `EventBus` with location-aware filtering
  - Synchronous dispatch with per-handler error isolation
  - Event filtering by type, location, ancestors, descendants
- `LocationModule` base class protocol
  - Config versioning with migration support
  - State dump/restore hooks
  - Schema-driven configuration

### OccupancyModule (95% Complete ✅)
- Native integration of occupancy_manager engine
- Hierarchical occupancy tracking with parent/child propagation
- Identity tracking (track who is in each location)
- Locking logic (party mode - freeze state)
- Time-agnostic design (host-controlled timeout checking)
- State persistence with stale data cleanup
- Event types: MOMENTARY, HOLD_START, HOLD_END, MANUAL, LOCK_CHANGE, PROPAGATED
- Category-based timeouts (motion, presence, door, media)
- Full EventBus integration

### ActionsModule (Starter)
- Basic module structure
- Protocol implementation
- Configuration schema (placeholder)

### Documentation (Complete ✅)
- README.md with quick start guide
- DESIGN.md (v1.3) - Kernel architecture specification
- CODING-STANDARDS.md - Code style and patterns
- CONTRIBUTING.md - Development workflow and release process
- ADR-LOG.md - Architecture decision records (7 decisions documented)
- WORK-TRACKING.md - Sprint status and task tracking
- docs/modules/occupancy-design.md - Occupancy specification
- docs/modules/occupancy-integration.md - Integration status
- docs/modules/actions-design.md - Actions specification
- docs/ai-development-guide.md - AI-assisted development guide
- docs/decisions-pending.md - Pending decisions and discussion topics

### Development Infrastructure (Complete ✅)
- Makefile with development commands
- pyproject.toml (hatchling-based)
- .cursorrules for AI-assisted development
- GitHub Actions CI/CD pipeline
- PR template
- Issue templates
- Date validation script
- .gitignore

### Testing
- Basic test suite (test_basic.py)
- OccupancyModule integration tests
- Test fixtures for common scenarios
- Working example scripts (example.py, occupancy-demo.py)

### Architecture Decisions (Documented in ADR-LOG.md)
- ADR-001: Synchronous EventBus
- ADR-002: Platform Independence  
- ADR-003: Module Config Versioning
- ADR-004: Native Occupancy Integration
- ADR-005: Signal Role Separation
- ADR-006: Host-Controlled Timeout Scheduling
- ADR-007: Module-Specific Design Docs

### Fixed
- Date errors across all documentation (2024 → 2025)
- Timer issue in OccupancyModule (removed threading, restored time-agnostic design)

### Core Features
- Location hierarchy with parent/child relationships
- Entity-to-location mapping (with or without HA Areas)
- Synchronous event bus with error isolation
- Module attachment system with dependency injection
- Configuration versioning and migration support
- State serialization hooks

### Modules
- **OccupancyModule**: Placeholder implementation
- **ActionsModule**: Placeholder implementation

### Documentation
- README with quick start guide
- Comprehensive design specification
- Coding standards and conventions
- Contributing guidelines

### Testing
- Unit tests for core components
- Test fixtures for common scenarios
- Example scripts

---

## Release Notes Format

Each release should include:

### Version Header
```markdown
## [X.Y.Z] - YYYY-MM-DD
```

### Categories
- **Added**: New features
- **Changed**: Changes to existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security fixes

### Breaking Changes
If a release includes breaking changes, add a section:

```markdown
### ⚠️ BREAKING CHANGES
- Description of breaking change and migration path
```

---

## Version History

- **0.1.0** (TBD): Initial alpha release
- **1.0.0** (Future): First stable release

---

**Notes**:
- Pre-1.0.0 releases may include breaking changes in minor versions
- After 1.0.0, breaking changes only in major versions (SemVer)

