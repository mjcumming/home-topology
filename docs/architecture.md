# home-topology Design Specification v1.5

> This document defines the architectural decisions, core principles, and implementation rules for the home-topology kernel.

**Status**: Active  
**Last Updated**: 2025-11-25

> **See also**: [Architecture Decisions](./decisions-pending.md) for high-level design rationale and decision log.

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
    parent_id: Optional[str]         # Parent location (None = root/unassigned)
    is_explicit_root: bool           # True = intentional root, False = unassigned when parent_id=None
    ha_area_id: Optional[str]        # Optional link to HA Area
    entity_ids: List[str]            # Platform entities in this location
    modules: Dict[str, Dict]         # Per-module config blobs
```

**Root vs Unassigned**: When `parent_id` is None:
- `is_explicit_root=True`: Intentional top-level (e.g., "House", "Garage")
- `is_explicit_root=False`: Discovered/unassigned (shows in Inbox)

### 3.3 Location Hierarchy

Locations form a **tree**:
- `house → main_floor → kitchen → kitchen_table_zone`
- Each location has zero or one parent
- Locations can have multiple children
- Root locations (e.g., "house") have `parent_id = None`

### 3.4 Entity-Location Mapping

**Design Decision**: Entities do NOT require platform-specific area assignments.

Rules:
- ✅ Entities can be assigned to Locations with or without platform area mappings
- ✅ `ha_area_id` on Location is **optional** (used for convenience/discovery)
- ✅ Entities/Locations without parents appear in "Unassigned" view
- ✅ Users can manually assign any entity to any Location
- ✅ Integration can auto-suggest/auto-link entities when platform areas match

Benefits:
- Works with well-organized platform setups (auto-discovery)
- Doesn't punish advanced setups (cloud entities, system entities, area-less devices)
- Provides "Inbox" workflow for unassigned items

### 3.5 Root vs Unassigned Locations

**Design Decision**: The kernel distinguishes "intentional roots" from "unassigned" via `is_explicit_root`.

The kernel does not have a special `Location` with `id: "unassigned"`. Instead:
- **Root locations**: `parent_id=None` AND `is_explicit_root=True`
- **Unassigned locations**: `parent_id=None` AND `is_explicit_root=False`

The UI/Integration uses `LocationManager.get_root_locations()` and `get_unassigned_locations()` to query these.

**Workflow**:
1. Integration discovers HA area → creates Location with `is_explicit_root=False`
2. User creates "House" → `is_explicit_root=True`
3. User drags Kitchen under House → `parent_id="house"`
4. User says "Garage is a standalone root" → `set_as_root("garage")`

This keeps the kernel self-describing while keeping "Inbox" as a UI concept.

### 3.6 Location Types (Downstream Concern)

**Design Decision**: The kernel is **type-agnostic**. Location types (Floor, Room, Zone, etc.) are an integration/UI responsibility, not a kernel concept.

The kernel provides:
- ✅ A tree structure (parent/child relationships)
- ✅ Storage for arbitrary metadata (via `modules` dict)
- ✅ No enforcement of what types of locations can contain what

The integration/UI layer is responsible for:
- ✅ Defining location types (Floor, Room, Zone, Suite, Outdoor, Building)
- ✅ Enforcing hierarchy rules (e.g., "Floors cannot be children of Rooms")
- ✅ Storing type metadata (either in integration's own store or in `modules["_meta"]`)
- ✅ Providing type-appropriate icons and UI treatment

**Why this separation?**

1. **Flexibility**: Different integrations may have different type taxonomies
2. **Simplicity**: Kernel stays minimal and focused on structure
3. **Extensibility**: New types can be added without kernel changes
4. **Power users**: API access can bypass UI constraints if needed

**Recommended approach for integrations**:

```python
# Option A: Integration maintains separate metadata
class LocationTypeRegistry:
    def get_type(self, location_id: str) -> str: ...
    def set_type(self, location_id: str, type: str): ...
    def can_parent(self, parent_type: str, child_type: str) -> bool: ...

# Option B: Store in modules dict by convention
loc_mgr.set_module_config(
    location_id="kitchen",
    module_id="_meta",  # Reserved for integration metadata
    config={"type": "room", "icon": "mdi:stove"}
)
```

> **See also**: [UI Design Spec](./ui/ui-design.md) section 5.3.1 for recommended type hierarchy and UI enforcement rules.

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

#### Layer 1: Integration-Driven Event Classification

The integration layer (not the core library) decides which entities send occupancy events. This prevents loops by design:

- Integration chooses what entities send TRIGGER/HOLD events
- Lights, switches, and other "output" devices are typically **not** configured to send events
- The core library simply processes events it receives - it has no knowledge of entity types

**Example**: Integration configures:
- `binary_sensor.kitchen_motion` → sends TRIGGER events ✅
- `light.kitchen` → NOT configured (prevents loop)

This is simpler than the original design and puts control where it belongs - in the integration layer that understands the platform.

See [docs/modules/occupancy-design.md](./modules/occupancy-design.md) for event types (TRIGGER, HOLD, RELEASE, VACATE, LOCK, UNLOCK).

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

### 6.2 Module Enable/Disable Granularity

**Design Decision**: Modules are enabled **globally**, not per-location.

When a module is enabled (e.g., Occupancy), it processes **all locations**. There is no per-location enable/disable toggle.

However, **per-location configuration** still exists:
- Different timeout values per room
- Different sensor rules per location
- Location-specific behavior settings

```python
# Module enabled globally
occupancy_module.enabled = True  # Applies to all locations

# Per-location configuration (only if module is enabled)
kitchen.modules["occupancy"] = {"timeout": 300, "devices": [...]}
bedroom.modules["occupancy"] = {"timeout": 900, "devices": [...]}
```

**Rationale**: Simpler mental model. "Occupancy is on" means it's on everywhere. Users configure behavior per-location, not whether the feature exists.

### 6.3 Module Lifecycle

1. **Instantiation**: `module = OccupancyModule()`
2. **Attachment**: `module.attach(bus, loc_manager)`
   - Module subscribes to events
   - Captures references to bus and location manager
3. **Configuration**: Per-location configs loaded from `location.modules["occupancy"]`
4. **Operation**: Module reacts to events, maintains state, emits semantic events
5. **Persistence**: Host platform calls `dump_state()` / `restore_state(state)`

### 6.4 Configuration Versioning

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

### 6.5 Configuration Schema

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

### 6.6 State Persistence

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

### 6.7 Built-In Modules

The `home-topology` kernel ships with these modules:

- **OccupancyModule** - Track occupancy state per location  
  See [docs/modules/occupancy-design.md](./modules/occupancy-design.md)

- **ActionsModule** - Execute automations based on semantic events  
  See [docs/modules/actions-design.md](./modules/actions-design.md)

Future modules:
- **ComfortModule** - Temperature, humidity, air quality per location
- **EnergyModule** - Power, energy consumption per location
- **SecurityModule** - Alarm state, lock state per location

---

## 7. Platform Integration (Separate Component)

> **Note**: While the core library is platform-agnostic, the primary integration target is Home Assistant. This section describes integration patterns that apply to any platform.

### 7.1 Adapter Layer

The integration is a **thin adapter** between platform and kernel:

**Platform → Kernel**:
- Translate platform state changes → normalized `Event` objects
- Feed into EventBus
- Sync topology (create/update/remove locations based on platform structure)

**Kernel → Platform**:
- Expose module state as platform entities (e.g., `binary_sensor.kitchen_occupied`)
- Execute actions via platform service calls
- Emit topology update events for platform to handle

### 7.2 Sync Model: Continuous via Integration

**Design Decision**: The integration maintains continuous synchronization.

**Inbound (Platform → Kernel)**:
- New areas/rooms created in platform → Integration calls `create_location()`
- New entities assigned in platform → Integration calls `add_entity_to_location()`
- Areas removed in platform → Integration updates or removes locations
- Entity state changes → Integration publishes normalized events

**Outbound (Kernel → Platform)**:
- User restructures hierarchy in our UI → Kernel emits topology update event
- Integration receives event → Decides whether/how to update platform

**First Run**:
1. Integration pulls platform's floor/area structure
2. Populates LocationManager with that hierarchy
3. User can add intermediate locations, restructure as desired

**Ongoing**:
1. Integration watches for platform changes (new areas, entities, etc.)
2. Updates our topology accordingly
3. Our changes can optionally propagate back to platform

**Key Principle**: The integration handles all platform-specific complexity. The kernel just provides its location tree and accepts updates via its API.

### 7.3 Event Normalization

**Design Decision**: Event normalization happens in the integration layer.

The core library expects **normalized events** with sensor types and event names:

| Sensor Type | Events | Platform Example |
|-------------|--------|------------------|
| `motion_sensor` | `motion`, `clear` | HA: `binary_sensor.*.motion` state changes |
| `contact_sensor` | `open`, `closed` | HA: `binary_sensor.*.door` state changes |
| `switch` | `on`, `off` | HA: `switch.*` state changes |
| `light` | `on`, `off`, `brightness_changed` | HA: `light.*` state/brightness changes |
| `media_player` | `playing`, `paused`, `idle`, `off`, `volume_changed` | HA: `media_player.*` state/volume changes |
| `person` | `home`, `away` | HA: `person.*` state changes |

The integration translates platform-specific events into this format before publishing to the EventBus.

### 7.4 Configuration UI

Provide a UI panel for:
- Location management (create, edit, delete, reorder hierarchy)
- Entity assignment (drag-and-drop from Unassigned inbox)
- Per-location module config (dynamic forms from schemas)
- Global module enable/disable

### 7.5 State Persistence

Integration stores:
- Locations → platform storage (e.g., `.storage/home_topology.locations.json`)
- Module state → platform storage (e.g., `.storage/home_topology.module_state.json`)

On startup:
1. Load locations into `LocationManager`
2. Sync with platform structure (reconcile differences)
3. Attach modules
4. Restore module state via `restore_state()`

### 7.6 Integration Layer Responsibilities

**Design Decision**: Clear division between kernel and integration.

The integration layer is responsible for:

| Responsibility | Description |
|----------------|-------------|
| **Sync** | Bidirectional sync between platform and kernel |
| **Discovery** | Import platform floors/areas as locations (`is_explicit_root=False`) |
| **Conflict Handling** | When platform and kernel disagree, integration decides resolution |
| **Entity Creation** | Create platform entities for kernel state (e.g., `binary_sensor.kitchen_occupied`) |
| **Event Classification** | Map platform events to normalized kernel events |
| **Timeout Scheduling** | Call `check_timeouts()` at appropriate times |

The kernel is responsible for:

| Responsibility | Description |
|----------------|-------------|
| **Tree Structure** | Store and query location hierarchy |
| **Module State** | Occupancy, actions, etc. |
| **Event Processing** | Handle normalized events |
| **State Export/Import** | `dump_state()` / `restore_state()` |

### 7.7 Sync Model

**Inbound (Platform → Kernel)**:
- Platform creates area → Integration creates Location (`is_explicit_root=False`, shows in Inbox)
- Platform assigns area to floor → Integration updates `parent_id`
- Platform entity state changes → Integration publishes normalized events

**Outbound (Kernel → Platform)**:
- User organizes hierarchy in our UI → Integration can sync back to platform (optional)
- Module state changes → Integration exposes as platform entities

**Conflict Handling**:
The integration decides how to handle conflicts when platform and kernel hierarchy differ:
- "We win": User's organization takes precedence, don't overwrite
- "Platform wins": Always sync from platform (not recommended)
- "User decides": Show conflict, let user choose

---

## 8. User Interface Strategy

> **Note**: UI implementation is platform-specific. This section documents the recommended patterns for integrations.

### 8.1 Tree View + Inspector Pattern

**Left Panel**: Tree visualization of location hierarchy
- Supports drag-and-drop for reorganization
- Shows nested structure (Floor → Wing → Room → Zone)
- "Unassigned" virtual group for parentless locations

**Right Panel**: Context-aware inspector
- Shows selected location's metadata
- Module configuration blocks
- Collapsible sections per module

### 8.2 Module Hub Pattern

The inspector uses a "Module Block" layout:

```
┌─────────────────────────────────┐
│ Location: Kitchen               │  ← Header (Kernel metadata)
├─────────────────────────────────┤
│ ▼ Occupancy                     │  ← Module Block
│   Default Timeout: 10 min       │
│   Wasp-in-a-Box: ☑              │
│   ▶ Kitchen Motion (1 rule)     │  ← Device cards (collapsible)
│   ▶ Main Lights (2 rules)       │
├─────────────────────────────────┤
│ ▼ Actions                       │  ← Module Block
│   When Occupied → Turn on lights│
│   When Clear → Turn off lights  │
└─────────────────────────────────┘
```

### 8.3 Config Schema → UI Mapping

Modules expose `location_config_schema()` returning JSON Schema. Integrations render dynamic forms from this schema without custom UI code per module.

---

## 9. Testing Strategy

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

## 10. Performance Considerations

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

## 11. Design Decisions Summary

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
- **Decision**: Integration-driven event classification + module dedupe + optional bus dedupe
- **Rationale**: Integration controls what sends occupancy events; core stays simple

### 10.9 Configurable Action State Checking
- **Decision**: Actions can trust or ignore device state
- **Rationale**: Supports flaky devices, user preference

### 10.10 Module Enable/Disable Granularity
- **Decision**: Modules enabled globally, not per-location
- **Rationale**: Simpler mental model; per-location config still exists for behavior tuning

### 10.11 Continuous Sync via Integration
- **Decision**: Integration maintains sync with platform, kernel doesn't know about platform
- **Rationale**: Platform-agnostic core, integration handles complexity

### 10.12 Event Normalization in Integration Layer
- **Decision**: Integration translates platform events to normalized format
- **Rationale**: Core library stays platform-agnostic, consistent event handling

### 10.13 "Unassigned" as UI Concept
- **Decision**: No special "unassigned" Location in kernel
- **Rationale**: Keeps kernel clean, presentation logic belongs in UI/integration

---

## 12. Non-Goals (Out of Scope)

- ❌ Multi-home support (one kernel per home)
- ❌ Cloud sync (host platform's responsibility)
- ❌ Machine learning models in core (modules can use external ML)
- ❌ Historical data storage (use platform's historian)
- ❌ Authentication/authorization (host platform's responsibility)
- ❌ WebSocket API (host platform exposes kernel state)

---

## 13. Future Considerations

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

## 14. Glossary

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
- **v1.4**: Added module granularity (global enable), sync model, event normalization, "Unassigned" clarification
- **v1.5**: Updated feedback loop prevention to reflect integration-driven classification (dropped primary/secondary signals)

---

**Document Status**: Active  
**Last Updated**: 2025-11-24

