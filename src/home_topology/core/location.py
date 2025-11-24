"""
Location dataclass and helpers.

A Location represents a logical space in the home: a room, floor, area, or virtual zone.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List


@dataclass
class Location:
    """
    A logical space in the home topology.

    Attributes:
        id: Unique identifier for this location
        name: Human-readable name
        parent_id: ID of parent location (None for root)
        ha_area_id: Optional link to Home Assistant Area
        entity_ids: Platform entity IDs mapped to this location
        modules: Per-module configuration blobs
    """

    id: str
    name: str
    parent_id: Optional[str] = None
    ha_area_id: Optional[str] = None
    entity_ids: List[str] = field(default_factory=list)
    modules: Dict[str, Dict] = field(default_factory=dict)
