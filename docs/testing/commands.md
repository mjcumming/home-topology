# Quick Test Reference Card

## Setup (One Time)
```bash
cd /home/mike/projects/home-topology
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

## Quick Test Commands

### Run All Tests
```bash
# Activate venv and run all tests
source venv/bin/activate && PYTHONPATH=src pytest tests/test-location-manager.py tests/test-occupancy-module.py -v

# Short version (28 tests total)
source venv/bin/activate && PYTHONPATH=src pytest tests/ -v
```

### Run with Detailed Logging

#### INFO Level (Recommended for following along)
```bash
source venv/bin/activate && PYTHONPATH=src pytest tests/test-location-manager.py -v -s --log-cli-level=INFO
source venv/bin/activate && PYTHONPATH=src pytest tests/test-occupancy-module.py -v -s --log-cli-level=INFO
```

#### DEBUG Level (Everything!)
```bash
source venv/bin/activate && PYTHONPATH=src pytest tests/test-location-manager.py -v -s --log-cli-level=DEBUG
source venv/bin/activate && PYTHONPATH=src pytest tests/test-occupancy-module.py -v -s --log-cli-level=DEBUG
```

### Run Specific Tests

#### LocationManager Tests
```bash
# All creation tests
source venv/bin/activate && PYTHONPATH=src pytest tests/test-location-manager.py::TestLocationManagerCreation -v -s --log-cli-level=INFO

# Hierarchy query tests
source venv/bin/activate && PYTHONPATH=src pytest tests/test-location-manager.py::TestLocationManagerHierarchyQueries -v -s --log-cli-level=INFO

# Full house topology test
source venv/bin/activate && PYTHONPATH=src pytest tests/test-location-manager.py::TestLocationManagerComplexScenarios::test_full_house_topology -v -s --log-cli-level=DEBUG
```

#### OccupancyModule Tests
```bash
# Motion sensor tests
source venv/bin/activate && PYTHONPATH=src pytest tests/test-occupancy-module.py::TestOccupancyModuleMotionEvents -v -s --log-cli-level=INFO

# Hierarchy propagation
source venv/bin/activate && PYTHONPATH=src pytest tests/test-occupancy-module.py::TestOccupancyModuleHierarchyPropagation -v -s --log-cli-level=INFO

# Identity tracking
source venv/bin/activate && PYTHONPATH=src pytest tests/test-occupancy-module.py::TestOccupancyModuleIdentityTracking -v -s --log-cli-level=INFO
```

### Single Test Examples
```bash
# Run one specific test with full logging
source venv/bin/activate && PYTHONPATH=src pytest \
  tests/test-occupancy-module.py::TestOccupancyModuleMotionEvents::test_motion_sensor_triggers_occupancy \
  -v -s --log-cli-level=INFO

# Another example
source venv/bin/activate && PYTHONPATH=src pytest \
  tests/test-location-manager.py::TestLocationManagerCreation::test_create_complex_hierarchy \
  -v -s --log-cli-level=DEBUG
```

## What You'll See in the Logs

### LocationManager Logs
- Location creation with parent relationships
- Hierarchy traversal (parent/children/ancestors/descendants)
- Entity mapping to locations
- Module configuration storage
- ✓ Success markers for each verification

### OccupancyModule Logs
- Event processing (motion/presence sensors)
- State transitions (VACANT → OCCUPIED)
- Hierarchy propagation (child → parent → grandparent)
- Identity tracking (WHO is in the room)
- Confidence scores
- Timeout scheduling
- 📢 Event emission markers

## Test Summary

**28 Total Tests - All Passing ✅**
- LocationManager: 16 tests
- OccupancyModule: 12 tests

## Log Level Comparison

| Level | What You See |
|-------|--------------|
| No logging | Just pass/fail status |
| INFO | High-level test steps and results |
| DEBUG | Every detail including internal state |

## Recommended Workflow

1. **Quick check**: Run without logging
   ```bash
   source venv/bin/activate && PYTHONPATH=src pytest tests/ -v
   ```

2. **Detailed review**: Run with INFO logging
   ```bash
   source venv/bin/activate && PYTHONPATH=src pytest tests/ -v -s --log-cli-level=INFO
   ```

3. **Deep debugging**: Run specific test with DEBUG
   ```bash
   source venv/bin/activate && PYTHONPATH=src pytest \
     tests/test-occupancy-module.py::TestOccupancyModuleHierarchyPropagation::test_child_occupancy_propagates_to_parent \
     -v -s --log-cli-level=DEBUG
   ```

## Additional Commands

### Coverage Report
```bash
source venv/bin/activate && PYTHONPATH=src pytest tests/ -v --cov=home_topology --cov-report=term-missing
```

### All Quality Checks (format, lint, typecheck, test)
```bash
source venv/bin/activate && make check
```

## Files Created

- `tests/test-location-manager.py` - 16 comprehensive LocationManager tests
- `tests/test-occupancy-module.py` - 12 comprehensive OccupancyModule tests
- `docs/testing/guide.md` - Full documentation
- `docs/testing/commands.md` - This quick reference

## Notes

- All tests include extensive logging at INFO and DEBUG levels
- Tests are organized into logical test classes
- Each test documents what it's verifying
- Fixtures handle common setup scenarios
- Error cases are tested along with success cases

