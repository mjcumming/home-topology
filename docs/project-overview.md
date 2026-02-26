# home-topology Project Overview

`home-topology` is a platform-agnostic kernel for home location graphs and behavior modules.

## What the Kernel Provides

1. Topology model (`Location`, `LocationManager`)
2. Event routing (`EventBus`, `EventFilter`)
3. Module runtime contracts (`LocationModule`)
4. Built-in modules:
- `occupancy`
- `automation`
- `ambient`
- `presence`
- `lighting` presets

## What Integrations Provide

1. Platform event translation (for example HA state changes -> kernel events)
2. State exposure back to platform entities
3. Persistent storage for topology/config/state
4. UI for location/module configuration

Topomation is the active Home Assistant integration that uses this kernel.

## Repository Layout

```text
home-topology/
├── src/home_topology/
│   ├── core/                    # Location + bus + manager
│   └── modules/                 # occupancy/automation/ambient/etc.
├── tests/
├── docs/
├── example.py
└── pyproject.toml
```

## Current Event Model

- Integrations publish normalized `occupancy.signal` events.
- `OccupancyModule` emits semantic `occupancy.changed` events.
- `AutomationModule` consumes semantic events and executes rules via an adapter.

## Quick Developer Flow

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
make check
make example
```

## Current Status

- Core kernel: active
- Occupancy: v3 model active (`TRIGGER`/`CLEAR` + command events)
- Automation engine: active (`automation` module; `actions` module is deprecated compatibility shim)
- Ambient module: active

## Related Docs

- [README.md](../README.md)
- [Architecture](./architecture.md)
- [Integration Guide](./integration/integration-guide.md)
- [Project Status](./project-status.md)
