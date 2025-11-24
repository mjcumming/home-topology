"""
LocationManager for topology and configuration management.

The LocationManager owns the topology and config, not the behavior.
"""

from typing import Dict, List, Optional, Set
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
    
    def __init__(self):
        """Initialize an empty location manager."""
        self._locations: Dict[str, Location] = {}
        self._entity_to_location: Dict[str, str] = {}
    
    def create_location(
        self,
        id: str,
        name: str,
        parent_id: Optional[str] = None,
        ha_area_id: Optional[str] = None,
    ) -> Location:
        """
        Create a new location in the topology.
        
        Args:
            id: Unique identifier
            name: Human-readable name
            parent_id: Parent location ID (None for root)
            ha_area_id: Optional Home Assistant area ID
            
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
            ha_area_id=ha_area_id,
        )
        
        self._locations[id] = location
        logger.info(f"Created location: {id} ({name})")
        
        return location
    
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
        return [
            loc for loc in self._locations.values()
            if loc.parent_id == location_id
        ]
    
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

