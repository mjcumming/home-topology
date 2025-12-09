"""
Tests for the Ambient Light Module.

Tests hierarchical sensor lookup, fallback strategies, and configuration.
"""

import pytest
from unittest.mock import Mock

from home_topology.modules.ambient import (
    AmbientLightModule,
    AmbientLightReading,
    AmbientLightConfig,
)
from home_topology.core import LocationManager, EventBus


@pytest.fixture
def platform_adapter():
    """Mock platform adapter."""
    adapter = Mock()
    adapter.get_numeric_state = Mock(return_value=None)
    adapter.get_state = Mock(return_value=None)
    adapter.get_device_class = Mock(return_value=None)
    adapter.get_unit_of_measurement = Mock(return_value=None)
    return adapter


@pytest.fixture
def loc_manager():
    """Location manager with test hierarchy."""
    mgr = LocationManager()

    # Create hierarchy:
    # house
    #   └─ main_floor
    #       ├─ kitchen
    #       └─ living_room
    mgr.create_location(
        id="house",
        name="House",
        parent_id=None,
        is_explicit_root=True,
    )
    mgr.create_location(
        id="main_floor",
        name="Main Floor",
        parent_id="house",
    )
    mgr.create_location(
        id="kitchen",
        name="Kitchen",
        parent_id="main_floor",
    )
    mgr.create_location(
        id="living_room",
        name="Living Room",
        parent_id="main_floor",
    )

    return mgr


@pytest.fixture
def event_bus():
    """Event bus."""
    return EventBus()


@pytest.fixture
def ambient_module(platform_adapter):
    """Ambient light module with mock platform."""
    return AmbientLightModule(platform_adapter=platform_adapter)


@pytest.fixture
def attached_ambient_module(ambient_module, event_bus, loc_manager):
    """Ambient module attached to kernel."""
    ambient_module.attach(event_bus, loc_manager)
    return ambient_module


# =============================================================================
# Basic Module Tests
# =============================================================================


class TestAmbientModuleBasics:
    """Basic behavior and regression tests."""

    def test_current_config_version_accessible(self):
        """CURRENT_CONFIG_VERSION should not recurse."""
        module = AmbientLightModule()
        assert isinstance(module.CURRENT_CONFIG_VERSION, int)
        assert module.CURRENT_CONFIG_VERSION == 1

    def test_current_config_version_class_attribute(self):
        """CURRENT_CONFIG_VERSION is a class attribute."""
        assert hasattr(AmbientLightModule, "CURRENT_CONFIG_VERSION")
        assert AmbientLightModule.CURRENT_CONFIG_VERSION == 1

    def test_module_attachment(self):
        """Module can attach to kernel."""
        loc_mgr = LocationManager()
        bus = EventBus()
        module = AmbientLightModule()

        module.attach(bus, loc_mgr)

        assert module._bus is bus
        assert module._location_manager is loc_mgr

    def test_default_config(self):
        """default_config returns valid config."""
        module = AmbientLightModule()
        config = module.default_config()

        assert isinstance(config, dict)
        assert config["version"] == module.CURRENT_CONFIG_VERSION
        assert "lux_sensor" in config
        assert "dark_threshold" in config
        assert "bright_threshold" in config
        assert config["auto_discover"] is True
        assert config["inherit_from_parent"] is True
        assert config["fallback_to_sun"] is True
        assert config["assume_dark_on_error"] is True

    def test_location_config_schema(self):
        """location_config_schema contains required properties."""
        module = AmbientLightModule()
        schema = module.location_config_schema()

        assert isinstance(schema, dict)
        assert schema["type"] == "object"
        props = schema["properties"]
        assert "lux_sensor" in props
        assert "dark_threshold" in props
        assert "bright_threshold" in props


# =============================================================================
# Configuration Tests
# =============================================================================


class TestConfiguration:
    """Test configuration management."""

    def test_set_lux_sensor(self, attached_ambient_module, loc_manager):
        """Setting lux sensor should persist to config."""
        attached_ambient_module.set_lux_sensor("kitchen", "sensor.kitchen_lux")

        config = loc_manager.get_module_config("kitchen", "ambient")
        assert config["lux_sensor"] == "sensor.kitchen_lux"

    def test_config_migration(self, ambient_module):
        """Existing current-version config stays unchanged."""
        old_config = {"version": 1, "lux_sensor": "sensor.test"}

        migrated = ambient_module.migrate_config(old_config)

        assert migrated == old_config
        assert migrated["version"] == 1
        assert migrated["lux_sensor"] == "sensor.test"


class TestAmbientModuleConfiguration:
    """Additional configuration tests."""

    def test_migrate_config_current_version(self):
        """Migration with matching version returns unchanged config."""
        module = AmbientLightModule()
        config = {
            "version": 1,
            "lux_sensor": "sensor.living_room_lux",
            "dark_threshold": 50.0,
        }

        migrated = module.migrate_config(config)

        assert migrated == config
        assert "lux_sensor" in migrated


# =============================================================================
# Sensor Detection Tests
# =============================================================================


class TestSensorDetection:
    """Test automatic sensor detection."""

    def test_detect_by_entity_id_pattern_lux(self, ambient_module):
        """Test detection by 'lux' in entity ID."""
        assert ambient_module._is_lux_sensor("sensor.kitchen_lux")
        assert ambient_module._is_lux_sensor("sensor.outdoor_lux_level")

    def test_detect_by_entity_id_pattern_illuminance(self, ambient_module):
        """Test detection by 'illuminance' in entity ID."""
        assert ambient_module._is_lux_sensor("sensor.kitchen_illuminance")
        assert ambient_module._is_lux_sensor("sensor.room_illuminance_level")

    def test_detect_by_device_class(self, platform_adapter, ambient_module):
        """Test detection by device_class = illuminance."""
        platform_adapter.get_device_class.return_value = "illuminance"

        assert ambient_module._is_lux_sensor("sensor.light_sensor_123")

    def test_detect_by_unit_of_measurement(self, platform_adapter, ambient_module):
        """Test detection by unit = lx."""
        platform_adapter.get_unit_of_measurement.return_value = "lx"

        assert ambient_module._is_lux_sensor("sensor.brightness_sensor")

    def test_no_detection(self, ambient_module):
        """Test non-lux sensors not detected."""
        assert not ambient_module._is_lux_sensor("sensor.temperature")
        assert not ambient_module._is_lux_sensor("light.kitchen_ceiling")
        assert not ambient_module._is_lux_sensor("binary_sensor.motion")

    def test_auto_discover_in_location(self, attached_ambient_module, loc_manager):
        """Test auto-discovering sensor in location's entities."""
        # Add lux sensor to kitchen
        loc_manager.add_entity_to_location("sensor.kitchen_lux", "kitchen")

        # Should auto-discover
        sensor = attached_ambient_module._find_lux_sensor_for_location("kitchen")
        assert sensor == "sensor.kitchen_lux"

    def test_explicit_sensor_overrides_discovery(self, attached_ambient_module, loc_manager):
        """Test explicit config overrides auto-discovery."""
        # Add two sensors
        loc_manager.add_entity_to_location("sensor.kitchen_lux_1", "kitchen")
        loc_manager.add_entity_to_location("sensor.kitchen_lux_2", "kitchen")

        # Set explicit sensor
        attached_ambient_module.set_lux_sensor("kitchen", "sensor.kitchen_lux_2")

        sensor = attached_ambient_module._find_lux_sensor_for_location("kitchen")
        assert sensor == "sensor.kitchen_lux_2"


# =============================================================================
# Hierarchical Lookup Tests
# =============================================================================


class TestHierarchicalLookup:
    """Test hierarchical sensor lookup."""

    def test_local_sensor_preferred(self, attached_ambient_module, loc_manager, platform_adapter):
        """Test local sensor is used if available."""
        # Add sensors at different levels
        loc_manager.add_entity_to_location("sensor.house_lux", "house")
        loc_manager.add_entity_to_location("sensor.kitchen_lux", "kitchen")

        attached_ambient_module.set_lux_sensor("house", "sensor.house_lux")
        attached_ambient_module.set_lux_sensor("kitchen", "sensor.kitchen_lux")

        # Kitchen should use local sensor
        platform_adapter.get_numeric_state.return_value = 200.0
        reading = attached_ambient_module.get_ambient_light("kitchen")

        assert reading.source_sensor == "sensor.kitchen_lux"
        assert reading.source_location == "kitchen"
        assert reading.is_inherited is False
        assert reading.lux == 200.0

    def test_inherit_from_parent(self, attached_ambient_module, loc_manager, platform_adapter):
        """Test inheriting sensor from parent."""
        # Only main_floor has sensor
        loc_manager.add_entity_to_location("sensor.main_floor_lux", "main_floor")
        attached_ambient_module.set_lux_sensor("main_floor", "sensor.main_floor_lux")

        # Kitchen should inherit from main_floor
        platform_adapter.get_numeric_state.return_value = 150.0
        reading = attached_ambient_module.get_ambient_light("kitchen")

        assert reading.source_sensor == "sensor.main_floor_lux"
        assert reading.source_location == "main_floor"
        assert reading.is_inherited is True
        assert reading.lux == 150.0

    def test_inherit_from_grandparent(self, attached_ambient_module, loc_manager, platform_adapter):
        """Test inheriting from grandparent."""
        # Only house has sensor
        loc_manager.add_entity_to_location("sensor.house_lux", "house")
        attached_ambient_module.set_lux_sensor("house", "sensor.house_lux")

        # Kitchen should inherit from house
        platform_adapter.get_numeric_state.return_value = 1000.0
        reading = attached_ambient_module.get_ambient_light("kitchen")

        assert reading.source_sensor == "sensor.house_lux"
        assert reading.source_location == "house"
        assert reading.is_inherited is True
        assert reading.lux == 1000.0

    def test_no_inherit_when_disabled(self, attached_ambient_module, loc_manager, platform_adapter):
        """Test inheritance can be disabled."""
        # House has sensor
        loc_manager.add_entity_to_location("sensor.house_lux", "house")
        attached_ambient_module.set_lux_sensor("house", "sensor.house_lux")

        # Kitchen disables inheritance
        loc_manager.set_module_config(
            "kitchen",
            "ambient",
            {
                "inherit_from_parent": False,
                "fallback_to_sun": True,
            },
        )

        # Should fall back to sun instead of inheriting
        platform_adapter.get_state.return_value = "above_horizon"
        reading = attached_ambient_module.get_ambient_light("kitchen", inherit=False)

        assert reading.source_sensor is None
        assert reading.fallback_method == "sun_position"


# =============================================================================
# Reading Tests
# =============================================================================


class TestAmbientLightReading:
    """Test ambient light reading generation."""

    def test_reading_with_lux(self, attached_ambient_module, loc_manager, platform_adapter):
        """Test reading with valid lux value."""
        loc_manager.add_entity_to_location("sensor.kitchen_lux", "kitchen")
        attached_ambient_module.set_lux_sensor("kitchen", "sensor.kitchen_lux")

        platform_adapter.get_numeric_state.return_value = 200.0
        reading = attached_ambient_module.get_ambient_light("kitchen")

        assert reading.lux == 200.0
        assert reading.is_dark is False  # 200 > 50
        assert reading.is_bright is False  # 200 < 500
        assert reading.dark_threshold == 50.0
        assert reading.bright_threshold == 500.0

    def test_reading_is_dark(self, attached_ambient_module, loc_manager, platform_adapter):
        """Test reading correctly identifies dark conditions."""
        loc_manager.add_entity_to_location("sensor.kitchen_lux", "kitchen")
        attached_ambient_module.set_lux_sensor("kitchen", "sensor.kitchen_lux")

        platform_adapter.get_numeric_state.return_value = 30.0
        reading = attached_ambient_module.get_ambient_light("kitchen")

        assert reading.is_dark is True  # 30 < 50
        assert reading.is_bright is False

    def test_reading_is_bright(self, attached_ambient_module, loc_manager, platform_adapter):
        """Test reading correctly identifies bright conditions."""
        loc_manager.add_entity_to_location("sensor.kitchen_lux", "kitchen")
        attached_ambient_module.set_lux_sensor("kitchen", "sensor.kitchen_lux")

        platform_adapter.get_numeric_state.return_value = 800.0
        reading = attached_ambient_module.get_ambient_light("kitchen")

        assert reading.is_dark is False
        assert reading.is_bright is True  # 800 > 500

    def test_custom_thresholds(self, attached_ambient_module, loc_manager, platform_adapter):
        """Test custom thresholds."""
        loc_manager.add_entity_to_location("sensor.kitchen_lux", "kitchen")
        attached_ambient_module.set_lux_sensor("kitchen", "sensor.kitchen_lux")

        # Set custom thresholds in config
        loc_manager.set_module_config(
            "kitchen",
            "ambient",
            {
                "dark_threshold": 20.0,
                "bright_threshold": 1000.0,
            },
        )

        platform_adapter.get_numeric_state.return_value = 30.0
        reading = attached_ambient_module.get_ambient_light("kitchen")

        assert reading.is_dark is False  # 30 > 20
        assert reading.dark_threshold == 20.0

    def test_override_thresholds(self, attached_ambient_module, loc_manager, platform_adapter):
        """Test overriding thresholds at query time."""
        loc_manager.add_entity_to_location("sensor.kitchen_lux", "kitchen")
        attached_ambient_module.set_lux_sensor("kitchen", "sensor.kitchen_lux")

        platform_adapter.get_numeric_state.return_value = 40.0

        # Override dark threshold
        reading = attached_ambient_module.get_ambient_light(
            "kitchen",
            dark_threshold=60.0,
        )

        assert reading.is_dark is True  # 40 < 60
        assert reading.dark_threshold == 60.0


# =============================================================================
# Fallback Strategy Tests
# =============================================================================


class TestFallbackStrategies:
    """Test fallback strategies when sensors unavailable."""

    def test_sun_fallback_below_horizon(self, attached_ambient_module, platform_adapter):
        """Test sun fallback when sun is below horizon."""
        platform_adapter.get_state.return_value = "below_horizon"

        reading = attached_ambient_module.get_ambient_light("kitchen")

        assert reading.fallback_method == "sun_position"
        assert reading.is_dark is True
        assert reading.lux == 0.0

    def test_sun_fallback_above_horizon(self, attached_ambient_module, platform_adapter):
        """Test sun fallback when sun is above horizon."""
        platform_adapter.get_state.return_value = "above_horizon"

        reading = attached_ambient_module.get_ambient_light("kitchen")

        assert reading.fallback_method == "sun_position"
        assert reading.is_dark is False
        assert reading.lux == 1000.0

    def test_assume_dark_on_error(self, attached_ambient_module, loc_manager):
        """Test assuming dark when sensor unavailable and sun fallback disabled."""
        loc_manager.set_module_config(
            "kitchen",
            "ambient",
            {
                "fallback_to_sun": False,
                "assume_dark_on_error": True,
            },
        )

        reading = attached_ambient_module.get_ambient_light("kitchen")

        assert reading.fallback_method == "assume_dark"
        assert reading.is_dark is True
        assert reading.lux is None

    def test_assume_bright_on_error(self, attached_ambient_module, loc_manager):
        """Test assuming bright when configured."""
        loc_manager.set_module_config(
            "kitchen",
            "ambient",
            {
                "fallback_to_sun": False,
                "assume_dark_on_error": False,
            },
        )

        reading = attached_ambient_module.get_ambient_light("kitchen")

        assert reading.fallback_method == "assume_bright"
        assert reading.is_dark is False
        assert reading.lux is None


# =============================================================================
# Convenience Method Tests
# =============================================================================


class TestConvenienceMethods:
    """Test convenience methods (is_dark, is_bright)."""

    def test_is_dark(self, attached_ambient_module, loc_manager, platform_adapter):
        """Test is_dark() convenience method."""
        loc_manager.add_entity_to_location("sensor.kitchen_lux", "kitchen")
        attached_ambient_module.set_lux_sensor("kitchen", "sensor.kitchen_lux")

        platform_adapter.get_numeric_state.return_value = 30.0

        assert attached_ambient_module.is_dark("kitchen") is True

    def test_is_bright(self, attached_ambient_module, loc_manager, platform_adapter):
        """Test is_bright() convenience method."""
        loc_manager.add_entity_to_location("sensor.kitchen_lux", "kitchen")
        attached_ambient_module.set_lux_sensor("kitchen", "sensor.kitchen_lux")

        platform_adapter.get_numeric_state.return_value = 800.0

        assert attached_ambient_module.is_bright("kitchen") is True

    def test_get_lux_sensor(self, attached_ambient_module, loc_manager):
        """Test get_lux_sensor() method."""
        # Set up hierarchy
        loc_manager.add_entity_to_location("sensor.house_lux", "house")
        attached_ambient_module.set_lux_sensor("house", "sensor.house_lux")

        # Local sensor
        loc_manager.add_entity_to_location("sensor.kitchen_lux", "kitchen")
        attached_ambient_module.set_lux_sensor("kitchen", "sensor.kitchen_lux")

        # Kitchen should return local
        assert attached_ambient_module.get_lux_sensor("kitchen") == "sensor.kitchen_lux"

        # Living room should inherit from house
        assert attached_ambient_module.get_lux_sensor("living_room") == "sensor.house_lux"

        # Living room with inherit=False should return None
        assert attached_ambient_module.get_lux_sensor("living_room", inherit=False) is None


# =============================================================================
# State Persistence Tests
# =============================================================================


class TestStatePersistence:
    """Test state dump and restore."""

    def test_dump_state(self, attached_ambient_module, loc_manager):
        """Test dumping module state."""
        attached_ambient_module.set_lux_sensor("kitchen", "sensor.kitchen_lux")

        state = attached_ambient_module.dump_state()

        assert state["version"] == 1
        assert "kitchen" in state["sensor_cache"]
        assert state["sensor_cache"]["kitchen"] == "sensor.kitchen_lux"

    def test_restore_state(self, attached_ambient_module):
        """Test restoring module state."""
        state = {
            "version": 1,
            "sensor_cache": {
                "kitchen": "sensor.kitchen_lux",
                "living_room": "sensor.living_room_lux",
            },
        }

        attached_ambient_module.restore_state(state)

        assert attached_ambient_module._sensor_cache["kitchen"] == "sensor.kitchen_lux"
        assert attached_ambient_module._sensor_cache["living_room"] == "sensor.living_room_lux"

    def test_restore_state_version_mismatch(self, attached_ambient_module):
        """Test handling version mismatch on restore."""
        state = {
            "version": 999,
            "sensor_cache": {},
        }

        # Should not crash, just log warning
        attached_ambient_module.restore_state(state)

        # Cache should be empty
        assert len(attached_ambient_module._sensor_cache) == 0


# =============================================================================
# Auto-Discovery Tests
# =============================================================================


class TestAutoDiscovery:
    """Test auto-discovery of sensors."""

    def test_auto_discover_sensors(self, attached_ambient_module, loc_manager):
        """Test auto-discovering all sensors."""
        # Add lux sensors to locations
        loc_manager.add_entity_to_location("sensor.kitchen_lux", "kitchen")
        loc_manager.add_entity_to_location("sensor.living_room_illuminance", "living_room")

        discovered = attached_ambient_module.auto_discover_sensors()

        assert "kitchen" in discovered
        assert "living_room" in discovered
        assert discovered["kitchen"] == "sensor.kitchen_lux"
        assert discovered["living_room"] == "sensor.living_room_illuminance"

    def test_auto_discover_skips_configured(self, attached_ambient_module, loc_manager):
        """Test auto-discovery skips already configured locations."""
        # Pre-configure kitchen
        attached_ambient_module.set_lux_sensor("kitchen", "sensor.kitchen_lux_manual")

        # Add different sensor to entities
        loc_manager.add_entity_to_location("sensor.kitchen_lux_auto", "kitchen")

        discovered = attached_ambient_module.auto_discover_sensors()

        # Kitchen should not be in discovered (already configured)
        assert "kitchen" not in discovered

        # Verify it still uses manual config
        sensor = attached_ambient_module.get_lux_sensor("kitchen")
        assert sensor == "sensor.kitchen_lux_manual"


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for realistic scenarios."""

    def test_whole_house_scenario(self, attached_ambient_module, loc_manager, platform_adapter):
        """Test realistic whole-house scenario."""
        # Set up sensors
        loc_manager.add_entity_to_location("sensor.outdoor_lux", "house")
        loc_manager.add_entity_to_location("sensor.kitchen_lux", "kitchen")

        attached_ambient_module.set_lux_sensor("house", "sensor.outdoor_lux")
        attached_ambient_module.set_lux_sensor("kitchen", "sensor.kitchen_lux")

        # Configure sensor values
        def get_numeric_state(entity_id):
            if entity_id == "sensor.outdoor_lux":
                return 1000.0
            elif entity_id == "sensor.kitchen_lux":
                return 200.0
            return None

        platform_adapter.get_numeric_state.side_effect = get_numeric_state

        # Kitchen uses local sensor
        kitchen_reading = attached_ambient_module.get_ambient_light("kitchen")
        assert kitchen_reading.lux == 200.0
        assert kitchen_reading.is_inherited is False

        # Living room inherits from house
        living_reading = attached_ambient_module.get_ambient_light("living_room")
        assert living_reading.lux == 1000.0
        assert living_reading.is_inherited is True
        assert living_reading.source_location == "house"


# =============================================================================
# Regression Tests
# =============================================================================


class TestAmbientModuleRegression:
    """Regression tests for specific bugs."""

    def test_no_recursion_error_on_setup(self):
        """Accessing CURRENT_CONFIG_VERSION should not recurse."""
        module = AmbientLightModule()
        loc_mgr = LocationManager()
        bus = EventBus()

        # Create a location
        loc_mgr.create_location("kitchen", "Kitchen")

        # Attach module
        module.attach(bus, loc_mgr)

        # Get default config - this is where the bug manifested
        default_config = module.default_config()

        # Try to access CURRENT_CONFIG_VERSION like _setup_default_configs does
        try:
            version = module.CURRENT_CONFIG_VERSION
            default_config["version"] = version
            success = True
        except RecursionError:
            success = False

        assert success, "Accessing CURRENT_CONFIG_VERSION caused RecursionError"
        assert default_config["version"] == 1

    def test_config_version_not_property(self):
        """CURRENT_CONFIG_VERSION should be a class attribute, not a property."""
        module = AmbientLightModule()

        # Check it's not a property object
        attr = getattr(type(module), "CURRENT_CONFIG_VERSION", None)
        assert not isinstance(attr, property), "CURRENT_CONFIG_VERSION should not be a property"

        # Should be directly accessible
        assert isinstance(module.CURRENT_CONFIG_VERSION, int)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
