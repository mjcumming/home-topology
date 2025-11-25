"""OccupancyModule - Native integration of occupancy tracking.

This module wraps the core occupancy engine and integrates it with the
home-topology kernel (EventBus, LocationManager).
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

from home_topology.modules.base import LocationModule
from home_topology.core.bus import Event, EventBus, EventFilter
from home_topology.core.manager import LocationManager

from .engine import OccupancyEngine
from .models import (
    LocationConfig,
    OccupancyEvent,
    EventType,
    OccupancyStrategy,
)

logger = logging.getLogger(__name__)


class OccupancyModule(LocationModule):
    """
    Occupancy tracking module.

    Features:
    - Hierarchical occupancy with parent/child propagation
    - Identity tracking (who is in the room)
    - Source-tracked locking (multiple automations can lock independently)
    - Time-agnostic testing (no internal timers)
    - State persistence with stale data cleanup
    - 7 event types: TRIGGER, HOLD, RELEASE, VACATE, LOCK, UNLOCK, UNLOCK_ALL

    Note: This module does NOT schedule timeout checks internally.
    The host integration (HA, test suite, etc.) is responsible for:
    1. Calling check_timeouts(now) periodically
    2. Using get_next_timeout() to know when to schedule next check
    """

    def __init__(self) -> None:
        self._bus: Optional[EventBus] = None
        self._loc_manager: Optional[LocationManager] = None
        self._engine: Optional[OccupancyEngine] = None

    @property
    def id(self) -> str:
        return "occupancy"

    @property
    def CURRENT_CONFIG_VERSION(self) -> int:
        return 1

    def attach(self, bus: EventBus, loc_manager: LocationManager) -> None:
        """Attach to the kernel and initialize engine."""
        logger.info("Attaching OccupancyModule")
        self._bus = bus
        self._loc_manager = loc_manager

        # Build LocationConfigs from the LocationManager
        configs = self._build_location_configs()

        # Initialize the engine
        self._engine = OccupancyEngine(configs)
        logger.info(f"Occupancy engine initialized with {len(configs)} locations")

        # Subscribe to platform sensor events
        bus.subscribe(self._on_sensor_event, EventFilter(event_type="sensor.state_changed"))

        # Note: Host integration must call check_timeouts() periodically
        # Use get_next_timeout() to know when to schedule

    def _build_location_configs(self) -> List[LocationConfig]:
        """Build LocationConfig list from LocationManager."""
        configs = []
        assert self._loc_manager is not None

        for location in self._loc_manager.all_locations():
            config_dict: Optional[Dict[str, Any]] = self._loc_manager.get_module_config(
                location.id, self.id
            )

            # Skip if disabled
            if config_dict and not config_dict.get("enabled", True):
                logger.debug(f"Skipping disabled location: {location.id}")
                continue

            # Get timeouts from config or use defaults
            default_timeout = 300  # 5 minutes
            hold_release_timeout = 120  # 2 minutes

            if config_dict:
                default_timeout = config_dict.get("default_timeout", default_timeout)
                hold_release_timeout = config_dict.get("hold_release_timeout", hold_release_timeout)

                # Support legacy "timeouts" dict format
                if "timeouts" in config_dict:
                    timeouts = config_dict["timeouts"]
                    default_timeout = timeouts.get("default", default_timeout)
                    # Use presence timeout as hold_release_timeout if available
                    hold_release_timeout = timeouts.get("presence", hold_release_timeout)

            # Get strategy
            strategy_str = "independent"
            if config_dict:
                strategy_str = config_dict.get("occupancy_strategy", strategy_str)
            strategy = OccupancyStrategy.INDEPENDENT
            if strategy_str == "follow_parent":
                strategy = OccupancyStrategy.FOLLOW_PARENT

            # Get contributes_to_parent
            contributes = True
            if config_dict:
                contributes = config_dict.get("contributes_to_parent", True)

            location_config = LocationConfig(
                id=location.id,
                parent_id=location.parent_id,
                occupancy_strategy=strategy,
                contributes_to_parent=contributes,
                default_timeout=default_timeout,
                hold_release_timeout=hold_release_timeout,
            )

            configs.append(location_config)
            logger.debug(
                f"Created config for {location.id}: "
                f"default_timeout={default_timeout}, hold_release_timeout={hold_release_timeout}"
            )

        return configs

    def _on_sensor_event(self, event: Event) -> None:
        """Handle sensor state change from platform."""
        # Translate to occupancy event
        occ_event = self._translate_event(event)
        if not occ_event:
            return

        # Process with engine
        assert self._engine is not None
        now = datetime.now(timezone.utc)
        result = self._engine.handle_event(occ_event, now)

        # Emit transitions as occupancy.changed events
        for transition in result.transitions:
            self._emit_occupancy_changed(transition)

        # Note: Host is responsible for scheduling timeout checks
        # Use get_next_timeout() to know when to schedule

    def _translate_event(self, event: Event) -> Optional[OccupancyEvent]:
        """Translate platform Event to OccupancyEvent.

        This is the integration layer's signal classification logic.
        It maps platform entity state changes to occupancy event types.
        """
        entity_id = event.entity_id
        if not entity_id:
            return None

        # Map entity to location
        assert self._loc_manager is not None
        location_id = self._loc_manager.get_entity_location(entity_id)
        if not location_id:
            logger.debug(f"Entity {entity_id} not mapped to any location")
            return None

        # Determine event type and timeout from entity state
        old_state = event.payload.get("old_state")
        new_state = event.payload.get("new_state")

        event_type, timeout = self._classify_signal(entity_id, old_state, new_state)
        if not event_type:
            return None

        # Extract occupant_id if present
        occupant_id = event.payload.get("occupant_id")

        return OccupancyEvent(
            location_id=location_id,
            event_type=event_type,
            source_id=entity_id,
            timestamp=event.timestamp,
            timeout=timeout,
            occupant_id=occupant_id,
        )

    def _classify_signal(
        self, entity_id: str, old_state: Optional[str], new_state: Optional[str]
    ) -> tuple[Optional[EventType], Optional[int]]:
        """Classify entity state change to EventType and timeout.

        This is the integration layer's signal classification logic.
        Returns (event_type, timeout_seconds) or (None, None) if not occupancy-related.

        Note: This logic belongs in the integration layer.
        This implementation serves as an example/reference.
        """

        # Motion sensor: off→on = TRIGGER with 5 min timeout
        if "motion" in entity_id.lower():
            if old_state == "off" and new_state == "on":
                return EventType.TRIGGER, 300  # 5 minutes

        # Presence/radar/mmwave: HOLD / RELEASE
        if any(x in entity_id.lower() for x in ["presence", "radar", "mmwave", "ble_"]):
            if old_state == "off" and new_state == "on":
                return EventType.HOLD, None  # No timeout for HOLD
            elif old_state == "on" and new_state == "off":
                return EventType.RELEASE, 120  # 2 min trailing timeout

        # Door sensor: off→on = TRIGGER with 2 min timeout
        if "door" in entity_id.lower():
            if old_state == "off" and new_state == "on":
                return EventType.TRIGGER, 120  # 2 minutes

        # Media player: playing = HOLD, not playing = RELEASE
        if "media_player" in entity_id.lower():
            if old_state != "playing" and new_state == "playing":
                return EventType.HOLD, None  # No timeout for HOLD
            elif old_state == "playing" and new_state != "playing":
                return EventType.RELEASE, 300  # 5 min trailing timeout

        return None, None

    def _emit_occupancy_changed(self, transition: Any) -> None:
        """Emit semantic occupancy.changed event."""
        assert self._bus is not None
        new_state = transition.new_state
        prev_state = transition.previous_state

        self._bus.publish(
            Event(
                type="occupancy.changed",
                source="occupancy",
                location_id=transition.location_id,
                payload={
                    "occupied": new_state.is_occupied,
                    "active_occupants": list(new_state.active_occupants),
                    "active_holds": list(new_state.active_holds),
                    "locked_by": list(new_state.locked_by),
                    "is_locked": new_state.is_locked,
                    "expires_at": (
                        new_state.occupied_until.isoformat() if new_state.occupied_until else None
                    ),
                    "previous_occupied": prev_state.is_occupied if prev_state else False,
                    "reason": transition.reason,
                },
                timestamp=datetime.now(timezone.utc),
            )
        )

        lock_status = f" [LOCKED by {list(new_state.locked_by)}]" if new_state.is_locked else ""
        logger.info(
            f"Occupancy changed: {transition.location_id} → "
            f"{'OCCUPIED' if new_state.is_occupied else 'VACANT'}{lock_status}"
        )

    def get_next_timeout(self, now: Optional[datetime] = None) -> Optional[datetime]:
        """Get when the next timeout check should occur.

        The host integration (HA, test suite, etc.) should call this after
        each event to know when to schedule check_timeouts().

        Args:
            now: Current time (defaults to datetime.now(UTC))

        Returns:
            datetime when next check needed, or None if no active timers

        Example:
            # In HA integration:
            next_check = occupancy.get_next_timeout()
            if next_check:
                async_track_point_in_time(hass, check_timeouts_callback, next_check)
        """
        if not self._engine:
            return None

        if now is None:
            now = datetime.now(timezone.utc)

        return self._engine._calculate_next_expiration(now)

    def check_timeouts(self, now: Optional[datetime] = None) -> None:
        """Check for expired timers and emit transitions.

        The host integration is responsible for calling this at appropriate times.
        Use get_next_timeout() to know when to schedule the next check.

        Args:
            now: Current time (defaults to datetime.now(UTC))

        Example:
            # In HA integration:
            def check_timeouts_callback(now):
                occupancy.check_timeouts(now)

            # In tests:
            occupancy.check_timeouts(test_time)
        """
        if not self._engine:
            return

        if now is None:
            now = datetime.now(timezone.utc)

        logger.debug(f"Checking timeouts at {now}")
        result = self._engine.check_timeouts(now)

        # Emit transitions
        for transition in result.transitions:
            self._emit_occupancy_changed(transition)

    def get_location_state(self, location_id: str) -> Optional[Dict]:
        """Get current occupancy state for a location."""
        if not self._engine or location_id not in self._engine.state:
            return None

        state = self._engine.state[location_id]

        return {
            "occupied": state.is_occupied,
            "active_occupants": list(state.active_occupants),
            "active_holds": list(state.active_holds),
            "locked_by": list(state.locked_by),
            "is_locked": state.is_locked,
            "occupied_until": (state.occupied_until.isoformat() if state.occupied_until else None),
        }

    def dump_state(self) -> Dict:
        """Export engine state for persistence."""
        if not self._engine:
            return {}

        return self._engine.export_state()

    def restore_state(self, state: Dict) -> None:
        """Restore engine state from persistence."""
        if not self._engine:
            logger.warning("Cannot restore state: engine not initialized")
            return

        now = datetime.now(timezone.utc)
        self._engine.restore_state(state, now)
        logger.info(f"Restored occupancy state for {len(state)} locations")

        # Note: Host should call get_next_timeout() and schedule check_timeouts()

    def default_config(self) -> Dict:
        """Default configuration for a location."""
        return {
            "version": self.CURRENT_CONFIG_VERSION,
            "enabled": True,
            "default_timeout": 300,  # 5 minutes for TRIGGER events
            "hold_release_timeout": 120,  # 2 minutes after RELEASE
            "occupancy_strategy": "independent",  # or "follow_parent"
            "contributes_to_parent": True,
        }

    def location_config_schema(self) -> Dict:
        """JSON schema for UI configuration."""
        return {
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "title": "Enable Occupancy Tracking",
                    "default": True,
                },
                "default_timeout": {
                    "type": "integer",
                    "title": "Default Timeout (seconds)",
                    "description": "Timer duration for TRIGGER events (motion, door, etc.)",
                    "minimum": 30,
                    "default": 300,
                },
                "hold_release_timeout": {
                    "type": "integer",
                    "title": "Hold Release Timeout (seconds)",
                    "description": "Trailing timer after RELEASE events (presence cleared)",
                    "minimum": 30,
                    "default": 120,
                },
                "occupancy_strategy": {
                    "type": "string",
                    "title": "Occupancy Strategy",
                    "enum": ["independent", "follow_parent"],
                    "default": "independent",
                    "description": "independent: track own sensors; follow_parent: mirror parent state",
                },
                "contributes_to_parent": {
                    "type": "boolean",
                    "title": "Contribute to Parent",
                    "default": True,
                    "description": "Whether this location's occupancy propagates up to parent",
                },
            },
        }

    # --- Direct API for sending events ---

    def trigger(
        self,
        location_id: str,
        source_id: str,
        timeout: Optional[int] = None,
        occupant_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> None:
        """Send a TRIGGER event (activity detected)."""
        assert self._engine is not None
        if now is None:
            now = datetime.now(timezone.utc)
        event = OccupancyEvent(
            location_id=location_id,
            event_type=EventType.TRIGGER,
            source_id=source_id,
            timestamp=now,
            timeout=timeout,
            occupant_id=occupant_id,
        )
        result = self._engine.handle_event(event, now)
        for transition in result.transitions:
            self._emit_occupancy_changed(transition)

    def hold(
        self,
        location_id: str,
        source_id: str,
        occupant_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> None:
        """Send a HOLD event (presence detected)."""
        assert self._engine is not None
        if now is None:
            now = datetime.now(timezone.utc)
        event = OccupancyEvent(
            location_id=location_id,
            event_type=EventType.HOLD,
            source_id=source_id,
            timestamp=now,
            occupant_id=occupant_id,
        )
        result = self._engine.handle_event(event, now)
        for transition in result.transitions:
            self._emit_occupancy_changed(transition)

    def release(
        self,
        location_id: str,
        source_id: str,
        timeout: Optional[int] = None,
        occupant_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> None:
        """Send a RELEASE event (presence cleared)."""
        assert self._engine is not None
        if now is None:
            now = datetime.now(timezone.utc)
        event = OccupancyEvent(
            location_id=location_id,
            event_type=EventType.RELEASE,
            source_id=source_id,
            timestamp=now,
            timeout=timeout,
            occupant_id=occupant_id,
        )
        result = self._engine.handle_event(event, now)
        for transition in result.transitions:
            self._emit_occupancy_changed(transition)

    def vacate(
        self,
        location_id: str,
        source_id: str,
        now: Optional[datetime] = None,
    ) -> None:
        """Send a VACATE event (force vacant)."""
        assert self._engine is not None
        if now is None:
            now = datetime.now(timezone.utc)
        event = OccupancyEvent(
            location_id=location_id,
            event_type=EventType.VACATE,
            source_id=source_id,
            timestamp=now,
        )
        result = self._engine.handle_event(event, now)
        for transition in result.transitions:
            self._emit_occupancy_changed(transition)

    def lock(
        self,
        location_id: str,
        source_id: str,
        now: Optional[datetime] = None,
    ) -> None:
        """Send a LOCK event (freeze state)."""
        assert self._engine is not None
        if now is None:
            now = datetime.now(timezone.utc)
        event = OccupancyEvent(
            location_id=location_id,
            event_type=EventType.LOCK,
            source_id=source_id,
            timestamp=now,
        )
        result = self._engine.handle_event(event, now)
        for transition in result.transitions:
            self._emit_occupancy_changed(transition)

    def unlock(
        self,
        location_id: str,
        source_id: str,
        now: Optional[datetime] = None,
    ) -> None:
        """Send an UNLOCK event (remove lock from this source)."""
        assert self._engine is not None
        if now is None:
            now = datetime.now(timezone.utc)
        event = OccupancyEvent(
            location_id=location_id,
            event_type=EventType.UNLOCK,
            source_id=source_id,
            timestamp=now,
        )
        result = self._engine.handle_event(event, now)
        for transition in result.transitions:
            self._emit_occupancy_changed(transition)

    def unlock_all(
        self,
        location_id: str,
        source_id: str = "force_unlock",
        now: Optional[datetime] = None,
    ) -> None:
        """Send an UNLOCK_ALL event (clear all locks)."""
        assert self._engine is not None
        if now is None:
            now = datetime.now(timezone.utc)
        event = OccupancyEvent(
            location_id=location_id,
            event_type=EventType.UNLOCK_ALL,
            source_id=source_id,
            timestamp=now,
        )
        result = self._engine.handle_event(event, now)
        for transition in result.transitions:
            self._emit_occupancy_changed(transition)

    def get_effective_timeout(
        self,
        location_id: str,
        now: Optional[datetime] = None,
    ) -> Optional[datetime]:
        """Get when location will TRULY become vacant (considers all descendants).

        Unlike `occupied_until` in location state (which is the location's own timer),
        this returns the maximum timeout across the location and ALL its descendants.

        Args:
            location_id: The location to check.
            now: Current time (defaults to datetime.now(UTC))

        Returns:
            The latest timeout datetime, or None if:
            - Location is vacant
            - Location or any descendant has indefinite occupancy (holds/occupants)

        Example:
            # House has timer until T+300s
            # But kitchen (child) has timer until T+400s
            state = module.get_location_state("house")
            own_timeout = state["occupied_until"]  # T+300s

            effective = module.get_effective_timeout("house")  # T+400s
        """
        if not self._engine:
            return None

        if now is None:
            now = datetime.now(timezone.utc)

        return self._engine.get_effective_timeout(location_id, now)

    def vacate_area(
        self,
        location_id: str,
        source_id: str,
        include_locked: bool = False,
        now: Optional[datetime] = None,
    ) -> List[Dict]:
        """Vacate a location and ALL its descendants.

        Unlike `vacate()` which only affects a single location, this method
        recursively vacates the specified location and all children, grandchildren, etc.

        Args:
            location_id: Root of the subtree to vacate.
            source_id: What initiated the vacate (for logging/debugging).
            include_locked: If True, also unlock and vacate locked locations.
                           If False (default), locked locations are skipped.
            now: Current time (defaults to datetime.now(UTC))

        Returns:
            List of dicts describing each transition that occurred:
            [{"location_id": "kitchen", "was_occupied": True, "is_occupied": False}, ...]

        Example:
            # Clear entire first floor
            transitions = module.vacate_area(
                "first_floor",
                "away_mode_activation",
            )
            print(f"Cleared {len(transitions)} locations")

            # Force clear including locked locations
            module.vacate_area("house", "emergency", include_locked=True)
        """
        if not self._engine:
            return []

        if now is None:
            now = datetime.now(timezone.utc)

        result = self._engine.vacate_area(location_id, source_id, now, include_locked)

        # Emit events for all transitions
        for transition in result.transitions:
            self._emit_occupancy_changed(transition)

        # Return simplified transition info
        return [
            {
                "location_id": t.location_id,
                "was_occupied": t.previous_state.is_occupied,
                "is_occupied": t.new_state.is_occupied,
                "reason": t.reason,
            }
            for t in result.transitions
        ]
