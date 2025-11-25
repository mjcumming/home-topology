"""Data models for the occupancy module.

This module defines the core data structures used throughout the occupancy system.
All state classes are frozen (immutable) to support functional programming.

Licensed under MIT License
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import FrozenSet


class EventType(Enum):
    """The mechanical behavior of an occupancy event.

    Occupancy Signals (sent by integrations):
        TRIGGER: Activity detected → occupied + timer
        HOLD: Presence detected → occupied indefinitely
        RELEASE: Presence cleared → trailing timer starts
        VACATE: Force vacant immediately

    State Control:
        LOCK: Add source to locked_by set (freeze state)
        UNLOCK: Remove source from locked_by set
        UNLOCK_ALL: Clear all locks (force unlock)
    """

    # Occupancy signals
    TRIGGER = "trigger"  # Activity detected → occupied + timer
    HOLD = "hold"  # Presence detected → occupied indefinitely
    RELEASE = "release"  # Presence cleared → trailing timer starts
    VACATE = "vacate"  # Force vacant immediately

    # State control
    LOCK = "lock"  # Add source to locked_by
    UNLOCK = "unlock"  # Remove source from locked_by
    UNLOCK_ALL = "unlock_all"  # Clear all locks


class OccupancyStrategy(Enum):
    """Occupancy strategy for a location."""

    INDEPENDENT = "independent"
    FOLLOW_PARENT = "follow_parent"


@dataclass(frozen=True)
class LocationConfig:
    """Configuration for a location.

    Attributes:
        id: Unique identifier.
        parent_id: Optional container location ID.
        occupancy_strategy: Strategy logic.
        contributes_to_parent: If False, occupancy stops here.
        default_timeout: Seconds for TRIGGER events (default: 300).
        hold_release_timeout: Trailing seconds after RELEASE (default: 120).
    """

    id: str
    parent_id: str | None = None
    occupancy_strategy: OccupancyStrategy = OccupancyStrategy.INDEPENDENT
    contributes_to_parent: bool = True
    default_timeout: int = 300  # 5 minutes for TRIGGER events
    hold_release_timeout: int = 120  # 2 minutes after RELEASE


@dataclass(frozen=True)
class LocationRuntimeState:
    """Runtime state for a location (Immutable).

    Attributes:
        is_occupied: Whether the location is currently occupied.
        occupied_until: Timer expiration (None = indefinite hold).
        active_occupants: Identity tracking (optional).
        active_holds: Source IDs with active holds.
        locked_by: Set of source IDs that have locked this location.
                   Location is locked when this set is non-empty.
    """

    is_occupied: bool = False
    occupied_until: datetime | None = None
    active_occupants: FrozenSet[str] = field(default_factory=frozenset)
    active_holds: FrozenSet[str] = field(default_factory=frozenset)
    locked_by: FrozenSet[str] = field(default_factory=frozenset)

    @property
    def is_locked(self) -> bool:
        """Check if this location is locked (frozen)."""
        return len(self.locked_by) > 0


@dataclass(frozen=True)
class OccupancyEvent:
    """An occupancy event sent by the integration layer.

    Attributes:
        location_id: Target location.
        event_type: The event type (TRIGGER, HOLD, RELEASE, VACATE, LOCK, UNLOCK, UNLOCK_ALL).
        source_id: Unique device/source ID (e.g. "binary_sensor.kitchen_motion").
        timestamp: When the event occurred.
        timeout: Optional timeout override in seconds (uses location default if None).
        occupant_id: Optional identity tracking.
    """

    location_id: str
    event_type: EventType
    source_id: str
    timestamp: datetime
    timeout: int | None = None  # Seconds, uses location default if None
    occupant_id: str | None = None


@dataclass(frozen=True)
class StateTransition:
    """A record of a state change for debugging."""

    location_id: str
    previous_state: LocationRuntimeState
    new_state: LocationRuntimeState
    reason: str


@dataclass(frozen=True)
class EngineResult:
    """Instructions for the Host Application."""

    next_expiration: datetime | None
    transitions: list[StateTransition] = field(default_factory=list)
