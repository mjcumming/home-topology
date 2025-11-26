"""
Event Bus implementation for location-aware event routing.

The Event Bus is a simple, synchronous dispatcher for domain events.
"""

from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Optional, Dict, Any, Callable, List

from home_topology.core.manager import LocationManager
import logging

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    """Get current UTC time (for default factory)."""
    return datetime.now(UTC)


@dataclass
class Event:
    """
    A domain event in the home topology system.

    Attributes:
        type: Event type (e.g., "sensor.state_changed", "occupancy.changed")
        source: Event source (e.g., "ha", "occupancy", "actions")
        location_id: Optional location ID this event relates to
        entity_id: Optional entity ID this event relates to
        payload: Event-specific data
        timestamp: When the event occurred
    """

    type: str
    source: str
    location_id: Optional[str] = None
    entity_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=_utc_now)


class EventFilter:
    """
    Filter for event subscriptions.

    Allows subscribers to filter events by type, location, ancestors, or descendants.
    """

    def __init__(
        self,
        event_type: Optional[str] = None,
        location_id: Optional[str] = None,
        include_ancestors: bool = False,
        include_descendants: bool = False,
    ):
        """
        Initialize an event filter.

        Args:
            event_type: Filter by event type (None = all types)
            location_id: Filter by location ID (None = all locations)
            include_ancestors: Include events from ancestor locations
            include_descendants: Include events from descendant locations
        """
        self.event_type = event_type
        self.location_id = location_id
        self.include_ancestors = include_ancestors
        self.include_descendants = include_descendants

    def matches(self, event: Event, location_manager: Optional[LocationManager] = None) -> bool:
        """
        Check if an event matches this filter.

        Args:
            event: The event to check
            location_manager: Optional LocationManager for ancestor/descendant queries

        Returns:
            True if the event matches the filter
        """
        # Check event type
        if self.event_type and event.type != self.event_type:
            return False

        # Check location
        if self.location_id and event.location_id:
            if event.location_id == self.location_id:
                return True

            # Check ancestors/descendants if location_manager provided
            if location_manager:
                if self.include_ancestors:
                    ancestors = location_manager.ancestors_of(event.location_id)
                    if self.location_id in [a.id for a in ancestors]:
                        return True

                if self.include_descendants:
                    descendants = location_manager.descendants_of(self.location_id)
                    if event.location_id in [d.id for d in descendants]:
                        return True

            return False

        return True


EventHandler = Callable[[Event], None]


class EventBus:
    """
    Simple, synchronous event bus for home topology events.

    Handlers are wrapped in try/except to prevent one bad module from crashing the kernel.
    """

    def __init__(self) -> None:
        """Initialize the event bus."""
        self._handlers: List[tuple[EventFilter, EventHandler]] = []
        self._location_manager: Optional[LocationManager] = None

    def set_location_manager(self, location_manager: LocationManager) -> None:
        """
        Set the LocationManager for ancestor/descendant filtering.

        Args:
            location_manager: The LocationManager instance
        """
        self._location_manager = location_manager

    def subscribe(
        self,
        handler: EventHandler,
        event_filter: Optional[EventFilter] = None,
    ) -> None:
        """
        Subscribe to events.

        Args:
            handler: Callable that receives Event objects
            event_filter: Optional filter for events (None = receive all events)
        """
        if event_filter is None:
            event_filter = EventFilter()

        self._handlers.append((event_filter, handler))
        logger.debug(f"Subscribed handler {handler.__name__} with filter {event_filter}")

    def publish(self, event: Event) -> None:
        """
        Publish an event to all matching subscribers.

        Handlers are called synchronously and wrapped in try/except.

        Args:
            event: The event to publish
        """
        logger.debug(f"Publishing event: {event.type} from {event.source}")

        for event_filter, handler in self._handlers:
            if event_filter.matches(event, self._location_manager):
                try:
                    handler(event)
                except Exception as e:
                    logger.error(
                        f"Error in event handler {handler.__name__} "
                        f"for event {event.type}: {e}",
                        exc_info=True,
                    )

    def unsubscribe(self, handler: EventHandler) -> None:
        """
        Unsubscribe a handler from all events.

        Args:
            handler: The handler to unsubscribe
        """
        self._handlers = [(f, h) for f, h in self._handlers if h != handler]
        logger.debug(f"Unsubscribed handler {handler.__name__}")
