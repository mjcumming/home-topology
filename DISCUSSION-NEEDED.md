# Discussion Topics for home-topology

This document outlines areas that need discussion or decisions before proceeding with implementation.

---

## 1. License Selection 📜

**Decision Needed**: Choose the project license.

### Options:
- **MIT**: Very permissive, simple, widely used
- **Apache 2.0**: Patent protection, more corporate-friendly
- **GPL v3**: Copyleft, requires derivatives to be open source

### Recommendation:
**MIT** - Matches the spirit of platform-agnostic, reusable library. Simple and widely accepted.

### Action Items:
- [ ] Choose license
- [ ] Add LICENSE file to repo
- [ ] Update pyproject.toml with license field
- [ ] Update README.md footer

---

## 2. Repository & Package Names 📦

**Current Setup**:
- Repository name: `home-topology`
- PyPI package name: `home-topology`
- Import name: `home_topology` (required by Python)

### Confirmed:
✅ Directory naming follows your preference (no underscores except Python packages)  
✅ Repo uses hyphen: `home-topology/`  
✅ Package dir uses underscore: `src/home_topology/` (Python requirement)

### Questions:
- [ ] Confirm GitHub organization or username
- [ ] Confirm PyPI account for publishing
- [ ] Decide if we want `hometopology` (one word) or `home-topology` (hyphenated)

---

## 3. CI/CD Pipeline Setup 🚀

**Decision Needed**: Which CI platform and what checks?

### Recommended: GitHub Actions

```yaml
# .github/workflows/ci.yml
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: black --check src/ tests/
      - run: ruff check src/ tests/
      - run: mypy src/
      - run: pytest tests/ --cov=home_topology
```

### Action Items:
- [ ] Create `.github/workflows/ci.yml`
- [ ] Configure branch protection on `main` (require CI pass)
- [ ] Set up coverage reporting (codecov.io or coveralls)
- [ ] Set up automated PyPI publishing on tag push

---

## 4. Version Numbering & Release Strategy 📊

**Current Plan**: SemVer (MAJOR.MINOR.PATCH)

### Pre-1.0 Strategy:
- Start at `0.1.0` (alpha)
- Allow breaking changes in `0.x` minor versions
- Once API is stable, release `1.0.0`

### Questions:
- [ ] Start with `0.1.0-alpha` or just `0.1.0`?
- [ ] Use release candidates (`1.0.0-rc.1`) or go straight to stable?
- [ ] How often to release? (Monthly? On-demand?)

### Recommendation:
```
0.1.0      - Initial alpha (core kernel)
0.2.0      - Occupancy module complete
0.3.0      - Actions module complete
1.0.0-rc.1 - Release candidate
1.0.0      - First stable release
```

---

## 5. Home Assistant Integration Strategy 🏠

**Decision Needed**: Separate repo or monorepo?

### Option A: Separate Repository (Recommended)
```
home-topology/              # Core library (this repo)
home-topology-ha/           # HA integration
  custom_components/
    home_topology/
```

**Pros**:
- Clear separation of concerns
- Core library versioning independent of HA integration
- Can have separate contributors/maintainers
- Different release cycles

**Cons**:
- Two repos to maintain
- Need to coordinate versions

### Option B: Monorepo
```
home-topology/
  src/home_topology/        # Core library
  ha_integration/           # HA integration
    custom_components/
```

**Pros**:
- Single repo, easier coordination
- Shared CI/CD

**Cons**:
- Mixed concerns
- Harder to version independently

### Recommendation:
**Option A (Separate Repos)** - Aligns with "platform agnostic" design principle.

### Action Items:
- [ ] Decide on repository structure
- [ ] If separate: create `home-topology-ha` repo
- [ ] Define version compatibility (e.g., HA integration 0.1.x requires core 0.1.x)

---

## 6. Documentation Site 📚

**Decision Needed**: Do we need a documentation site?

### Options:

#### Option A: GitHub README/Wiki Only (Simple)
- README.md for quick start
- Wiki for detailed guides
- Good for small projects

#### Option B: MkDocs Site (Recommended)
- Static site generator
- Versioned docs
- Search functionality
- Professional appearance

```
docs/
  index.md
  getting-started.md
  core/
    location-manager.md
    event-bus.md
  modules/
    occupancy.md
    actions.md
  api-reference.md
```

#### Option C: Sphinx (Python Standard)
- More complex setup
- Better for API docs (autodoc)
- Standard for Python projects

### Recommendation:
**Start with Option A**, add Option B when we have users.

### Action Items:
- [ ] Decide documentation strategy
- [ ] If MkDocs: set up docs/ structure
- [ ] Configure GitHub Pages for hosting

---

## 7. Community & Communication 💬

**Decision Needed**: Where do users ask questions?

### Options:
- **GitHub Issues**: Bug reports, feature requests
- **GitHub Discussions**: Questions, ideas, show-and-tell
- **Discord**: Real-time chat (requires moderation)
- **Home Assistant Forums**: Announce releases, integration support

### Recommendation:
- ✅ GitHub Issues: Bugs and features
- ✅ GitHub Discussions: Everything else
- ⏳ Discord: If community grows
- ✅ HA Forums: For HA integration announcements

### Action Items:
- [ ] Enable GitHub Discussions on repo
- [ ] Create discussion categories (Q&A, Ideas, Show & Tell)
- [ ] Add links to README.md

---

## 8. Contributor Recognition 🏆

**Decision Needed**: How to recognize contributors?

### Recommendation:
- Create `AUTHORS.md` listing all contributors
- Mention significant contributions in release notes
- Use GitHub's "all-contributors" bot

### Action Items:
- [ ] Create AUTHORS.md
- [ ] Add yourself as initial author
- [ ] Decide on contributor levels (maintainer, contributor, etc.)

---

## 9. Code Ownership & Maintenance 👥

**Decision Needed**: Who maintains what?

### Questions:
- [ ] Who are the initial maintainers?
- [ ] What's the review process? (1 approval? 2?)
- [ ] Who can merge to `main`?
- [ ] Who can publish to PyPI?

### Recommendation:
Start small:
- 1-2 core maintainers
- 1 approval required for PRs
- Maintainers can merge
- Automated PyPI publish via CI

---

## 10. Testing Requirements 🧪

**Decision Needed**: What are the testing standards?

### Current:
- Unit tests for all core components
- Integration tests for module interactions
- Basic test coverage established

### Questions:
- [ ] Minimum coverage percentage? (Suggestion: 80%)
- [ ] Coverage enforcement in CI? (Block merge if coverage drops?)
- [ ] Performance tests / benchmarks?
- [ ] HA integration testing strategy?

### Recommendation:
```
- Core library: 90% coverage required
- Modules: 80% coverage required
- Coverage must not decrease with PRs
- Performance tests: Add later if needed
```

### Action Items:
- [ ] Set coverage thresholds in pytest config
- [ ] Add coverage check to CI
- [ ] Add coverage badge to README

---

## 11. Module Development Guidelines 🔧

**Decision Needed**: How do external developers create modules?

### Questions:
- [ ] Should custom modules be in the main repo or separate?
- [ ] Do we need a "module registry"?
- [ ] What's the approval process for new modules?

### Recommendation:
**Phase 1** (v0.x): Core team develops built-in modules
- Occupancy, Actions in main repo
- Focus on solid module API

**Phase 2** (v1.x): Community modules
- Example custom module in main repo
- Community modules in separate repos
- Optional: registry/directory on website

### Action Items:
- [ ] Document module development guide (examples/custom-module.py)
- [ ] Define module API stability guarantees
- [ ] Decide if we want a plugin marketplace (later)

---

## 12. Breaking Change Policy ⚠️

**Decision Needed**: How do we handle breaking changes?

### Recommendation:
**Pre-1.0 (v0.x)**:
- Breaking changes allowed in minor versions
- Document in CHANGELOG with migration guide
- Deprecation warnings where possible

**Post-1.0 (v1.x+)**:
- Breaking changes only in major versions
- Deprecation warnings in previous minor version
- Migration guide required
- Support last major version for 6 months

### Action Items:
- [ ] Document breaking change policy
- [ ] Add deprecation warning helpers
- [ ] Create migration guide template

---

## 13. Security Policy 🔒

**Decision Needed**: How to handle security issues?

### Recommendation:
Create `SECURITY.md`:

```markdown
# Security Policy

## Supported Versions
| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | ✅                 |
| 0.x.x   | ⚠️ (best effort)   |

## Reporting a Vulnerability
Email: security@example.com (not public issue tracker)

We will respond within 48 hours.
```

### Action Items:
- [ ] Create SECURITY.md
- [ ] Set up security email or use GitHub security advisories
- [ ] Add security policy to README

---

## 14. Performance Targets 🎯

**Decision Needed**: What are acceptable performance characteristics?

### Questions:
- [ ] Max event processing latency?
- [ ] Max memory usage for typical setup?
- [ ] How many locations/entities to support?

### Suggested Targets:
```
Supported Scale:
- 100 locations
- 1,000 entities
- 10 modules
- 100 events/second

Performance:
- Event processing: <10ms per event
- Hierarchy query: <1ms
- Memory usage: <100MB for typical setup
```

### Action Items:
- [ ] Define performance targets
- [ ] Add performance tests (later, if needed)
- [ ] Document limitations in README

---

## 15. Immediate Next Steps 🚶

What needs to be done **before** starting module implementation?

### Must Have:
- [ ] **Choose license** (blocks publishing)
- [ ] **Set up CI** (ensure quality)
- [ ] **Create .github/workflows/ci.yml**

### Should Have:
- [ ] Enable GitHub Discussions
- [ ] Create AUTHORS.md
- [ ] Set up coverage reporting

### Nice to Have:
- [ ] Documentation site setup
- [ ] Discord/community channels
- [ ] Performance benchmarks

---

## Summary: Decisions Required

| Topic | Priority | Status |
|-------|----------|--------|
| License | 🔴 High | ❓ Choose: MIT/Apache/GPL |
| CI/CD Setup | 🔴 High | ❓ Approve GitHub Actions config |
| HA Integration Strategy | 🟡 Medium | ❓ Separate repo or monorepo? |
| Version Strategy | 🟡 Medium | ❓ Start at 0.1.0 or 0.1.0-alpha? |
| Documentation Site | 🟢 Low | ❓ MkDocs later or now? |
| Community Channels | 🟢 Low | ❓ GitHub Discussions + what else? |

---

## Recommended Immediate Actions

1. **Choose MIT License** (simplest, most permissive)
2. **Create `.github/workflows/ci.yml`** with the config above
3. **Enable GitHub Discussions** for community Q&A
4. **Start implementing OccupancyModule behavior**

Everything else can be decided as the project grows!

---

**Status**: Ready for Discussion  
**Last Updated**: 2024-11-24

