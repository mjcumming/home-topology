# How Cursor AI Uses Your Project Rules

**Understanding AI context management for developers**

---

## 🤖 How Cursor AI Actually Works

### What I See Automatically (Every Conversation)

1. **`.cursorrules` file** ✅
   - Located in project root
   - Loaded EVERY conversation
   - ~500 lines max (I just read the whole thing)
   - This is your "AI briefing document"

2. **Open files in your editor** ✅
   - Whatever you have open right now
   - Appears in my context automatically

3. **Recently viewed files** ✅
   - Files you've looked at recently
   - Listed in conversation metadata

4. **Chat history** ✅
   - Our conversation so far
   - Decisions we've made

### What I DON'T See (Unless Explicitly Loaded)

- ❌ WORK-TRACKING.md (unless I `read_file` it)
- ❌ DESIGN.md (unless I `read_file` it)
- ❌ ADR-LOG.md (unless I `read_file` it)
- ❌ Any closed files in your repo

---

## 📋 The `.cursorrules` Strategy

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
- I don't spam you with info you don't need
- I know where to look when I DO need it
- The system scales (add modules without bloating .cursorrules)

---

## 🎯 How I Decide What to Read

### Example: "Add timeout tests for occupancy"

**My thought process**:
```
1. Check .cursorrules → "Read WORK-TRACKING.md first"
2. read_file("WORK-TRACKING.md") → Check if already in progress
3. Check .cursorrules → "For module work, read docs/modules/{module}-design.md"
4. read_file("docs/modules/occupancy-design.md") → Get timeout details
5. grep("timeout", path="src/home_topology/modules/occupancy/") → Find existing code
6. Write tests
7. Update WORK-TRACKING.md
```

**What I DON'T read**:
- ❌ DESIGN.md (not kernel work)
- ❌ CODING-STANDARDS.md (covered in .cursorrules)
- ❌ ADR-LOG.md (not making architectural decision)

---

## 🧠 Smart Context Management

### The Problem: Context Window Limits

I have a large context window (1M tokens), but:
- Reading everything is slow
- Most docs aren't relevant to current task
- You want fast responses, not doc dumps

### The Solution: Lazy Loading + Decision Tree

```
.cursorrules (always loaded)
    ↓
    "For this task type, read X"
    ↓
Read X only (not Y, Z, A, B, C...)
    ↓
Fast, focused response
```

---

## 📊 Document Usage Patterns

### High-Frequency (Read Often)
- `WORK-TRACKING.md` - Almost every conversation
- Module design docs - When working on that module
- `.cursorrules` - Automatically every time

### Medium-Frequency (Read Sometimes)
- `DESIGN.md` - When working on kernel
- `ADR-LOG.md` - When making decisions
- `CODING-STANDARDS.md` - When unsure about style

### Low-Frequency (Read Rarely)
- `CONTRIBUTING.md` - New contributors
- `PROJECT-MANAGEMENT.md` - Process questions
- `DISCUSSION-NEEDED.md` - When have questions

---

## 🎮 How to Use This System

### As a Developer

#### Starting Your Day
```bash
# Open the files YOU need
cursor WORK-TRACKING.md  # Check status

# I'll see:
# - .cursorrules (automatic)
# - WORK-TRACKING.md (you opened it)
# - Any other open files
```

#### Working on a Task
```bash
# You: "Add motion sensor support"

# Me (internally):
# 1. Check .cursorrules → "Read WORK-TRACKING.md first"
# 2. Read WORK-TRACKING.md
# 3. Check .cursorrules → "For module work, read module design doc"
# 4. Read docs/modules/occupancy-design.md
# 5. grep for existing motion sensor code
# 6. Write implementation
```

#### You Control What I See
```bash
# Want me to see DESIGN.md?
cursor DESIGN.md  # Open it, I'll see it

# Want me to make a decision?
cursor ADR-LOG.md  # I'll check prior decisions

# Don't want me to read everything?
# Don't open everything! I'll use .cursorrules to navigate
```

---

## 🛠️ Tools I Use to Avoid Over-Reading

### 1. `grep` - Exact Text Search
```python
# Instead of reading entire file:
grep("EventBus", path="src/home_topology/core/")
# Returns just the matching lines
```

### 2. `codebase_search` - Semantic Search
```python
# Instead of reading multiple files:
codebase_search(
    query="How are occupancy timeouts calculated?",
    target_directories=["src/home_topology/modules/occupancy"]
)
# Returns relevant code chunks only
```

### 3. `read_file` with offset/limit
```python
# Instead of reading 1000-line file:
read_file("DESIGN.md", offset=100, limit=50)
# Read just the section I need
```

---

## 📈 Performance Comparison

### ❌ Naive Approach (Slow)
```python
# Read everything every time
read_file("DESIGN.md")              # 590 lines
read_file("CODING-STANDARDS.md")   # 450 lines
read_file("WORK-TRACKING.md")       # 200 lines
read_file("ADR-LOG.md")             # 300 lines
read_file("docs/modules/occupancy-design.md")  # 538 lines
read_file("docs/modules/actions-design.md")    # 632 lines
# Total: 2,710 lines read (mostly irrelevant!)
```

### ✅ Smart Approach (Fast)
```python
# .cursorrules loaded automatically (400 lines)
read_file("WORK-TRACKING.md")  # 200 lines (always needed)
# Task: "Add timeout test"
read_file("docs/modules/occupancy-design.md")  # 538 lines (task-specific)
# Total: 1,138 lines (all relevant!)
```

**Result**: 2.4x less reading, 100% more relevance

---

## 🎯 The `.cursorrules` Sweet Spot

### Current Size: ~400 lines

**Contains**:
- Document map (50 lines)
- Quick architectural rules (100 lines)
- Decision tree (50 lines)
- Code style essentials (100 lines)
- Examples (100 lines)

### Maintenance

**When to update `.cursorrules`**:
- ✅ Added new doc type (tell AI where it is)
- ✅ New core rule (don't make AI guess)
- ✅ Common question (add to decision tree)

**When NOT to update `.cursorrules`**:
- ❌ Detailed design decisions (→ ADR-LOG.md)
- ❌ Current task status (→ WORK-TRACKING.md)
- ❌ Implementation details (→ module docs)

**Keep it under 1000 lines!**

---

## 💡 Pro Tips

### 1. Use Comments to Guide AI
```python
# In your code:
# See docs/modules/occupancy-design.md Section 4.2 for signal handling details
def _translate_event(self, event):
    ...
```

Now when I read this code, I know where to look for context.

### 2. Open Files Strategically
```bash
# Starting new module?
cursor DESIGN.md docs/modules/occupancy-design.md

# Bug hunting?
cursor src/home_topology/modules/occupancy/module.py

# Just coding?
# Don't open docs! I'll use .cursorrules to navigate
```

### 3. Tell Me What You Want
```
You: "Add timeout tests. Read the occupancy design doc first."

Me: *reads docs/modules/occupancy-design.md*
    *writes tests*
```

Clear instructions override my decision tree.

---

## 🔍 How to Debug My Decisions

### If I'm Not Reading What You Expect

**Check**:
1. Is the file path correct in `.cursorrules`?
2. Is the decision tree clear for this task type?
3. Did you give me clear task categorization?

**Fix**:
```bash
# Update .cursorrules
vim .cursorrules

# Or tell me explicitly:
"Read DESIGN.md before doing this"
```

### If I'm Reading Too Much

**Check**:
1. Is `.cursorrules` too generic?
2. Are task types not specific enough?

**Fix**:
```bash
# Make decision tree more specific
# Add "DON'T read X when doing Y"
```

---

## 📊 Success Metrics

### You'll Know It's Working When:

✅ I read WORK-TRACKING.md almost every conversation  
✅ I read design docs only when relevant  
✅ I reference .cursorrules rules without reading full docs  
✅ I ask "Should I read X?" when unsure  
✅ Responses are fast and focused  

### Warning Signs:

⚠️ I read everything every time (too slow)  
⚠️ I miss important docs (decision tree broken)  
⚠️ I ask you for info that's in docs (doc map unclear)  
⚠️ I ignore `.cursorrules` (file not found or too long)  

---

## 🎓 Advanced: Multi-Agent Workflows

### Future: Specialized Agents

```
┌─────────────────┐
│ Coordinator AI  │ ← Has full .cursorrules
└────────┬────────┘
         │
    ┌────┴────┬────────────┐
    ▼         ▼            ▼
┌────────┐ ┌────────┐ ┌─────────┐
│Kernel  │ │Module  │ │Testing  │
│Agent   │ │Agent   │ │Agent    │
└────────┘ └────────┘ └─────────┘
   │          │           │
   └──────────┴───────────┘
         │
    Shared Docs
```

Each specialist knows subset of rules. Coordinator delegates.

*This is future work, but .cursorrules enables it.*

---

## 📝 TL;DR

### How It Works

1. **`.cursorrules`** = AI's briefing doc (loaded every conversation)
2. **Other docs** = Reference library (loaded on demand)
3. **Decision tree** in .cursorrules tells me what to read when
4. **You control** what I see by opening files

### Best Practices

✅ Keep `.cursorrules` under 1000 lines  
✅ Update it when patterns change  
✅ Use it as a map, not a manual  
✅ Let AI read docs on demand  

### Anti-Patterns

❌ Put everything in `.cursorrules` (too big)  
❌ Skip `.cursorrules` and explain every time (inefficient)  
❌ Never update it (goes stale)  
❌ Open all docs every session (unnecessary)  

---

## 🚀 What You've Built

With `.cursorrules` + your doc system, you have:

1. **Smart routing** - AI knows which doc for which task
2. **Minimal reading** - Only what's needed
3. **Consistent behavior** - Same rules every conversation
4. **Scalability** - Add modules without bloating .cursorrules
5. **Fast responses** - Less reading = faster AI

**This is production-grade AI context management.** 🎉

---

**Questions?** Check `.cursorrules` first, then ask!

---

Last Updated: 2025-11-24

