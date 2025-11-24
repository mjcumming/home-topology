"""OccupancyModule - Native integration of occupancy tracking.

This module wraps the core occupancy engine and integrates it with the
home-topology kernel (EventBus, LocationManager).
"""

import logging
from datetime import datetime, UTC
from typing import Dict, Optional, List

from home_topology.modules.base import LocationModule
from home_topology.core.bus import Event, EventBus, EventFilter
from home_topology.core.manager import LocationManager

from .engine import OccupancyEngine
from .models import (
    LocationConfig,
    LocationKind,
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
    - Locking logic (party mode - freeze state)
    - Time-agnostic testing (no internal timers)
    - State persistence with stale data cleanup
    - Multiple event types: momentary, hold_start, hold_end, manual

    Note: This module does NOT schedule timeout checks internally.
    The host integration (HA, test suite, etc.) is responsible for:
    1. Calling check_timeouts(now) periodically
    2. Using get_next_timeout() to know when to schedule next check
    """

    def __init__(self):
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

        for location in self._loc_manager.all_locations():
            config_dict = self._loc_manager.get_module_config(location.id, self.id)

            # Skip if disabled
            if config_dict and not config_dict.get("enabled", True):
                logger.debug(f"Skipping disabled location: {location.id}")
                continue

            # Build timeout dict from config
            timeouts = {}
            if config_dict and "timeouts" in config_dict:
                # Convert seconds to minutes for engine
                for category, seconds in config_dict["timeouts"].items():
                    timeouts[category] = seconds // 60  # seconds → minutes
            else:
                # Use defaults
                timeouts = self.default_config()["timeouts"]
                # Convert to minutes
                timeouts = {k: v // 60 for k, v in timeouts.items()}

            location_config = LocationConfig(
                id=location.id,
                parent_id=location.parent_id,
                kind=LocationKind.AREA,  # Could be configurable
                occupancy_strategy=OccupancyStrategy.INDEPENDENT,  # Could be config
                contributes_to_parent=True,  # Could be configurable
                timeouts=timeouts,
            )

            configs.append(location_config)
            logger.debug(f"Created config for {location.id}: timeouts={timeouts}")

        return configs

    def _on_sensor_event(self, event: Event) -> None:
        """Handle sensor state change from platform."""
        # Translate to occupancy event
        occ_event = self._translate_event(event)
        if not occ_event:
            return

        # Process with engine
        now = datetime.now(UTC)
        result = self._engine.handle_event(occ_event, now)

        # Emit transitions as occupancy.changed events
        for transition in result.transitions:
            self._emit_occupancy_changed(transition)

        # Note: Host is responsible for scheduling timeout checks
        # Use get_next_timeout() to know when to schedule

    def _translate_event(self, event: Event) -> Optional[OccupancyEvent]:
        """Translate platform Event to OccupancyEvent."""
        entity_id = event.entity_id
        if not entity_id:
            return None

        # Map entity to location
        location_id = self._loc_manager.get_entity_location(entity_id)
        if not location_id:
            logger.debug(f"Entity {entity_id} not mapped to any location")
            return None

        # Determine event type and category from entity state
        old_state = event.payload.get("old_state")
        new_state = event.payload.get("new_state")

        event_type, category = self._determine_event_type(entity_id, old_state, new_state)
        if not event_type:
            return None

        # Extract occupant_id if present
        occupant_id = event.payload.get("occupant_id")

        return OccupancyEvent(
            location_id=location_id,
            event_type=event_type,
            category=category,
            source_id=entity_id,
            timestamp=event.timestamp,
            occupant_id=occupant_id,
        )

    def _determine_event_type(
        self, entity_id: str, old_state: Optional[str], new_state: Optional[str]
    ) -> tuple[Optional[EventType], Optional[str]]:
        """Map entity state change to EventType and category."""

        # Motion sensor: off→on = MOMENTARY
        if "motion" in entity_id.lower():
            if old_state == "off" and new_state == "on":
                return EventType.MOMENTARY, "motion"

        # Presence/radar/mmwave: HOLD_START / HOLD_END
        if any(x in entity_id.lower() for x in ["presence", "radar", "mmwave", "ble_"]):
            if old_state == "off" and new_state == "on":
                return EventType.HOLD_START, "presence"
            elif old_state == "on" and new_state == "off":
                return EventType.HOLD_END, "presence"

        # Door sensor: off→on = MOMENTARY (entry/exit)
        if "door" in entity_id.lower():
            if old_state == "off" and new_state == "on":
                return EventType.MOMENTARY, "door"

        # Media player: playing = HOLD_START, not playing = HOLD_END
        if "media_player" in entity_id.lower():
            if old_state != "playing" and new_state == "playing":
                return EventType.HOLD_START, "media"
            elif old_state == "playing" and new_state != "playing":
                return EventType.HOLD_END, "media"

        return None, None

    def _emit_occupancy_changed(self, transition) -> None:
        """Emit semantic occupancy.changed event."""
        new_state = transition.new_state
        prev_state = transition.previous_state

        # Calculate confidence (simple: 1.0 if occupied, 0.0 if vacant)
        confidence = 1.0 if new_state.is_occupied else 0.0

        # If we have active holds or occupants, confidence is high
        if new_state.active_holds or new_state.active_occupants:
            confidence = 1.0
        # If timer is ticking down, reduce confidence over time
        elif new_state.occupied_until and new_state.is_occupied:
            # Could calculate based on how close to expiry
            confidence = 0.8

        self._bus.publish(
            Event(
                type="occupancy.changed",
                source="occupancy",
                location_id=transition.location_id,
                payload={
                    "occupied": new_state.is_occupied,
                    "confidence": confidence,
                    "active_occupants": list(new_state.active_occupants),
                    "active_holds": list(new_state.active_holds),
                    "expires_at": (
                        new_state.occupied_until.isoformat() if new_state.occupied_until else None
                    ),
                    "previous_occupied": prev_state.is_occupied if prev_state else False,
                    "reason": transition.reason,
                    "lock_state": new_state.lock_state.value,
                },
                timestamp=datetime.now(UTC),
            )
        )

        logger.info(
            f"Occupancy changed: {transition.location_id} → "
            f"{'OCCUPIED' if new_state.is_occupied else 'VACANT'} "
            f"(confidence={confidence:.2f})"
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
            now = datetime.now(UTC)

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
            now = datetime.now(UTC)

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
            "confidence": 1.0 if state.is_occupied else 0.0,
            "active_occupants": list(state.active_occupants),
            "active_holds": list(state.active_holds),
            "occupied_until": (state.occupied_until.isoformat() if state.occupied_until else None),
            "lock_state": state.lock_state.value,
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

        now = datetime.now(UTC)
        self._engine.restore_state(state, now)
        logger.info(f"Restored occupancy state for {len(state)} locations")

        # Note: Host should call get_next_timeout() and schedule check_timeouts()

    def default_config(self) -> Dict:
        """Default configuration for a location."""
        return {
            "version": self.CURRENT_CONFIG_VERSION,
            "enabled": True,
            "timeouts": {
                "default": 600,  # 10 minutes (in seconds)
                "motion": 300,  # 5 minutes
                "presence": 600,  # 10 minutes
                "door": 120,  # 2 minutes
                "media": 300,  # 5 minutes
            },
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
                "timeouts": {
                    "type": "object",
                    "title": "Timeout Durations (seconds)",
                    "properties": {
                        "default": {
                            "type": "integer",
                            "title": "Default Timeout",
                            "minimum": 30,
                            "default": 600,
                        },
                        "motion": {
                            "type": "integer",
                            "title": "Motion Sensor Timeout",
                            "minimum": 30,
                            "default": 300,
                        },
                        "presence": {
                            "type": "integer",
                            "title": "Presence Sensor Timeout",
                            "minimum": 60,
                            "default": 600,
                        },
                        "door": {
                            "type": "integer",
                            "title": "Door Sensor Timeout",
                            "minimum": 30,
                            "default": 120,
                        },
                        "media": {
                            "type": "integer",
                            "title": "Media Player Timeout",
                            "minimum": 60,
                            "default": 300,
                        },
                    },
                },
                "occupancy_strategy": {
                    "type": "string",
                    "title": "Occupancy Strategy",
                    "enum": ["independent", "follow_parent"],
                    "default": "independent",
                    "description": "independent: track own sensors; follow_parent: follow parent location state",
                },
                "contributes_to_parent": {
                    "type": "boolean",
                    "title": "Contribute to Parent",
                    "default": True,
                    "description": "Whether this location's occupancy propagates up to parent",
                },
            },
        }
