"""
Occupancy module for home-topology.

Computes occupied / confidence per Location based on sensor inputs.

Features:
- Hierarchical occupancy with parent/child propagation
- Identity tracking (who is in the room)
- Locking logic (party mode - freeze state)
- Multiple event types: momentary, hold_start, hold_end, manual
- State persistence with stale data cleanup

"""

from .module import OccupancyModule
from .models import (
    EventType,
    LocationKind,
    LockState,
    OccupancyStrategy,
)

__all__ = [
    "OccupancyModule",
    "EventType",
    "LocationKind",
    "LockState",
    "OccupancyStrategy",
]
