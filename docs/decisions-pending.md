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
- black, ruff, mypy, pytest with coverage
- Codecov integration
- **Status**: `.github/workflows/ci.yml` created

### 4. Version Strategy 📊
**Decision**: SemVer with `-alpha` suffix
```
0.1.0-alpha ← Current
0.2.0-alpha - Occupancy complete
0.3.0-alpha - Actions complete  
1.0.0-rc.1  - Release candidate
1.0.0       - Stable
```

### 5. Home Assistant Integration 🏠
**Decision**: Separate repository (`home-topology-ha`)  
**Rationale**: Required for HACS compatibility

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

---

## 🔮 Deferred (Design Later)

These will be addressed when we reach that phase of development:

### Wasp-in-a-Box Implementation 🚪
- Options: Auto-generate rules vs guided wizard vs engine flag
- Design when occupancy rule engine is more mature

### Actions Module Design 🎬
- Design when we start Actions module work

### Sync Conflict Resolution 🔄
- Integration-level concern
- Design when building HA integration

### UI Strategy 🖥️
- Tree View + Inspector pattern confirmed conceptually
- Detail when building frontend

---

## 📋 Remaining Setup Tasks

- [ ] Enable GitHub Discussions (when needed)
- [ ] Configure branch protection on `main`
- [ ] Set up automated PyPI publishing on tag push

---

**Status**: Core decisions complete  
**Last Updated**: 2025-11-25
