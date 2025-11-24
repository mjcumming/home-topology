# Changelog

All notable changes to `home-topology` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- N/A

### Changed
- N/A

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
- docs/ai-guide.md - AI-assisted development guide
- docs/open-questions.md - Open questions and discussions

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

