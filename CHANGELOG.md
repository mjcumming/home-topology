# Changelog

All notable changes to `home-topology` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Initial project structure and core components
- `Location` dataclass for representing spaces
- `LocationManager` for topology and config management
- `EventBus` with location-aware filtering
- `LocationModule` base class for behavior plug-ins
- `OccupancyModule` starter implementation
- `ActionsModule` starter implementation
- Comprehensive design documentation (DESIGN.md)
- Coding standards documentation (CODING-STANDARDS.md)
- Contributing guidelines (CONTRIBUTING.md)
- Example script demonstrating basic usage

### Changed
- N/A (initial release)

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A

---

## [0.1.0] - TBD

Initial alpha release.

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

