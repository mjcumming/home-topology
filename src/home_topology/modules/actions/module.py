"""
ActionsModule implementation.

Triggers automations based on location events and state changes.
"""

from typing import Dict
from home_topology.modules.base import LocationModule


class ActionsModule(LocationModule):
    """
    Module that handles action/automation execution.

    Responds to semantic events (like occupancy changes) and triggers
    platform-specific actions.
    """

    @property
    def id(self) -> str:
        return "actions"

    @property
    def CURRENT_CONFIG_VERSION(self) -> int:
        return 1

    def attach(self, bus, loc_manager) -> None:
        """
        Attach the actions module to the kernel.

        TODO: Subscribe to semantic events
        """
        self._bus = bus
        self._loc_manager = loc_manager

        # TODO: Subscribe to events
        # bus.subscribe(self._on_occupancy_changed, EventFilter(event_type="occupancy.changed"))

    def default_config(self) -> Dict:
        """Get default actions configuration."""
        return {
            "version": self.CURRENT_CONFIG_VERSION,
            "rules": [],
            "enabled": True,
        }

    def location_config_schema(self) -> Dict:
        """
        Get configuration schema for actions module.

        Returns a JSON-schema-like structure for UI rendering.
        """
        return {
            "type": "object",
            "properties": {
                "version": {
                    "type": "integer",
                    "title": "Config Version",
                    "readOnly": True,
                },
                "rules": {
                    "type": "array",
                    "title": "Action Rules",
                    "description": "Automation rules for this location",
                    "items": {
                        "type": "object",
                        "properties": {
                            "trigger": {"type": "string"},
                            "condition": {"type": "object"},
                            "actions": {"type": "array"},
                        },
                    },
                },
                "enabled": {
                    "type": "boolean",
                    "title": "Enabled",
                    "description": "Enable actions for this location",
                    "default": True,
                },
            },
            "required": ["version", "enabled"],
        }
