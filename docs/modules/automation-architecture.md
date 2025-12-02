# Automation Engine Architecture

**Last Updated**: 2025-11-26

---

## Overview

The automation system follows a layered architecture where domain-specific modules (lighting, climate, media) build on top of a generic automation engine.

```
┌─────────────────────────────────────────────────────────────┐
│                     Domain Modules                           │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐ │
│  │ Lighting  │  │  Climate  │  │   Media   │  │Appliances │ │
│  │  Module   │  │  Module   │  │  Module   │  │  Module   │ │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘ │
│        │              │              │              │        │
│        └──────────────┴──────┬───────┴──────────────┘        │
│                              │                               │
│                              ▼                               │
│               ┌──────────────────────────┐                   │
│               │   Automation Engine      │                   │
│               │   (triggers, conditions, │                   │
│               │    actions, rules)       │                   │
│               └──────────────────────────┘                   │
│                              │                               │
│               ┌──────────────┴──────────────┐                │
│               │                             │                │
│               ▼                             ▼                │
│      ┌─────────────────┐          ┌─────────────────┐        │
│      │    Occupancy    │          │    EventBus     │        │
│      │     Module      │          │    (kernel)     │        │
│      └─────────────────┘          └─────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Module Structure

```
src/home_topology/modules/
├── automation/           # Core automation engine
│   ├── __init__.py       # Public API
│   ├── adapter.py        # Platform adapter interface
│   ├── engine.py         # Rule processing engine
│   ├── evaluators.py     # Condition evaluators
│   ├── models.py         # Data models (rules, triggers, conditions, actions)
│   ├── module.py         # AutomationModule (LocationModule implementation)
│   └── presets.py        # Generic presets (switch, fan, media off)
│
├── lighting/             # Lighting domain module
│   ├── __init__.py       # Public API
│   └── presets.py        # Lighting presets (lights on/off, adaptive, scenes)
│
├── actions/              # DEPRECATED - backwards compatibility shim
│   └── __init__.py       # Re-exports from automation/ and lighting/
│
├── occupancy/            # Occupancy tracking module
│   └── ...
│
└── base.py               # LocationModule base class
```

## Design Principles

### 1. Layered Architecture

- **Automation Engine**: Generic rule-based automation (triggers → conditions → actions)
- **Domain Modules**: Provide domain-specific APIs and presets using the engine

### 2. Platform Agnostic

The core library doesn't know about Home Assistant (or any other platform):

- **PlatformAdapter**: Abstract interface for service calls and state queries
- **StateCondition**: Check entity states without knowing implementation
- **ServiceCallAction**: Execute services without platform coupling

The integration layer (separate repo) provides the concrete adapter.

### 3. Simple Configuration, Complex Behavior

Domain modules translate simple configuration:

```python
# Simple domain API
lights_on_when_occupied("kitchen", "light.kitchen", brightness_pct=80)
```

Into automation rules:

```python
# Generated internally
AutomationRule(
    id="kitchen",
    trigger=EventTriggerConfig(event_type="occupancy.changed", ...),
    conditions=[StateCondition(entity_id="sun.sun", state="below_horizon")],
    actions=[ServiceCallAction(service="light.turn_on", ...)],
)
```

### 4. Host-Controlled Scheduling

The engine is synchronous. Delays and time-based triggers are recorded but executed by the host platform:

```python
# Engine records delay, returns immediately
actions=[
    DelayAction(seconds=60),  # Host schedules this
    ServiceCallAction(service="light.turn_off", ...),
]
```

This keeps the core library simple and testable.

## Components

### Automation Engine (`automation/engine.py`)

Core responsibilities:
- Match events to rule triggers
- Evaluate conditions
- Execute actions via platform adapter
- Track execution history
- Handle execution modes (SINGLE, RESTART, PARALLEL)

### Platform Adapter (`automation/adapter.py`)

Abstract interface:
- `call_service(domain, service, entity_id, data)` - Execute service calls
- `get_state(entity_id)` - Get entity state
- `get_numeric_state(entity_id)` - Get numeric sensor value
- `get_current_time()` - Get current time

### Condition Evaluator (`automation/evaluators.py`)

Evaluates condition types:
- `TimeOfDayCondition` - Time window (supports midnight spanning)
- `StateCondition` - Entity state check
- `NumericStateCondition` - Numeric comparison
- `LuxLevelCondition` - Light level check
- `LocationOccupiedCondition` - Occupancy check
- `DayOfWeekCondition` - Day filter

### Lighting Module (`lighting/`)

Provides lighting-specific presets:
- `lights_on_when_occupied()` - Turn on lights when occupied
- `lights_off_when_vacant()` - Turn off lights when vacant
- `scene_when_occupied()` - Activate scene when occupied
- `adaptive_lighting()` - Brightness by time of day

## Migration from Actions

The `actions/` module is deprecated. Migration path:

```python
# Old (deprecated)
from home_topology.modules.actions import ActionsModule, lights_on_when_occupied

# New
from home_topology.modules.automation import AutomationModule
from home_topology.modules.lighting import lights_on_when_occupied
```

The backwards compatibility shim in `actions/__init__.py` re-exports all symbols for gradual migration.

## Future Domain Modules

Planned modules following the same pattern:

### Climate Module (future)
```python
from home_topology.modules.climate import (
    set_temperature_when_occupied,
    eco_mode_when_vacant,
    schedule_temperature,
)
```

### Media Module (future)
```python
from home_topology.modules.media import (
    pause_when_vacant,
    resume_when_occupied,
    volume_by_time_of_day,
)
```

### Appliances Module (future)
```python
from home_topology.modules.appliances import (
    power_off_when_vacant,
    schedule_operation,
    energy_limit,
)
```

## Testing

Each module has comprehensive tests:

```
tests/modules/
├── automation/
│   ├── test_engine.py      # Engine tests
│   ├── test_evaluators.py  # Condition evaluator tests
│   └── test_models.py      # Model serialization tests
│
├── lighting/
│   └── test_presets.py     # Lighting preset tests
│
└── actions/                # Backwards compat tests (deprecated)
    └── ...
```

Run tests:
```bash
make test                    # All tests
pytest tests/modules/automation/  # Automation only
pytest tests/modules/lighting/    # Lighting only
```

## Status

| Module | Status | Tests |
|--------|--------|-------|
| `automation/` | ✅ Complete | 59 tests |
| `lighting/` | ✅ Complete | 14 tests |
| `actions/` | ⚠️ Deprecated | Uses compat shim |
| `climate/` | 📋 Planned | - |
| `media/` | 📋 Planned | - |
| `appliances/` | 📋 Planned | - |


