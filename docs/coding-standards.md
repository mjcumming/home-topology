# Coding Standards for home-topology

> These standards ensure consistency, maintainability, and quality across the codebase.

---

## 1. File and Directory Naming

### 1.1 Directory Names
**Rule**: No underscores in directory names. Use hyphens for multi-word names.

✅ **Good**:
```
home-topology/
docs/
release-notes/
```

❌ **Bad**:
```
home_topology/      # Exception: Python package names MUST use underscores
doc_files/
release_notes/
```

**Exception**: The `src/home_topology/` directory uses an underscore because Python requires valid identifiers for package names.

### 1.2 Python File Names
**Rule**: Use lowercase with underscores for Python modules (PEP 8 convention).

✅ **Good**:
```python
location.py
bus.py
manager.py
occupancy_module.py  # If needed
```

❌ **Bad**:
```python
Location.py
eventBus.py
OccupancyModule.py
```

### 1.3 Test File Names
**Rule**: Prefix test files with `test_`.

✅ **Good**:
```python
test_location.py
test_bus.py
test_occupancy_module.py
```

---

## 2. Python Code Style

### 2.1 Base Standards
We follow **PEP 8** with these tools:
- **Formatter**: `black` (line length: 100)
- **Linter**: `ruff`
- **Type Checker**: `mypy` (strict mode)

### 2.2 Formatting Rules

```python
# Line length: 100 characters
MAX_LINE_LENGTH = 100

# Indentation: 4 spaces (no tabs)
def example_function():
    if condition:
        do_something()

# Imports: organized in three groups
import os                          # stdlib
import sys

from typing import Dict, List      # stdlib typing

from home_topology.core import Location  # local imports

# String quotes: Prefer double quotes for consistency
name = "Kitchen"
description = "Main cooking area"

# Trailing commas in multi-line structures
items = [
    "first",
    "second",
    "third",  # ← trailing comma
]
```

### 2.3 Naming Conventions

```python
# Classes: PascalCase
class LocationManager:
    pass

class OccupancyModule:
    pass

# Functions/methods: snake_case
def create_location():
    pass

def get_entity_location():
    pass

# Variables: snake_case
location_id = "kitchen"
motion_sensors = ["sensor.motion_1"]

# Constants: UPPER_SNAKE_CASE
CURRENT_CONFIG_VERSION = 3
DEFAULT_TIMEOUT_SECONDS = 300

# Private attributes/methods: leading underscore
class MyClass:
    def __init__(self):
        self._internal_state = {}
    
    def _helper_method(self):
        pass
```

### 2.4 Type Hints

**Rule**: All public functions and methods must have type hints.

✅ **Good**:
```python
def create_location(
    id: str,
    name: str,
    parent_id: Optional[str] = None,
) -> Location:
    """Create a new location."""
    return Location(id=id, name=name, parent_id=parent_id)

def get_location(location_id: str) -> Optional[Location]:
    """Get a location by ID."""
    return self._locations.get(location_id)
```

❌ **Bad**:
```python
def create_location(id, name, parent_id=None):  # No type hints
    return Location(id=id, name=name, parent_id=parent_id)
```

### 2.5 Docstrings

**Rule**: All public classes, methods, and functions must have docstrings.

Format: Google style

```python
def ancestors_of(self, location_id: str) -> List[Location]:
    """
    Get all ancestors of a location.
    
    Args:
        location_id: The location ID
        
    Returns:
        List of ancestor Locations, ordered from parent to root
        
    Example:
        >>> mgr.ancestors_of("kitchen")
        [Location(id="main_floor"), Location(id="house")]
    """
    ancestors = []
    current = self.parent_of(location_id)
    while current:
        ancestors.append(current)
        current = self.parent_of(current.id)
    return ancestors
```

For simple getters/setters, one-line docstrings are acceptable:
```python
def get_location(self, location_id: str) -> Optional[Location]:
    """Get a location by ID."""
    return self._locations.get(location_id)
```

---

## 3. Architecture Patterns

### 3.1 Separation of Concerns

**Rule**: Follow the design spec's separation:
- `LocationManager`: Topology and config only
- Modules: Behavior and runtime state only
- `EventBus`: Event routing only

❌ **Bad**:
```python
class LocationManager:
    def calculate_occupancy(self, location_id):  # Wrong! Behavior in topology
        pass
```

✅ **Good**:
```python
class OccupancyModule:
    def _calculate_occupancy(self, location_id):  # Right! Behavior in module
        pass
```

### 3.2 Dataclasses for Data

**Rule**: Use `@dataclass` for simple data containers.

✅ **Good**:
```python
from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class Location:
    id: str
    name: str
    parent_id: Optional[str] = None
    entity_ids: List[str] = field(default_factory=list)
    modules: Dict[str, Dict] = field(default_factory=dict)
```

### 3.3 Dependency Injection

**Rule**: Pass dependencies explicitly (no global state).

✅ **Good**:
```python
class OccupancyModule:
    def attach(self, bus: EventBus, loc_manager: LocationManager) -> None:
        self._bus = bus
        self._loc_manager = loc_manager
```

❌ **Bad**:
```python
# Global state
_global_bus = EventBus()

class OccupancyModule:
    def attach(self):
        self._bus = _global_bus  # Implicit dependency
```

### 3.4 Error Handling

**Rule**: Raise specific exceptions with helpful messages.

✅ **Good**:
```python
def create_location(self, id: str, name: str, parent_id: Optional[str] = None):
    if id in self._locations:
        raise ValueError(f"Location with id '{id}' already exists")
    
    if parent_id and parent_id not in self._locations:
        raise ValueError(f"Parent location '{parent_id}' does not exist")
```

**Rule**: Log errors but don't crash in event handlers.

```python
def publish(self, event: Event) -> None:
    for event_filter, handler in self._handlers:
        if event_filter.matches(event):
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    f"Error in event handler {handler.__name__}: {e}",
                    exc_info=True,
                )
                # Continue to next handler
```

---

## 4. Testing Standards

### 4.1 Test Organization

```
tests/
├── test_location.py          # Unit tests for Location dataclass
├── test_bus.py               # Unit tests for EventBus
├── test_manager.py           # Unit tests for LocationManager
├── modules/
│   ├── test_occupancy.py     # Unit tests for OccupancyModule
│   └── test_actions.py       # Unit tests for ActionsModule
└── integration/
    └── test_occupancy_actions.py  # Integration tests
```

### 4.2 Test Naming

```python
def test_location_creation():
    """Test basic Location dataclass creation."""
    pass

def test_location_manager_hierarchy_queries():
    """Test LocationManager parent/children/ancestors/descendants."""
    pass

def test_event_bus_error_isolation():
    """Test that one bad handler doesn't crash the bus."""
    pass
```

### 4.3 Test Structure (AAA Pattern)

```python
def test_location_manager_entity_mapping():
    """Test entity-to-location mapping."""
    # Arrange
    mgr = LocationManager()
    mgr.create_location(id="kitchen", name="Kitchen")
    
    # Act
    mgr.add_entity_to_location("binary_sensor.kitchen_motion", "kitchen")
    
    # Assert
    assert mgr.get_entity_location("binary_sensor.kitchen_motion") == "kitchen"
    kitchen = mgr.get_location("kitchen")
    assert "binary_sensor.kitchen_motion" in kitchen.entity_ids
```

### 4.4 Test Coverage Goals

- **Core library**: >90% coverage
- **Modules**: >80% coverage
- **HA integration**: >70% coverage (may require HA test harness)

### 4.5 Fixtures and Helpers

**Rule**: Use pytest fixtures for common setup.

```python
import pytest
from home_topology import LocationManager, EventBus

@pytest.fixture
def location_manager():
    """Provide a fresh LocationManager."""
    return LocationManager()

@pytest.fixture
def event_bus():
    """Provide a fresh EventBus."""
    return EventBus()

@pytest.fixture
def sample_topology(location_manager):
    """Provide a standard test topology."""
    location_manager.create_location(id="house", name="House")
    location_manager.create_location(id="main_floor", name="Main Floor", parent_id="house")
    location_manager.create_location(id="kitchen", name="Kitchen", parent_id="main_floor")
    return location_manager

def test_hierarchy(sample_topology):
    """Test using the fixture."""
    ancestors = sample_topology.ancestors_of("kitchen")
    assert len(ancestors) == 2
```

---

## 5. Logging

### 5.1 Logger Setup

```python
import logging

logger = logging.getLogger(__name__)

# Usage
logger.debug("Created location: %s", location.id)
logger.info("Occupancy changed: %s → %s", location.id, state.occupied)
logger.warning("Timeout not configured for location: %s", location.id)
logger.error("Failed to process event: %s", event, exc_info=True)
```

### 5.2 Log Levels

- `DEBUG`: Detailed diagnostic info (event processing, state transitions)
- `INFO`: Key events (location created, module attached, occupancy changed)
- `WARNING`: Unexpected but handled (missing config, stale state)
- `ERROR`: Failures (handler exceptions, invalid config)

### 5.3 Sensitive Data

**Rule**: Never log sensitive data (tokens, passwords, personal info).

✅ **Good**:
```python
logger.info("Entity %s mapped to location %s", entity_id, location_id)
```

❌ **Bad**:
```python
logger.info("Full config: %s", config)  # May contain secrets
```

---

## 6. Version Control

### 6.1 Commit Messages

Format:
```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, no logic change)
- `refactor`: Code restructuring (no behavior change)
- `test`: Adding/updating tests
- `chore`: Maintenance (dependencies, build)

Examples:
```
feat(occupancy): add adaptive timeout mode

Implements configurable timeout modes: simple, adaptive, hierarchy.
Adaptive mode learns from historical occupancy patterns.

Closes #42

---

fix(bus): prevent handler exceptions from crashing kernel

Wrapped all handlers in try/except to isolate errors.

---

docs(design): clarify entity-location mapping rules

Updated DESIGN.md section 11.6 to explain Areas are optional.
```

### 6.2 Branch Naming

- `main`: Stable, released code
- `develop`: Integration branch for next release
- `feat/feature-name`: Feature branches
- `fix/bug-description`: Bug fix branches
- `docs/topic`: Documentation updates

### 6.3 Pull Request Process

1. Create feature branch from `develop`
2. Implement changes with tests
3. Run full test suite locally
4. Create PR with description and linked issues
5. Pass CI checks (linting, typing, tests)
6. Code review by maintainer
7. Squash merge to `develop`

---

## 7. Dependencies

### 7.1 Core Library Rules

**Rule**: Core library (`src/home_topology/`) has **zero external dependencies**.

Allowed:
- Python stdlib only
- Type hints from `typing` module

Forbidden:
- `homeassistant.*`
- `requests`, `aiohttp` (use in HA integration, not core)
- Any platform-specific libraries

### 7.2 Development Dependencies

In `pyproject.toml`:
```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "black>=23.0",
    "ruff>=0.1.0",
    "mypy>=1.0",
]
```

---

## 8. Documentation

### 8.1 Required Documentation

Each module must have:
- Docstrings on all public classes/functions
- Usage examples in docstrings or separate examples file
- Configuration schema documentation

### 8.2 Documentation Files

- `README.md`: Overview, installation, quick example
- `docs/architecture.md`: Architecture, design decisions
- `docs/coding-standards.md`: Coding standards (this file)
- `CONTRIBUTING.md`: How to contribute
- `CHANGELOG.md`: Version history and release notes

### 8.3 Code Examples

Include runnable examples:
- `example.py`: Basic usage demonstration
- `examples/advanced-occupancy.py`: Advanced module usage
- `examples/custom-module.py`: How to write a custom module

---

## 9. Performance Guidelines

### 9.1 Premature Optimization

**Rule**: Prefer clarity over cleverness.

Write simple, readable code first. Optimize only when:
1. You have profiling data showing a bottleneck
2. The optimization doesn't harm readability significantly

### 9.2 Acceptable Patterns

✅ **Linear scans** for small collections (<100 items):
```python
def get_location(self, location_id: str) -> Optional[Location]:
    return self._locations.get(location_id)  # Dict lookup is fine
```

✅ **Tree walks** for typical home topology (3-4 levels):
```python
def ancestors_of(self, location_id: str) -> List[Location]:
    ancestors = []
    current = self.parent_of(location_id)
    while current:
        ancestors.append(current)
        current = self.parent_of(current.id)
    return ancestors
```

### 9.3 When to Optimize

Consider optimization if:
- Location count >500
- Event rate >1000/sec
- Module state >10MB
- Hierarchy depth >10 levels

Then:
- Cache hierarchy queries
- Use event batching
- Profile with `cProfile`

---

## 10. Security

### 10.1 Input Validation

**Rule**: Validate all external inputs.

```python
def create_location(self, id: str, name: str, parent_id: Optional[str] = None):
    if not id or not isinstance(id, str):
        raise ValueError("Location id must be a non-empty string")
    
    if not name or not isinstance(name, str):
        raise ValueError("Location name must be a non-empty string")
    
    if parent_id and parent_id not in self._locations:
        raise ValueError(f"Parent location '{parent_id}' does not exist")
```

### 10.2 State Restoration

**Rule**: Treat restored state as untrusted.

```python
def restore_state(self, state: Dict) -> None:
    """Restore runtime state from serialized form."""
    try:
        version = state.get("version")
        if version != self.STATE_VERSION:
            logger.warning("State version mismatch, resetting to defaults")
            self._initialize_default_state()
            return
        
        # Validate structure
        if "location_states" not in state:
            raise ValueError("Missing location_states in state blob")
        
        self._state = state["location_states"]
    except Exception as e:
        logger.error("Failed to restore state: %s", e, exc_info=True)
        self._initialize_default_state()
```

---

## 11. Tooling Configuration

### 11.1 pyproject.toml

```toml
[tool.black]
line-length = 100
target-version = ["py310"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

### 11.2 Pre-commit Checks

Before committing:
```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/

# Run tests
pytest tests/ -v --cov=home_topology
```

### 11.3 CI Pipeline

On every PR:
1. Run linters (ruff)
2. Run type checker (mypy)
3. Run test suite (pytest)
4. Check coverage (must not decrease)
5. Build package (ensure it installs)

---

## 12. Anti-Patterns to Avoid

### 12.1 God Objects
❌ Don't put everything in one class:
```python
class HomeTopology:  # BAD: Does too much
    def create_location(self): pass
    def publish_event(self): pass
    def calculate_occupancy(self): pass
    def execute_action(self): pass
```

✅ Separate concerns:
```python
class LocationManager: ...
class EventBus: ...
class OccupancyModule: ...
class ActionsModule: ...
```

### 12.2 Circular Imports
❌ Module A imports Module B which imports Module A

✅ Use dependency injection or move shared code to a common module.

### 12.3 Mutable Default Arguments
❌ **Bad**:
```python
def create_location(self, entity_ids=[]):  # Mutable default!
    pass
```

✅ **Good**:
```python
def create_location(self, entity_ids: Optional[List[str]] = None):
    if entity_ids is None:
        entity_ids = []
```

### 12.4 Bare Except
❌ **Bad**:
```python
try:
    handler(event)
except:  # Catches KeyboardInterrupt, SystemExit!
    pass
```

✅ **Good**:
```python
try:
    handler(event)
except Exception as e:  # Specific exception type
    logger.error("Handler failed: %s", e, exc_info=True)
```

---

## 13. Standards Enforcement

### 13.1 Automated Checks
- Formatting: `black --check`
- Linting: `ruff check`
- Type checking: `mypy`
- Tests: `pytest`

All must pass before merge.

### 13.2 Code Review Checklist
- [ ] Follows naming conventions
- [ ] Has type hints
- [ ] Has docstrings
- [ ] Has tests
- [ ] Follows architecture patterns
- [ ] No new external dependencies in core
- [ ] Commit messages follow format

### 13.3 Continuous Improvement
Standards evolve. Propose changes via:
1. Discussion in issue
2. Draft PR updating this document
3. Team consensus
4. Merge and announce

---

## 14. Summary: Quick Reference

| Category | Rule |
|----------|------|
| **Files** | No underscores in directory names (except `src/home_topology/`) |
| **Python** | PEP 8, black (100 chars), ruff, mypy strict |
| **Types** | All public functions/methods must have type hints |
| **Docs** | All public classes/functions must have docstrings |
| **Tests** | AAA pattern, pytest fixtures, >80% coverage |
| **Deps** | Core library: stdlib only |
| **Commits** | `<type>(<scope>): <subject>` format |
| **Errors** | Raise specific exceptions, log but don't crash in handlers |
| **Logging** | Use `logger = logging.getLogger(__name__)` |
| **Architecture** | LocationManager = topology, Modules = behavior, EventBus = routing |

---

**Document Status**: Active  
**Last Updated**: 2025-11-24

