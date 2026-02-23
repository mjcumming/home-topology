# Occupancy module implementation status

**Status**: v3.0 implemented
**Last Updated**: 2026-02-23 (hardening pass)

## Current implementation

The occupancy module now uses the v3 model:

- Events: `TRIGGER`, `CLEAR`
- Commands: `VACATE`, `LOCK`, `UNLOCK`, `UNLOCK_ALL`
- State model: per-source `contributions` with `expires_at`
- Lock behavior: contribution suspension/resume while locked
- FOLLOW_PARENT: strict mirror (direct occupancy events ignored)
- Parent-child propagation: parent occupancy remains derived from child occupancy

## Completed in this migration

- Replaced v2.3 event handling (`HOLD`, `RELEASE`, `EXTEND`) with v3 behavior
- Replaced `active_holds` + shared `occupied_until` model with per-source contributions
- Updated occupancy module API to `trigger()` and `clear()`
- Updated emitted `occupancy.changed` payload to expose `contributions`
- Added/updated v3-focused tests for engine and module behavior
- Fixed parent/child invariant so parent vacancy is child-state derived
- Enforced strict `FOLLOW_PARENT` direct-event ignore semantics
- Normalized inbound timestamps to UTC-aware datetimes
- Added timeout input validation for public API methods (reject negative/non-integer)
- Added topology-mutation rebuild path with state preservation
- Defined stable transition reason contract:
  - `event:<event_type>`
  - `propagation:child:<location_id>`
  - `propagation:parent`
  - `timeout`

## Validation snapshot

Targeted occupancy tests pass:

- `tests/test_occupancy_integration.py`
- `tests/test_occupancy_module.py`
- `tests/test_advanced_occupancy.py`

Run command used:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  tests/test_occupancy_integration.py \
  tests/test_occupancy_module.py \
  tests/test_advanced_occupancy.py
```

## Remaining work

- Optional: full project-wide pytest run in a clean CI-like environment
- Optional: add explicit fuzz/property tests for randomized event interleavings
