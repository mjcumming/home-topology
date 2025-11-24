"""
OccupancyModule implementation.

Tracks occupancy state and confidence for locations based on sensor inputs.
"""

from typing import Dict
from home_topology.modules.base import LocationModule


class OccupancyModule(LocationModule):
    """
    Module that computes occupancy state per location.
    
    Tracks:
    - occupied: bool (is the location currently occupied?)
    - confidence: float 0-1 (how confident are we?)
    """
    
    @property
    def id(self) -> str:
        return "occupancy"
    
    @property
    def CURRENT_CONFIG_VERSION(self) -> int:
        return 1
    
    def attach(self, bus, loc_manager) -> None:
        """
        Attach the occupancy module to the kernel.
        
        TODO: Subscribe to relevant events (e.g., sensor.state_changed)
        """
        self._bus = bus
        self._loc_manager = loc_manager
        
        # TODO: Subscribe to events
        # bus.subscribe(self._on_sensor_state_changed, EventFilter(event_type="sensor.state_changed"))
    
    def default_config(self) -> Dict:
        """Get default occupancy configuration."""
        return {
            "version": self.CURRENT_CONFIG_VERSION,
            "motion_sensors": [],
            "timeout_seconds": 300,  # 5 minutes default
            "enabled": True,
        }
    
    def location_config_schema(self) -> Dict:
        """
        Get configuration schema for occupancy module.
        
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
                "motion_sensors": {
                    "type": "array",
                    "title": "Motion Sensors",
                    "description": "Entity IDs of motion sensors for this location",
                    "items": {"type": "string"},
                },
                "timeout_seconds": {
                    "type": "integer",
                    "title": "Timeout (seconds)",
                    "description": "How long after last motion before marking unoccupied",
                    "minimum": 0,
                    "default": 300,
                },
                "enabled": {
                    "type": "boolean",
                    "title": "Enabled",
                    "description": "Enable occupancy tracking for this location",
                    "default": True,
                },
            },
            "required": ["version", "enabled"],
        }
    
    def get_location_state(self, location_id: str) -> Dict:
        """
        Get occupancy state for a location.
        
        TODO: Implement actual state tracking
        
        Args:
            location_id: The location ID
            
        Returns:
            Dict with 'occupied' and 'confidence' keys
        """
        # Placeholder implementation
        return {
            "occupied": False,
            "confidence": 0.0,
        }

