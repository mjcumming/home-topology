# Home Topology Integration - Architecture Decisions

**Scope**: Decisions specific to the Home Assistant integration layer  
**Note**: These decisions will move to the `home-topology-ha` repository when the integration is separated.

---

## Overview

This document captures architecture decisions for the Home Assistant integration. These are distinct from core library decisions (see `docs/library/modules/*/design-decisions.md`).

The integration layer is responsible for:
- Translating HA entity states → occupancy events
- UI for location management
- Entity-to-location mapping
- HA services and entities

---

## ADR-INT-001: Entity Scope - Area Entities Only

**Date**: 2025-11-26  
**Status**: Accepted

### Context

When configuring "Occupancy Sources" (entities that generate occupancy events for a location), we need to decide which entities are available:

- **Option A**: Only entities assigned to this HA area
- **Option B**: Any entity from anywhere in HA
- **Option C**: Default to area entities, allow adding from elsewhere

### Decision

**Option A: Strict - Only entities assigned to this HA area.**

### Rationale

1. **Follows HA paradigm** - Home Assistant already has areas, and entities belong to areas. We leverage that existing model.

2. **Simpler mental model** - "Occupancy Sources are the entities in this location" is easy to explain.

3. **Separation of concerns** - If a sensor needs to affect multiple locations, that's an HA configuration decision (template sensors, groups), not a home-topology decision.

4. **Simpler UI** - No need for a complex entity picker showing all entities.

5. **Easier debugging** - "Why is my living room occupied?" → Check the entities in Living Room area.

6. **Can expand later** - If users demand flexibility, we can add "Add from other areas" in v2.

### Workaround for Edge Cases

If a user wants one sensor to affect multiple locations (e.g., hallway motion for both Hallway and Living Room):

```yaml
# In HA configuration.yaml
template:
  - binary_sensor:
      - name: "Living Room Motion (from Hallway)"
        state: "{{ states('binary_sensor.hallway_motion') }}"
```

Then assign the template sensor to the Living Room area. The complexity stays in HA where users already manage it.

### Consequences

- Users must have entities properly assigned to HA areas before configuring occupancy
- Edge cases require HA-native workarounds (template sensors)
- UI only needs to show entities from current area (simpler implementation)

---

## ADR-INT-002: UI Terminology

**Date**: 2025-11-26  
**Status**: Accepted

### Decision

| Term | Usage |
|------|-------|
| **Location** | A place in the topology (room, floor, zone) |
| **Entity** | A Home Assistant entity (not "device") |
| **Occupancy Sources** | Entities that generate occupancy events (not "Device Mappings") |
| **Occupancy Settings** | Location-level occupancy configuration |
| **Timeout** | Duration for TRIGGER events |
| **Trailing Timeout** | Duration after CLEAR before fully vacant |

### Rationale

- "Entity" follows HA terminology (sensors are entities, not devices)
- "Occupancy Sources" is descriptive of what the section does
- "Device Mappings" was confusing - we're not mapping devices

---

## ADR-INT-003: Entity Configuration Model - Two Trigger Modes

**Date**: 2025-11-26  
**Status**: Accepted

### Context

Not all entities have simple binary on/off states:
- Motion sensors: on/off (simple)
- Dimmers: 0-100% brightness
- Media players: playing/paused/idle + volume + source
- Thermostats: temperature, mode, setpoint

We need a model that handles both simple and complex entities.

### Decision

**Two trigger modes for entity configuration:**

#### Mode 1: "Any Change" (Activity Detection)
- Any state change → TRIGGER with timeout
- Simple, no need to understand entity semantics
- Best for: dimmers, volume controls, thermostats, unusual sensors

#### Mode 2: "Specific States" (Binary Mapping)  
- User configures what happens on ON vs OFF state
- ON state → TRIGGER (with timeout or indefinite)
- OFF state → Ignore or CLEAR (with trailing timeout)
- Best for: motion, presence, door, media player state

### Entity Configuration Dialog

```
TRIGGER MODE
─────────────────────────────────────────────────────────
● Any change (triggers on any state change)
○ Specific states (configure ON/OFF below)

[If "Any change":]
  Timeout: [5] min

[If "Specific states":]
  ON STATE (off → on)
    Event: ● TRIGGER  ○ None
    Timeout: [5] min

  OFF STATE (on → off)
    Event: ● None  ○ CLEAR
    Trailing: [2] min
```

### State Normalization for Dimmable Entities

For lights and dimmers, the integration normalizes states:

| Raw HA State | Normalized State |
|--------------|------------------|
| `state: on` (any brightness 1-100%) | **ON** |
| `state: on, brightness: 0` | **OFF** |
| `state: off` | **OFF** |

**Brightness changes while ON** (e.g., 50% → 75%) are treated as re-triggering the ON state, extending any active timeout.

### Default Mode by Entity Type

| Entity Type | Default Mode | Default Config |
|-------------|--------------|----------------|
| Motion sensor | Specific states | ON→TRIGGER(5m), OFF→ignore |
| Presence sensor | Specific states | ON→TRIGGER(∞), OFF→CLEAR(2m) |
| Door sensor | Specific states | ON→TRIGGER(2m), OFF→ignore | Entry door pattern (default) |
| Door sensor (state-based) | Specific states | ON→TRIGGER(∞), OFF→CLEAR(0) | State door pattern (garage, storage) |
| Light/Dimmer | Specific states | ON→TRIGGER(5m), OFF→ignore |
| Media player | Specific states | playing→TRIGGER(∞), idle→CLEAR(5m) |
| Thermostat | Any change | TRIGGER(10m) |
| Unknown | Any change | TRIGGER(5m) |

### Configuration Options for Each State

**Important**: The UI provides **full flexibility**. Any event (ON or OFF) can trigger any action. The defaults above are just common patterns.

**ON state options** (available for any sensor):
- TRIGGER with timeout (e.g., 5 min)
- TRIGGER indefinite (until OFF state triggers CLEAR)
- CLEAR with trailing timeout (unusual, but allowed)
- CLEAR immediate (unusual, but allowed)
- None (ignore)

**OFF state options** (available for any sensor):
- CLEAR with trailing timeout (e.g., 2 min)
- CLEAR immediate (trailing=0)
- TRIGGER with timeout (treat OFF as activity - unusual but allowed)
- TRIGGER indefinite (unusual, but allowed)
- None (ignore)

**Key principle**: Any event can do any option. The UI allows complete flexibility to match any use case.

### Edge Cases

For truly unusual scenarios, users can bypass the UI entirely:

```yaml
# User's own automation
- trigger:
    - platform: state
      entity_id: sensor.weird_thing
  action:
    - service: home_topology.trigger
      data:
        location_id: living_room
        source_id: sensor.weird_thing
        timeout: 300
```

We don't need to solve every edge case in the configuration UI.

### Rationale

1. **Two modes cover 99% of cases** - Simple binary or "any activity"
2. **Escape hatch exists** - Direct service calls for edge cases
3. **Progressive complexity** - "Any change" is simplest, "Specific states" for fine control
4. **Sensible defaults** - Auto-detect entity type where possible

---

## Future Decisions (Pending)

### Entity Auto-Detection
Should the integration auto-detect entity types based on device class?
- e.g., `binary_sensor` with `device_class: motion` → Motion preset

### Default Occupancy Sources
When a new location is created, should we auto-add entities from the HA area?
- Or require explicit "Add Entity" for each?

---

**Last Updated**: 2025-11-26

