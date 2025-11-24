"""
Core components of the home-topology kernel.

This package contains:
- bus: Event Bus implementation
- location: Location dataclass and helpers
- manager: LocationManager for topology and config
"""

from home_topology.core.location import Location
from home_topology.core.bus import Event, EventBus, EventFilter
from home_topology.core.manager import LocationManager

__all__ = [
    "Location",
    "Event",
    "EventBus",
    "EventFilter",
    "LocationManager",
]

