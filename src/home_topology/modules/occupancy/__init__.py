"""
Occupancy module for home-topology.

Computes occupied/vacant state per location based on source contributions.

Features:
- Hierarchical occupancy with parent/child propagation
- Source-tracked locking (multiple automations can lock independently)
- v3 event model: TRIGGER, CLEAR, VACATE, LOCK, UNLOCK, UNLOCK_ALL
- State persistence with stale data cleanup
- Binary occupied/vacant state (no confidence scoring)
- Signal classification at integration layer
"""

from .engine import OccupancyEngine
from .models import (
    EngineResult,
    EventType,
    LocationConfig,
    LocationRuntimeState,
    OccupancyEvent,
    OccupancyStrategy,
    SourceContribution,
    StateTransition,
    SuspendedContribution,
)
from .module import OccupancyModule

__all__ = [
    "OccupancyModule",
    "OccupancyEngine",
    "EventType",
    "OccupancyStrategy",
    "LocationConfig",
    "LocationRuntimeState",
    "SourceContribution",
    "SuspendedContribution",
    "OccupancyEvent",
    "StateTransition",
    "EngineResult",
]
