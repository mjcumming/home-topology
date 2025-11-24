# home-topology

[![CI](https://github.com/mjcumming/home-topology/actions/workflows/ci.yml/badge.svg)](https://github.com/mjcumming/home-topology/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> A platform-agnostic **home topology kernel** for modeling spaces (Locations), attaching behavior (Modules), and wiring everything together with a location-aware **Event Bus**.

`home-topology` is the structural backbone for smart homes:

- It models **where things are** (rooms, floors, zones, virtual spaces).
- It lets you attach **modules** like Occupancy, Actions, Comfort, Energy.
- It routes **events** through this topology so modules can react cleanly.
- It stays **independent of Home Assistant** or any specific platform.

Think of it as a tiny "operating system" for your home's spatial model.  
Occupancy, automations, energy logic, etc. are apps running on top.

---

## Features

- 🧱 **Location graph (topology)**  
  Structured model of your home: house → floors → rooms → zones, with optional links to Home Assistant Areas.

- 🧠 **Modules as plug-ins**  
  Occupancy, Actions, Comfort, Energy, etc. are independent modules that attach to Locations and react to events.

- 🔁 **Location-aware Event Bus**  
  Simple, synchronous event pipeline with filters for type / location / ancestors / descendants.

- 🧩 **Schema-driven configuration**  
  Each module exposes a config schema; UIs can render dynamic forms per location without custom frontend code.

- 🧪 **Platform agnostic**  
  Core library has **no** dependency on Home Assistant. HA support is a thin adapter layer.

- 💾 **Config & state evolution**  
  Modules can version and migrate their configs, and optionally dump/restore runtime state via the host platform.

---

## Installation

```bash
pip install home-topology
```

(Placeholder – adjust once published.)

---

## Core Concepts

### Location

A `Location` is a logical space: a room, floor, area, or virtual zone.

```python
from dataclasses import dataclass
from typing import Optional, Dict, List

@dataclass
class Location:
    id: str
    name: str
    parent_id: Optional[str]
    ha_area_id: Optional[str]           # optional link to a HA Area
    entity_ids: List[str]               # platform entity IDs mapped here
    modules: Dict[str, Dict]            # per-module config blobs
```

Locations form a **hierarchy** (e.g. `house → main_floor → kitchen → kitchen_table_zone`).

### LocationManager

`LocationManager` owns the **topology and config**, not the behavior.

Responsibilities:

* Store the location tree.
* Provide graph queries: `parent_of`, `children_of`, `ancestors_of`, `descendants_of`.
* Maintain entity → location mappings.
* Store per-location module config:

  ```python
  location.modules["occupancy"]  # config for the Occupancy module on this location
  ```

It does **not** implement occupancy, energy, or actions logic.

### Event Bus

The **Event Bus** is a simple, synchronous dispatcher for domain events:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any

@dataclass
class Event:
    type: str                  # "sensor.state_changed", "occupancy.changed", ...
    source: str                # "ha", "occupancy", "actions", ...
    location_id: Optional[str]
    entity_id: Optional[str]
    payload: Dict[str, Any]
    timestamp: datetime
```

* `publish(event)` synchronously delivers events to subscribers.
* Handlers are wrapped in `try/except` so one bad module cannot crash the kernel.
* Modules treat handlers as **fast and CPU-bound**.
* A helper (`run_in_background`) is provided for I/O-heavy work.

### Modules

Modules are plug-ins that add behavior to the topology:

* **OccupancyModule** – computes `occupied` / `confidence` per Location.
* **ActionsModule** – runs automations in response to semantic events.
* **ComfortModule** (future) – room comfort metrics.
* **EnergyModule** (future) – room-level energy and power.

A module:

* Receives events from the Event Bus.
* Uses the `LocationManager` to understand hierarchy.
* Maintains its own runtime state.
* Emits **semantic events** that other modules can consume.

Example interface (simplified):

```python
class LocationModule:
    id: str
    CURRENT_CONFIG_VERSION: int

    def attach(self, bus, loc_manager) -> None:
        """Register event subscriptions and capture references."""

    def default_config(self) -> dict:
        """Default per-location config."""

    def location_config_schema(self) -> dict:
        """JSON-schema-like definition for UI configuration."""

    def migrate_config(self, config: dict) -> dict:
        """Upgrade older config versions to CURRENT_CONFIG_VERSION."""

    def on_location_config_changed(self, location_id: str, config: dict) -> None:
        """React to config updates for a given location."""

    def dump_state(self) -> dict:
        """Optional: serialize runtime state (host is responsible for storage)."""

    def restore_state(self, state: dict) -> None:
        """Optional: restore runtime state from serialized form."""
```

---

## Quick Example

> **Note:** This is illustrative, not a final API.

```python
from home_topology.core.manager import LocationManager
from home_topology.core.bus import EventBus, Event
from home_topology.modules.occupancy.module import OccupancyModule

# 1. Kernel components
loc_mgr = LocationManager()
bus = EventBus()

# 2. Create a simple topology
kitchen = loc_mgr.create_location(
    id="kitchen",
    name="Kitchen",
    parent_id="main_floor",
    ha_area_id="area.kitchen",
)

# Map a motion sensor entity to the kitchen
loc_mgr.add_entity_to_location("binary_sensor.kitchen_motion", "kitchen")

# 3. Attach the Occupancy module
occupancy = OccupancyModule()
occupancy.attach(bus, loc_mgr)

# Optionally override per-location config
loc_mgr.set_module_config(
    location_id="kitchen",
    module_id="occupancy",
    config={
        "version": occupancy.CURRENT_CONFIG_VERSION,
        "motion_sensors": ["binary_sensor.kitchen_motion"],
        "timeout_seconds": 300,
    },
)

# 4. Feed a sensor event into the kernel (e.g. from Home Assistant)
bus.publish(
    Event(
        type="sensor.state_changed",
        source="ha",
        location_id="kitchen",
        entity_id="binary_sensor.kitchen_motion",
        payload={"old_state": "off", "new_state": "on"},
        timestamp=datetime.utcnow(),
    )
)

# 5. Query occupancy state (implementation-dependent)
state = occupancy.get_location_state("kitchen")
print(state.occupied, state.confidence)
```

In a Home Assistant integration, you'd:

* Translate HA state changes → `Event`s.
* Expose module state back as HA entities.
* Optionally provide a UI to configure modules per location.

---

## Relationship to Home Assistant

`home-topology` is **not** a Home Assistant custom component.
It's a pure Python library that can *back* a HA integration (and other platforms).

A typical HA setup would add:

* `custom_components/home_topology/`

  * Uses this library to:

    * Build a location graph from HA Areas / devices / entities.
    * Feed HA events into the Event Bus.
    * Expose module state (e.g., occupancy sensors) back to HA.
    * Provide a UI for Locations and their modules (with an "Unassigned/Inbox" view for entities).

---

## Project Status

This is a **work-in-progress** architecture focused on:

* Clean separation between topology, events, and behavior.
* Extensibility via modules.
* Strong testability in pure Python (without spinning up HA).

Expect breaking changes while the core stabilizes.

---

## Development

### Quick Start

```bash
# Clone and setup
git clone https://github.com/mjcumming/home-topology.git
cd home-topology
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode
make dev-install

# Run tests
make test

# Run example
make example

# Run all checks
make check
```

### Documentation

**📖 Start Here**:
- **[README.md](./README.md)** - This file (project overview)
- **[WORK-TRACKING.md](./WORK-TRACKING.md)** ⭐ - Current sprint status, task dashboard

**📊 Daily Operations**:
- **[ADR-LOG.md](./ADR-LOG.md)** - Architecture decisions with rationale
- **[docs/open-questions.md](./docs/open-questions.md)** - Open questions needing answers

**🏗️ Architecture**:
- **[DESIGN.md](./DESIGN.md)** - Complete kernel architecture specification
- **[CODING-STANDARDS.md](./CODING-STANDARDS.md)** - Code style and patterns
- **[CONTRIBUTING.md](./CONTRIBUTING.md)** - How to contribute

**📦 Modules**:
- **[docs/modules/occupancy-design.md](./docs/modules/occupancy-design.md)** - Occupancy module specification
- **[docs/modules/occupancy-integration.md](./docs/modules/occupancy-integration.md)** - Occupancy integration status
- **[docs/modules/actions-design.md](./docs/modules/actions-design.md)** - Actions module specification

**📚 Reference**:
- **[docs/project-overview.md](./docs/project-overview.md)** - Detailed project guide
- **[docs/ai-guide.md](./docs/ai-guide.md)** - AI-assisted development guide
- **[CHANGELOG.md](./CHANGELOG.md)** - Version history

### Development Commands

```bash
make help          # Show all available commands
make test-cov      # Run tests with coverage
make format        # Format code with black
make lint          # Run ruff linter
make typecheck     # Run mypy type checker
make check         # Run all quality checks
```

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](./CONTRIBUTING.md) before submitting PRs.

Key guidelines:
- Follow [CODING-STANDARDS.md](./CODING-STANDARDS.md)
- Add tests for new functionality
- Update documentation
- Run `make check` before committing

---

## License

TBD – e.g., MIT or Apache-2.0.

---

## Links

- **Documentation**: [docs/](./docs/)
- **Issues**: [GitHub Issues](https://github.com/mjcumming/home-topology/issues)
- **Discussions**: [GitHub Discussions](https://github.com/mjcumming/home-topology/discussions)

