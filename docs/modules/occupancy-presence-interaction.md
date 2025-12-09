# OccupancyModule and PresenceModule Interaction

**Version**: 1.0  
**Date**: 2025.12.09  
**Status**: Design Reference

---

## Overview

This document explains how OccupancyModule and PresenceModule work together to provide both generic and personalized automation capabilities.

**Key Principle**: Modules emit events independently. No coordination. User composes them via rules.

---

## Module Responsibilities

### OccupancyModule: "Is someone there?"

**Purpose**: Detect when a location is occupied or vacant

**Sources**: 
- Motion sensors (immediate)
- Door sensors (entry detection)
- Presence sensors (mmWave, radar)
- Media players (playing = occupied)

**State**: Binary (True/False)
- No confidence scoring
- Simple: occupied or not

**Events**:
```python
{
    "type": "occupancy.changed",
    "location_id": "kitchen",
    "payload": {
        "occupied": True  # or False
    }
}
```

**Use Cases**:
- Turn lights on when occupied
- Turn off when vacant
- Energy management
- Security monitoring

---

### PresenceModule: "WHO is there?"

**Purpose**: Track identified entities (people) and their current locations

**Sources**:
- Device trackers (phones, watches)
- BLE tags
- Camera person detection
- Zone tracking

**State**: Person registry with current locations

**Events**:
```python
{
    "type": "presence.changed",
    "location_id": "kitchen",
    "payload": {
        "person_id": "mike",
        "person_name": "Mike",
        "from_location": "bedroom",
        "to_location": "kitchen",
        "person_entered": "mike",
        "people_in_location": ["mike", "sarah"]
    }
}
```

**Use Cases**:
- Person-specific scenes
- Multi-person scenarios
- Voice queries ("Where is Mike?")
- Notifications ("Sarah arrived home")

---

## Event Timeline (Real-World)

```
T+0.0s: Door opens
  → Motion sensor detects movement
  → OccupancyModule emits: occupancy.changed (occupied=True)

T+0.0s: ActionsModule receives occupancy.changed
  → Rule "turn on generic lights" executes
  → ✅ Lights turn ON immediately

T+2.5s: BLE tracker detects phone
  → Camera identifies person as Mike
  → PresenceModule emits: presence.changed (person=mike)

T+2.5s: ActionsModule receives presence.changed
  → Rule "if mike in office, apply warm scene" executes
  → ✅ Mike's scene applies (overrides generic lights)

Result: 
- Instant response (lights on)
- Personalized 2.5s later (Mike's scene)
- No artificial delays
```

---

## Automation Patterns

### Pattern 1: Occupancy Only (90% of cases)

Most automations don't care WHO is there:

```yaml
# Simple: Just turn lights on/off
automation:
  - alias: "Bathroom Lights"
    trigger:
      - platform: event
        event_type: home_topology.occupancy_changed
        event_data:
          location_id: bathroom
    action:
      - if: "{{ trigger.event.data.occupied }}"
        then:
          - service: light.turn_on
            target:
              entity_id: light.bathroom
        else:
          - service: light.turn_off
            target:
              entity_id: light.bathroom
```

**When to use**: Generic automations, energy management, basic lighting

---

### Pattern 2: Sequential Override

Let generic action fire, then personalize:

```yaml
# Rule 1: Generic response (immediate)
automation:
  - alias: "Office Lights - Generic"
    trigger:
      - platform: event
        event_type: home_topology.occupancy_changed
        event_data:
          location_id: office
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.occupied }}"
    action:
      - service: light.turn_on
        target:
          entity_id: light.office
        data:
          brightness: 128  # Generic 50% brightness

# Rule 2: Personalization (2-5 seconds later)
automation:
  - alias: "Office Lights - Mike's Preference"
    trigger:
      - platform: event
        event_type: home_topology.presence_changed
        event_data:
          location_id: office
          person_entered: mike
    action:
      - service: scene.turn_on
        target:
          entity_id: scene.office_mike_warm
```

**Timeline**:
- T+0s: Lights turn on at 50% brightness
- T+3s: Mike's warm scene applies (adjusts to his preference)

**When to use**: Want instant response + personalization

---

### Pattern 3: Optional Wait (User's Choice)

Explicitly wait for person detection before acting:

```yaml
automation:
  - alias: "Office Lights - Wait for Person"
    trigger:
      - platform: event
        event_type: home_topology.occupancy_changed
        event_data:
          location_id: office
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.occupied }}"
    action:
      # Wait 5 seconds to see if we identify the person
      - delay: 5
      
      # Query presence module
      - variables:
          mike_present: >
            {{ 'mike' in state_attr('sensor.office_presence', 'people') }}
      
      # Conditional action
      - if: "{{ mike_present }}"
        then:
          - service: scene.turn_on
            target:
              entity_id: scene.office_mike
        else:
          - service: light.turn_on
            target:
              entity_id: light.office
            data:
              brightness: 128
```

**Timeline**:
- T+0s: Occupancy detected, wait begins
- T+5s: Check who's there, apply appropriate scene

**When to use**: Specific scenarios where you want complete state before acting

**Trade-off**: 5 second delay before any action

---

### Pattern 4: Presence-Only Triggers

Some automations only care about specific people:

```yaml
automation:
  - alias: "Mike Arrives Home - Welcome"
    trigger:
      - platform: event
        event_type: home_topology.presence_changed
        event_data:
          person_entered: mike
          to_location: house  # Or any child location
    action:
      - service: notify.mobile_app
        data:
          message: "Welcome home, Mike!"
      - service: climate.set_temperature
        data:
          temperature: 72  # Mike's preferred temp
```

**When to use**: Person-specific notifications, settings, preferences

---

### Pattern 5: Combined State Checking

Use occupancy + presence in conditions:

```yaml
automation:
  - alias: "Security Alert - Unknown Occupancy"
    trigger:
      - platform: event
        event_type: home_topology.occupancy_changed
        event_data:
          occupied: true
    condition:
      # Room is occupied BUT no known person
      - condition: template
        value_template: >
          {{ state_attr('sensor.' + trigger.event.data.location_id + '_presence', 'people') | length == 0 }}
      # And it's nighttime
      - condition: state
        entity_id: sun.sun
        state: below_horizon
    action:
      - service: notify.security
        data:
          message: "Unknown person detected in {{ trigger.event.data.location_id }}"
```

**When to use**: Security, anomaly detection, guest management

---

## HA Integration Patterns

### Exposing State as Entities

**Occupancy Sensor** (per location):
```yaml
binary_sensor.kitchen_occupied:
  state: on/off
  attributes:
    source: motion_sensor
    locked: false
```

**Presence Sensor** (per location):
```yaml
sensor.kitchen_presence:
  state: 2  # Number of people
  attributes:
    people: ["mike", "sarah"]
    people_names: ["Mike", "Sarah"]
```

**Person Location** (per person):
```yaml
sensor.person_mike_location:
  state: kitchen
  attributes:
    location_name: Kitchen
    entered_at: "2025-12-09T10:30:00Z"
    trackers: ["device_tracker.phone", "device_tracker.watch"]
```

---

## Real-World Examples

### Example 1: Kitchen (Generic)

```yaml
# Just turn lights on/off based on occupancy
automation:
  - alias: "Kitchen Lights"
    trigger:
      - platform: event
        event_type: home_topology.occupancy_changed
        event_data:
          location_id: kitchen
    action:
      - service: light.turn_{{ 'on' if trigger.event.data.occupied else 'off' }}
        target:
          entity_id: light.kitchen
```

**No presence needed** - simplest case.

---

### Example 2: Office (Personalized)

```yaml
# Generic lights immediately, personalize when known
automation:
  - alias: "Office Lights - Generic"
    trigger:
      - platform: event
        event_type: home_topology.occupancy_changed
        event_data:
          location_id: office
          occupied: true
    action:
      - service: light.turn_on
        target:
          entity_id: light.office

  - alias: "Office Lights - Mike"
    trigger:
      - platform: event
        event_type: home_topology.presence_changed
        event_data:
          location_id: office
          person_entered: mike
    action:
      - service: scene.turn_on
        target:
          entity_id: scene.office_mike_warm
  
  - alias: "Office Lights - Sarah"
    trigger:
      - platform: event
        event_type: home_topology.presence_changed
        event_data:
          location_id: office
          person_entered: sarah
    action:
      - service: scene.turn_on
        target:
          entity_id: scene.office_sarah_bright
```

**Result**: 
- Lights on immediately
- Personalized scene 2-5 seconds later

---

### Example 3: Living Room (Multi-Person)

```yaml
automation:
  - alias: "Movie Mode - Both Present"
    trigger:
      - platform: event
        event_type: home_topology.presence_changed
        event_data:
          location_id: living_room
    condition:
      # Both Mike and Sarah in living room
      - condition: template
        value_template: >
          {% set people = state_attr('sensor.living_room_presence', 'people') %}
          {{ 'mike' in people and 'sarah' in people }}
      # After 8pm
      - condition: time
        after: "20:00:00"
    action:
      - service: scene.turn_on
        target:
          entity_id: scene.movie_mode
```

**When to use**: Couple activities, family scenarios

---

## Design Philosophy

### Independent Modules

Each module has a single responsibility:
- **OccupancyModule**: Detect activity
- **PresenceModule**: Identify entities
- **ActionsModule**: Execute logic

### No Coordination

Modules don't wait for each other:
- Fast response (occupancy fires immediately)
- Optional enhancement (presence fires when ready)
- User chooses pattern (immediate, wait, ignore)

### Composable Events

ActionsModule can use:
- Occupancy events only (90% of cases)
- Presence events only (specific notifications)
- Both events (smart combinations)

---

## When to Use What

| Use Case | Occupancy | Presence | Both |
|----------|-----------|----------|------|
| Generic lighting | ✅ | ❌ | ❌ |
| Energy management | ✅ | ❌ | ❌ |
| Person-specific scene | ❌ | ✅ | ❌ |
| "Where is X?" queries | ❌ | ✅ | ❌ |
| Multi-person scenarios | ❌ | ✅ | ❌ |
| Security (unknown person) | ❌ | ❌ | ✅ |
| Personalized + instant | ✅ | ✅ | ✅ |

---

## Summary

**OccupancyModule + PresenceModule = Complete Picture**

- OccupancyModule: Fast, generic, binary occupancy detection
- PresenceModule: Slower, specific, person identification
- ActionsModule: Composes both event streams flexibly

**No coordination needed** - modules are independent, user chooses patterns.

**90% of automations** only need occupancy.  
**10% of automations** use presence for personalization.  
**5% of automations** use both for advanced logic.

---

**Document Version**: 1.0  
**Last Updated**: 2025.12.09  
**Status**: Active

