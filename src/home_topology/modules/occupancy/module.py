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
_GROUP_AUTHORITY_PREFIX = "__occupancy_group__:"
_GROUP_MEMBER_SOURCE_PREFIX = "__group_member__:"


class OccupancyModule(LocationModule):
    """Occupancy tracking module (v3.0)."""

    def __init__(self) -> None:
        self._bus: Optional[EventBus] = None
        self._loc_manager: Optional[LocationManager] = None
        self._engine: Optional[OccupancyEngine] = None
        self._group_authority_by_member: dict[str, str] = {}
        self._group_members_by_authority: dict[str, list[str]] = {}
        self._group_id_by_authority: dict[str, str] = {}
        self._last_transition_by_location: dict[str, dict[str, Any]] = {}

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
        self._group_authority_by_member = {}
        self._group_members_by_authority = {}
        self._group_id_by_authority = {}

        raw_entries: list[dict[str, Any]] = []

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

            occupancy_group_id = self._normalize_group_id(
                config_dict.get("occupancy_group_id") if config_dict else None
            )
            raw_entries.append(
                {
                    "id": location.id,
                    "parent_id": location.parent_id,
                    "occupancy_group_id": occupancy_group_id,
                    "occupancy_strategy": strategy,
                    "contributes_to_parent": contributes,
                    "default_timeout": default_timeout,
                    "default_trailing_timeout": default_trailing_timeout,
                }
            )

        grouped_parent_ids: dict[str, set[str | None]] = {}
        grouped_defaults: dict[str, tuple[int, int]] = {}
        for entry in raw_entries:
            occupancy_group_id = entry["occupancy_group_id"]
            if occupancy_group_id is None:
                continue
            authority_id = self._group_authority_location_id(occupancy_group_id)
            self._group_authority_by_member[entry["id"]] = authority_id
            self._group_members_by_authority.setdefault(authority_id, []).append(entry["id"])
            self._group_id_by_authority[authority_id] = occupancy_group_id
            grouped_parent_ids.setdefault(authority_id, set()).add(entry["parent_id"])
            grouped_defaults.setdefault(
                authority_id,
                (
                    int(entry["default_timeout"]),
                    int(entry["default_trailing_timeout"]),
                ),
            )

        for entry in raw_entries:
            member_authority_id = self._group_authority_by_member.get(entry["id"])
            if member_authority_id is not None:
                configs.append(
                    LocationConfig(
                        id=entry["id"],
                        parent_id=member_authority_id,
                        occupancy_group_id=self._group_id_by_authority.get(member_authority_id),
                        occupancy_strategy=OccupancyStrategy.FOLLOW_PARENT,
                        contributes_to_parent=False,
                        default_timeout=int(entry["default_timeout"]),
                        default_trailing_timeout=int(entry["default_trailing_timeout"]),
                    )
                )
                continue

            configs.append(
                LocationConfig(
                    id=entry["id"],
                    parent_id=entry["parent_id"],
                    occupancy_group_id=None,
                    occupancy_strategy=entry["occupancy_strategy"],
                    contributes_to_parent=entry["contributes_to_parent"],
                    default_timeout=int(entry["default_timeout"]),
                    default_trailing_timeout=int(entry["default_trailing_timeout"]),
                )
            )

        for authority_id, member_ids in sorted(self._group_members_by_authority.items()):
            parent_ids = grouped_parent_ids.get(authority_id, set())
            authority_parent_id = next(iter(parent_ids)) if len(parent_ids) == 1 else None
            default_timeout, default_trailing_timeout = grouped_defaults.get(
                authority_id, (300, 120)
            )
            configs.append(
                LocationConfig(
                    id=authority_id,
                    parent_id=authority_parent_id,
                    occupancy_group_id=self._group_id_by_authority.get(authority_id),
                    occupancy_strategy=OccupancyStrategy.INDEPENDENT,
                    contributes_to_parent=True,
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

        # Integration contract: configured HA "off" with zero trailing vacates the whole room.
        if (
            bool(payload.get("authoritative_vacant"))
            and event_type == EventType.CLEAR
            and timeout_set
            and timeout == 0
        ):
            event_type = EventType.VACATE
            timeout_set = False
            timeout = None

        resolved_location_id, resolved_source_id, timeout, timeout_set, lock_scope = (
            self._resolve_group_event(
                location_id,
                str(source_id),
                event_type=event_type,
                timeout=timeout,
                timeout_set=timeout_set,
                lock_scope=lock_scope,
            )
        )

        return OccupancyEvent(
            location_id=resolved_location_id,
            event_type=event_type,
            source_id=resolved_source_id,
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

        aliases = {
            "vacant": EventType.VACATE,
            "unoccupied": EventType.VACATE,
        }
        lowered = normalized.lower()
        if lowered in aliases:
            return aliases[lowered]

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
        location_id = transition.location_id
        event_timestamp = datetime.now(UTC)
        if self._is_group_authority_location(location_id):
            for member_id in self._group_members_by_authority.get(location_id, []):
                latest_transition = self._serialize_transition_explanation(
                    transition,
                    public_location_id=member_id,
                    changed_at=event_timestamp,
                )
                self._last_transition_by_location[member_id] = latest_transition
                payload = self._serialize_public_state(
                    member_id,
                    state_override=transition.new_state,
                    include_explanation=False,
                )
                payload["previous_occupied"] = (
                    transition.previous_state.is_occupied if transition.previous_state else False
                )
                payload["reason"] = transition.reason
                self._bus.publish(
                    Event(
                        type="occupancy.changed",
                        source="occupancy",
                        location_id=member_id,
                        payload=payload,
                        timestamp=event_timestamp,
                    )
                )
            return

        if location_id in self._group_authority_by_member:
            return

        latest_transition = self._serialize_transition_explanation(
            transition,
            public_location_id=location_id,
            changed_at=event_timestamp,
        )
        self._last_transition_by_location[location_id] = latest_transition
        payload = self._serialize_public_state(
            location_id,
            state_override=transition.new_state,
            include_explanation=False,
        )
        payload["previous_occupied"] = (
            transition.previous_state.is_occupied if transition.previous_state else False
        )
        payload["reason"] = transition.reason

        self._bus.publish(
            Event(
                type="occupancy.changed",
                source="occupancy",
                location_id=location_id,
                payload=payload,
                timestamp=event_timestamp,
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
        if not self._engine:
            return None
        authority_id = self._group_authority_by_member.get(location_id)
        runtime_location_id = authority_id or location_id
        if runtime_location_id not in self._engine.state:
            return None

        state = self._engine.state[runtime_location_id]
        return self._serialize_public_state(location_id, state_override=state)

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
            "occupancy_group_id": None,
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
                "occupancy_group_id": {
                    "type": ["string", "null"],
                    "title": "Occupancy group ID",
                    "default": None,
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
        event = self._rewrite_public_event(event)
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
        event = self._rewrite_public_event(event)
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
        event = self._rewrite_public_event(event)
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
        event = self._rewrite_public_event(event)
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
        event = self._rewrite_public_event(event)
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
        event = self._rewrite_public_event(event)
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
        runtime_location_id = self._group_authority_by_member.get(location_id, location_id)
        return self._engine.get_effective_timeout(runtime_location_id, now)

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

        runtime_location_id = self._group_authority_by_member.get(location_id, location_id)
        result = self._engine.vacate_area(runtime_location_id, source_id, now, include_locked)
        for transition in result.transitions:
            self._emit_occupancy_changed(transition)

        public_transitions: list[Dict[str, Any]] = []
        seen_locations: set[str] = set()
        for transition in result.transitions:
            if self._is_group_authority_location(transition.location_id):
                for member_id in self._group_members_by_authority.get(transition.location_id, []):
                    if member_id in seen_locations:
                        continue
                    seen_locations.add(member_id)
                    public_transitions.append(
                        {
                            "location_id": member_id,
                            "was_occupied": transition.previous_state.is_occupied,
                            "is_occupied": transition.new_state.is_occupied,
                            "reason": transition.reason,
                        }
                    )
                continue
            if transition.location_id in self._group_authority_by_member:
                continue
            if transition.location_id in seen_locations:
                continue
            seen_locations.add(transition.location_id)
            public_transitions.append(
                {
                    "location_id": transition.location_id,
                    "was_occupied": transition.previous_state.is_occupied,
                    "is_occupied": transition.new_state.is_occupied,
                    "reason": transition.reason,
                }
            )
        return public_transitions

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

    @staticmethod
    def _normalize_group_id(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _group_authority_location_id(group_id: str) -> str:
        return f"{_GROUP_AUTHORITY_PREFIX}{group_id}"

    def _is_group_authority_location(self, location_id: str) -> bool:
        return location_id.startswith(_GROUP_AUTHORITY_PREFIX)

    @staticmethod
    def _group_member_source_id(origin_location_id: str, source_id: str) -> str:
        return f"{_GROUP_MEMBER_SOURCE_PREFIX}{origin_location_id}::{source_id}"

    @staticmethod
    def _parse_group_member_source_id(source_id: str) -> tuple[str, str] | None:
        if not source_id.startswith(_GROUP_MEMBER_SOURCE_PREFIX):
            return None
        remainder = source_id[len(_GROUP_MEMBER_SOURCE_PREFIX) :]
        origin_location_id, separator, origin_source_id = remainder.partition("::")
        if not separator or not origin_location_id or not origin_source_id:
            return None
        return origin_location_id, origin_source_id

    def _config_for_location(self, location_id: str) -> Dict[str, Any]:
        if self._loc_manager is None:
            return {}
        config = self._loc_manager.get_module_config(location_id, self.id)
        return config if isinstance(config, dict) else {}

    def _resolve_group_event(
        self,
        location_id: str,
        source_id: str,
        *,
        event_type: EventType,
        timeout: int | None,
        timeout_set: bool,
        lock_scope: LockScope,
    ) -> tuple[str, str, int | None, bool, LockScope]:
        authority_id = self._group_authority_by_member.get(location_id)
        if authority_id is None:
            return location_id, source_id, timeout, timeout_set, lock_scope

        resolved_timeout = timeout
        resolved_timeout_set = timeout_set
        if not timeout_set and event_type == EventType.TRIGGER:
            resolved_timeout = int(
                self._config_for_location(location_id).get("default_timeout", 300)
            )
            resolved_timeout_set = True
        elif not timeout_set and event_type == EventType.CLEAR:
            resolved_timeout = int(
                self._config_for_location(location_id).get("default_trailing_timeout", 120)
            )
            resolved_timeout_set = True

        resolved_scope = lock_scope
        if event_type == EventType.LOCK:
            resolved_scope = LockScope.SUBTREE

        return (
            authority_id,
            self._group_member_source_id(location_id, source_id),
            resolved_timeout,
            resolved_timeout_set,
            resolved_scope,
        )

    def _rewrite_public_event(self, event: OccupancyEvent) -> OccupancyEvent:
        (
            resolved_location_id,
            resolved_source_id,
            resolved_timeout,
            resolved_timeout_set,
            resolved_lock_scope,
        ) = self._resolve_group_event(
            event.location_id,
            event.source_id,
            event_type=event.event_type,
            timeout=event.timeout,
            timeout_set=event.timeout_set,
            lock_scope=event.lock_scope,
        )
        return OccupancyEvent(
            location_id=resolved_location_id,
            event_type=event.event_type,
            source_id=resolved_source_id,
            timestamp=event.timestamp,
            timeout=resolved_timeout,
            timeout_set=resolved_timeout_set,
            lock_mode=event.lock_mode,
            lock_scope=resolved_lock_scope,
        )

    def _serialize_public_state(
        self,
        location_id: str,
        *,
        state_override: Any,
        latest_transition: Dict[str, Any] | None = None,
        include_explanation: bool = True,
    ) -> Dict[str, Any]:
        authority_id = self._group_authority_by_member.get(location_id)
        occupancy_group_id: str | None = None
        if authority_id is not None:
            occupancy_group_id = self._group_id_by_authority.get(authority_id)

        payload: Dict[str, Any] = {
            "occupied": state_override.is_occupied,
            "locked_by": list(state_override.locked_by),
            "is_locked": state_override.is_locked,
            "lock_modes": [
                mode.value for mode in sorted(state_override.lock_modes, key=lambda m: m.value)
            ],
            "direct_locks": [
                self._serialize_lock(lock, occupancy_group_id)
                for lock in sorted(
                    state_override.direct_locks,
                    key=lambda lock: (lock.source_id, lock.mode.value, lock.scope.value),
                )
            ],
            "contributions": [
                self._serialize_contribution(contribution, occupancy_group_id)
                for contribution in sorted(state_override.contributions, key=lambda c: c.source_id)
            ],
            "suspended_contributions": [
                self._serialize_suspended_contribution(contribution, occupancy_group_id)
                for contribution in sorted(
                    state_override.suspended_contributions,
                    key=lambda c: c.source_id,
                )
            ],
            "occupancy_group_id": occupancy_group_id,
        }
        if include_explanation:
            payload["explanation"] = self._build_public_explanation(
                location_id,
                state_override=state_override,
                occupancy_group_id=occupancy_group_id,
                latest_transition=latest_transition,
            )
        return payload

    def _build_public_explanation(
        self,
        location_id: str,
        *,
        state_override: Any,
        occupancy_group_id: str | None,
        latest_transition: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Build a machine-readable explanation for the current occupancy state."""
        authority_id = self._group_authority_by_member.get(location_id)
        holders = [
            self._serialize_explanation_holder(contribution, occupancy_group_id)
            for contribution in sorted(state_override.contributions, key=lambda c: c.source_id)
        ]
        suspended_holds = [
            self._serialize_suspended_contribution(contribution, occupancy_group_id)
            for contribution in sorted(
                state_override.suspended_contributions,
                key=lambda c: c.source_id,
            )
        ]

        if state_override.is_occupied and not holders and state_override.is_locked:
            holders.append(
                {
                    "kind": "lock",
                    "locked_by": list(state_override.locked_by),
                    "lock_modes": [
                        mode.value
                        for mode in sorted(state_override.lock_modes, key=lambda m: m.value)
                    ],
                }
            )

        explanation: dict[str, Any] = {
            "version": 1,
            "basis": self._explanation_basis(
                state_override,
                authority_id=authority_id,
            ),
            "held_by": holders if state_override.is_occupied else [],
        }

        projected_from = self._projected_from(location_id, authority_id, occupancy_group_id)
        if projected_from is not None:
            explanation["projected_from"] = projected_from

        transition = latest_transition or self._last_transition_by_location.get(location_id)
        if transition is not None:
            explanation["latest_transition"] = transition

        if state_override.is_locked:
            explanation["locks"] = {
                "locked_by": list(state_override.locked_by),
                "lock_modes": [
                    mode.value for mode in sorted(state_override.lock_modes, key=lambda m: m.value)
                ],
                "direct_locks": [
                    self._serialize_lock(lock, occupancy_group_id)
                    for lock in sorted(
                        state_override.direct_locks,
                        key=lambda lock: (lock.source_id, lock.mode.value, lock.scope.value),
                    )
                ],
            }

        if suspended_holds:
            explanation["suspended_holds"] = suspended_holds

        return explanation

    def _explanation_basis(self, state: Any, *, authority_id: str | None) -> str:
        """Return the current-state basis code for an explanation."""
        if not state.is_occupied:
            return "no_active_holds"
        if authority_id is not None:
            return "occupancy_group"

        source_ids = {contribution.source_id for contribution in state.contributions}
        if any(source_id.startswith("__child__:") for source_id in source_ids):
            return "child_rollup"
        if any(source_id.startswith("__follow_parent__:") for source_id in source_ids):
            return "follow_parent"
        if any(source_id.startswith("__lock_hold__:") for source_id in source_ids):
            return "lock_hold"
        if not source_ids and state.is_locked:
            return "lock_freeze"
        if source_ids:
            return "direct"
        return "retained_state"

    def _projected_from(
        self,
        location_id: str,
        authority_id: str | None,
        occupancy_group_id: str | None,
    ) -> Dict[str, Any] | None:
        """Return projection metadata for public locations backed by runtime authority."""
        if authority_id is None:
            return None
        return {
            "kind": "occupancy_group",
            "group_id": occupancy_group_id,
            "authority_location_id": authority_id,
            "members": list(self._group_members_by_authority.get(authority_id, [location_id])),
        }

    def _serialize_explanation_holder(
        self,
        contribution: Any,
        occupancy_group_id: str | None,
    ) -> Dict[str, Any]:
        """Serialize one active holder with stable provenance fields."""
        item = self._serialize_contribution(contribution, occupancy_group_id)
        source_id = contribution.source_id
        item["kind"] = "source"

        if source_id.startswith("__child__:"):
            item["kind"] = "child"
            item["origin_location_id"] = source_id[len("__child__:") :]
        elif source_id.startswith("__follow_parent__:"):
            item["kind"] = "parent"
            item["origin_location_id"] = source_id[len("__follow_parent__:") :]
        elif source_id.startswith("__lock_hold__:"):
            item["kind"] = "lock_hold"
            item["origin_location_id"] = source_id[len("__lock_hold__:") :]

        parsed = self._parse_group_member_source_id(source_id)
        if parsed is not None:
            origin_location_id, origin_source_id = parsed
            item["kind"] = "source"
            item["origin_location_id"] = origin_location_id
            item["origin_source_id"] = origin_source_id
            item["via_occupancy_group"] = occupancy_group_id

        return item

    def _serialize_transition_explanation(
        self,
        transition: Any,
        *,
        public_location_id: str,
        changed_at: datetime,
    ) -> Dict[str, Any]:
        """Serialize the latest transition with cause and source provenance."""
        item: dict[str, Any] = {
            "event": "occupied" if transition.new_state.is_occupied else "vacant",
            "previous_occupied": (
                transition.previous_state.is_occupied if transition.previous_state else False
            ),
            "reason": transition.reason,
            "cause": self._transition_cause(transition.reason),
            "location_id": public_location_id,
            "changed_at": changed_at.isoformat(),
        }

        cause_event = getattr(transition, "event", None)
        if cause_event is not None:
            item["signal_event"] = cause_event.event_type.value
            item["source_id"] = cause_event.source_id
            item["runtime_location_id"] = cause_event.location_id
            parsed = self._parse_group_member_source_id(cause_event.source_id)
            if parsed is not None:
                origin_location_id, origin_source_id = parsed
                item["origin_location_id"] = origin_location_id
                item["origin_source_id"] = origin_source_id
                item["via_occupancy_group"] = self._group_id_by_authority.get(
                    cause_event.location_id
                )

        propagated_from_child = getattr(transition, "propagated_from_child", None)
        if propagated_from_child:
            item["origin_location_id"] = propagated_from_child
        if getattr(transition, "propagated_parent", False):
            item["projected_from_parent"] = True

        return item

    @staticmethod
    def _transition_cause(reason: str) -> str:
        """Normalize a transition reason string to a stable cause code."""
        if reason.startswith("event:"):
            return reason.split(":", 1)[1] or "event"
        if reason.startswith("propagation:child:"):
            return "child"
        if reason == "propagation:parent":
            return "parent"
        if reason == "timeout":
            return "timeout"
        return reason or "unknown"

    def _serialize_contribution(
        self,
        contribution: Any,
        occupancy_group_id: str | None,
    ) -> Dict[str, Any]:
        item: Dict[str, Any] = {
            "source_id": contribution.source_id,
            "expires_at": contribution.expires_at.isoformat() if contribution.expires_at else None,
        }
        if getattr(contribution, "exit_grace", False):
            item["exit_grace"] = True
        parsed = self._parse_group_member_source_id(contribution.source_id)
        if parsed is not None:
            origin_location_id, origin_source_id = parsed
            item["origin_location_id"] = origin_location_id
            item["origin_source_id"] = origin_source_id
            item["via_occupancy_group"] = occupancy_group_id
        return item

    def _serialize_suspended_contribution(
        self,
        contribution: Any,
        occupancy_group_id: str | None,
    ) -> Dict[str, Any]:
        item: Dict[str, Any] = {
            "source_id": contribution.source_id,
            "remaining": (
                contribution.remaining.total_seconds()
                if contribution.remaining is not None
                else None
            ),
        }
        parsed = self._parse_group_member_source_id(contribution.source_id)
        if parsed is not None:
            origin_location_id, origin_source_id = parsed
            item["origin_location_id"] = origin_location_id
            item["origin_source_id"] = origin_source_id
            item["via_occupancy_group"] = occupancy_group_id
        return item

    def _serialize_lock(
        self,
        lock: Any,
        occupancy_group_id: str | None,
    ) -> Dict[str, Any]:
        item: Dict[str, Any] = {
            "source_id": lock.source_id,
            "mode": lock.mode.value,
            "scope": lock.scope.value,
        }
        parsed = self._parse_group_member_source_id(lock.source_id)
        if parsed is not None:
            origin_location_id, origin_source_id = parsed
            item["origin_location_id"] = origin_location_id
            item["origin_source_id"] = origin_source_id
            item["via_occupancy_group"] = occupancy_group_id
        return item
