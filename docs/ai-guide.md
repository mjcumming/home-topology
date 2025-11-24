# Known AI Issues & Mitigations

**Issues specific to AI-assisted development and how we prevent them**

---

## 🗓️ Issue #1: Incorrect Dates (CRITICAL)

### The Problem

**What happens**: AI sometimes writes wrong year in dates (e.g., 2024 instead of 2025)

**Why it happens**: 
- AI training data has a cutoff date
- Defaults to familiar dates from training period
- Doesn't always read system date correctly

**Impact**: 
- ❌ Confusing documentation
- ❌ Files look outdated
- ❌ Version history incorrect
- ❌ Unprofessional

### The Fix ✅

**Multiple layers of protection**:

1. **`.cursorrules` reminder** (Line 357)
   ```
   9. ALWAYS use 2025 for current dates (NOT 2024!) ⚠️
   ```

2. **Automated check** (`scripts/check-dates.sh`)
   ```bash
   # Run before committing
   ./scripts/check-dates.sh
   ```

3. **Makefile integration**
   ```bash
   make pre-commit  # Includes date check
   make check-dates # Just the date check
   ```

4. **Manual verification**
   ```bash
   # Check if any 2024 dates snuck in
   grep -r "2024-" --include="*.md" .
   ```

### Prevention Checklist

Before committing documentation:
- [ ] Run `make check-dates`
- [ ] Verify dates in ADR-LOG.md
- [ ] Check WORK-TRACKING.md dates
- [ ] Scan commit message dates

### If You Find Wrong Dates

```bash
# Fix all at once
find . -name "*.md" -exec sed -i 's/2025-11-24/2025-11-24/g' {} \;

# Verify
./scripts/check-dates.sh
```

---

## 🤖 Issue #2: Over-Reading Documentation (Medium)

### The Problem

**What happens**: AI reads all documentation even when not needed  
**Why it happens**: AI doesn't know what's relevant without context  
**Impact**: Slow responses, wasted context

### The Fix ✅

**`.cursorrules` decision tree**:
- Maps task types → required docs
- Prevents reading unnecessary content
- Uses grep/search before reading full files

**Prevention**: Check `.cursorrules` has clear doc routing

---

## 📝 Issue #3: Forgetting to Update Work Tracking (Medium)

### The Problem

**What happens**: Code changes without WORK-TRACKING.md updates  
**Why it happens**: Focused on code, forget to update status  
**Impact**: Status gets stale, lose track of progress

### The Fix ✅

**`.cursorrules` Golden Rule #1**: "ALWAYS read WORK-TRACKING.md first"

**Commit template**:
```
feat(module): add feature

Updated WORK-TRACKING.md: [task moved to completed]
```

**Prevention**: Include WORK-TRACKING.md check in PR template

---

## 🔄 Issue #4: Inconsistent Commit Messages (Low)

### The Problem

**What happens**: Commit messages don't follow convention  
**Why it happens**: Format not enforced automatically  
**Impact**: Hard to generate CHANGELOG, poor git history

### The Fix ✅

**`.cursorrules` Section 11**: Commit message format defined

**Conventional Commits**:
```
<type>(<scope>): <subject>
```

**Prevention**: Add commitlint to CI (future)

---

## 🧪 Issue #5: Decreasing Test Coverage (Medium)

### The Problem

**What happens**: New code without tests reduces coverage  
**Why it happens**: Easy to forget tests  
**Impact**: Quality degrades

### The Fix ✅

**`.cursorrules` Golden Rule #6**: "Test everything, maintain coverage"

**Makefile enforcement**:
```bash
make test-cov  # Shows coverage percentage
```

**Prevention**: 
- [ ] Add coverage threshold to pytest config
- [ ] Fail CI if coverage decreases

---

## 🚫 Issue #6: Platform Dependencies Creeping In (High)

### The Problem

**What happens**: Someone imports `homeassistant.*` in core  
**Why it happens**: Convenient for testing/examples  
**Impact**: Breaks platform independence

### The Fix ✅

**`.cursorrules` Golden Rule #8**: "No HA dependencies in core"

**Prevention**:
```bash
# Check for HA imports
grep -r "from homeassistant\|import homeassistant" src/home_topology/

# Should return nothing
```

**CI check** (future):
```python
# In CI
assert no HA imports in src/home_topology/
```

---

## 📚 How to Use This Document

### For Developers
- Review before starting work
- Check prevention strategies
- Run automated checks

### For AI
- Reference when making changes
- Follow prevention strategies
- Check this doc if user reports known issue

### For Project Management
- Review quarterly
- Add new issues as discovered
- Update mitigations as implemented

---

## 🔄 Issue Lifecycle

```
Issue Discovered
    ↓
Add to this document
    ↓
Create mitigation strategy
    ↓
Add to .cursorrules if frequent
    ↓
Automate check if possible
    ↓
Add to CI/pre-commit
    ↓
Monitor for recurrence
```

---

## 📊 Current Mitigations

| Issue | Severity | Mitigation | Automated |
|-------|----------|------------|-----------|
| Wrong dates | 🔴 Critical | .cursorrules rule + script | ✅ Yes |
| Over-reading docs | 🟡 Medium | .cursorrules decision tree | ✅ Yes |
| Stale WORK-TRACKING | 🟡 Medium | .cursorrules Golden Rule #1 | ⚠️ Partial |
| Bad commit messages | 🟢 Low | .cursorrules format | ❌ Not yet |
| Low coverage | 🟡 Medium | .cursorrules + make test-cov | ⚠️ Partial |
| HA deps in core | 🔴 Critical | .cursorrules hard rule | ❌ Not yet |

---

## 🎯 Next Steps for Mitigation

### Short-term
- [x] Add date check script ✅
- [x] Add to Makefile ✅
- [x] Add to .cursorrules ✅
- [ ] Add to CI workflow

### Long-term
- [ ] Add commitlint
- [ ] Add coverage threshold enforcement
- [ ] Add HA import checker to CI
- [ ] Add pre-commit hooks

---

## 📝 Reporting New Issues

Found a recurring AI issue?

1. Add to this document with:
   - Problem description
   - Why it happens
   - Impact
   - Proposed mitigation

2. If critical: Add to `.cursorrules` immediately

3. If automatable: Create check script

4. Update this doc with resolution

---

**Status**: Active Issue Tracker  
**Owner**: Project Team  
**Last Updated**: 2025-11-24 (verified correct! ✅)

