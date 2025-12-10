"""
LocationManager for topology and configuration management.

The LocationManager owns the topology and config, not the behavior.
"""

from typing import Dict, List, Optional
import logging

from home_topology.core.location import Location

logger = logging.getLogger(__name__)


class LocationManager:
    """
    Manages the location topology and per-location module configuration.

    Responsibilities:
    - Store the location tree
    - Provide graph queries (parent, children, ancestors, descendants)
    - Maintain entity → location mappings
    - Store per-location module config

    Does NOT implement occupancy, energy, or actions logic.
    """

    def __init__(self) -> None:
        """Initialize an empty location manager."""
        self._locations: Dict[str, Location] = {}
        self._entity_to_location: Dict[str, str] = {}

    def create_location(
        self,
        id: str,
        name: str,
        parent_id: Optional[str] = None,
        is_explicit_root: bool = False,
        ha_area_id: Optional[str] = None,
        aliases: Optional[List[str]] = None,
    ) -> Location:
        """
        Create a new location in the topology.

        Args:
            id: Unique identifier
            name: Human-readable name
            parent_id: Parent location ID (None for root/unassigned)
            is_explicit_root: True if intentionally top-level (e.g., "House").
                When parent_id is None:
                - is_explicit_root=True: Shows as root in hierarchy
                - is_explicit_root=False: Shows in Inbox (unassigned)
            ha_area_id: Optional Home Assistant area ID
            aliases: Alternative names for this location (for voice assistants)

        Returns:
            The created Location

        Raises:
            ValueError: If location ID already exists or parent doesn't exist
        """
        if id in self._locations:
            raise ValueError(f"Location with id '{id}' already exists")

        if parent_id and parent_id not in self._locations:
            raise ValueError(f"Parent location '{parent_id}' does not exist")

        location = Location(
            id=id,
            name=name,
            parent_id=parent_id,
            is_explicit_root=is_explicit_root,
            ha_area_id=ha_area_id,
            aliases=aliases or [],
        )

        self._locations[id] = location
        logger.info(f"Created location: {id} ({name})")

        return location

    def get_root_locations(self) -> List[Location]:
        """
        Get all intentional root locations.

        These are locations with parent_id=None AND is_explicit_root=True.
        Used to display the top-level hierarchy.

        Returns:
            List of root Locations
        """
        return [
            loc
            for loc in self._locations.values()
            if loc.parent_id is None and loc.is_explicit_root
        ]

    def get_unassigned_locations(self) -> List[Location]:
        """
        Get all unassigned locations (Inbox).

        These are locations with parent_id=None AND is_explicit_root=False.
        Typically discovered from the platform (HA areas) that need organization.

        Returns:
            List of unassigned Locations
        """
        return [
            loc
            for loc in self._locations.values()
            if loc.parent_id is None and not loc.is_explicit_root
        ]

    def set_as_root(self, location_id: str) -> None:
        """
        Mark a location as an explicit root.

        Use this to promote an unassigned location to be a top-level root.

        Args:
            location_id: The location ID

        Raises:
            ValueError: If location doesn't exist or has a parent
        """
        location = self.get_location(location_id)
        if not location:
            raise ValueError(f"Location '{location_id}' does not exist")
        if location.parent_id:
            raise ValueError(f"Location '{location_id}' has a parent; cannot be root")

        location.is_explicit_root = True
        logger.info(f"Marked location as root: {location_id}")

    def get_location(self, location_id: str) -> Optional[Location]:
        """
        Get a location by ID.

        Args:
            location_id: The location ID

        Returns:
            The Location or None if not found
        """
        return self._locations.get(location_id)

    def all_locations(self) -> List[Location]:
        """
        Get all locations.

        Returns:
            List of all locations
        """
        return list(self._locations.values())

    def parent_of(self, location_id: str) -> Optional[Location]:
        """
        Get the parent of a location.

        Args:
            location_id: The location ID

        Returns:
            Parent Location or None if no parent or location not found
        """
        location = self.get_location(location_id)
        if not location or not location.parent_id:
            return None
        return self.get_location(location.parent_id)

    def children_of(self, location_id: str) -> List[Location]:
        """
        Get direct children of a location.

        Args:
            location_id: The location ID

        Returns:
            List of child Locations
        """
        return [loc for loc in self._locations.values() if loc.parent_id == location_id]

    def ancestors_of(self, location_id: str) -> List[Location]:
        """
        Get all ancestors of a location (parent, grandparent, etc.).

        Args:
            location_id: The location ID

        Returns:
            List of ancestor Locations, ordered from parent to root
        """
        ancestors = []
        current = self.parent_of(location_id)

        while current:
            ancestors.append(current)
            current = self.parent_of(current.id)

        return ancestors

    def descendants_of(self, location_id: str) -> List[Location]:
        """
        Get all descendants of a location (children, grandchildren, etc.).

        Args:
            location_id: The location ID

        Returns:
            List of descendant Locations
        """
        descendants = []
        to_visit = self.children_of(location_id)

        while to_visit:
            current = to_visit.pop(0)
            descendants.append(current)
            to_visit.extend(self.children_of(current.id))

        return descendants

    def add_entity_to_location(self, entity_id: str, location_id: str) -> None:
        """
        Map an entity to a location.

        Args:
            entity_id: The entity ID
            location_id: The location ID

        Raises:
            ValueError: If location doesn't exist
        """
        location = self.get_location(location_id)
        if not location:
            raise ValueError(f"Location '{location_id}' does not exist")

        # Remove from previous location if mapped
        if entity_id in self._entity_to_location:
            old_location_id = self._entity_to_location[entity_id]
            old_location = self.get_location(old_location_id)
            if old_location and entity_id in old_location.entity_ids:
                old_location.entity_ids.remove(entity_id)

        # Add to new location
        if entity_id not in location.entity_ids:
            location.entity_ids.append(entity_id)

        self._entity_to_location[entity_id] = location_id
        logger.debug(f"Mapped entity {entity_id} to location {location_id}")

    def get_entity_location(self, entity_id: str) -> Optional[str]:
        """
        Get the location ID for an entity.

        Args:
            entity_id: The entity ID

        Returns:
            Location ID or None if not mapped
        """
        return self._entity_to_location.get(entity_id)

    def set_module_config(
        self,
        location_id: str,
        module_id: str,
        config: Dict,
    ) -> None:
        """
        Set module configuration for a location.

        Args:
            location_id: The location ID
            module_id: The module ID
            config: Module configuration dict

        Raises:
            ValueError: If location doesn't exist
        """
        location = self.get_location(location_id)
        if not location:
            raise ValueError(f"Location '{location_id}' does not exist")

        location.modules[module_id] = config
        logger.debug(f"Set config for module '{module_id}' on location '{location_id}'")

    def get_module_config(
        self,
        location_id: str,
        module_id: str,
    ) -> Optional[Dict]:
        """
        Get module configuration for a location.

        Args:
            location_id: The location ID
            module_id: The module ID

        Returns:
            Module configuration dict or None if not set
        """
        location = self.get_location(location_id)
        if not location:
            return None

        return location.modules.get(module_id)

    # Alias Management Methods

    def add_alias(self, location_id: str, alias: str) -> None:
        """
        Add a single alias to a location.

        Duplicate aliases are ignored.

        Args:
            location_id: The location ID
            alias: The alias to add

        Raises:
            ValueError: If location doesn't exist
        """
        location = self.get_location(location_id)
        if not location:
            raise ValueError(f"Location '{location_id}' does not exist")

        if alias and alias not in location.aliases:
            location.aliases.append(alias)
            logger.debug(f"Added alias '{alias}' to location '{location_id}'")

    def add_aliases(self, location_id: str, aliases: List[str]) -> None:
        """
        Add multiple aliases to a location.

        Duplicate aliases are ignored.

        Args:
            location_id: The location ID
            aliases: List of aliases to add

        Raises:
            ValueError: If location doesn't exist
        """
        for alias in aliases:
            self.add_alias(location_id, alias)

    def remove_alias(self, location_id: str, alias: str) -> None:
        """
        Remove an alias from a location.

        If the alias doesn't exist, this is a no-op.

        Args:
            location_id: The location ID
            alias: The alias to remove

        Raises:
            ValueError: If location doesn't exist
        """
        location = self.get_location(location_id)
        if not location:
            raise ValueError(f"Location '{location_id}' does not exist")

        if alias in location.aliases:
            location.aliases.remove(alias)
            logger.debug(f"Removed alias '{alias}' from location '{location_id}'")

    def set_aliases(self, location_id: str, aliases: List[str]) -> None:
        """
        Replace all aliases for a location.

        Args:
            location_id: The location ID
            aliases: New list of aliases (replaces existing)

        Raises:
            ValueError: If location doesn't exist
        """
        location = self.get_location(location_id)
        if not location:
            raise ValueError(f"Location '{location_id}' does not exist")

        location.aliases = aliases.copy()
        logger.debug(f"Set aliases for location '{location_id}': {aliases}")

    def find_by_alias(self, alias: str) -> Optional[Location]:
        """
        Find a location by alias.

        Args:
            alias: The alias to search for

        Returns:
            First matching Location or None if not found
        """
        for location in self._locations.values():
            if alias in location.aliases:
                return location
        return None

    def get_location_by_name(self, name: str) -> Optional[Location]:
        """
        Find a location by name (exact match, case-sensitive).

        Args:
            name: The location name to search for

        Returns:
            First matching Location or None if not found
        """
        for location in self._locations.values():
            if location.name == name:
                return location
        return None

    # Batch Entity Operations

    def add_entities_to_location(self, entity_ids: List[str], location_id: str) -> None:
        """
        Map multiple entities to a location.

        This is equivalent to calling add_entity_to_location for each entity,
        but more efficient.

        Args:
            entity_ids: List of entity IDs to add
            location_id: The location ID

        Raises:
            ValueError: If location doesn't exist
        """
        location = self.get_location(location_id)
        if not location:
            raise ValueError(f"Location '{location_id}' does not exist")

        for entity_id in entity_ids:
            self.add_entity_to_location(entity_id, location_id)

    def remove_entities_from_location(self, entity_ids: List[str]) -> None:
        """
        Remove multiple entities from their current locations.

        For each entity, removes it from whichever location it's currently in.
        If an entity isn't mapped to any location, this is a no-op for that entity.

        Args:
            entity_ids: List of entity IDs to remove
        """
        for entity_id in entity_ids:
            location_id = self._entity_to_location.get(entity_id)
            if location_id:
                location = self.get_location(location_id)
                if location and entity_id in location.entity_ids:
                    location.entity_ids.remove(entity_id)
                del self._entity_to_location[entity_id]
                logger.debug(f"Removed entity {entity_id} from location {location_id}")

    def move_entities(self, entity_ids: List[str], to_location_id: str) -> None:
        """
        Move multiple entities from their current locations to a new location.

        This is equivalent to calling add_entity_to_location for each entity
        (which automatically removes from old location).

        Args:
            entity_ids: List of entity IDs to move
            to_location_id: Destination location ID

        Raises:
            ValueError: If destination location doesn't exist
        """
        to_location = self.get_location(to_location_id)
        if not to_location:
            raise ValueError(f"Location '{to_location_id}' does not exist")

        for entity_id in entity_ids:
            self.add_entity_to_location(entity_id, to_location_id)

    def update_location(
        self,
        location_id: str,
        name: Optional[str] = None,
        parent_id: Optional[str] = None,
        is_explicit_root: Optional[bool] = None,
        ha_area_id: Optional[str] = None,
        aliases: Optional[List[str]] = None,
    ) -> Location:
        """
        Update a location's properties.

        Args:
            location_id: Location ID to update
            name: New name (None to keep current)
            parent_id: New parent ID (None to keep current, use empty string to clear)
            is_explicit_root: New explicit root flag (None to keep current)
            ha_area_id: New HA area ID (None to keep current, use empty string to clear)
            aliases: New aliases list (None to keep current)

        Returns:
            The updated Location

        Raises:
            ValueError: If location doesn't exist
            ValueError: If new parent doesn't exist
            ValueError: If reparenting would create a cycle
        """
        location = self.get_location(location_id)
        if not location:
            raise ValueError(f"Location '{location_id}' does not exist")

        # Update name
        if name is not None:
            location.name = name
            logger.debug(f"Updated name for {location_id}: {name}")

        # Update parent
        if parent_id is not None:
            # Empty string means clear parent
            if parent_id == "":
                parent_id = None

            # Validate new parent exists (if provided)
            if parent_id and parent_id not in self._locations:
                raise ValueError(f"Parent location '{parent_id}' does not exist")

            # Check for cycles (new parent is a descendant)
            if parent_id:
                if parent_id == location_id:
                    raise ValueError(f"Location cannot be its own parent")
                descendants = self.descendants_of(location_id)
                if any(d.id == parent_id for d in descendants):
                    raise ValueError(
                        f"Cannot set parent '{parent_id}': would create cycle "
                        f"(location is ancestor of new parent)"
                    )

            location.parent_id = parent_id
            logger.debug(f"Updated parent for {location_id}: {parent_id}")

        # Update explicit root flag
        if is_explicit_root is not None:
            location.is_explicit_root = is_explicit_root
            logger.debug(f"Updated is_explicit_root for {location_id}: {is_explicit_root}")

        # Update HA area ID
        if ha_area_id is not None:
            # Empty string means clear
            location.ha_area_id = ha_area_id if ha_area_id != "" else None
            logger.debug(f"Updated ha_area_id for {location_id}: {location.ha_area_id}")

        # Update aliases
        if aliases is not None:
            location.aliases = aliases.copy()
            logger.debug(f"Updated aliases for {location_id}: {aliases}")

        logger.info(f"Updated location: {location_id}")
        return location

    def delete_location(
        self,
        location_id: str,
        cascade: bool = False,
        orphan_children: bool = False,
    ) -> List[str]:
        """
        Delete a location from the topology.

        Args:
            location_id: Location ID to delete
            cascade: If True, delete all descendants first (recursive)
            orphan_children: If True, move direct children to Inbox (unassigned)
                Ignored if cascade=True

        Returns:
            List of deleted location IDs (for cascade mode)

        Raises:
            ValueError: If location doesn't exist
            ValueError: If location has children and neither cascade nor orphan_children is True
        """
        location = self.get_location(location_id)
        if not location:
            raise ValueError(f"Location '{location_id}' does not exist")

        deleted_ids = []
        children = self.children_of(location_id)

        # Handle children
        if children:
            if cascade:
                # Delete all descendants first (bottom-up)
                descendants = self.descendants_of(location_id)
                for desc in reversed(descendants):  # Children before parents
                    deleted_ids.extend(self._delete_location_internal(desc.id))
            elif orphan_children:
                # Move children to Inbox
                for child in children:
                    child.parent_id = None
                    child.is_explicit_root = False
                    logger.info(f"Orphaned child location: {child.id}")
            else:
                raise ValueError(
                    f"Cannot delete location '{location_id}': has {len(children)} children. "
                    f"Use cascade=True to delete descendants, or orphan_children=True to move children to Inbox."
                )

        # Delete the location itself
        deleted_ids.extend(self._delete_location_internal(location_id))

        return deleted_ids

    def _delete_location_internal(self, location_id: str) -> List[str]:
        """
        Internal method to delete a location (assumes no children).

        Returns:
            List containing the deleted location_id
        """
        location = self.get_location(location_id)
        if not location:
            return []

        # Remove all entity mappings
        for entity_id in location.entity_ids.copy():
            if self._entity_to_location.get(entity_id) == location_id:
                del self._entity_to_location[entity_id]
                logger.debug(f"Unmapped entity {entity_id} from deleted location {location_id}")

        # Delete location
        del self._locations[location_id]
        logger.info(f"Deleted location: {location_id} ({location.name})")

        return [location_id]
