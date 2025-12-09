"""Tests for AmbientLightModule.

Tests basic module functionality including:
- Module initialization
- Configuration management
- CURRENT_CONFIG_VERSION accessibility (regression test for recursion bug)
"""

from __future__ import annotations

import pytest

from home_topology import EventBus, LocationManager
from home_topology.modules.ambient import AmbientLightModule


class TestAmbientModuleBasics:
    """Test basic AmbientLightModule functionality."""

    def test_module_creation(self):
        """Test that AmbientLightModule can be instantiated."""
        module = AmbientLightModule()
        assert module is not None
        assert module.id == "ambient"

    def test_current_config_version_accessible(self):
        """Test CURRENT_CONFIG_VERSION doesn't cause recursion.
        
        Regression test for bug where CURRENT_CONFIG_VERSION property
        was calling itself infinitely.
        """
        module = AmbientLightModule()
        
        # This should not raise RecursionError
        version = module.CURRENT_CONFIG_VERSION
        
        assert isinstance(version, int)
        assert version == 1

    def test_current_config_version_class_attribute(self):
        """Test CURRENT_CONFIG_VERSION exists as class attribute."""
        # Should be accessible on class
        assert hasattr(AmbientLightModule, "CURRENT_CONFIG_VERSION")
        assert AmbientLightModule.CURRENT_CONFIG_VERSION == 1

    def test_module_attachment(self):
        """Test that module can be attached to kernel."""
        loc_mgr = LocationManager()
        bus = EventBus()
        module = AmbientLightModule()
        
        # Should not raise
        module.attach(bus, loc_mgr)
        
        # Verify internal state set
        assert module._bus is bus
        assert module._location_manager is loc_mgr

    def test_default_config(self):
        """Test that default_config returns valid config."""
        module = AmbientLightModule()
        config = module.default_config()
        
        assert isinstance(config, dict)
        assert "version" in config
        assert config["version"] == 1
        assert "lux_sensor" in config
        assert "dark_threshold" in config
        assert "bright_threshold" in config

    def test_default_config_uses_current_version(self):
        """Test that default config includes CURRENT_CONFIG_VERSION."""
        module = AmbientLightModule()
        config = module.default_config()
        
        # Should match CURRENT_CONFIG_VERSION
        assert config["version"] == module.CURRENT_CONFIG_VERSION

    def test_location_config_schema(self):
        """Test that location config schema is valid."""
        module = AmbientLightModule()
        schema = module.location_config_schema()
        
        assert isinstance(schema, dict)
        assert schema["type"] == "object"
        assert "properties" in schema
        
        # Check key properties exist
        props = schema["properties"]
        assert "lux_sensor" in props
        assert "dark_threshold" in props
        assert "bright_threshold" in props


class TestAmbientModuleConfiguration:
    """Test configuration-related functionality."""

    def test_migrate_config_current_version(self):
        """Test migration of already-current config."""
        module = AmbientLightModule()
        config = {
            "version": 1,
            "lux_sensor": "sensor.living_room_lux",
            "dark_threshold": 50.0,
        }
        
        migrated = module.migrate_config(config)
        
        # Should return unchanged
        assert migrated == config
        assert migrated["version"] == 1

    def test_migrate_config_no_version(self):
        """Test migration of config without version field."""
        module = AmbientLightModule()
        config = {
            "lux_sensor": "sensor.living_room_lux",
        }
        
        migrated = module.migrate_config(config)
        
        # Current implementation returns unchanged if version matches
        # This test documents current behavior - may want to enhance later
        assert "lux_sensor" in migrated


class TestAmbientModuleRegression:
    """Regression tests for specific bugs."""

    def test_no_recursion_error_on_setup(self):
        """Test that setting up default configs doesn't cause recursion.
        
        This was the exact error that occurred in HA integration:
        RecursionError when trying to access module.CURRENT_CONFIG_VERSION
        during _setup_default_configs.
        """
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
        """Test that CURRENT_CONFIG_VERSION is not a property.
        
        The bug was caused by making CURRENT_CONFIG_VERSION a @property
        that returned self.CURRENT_CONFIG_VERSION, causing infinite recursion.
        """
        module = AmbientLightModule()
        
        # Check it's not a property object
        attr = getattr(type(module), "CURRENT_CONFIG_VERSION", None)
        assert not isinstance(attr, property), \
            "CURRENT_CONFIG_VERSION should be a class attribute, not a property"
        
        # Should be directly accessible
        assert isinstance(module.CURRENT_CONFIG_VERSION, int)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

