# home-topology Project Overview

This document provides a high-level overview of the project structure, decisions, and getting started guide.

---

## What is home-topology?

`home-topology` is a **platform-agnostic Python library** that provides:

1. **Spatial Model**: Represent your home as a tree of Locations (rooms, floors, zones)
2. **Behavior Modules**: Plug-in architecture for Occupancy, Actions, Comfort, Energy
3. **Event System**: Location-aware event bus for wiring everything together

It's designed to be the "kernel" for smart home logic, with Home Assistant (or other platforms) as thin adapters on top.

---

## Project Structure

```
home-topology/
├── README.md                      # Quick start, installation
├── DESIGN.md                      # Architecture specification ⭐
├── CODING-STANDARDS.md            # Coding conventions ⭐
├── CONTRIBUTING.md                # How to contribute ⭐
├── CHANGELOG.md                   # Version history
├── pyproject.toml                 # Package configuration
├── Makefile                       # Development commands
├── example.py                     # Runnable example
│
├── src/home_topology/             # Core library
│   ├── __init__.py                # Package exports
│   │
│   ├── core/                      # Kernel components
│   │   ├── __init__.py
│   │   ├── location.py            # Location dataclass
│   │   ├── bus.py                 # Event, EventBus, EventFilter
│   │   └── manager.py             # LocationManager
│   │
│   └── modules/                   # Behavior plug-ins
│       ├── __init__.py
│       ├── base.py                # LocationModule base class
│       │
│       ├── occupancy/             # Occupancy tracking
│       │   ├── __init__.py
│       │   └── module.py          # OccupancyModule
│       │
│       └── actions/               # Automation execution
│           ├── __init__.py
│           └── module.py          # ActionsModule
│
├── tests/                         # Test suite
│   ├── __init__.py
│   ├── test_basic.py              # Core component tests
│   └── ...
│
└── docs/                          # Additional documentation
    └── project-overview.md        # This file
```

---

## Key Design Decisions

### 1. Platform Independence
**Decision**: Core library has zero Home Assistant dependencies.

**Why**: Testability, portability, clean architecture.

**How**: HA integration is a separate adapter layer that translates HA events → kernel events.

---

### 2. Synchronous EventBus
**Decision**: Events are processed synchronously with try/except per handler.

**Why**: Simplicity, predictability, easy debugging. No asyncio complexity.

**Escape Hatch**: Modules can use `run_in_background()` for I/O-heavy work.

---

### 3. Topology vs Behavior Separation
**Decision**: `LocationManager` stores structure and config, NOT runtime state or behavior.

**Why**: Clear separation of concerns. LocationManager is "database", Modules are "applications".

---

### 4. Entities Don't Require Areas
**Decision**: Entities can be assigned to Locations without HA Areas.

**Why**: 
- Works with "Areas done right" setups (auto-discovery)
- Doesn't punish advanced setups (cloud entities, system sensors)
- Provides "Inbox" workflow for unassigned entities

---

### 5. Feedback Loop Prevention
**Decision**: Multi-layer protection:
- Layer 1: Signal role separation (lights aren't occupancy inputs by default)
- Layer 2: Module deduplication (only emit events on actual state change)
- Layer 3: Optional bus-level deduplication

**Why**: Prevent "light on → occupancy → light on → ..." loops without complex state management.

---

### 6. Configuration Versioning
**Decision**: Modules version their configs and handle migration.

**Why**: Allows module evolution without breaking existing setups.

---

### 7. State Persistence Delegation
**Decision**: Modules provide `dump_state()`/`restore_state()`, host handles storage.

**Why**: Platform flexibility. Kernel doesn't care about disk I/O or storage format.

---

## Quick Start for Developers

### 1. Clone and Setup

```bash
git clone https://github.com/yourusername/home-topology.git
cd home-topology
python3 -m venv .venv
source .venv/bin/activate
make dev-install
```

### 2. Verify Setup

```bash
make example
```

Should output:
```
============================================================
home-topology Example
============================================================
...
✓ Kitchen occupancy: occupied=False, confidence=0.0
============================================================
```

### 3. Run Tests

```bash
make test-verbose
```

### 4. Make Changes

Follow [CODING-STANDARDS.md](../CODING-STANDARDS.md):
- Add tests for new functionality
- Update documentation
- Run `make check` before committing

### 5. Submit PR

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full process.

---

## Key Documents

| Document | Purpose |
|----------|---------|
| **README.md** | Quick start, installation, basic usage |
| **DESIGN.md** | Architecture spec, design decisions ⭐ |
| **CODING-STANDARDS.md** | Code style, patterns, anti-patterns ⭐ |
| **CONTRIBUTING.md** | Development workflow, PR process ⭐ |
| **CHANGELOG.md** | Version history, release notes |

**⭐ = Must read before contributing**

---

## Development Commands

See `make help` for all commands. Most useful:

```bash
make check          # Format, lint, typecheck, test (run before commit)
make test-cov       # Test with coverage report
make example        # Run example script
make format         # Format code with black
make lint           # Run ruff linter
make typecheck      # Run mypy type checker
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                Home Assistant                       │
│          (or other platform adapter)                │
└────────────────┬────────────────────────────────────┘
                 │ HA Events → kernel Events
                 │ Module State → HA Entities
                 │
┌────────────────▼────────────────────────────────────┐
│              home-topology Kernel                   │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │ Location     │  │   EventBus   │  │ Modules  │ │
│  │ Manager      │◄─┤              ├─►│          │ │
│  │              │  │              │  │ Occupancy│ │
│  │ - Topology   │  │ - Publish    │  │ Actions  │ │
│  │ - Config     │  │ - Subscribe  │  │ Comfort  │ │
│  │ - Entities   │  │ - Filtering  │  │ Energy   │ │
│  └──────────────┘  └──────────────┘  └──────────┘ │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Data Flow

1. **Platform → Kernel**: HA state change → `Event(type="sensor.state_changed")`
2. **Kernel Processing**: EventBus routes to OccupancyModule
3. **Module Logic**: OccupancyModule updates internal state
4. **Semantic Event**: OccupancyModule emits `Event(type="occupancy.changed")`
5. **Actions React**: ActionsModule receives occupancy event, executes rules
6. **Kernel → Platform**: ActionsModule calls HA service via adapter

---

## Modules in Detail

### OccupancyModule

**Purpose**: Track occupancy state per Location.

**Inputs**:
- Motion sensors
- Presence sensors  
- Door/window sensors (configurable)
- Media player state

**Outputs**:
- `occupancy.changed` events
- Per-location state: `occupied` (bool), `confidence` (0-1)

**Features** (planned):
- Timeout logic (simple, adaptive, hierarchy)
- Upward propagation (child occupied → parent occupied)
- Downward confidence boost

---

### ActionsModule

**Purpose**: Execute automations based on semantic events.

**Inputs**:
- Semantic events (`occupancy.changed`, etc.)
- Time of day, sun position, entity states

**Outputs**:
- Platform service calls (lights, climate, etc.)
- `action.executed` events for observability

**Features** (planned):
- Rule-based triggers and conditions
- Configurable state checking (trust device state or always send commands)
- Action history/logging

---

## Testing Philosophy

### Unit Tests
Test components in isolation:
- `LocationManager` hierarchy queries
- `EventBus` filtering
- Module logic

**No HA required**. Pure Python.

### Integration Tests
Test module interactions:
- Occupancy emits event → Actions reacts
- Hierarchy propagation

Still pure Python.

### HA Integration Tests
Test adapter layer:
- HA events → kernel
- Kernel state → HA entities

Requires HA test harness.

---

## Current Status

**Phase**: Initial Development (v0.1.0-alpha)

**Complete**:
- ✅ Core data structures (Location, Event, EventBus, LocationManager)
- ✅ Module architecture and base classes
- ✅ Skeleton implementations (OccupancyModule, ActionsModule)
- ✅ Basic tests
- ✅ Documentation (DESIGN, CODING-STANDARDS, CONTRIBUTING)

**In Progress**:
- 🔨 OccupancyModule behavior implementation
- 🔨 ActionsModule behavior implementation

**Next**:
- State serialization
- Config migration
- HA integration adapter

---

## Roadmap

### v0.1.0 (Alpha)
- Core kernel functionality
- Basic Occupancy and Actions modules
- Test coverage >80%

### v0.2.0
- Adaptive occupancy timeout
- Hierarchy propagation
- Config migration support

### v0.3.0
- Home Assistant integration (separate repo)
- UI for location/entity management
- Module config UI

### v1.0.0 (Stable)
- Production-ready Occupancy and Actions
- Full HA integration
- Documentation site

### Future
- ComfortModule
- EnergyModule
- SecurityModule

---

## Questions?

- **Issues**: Bug reports, feature requests
- **Discussions**: Questions, ideas, help
- **Discord**: Real-time chat (link TBD)

See [CONTRIBUTING.md](../CONTRIBUTING.md) for details.

---

## License

TBD (likely MIT or Apache-2.0)

---

**Document Status**: Living Document  
**Last Updated**: 2024-11-24

