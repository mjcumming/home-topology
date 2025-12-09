"""
Ambient Light Module implementation.

Provides intelligent ambient light detection with hierarchical sensor lookup
and automatic fallback strategies.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List, TYPE_CHECKING

from home_topology.modules.base import LocationModule
from .models import AmbientLightReading, AmbientLightConfig

if TYPE_CHECKING:
    from home_topology.core import EventBus, LocationManager

logger = logging.getLogger(__name__)


class AmbientLightModule(LocationModule):
    """
    Ambient Light Module - Track ambient light levels per location.

    Features:
    - Automatic sensor discovery
    - Hierarchical sensor inheritance (child → parent)
    - Sun position fallback
    - Per-location thresholds
    - Reading provenance tracking
    """

    CURRENT_CONFIG_VERSION = 1

    def __init__(self, platform_adapter=None):
        """
        Initialize ambient light module.

        Args:
            platform_adapter: Platform adapter for sensor access
        """
        self._platform = platform_adapter
        self._bus: Optional["EventBus"] = None
        self._location_manager: Optional["LocationManager"] = None
        self._sensor_cache: Dict[str, Optional[str]] = {}  # location_id → sensor_id
        self._last_readings: Dict[str, AmbientLightReading] = {}

    @property
    def id(self) -> str:
        """Module identifier."""
        return "ambient"

    # =============================================================================
    # Module Lifecycle
    # =============================================================================

    def attach(self, bus: "EventBus", loc_manager: "LocationManager") -> None:
        """Attach module to kernel."""
        self._bus = bus
        self._location_manager = loc_manager
        logger.info("AmbientLightModule attached")

    def default_config(self) -> Dict:
        """Default configuration for a location."""
        return AmbientLightConfig().to_dict()

    def location_config_schema(self) -> Dict:
        """JSON schema for location configuration."""
        return {
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

    def migrate_config(self, config: Dict) -> Dict:
        """Migrate configuration to current version."""
        version = config.get("version", 1)

        if version == self.CURRENT_CONFIG_VERSION:
            return config

        # Future migrations go here

        config["version"] = self.CURRENT_CONFIG_VERSION
        return config

    def on_location_config_changed(self, location_id: str, config: Dict) -> None:
        """Handle location configuration changes."""
        # Clear sensor cache for this location
        if location_id in self._sensor_cache:
            del self._sensor_cache[location_id]

        logger.debug(f"Ambient config changed for {location_id}")

    def dump_state(self) -> Dict:
        """Dump module state for persistence."""
        return {
            "version": 1,
            "sensor_cache": self._sensor_cache,
            "last_readings": {
                loc_id: reading.to_dict()
                for loc_id, reading in self._last_readings.items()
            },
        }

    def restore_state(self, state: Dict) -> None:
        """Restore module state from persistence."""
        if state.get("version") != 1:
            logger.warning("State version mismatch, resetting")
            return

        self._sensor_cache = state.get("sensor_cache", {})
        # Note: We don't restore last_readings as they may be stale
        logger.info("AmbientLightModule state restored")

    # =============================================================================
    # Public API - Reading Queries
    # =============================================================================

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
        # Get configuration
        config = self._get_location_config(location_id)
        dark_thresh = dark_threshold or config.dark_threshold
        bright_thresh = bright_threshold or config.bright_threshold

        # 1. Try local sensor first
        sensor = self._find_lux_sensor_for_location(location_id)
        if sensor:
            lux = self._get_sensor_value(sensor)
            if lux is not None:
                reading = AmbientLightReading(
                    lux=lux,
                    source_sensor=sensor,
                    source_location=location_id,
                    is_inherited=False,
                    is_dark=lux < dark_thresh,
                    is_bright=lux > bright_thresh,
                    dark_threshold=dark_thresh,
                    bright_threshold=bright_thresh,
                    timestamp=datetime.now()
                )
                self._last_readings[location_id] = reading
                return reading

        # 2. Walk up parent hierarchy if inherit=True
        if inherit and config.inherit_from_parent:
            ancestors = self._location_manager.ancestors_of(location_id)
            for ancestor in ancestors:
                sensor = self._find_lux_sensor_for_location(ancestor.id)
                if sensor:
                    lux = self._get_sensor_value(sensor)
                    if lux is not None:
                        reading = AmbientLightReading(
                            lux=lux,
                            source_sensor=sensor,
                            source_location=ancestor.id,
                            is_inherited=True,
                            is_dark=lux < dark_thresh,
                            is_bright=lux > bright_thresh,
                            dark_threshold=dark_thresh,
                            bright_threshold=bright_thresh,
                            timestamp=datetime.now()
                        )
                        self._last_readings[location_id] = reading
                        return reading

        # 3. Fall back to sun position or error state
        if config.fallback_to_sun:
            reading = self._get_sun_fallback(dark_thresh, bright_thresh)
        else:
            reading = self._get_error_fallback(config, dark_thresh, bright_thresh)

        self._last_readings[location_id] = reading
        return reading

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
        """
        Check if location is bright.

        Args:
            location_id: Location to check
            threshold: Lux threshold (default from config)

        Returns:
            True if lux > threshold
        """
        reading = self.get_ambient_light(location_id, bright_threshold=threshold)
        return reading.is_bright

    # =============================================================================
    # Public API - Sensor Configuration
    # =============================================================================

    def set_lux_sensor(
        self,
        location_id: str,
        entity_id: str
    ) -> None:
        """
        Set the lux sensor for a location.

        Args:
            location_id: Location to configure
            entity_id: Lux sensor entity ID
        """
        config = self._get_location_config(location_id)
        config.lux_sensor = entity_id

        self._location_manager.set_module_config(
            location_id,
            self.id,
            config.to_dict()
        )

        # Update cache
        self._sensor_cache[location_id] = entity_id
        logger.info(f"Set lux sensor for {location_id}: {entity_id}")

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
        # Try local first
        sensor = self._find_lux_sensor_for_location(location_id)
        if sensor:
            return sensor

        # Walk up hierarchy if inherit=True
        if inherit:
            ancestors = self._location_manager.ancestors_of(location_id)
            for ancestor in ancestors:
                sensor = self._find_lux_sensor_for_location(ancestor.id)
                if sensor:
                    return sensor

        return None

    def auto_discover_sensors(self) -> Dict[str, str]:
        """
        Auto-discover lux sensors in all locations.

        Returns:
            Dict mapping location_id → sensor entity_id
        """
        discovered = {}

        for location in self._location_manager.all_locations():
            config = self._get_location_config(location.id)

            # Skip if auto-discover is disabled or sensor already configured
            if not config.auto_discover or config.lux_sensor:
                continue

            # Try to find lux sensor in location's entities
            for entity_id in location.entity_ids:
                if self._is_lux_sensor(entity_id):
                    discovered[location.id] = entity_id
                    # Update config
                    config.lux_sensor = entity_id
                    self._location_manager.set_module_config(
                        location.id,
                        self.id,
                        config.to_dict()
                    )
                    logger.info(f"Auto-discovered lux sensor: {location.id} → {entity_id}")
                    break

        return discovered

    # =============================================================================
    # Private Helpers - Sensor Detection
    # =============================================================================

    def _find_lux_sensor_for_location(self, location_id: str) -> Optional[str]:
        """Find lux sensor entity in location."""
        # Check cache first
        if location_id in self._sensor_cache:
            return self._sensor_cache[location_id]

        # Check config
        config = self._get_location_config(location_id)
        if config.lux_sensor:
            self._sensor_cache[location_id] = config.lux_sensor
            return config.lux_sensor

        # Auto-discover if enabled
        if config.auto_discover:
            location = self._location_manager.get_location(location_id)
            if location:
                for entity_id in location.entity_ids:
                    if self._is_lux_sensor(entity_id):
                        self._sensor_cache[location_id] = entity_id
                        return entity_id

        # Not found
        self._sensor_cache[location_id] = None
        return None

    def _is_lux_sensor(self, entity_id: str) -> bool:
        """
        Check if entity is a lux sensor.

        Args:
            entity_id: Entity ID to check

        Returns:
            True if entity appears to be a lux sensor
        """
        if not self._platform:
            # Fallback to pattern matching if no platform adapter
            return any(pattern in entity_id.lower()
                      for pattern in ["lux", "illuminance", "light_level", "brightness"])

        # Check entity ID pattern
        if any(pattern in entity_id.lower()
               for pattern in ["lux", "illuminance", "light_level"]):
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

    def _get_sensor_value(self, entity_id: str) -> Optional[float]:
        """Get numeric value from sensor."""
        if not self._platform:
            return None

        return self._platform.get_numeric_state(entity_id)

    # =============================================================================
    # Private Helpers - Configuration
    # =============================================================================

    def _get_location_config(self, location_id: str) -> AmbientLightConfig:
        """Get ambient light config for a location."""
        config_dict = self._location_manager.get_module_config(location_id, self.id)

        if config_dict:
            return AmbientLightConfig.from_dict(config_dict)

        return AmbientLightConfig()

    # =============================================================================
    # Private Helpers - Fallback Strategies
    # =============================================================================

    def _get_sun_fallback(
        self,
        dark_threshold: float,
        bright_threshold: float
    ) -> AmbientLightReading:
        """Get ambient light reading from sun position."""
        if not self._platform:
            # No platform adapter, assume dark
            return AmbientLightReading(
                lux=None,
                source_sensor=None,
                source_location=None,
                is_inherited=False,
                is_dark=True,
                is_bright=False,
                dark_threshold=dark_threshold,
                bright_threshold=bright_threshold,
                fallback_method="no_platform",
                timestamp=datetime.now()
            )

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
            timestamp=datetime.now()
        )

    def _get_error_fallback(
        self,
        config: AmbientLightConfig,
        dark_threshold: float,
        bright_threshold: float
    ) -> AmbientLightReading:
        """Get fallback reading when sensor unavailable and sun fallback disabled."""
        assume_dark = config.assume_dark_on_error

        return AmbientLightReading(
            lux=None,
            source_sensor=None,
            source_location=None,
            is_inherited=False,
            is_dark=assume_dark,
            is_bright=not assume_dark,
            dark_threshold=dark_threshold,
            bright_threshold=bright_threshold,
            fallback_method="assume_dark" if assume_dark else "assume_bright",
            timestamp=datetime.now()
        )

