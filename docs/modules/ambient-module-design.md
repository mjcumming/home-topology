# Ambient Light Module - Design Spec

**Status**: ✅ Implemented  
**Date**: 2025.12.09  
**Version**: 1.0

---

## Overview

The Ambient Light Module provides intelligent ambient light detection for locations, with automatic sensor inheritance through the location hierarchy. It answers the question: **"How bright is it in this location?"**

### Key Concepts

1. **Lux sensors provide ground truth** - Physical light level measurements are most accurate
2. **Automatic sensor inheritance** - Child locations inherit from parent when no local sensor
3. **Graceful fallback** - Falls back to sun position when no sensors available
4. **Location-aware** - Every location can query its effective ambient light level
5. **Provenance tracking** - Know exactly where a reading came from

### Mental Model

```
House
  ├─ sensor.outdoor_lux (1000 lux)
  │
  ├─ Main Floor (inherits 1000 lux from House)
  │   ├─ Kitchen
  │   │   └─ sensor.kitchen_lux (200 lux)  ← Local sensor wins
  │   │
  │   └─ Living Room (inherits 1000 lux from House)
  │
  └─ Upper Floor (inherits 1000 lux from House)
      └─ Bedroom
          └─ sensor.bedroom_lux (5 lux)  ← Local sensor wins

Query: "Is Kitchen dark?"
  → sensor.kitchen_lux = 200 lux → Not dark (threshold 50)

Query: "Is Living Room dark?"
  → No local sensor → Check parent (Main Floor) → No sensor
  → Check grandparent (House) → sensor.outdoor_lux = 1000 lux
  → Not dark (using inherited value)
```

This provides automatic, intelligent light level detection without manual configuration.

---

## Design Principles

### 1. Ambient Light Reading Data Model

```python
@dataclass
class AmbientLightReading:
    """Ambient light reading for a location."""
    
    lux: Optional[float]                   # Light level in lux (None if unavailable)
    source_sensor: Optional[str]           # Entity ID of sensor that provided value
    source_location: Optional[str]         # Location that owns the sensor
    is_inherited: bool                     # True if from parent/ancestor
    is_dark: bool                          # Convenience: lux < dark_threshold
    is_bright: bool                        # Convenience: lux > bright_threshold
    dark_threshold: float = 50.0           # Lux below which is "dark"
    bright_threshold: float = 500.0        # Lux above which is "bright"
    fallback_method: Optional[str] = None  # How value was determined if no sensor
    timestamp: datetime                    # When reading was taken
```

### 2. Module Responsibilities

1. **Sensor Discovery**: Auto-detect lux sensors in locations
2. **Hierarchical Lookup**: Walk up parent chain to find sensors
3. **Fallback Strategy**: Use sun.sun when no sensors available
4. **Threshold Management**: Per-location dark/bright thresholds
5. **Reading Provenance**: Track where readings came from

### 3. AmbientLightModule API

```python
class AmbientLightModule(LocationModule):
    @property
    def id(self) -> str:
        return "ambient"
    
    # Reading Queries
    
    def get_ambient_light(
        self,
        location_id: str,
        dark_threshold: Optional[float] = None,
        bright_threshold: Optional[float] = None,
        inherit: bool = True
    ) -> AmbientLightReading:
        """
        Get ambient light reading for a location.
        
        Args:
            location_id: Location to query
            dark_threshold: Override default dark threshold (lux)
            bright_threshold: Override default bright threshold (lux)
            inherit: If True, check parent locations for sensors
        
        Returns:
            AmbientLightReading with lux value and metadata
        """
        ...
    
    def is_dark(
        self,
        location_id: str,
        threshold: Optional[float] = None
    ) -> bool:
        """
        Check if location is dark (convenience wrapper).
        
        Args:
            location_id: Location to check
            threshold: Lux threshold (default from config)
        
        Returns:
            True if lux < threshold
        """
        reading = self.get_ambient_light(location_id, dark_threshold=threshold)
        return reading.is_dark
    
    def is_bright(
        self,
        location_id: str,
        threshold: Optional[float] = None
    ) -> bool:
        """Check if location is bright."""
        reading = self.get_ambient_light(location_id, bright_threshold=threshold)
        return reading.is_bright
    
    # Sensor Configuration
    
    def set_lux_sensor(
        self,
        location_id: str,
        entity_id: str
    ) -> None:
        """Set the lux sensor for a location."""
        ...
    
    def get_lux_sensor(
        self,
        location_id: str,
        inherit: bool = True
    ) -> Optional[str]:
        """
        Get the effective lux sensor for a location.
        
        Args:
            location_id: Location to query
            inherit: If True, check parent locations
        
        Returns:
            Entity ID of lux sensor, or None
        """
        ...
    
    def auto_discover_sensors(self) -> Dict[str, str]:
        """
        Auto-discover lux sensors in all locations.
        
        Returns:
            Dict mapping location_id → sensor entity_id
        """
        ...
```

---

## Sensor Discovery

### Automatic Detection

The module can auto-detect lux sensors based on:

1. **Entity ID patterns**: Contains "lux", "illuminance", "light_level"
2. **Device class**: `device_class: illuminance`
3. **Unit of measurement**: `lx`, `lux`
4. **Entity domain**: `sensor.*`

```python
def _is_lux_sensor(self, entity_id: str) -> bool:
    """Check if entity is a lux sensor."""
    
    # Check entity ID pattern
    if any(pattern in entity_id.lower() for pattern in ["lux", "illuminance", "light_level"]):
        return True
    
    # Check device class
    device_class = self._platform.get_device_class(entity_id)
    if device_class == "illuminance":
        return True
    
    # Check unit of measurement
    unit = self._platform.get_unit_of_measurement(entity_id)
    if unit and unit.lower() in ["lx", "lux"]:
        return True
    
    return False
```

### Manual Configuration

Users can explicitly configure sensors per location:

```python
# Set specific sensor for kitchen
ambient_module.set_lux_sensor(
    location_id="kitchen",
    entity_id="sensor.kitchen_illuminance"
)

# Or via location config
loc_mgr.set_module_config(
    location_id="kitchen",
    module_id="ambient",
    config={
        "lux_sensor": "sensor.kitchen_illuminance",
        "dark_threshold": 30.0,  # Kitchen needs to be darker for lights
        "bright_threshold": 800.0,
    }
)
```

---

## Hierarchical Sensor Lookup

### Lookup Algorithm

```python
def get_ambient_light(
    self,
    location_id: str,
    dark_threshold: Optional[float] = None,
    bright_threshold: Optional[float] = None,
    inherit: bool = True
) -> AmbientLightReading:
    """Get ambient light reading with hierarchical lookup."""
    
    # Get thresholds from config or use defaults
    config = self._get_location_config(location_id)
    dark_thresh = dark_threshold or config.get("dark_threshold", 50.0)
    bright_thresh = bright_threshold or config.get("bright_threshold", 500.0)
    
    # 1. Try local sensor first
    sensor = self._find_lux_sensor_for_location(location_id)
    if sensor:
        lux = self._platform.get_numeric_state(sensor)
        if lux is not None:
            return AmbientLightReading(
                lux=lux,
                source_sensor=sensor,
                source_location=location_id,
                is_inherited=False,
                is_dark=lux < dark_thresh,
                is_bright=lux > bright_thresh,
                dark_threshold=dark_thresh,
                bright_threshold=bright_thresh,
                timestamp=datetime.now(UTC)
            )
    
    # 2. Walk up parent hierarchy if inherit=True
    if inherit:
        ancestors = self._location_manager.ancestors_of(location_id)
        for ancestor in ancestors:
            sensor = self._find_lux_sensor_for_location(ancestor.id)
            if sensor:
                lux = self._platform.get_numeric_state(sensor)
                if lux is not None:
                    return AmbientLightReading(
                        lux=lux,
                        source_sensor=sensor,
                        source_location=ancestor.id,
                        is_inherited=True,
                        is_dark=lux < dark_thresh,
                        is_bright=lux > bright_thresh,
                        dark_threshold=dark_thresh,
                        bright_threshold=bright_thresh,
                        timestamp=datetime.now(UTC)
                    )
    
    # 3. Fall back to sun position
    return self._get_sun_fallback(dark_thresh, bright_thresh)
```

### Example Walkthrough

```
Location hierarchy:
  house
    └─ main_floor
        └─ kitchen

Scenario 1: Kitchen has sensor
  Query: get_ambient_light("kitchen")
  → Check kitchen → sensor.kitchen_lux found → Return 200 lux (local)

Scenario 2: Kitchen has no sensor, main_floor has sensor
  Query: get_ambient_light("kitchen")
  → Check kitchen → No sensor
  → Check main_floor → sensor.main_floor_lux found → Return 150 lux (inherited)

Scenario 3: No sensors anywhere
  Query: get_ambient_light("kitchen")
  → Check kitchen → No sensor
  → Check main_floor → No sensor
  → Check house → No sensor
  → Fall back to sun.sun → Return "dark" (sun below horizon)
```

---

## Integration with Automation

### Enhanced LuxLevelCondition

The existing `LuxLevelCondition` is enhanced to support location-based lookups:

```python
@dataclass(frozen=True)
class LuxLevelCondition:
    """Check light level condition.
    
    Two modes:
    1. Explicit sensor: entity_id specified
    2. Location-based: location_id specified (with automatic inheritance)
    """
    
    # Explicit sensor (Option A)
    entity_id: Optional[str] = None
    
    # Location-based (Option B)
    location_id: Optional[str] = None
    inherit_from_parent: bool = True
    
    # Thresholds
    below: Optional[float] = None  # Trigger if lux < this
    above: Optional[float] = None  # Trigger if lux > this
    
    def __post_init__(self):
        if not self.entity_id and not self.location_id:
            raise ValueError("Must specify either entity_id or location_id")
```

### Usage in Automation Rules

```python
# Option A: Explicit sensor (existing behavior)
rule = AutomationRule(
    id="kitchen_lights_explicit",
    trigger=EventTriggerConfig(
        event_type="occupancy.changed",
        payload_match={"occupied": True}
    ),
    conditions=[
        LuxLevelCondition(
            entity_id="sensor.kitchen_lux",
            below=50.0
        )
    ],
    actions=[
        ServiceCallAction(
            service="light.turn_on",
            entity_id="light.kitchen_ceiling"
        )
    ]
)

# Option B: Location-based with inheritance (NEW)
rule = AutomationRule(
    id="kitchen_lights_smart",
    trigger=EventTriggerConfig(
        event_type="occupancy.changed",
        payload_match={"occupied": True}
    ),
    conditions=[
        LuxLevelCondition(
            location_id="kitchen",  # Automatically finds sensor
            inherit_from_parent=True,  # Walks up hierarchy
            below=50.0
        )
    ],
    actions=[
        ServiceCallAction(
            service="light.turn_on",
            entity_id="light.kitchen_ceiling"
        )
    ]
)
```

### Lighting Preset Integration

The lighting presets can now use location-based lux:

```python
# Before: Must specify sensor explicitly
rule = lights_on_when_occupied(
    rule_id="kitchen_auto_lights",
    light_entity="light.kitchen_ceiling",
    lux_sensor="sensor.kitchen_lux",  # Manual specification
    lux_threshold=50.0
)

# After: Can use location (with auto-discovery)
rule = lights_on_when_occupied(
    rule_id="kitchen_auto_lights",
    light_entity="light.kitchen_ceiling",
    location_id="kitchen",  # Automatic sensor lookup
    lux_threshold=50.0
)
```

---

## Configuration Schema

### Per-Location Config

```python
{
    "ambient": {
        "version": 1,
        
        # Sensor configuration
        "lux_sensor": "sensor.kitchen_illuminance",  # Optional: explicit sensor
        "auto_discover": true,  # Auto-detect lux sensors in this location
        "inherit_from_parent": true,  # Use parent sensor if local not found
        
        # Thresholds
        "dark_threshold": 50.0,  # Lux below which is "dark"
        "bright_threshold": 500.0,  # Lux above which is "bright"
        
        # Fallback behavior
        "fallback_to_sun": true,  # Use sun.sun if no sensors found
        "assume_dark_on_error": true,  # If sensor unavailable, assume dark
        
        # Advanced
        "prefer_lux_over_sun": true,  # Always use lux sensor over sun position
        "sensor_timeout_seconds": 300,  # Consider sensor stale after 5 min
    }
}
```

### Module Config Schema

```python
def location_config_schema(self) -> Dict:
    return {
        "type": "object",
        "properties": {
            "lux_sensor": {
                "type": "string",
                "title": "Lux Sensor",
                "description": "Entity ID of illuminance sensor (leave empty for auto-detect)",
                "entity_filter": {"domain": "sensor", "device_class": "illuminance"},
            },
            "auto_discover": {
                "type": "boolean",
                "title": "Auto-discover sensor",
                "description": "Automatically detect lux sensors in this location",
                "default": True,
            },
            "inherit_from_parent": {
                "type": "boolean",
                "title": "Inherit from parent",
                "description": "Use parent location's sensor if no local sensor",
                "default": True,
            },
            "dark_threshold": {
                "type": "number",
                "title": "Dark Threshold (lux)",
                "description": "Light level below which is considered 'dark'",
                "minimum": 0,
                "maximum": 1000,
                "default": 50.0,
            },
            "bright_threshold": {
                "type": "number",
                "title": "Bright Threshold (lux)",
                "description": "Light level above which is considered 'bright'",
                "minimum": 0,
                "maximum": 10000,
                "default": 500.0,
            },
            "fallback_to_sun": {
                "type": "boolean",
                "title": "Fallback to sun position",
                "description": "Use sun.sun when no sensors available",
                "default": True,
            },
            "assume_dark_on_error": {
                "type": "boolean",
                "title": "Assume dark on error",
                "description": "If sensor is unavailable, assume it's dark (safer for lighting)",
                "default": True,
            },
        },
    }
```

---

## Fallback Strategies

### Sun Position Fallback

When no lux sensors are available, fall back to sun position:

```python
def _get_sun_fallback(
    self,
    dark_threshold: float,
    bright_threshold: float
) -> AmbientLightReading:
    """Get ambient light reading from sun position."""
    
    sun_state = self._platform.get_state("sun.sun")
    
    # Map sun position to lux estimate
    # below_horizon = dark (0 lux), above_horizon = bright (1000 lux)
    is_dark = sun_state == "below_horizon" if sun_state else True
    estimated_lux = 0.0 if is_dark else 1000.0
    
    return AmbientLightReading(
        lux=estimated_lux,
        source_sensor=None,
        source_location=None,
        is_inherited=False,
        is_dark=is_dark,
        is_bright=not is_dark,
        dark_threshold=dark_threshold,
        bright_threshold=bright_threshold,
        fallback_method="sun_position",
        timestamp=datetime.now(UTC)
    )
```

### Sunrise/Sunset Offset

Support for offset calculations:

```python
# Check if it's dark, considering civil twilight
reading = ambient_module.get_ambient_light(
    "kitchen",
    dark_threshold=100.0  # Higher threshold during twilight
)

# Or use time-based adjustments in conditions
TimeOfDayCondition(
    after="sunset-00:30",  # 30 min before sunset
    before="sunrise+00:30"  # 30 min after sunrise
)
```

---

## Use Cases

### 1. Smart Lighting with Auto-Discovery

```python
# Kitchen has sensor.kitchen_lux
# Living room has no sensor, but main_floor has sensor.main_floor_lux

# Both locations automatically use the right sensor:
kitchen_reading = ambient_module.get_ambient_light("kitchen")
# → Uses sensor.kitchen_lux (local)

living_reading = ambient_module.get_ambient_light("living_room")
# → Uses sensor.main_floor_lux (inherited from parent)
```

### 2. Adaptive Brightness Based on Ambient Light

```python
def get_target_brightness(location_id: str) -> int:
    """Calculate light brightness based on ambient light."""
    
    reading = ambient_module.get_ambient_light(location_id)
    
    if reading.lux is None:
        return 80  # Default
    
    # Brighter ambient → dimmer lights
    if reading.lux < 10:
        return 100  # Very dark, full brightness
    elif reading.lux < 50:
        return 80   # Dark, high brightness
    elif reading.lux < 200:
        return 50   # Dim, medium brightness
    else:
        return 20   # Bright, low brightness
```

### 3. Different Thresholds per Location

```python
# Bedroom: darker threshold (lights on earlier)
loc_mgr.set_module_config("bedroom", "ambient", {
    "dark_threshold": 20.0,  # Very dark needed
})

# Office: brighter threshold (lights on later)
loc_mgr.set_module_config("office", "ambient", {
    "dark_threshold": 100.0,  # Need significant darkness
})
```

### 4. Debugging Sensor Coverage

```python
# Check what sensor each location uses
for location in loc_mgr.all_locations():
    reading = ambient_module.get_ambient_light(location.id)
    
    if reading.source_sensor:
        status = "inherited" if reading.is_inherited else "local"
        print(f"{location.name}: {reading.lux} lux "
              f"({status} from {reading.source_location})")
    else:
        print(f"{location.name}: No sensor (using {reading.fallback_method})")

# Output:
# Kitchen: 200 lux (local from kitchen)
# Living Room: 150 lux (inherited from main_floor)
# Bedroom: 5 lux (local from bedroom)
# Bathroom: No sensor (using sun_position)
```

---

## Events

### ambient.reading_changed

Emitted when ambient light level crosses thresholds:

```python
{
    "type": "ambient.reading_changed",
    "source": "ambient",
    "location_id": "kitchen",
    "payload": {
        "lux": 45.0,
        "previous_lux": 60.0,
        "crossed_dark_threshold": True,  # Just became dark
        "is_dark": True,
        "is_bright": False,
        "source_sensor": "sensor.kitchen_lux",
        "source_location": "kitchen",
        "is_inherited": False,
        "timestamp": "2025-12-09T14:30:00Z"
    }
}
```

### Automation with Ambient Events

```python
# Turn on lights when location becomes dark (not just occupied)
rule = AutomationRule(
    id="lights_on_when_dark",
    trigger=EventTriggerConfig(
        event_type="ambient.reading_changed",
        payload_match={"crossed_dark_threshold": True}
    ),
    conditions=[
        LocationOccupiedCondition(
            location_id="kitchen",
            occupied=True
        )
    ],
    actions=[
        ServiceCallAction(
            service="light.turn_on",
            entity_id="light.kitchen_ceiling"
        )
    ]
)
```

---

## State Schema

### Ambient State per Location

```python
{
    "location_id": "kitchen",
    "lux": 200.0,
    "source_sensor": "sensor.kitchen_illuminance",
    "source_location": "kitchen",
    "is_inherited": False,
    "is_dark": False,
    "is_bright": False,
    "dark_threshold": 50.0,
    "bright_threshold": 500.0,
    "last_updated": "2025-12-09T14:30:00Z",
    "sensor_available": True,
    "fallback_method": None
}
```

### Module State Dump

```python
{
    "version": 1,
    "location_sensors": {
        "kitchen": "sensor.kitchen_illuminance",
        "bedroom": "sensor.bedroom_lux",
        "main_floor": "sensor.main_floor_lux"
    },
    "last_readings": {
        "kitchen": {
            "lux": 200.0,
            "timestamp": "2025-12-09T14:30:00Z"
        },
        # ... other locations
    }
}
```

---

## HA Integration Patterns

### Sensor Entities

Integration creates sensor entities for each location:

```yaml
# sensor.kitchen_ambient_light
sensor:
  - platform: home_topology
    location_id: kitchen
    sensor_type: ambient_light
    
    # Attributes:
    state: 200.0  # Current lux
    unit_of_measurement: lx
    device_class: illuminance
    attributes:
      is_dark: false
      is_bright: false
      source_sensor: sensor.kitchen_illuminance
      source_location: kitchen
      is_inherited: false
      dark_threshold: 50.0
      bright_threshold: 500.0
```

### Binary Sensors

```yaml
# binary_sensor.kitchen_is_dark
binary_sensor:
  - platform: home_topology
    location_id: kitchen
    binary_sensor_type: is_dark
    
    # State:
    state: "off"  # Not dark
    device_class: light

# binary_sensor.kitchen_is_bright  
binary_sensor:
  - platform: home_topology
    location_id: kitchen
    binary_sensor_type: is_bright
    
    # State:
    state: "off"  # Not bright
    device_class: light
```

### UI Panel

```
┌─────────────────────────────────┐
│ Location: Kitchen               │
├─────────────────────────────────┤
│ ▼ Ambient Light                 │
│                                 │
│   Current: 200 lx               │
│   Status: ● Normal              │
│                                 │
│   Sensor: sensor.kitchen_lux    │
│   Source: Local ✓               │
│                                 │
│   Thresholds:                   │
│   Dark:   [50] lx               │
│   Bright: [500] lx              │
│                                 │
│   ☑ Auto-discover sensor        │
│   ☑ Inherit from parent         │
│   ☑ Fallback to sun position    │
└─────────────────────────────────┘
```

---

## Implementation Status

### ✅ Phase 1: Core Implementation (v0.2.0 - 2025.12.09)

**Implemented**:
- ✅ AmbientLightReading data model
- ✅ AmbientLightModule with hierarchical lookup
- ✅ Automatic sensor discovery
- ✅ Sun position fallback
- ✅ Location-based LuxLevelCondition
- ✅ Integration with automation engine
- ✅ Threshold configuration
- ✅ State persistence
- ✅ Comprehensive tests

**Files**:
- `src/home_topology/modules/ambient/models.py` - Data models
- `src/home_topology/modules/ambient/module.py` - Module implementation
- `tests/modules/test_ambient_module.py` - Tests

### 📅 Phase 2: HA Integration (v0.3.0 - Planned)

**To Implement**:
- [ ] Auto-discover sensors from HA
- [ ] Sensor entity creation (`sensor.{location}_ambient_light`)
- [ ] Binary sensor entities (`binary_sensor.{location}_is_dark`)
- [ ] UI panel for ambient configuration
- [ ] Device class detection
- [ ] Unit of measurement validation

### 🔮 Phase 3: Advanced Features (v1.x - Future)

**To Design**:
- [ ] Ambient light change events with hysteresis
- [ ] Historical ambient light tracking
- [ ] Circadian rhythm integration
- [ ] Weather-based adjustments
- [ ] Multi-sensor averaging

---

## Design Decisions

### Why Hierarchical Sensor Lookup?

**Decision**: Automatically inherit lux sensors from parent locations.

**Rationale**:
- ✅ **Reduces configuration**: Don't need sensor in every room
- ✅ **Intelligent defaults**: Whole floor can share one sensor
- ✅ **Graceful degradation**: Always has a reading (sun fallback)
- ✅ **Realistic sensor placement**: One sensor per floor is common
- ✅ **User override**: Can still specify per-location sensors

**Example**:
```
Most homes have:
- 1-2 outdoor sensors (house level)
- 1 sensor per floor (floor level)
- Individual sensors in key rooms (room level)

Hierarchical lookup handles all these naturally.
```

### Why Both Lux Value and Boolean Flags?

**Decision**: AmbientLightReading includes both numeric lux and is_dark/is_bright booleans.

**Rationale**:
- ✅ **Convenience**: Most automations just need "is it dark?"
- ✅ **Flexibility**: Advanced rules can use exact lux values
- ✅ **Consistency**: Matches existing HA patterns (numeric sensor + binary sensor)
- ✅ **Debuggability**: Can see exact value that determined boolean

### Why Fall Back to Sun Position?

**Decision**: Use sun.sun state when no lux sensors available.

**Rationale**:
- ✅ **Universal availability**: Every HA install has sun.sun
- ✅ **Better than nothing**: Rough guidance is better than failing
- ✅ **User expectations**: "Turn lights on at sunset" is intuitive
- ✅ **Gradual migration**: Users can start without sensors, add later

**Trade-offs**:
- ⚠️ Less accurate than lux sensor (cloudy days, indoor spaces)
- ✅ Can be disabled per-location if desired

### Why Support Both entity_id and location_id in Conditions?

**Decision**: LuxLevelCondition accepts either explicit sensor or location ID.

**Rationale**:
- ✅ **Backward compatibility**: Existing rules with entity_id still work
- ✅ **Power users**: Can override auto-detection when needed
- ✅ **Migration path**: Users can move to location_id gradually
- ✅ **Flexibility**: Different use cases need different approaches

---

## Summary

The Ambient Light Module provides intelligent ambient light detection for all locations with minimal configuration.

**Key Features**:
- Automatic sensor discovery
- Hierarchical sensor inheritance
- Sun position fallback
- Location-based automation conditions
- Per-location thresholds
- Full provenance tracking

**Benefits**:
- Less configuration needed
- Works with any sensor topology
- Intelligent defaults
- Powerful debugging
- Seamless integration with automation

---

**Document Status**: Implementation Complete  
**Last Updated**: 2025.12.09  
**Implementation**: v0.2.0

