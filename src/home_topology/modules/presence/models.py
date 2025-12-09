"""Data models for PresenceModule."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime


@dataclass
class Person:
    """
    Represents a tracked person with a current location.

    Attributes:
        id: Unique identifier (e.g., "mike")
        name: Display name (e.g., "Mike")
        current_location_id: Where the person currently is (None if unknown/away)
        device_trackers: Entity IDs of device trackers for this person
        user_id: Optional platform user account ID
        picture: Optional path to avatar image
        primary_tracker: Primary device tracker (most reliable)
        tracker_priority: Priority map for trackers (lower number = higher priority)
    """

    id: str
    name: str
    current_location_id: Optional[str] = None
    device_trackers: List[str] = field(default_factory=list)
    user_id: Optional[str] = None
    picture: Optional[str] = None
    primary_tracker: Optional[str] = None
    tracker_priority: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Set primary tracker if not specified."""
        if not self.primary_tracker and self.device_trackers:
            self.primary_tracker = self.device_trackers[0]


@dataclass
class PresenceChange:
    """
    Represents a person's location change.

    Attributes:
        person_id: ID of the person who moved
        person_name: Name of the person
        from_location: Previous location ID (None if entering system)
        to_location: New location ID (None if leaving system)
        source_tracker: Which device tracker triggered this change
        timestamp: When the change occurred
    """

    person_id: str
    person_name: str
    from_location: Optional[str]
    to_location: Optional[str]
    source_tracker: Optional[str]
    timestamp: datetime
