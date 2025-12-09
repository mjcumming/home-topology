"""PresenceModule - Track WHO is in each location."""

import logging
from datetime import datetime, UTC
from typing import Optional, List, Dict

from home_topology.modules.base import LocationModule
from home_topology.core.bus import Event, EventBus, EventFilter
from home_topology.core.manager import LocationManager

from .models import Person, PresenceChange

logger = logging.getLogger(__name__)


class PresenceModule(LocationModule):
    """
    Presence tracking module.

    Tracks identified entities (people, pets, objects) and their current locations.

    Features:
    - Person registry (separate from Location topology)
    - Device tracker management (add/remove trackers dynamically)
    - Location tracking (where is each person)
    - Presence events (person entered/left location)

    Events Emitted:
    - presence.changed: When a person's location changes

    Events Consumed:
    - sensor.state_changed: Device tracker updates

    Note: This module is platform-agnostic. Integration layer maps
    platform-specific Person entities to this generic tracking system.
    """

    def __init__(self) -> None:
        self._bus: Optional[EventBus] = None
        self._loc_manager: Optional[LocationManager] = None
        self._people: Dict[str, Person] = {}  # person_id → Person

    @property
    def id(self) -> str:
        return "presence"

    @property
    def CURRENT_CONFIG_VERSION(self) -> int:
        return 1

    def attach(self, bus: EventBus, loc_manager: LocationManager) -> None:
        """Attach to kernel components."""
        self._bus = bus
        self._loc_manager = loc_manager

        # Subscribe to device tracker state changes
        bus.subscribe(
            handler=self._on_state_changed,
            event_filter=EventFilter(event_type="sensor.state_changed"),
        )

        logger.info("PresenceModule attached to kernel")

    def default_config(self) -> Dict:
        """Return default configuration for a location."""
        return {
            "version": self.CURRENT_CONFIG_VERSION,
            "enabled": True,
        }

    def location_config_schema(self) -> Dict:
        """Return JSON schema for location configuration."""
        return {
            "type": "object",
            "properties": {
                "version": {"type": "integer", "default": 1},
                "enabled": {"type": "boolean", "default": True},
            },
        }

    def migrate_config(self, config: Dict) -> Dict:
        """Migrate configuration from older versions."""
        version = config.get("version", 1)
        if version == self.CURRENT_CONFIG_VERSION:
            return config

        # No migrations yet (v1 is first version)
        config["version"] = self.CURRENT_CONFIG_VERSION
        return config

    def on_location_config_changed(self, location_id: str, config: Dict) -> None:
        """Handle location configuration changes."""
        # Presence module doesn't need per-location config currently
        pass

    # Person Management

    def create_person(
        self,
        id: str,
        name: str,
        device_trackers: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        picture: Optional[str] = None,
    ) -> Person:
        """
        Create a new person to track.

        Args:
            id: Unique identifier
            name: Display name
            device_trackers: List of device tracker entity IDs
            user_id: Optional platform user account ID
            picture: Optional avatar image path

        Returns:
            Created Person object

        Raises:
            ValueError: If person ID already exists
        """
        if id in self._people:
            raise ValueError(f"Person '{id}' already exists")

        person = Person(
            id=id,
            name=name,
            device_trackers=device_trackers or [],
            user_id=user_id,
            picture=picture,
        )

        self._people[id] = person
        logger.info(f"Created person: {id} ({name})")

        return person

    def delete_person(self, person_id: str) -> None:
        """
        Remove a person from tracking.

        Args:
            person_id: ID of person to delete

        Raises:
            ValueError: If person doesn't exist
        """
        if person_id not in self._people:
            raise ValueError(f"Person '{person_id}' not found")

        del self._people[person_id]
        logger.info(f"Deleted person: {person_id}")

    def get_person(self, person_id: str) -> Optional[Person]:
        """
        Get a person by ID.

        Args:
            person_id: Person ID

        Returns:
            Person object or None if not found
        """
        return self._people.get(person_id)

    def all_people(self) -> List[Person]:
        """
        Get all tracked people.

        Returns:
            List of all Person objects
        """
        return list(self._people.values())

    # Device Tracker Management

    def add_device_tracker(
        self, person_id: str, device_tracker: str, priority: Optional[int] = None
    ) -> None:
        """
        Add a device tracker to a person.

        Args:
            person_id: Person ID
            device_tracker: Device tracker entity ID
            priority: Optional priority (lower = higher priority)

        Raises:
            ValueError: If person doesn't exist
        """
        person = self._people.get(person_id)
        if not person:
            raise ValueError(f"Person '{person_id}' not found")

        if device_tracker not in person.device_trackers:
            person.device_trackers.append(device_tracker)
            logger.debug(f"Added tracker {device_tracker} to person {person_id}")

        if priority is not None:
            person.tracker_priority[device_tracker] = priority

        # Set as primary if it's the only tracker
        if len(person.device_trackers) == 1:
            person.primary_tracker = device_tracker

    def remove_device_tracker(self, person_id: str, device_tracker: str) -> None:
        """
        Remove a device tracker from a person.

        Args:
            person_id: Person ID
            device_tracker: Device tracker entity ID

        Raises:
            ValueError: If person doesn't exist
        """
        person = self._people.get(person_id)
        if not person:
            raise ValueError(f"Person '{person_id}' not found")

        if device_tracker in person.device_trackers:
            person.device_trackers.remove(device_tracker)
            logger.debug(f"Removed tracker {device_tracker} from person {person_id}")

        if device_tracker in person.tracker_priority:
            del person.tracker_priority[device_tracker]

        # Update primary if removed
        if person.primary_tracker == device_tracker:
            person.primary_tracker = person.device_trackers[0] if person.device_trackers else None

    # Location Queries

    def get_people_in_location(self, location_id: str) -> List[Person]:
        """
        Get all people currently in a location.

        Args:
            location_id: Location ID

        Returns:
            List of Person objects in that location
        """
        return [
            person for person in self._people.values() if person.current_location_id == location_id
        ]

    def get_person_location(self, person_id: str) -> Optional[str]:
        """
        Get current location of a person.

        Args:
            person_id: Person ID

        Returns:
            Location ID or None if person not found or location unknown
        """
        person = self._people.get(person_id)
        return person.current_location_id if person else None

    def move_person(
        self, person_id: str, to_location_id: Optional[str], source_tracker: Optional[str] = None
    ) -> None:
        """
        Move person to a new location.

        Args:
            person_id: Person ID
            to_location_id: Destination location ID (None = away/unknown)
            source_tracker: Which tracker triggered this (for logging)

        Raises:
            ValueError: If person doesn't exist or location doesn't exist
        """
        person = self._people.get(person_id)
        if not person:
            raise ValueError(f"Person '{person_id}' not found")

        # Validate location exists (unless going away)
        if to_location_id:
            if not self._loc_manager:
                raise RuntimeError("PresenceModule not attached to LocationManager")
            if not self._loc_manager.get_location(to_location_id):
                raise ValueError(f"Location '{to_location_id}' not found")

        # Check if actually changed
        if person.current_location_id == to_location_id:
            return  # No change

        old_location = person.current_location_id
        person.current_location_id = to_location_id

        logger.info(
            f"Person {person_id} moved: {old_location or 'away'} → {to_location_id or 'away'}"
        )

        # Emit presence event
        if self._bus:
            change = PresenceChange(
                person_id=person.id,
                person_name=person.name,
                from_location=old_location,
                to_location=to_location_id,
                source_tracker=source_tracker,
                timestamp=datetime.now(UTC),
            )

            self._bus.publish(
                Event(
                    type="presence.changed",
                    source=self.id,
                    location_id=to_location_id,
                    payload={
                        "person_id": change.person_id,
                        "person_name": change.person_name,
                        "from_location": change.from_location,
                        "to_location": change.to_location,
                        "source_tracker": change.source_tracker,
                        "timestamp": change.timestamp.isoformat(),
                        # Helper fields for common queries
                        "person_entered": person.id if to_location_id else None,
                        "person_left": person.id if not to_location_id else None,
                        "people_in_location": (
                            [p.id for p in self.get_people_in_location(to_location_id)]
                            if to_location_id
                            else []
                        ),
                    },
                )
            )

    # Event Handling

    def _on_state_changed(self, event: Event) -> None:
        """Handle device tracker state changes."""
        entity_id = event.entity_id
        if not entity_id:
            return

        # Find which person owns this tracker
        person = self._find_person_for_tracker(entity_id)
        if not person:
            return  # Not a tracked device

        # Determine location from tracker state
        new_location = self._determine_location_from_state(
            entity_id, event.payload.get("new_state")
        )

        # Move person if location changed
        if person.current_location_id != new_location:
            self.move_person(person.id, new_location, source_tracker=entity_id)

    def _find_person_for_tracker(self, tracker_id: str) -> Optional[Person]:
        """Find which person owns a device tracker."""
        for person in self._people.values():
            if tracker_id in person.device_trackers:
                return person
        return None

    def _determine_location_from_state(self, entity_id: str, state: Optional[str]) -> Optional[str]:
        """
        Determine location from device tracker state.

        This is a simplified implementation. Real integration should:
        1. Check if tracker is in a zone
        2. Map zone → location
        3. Handle "home", "away", "not_home" states

        Args:
            entity_id: Device tracker entity ID
            state: Current state of tracker

        Returns:
            Location ID or None if away/unknown
        """
        if not state:
            return None

        # Check if entity is mapped to a location
        if self._loc_manager:
            location_id = self._loc_manager.get_entity_location(entity_id)
            if location_id:
                return location_id

        # TODO: Integration layer should map zones → locations
        # For now, return None (away/unknown)
        return None

    # State Persistence

    def dump_state(self) -> Dict:
        """
        Dump current state for persistence.

        Returns:
            State dictionary
        """
        return {
            "version": 1,
            "people": {
                person_id: {
                    "id": person.id,
                    "name": person.name,
                    "current_location_id": person.current_location_id,
                    "device_trackers": person.device_trackers,
                    "user_id": person.user_id,
                    "picture": person.picture,
                    "primary_tracker": person.primary_tracker,
                    "tracker_priority": person.tracker_priority,
                }
                for person_id, person in self._people.items()
            },
        }

    def restore_state(self, state: Dict) -> None:
        """
        Restore state from persistence.

        Args:
            state: State dictionary from dump_state()
        """
        version = state.get("version", 1)
        if version != 1:
            logger.warning(f"Unknown state version {version}, resetting")
            return

        people_data = state.get("people", {})

        for person_id, person_data in people_data.items():
            person = Person(
                id=person_data["id"],
                name=person_data["name"],
                current_location_id=person_data.get("current_location_id"),
                device_trackers=person_data.get("device_trackers", []),
                user_id=person_data.get("user_id"),
                picture=person_data.get("picture"),
                primary_tracker=person_data.get("primary_tracker"),
                tracker_priority=person_data.get("tracker_priority", {}),
            )
            self._people[person_id] = person

        logger.info(f"Restored {len(self._people)} people from state")
