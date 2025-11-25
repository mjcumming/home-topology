"""
Occupancy module for home-topology.

Computes occupied/vacant state per Location based on sensor inputs.

Features:
- Hierarchical occupancy with parent/child propagation
- Identity tracking (who is in the room)
- Source-tracked locking (multiple automations can lock independently)
- 7 event types: TRIGGER, HOLD, RELEASE, VACATE, LOCK, UNLOCK, UNLOCK_ALL
- State persistence with stale data cleanup
- Binary occupied/vacant state (no confidence scoring)
- Signal classification at integration layer
"""

from .module import OccupancyModule
from .models import (
    EventType,
    OccupancyStrategy,
    LocationConfig,
    LocationRuntimeState,
    OccupancyEvent,
    StateTransition,
    EngineResult,
)
from .engine import OccupancyEngine

__all__ = [
    "OccupancyModule",
    "OccupancyEngine",
    "EventType",
    "OccupancyStrategy",
    "LocationConfig",
    "LocationRuntimeState",
    "OccupancyEvent",
    "StateTransition",
    "EngineResult",
]
