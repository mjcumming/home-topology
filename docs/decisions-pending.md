# Decisions Log

**Project decisions - decided and deferred**

---

## ✅ Decided

### 1. License 📜
**Decision**: MIT License  
**Status**: Complete - LICENSE file added

### 2. Repository & Package Names 📦
- Repository: `home-topology`
- PyPI package: `home-topology`
- Import name: `home_topology`
- GitHub: `mjcumming`
- PyPI: `mjcumming`

### 3. CI/CD Pipeline 🚀
**Decision**: GitHub Actions  
- Python 3.10, 3.11, 3.12 matrix
- Python 3.12, 3.13 matrix
- black, ruff, mypy, pytest with coverage
- Codecov integration
- **Status**: `.github/workflows/ci.yml` created

### 4. Version Strategy 📊
**Decision**: SemVer with pre-release `aN` suffix
```
1.0.1       ← Current
0.3.0a0     - Next pre-release
1.0.0-rc.1  - Release candidate
1.0.0       - Stable
```

### 5. Home Assistant Integration 🏠
**Decision**: Separate repository (`topomation`)  
**Rationale**: Keep the kernel platform-agnostic; HA adapter lifecycle stays independent

### 6. Documentation Site 📚
**Decision**: GitHub README/Wiki for now  
Add MkDocs when we have users.

### 7. Community & Communication 💬
**Decision**: Keep it simple
- GitHub Issues for bugs/features
- GitHub Discussions for Q&A (enable when needed)
- HA Forums for integration announcements (later)

### 8. Contributor Recognition 🏆
**Decision**: Just maintainer for now (mjcumming)  
Consider all-contributors bot later if community grows.

### 9. Code Ownership 👥
**Decision**: Solo maintainer (mjcumming)
- 1 maintainer
- Automated PyPI publish via CI (when ready)

### 10. Testing Requirements 🧪
**Decision**: Follow recommended coverage targets
- Core library: 90% coverage target
- Modules: 80% coverage target
- Coverage must not decrease with PRs
- Performance tests: Add later if needed

### 11. Module Development Guidelines 🔧
**Decision**: Defer until proof of concept complete
- Phase 1 (v0.x): Core team develops built-in modules
- Phase 2 (v1.x): Document for community modules

### 12. Breaking Change Policy ⚠️
**Decision**: Standard approach
- Pre-1.0: Breaking changes allowed, document in CHANGELOG
- Post-1.0: Breaking changes only in major versions

### 13. Security Policy 🔒
**Decision**: Standard GitHub security advisories  
**Status**: `SECURITY.md` created

### 14. Performance Targets 🎯
**Decision**: Defer formal targets, use sensible defaults
- Design for ~100 locations, ~1000 entities
- Add benchmarks later if performance issues arise

### 15. Occupancy Event Model (v3.0) 🎯
**Decision**: TRIGGER + CLEAR with per-source tracking  
**Date**: 2025-11-26  
- Replaces TRIGGER/HOLD/RELEASE with simpler TRIGGER/CLEAR
- Per-source contribution tracking (each entity tracked independently)
- `timeout=None` for indefinite contributions
- **Status**: Design docs updated, implementation pending

### 16. UI Terminology: "Occupancy Sources" 📝
**Decision**: Use "Occupancy Sources" instead of "Device Mappings"  
**Date**: 2025-11-26  
- More descriptive of what the section does
- "Presence Inputs" reserved for future Presence module
- Use "entity" not "device" (follows HA paradigm)

### 17. Timeout Model 🕐
**Decision**: Location default + per-entity override  
**Date**: 2025-11-26  
- Location has `default_timeout` and `default_trailing_timeout`
- Each entity can override with specific timeout
- If entity doesn't specify, inherits from location

### 18. Alias Support 🎤
**Decision**: Native field in Location dataclass  
**Date**: 2025.12.09  
- Universal feature for voice assistants (Google, Alexa, HA Assist, Siri)
- Simple to implement and query
- HA integration syncs with HA area aliases
- Supports multiple alternative names per location

### 19. Batch Entity Operations ⚡
**Decision**: Add batch methods to LocationManager  
**Date**: 2025.12.09  
- `add_entities_to_location()` - assign multiple entities at once
- `remove_entities_from_location()` - remove multiple entities
- `move_entities()` - move multiple entities between locations
- More efficient than individual calls for bulk operations

### 20. Occupancy: Binary Only (No Confidence) 🎯
**Decision**: Occupancy is binary (True/False), no confidence scoring  
**Date**: 2025.12.09  
- After years of real-world experience: confidence doesn't add value
- No clear use case for "maybe occupied" - you either act or don't
- Simpler implementation, easier to understand
- Confidence is out of scope unless a future ADR supersedes this decision

### 21. No Event Coordination Between Modules 🔄
**Decision**: Modules emit events independently and immediately, no delays  
**Date**: 2025.12.09  
- 90% of automations don't need person identification
- Real-world sensor timing: seconds, not milliseconds
- User can choose to wait (DelayAction) or accept sequential override
- Simpler architecture, more flexible

### 22. PresenceModule Implementation 👥
**Decision**: Implement PresenceModule now (v0.2), not defer to v0.4  
**Date**: 2025.12.09  
- Simple to implement (33 tests, ~350 lines)
- Validates architecture early
- Person registry separate from LocationManager
- Platform-agnostic core, HA integration uses HA Person entities

---

## 🔮 Deferred (Design Later)

These will be addressed when we reach that phase of development:

### Actions Module Design 🎬 ✅
- **Status**: Complete (2025-11-26)
- Implemented rule-based automation with:
  - Event triggers (occupancy.changed, etc.)
  - Condition types (time_of_day, lux_level, state, numeric_state, location_occupied, day_of_week)
  - Action types (service_call, delay)
  - Execution modes (single, restart, parallel)
  - Pre-built presets for common patterns
- 68 tests passing

### Sync Conflict Resolution 🔄
- Integration-level concern
- Design when building HA integration

### UI Strategy 🖥️
- Tree View + Inspector pattern confirmed conceptually
- Prototyping in Gemini Canvas
- **Remaining mockups needed**:
  - New Location Dialog
  - Entity Configuration Dialog
  - Hover states (drag handle, delete button)
  - State indicators (pending changes, occupancy status)

---

## 📋 Remaining Setup Tasks

- [ ] Enable GitHub Discussions (when needed)
- [ ] Configure branch protection on `main`
- [ ] Set up automated PyPI publishing on tag push

---

**Status**: Core decisions complete, UI mockup phase  
**Last Updated**: 2026-03-01
