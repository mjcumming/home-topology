"""
Comprehensive tests for LocationManager with extensive logging.

These tests verify:
- Location creation and hierarchy management
- Entity-to-location mappings
- Module configuration storage and retrieval
- Graph queries (parent, children, ancestors, descendants)
- Error handling and edge cases
"""

import logging
import pytest
from home_topology import LocationManager

# Configure logging for verbose test output
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


class TestLocationManagerCreation:
    """Test suite for location creation."""

    def test_create_root_location(self):
        """Test creating a root location (no parent)."""
        logger.info("=" * 80)
        logger.info("TEST: Create root location")
        logger.info("=" * 80)

        mgr = LocationManager()
        logger.debug("Created LocationManager instance")

        logger.info("Creating root location: 'house'")
        house = mgr.create_location(id="house", name="My House")

        logger.info(f"✓ Created location: {house.id} - {house.name}")
        logger.debug(f"  parent_id: {house.parent_id}")
        logger.debug(f"  entity_ids: {house.entity_ids}")
        logger.debug(f"  modules: {house.modules}")

        assert house.id == "house"
        assert house.name == "My House"
        assert house.parent_id is None
        logger.info("✓ Root location created successfully")

    def test_create_child_location(self):
        """Test creating a child location."""
        logger.info("=" * 80)
        logger.info("TEST: Create child location")
        logger.info("=" * 80)

        mgr = LocationManager()
        logger.debug("Created LocationManager instance")

        logger.info("Step 1: Create root location 'house'")
        house = mgr.create_location(id="house", name="House")
        logger.info(f"✓ Created: {house.id}")

        logger.info("Step 2: Create child location 'main_floor'")
        main_floor = mgr.create_location(id="main_floor", name="Main Floor", parent_id="house")
        logger.info(f"✓ Created: {main_floor.id} (parent: {main_floor.parent_id})")

        assert main_floor.parent_id == "house"
        logger.info("✓ Child location created successfully with correct parent")

    def test_create_complex_hierarchy(self):
        """Test creating a multi-level hierarchy."""
        logger.info("=" * 80)
        logger.info("TEST: Create complex location hierarchy")
        logger.info("=" * 80)

        mgr = LocationManager()
        logger.info("Building hierarchy: house -> main_floor -> kitchen")

        # Level 0: Root
        logger.info("Level 0: Creating root 'house'")
        house = mgr.create_location(id="house", name="House")
        logger.debug(f"  Created: {house.id}")

        # Level 1: Floor
        logger.info("Level 1: Creating 'main_floor' under 'house'")
        main_floor = mgr.create_location(id="main_floor", name="Main Floor", parent_id="house")
        logger.debug(f"  Created: {main_floor.id} -> parent: {main_floor.parent_id}")

        # Level 2: Room
        logger.info("Level 2: Creating 'kitchen' under 'main_floor'")
        kitchen = mgr.create_location(id="kitchen", name="Kitchen", parent_id="main_floor")
        logger.debug(f"  Created: {kitchen.id} -> parent: {kitchen.parent_id}")

        logger.info("Verifying hierarchy...")
        all_locs = mgr.all_locations()
        logger.info(f"Total locations: {len(all_locs)}")
        for loc in all_locs:
            logger.debug(f"  - {loc.id} (parent: {loc.parent_id or 'None'})")

        assert len(all_locs) == 3
        logger.info("✓ Complex hierarchy created successfully")

    def test_duplicate_location_error(self):
        """Test that duplicate location IDs are rejected."""
        logger.info("=" * 80)
        logger.info("TEST: Duplicate location ID error handling")
        logger.info("=" * 80)

        mgr = LocationManager()

        logger.info("Step 1: Create location 'kitchen'")
        mgr.create_location(id="kitchen", name="Kitchen")
        logger.info("✓ First 'kitchen' created")

        logger.info("Step 2: Attempt to create duplicate 'kitchen'")
        try:
            mgr.create_location(id="kitchen", name="Another Kitchen")
            logger.error("✗ Expected ValueError but none was raised!")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            logger.info(f"✓ Correctly raised ValueError: {e}")
            assert "already exists" in str(e)

    def test_invalid_parent_error(self):
        """Test that invalid parent IDs are rejected."""
        logger.info("=" * 80)
        logger.info("TEST: Invalid parent ID error handling")
        logger.info("=" * 80)

        mgr = LocationManager()

        logger.info("Attempting to create location with non-existent parent")
        try:
            mgr.create_location(id="kitchen", name="Kitchen", parent_id="nonexistent")
            logger.error("✗ Expected ValueError but none was raised!")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            logger.info(f"✓ Correctly raised ValueError: {e}")
            assert "does not exist" in str(e)


class TestLocationManagerHierarchyQueries:
    """Test suite for hierarchy graph queries."""

    @pytest.fixture
    def simple_hierarchy(self):
        """Create a simple 3-level hierarchy for testing."""
        logger.info("Setting up simple hierarchy fixture")
        mgr = LocationManager()
        mgr.create_location(id="house", name="House")
        mgr.create_location(id="main_floor", name="Main Floor", parent_id="house")
        mgr.create_location(id="kitchen", name="Kitchen", parent_id="main_floor")
        logger.debug("Hierarchy: house -> main_floor -> kitchen")
        return mgr

    def test_parent_of(self, simple_hierarchy):
        """Test parent_of query."""
        logger.info("=" * 80)
        logger.info("TEST: parent_of() query")
        logger.info("=" * 80)

        mgr = simple_hierarchy

        logger.info("Query: parent_of('kitchen')")
        parent = mgr.parent_of("kitchen")
        logger.info(f"Result: {parent.id if parent else 'None'}")
        assert parent.id == "main_floor"
        logger.info("✓ Correct parent found")

        logger.info("Query: parent_of('main_floor')")
        parent = mgr.parent_of("main_floor")
        logger.info(f"Result: {parent.id if parent else 'None'}")
        assert parent.id == "house"
        logger.info("✓ Correct parent found")

        logger.info("Query: parent_of('house')")
        parent = mgr.parent_of("house")
        logger.info(f"Result: {parent.id if parent else 'None'}")
        assert parent is None
        logger.info("✓ Root has no parent")

    def test_children_of(self, simple_hierarchy):
        """Test children_of query."""
        logger.info("=" * 80)
        logger.info("TEST: children_of() query")
        logger.info("=" * 80)

        mgr = simple_hierarchy

        logger.info("Query: children_of('house')")
        children = mgr.children_of("house")
        logger.info(f"Found {len(children)} children")
        for child in children:
            logger.debug(f"  - {child.id}")
        assert len(children) == 1
        assert children[0].id == "main_floor"
        logger.info("✓ Correct children found")

        logger.info("Query: children_of('main_floor')")
        children = mgr.children_of("main_floor")
        logger.info(f"Found {len(children)} children")
        for child in children:
            logger.debug(f"  - {child.id}")
        assert len(children) == 1
        assert children[0].id == "kitchen"
        logger.info("✓ Correct children found")

        logger.info("Query: children_of('kitchen')")
        children = mgr.children_of("kitchen")
        logger.info(f"Found {len(children)} children")
        assert len(children) == 0
        logger.info("✓ Leaf node has no children")

    def test_ancestors_of(self, simple_hierarchy):
        """Test ancestors_of query."""
        logger.info("=" * 80)
        logger.info("TEST: ancestors_of() query")
        logger.info("=" * 80)

        mgr = simple_hierarchy

        logger.info("Query: ancestors_of('kitchen')")
        ancestors = mgr.ancestors_of("kitchen")
        logger.info(f"Found {len(ancestors)} ancestors")
        for i, ancestor in enumerate(ancestors):
            logger.debug(f"  {i}: {ancestor.id}")

        assert len(ancestors) == 2
        assert ancestors[0].id == "main_floor"  # Direct parent
        assert ancestors[1].id == "house"  # Grandparent
        logger.info("✓ All ancestors found in correct order (parent to root)")

    def test_descendants_of(self, simple_hierarchy):
        """Test descendants_of query."""
        logger.info("=" * 80)
        logger.info("TEST: descendants_of() query")
        logger.info("=" * 80)

        mgr = simple_hierarchy

        logger.info("Query: descendants_of('house')")
        descendants = mgr.descendants_of("house")
        logger.info(f"Found {len(descendants)} descendants")
        descendant_ids = {d.id for d in descendants}
        for desc_id in descendant_ids:
            logger.debug(f"  - {desc_id}")

        assert len(descendants) == 2
        assert "main_floor" in descendant_ids
        assert "kitchen" in descendant_ids
        logger.info("✓ All descendants found")


class TestLocationManagerEntityMapping:
    """Test suite for entity-to-location mapping."""

    def test_add_entity_to_location(self):
        """Test mapping entities to locations."""
        logger.info("=" * 80)
        logger.info("TEST: Add entity to location")
        logger.info("=" * 80)

        mgr = LocationManager()
        mgr.create_location(id="kitchen", name="Kitchen")
        logger.info("Created location: kitchen")

        logger.info("Adding entity: binary_sensor.kitchen_motion")
        mgr.add_entity_to_location("binary_sensor.kitchen_motion", "kitchen")
        logger.info("✓ Entity added")

        logger.info("Verifying entity mapping...")
        location_id = mgr.get_entity_location("binary_sensor.kitchen_motion")
        logger.info(f"Entity location: {location_id}")
        assert location_id == "kitchen"

        logger.info("Verifying entity appears in location's entity_ids...")
        kitchen = mgr.get_location("kitchen")
        logger.debug(f"Kitchen entity_ids: {kitchen.entity_ids}")
        assert "binary_sensor.kitchen_motion" in kitchen.entity_ids
        logger.info("✓ Entity successfully mapped to location")

    def test_move_entity_between_locations(self):
        """Test moving an entity from one location to another."""
        logger.info("=" * 80)
        logger.info("TEST: Move entity between locations")
        logger.info("=" * 80)

        mgr = LocationManager()
        mgr.create_location(id="kitchen", name="Kitchen")
        mgr.create_location(id="living_room", name="Living Room")
        logger.info("Created locations: kitchen, living_room")

        entity = "sensor.temp_sensor"

        logger.info(f"Step 1: Add {entity} to kitchen")
        mgr.add_entity_to_location(entity, "kitchen")
        logger.info(f"✓ {entity} -> kitchen")
        logger.debug(f"Kitchen entities: {mgr.get_location('kitchen').entity_ids}")

        logger.info(f"Step 2: Move {entity} to living_room")
        mgr.add_entity_to_location(entity, "living_room")
        logger.info(f"✓ {entity} -> living_room")

        logger.info("Verifying entity removed from kitchen...")
        kitchen = mgr.get_location("kitchen")
        logger.debug(f"Kitchen entities: {kitchen.entity_ids}")
        assert entity not in kitchen.entity_ids
        logger.info("✓ Entity removed from old location")

        logger.info("Verifying entity added to living_room...")
        living_room = mgr.get_location("living_room")
        logger.debug(f"Living room entities: {living_room.entity_ids}")
        assert entity in living_room.entity_ids
        logger.info("✓ Entity added to new location")

        logger.info("Verifying entity mapping updated...")
        location_id = mgr.get_entity_location(entity)
        logger.debug(f"Entity location: {location_id}")
        assert location_id == "living_room"
        logger.info("✓ Entity successfully moved")

    def test_add_entity_to_invalid_location(self):
        """Test that adding entity to invalid location raises error."""
        logger.info("=" * 80)
        logger.info("TEST: Add entity to invalid location")
        logger.info("=" * 80)

        mgr = LocationManager()

        logger.info("Attempting to add entity to non-existent location")
        try:
            mgr.add_entity_to_location("sensor.test", "nonexistent")
            logger.error("✗ Expected ValueError but none was raised!")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            logger.info(f"✓ Correctly raised ValueError: {e}")
            assert "does not exist" in str(e)


class TestLocationManagerModuleConfig:
    """Test suite for module configuration storage."""

    def test_set_and_get_module_config(self):
        """Test storing and retrieving module configuration."""
        logger.info("=" * 80)
        logger.info("TEST: Set and get module configuration")
        logger.info("=" * 80)

        mgr = LocationManager()
        mgr.create_location(id="kitchen", name="Kitchen")
        logger.info("Created location: kitchen")

        config = {
            "version": 1,
            "enabled": True,
            "timeouts": {
                "motion": 300,
                "presence": 600,
            },
        }

        logger.info("Setting module config for 'occupancy' on kitchen")
        logger.debug(f"Config: {config}")
        mgr.set_module_config("kitchen", "occupancy", config)
        logger.info("✓ Config stored")

        logger.info("Retrieving module config...")
        retrieved = mgr.get_module_config("kitchen", "occupancy")
        logger.debug(f"Retrieved: {retrieved}")

        assert retrieved == config
        assert retrieved["timeouts"]["motion"] == 300
        logger.info("✓ Config retrieved successfully")

    def test_multiple_module_configs(self):
        """Test storing multiple module configurations."""
        logger.info("=" * 80)
        logger.info("TEST: Multiple module configurations")
        logger.info("=" * 80)

        mgr = LocationManager()
        mgr.create_location(id="kitchen", name="Kitchen")
        logger.info("Created location: kitchen")

        logger.info("Setting config for 'occupancy' module")
        occupancy_config = {"enabled": True, "timeout": 300}
        mgr.set_module_config("kitchen", "occupancy", occupancy_config)
        logger.debug(f"Occupancy config: {occupancy_config}")

        logger.info("Setting config for 'energy' module")
        energy_config = {"track_power": True}
        mgr.set_module_config("kitchen", "energy", energy_config)
        logger.debug(f"Energy config: {energy_config}")

        logger.info("Verifying both configs are stored independently...")
        occ_retrieved = mgr.get_module_config("kitchen", "occupancy")
        energy_retrieved = mgr.get_module_config("kitchen", "energy")

        logger.debug(f"Occupancy retrieved: {occ_retrieved}")
        logger.debug(f"Energy retrieved: {energy_retrieved}")

        assert occ_retrieved == occupancy_config
        assert energy_retrieved == energy_config
        logger.info("✓ Multiple module configs stored successfully")

    def test_get_nonexistent_module_config(self):
        """Test getting config for non-existent module."""
        logger.info("=" * 80)
        logger.info("TEST: Get non-existent module config")
        logger.info("=" * 80)

        mgr = LocationManager()
        mgr.create_location(id="kitchen", name="Kitchen")
        logger.info("Created location: kitchen")

        logger.info("Attempting to get config for non-existent module")
        config = mgr.get_module_config("kitchen", "nonexistent")
        logger.info(f"Result: {config}")

        assert config is None
        logger.info("✓ Returns None for non-existent module")


class TestLocationManagerComplexScenarios:
    """Test suite for complex real-world scenarios."""

    def test_full_house_topology(self):
        """Test creating a realistic house topology."""
        logger.info("=" * 80)
        logger.info("TEST: Full house topology")
        logger.info("=" * 80)

        mgr = LocationManager()

        logger.info("Building realistic house topology...")
        logger.info("Level 0: House")
        mgr.create_location(id="house", name="House")

        logger.info("Level 1: Floors")
        mgr.create_location(id="main_floor", name="Main Floor", parent_id="house")
        mgr.create_location(id="upper_floor", name="Upper Floor", parent_id="house")
        mgr.create_location(id="basement", name="Basement", parent_id="house")

        logger.info("Level 2: Rooms on main floor")
        mgr.create_location(id="kitchen", name="Kitchen", parent_id="main_floor")
        mgr.create_location(id="living_room", name="Living Room", parent_id="main_floor")
        mgr.create_location(id="dining_room", name="Dining Room", parent_id="main_floor")

        logger.info("Level 2: Rooms on upper floor")
        mgr.create_location(id="master_bedroom", name="Master Bedroom", parent_id="upper_floor")
        mgr.create_location(id="bedroom_2", name="Bedroom 2", parent_id="upper_floor")

        logger.info("Level 2: Basement areas")
        mgr.create_location(id="garage", name="Garage", parent_id="basement")

        all_locs = mgr.all_locations()
        logger.info(f"Total locations created: {len(all_locs)}")

        logger.info("Topology structure:")
        for loc in all_locs:
            parent_name = ""
            if loc.parent_id:
                parent = mgr.get_location(loc.parent_id)
                parent_name = f" (parent: {parent.name})"
            logger.debug(f"  - {loc.name}{parent_name}")

        assert len(all_locs) == 10
        logger.info("✓ Full house topology created successfully")

        logger.info("Testing descendant query on 'house'...")
        house_descendants = mgr.descendants_of("house")
        logger.info(f"House has {len(house_descendants)} descendants")
        assert len(house_descendants) == 9
        logger.info("✓ All descendants found")

        logger.info("Testing children query on 'main_floor'...")
        main_floor_children = mgr.children_of("main_floor")
        logger.info(f"Main floor has {len(main_floor_children)} children")
        child_names = [c.name for c in main_floor_children]
        logger.debug(f"Children: {', '.join(child_names)}")
        assert len(main_floor_children) == 3
        logger.info("✓ Main floor children correct")


if __name__ == "__main__":
    # Enable running tests directly
    pytest.main([__file__, "-v", "-s"])
