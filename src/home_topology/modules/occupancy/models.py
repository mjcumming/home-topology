"""Data models for the occupancy module (v3.0)."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import FrozenSet

# Stable reason patterns emitted by the occupancy engine.
# - event:<event_type>
# - propagation:child:<child_location_id>
# - propagation:parent
# - timeout
REASON_EVENT_PREFIX = "event:"
REASON_PROPAGATION_CHILD_PREFIX = "propagation:child:"
REASON_PROPAGATION_PARENT = "propagation:parent"
REASON_TIMEOUT = "timeout"


class EventType(Enum):
    """The type of occupancy signal."""

    # Events (from device mappings)
    TRIGGER = "trigger"  # Source contributes occupancy (timed or indefinite)
    CLEAR = "clear"  # Source stops contributing (immediate or trailing)

    # Commands (from automations/UI)
    VACATE = "vacate"  # Force vacant immediately
    LOCK = "lock"  # Add source to locked_by
    UNLOCK = "unlock"  # Remove source from locked_by
    UNLOCK_ALL = "unlock_all"  # Clear all locks


class OccupancyStrategy(Enum):
    """Occupancy strategy for a location."""

    INDEPENDENT = "independent"
    FOLLOW_PARENT = "follow_parent"


@dataclass(frozen=True)
class LocationConfig:
    """Configuration for a location."""

    id: str
    parent_id: str | None = None
    occupancy_strategy: OccupancyStrategy = OccupancyStrategy.INDEPENDENT
    contributes_to_parent: bool = True
    default_timeout: int = 300  # 5 minutes for TRIGGER events
    default_trailing_timeout: int = 120  # 2 minutes for CLEAR events


@dataclass(frozen=True)
class SourceContribution:
    """A source's contribution to occupancy."""

    source_id: str
    expires_at: datetime | None  # None = indefinite


@dataclass(frozen=True)
class SuspendedContribution:
    """A contribution suspended while locked."""

    source_id: str
    remaining: timedelta | None  # None = indefinite


@dataclass(frozen=True)
class LocationRuntimeState:
    """Runtime state for a location (immutable)."""

    is_occupied: bool = False
    contributions: FrozenSet[SourceContribution] = field(default_factory=frozenset)
    suspended_contributions: FrozenSet[SuspendedContribution] = field(default_factory=frozenset)
    locked_by: FrozenSet[str] = field(default_factory=frozenset)

    @property
    def is_locked(self) -> bool:
        """Check if this location is locked (frozen)."""
        return len(self.locked_by) > 0


@dataclass(frozen=True)
class OccupancyEvent:
    """An occupancy event for internal engine processing."""

    location_id: str
    event_type: EventType
    source_id: str
    timestamp: datetime
    timeout: int | None = None  # Seconds; None = indefinite for TRIGGER
    timeout_set: bool = False  # Distinguish explicit None from omitted timeout


@dataclass(frozen=True)
class StateTransition:
    """A record of a state change for debugging."""

    location_id: str
    previous_state: LocationRuntimeState
    new_state: LocationRuntimeState
    reason: str


@dataclass(frozen=True)
class EngineResult:
    """Instructions for the host application."""

    next_expiration: datetime | None
    transitions: list[StateTransition] = field(default_factory=list)
