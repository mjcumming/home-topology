# AI-Assisted Development Guide

**How AI (Cursor) works with this project and known issues to watch for**

---

## Table of Contents

1. [How Cursor AI Works](#how-cursor-ai-works)
2. [The .cursorrules Strategy](#the-cursorrules-strategy)
3. [Smart Context Management](#smart-context-management)
4. [Known AI Issues & Mitigations](#known-ai-issues--mitigations)
5. [Best Practices](#best-practices)

---

## How Cursor AI Works

### What AI Sees Automatically (Every Conversation)

1. **`.cursorrules` file** ✅
   - Located in project root
   - Loaded EVERY conversation
   - ~500 lines max (read completely)
   - This is the "AI briefing document"

2. **Open files in your editor** ✅
   - Whatever you have open right now
   - Appears in context automatically

3. **Recently viewed files** ✅
   - Files you've looked at recently
   - Listed in conversation metadata

4. **Chat history** ✅
   - Our conversation so far
   - Decisions we've made

### What AI Does NOT See (Unless Explicitly Loaded)

- ❌ WORK-TRACKING.md (unless `read_file` is called)
- ❌ DESIGN.md (unless `read_file` is called)
- ❌ ADR-LOG.md (unless `read_file` is called)
- ❌ Any closed files in your repo

---

## The .cursorrules Strategy

### What Goes in `.cursorrules`? (Keep it under 1000 lines)

✅ **Include**:
- Quick reference rules (the essentials)
- Document map (what exists, when to read it)
- Decision tree (which doc for which task)
- Core architectural constraints
- Code style cliff notes
- Anti-patterns to avoid

❌ **Don't Include**:
- Full design specifications (→ DESIGN.md)
- Detailed module docs (→ docs/modules/)
- Decision history (→ ADR-LOG.md)
- Current task status (→ WORK-TRACKING.md)

### Why This Split?

**`.cursorrules`**: "Here's what exists and when to use it"  
**Other docs**: "Here's the detailed content"

This way:
- AI doesn't spam you with info you don't need
- AI knows where to look when needed
- The system scales (add modules without bloating .cursorrules)

---

## Smart Context Management

### The Decision Process

Example: "Add timeout tests for occupancy"

```
1. Check .cursorrules → "Read WORK-TRACKING.md first"
2. read_file("WORK-TRACKING.md") → Check if already in progress
3. Check .cursorrules → "For module work, read docs/modules/{module}-design.md"
4. read_file("docs/modules/occupancy-design.md") → Get timeout details
5. grep("timeout", path="src/home_topology/modules/occupancy/") → Find existing code
6. Write tests
7. Update WORK-TRACKING.md
```

**What AI won't read**:
- ❌ DESIGN.md (not kernel work)
- ❌ CODING-STANDARDS.md (covered in .cursorrules)
- ❌ ADR-LOG.md (not making architectural decision)

### Document Usage Patterns

**High-Frequency (Read Often)**:
- `WORK-TRACKING.md` - Almost every conversation
- Module design docs - When working on that module
- `.cursorrules` - Automatically every time

**Medium-Frequency (Read Sometimes)**:
- `DESIGN.md` - When working on kernel
- `ADR-LOG.md` - When making decisions
- `CODING-STANDARDS.md` - When unsure about style

**Low-Frequency (Read Rarely)**:
- `CONTRIBUTING.md` - New contributors
- `decisions-pending.md` - When have questions

### Tools Used to Avoid Over-Reading

1. **`grep`** - Exact text search (returns matching lines only)
2. **`codebase_search`** - Semantic search (returns relevant chunks)
3. **`read_file` with offset/limit** - Read specific sections

---

## Known AI Issues & Mitigations

### 🗓️ Issue #1: Incorrect Dates (CRITICAL)

**What happens**: AI sometimes writes wrong year in dates (e.g., 2024 instead of 2025)

**Why it happens**: 
- AI training data has a cutoff date
- Defaults to familiar dates from training period

**Impact**: Confusing documentation, files look outdated, version history incorrect

**The Fix** ✅:

1. **`.cursorrules` reminder**: "ALWAYS use 2025 for current dates"

2. **Automated check** (`scripts/check-dates.sh`):
   ```bash
   ./scripts/check-dates.sh
   ```

3. **Makefile integration**:
   ```bash
   make pre-commit  # Includes date check
   make check-dates # Just the date check
   ```

4. **Manual verification**:
   ```bash
   grep -r "2024-" --include="*.md" .
   ```

---

### 🤖 Issue #2: Over-Reading Documentation (Medium)

**What happens**: AI reads all documentation even when not needed  
**Why it happens**: AI doesn't know what's relevant without context  
**Impact**: Slow responses, wasted context

**The Fix** ✅:
- `.cursorrules` decision tree maps task types → required docs
- Prevents reading unnecessary content
- Uses grep/search before reading full files

---

### 📝 Issue #3: Forgetting to Update Work Tracking (Medium)

**What happens**: Code changes without WORK-TRACKING.md updates  
**Why it happens**: Focused on code, forget to update status  
**Impact**: Status gets stale, lose track of progress

**The Fix** ✅:
- `.cursorrules` Golden Rule #1: "ALWAYS read WORK-TRACKING.md first"
- Include WORK-TRACKING.md check in PR template

---

### 🔄 Issue #4: Inconsistent Commit Messages (Low)

**What happens**: Commit messages don't follow convention  
**Why it happens**: Format not enforced automatically  
**Impact**: Hard to generate CHANGELOG, poor git history

**The Fix** ✅:
- `.cursorrules` defines commit message format
- Conventional Commits: `<type>(<scope>): <subject>`

---

### 🧪 Issue #5: Decreasing Test Coverage (Medium)

**What happens**: New code without tests reduces coverage  
**Why it happens**: Easy to forget tests  
**Impact**: Quality degrades

**The Fix** ✅:
- `.cursorrules` Golden Rule: "Test everything, maintain coverage"
- `make test-cov` shows coverage percentage

---

### 🚫 Issue #6: Platform Dependencies Creeping In (High)

**What happens**: Someone imports `homeassistant.*` in core  
**Why it happens**: Convenient for testing/examples  
**Impact**: Breaks platform independence

**The Fix** ✅:
- `.cursorrules` hard rule: "No HA dependencies in core"
- Check: `grep -r "from homeassistant\|import homeassistant" src/home_topology/`

---

## Best Practices

### For Developers

**Starting Your Day**:
```bash
# Open the files YOU need
cursor WORK-TRACKING.md  # Check status

# AI sees:
# - .cursorrules (automatic)
# - WORK-TRACKING.md (you opened it)
# - Any other open files
```

**Working on a Task**:
```bash
# You: "Add motion sensor support"

# AI (internally):
# 1. Check .cursorrules → "Read WORK-TRACKING.md first"
# 2. Read WORK-TRACKING.md
# 3. Check .cursorrules → "For module work, read module design doc"
# 4. Read docs/modules/occupancy-design.md
# 5. grep for existing motion sensor code
# 6. Write implementation
```

**You Control What AI Sees**:
```bash
# Want AI to see DESIGN.md?
cursor DESIGN.md  # Open it

# Want AI to make a decision?
cursor ADR-LOG.md  # AI checks prior decisions

# Don't want AI to read everything?
# Don't open everything! AI uses .cursorrules to navigate
```

### Pro Tips

1. **Use Comments to Guide AI**:
   ```python
   # See docs/modules/occupancy-design.md Section 4.2 for event handling details
   def _translate_event(self, event):
       ...
   ```

2. **Open Files Strategically**:
   - Starting new module? Open DESIGN.md + module design doc
   - Bug hunting? Open the source file
   - Just coding? Don't open docs, AI uses .cursorrules

3. **Tell AI What You Want**:
   ```
   You: "Add timeout tests. Read the occupancy design doc first."
   ```
   Clear instructions override the decision tree.

### Debugging AI Decisions

**If AI is Not Reading What You Expect**:
1. Is the file path correct in `.cursorrules`?
2. Is the decision tree clear for this task type?
3. Did you give clear task categorization?

**If AI is Reading Too Much**:
1. Is `.cursorrules` too generic?
2. Are task types not specific enough?

---

## Issue Lifecycle

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

## Current Mitigations Summary

| Issue | Severity | Mitigation | Automated |
|-------|----------|------------|-----------|
| Wrong dates | 🔴 Critical | .cursorrules rule + script | ✅ Yes |
| Over-reading docs | 🟡 Medium | .cursorrules decision tree | ✅ Yes |
| Stale WORK-TRACKING | 🟡 Medium | .cursorrules Golden Rule #1 | ⚠️ Partial |
| Bad commit messages | 🟢 Low | .cursorrules format | ❌ Not yet |
| Low coverage | 🟡 Medium | .cursorrules + make test-cov | ⚠️ Partial |
| HA deps in core | 🔴 Critical | .cursorrules hard rule | ❌ Not yet |

---

## Reporting New AI Issues

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

**Status**: Active Guide  
**Last Updated**: 2025-11-25

