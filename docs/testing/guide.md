# Testing Guide for home-topology

## Overview

This guide documents the comprehensive test suites for the home-topology project, specifically focusing on the **LocationManager** and **OccupancyModule** components.

## Test Suites

### 1. LocationManager Tests (`test-location-manager.py`)

The LocationManager test suite contains **16 comprehensive tests** organized into 5 test classes:

#### TestLocationManagerCreation (5 tests)
- ✅ `test_create_root_location` - Verify root location creation
- ✅ `test_create_child_location` - Verify child location with parent
- ✅ `test_create_complex_hierarchy` - Multi-level hierarchy (house → floor → room)
- ✅ `test_duplicate_location_error` - Error handling for duplicate IDs
- ✅ `test_invalid_parent_error` - Error handling for invalid parents

#### TestLocationManagerHierarchyQueries (4 tests)
- ✅ `test_parent_of` - Query parent location
- ✅ `test_children_of` - Query direct children
- ✅ `test_ancestors_of` - Query all ancestors (parent chain to root)
- ✅ `test_descendants_of` - Query all descendants (entire subtree)

#### TestLocationManagerEntityMapping (3 tests)
- ✅ `test_add_entity_to_location` - Map entities to locations
- ✅ `test_move_entity_between_locations` - Move entity between locations
- ✅ `test_add_entity_to_invalid_location` - Error handling for invalid location

#### TestLocationManagerModuleConfig (3 tests)
- ✅ `test_set_and_get_module_config` - Store and retrieve module config
- ✅ `test_multiple_module_configs` - Multiple modules per location
- ✅ `test_get_nonexistent_module_config` - Handle missing configs

#### TestLocationManagerComplexScenarios (1 test)
- ✅ `test_full_house_topology` - Realistic 10-location house hierarchy

**Total: 16 tests - All Passing ✅**

### 2. OccupancyModule Tests (`test-occupancy-module.py`)

The OccupancyModule test suite contains **12 comprehensive tests** organized into 7 test classes:

#### TestOccupancyModuleAttachment (1 test)
- ✅ `test_module_attachment` - Engine initialization and state setup

#### TestOccupancyModuleMotionEvents (2 tests)
- ✅ `test_motion_sensor_triggers_occupancy` - Motion on → off triggers occupancy
- ✅ `test_motion_off_to_off_ignored` - No-change events are ignored

#### TestOccupancyModuleHierarchyPropagation (1 test)
- ✅ `test_child_occupancy_propagates_to_parent` - Upward propagation through hierarchy

#### TestOccupancyModuleIdentityTracking (2 tests)
- ✅ `test_presence_sensor_tracks_identity` - Track WHO is in location
- ✅ `test_presence_sensor_departure` - Remove identity on departure

#### TestOccupancyModuleStatePersistence (1 test)
- ✅ `test_dump_and_restore_state` - State persistence across restarts

#### TestOccupancyModuleConfiguration (2 tests)
- ✅ `test_default_config` - Default configuration values
- ✅ `test_config_schema` - Configuration schema structure

#### TestOccupancyModuleTimeouts (2 tests)
- ✅ `test_next_timeout_calculation` - Timeout scheduling
- ✅ `test_check_timeouts_manually` - Manual timeout checking

#### TestOccupancyModuleComplexScenarios (1 test)
- ✅ `test_multiple_sensors_same_room` - Multiple sensors in one location

**Total: 12 tests - All Passing ✅**

## Running the Tests

### Setup (First Time Only)

```bash
cd /home/mike/projects/home-topology

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install project with dev dependencies
pip install -e ".[dev]"
```

### Quick Test Commands

#### Run All Tests
```bash
# Quick run (all tests)
source venv/bin/activate && PYTHONPATH=src pytest tests/ -v

# With coverage
source venv/bin/activate && make test-cov
```

#### Run Specific Test Suites
```bash
# LocationManager tests only
source venv/bin/activate && PYTHONPATH=src pytest tests/test-location-manager.py -v

# OccupancyModule tests only
source venv/bin/activate && PYTHONPATH=src pytest tests/test-occupancy-module.py -v
```

#### Run with Detailed Logging
```bash
# All tests with INFO-level logging
source venv/bin/activate && PYTHONPATH=src pytest tests/ -v -s --log-cli-level=INFO

# All tests with DEBUG-level logging
source venv/bin/activate && PYTHONPATH=src pytest tests/ -v -s --log-cli-level=DEBUG

# Single test with logging
source venv/bin/activate && PYTHONPATH=src pytest \
  tests/test-occupancy-module.py::TestOccupancyModuleMotionEvents::test_motion_sensor_triggers_occupancy \
  -v -s --log-cli-level=INFO
```

#### Run Specific Test Class
```bash
# Run all LocationManager creation tests
source venv/bin/activate && PYTHONPATH=src pytest \
  tests/test-location-manager.py::TestLocationManagerCreation -v -s --log-cli-level=INFO

# Run all occupancy motion event tests
source venv/bin/activate && PYTHONPATH=src pytest \
  tests/test-occupancy-module.py::TestOccupancyModuleMotionEvents -v -s --log-cli-level=INFO
```

## Test Output Examples

### LocationManager Test Output
```
INFO     Creating location hierarchy...
INFO     Created location: house (House)
INFO     Created location: main_floor (Main Floor)
INFO     Created location: kitchen (Kitchen)
INFO     ✓ Complex hierarchy created successfully
```

### OccupancyModule Test Output
```
INFO     Triggering kitchen motion...
INFO     Handling event: momentary in kitchen (category=motion, source=binary_sensor.kitchen_motion)
INFO     kitchen: VACANT -> OCCUPIED (event)
INFO     main_floor: VACANT -> OCCUPIED (event)
INFO     house: VACANT -> OCCUPIED (event)
INFO     Occupancy changed: kitchen → OCCUPIED (confidence=0.80)
INFO     Occupancy changed: main_floor → OCCUPIED (confidence=0.80)
INFO     Occupancy changed: house → OCCUPIED (confidence=0.80)
INFO     ✓ Occupancy successfully propagated up hierarchy
```

## What the Tests Verify

### LocationManager
1. **Topology Management**: Creating and managing location hierarchies
2. **Graph Queries**: Parent, children, ancestor, and descendant queries
3. **Entity Mapping**: Mapping Home Assistant entities to locations
4. **Module Configuration**: Per-location module configuration storage
5. **Error Handling**: Proper validation and error messages

### OccupancyModule
1. **Event Processing**: Motion sensors, presence sensors, door sensors
2. **Hierarchy Propagation**: Child occupancy flows up to parents
3. **Identity Tracking**: Track WHO is in each location
4. **State Persistence**: Save and restore state across restarts
5. **Timeout Management**: Automatic vacancy after timeouts
6. **Configuration**: Module-specific configuration per location

## Logging Levels

The tests use extensive logging to show exactly what's happening:

- **INFO**: High-level test progress and key events
- **DEBUG**: Detailed internal state and transitions
- **Symbols**:
  - ✅ Success markers
  - 📢 Event emission markers
  - → State transitions

## Test Features

1. **Comprehensive Coverage**: Tests cover all major functionality
2. **Extensive Logging**: Every test step is logged for debugging
3. **Clear Organization**: Tests grouped by feature area
4. **Fixtures**: Reusable test fixtures for common setups
5. **Edge Cases**: Error handling and boundary conditions tested
6. **Real-World Scenarios**: Complex multi-location hierarchies

## Continuous Integration

To run all quality checks (format, lint, typecheck, test):

```bash
source venv/bin/activate && make check
```

This runs:
1. `black` - Code formatting
2. `ruff` - Linting
3. `mypy` - Type checking
4. `pytest` - All tests

## Test Results Summary

**Total Tests: 28**
- LocationManager: 16 tests ✅
- OccupancyModule: 12 tests ✅
- **All Passing**: 28/28 (100%)

## Next Steps

To add more tests:
1. Add new test methods to existing classes
2. Create new test classes for new features
3. Follow the existing logging patterns
4. Run `make check` before committing

## Need Help?

- Run `pytest --help` for pytest options
- Run `make help` for available make targets
- Check existing tests for examples
- All tests have extensive inline documentation

