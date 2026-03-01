"""
Adjacency edge model for topology-level boundary connections.

These structures represent durable topology relationships only.
They do not implement occupancy inference behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

VALID_DIRECTIONALITY = frozenset({"bidirectional", "a_to_b", "b_to_a"})


@dataclass
class AdjacencyEdge:
    """A directed or bidirectional edge between two locations."""

    edge_id: str
    from_location_id: str
    to_location_id: str
    directionality: str = "bidirectional"
    boundary_type: str = "virtual"
    crossing_sources: list[str] = field(default_factory=list)
    handoff_window_sec: int = 12
    priority: int = 50

    def to_dict(self) -> dict[str, Any]:
        """Serialize edge for storage and API responses."""
        return {
            "edge_id": self.edge_id,
            "from_location_id": self.from_location_id,
            "to_location_id": self.to_location_id,
            "directionality": self.directionality,
            "boundary_type": self.boundary_type,
            "crossing_sources": list(self.crossing_sources),
            "handoff_window_sec": int(self.handoff_window_sec),
            "priority": int(self.priority),
        }
