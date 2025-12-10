# Ambient Light Module - API Reference

**Status**: v1.0  
**Date**: 2025.01.27  
**Module ID**: `ambient`

---

## Overview

The AmbientLightModule provides intelligent ambient light detection with hierarchical sensor lookup and automatic fallback strategies.

**Key Features**:
- Automatic sensor discovery
- Hierarchical sensor inheritance (child → parent)
- Sun position fallback
- Per-location thresholds
- Reading provenance tracking

---

## Architecture

```
Location Query
    │
    ▼
AmbientLightModule
    │
    │  Strategy:
    │  1. Check local sensor
    │  2. Walk up parent hierarchy
    │  3. Fall back to sun position
    │  4. Fall back to error state
    │
    ▼
PlatformAdapter (You implement this)
    │
    │  Responsibilities:
    │  - Query sensor state
    │  - Get sun position
    │
    ▼
Platform (Home Assistant, etc.)
```

---

## Initialization

```python
from home_topology.modules.ambient import AmbientLightModule

# Create platform adapter (you implement this)
class MyPlatformAdapter:
    def get_state(self, entity_id: str):
        # Get entity state
        pass
    
    def get_sun_position(self):
        # Get sun position (elevation, azimuth)
        # Returns: {"elevation": float, "azimuth": float}
        pass

# Initialize module
platform_adapter = MyPlatformAdapter()
ambient = AmbientLightModule(platform_adapter=platform_adapter)

# Attach to kernel
ambient.attach(bus, loc_mgr)
```

---

## Reading Queries

### Get Ambient Light Reading

```python
reading = ambient.get_ambient_light(
    location_id="kitchen",
    dark_threshold=50.0,  # Optional override
    bright_threshold=500.0,  # Optional override
    inherit=True,  # Check parent locations
)

# Reading object:
# AmbientLightReading {
#     lux: float,  # Light level in lux
#     is_dark: bool,  # True if lux < dark_threshold
#     is_bright: bool,  # True if lux > bright_threshold
#     source_sensor: Optional[str],  # Entity ID of sensor used
#     source_location: str,  # Location ID where sensor was found
#     is_inherited: bool,  # True if sensor from parent
#     dark_threshold: float,
#     bright_threshold: float,
#     timestamp: datetime,
# }
```

### Convenience Methods

```python
# Check if location is dark
is_dark = ambient.is_dark("kitchen", threshold=50.0)

# Check if location is bright
is_bright = ambient.is_bright("kitchen", threshold=500.0)
```

---

## Sensor Configuration

### Set Lux Sensor

```python
# Explicitly set sensor for a location
ambient.set_lux_sensor("kitchen", "sensor.kitchen_lux")
```

### Get Lux Sensor

```python
# Get effective sensor (checks hierarchy)
sensor = ambient.get_lux_sensor("kitchen", inherit=True)
# Returns: "sensor.kitchen_lux" or None
```

### Refresh Sensor Cache

```python
# Force re-discovery of sensors
ambient.refresh_sensor_cache("kitchen")
```

---

## Sensor Discovery

The module automatically discovers illuminance sensors:

1. **Explicit config** - `lux_sensor` in location config
2. **Auto-discovery** - Scans entities in location for illuminance sensors
3. **Parent inheritance** - Uses parent location's sensor if `inherit_from_parent=True`
4. **Sun fallback** - Uses sun position if `fallback_to_sun=True`
5. **Error fallback** - Returns error state if all else fails

### Auto-Discovery Rules

- Entity device class is `illuminance`
- Entity unit is `lx` or `lux`
- Entity is mapped to the location

---

## Configuration

```python
config = {
    "version": 1,
    "enabled": True,
    "lux_sensor": "sensor.kitchen_lux",  # Optional: explicit sensor
    "auto_discover": True,  # Auto-detect sensors in location
    "inherit_from_parent": True,  # Use parent sensor if no local sensor
    "dark_threshold": 50.0,  # Lux below which is "dark"
    "bright_threshold": 500.0,  # Lux above which is "bright"
    "fallback_to_sun": True,  # Use sun position as fallback
    "assume_dark_on_error": True,  # Assume dark if sensor unavailable
}

loc_mgr.set_module_config("kitchen", "ambient", config)
```

### Configuration Schema

```python
{
    "type": "object",
    "properties": {
        "lux_sensor": {
            "type": "string",
            "title": "Lux Sensor",
            "description": "Entity ID of illuminance sensor (leave empty for auto-detect)",
        },
        "auto_discover": {
            "type": "boolean",
            "title": "Auto-discover sensor",
            "default": True,
        },
        "inherit_from_parent": {
            "type": "boolean",
            "title": "Inherit from parent",
            "default": True,
        },
        "dark_threshold": {
            "type": "number",
            "title": "Dark Threshold (lux)",
            "minimum": 0,
            "maximum": 1000,
            "default": 50.0,
        },
        "bright_threshold": {
            "type": "number",
            "title": "Bright Threshold (lux)",
            "minimum": 0,
            "maximum": 10000,
            "default": 500.0,
        },
        "fallback_to_sun": {
            "type": "boolean",
            "title": "Fallback to sun position",
            "default": True,
        },
        "assume_dark_on_error": {
            "type": "boolean",
            "title": "Assume dark on error",
            "default": True,
        },
    },
}
```

---

## Events Emitted

### ambient.light_changed

Emitted when light level changes significantly (threshold-based):

```python
Event(
    type="ambient.light_changed",
    source="ambient",
    location_id="kitchen",
    payload={
        "lux": 45.0,
        "is_dark": True,
        "is_bright": False,
        "source_sensor": "sensor.kitchen_lux",
        "source_location": "kitchen",
        "is_inherited": False,
    },
)
```

**Note**: Change detection is based on threshold crossings, not continuous monitoring.

---

## Events Consumed

- `sensor.state_changed` - Illuminance sensor updates (processed internally)

---

## PlatformAdapter Interface

You must implement sensor access:

```python
class MyPlatformAdapter:
    def get_state(self, entity_id: str) -> Optional[Dict]:
        """
        Get entity state.
        
        Args:
            entity_id: Entity ID
        
        Returns:
            State dict with "state" (float lux value) and "attributes", or None
        """
        # Your implementation
        pass
    
    def get_sun_position(self) -> Optional[Dict]:
        """
        Get sun position for fallback.
        
        Returns:
            {"elevation": float, "azimuth": float} or None
        """
        # Your implementation
        pass
```

---

## State Persistence

```python
# Dump state (sensor cache)
state = ambient.dump_state()
# {
#     "version": 1,
#     "sensor_cache": {"kitchen": "sensor.kitchen_lux"},
#     "last_readings": {...},  # Optional, may be stale
# }

# Restore state
ambient.restore_state(state)
```

**Note**: `last_readings` are not restored as they may be stale. The module will re-read sensors on next query.

---

## Usage Examples

### Basic Query

```python
# Get light reading
reading = ambient.get_ambient_light("kitchen")

if reading.is_dark:
    print(f"Kitchen is dark ({reading.lux} lux)")
elif reading.is_bright:
    print(f"Kitchen is bright ({reading.lux} lux)")
else:
    print(f"Kitchen is normal ({reading.lux} lux)")
```

### In Automation Rules

```python
from home_topology.modules.automation.models import LuxLevelCondition

# Use in automation condition
condition = LuxLevelCondition(
    location_id="kitchen",
    below=50.0,  # Only if dark
)
```

### Hierarchical Lookup

```python
# Kitchen has no sensor, but parent "main_floor" does
reading = ambient.get_ambient_light("kitchen", inherit=True)
# reading.source_location = "main_floor"
# reading.is_inherited = True
```

### Sun Fallback

```python
# No sensors available, use sun position
reading = ambient.get_ambient_light("outdoor_patio")
# reading.source_sensor = None
# reading.source_location = "outdoor_patio"
# reading.lux = estimated from sun elevation
```

---

## Best Practices

1. **Set explicit sensors** - If you know the sensor, set it explicitly
2. **Use inheritance** - Enable `inherit_from_parent` for hierarchical setups
3. **Configure thresholds** - Adjust `dark_threshold` and `bright_threshold` per location
4. **Handle errors** - Set `assume_dark_on_error=True` for safer lighting automation
5. **Cache sensors** - The module caches sensor lookups for performance

---

## Troubleshooting

### No Sensor Found

- Check `auto_discover=True` in config
- Verify entity has `device_class: illuminance`
- Check entity is mapped to location
- Enable `inherit_from_parent` to use parent sensor

### Stale Readings

- Module doesn't cache readings by default
- Each `get_ambient_light()` call queries current state
- `last_readings` in state dump is for debugging only

### Sun Fallback Not Working

- Verify `fallback_to_sun=True` in config
- Check platform adapter implements `get_sun_position()`
- Sun fallback only used if no sensors available

---

**Document Version**: 1.0  
**Last Updated**: 2025.01.27  
**Status**: Living Document

