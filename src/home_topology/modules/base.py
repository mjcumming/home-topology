"""
Base classes and protocols for home-topology modules.

Modules are plug-ins that add behavior to locations.
"""

from abc import ABC, abstractmethod
from typing import Dict


class LocationModule(ABC):
    """
    Base class for location modules.

    A module:
    - Receives events from the Event Bus
    - Uses the LocationManager to understand hierarchy
    - Maintains its own runtime state
    - Emits semantic events that other modules can consume
    """

    @property
    @abstractmethod
    def id(self) -> str:
        """Unique identifier for this module type."""
        pass

    @property
    @abstractmethod
    def CURRENT_CONFIG_VERSION(self) -> int:
        """Current configuration version for this module."""
        pass

    @abstractmethod
    def attach(self, bus, loc_manager) -> None:
        """
        Attach the module to the kernel.

        Register event subscriptions and capture references to bus and location manager.

        Args:
            bus: EventBus instance
            loc_manager: LocationManager instance
        """
        pass

    @abstractmethod
    def default_config(self) -> Dict:
        """
        Get default configuration for this module.

        Returns:
            Default configuration dict
        """
        pass

    @abstractmethod
    def location_config_schema(self) -> Dict:
        """
        Get JSON-schema-like definition for UI configuration.

        Returns:
            Schema dict that UIs can use to render configuration forms
        """
        pass

    def migrate_config(self, config: Dict) -> Dict:
        """
        Migrate configuration to current version.

        Default implementation returns config unchanged.
        Override to handle version upgrades.

        Args:
            config: Configuration dict (potentially older version)

        Returns:
            Migrated configuration dict
        """
        return config

    def on_location_config_changed(self, location_id: str, config: Dict) -> None:
        """
        React to configuration changes for a location.

        Called when configuration is updated for this module on a specific location.

        Args:
            location_id: The location ID
            config: The new configuration
        """
        pass

    def dump_state(self) -> Dict:
        """
        Serialize runtime state for persistence.

        Optional: Override to enable state dump/restore.
        Host platform is responsible for storage.

        Returns:
            Serialized state dict
        """
        return {}

    def restore_state(self, state: Dict) -> None:
        """
        Restore runtime state from serialized form.

        Optional: Override to enable state dump/restore.

        Args:
            state: Previously serialized state dict
        """
        pass
