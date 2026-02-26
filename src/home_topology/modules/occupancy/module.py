"""OccupancyModule - Native integration of occupancy tracking (v3.0)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from home_topology.core.bus import Event, EventBus, EventFilter
from home_topology.core.manager import LocationManager
from home_topology.modules.base import LocationModule

from .engine import OccupancyEngine
from .models import (
    EventType,
    LocationConfig,
    LockMode,
    LockScope,
    OccupancyEvent,
    OccupancyStrategy,
)

logger = logging.getLogger(__name__)

_UNSET = object()


class OccupancyModule(LocationModule):
    """Occupancy tracking module (v3.0)."""

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
        """Attach to the kernel and initialize the engine."""
        self._bus = bus
        self._loc_manager = loc_manager

        configs = self._build_location_configs()
        self._engine = OccupancyEngine(configs)

        bus.subscribe(self._on_occupancy_signal, EventFilter(event_type="occupancy.signal"))
        for event_type in (
            "location.created",
            "location.deleted",
            "location.parent_changed",
            "location.reordered",
        ):
            bus.subscribe(self._on_topology_mutation, EventFilter(event_type=event_type))

    def _build_location_configs(self) -> List[LocationConfig]:
        """Build LocationConfig list from LocationManager."""
        configs: list[LocationConfig] = []
        assert self._loc_manager is not None

        for location in self._loc_manager.all_locations():
            config_dict: Optional[Dict[str, Any]] = self._loc_manager.get_module_config(
                location.id, self.id
            )

            if config_dict and not config_dict.get("enabled", True):
                continue

            default_timeout = 300
            default_trailing_timeout = 120
            if config_dict:
                default_timeout = config_dict.get("default_timeout", default_timeout)
                default_trailing_timeout = config_dict.get(
                    "default_trailing_timeout",
                    config_dict.get("hold_release_timeout", default_trailing_timeout),
                )

                # Legacy `timeouts` format support.
                if "timeouts" in config_dict:
                    timeouts = config_dict["timeouts"]
                    default_timeout = timeouts.get("default", default_timeout)
                    default_trailing_timeout = timeouts.get("presence", default_trailing_timeout)

            strategy_str = (
                config_dict.get("occupancy_strategy", "independent")
                if config_dict
                else "independent"
            )
            strategy = (
                OccupancyStrategy.FOLLOW_PARENT
                if strategy_str == "follow_parent"
                else OccupancyStrategy.INDEPENDENT
            )

            contributes = config_dict.get("contributes_to_parent", True) if config_dict else True
            if strategy == OccupancyStrategy.FOLLOW_PARENT:
                # Prevent parent-child feedback loops.
                contributes = False

            configs.append(
                LocationConfig(
                    id=location.id,
                    parent_id=location.parent_id,
                    occupancy_strategy=strategy,
                    contributes_to_parent=contributes,
                    default_timeout=default_timeout,
                    default_trailing_timeout=default_trailing_timeout,
                )
            )

        return configs

    def _on_occupancy_signal(self, event: Event) -> None:
        """Handle normalized occupancy signal from integration."""
        occ_event = self._translate_signal_event(event)
        if not occ_event:
            return

        assert self._engine is not None
        now = self._normalize_timestamp(event.timestamp)
        result = self._engine.handle_event(occ_event, now)

        for transition in result.transitions:
            self._emit_occupancy_changed(transition)

    def _on_topology_mutation(self, event: Event) -> None:
        """Rebuild engine when topology structure changes."""
        self._rebuild_engine_preserving_state(event.timestamp)

    def _translate_signal_event(self, event: Event) -> Optional[OccupancyEvent]:
        """Translate a normalized `occupancy.signal` event to OccupancyEvent."""
        payload = event.payload or {}

        raw_event_type = payload.get("event_type", payload.get("signal_type"))
        if raw_event_type is None:
            logger.warning("Ignoring occupancy.signal without payload.event_type")
            return None

        event_type = self._parse_event_type(raw_event_type)
        if event_type is None:
            logger.warning("Ignoring occupancy.signal with unknown event_type: %s", raw_event_type)
            return None

        timeout: Optional[int] = None
        timeout_set = "timeout" in payload
        if timeout_set:
            raw_timeout = payload.get("timeout")
            if raw_timeout is not None:
                try:
                    timeout = int(raw_timeout)
                except (TypeError, ValueError):
                    logger.warning(
                        "Ignoring occupancy.signal with invalid timeout: %s", raw_timeout
                    )
                    return None
                if timeout < 0:
                    logger.warning(
                        "Ignoring occupancy.signal with negative timeout: %s", raw_timeout
                    )
                    return None

        lock_mode = LockMode.FREEZE
        lock_scope = LockScope.SELF
        if event_type == EventType.LOCK:
            lock_mode = self._parse_lock_mode(payload.get("lock_mode", LockMode.FREEZE.value))
            lock_scope = self._parse_lock_scope(payload.get("lock_scope", LockScope.SELF.value))

        source_id = payload.get("source_id") or event.entity_id or event.source
        location_id = event.location_id or payload.get("location_id")

        if not location_id and event.entity_id and self._loc_manager:
            location_id = self._loc_manager.get_entity_location(event.entity_id)

        if not location_id:
            logger.warning("Ignoring occupancy.signal without location_id")
            return None

        if self._loc_manager and self._loc_manager.get_location(location_id) is None:
            logger.warning("Ignoring occupancy.signal for unknown location: %s", location_id)
            return None

        return OccupancyEvent(
            location_id=location_id,
            event_type=event_type,
            source_id=source_id,
            timestamp=self._normalize_timestamp(event.timestamp),
            timeout=timeout,
            timeout_set=timeout_set,
            lock_mode=lock_mode,
            lock_scope=lock_scope,
        )

    def _parse_event_type(self, value: Any) -> Optional[EventType]:
        """Parse event type from value/name to EventType."""
        if isinstance(value, EventType):
            return value
        if not isinstance(value, str):
            return None

        normalized = value.strip()
        if not normalized:
            return None

        try:
            return EventType(normalized.lower())
        except ValueError:
            pass

        try:
            return EventType[normalized.upper()]
        except KeyError:
            return None

    def _parse_lock_mode(self, value: Any) -> LockMode:
        """Parse lock mode from value/name to LockMode."""
        if isinstance(value, LockMode):
            return value
        if not isinstance(value, str):
            return LockMode.FREEZE
        normalized = value.strip().lower()
        try:
            return LockMode(normalized)
        except ValueError:
            return LockMode.FREEZE

    def _parse_lock_scope(self, value: Any) -> LockScope:
        """Parse lock scope from value/name to LockScope."""
        if isinstance(value, LockScope):
            return value
        if not isinstance(value, str):
            return LockScope.SELF
        normalized = value.strip().lower()
        try:
            return LockScope(normalized)
        except ValueError:
            return LockScope.SELF

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
                    "locked_by": list(new_state.locked_by),
                    "is_locked": new_state.is_locked,
                    "lock_modes": [
                        mode.value for mode in sorted(new_state.lock_modes, key=lambda m: m.value)
                    ],
                    "direct_locks": [
                        {
                            "source_id": lock.source_id,
                            "mode": lock.mode.value,
                            "scope": lock.scope.value,
                        }
                        for lock in sorted(
                            new_state.direct_locks,
                            key=lambda lock: (lock.source_id, lock.mode.value, lock.scope.value),
                        )
                    ],
                    "contributions": [
                        {
                            "source_id": contribution.source_id,
                            "expires_at": (
                                contribution.expires_at.isoformat()
                                if contribution.expires_at
                                else None
                            ),
                        }
                        for contribution in sorted(
                            new_state.contributions,
                            key=lambda c: c.source_id,
                        )
                    ],
                    "previous_occupied": prev_state.is_occupied if prev_state else False,
                    # Stable reason format:
                    # - event:<event_type>
                    # - propagation:child:<location_id>
                    # - propagation:parent
                    # - timeout
                    "reason": transition.reason,
                },
                timestamp=datetime.now(UTC),
            )
        )

    def get_next_timeout(self, now: Optional[datetime] = None) -> Optional[datetime]:
        """Get when the next timeout check should occur."""
        if not self._engine:
            return None
        if now is None:
            now = datetime.now(UTC)
        else:
            now = self._normalize_timestamp(now)
        return self._engine._calculate_next_expiration(now)

    def check_timeouts(self, now: Optional[datetime] = None) -> None:
        """Check for expired timers and emit transitions."""
        if not self._engine:
            return

        if now is None:
            now = datetime.now(UTC)
        else:
            now = self._normalize_timestamp(now)

        result = self._engine.check_timeouts(now)
        for transition in result.transitions:
            self._emit_occupancy_changed(transition)

    def get_location_state(self, location_id: str) -> Optional[Dict[str, Any]]:
        """Get current occupancy state for a location."""
        if not self._engine or location_id not in self._engine.state:
            return None

        state = self._engine.state[location_id]
        return {
            "occupied": state.is_occupied,
            "locked_by": list(state.locked_by),
            "is_locked": state.is_locked,
            "lock_modes": [mode.value for mode in sorted(state.lock_modes, key=lambda m: m.value)],
            "direct_locks": [
                {
                    "source_id": lock.source_id,
                    "mode": lock.mode.value,
                    "scope": lock.scope.value,
                }
                for lock in sorted(
                    state.direct_locks,
                    key=lambda lock: (lock.source_id, lock.mode.value, lock.scope.value),
                )
            ],
            "contributions": [
                {
                    "source_id": contribution.source_id,
                    "expires_at": (
                        contribution.expires_at.isoformat() if contribution.expires_at else None
                    ),
                }
                for contribution in sorted(state.contributions, key=lambda c: c.source_id)
            ],
            "suspended_contributions": [
                {
                    "source_id": contribution.source_id,
                    "remaining": (
                        contribution.remaining.total_seconds()
                        if contribution.remaining is not None
                        else None
                    ),
                }
                for contribution in sorted(
                    state.suspended_contributions,
                    key=lambda c: c.source_id,
                )
            ],
        }

    def dump_state(self) -> Dict[str, Any]:
        """Export engine state for persistence."""
        if not self._engine:
            return {}
        return self._engine.export_state()

    def restore_state(self, state: Dict[str, Any]) -> None:
        """Restore engine state from persistence."""
        if not self._engine:
            logger.warning("Cannot restore state: engine not initialized")
            return

        self._engine.restore_state(state, datetime.now(UTC))

    def default_config(self) -> Dict[str, Any]:
        """Default configuration for a location."""
        return {
            "version": self.CURRENT_CONFIG_VERSION,
            "enabled": True,
            "default_timeout": 300,
            "default_trailing_timeout": 120,
            "occupancy_strategy": "independent",
            "contributes_to_parent": True,
        }

    def location_config_schema(self) -> Dict[str, Any]:
        """JSON schema for UI configuration."""
        return {
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "title": "Enable occupancy tracking",
                    "default": True,
                },
                "default_timeout": {
                    "type": "integer",
                    "title": "Default timeout (seconds)",
                    "description": "Timer duration for trigger events",
                    "minimum": 30,
                    "default": 300,
                },
                "default_trailing_timeout": {
                    "type": "integer",
                    "title": "Default trailing timeout (seconds)",
                    "description": "Trailing duration for clear events",
                    "minimum": 0,
                    "default": 120,
                },
                "occupancy_strategy": {
                    "type": "string",
                    "title": "Occupancy strategy",
                    "enum": ["independent", "follow_parent"],
                    "default": "independent",
                },
                "contributes_to_parent": {
                    "type": "boolean",
                    "title": "Contribute to parent",
                    "default": True,
                },
            },
        }

    # --- Events API ---

    def trigger(
        self,
        location_id: str,
        source_id: str,
        timeout: Any = _UNSET,
        now: Optional[datetime] = None,
    ) -> None:
        """Send a TRIGGER event (source contributes occupancy)."""
        assert self._engine is not None
        if now is None:
            now = datetime.now(UTC)
        else:
            now = self._normalize_timestamp(now)

        timeout_set = timeout is not _UNSET
        timeout_value: int | None
        if timeout is _UNSET:
            timeout_value = None
        else:
            self._validate_timeout_value("timeout", timeout, allow_none=True)
            timeout_value = None if timeout is None else int(timeout)

        event = OccupancyEvent(
            location_id=location_id,
            event_type=EventType.TRIGGER,
            source_id=source_id,
            timestamp=now,
            timeout=timeout_value,
            timeout_set=timeout_set,
        )
        result = self._engine.handle_event(event, now)
        for transition in result.transitions:
            self._emit_occupancy_changed(transition)

    def clear(
        self,
        location_id: str,
        source_id: str,
        trailing_timeout: Any = _UNSET,
        now: Optional[datetime] = None,
    ) -> None:
        """Send a CLEAR event (source stops contributing)."""
        assert self._engine is not None
        if now is None:
            now = datetime.now(UTC)
        else:
            now = self._normalize_timestamp(now)

        timeout_set = trailing_timeout is not _UNSET
        timeout_value: int | None
        if trailing_timeout is _UNSET:
            timeout_value = None
        else:
            self._validate_timeout_value("trailing_timeout", trailing_timeout, allow_none=True)
            timeout_value = None if trailing_timeout is None else int(trailing_timeout)

        event = OccupancyEvent(
            location_id=location_id,
            event_type=EventType.CLEAR,
            source_id=source_id,
            timestamp=now,
            timeout=timeout_value,
            timeout_set=timeout_set,
        )
        result = self._engine.handle_event(event, now)
        for transition in result.transitions:
            self._emit_occupancy_changed(transition)

    # --- Commands API ---

    def vacate(self, location_id: str, now: Optional[datetime] = None) -> None:
        """Force location vacant immediately."""
        assert self._engine is not None
        if now is None:
            now = datetime.now(UTC)
        else:
            now = self._normalize_timestamp(now)

        event = OccupancyEvent(
            location_id=location_id,
            event_type=EventType.VACATE,
            source_id="command",
            timestamp=now,
        )
        result = self._engine.handle_event(event, now)
        for transition in result.transitions:
            self._emit_occupancy_changed(transition)

    def lock(
        self,
        location_id: str,
        source_id: str,
        mode: LockMode | str = LockMode.FREEZE,
        scope: LockScope | str = LockScope.SELF,
        now: Optional[datetime] = None,
    ) -> None:
        """Apply/update a lock directive for a source."""
        assert self._engine is not None
        if now is None:
            now = datetime.now(UTC)
        else:
            now = self._normalize_timestamp(now)

        parsed_mode = self._parse_lock_mode(mode)
        parsed_scope = self._parse_lock_scope(scope)

        event = OccupancyEvent(
            location_id=location_id,
            event_type=EventType.LOCK,
            source_id=source_id,
            timestamp=now,
            lock_mode=parsed_mode,
            lock_scope=parsed_scope,
        )
        result = self._engine.handle_event(event, now)
        for transition in result.transitions:
            self._emit_occupancy_changed(transition)

    def unlock(self, location_id: str, source_id: str, now: Optional[datetime] = None) -> None:
        """Remove lock from this source."""
        assert self._engine is not None
        if now is None:
            now = datetime.now(UTC)
        else:
            now = self._normalize_timestamp(now)

        event = OccupancyEvent(
            location_id=location_id,
            event_type=EventType.UNLOCK,
            source_id=source_id,
            timestamp=now,
        )
        result = self._engine.handle_event(event, now)
        for transition in result.transitions:
            self._emit_occupancy_changed(transition)

    def unlock_all(self, location_id: str, now: Optional[datetime] = None) -> None:
        """Force clear all locks."""
        assert self._engine is not None
        if now is None:
            now = datetime.now(UTC)
        else:
            now = self._normalize_timestamp(now)

        event = OccupancyEvent(
            location_id=location_id,
            event_type=EventType.UNLOCK_ALL,
            source_id="force_unlock",
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
        """Get when location will truly become vacant (considers descendants)."""
        if not self._engine:
            return None
        if now is None:
            now = datetime.now(UTC)
        else:
            now = self._normalize_timestamp(now)
        return self._engine.get_effective_timeout(location_id, now)

    def vacate_area(
        self,
        location_id: str,
        source_id: str,
        include_locked: bool = False,
        now: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Vacate a location and all descendants."""
        if not self._engine:
            return []

        if now is None:
            now = datetime.now(UTC)
        else:
            now = self._normalize_timestamp(now)

        result = self._engine.vacate_area(location_id, source_id, now, include_locked)
        for transition in result.transitions:
            self._emit_occupancy_changed(transition)

        return [
            {
                "location_id": t.location_id,
                "was_occupied": t.previous_state.is_occupied,
                "is_occupied": t.new_state.is_occupied,
                "reason": t.reason,
            }
            for t in result.transitions
        ]

    def on_location_config_changed(self, location_id: str, config: Dict) -> None:
        """Rebuild engine when location config changes."""
        self._rebuild_engine_preserving_state(datetime.now(UTC))

    def _rebuild_engine_preserving_state(self, now: datetime) -> None:
        """Rebuild occupancy engine from current topology and restore runtime state."""
        if not self._engine:
            return
        now = self._normalize_timestamp(now)
        snapshot = self._engine.export_state()
        self._engine = OccupancyEngine(self._build_location_configs())
        self._engine.restore_state(snapshot, now)

    @staticmethod
    def _normalize_timestamp(ts: datetime) -> datetime:
        """Normalize inbound timestamps to UTC-aware datetimes."""
        if ts.tzinfo is None:
            return ts.replace(tzinfo=UTC)
        return ts.astimezone(UTC)

    @staticmethod
    def _validate_timeout_value(
        field_name: str,
        value: object,
        *,
        allow_none: bool,
    ) -> None:
        """Validate timeout-like values for public API methods."""
        if value is None:
            if allow_none:
                return
            raise ValueError(f"{field_name} cannot be None")
        if not isinstance(value, int):
            raise ValueError(f"{field_name} must be an integer number of seconds")
        if value < 0:
            raise ValueError(f"{field_name} must be >= 0")
