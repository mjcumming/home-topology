# home-topology Design Specification v1.3

> This document defines the architectural decisions, core principles, and implementation rules for the home-topology kernel.

**Status**: Active  
**Last Updated**: 2024-11-24

---

## 1. Core Philosophy

`home-topology` is a **platform-agnostic home topology kernel** that provides:

1. **Topology** - A spatial model of your home (Locations)
2. **Behavior** - Pluggable modules (Occupancy, Actions, Comfort, Energy)
3. **Events** - Location-aware event routing (EventBus)

### Key Principles

- **Platform Independence**: Core library has zero dependency on Home Assistant
- **Clean Separation**: Topology (LocationManager) owns structure, not behavior
- **Module Architecture**: Behavior is implemented as independent, composable modules
- **Testability**: Pure Python, fully testable without spinning up HA or any platform

---

## 2. Division of Responsibilities

The kernel separates concerns into three primary components:

### LocationManager (Data & Structure)
**Owns**: Topology, configuration storage, entity mappings  
**Does NOT**: Implement behavior, subscribe to events, maintain runtime state

- ✅ Store location tree
- ✅ Provide graph queries (parent, children, ancestors, descendants)
- ✅ Maintain entity → location mappings
- ✅ Store per-location module configurations

### EventBus (Communication)
**Owns**: Event routing, filtering, delivery  
**Does NOT**: Implement logic, make decisions, store state

- ✅ Publish events to subscribers
- ✅ Filter events by type, location, hierarchy
- ✅ Isolate errors per handler (try/except)

### Modules (Behavior)
**Owns**: Feature logic, runtime state, semantic events  
**Does NOT**: Modify topology, change entity mappings, depend on platform APIs

- ✅ Subscribe to events
- ✅ Implement occupancy/actions/comfort/energy logic
- ✅ Maintain runtime state
- ✅ Emit semantic events

**Why this separation?**

This prevents the "God Object" anti-pattern where one component does everything. Each component has a single, clear responsibility, making the system:
- Easier to test (mock one component, test another)
- Easier to extend (add modules without touching core)
- Easier to reason about (clear boundaries)

---

## 3. Location Model

### 3.1 What is a Location?

A `Location` represents a logical space in the home:
- Physical: room, floor, hallway, closet
- Virtual: "upstairs", "guest areas", "night zone"
- Special: "outside", "garage", "whole house"

### 3.2 Location Dataclass

```python
@dataclass
class Location:
    id: str                          # Unique identifier
    name: str                        # Human-readable name
    parent_id: Optional[str]         # Parent location (None = root)
    ha_area_id: Optional[str]        # Optional link to HA Area
    entity_ids: List[str]            # Platform entities in this location
    modules: Dict[str, Dict]         # Per-module config blobs
```

### 3.3 Location Hierarchy

Locations form a **tree**:
- `house → main_floor → kitchen → kitchen_table_zone`
- Each location has zero or one parent
- Locations can have multiple children
- Root locations (e.g., "house") have `parent_id = None`

### 3.4 Entity-Location Mapping

**Design Decision**: Entities do NOT require Home Assistant Areas.

Rules:
- ✅ Entities can be assigned to Locations **with or without** HA Areas
- ✅ `ha_area_id` on Location is **optional** (used for convenience/discovery)
- ✅ Entities without Areas appear in **global "Unassigned" pool**
- ✅ Users can manually assign any entity to any Location
- ✅ Integration can auto-suggest/auto-link entities when HA Area matches

Benefits:
- Works with "Areas done right" setups (auto-discovery)
- Doesn't punish advanced setups (cloud entities, system entities, Area-less devices)
- Provides "Inbox" workflow for unassigned entities

---

## 4. LocationManager

### 4.1 Responsibilities

The `LocationManager` owns **topology and configuration**, not behavior.

It provides:
- ✅ Location CRUD (create, read, update, delete)
- ✅ Hierarchy queries: `parent_of`, `children_of`, `ancestors_of`, `descendants_of`
- ✅ Entity-to-location mapping
- ✅ Per-location module configuration storage

### 4.2 Key Methods

```python
class LocationManager:
    def create_location(...) -> Location
    def get_location(location_id: str) -> Optional[Location]
    def parent_of(location_id: str) -> Optional[Location]
    def children_of(location_id: str) -> List[Location]
    def ancestors_of(location_id: str) -> List[Location]
    def descendants_of(location_id: str) -> List[Location]
    def add_entity_to_location(entity_id: str, location_id: str)
    def get_entity_location(entity_id: str) -> Optional[str]
    def set_module_config(location_id: str, module_id: str, config: Dict)
    def get_module_config(location_id: str, module_id: str) -> Optional[Dict]
```

---

## 5. Event Bus

### 5.1 Event Model

```python
@dataclass
class Event:
    type: str                    # "sensor.state_changed", "occupancy.changed"
    source: str                  # "ha", "occupancy", "actions"
    location_id: Optional[str]   # Location this event relates to
    entity_id: Optional[str]     # Entity this event relates to
    payload: Dict[str, Any]      # Event-specific data
    timestamp: datetime          # When event occurred (UTC)
```

### 5.2 Synchronous EventBus

**Design Decision**: EventBus is **synchronous** by default.

Rationale:
- Simple, predictable execution order
- Easy to reason about and debug
- Handlers are fast, CPU-bound operations
- No asyncio complexity in the core kernel

For I/O-heavy work, modules use `run_in_background(coro)` helper.

### 5.3 Error Isolation

**Design Decision**: Each handler is wrapped in `try/except`.

```python
def publish(self, event: Event):
    for filter, handler in self._handlers:
        if filter.matches(event):
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in handler {handler.__name__}: {e}")
```

**Guarantee**: One bad module cannot crash the kernel.

### 5.4 Event Filtering

Subscribers can filter by:
- `event_type`: Only specific event types
- `location_id`: Only events for a specific location
- `include_ancestors`: Include events from ancestor locations
- `include_descendants`: Include events from descendant locations

Example:
```python
# Subscribe to occupancy changes in kitchen and all its sub-zones
bus.subscribe(
    handler=my_handler,
    event_filter=EventFilter(
        event_type="occupancy.changed",
        location_id="kitchen",
        include_descendants=True,
    )
)
```

### 5.5 Feedback Loop Prevention

**Design Decision**: Multiple layers of loop protection.

#### Layer 1: Signal Role Separation

Modules separate signals into **primary** (direct triggers) and **secondary** (confidence boosters):

**Primary Signals** - Can directly trigger state changes:
- ✅ Motion sensors - Direct presence indicator
- ✅ Presence sensors - Direct presence indicator  
- ✅ Door/window contacts - Configurable entrance/exit detection

**Secondary Signals** - Adjust confidence, don't directly trigger:
- ✅ Lights ON - Increases confidence but doesn't directly trigger "occupied"
- ✅ Switches/appliances ON - Increases confidence
- ✅ Media players playing - Increases confidence
- ✅ Power consumption - Increases confidence

**Why?** This prevents loops:
- Actions turns light ON → Light feeds into occupancy as confidence boost
- But light ON alone doesn't trigger "occupied" directly
- Motion sensor still required for primary trigger
- Result: No loop, but we still use light state intelligently

See [docs/modules/occupancy-design.md](./docs/modules/occupancy-design.md) for detailed signal handling.

#### Layer 2: Module-Level Deduplication

Modules only emit semantic events when state **actually changes**.

```python
# Occupancy module
def _update_state(self, location_id: str, new_state: bool):
    old_state = self._state[location_id]
    if old_state.occupied != new_state:  # Only emit if changed
        self._state[location_id] = new_state
        self._bus.publish(Event(type="occupancy.changed", ...))
```

This prevents: `True → True → True` spam from re-triggering actions.

#### Layer 3: Optional Bus-Level Deduplication

EventBus can drop exact duplicate semantic events within a time window.

This is a **safety net** for misconfigured setups, not the primary defense.

---

## 6. Modules

### 6.1 Module Interface

All modules implement the `LocationModule` protocol:

```python
class LocationModule(ABC):
    @property
    def id(self) -> str: ...
    
    @property
    def CURRENT_CONFIG_VERSION(self) -> int: ...
    
    def attach(self, bus: EventBus, loc_manager: LocationManager) -> None: ...
    def default_config(self) -> Dict: ...
    def location_config_schema(self) -> Dict: ...
    def migrate_config(self, config: Dict) -> Dict: ...
    def on_location_config_changed(self, location_id: str, config: Dict) -> None: ...
    def dump_state(self) -> Dict: ...
    def restore_state(self, state: Dict) -> None: ...
```

### 6.2 Module Lifecycle

1. **Instantiation**: `module = OccupancyModule()`
2. **Attachment**: `module.attach(bus, loc_manager)`
   - Module subscribes to events
   - Captures references to bus and location manager
3. **Configuration**: Per-location configs loaded from `location.modules["occupancy"]`
4. **Operation**: Module reacts to events, maintains state, emits semantic events
5. **Persistence**: Host platform calls `dump_state()` / `restore_state(state)`

### 6.3 Configuration Versioning

**Design Decision**: Modules version their configs and handle migration.

Each module has:
```python
CURRENT_CONFIG_VERSION = 3

def migrate_config(self, config: Dict) -> Dict:
    version = config.get("version", 1)
    
    if version < 2:
        # Migrate v1 → v2
        config = self._migrate_v1_to_v2(config)
    
    if version < 3:
        # Migrate v2 → v3
        config = self._migrate_v2_to_v3(config)
    
    config["version"] = self.CURRENT_CONFIG_VERSION
    return config
```

**Rules**:
- Every config blob has a `"version"` key
- Modules handle their own migrations
- Migration is non-destructive (old configs remain loadable)
- Host platform (HA integration) calls `migrate_config` on load

### 6.4 Configuration Schema

Modules expose a **JSON-schema-like** structure for UI generation:

```python
def location_config_schema(self) -> Dict:
    return {
        "type": "object",
        "properties": {
            "motion_sensors": {
                "type": "array",
                "title": "Motion Sensors",
                "description": "Entity IDs for motion detection",
                "items": {"type": "string"},
            },
            "timeout_seconds": {
                "type": "integer",
                "title": "Timeout (seconds)",
                "minimum": 0,
                "default": 300,
            },
        },
    }
```

Benefits:
- UIs can render forms dynamically
- No custom frontend code per module
- Schema-driven validation

### 6.5 State Persistence

**Design Decision**: Modules provide state dump/restore; host handles storage.

```python
# Module side
def dump_state(self) -> Dict:
    return {
        "location_states": self._state,
        "timers": self._timers,
        "version": self.STATE_VERSION,
    }

def restore_state(self, state: Dict) -> None:
    if state.get("version") == self.STATE_VERSION:
        self._state = state["location_states"]
        self._timers = state["timers"]
    else:
        # State is stale, reset to defaults
        self._initialize_default_state()
```

**Rules**:
- Modules serialize their own runtime state
- Host platform (HA integration) stores/loads the blob
- Modules handle staleness/version mismatches gracefully
- State persistence is **optional** (modules can be stateless)

### 6.6 Built-In Modules

The `home-topology` kernel ships with these modules:

- **OccupancyModule** - Track occupancy state per location  
  See [docs/modules/occupancy-design.md](./docs/modules/occupancy-design.md)

- **ActionsModule** - Execute automations based on semantic events  
  See [docs/modules/actions-design.md](./docs/modules/actions-design.md)

Future modules:
- **ComfortModule** - Temperature, humidity, air quality per location
- **EnergyModule** - Power, energy consumption per location
- **SecurityModule** - Alarm state, lock state per location

---

## 7. Home Assistant Integration (Separate Component)

### 7.1 Adapter Layer

`custom_components/home_topology/` is a **thin adapter**:

**HA → Kernel**:
- Translate HA state changes → `Event(type="sensor.state_changed")`
- Feed into EventBus

**Kernel → HA**:
- Expose module state as HA entities
  - `binary_sensor.kitchen_occupied`
  - `sensor.kitchen_occupancy_confidence`
- Execute actions via HA service calls

### 7.2 Configuration UI

Provide a UI panel for:
- Location management (create, edit, delete, reorder)
- Entity assignment (drag-and-drop from Unassigned inbox)
- Per-location module config (dynamic forms from schemas)
- Module enable/disable per location

### 7.3 State Persistence

HA integration stores:
- Locations → `.storage/home_topology.locations.json`
- Module state → `.storage/home_topology.module_state.json`

On startup:
1. Load locations into `LocationManager`
2. Attach modules
3. Restore module state via `restore_state()`

---

## 8. Testing Strategy

### 8.1 Unit Tests (Pure Python)

Test core components in isolation:
- `LocationManager` hierarchy queries
- `EventBus` filtering and error handling
- Module logic (occupancy timeout, action conditions)

**No HA required**.

### 8.2 Integration Tests

Test module interactions:
- Occupancy emits event → Actions reacts
- Parent occupancy propagation
- Config migration across versions

### 8.3 HA Integration Tests

Test adapter layer:
- HA state changes → kernel events
- Module state → HA entities
- UI config persistence

---

## 9. Performance Considerations

### 9.1 Synchronous EventBus

Expected load:
- 10-100 locations
- 100-1000 entities
- 10-100 events/second peak

Synchronous bus is sufficient for this scale.

### 9.2 Hierarchy Queries

`ancestors_of` and `descendants_of` walk the tree on each call.

For typical home (3-4 levels, 50 locations), this is negligible.

If needed, cache graph queries with invalidation on topology changes.

### 9.3 Module State

Modules maintain per-location state in memory (dicts).

For 100 locations × 5 modules × 1KB state = ~500KB total.

State persistence is triggered by HA (e.g., on shutdown, periodic backup).

---

## 10. Design Decisions Summary

### 10.1 Synchronous EventBus
- **Decision**: EventBus is synchronous, handlers wrapped in try/except
- **Rationale**: Simplicity, predictability, error isolation
- **Escape hatch**: `run_in_background()` for I/O

### 10.2 Platform Independence
- **Decision**: Core library has zero HA dependencies
- **Rationale**: Testability, portability, clean architecture

### 10.3 Division of Responsibilities
- **Decision**: LocationManager = data, Modules = behavior, EventBus = routing
- **Rationale**: Separation of concerns, module independence

### 10.4 Config Versioning
- **Decision**: Modules version and migrate their own configs
- **Rationale**: Module evolution, backward compatibility

### 10.5 State Persistence Delegation
- **Decision**: Modules dump/restore state, host handles storage
- **Rationale**: Platform flexibility, module doesn't care about disk I/O

### 10.6 Entity–Location Mapping & Inbox
- **Decision**: Entities don't require HA Areas
- **Rationale**: Flexibility, supports advanced setups, provides discovery UX

### 10.7 Runtime State Serialization
- **Decision**: Modules handle staleness/version mismatches gracefully
- **Rationale**: Resilience to code updates, state corruption

### 10.8 Feedback Loop Mitigation
- **Decision**: Signal roles + module dedupe + optional bus dedupe
- **Rationale**: Reliability without complex state management

### 10.9 Configurable Action State Checking
- **Decision**: Actions can trust or ignore device state
- **Rationale**: Supports flaky devices, user preference

---

## 11. Non-Goals (Out of Scope)

- ❌ Multi-home support (one kernel per home)
- ❌ Cloud sync (host platform's responsibility)
- ❌ Machine learning models in core (modules can use external ML)
- ❌ Historical data storage (use platform's historian)
- ❌ Authentication/authorization (host platform's responsibility)
- ❌ WebSocket API (host platform exposes kernel state)

---

## 12. Future Considerations

### 12.1 Additional Modules
- **ComfortModule**: Temperature, humidity, air quality per location
- **EnergyModule**: Power, energy consumption per location
- **SecurityModule**: Alarm state, lock state per location

### 12.2 Module Dependencies
Some modules may depend on others:
- Actions may depend on Occupancy
- Comfort may depend on Occupancy + Energy

Design TBD: explicit dependency graph or implicit (modules just subscribe to each other's events).

### 12.3 Multi-Kernel Scenarios
Advanced users may want multiple kernels:
- "Main house" kernel
- "Guest house" kernel
- "Workshop" kernel

Each with independent topology and modules.

Host platform (HA) could manage multiple kernel instances.

---

## 13. Glossary

- **Location**: A logical space in the home (room, floor, zone)
- **Entity**: A platform object (sensor, switch, light) from HA or other platforms
- **Module**: A plug-in that adds behavior to locations
- **Event**: A message on the EventBus
- **Semantic Event**: High-level event from modules (e.g., `occupancy.changed`)
- **Platform Event**: Low-level event from platform (e.g., `sensor.state_changed`)
- **Kernel**: The core `home-topology` library (LocationManager + EventBus)
- **Host Platform**: The system running the kernel (e.g., Home Assistant)
- **Adapter**: The integration layer between kernel and platform

---

## Version History

- **v1.0**: Initial design (Location, EventBus, Modules)
- **v1.1**: Added hierarchy propagation, config schemas
- **v1.2**: Clarified entity-Area relationship, feedback loop prevention, configurable action behavior, state persistence
- **v1.3**: Refactored - moved module implementation details to separate docs, added Division of Responsibilities section

---

**Document Status**: Active  
**Last Updated**: 2024-11-24
