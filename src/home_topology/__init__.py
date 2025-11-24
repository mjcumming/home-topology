"""
home-topology: A platform-agnostic home topology kernel.

This library provides the structural backbone for smart homes:
- Location graph (topology) modeling
- Module-based behavior plug-ins
- Location-aware Event Bus
- Schema-driven configuration
"""

from home_topology.core.location import Location
from home_topology.core.bus import Event, EventBus, EventFilter
from home_topology.core.manager import LocationManager

__version__ = "0.1.0"

__all__ = [
    "Location",
    "Event",
    "EventBus",
    "EventFilter",
    "LocationManager",
]

