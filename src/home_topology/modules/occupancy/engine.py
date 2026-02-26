"""The core logic engine for occupancy (v3.0)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from .models import (
    REASON_EVENT_PREFIX,
    REASON_PROPAGATION_CHILD_PREFIX,
    REASON_PROPAGATION_PARENT,
    REASON_TIMEOUT,
    EngineResult,
    EventType,
    LocationConfig,
    LocationRuntimeState,
    LockDirective,
    LockMode,
    LockScope,
    OccupancyEvent,
    OccupancyStrategy,
    SourceContribution,
    StateTransition,
    SuspendedContribution,
)

_LOGGER = logging.getLogger(__name__)

_CHILD_PREFIX = "__child__"
_FOLLOW_PREFIX = "__follow_parent__"
_LOCK_HOLD_PREFIX = "__lock_hold__"


class OccupancyEngine:
    """The functional core of the occupancy system."""

    def __init__(
        self,
        configs: list[LocationConfig],
        initial_state: dict[str, LocationRuntimeState] | None = None,
    ) -> None:
        self.configs: dict[str, LocationConfig] = {c.id: c for c in configs}

        if initial_state:
            self.state = initial_state.copy()
            for c in configs:
                if c.id not in self.state:
                    self.state[c.id] = LocationRuntimeState()
        else:
            self.state = {c.id: LocationRuntimeState() for c in configs}

        self.children_map: dict[str, list[str]] = {}
        for c in configs:
            if c.parent_id:
                self.children_map.setdefault(c.parent_id, []).append(c.id)

    def handle_event(self, event: OccupancyEvent, now: datetime) -> EngineResult:
        """Process one event and return transitions + scheduling hint."""
        if event.location_id not in self.configs:
            _LOGGER.warning("Event for unknown location: %s", event.location_id)
            return EngineResult(next_expiration=self._calculate_next_expiration(now))

        transitions: list[StateTransition] = []
        self._process_location_update(event.location_id, event, now, transitions)

        # Lock scope can affect descendants even without direct events there.
        if event.event_type in (EventType.LOCK, EventType.UNLOCK, EventType.UNLOCK_ALL):
            for child_id in self._get_descendants(event.location_id):
                self._process_location_update(child_id, None, now, transitions)

        return EngineResult(
            next_expiration=self._calculate_next_expiration(now),
            transitions=transitions,
        )

    def check_timeouts(self, now: datetime) -> EngineResult:
        """Expire timed contributions and propagate resulting state transitions."""
        transitions: list[StateTransition] = []

        for location_id in self.configs:
            self._process_location_update(location_id, None, now, transitions)

        return EngineResult(
            next_expiration=self._calculate_next_expiration(now),
            transitions=transitions,
        )

    def _process_location_update(
        self,
        location_id: str,
        event: OccupancyEvent | None,
        now: datetime,
        transitions: list[StateTransition],
        propagated_from_child: str | None = None,
        propagated_parent: bool = False,
    ) -> None:
        state_changed = self._evaluate_state(
            location_id,
            event,
            now,
            transitions,
            propagated_from_child=propagated_from_child,
            propagated_parent=propagated_parent,
        )
        if not state_changed:
            return

        config = self.configs[location_id]

        # Bubble up both occupancy and vacancy so parent state stays derived from children.
        if config.parent_id:
            self._process_location_update(
                config.parent_id,
                event=None,
                now=now,
                transitions=transitions,
                propagated_from_child=location_id,
                propagated_parent=False,
            )

        # FOLLOW_PARENT dependents mirror parent state changes.
        for child_id in self.children_map.get(location_id, []):
            child_config = self.configs[child_id]
            if child_config.occupancy_strategy == OccupancyStrategy.FOLLOW_PARENT:
                self._process_location_update(
                    child_id,
                    event=None,
                    now=now,
                    transitions=transitions,
                    propagated_from_child=None,
                    propagated_parent=True,
                )

    def _evaluate_state(
        self,
        location_id: str,
        event: OccupancyEvent | None,
        now: datetime,
        transitions: list[StateTransition],
        propagated_from_child: str | None,
        propagated_parent: bool,
    ) -> bool:
        config = self.configs[location_id]
        current_state = self.state[location_id]

        direct_lock_map = self._direct_lock_map(current_state.direct_locks)
        if event and event.event_type == EventType.LOCK:
            direct_lock_map[event.source_id] = LockDirective(
                source_id=event.source_id,
                mode=event.lock_mode,
                scope=event.lock_scope,
            )
        elif event and event.event_type == EventType.UNLOCK:
            direct_lock_map.pop(event.source_id, None)
        elif event and event.event_type == EventType.UNLOCK_ALL:
            direct_lock_map.clear()

        effective_locks = self._effective_locks(location_id, direct_lock_map)
        next_locked_by = {directive.source_id for directive in effective_locks}
        next_lock_modes = {directive.mode for directive in effective_locks}

        prev_freeze = LockMode.FREEZE in current_state.lock_modes
        next_freeze = LockMode.FREEZE in next_lock_modes
        contrib_map = self._contrib_map(current_state.contributions)
        suspended_map = self._suspended_map(current_state.suspended_contributions)

        # Remove expired timed contributions.
        self._drop_expired(contrib_map, now)

        if not prev_freeze and next_freeze:
            suspended_map = {
                source_id: (
                    None if expires_at is None else max(timedelta(seconds=0), expires_at - now)
                )
                for source_id, expires_at in contrib_map.items()
            }
            contrib_map = {}
        elif prev_freeze and not next_freeze:
            contrib_map = self._resume_contributions(suspended_map, now)
            suspended_map = {}

        # Remove synthetic lock holds when their mode no longer applies.
        if LockMode.BLOCK_VACANT not in next_lock_modes:
            for source_id in [
                sid for sid in contrib_map if sid.startswith(f"{_LOCK_HOLD_PREFIX}:")
            ]:
                contrib_map.pop(source_id, None)

        # Freeze mode ignores occupancy-changing events until unlocked.
        if (
            next_freeze
            and event is not None
            and event.event_type not in (EventType.LOCK, EventType.UNLOCK, EventType.UNLOCK_ALL)
        ):
            return False

        if event and event.event_type == EventType.VACATE:
            contrib_map.clear()
            suspended_map.clear()

        elif event and event.event_type == EventType.TRIGGER:
            if config.occupancy_strategy == OccupancyStrategy.FOLLOW_PARENT:
                # FOLLOW_PARENT is strict: direct occupancy events are ignored.
                pass
            else:
                timeout_value = self._get_trigger_timeout(event, config)
                expires_at = (
                    None if timeout_value is None else now + timedelta(seconds=timeout_value)
                )
                contrib_map[event.source_id] = expires_at

        elif event and event.event_type == EventType.CLEAR:
            if config.occupancy_strategy == OccupancyStrategy.FOLLOW_PARENT:
                # FOLLOW_PARENT is strict: direct occupancy events are ignored.
                pass
            elif event.source_id in contrib_map:
                trailing_timeout = self._get_clear_timeout(event, config)
                if trailing_timeout > 0:
                    contrib_map[event.source_id] = now + timedelta(seconds=trailing_timeout)
                else:
                    del contrib_map[event.source_id]

        # Maintain parent synthetic contribution for a child that changed.
        if propagated_from_child and config.occupancy_strategy != OccupancyStrategy.FOLLOW_PARENT:
            child_cfg = self.configs.get(propagated_from_child)
            child_state = self.state.get(propagated_from_child)
            if child_cfg and child_state:
                child_source = self._child_source_id(propagated_from_child)
                if child_cfg.contributes_to_parent and child_state.is_occupied:
                    contrib_map[child_source] = self.get_effective_timeout(
                        propagated_from_child, now
                    )
                else:
                    contrib_map.pop(child_source, None)

        # Enforce strict FOLLOW_PARENT behavior.
        if config.occupancy_strategy == OccupancyStrategy.FOLLOW_PARENT:
            follow_source = self._follow_source_id(config.parent_id)
            contrib_map = {
                source_id: expires_at
                for source_id, expires_at in contrib_map.items()
                if source_id == follow_source
            }
            parent_state = self.state.get(config.parent_id) if config.parent_id else None
            if parent_state and parent_state.is_occupied and follow_source:
                # FOLLOW_PARENT mirrors occupancy state only; it does not create independent timers.
                contrib_map[follow_source] = None
            else:
                contrib_map.pop(follow_source, None)

        if LockMode.BLOCK_OCCUPIED in next_lock_modes:
            contrib_map.clear()
            suspended_map.clear()
            next_is_occupied = False
        else:
            if LockMode.BLOCK_VACANT in next_lock_modes and not contrib_map:
                contrib_map[f"{_LOCK_HOLD_PREFIX}:{location_id}"] = None
            if LockMode.BLOCK_VACANT in next_lock_modes:
                next_is_occupied = True
            elif next_freeze:
                next_is_occupied = current_state.is_occupied
            else:
                next_is_occupied = bool(contrib_map)

        next_state = LocationRuntimeState(
            is_occupied=next_is_occupied,
            contributions=frozenset(
                SourceContribution(source_id=sid, expires_at=exp)
                for sid, exp in sorted(contrib_map.items())
            ),
            suspended_contributions=frozenset(
                SuspendedContribution(source_id=sid, remaining=remaining)
                for sid, remaining in sorted(suspended_map.items())
            ),
            locked_by=frozenset(next_locked_by),
            lock_modes=frozenset(next_lock_modes),
            direct_locks=frozenset(direct_lock_map.values()),
        )

        if next_state == current_state:
            return False

        self.state[location_id] = next_state
        transitions.append(
            StateTransition(
                location_id=location_id,
                previous_state=current_state,
                new_state=next_state,
                reason=self._reason_for(event, propagated_from_child, propagated_parent),
            )
        )
        return True

    def _calculate_next_expiration(self, now: datetime) -> datetime | None:
        """Find the earliest future timeout across all unlocked locations."""
        next_exp: datetime | None = None

        for state in self.state.values():
            if LockMode.FREEZE in state.lock_modes:
                continue

            for contribution in state.contributions:
                if contribution.expires_at and contribution.expires_at > now:
                    if next_exp is None or contribution.expires_at < next_exp:
                        next_exp = contribution.expires_at

        return next_exp

    def _get_trigger_timeout(
        self,
        event: OccupancyEvent,
        config: LocationConfig,
    ) -> int | None:
        """Resolve TRIGGER timeout."""
        if event.timeout_set:
            return event.timeout
        return config.default_timeout

    def _get_clear_timeout(
        self,
        event: OccupancyEvent,
        config: LocationConfig,
    ) -> int:
        """Resolve CLEAR trailing timeout."""
        if event.timeout_set:
            # Explicit None for CLEAR means immediate clear.
            return 0 if event.timeout is None else event.timeout
        return config.default_trailing_timeout

    def export_state(self) -> dict[str, dict[str, Any]]:
        """Create a JSON-serializable state dump."""
        dump: dict[str, dict[str, Any]] = {}

        for loc_id, state in self.state.items():
            if (
                not state.is_occupied
                and not state.direct_locks
                and not state.contributions
                and not state.suspended_contributions
            ):
                continue

            dump[loc_id] = {
                "is_occupied": state.is_occupied,
                "locked_by": list(state.locked_by),
                "lock_modes": [
                    mode.value for mode in sorted(state.lock_modes, key=lambda m: m.value)
                ],
                "direct_locks": [
                    {
                        "source_id": lock.source_id,
                        "mode": lock.mode.value,
                        "scope": lock.scope.value,
                    }
                    for lock in sorted(
                        state.direct_locks,
                        key=lambda lock_item: (
                            lock_item.source_id,
                            lock_item.mode.value,
                            lock_item.scope.value,
                        ),
                    )
                ],
                "contributions": [
                    {
                        "source_id": c.source_id,
                        "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                    }
                    for c in sorted(state.contributions, key=lambda x: x.source_id)
                ],
                "suspended_contributions": [
                    {
                        "source_id": c.source_id,
                        "remaining": c.remaining.total_seconds() if c.remaining else None,
                    }
                    for c in sorted(state.suspended_contributions, key=lambda x: x.source_id)
                ],
            }

        return dump

    def restore_state(
        self,
        snapshot: dict[str, dict[str, Any]],
        now: datetime,
        max_age_minutes: int = 15,
    ) -> None:
        """Restore state from a persisted snapshot."""
        max_age = timedelta(minutes=max_age_minutes)

        for loc_id, data in snapshot.items():
            if loc_id not in self.configs:
                continue

            direct_locks: list[LockDirective] = []
            for raw in data.get("direct_locks", []):
                source_id = raw.get("source_id")
                if not source_id:
                    continue
                try:
                    mode = LockMode(str(raw.get("mode", LockMode.FREEZE.value)))
                except ValueError:
                    mode = LockMode.FREEZE
                try:
                    scope = LockScope(str(raw.get("scope", LockScope.SELF.value)))
                except ValueError:
                    scope = LockScope.SELF
                direct_locks.append(LockDirective(source_id=source_id, mode=mode, scope=scope))

            # Backward compatibility with v3 snapshots that persisted only locked_by.
            if not direct_locks:
                for source_id in data.get("locked_by", []):
                    if not source_id:
                        continue
                    direct_locks.append(
                        LockDirective(
                            source_id=str(source_id),
                            mode=LockMode.FREEZE,
                            scope=LockScope.SELF,
                        )
                    )

            contributions: list[SourceContribution] = []
            for raw in data.get("contributions", []):
                source_id = raw.get("source_id")
                if not source_id:
                    continue

                expires_at = None
                if raw.get("expires_at"):
                    try:
                        expires_at = datetime.fromisoformat(raw["expires_at"])
                        if expires_at.tzinfo is None:
                            expires_at = expires_at.replace(tzinfo=UTC)
                    except (TypeError, ValueError):
                        expires_at = None

                if expires_at and expires_at < now - max_age:
                    continue

                contributions.append(SourceContribution(source_id=source_id, expires_at=expires_at))

            suspended: list[SuspendedContribution] = []
            for raw in data.get("suspended_contributions", []):
                source_id = raw.get("source_id")
                if not source_id:
                    continue

                remaining = None
                if raw.get("remaining") is not None:
                    try:
                        remaining = timedelta(seconds=float(raw["remaining"]))
                    except (TypeError, ValueError):
                        remaining = None

                suspended.append(SuspendedContribution(source_id=source_id, remaining=remaining))

            is_occupied = bool(contributions)
            if data.get("is_occupied") and not contributions and direct_locks:
                is_occupied = True

            self.state[loc_id] = LocationRuntimeState(
                is_occupied=is_occupied,
                contributions=frozenset(contributions),
                suspended_contributions=frozenset(suspended),
                locked_by=frozenset(lock.source_id for lock in direct_locks),
                lock_modes=frozenset(lock.mode for lock in direct_locks),
                direct_locks=frozenset(direct_locks),
            )

        # Reconcile effective lock inheritance and resulting occupancy constraints.
        reconcile_transitions: list[StateTransition] = []
        for location_id in self.configs:
            self._process_location_update(location_id, None, now, reconcile_transitions)

    def get_effective_timeout(self, location_id: str, now: datetime) -> datetime | None:
        """Get when location truly becomes vacant considering descendants."""
        if location_id not in self.state:
            return None

        state = self.state[location_id]
        if not state.is_occupied:
            return None

        effective: datetime | None = None
        for contribution in state.contributions:
            if contribution.expires_at is None:
                return None
            if contribution.expires_at <= now:
                continue
            if effective is None or contribution.expires_at > effective:
                effective = contribution.expires_at

        for child_id in self.children_map.get(location_id, []):
            child_cfg = self.configs[child_id]
            # FOLLOW_PARENT descendants don't independently extend timeout.
            if child_cfg.occupancy_strategy == OccupancyStrategy.FOLLOW_PARENT:
                continue

            child_effective = self.get_effective_timeout(child_id, now)
            child_state = self.state.get(child_id)

            if child_state and child_state.is_occupied and child_effective is None:
                return None

            if child_effective and (effective is None or child_effective > effective):
                effective = child_effective

        return effective

    def vacate_area(
        self,
        location_id: str,
        source_id: str,
        now: datetime,
        include_locked: bool = False,
    ) -> EngineResult:
        """Vacate location and all descendants."""
        transitions: list[StateTransition] = []

        locations_to_vacate = [location_id, *self._get_descendants(location_id)]
        for loc_id in locations_to_vacate:
            if loc_id not in self.configs:
                continue

            state = self.state[loc_id]
            if state.is_locked and not include_locked:
                continue

            if state.is_locked and include_locked:
                self._process_location_update(
                    loc_id,
                    OccupancyEvent(
                        location_id=loc_id,
                        event_type=EventType.UNLOCK_ALL,
                        source_id=source_id,
                        timestamp=now,
                    ),
                    now,
                    transitions,
                )
                if self.state[loc_id].is_locked:
                    # Still locked due inherited subtree policy from an ancestor.
                    continue

            self._process_location_update(
                loc_id,
                OccupancyEvent(
                    location_id=loc_id,
                    event_type=EventType.VACATE,
                    source_id=source_id,
                    timestamp=now,
                ),
                now,
                transitions,
            )

        return EngineResult(
            next_expiration=self._calculate_next_expiration(now),
            transitions=transitions,
        )

    def _get_descendants(self, location_id: str) -> list[str]:
        descendants: list[str] = []
        for child_id in self.children_map.get(location_id, []):
            descendants.append(child_id)
            descendants.extend(self._get_descendants(child_id))
        return descendants

    def _effective_locks(
        self,
        location_id: str,
        location_override: dict[str, LockDirective] | None = None,
    ) -> list[LockDirective]:
        """Resolve direct + inherited subtree lock directives affecting a location."""
        effective: list[LockDirective] = []
        current_id: str | None = location_id
        while current_id is not None:
            state = self.state[current_id]
            directives = (
                location_override.values()
                if current_id == location_id and location_override is not None
                else state.direct_locks
            )
            for directive in directives:
                if current_id == location_id or directive.scope == LockScope.SUBTREE:
                    effective.append(directive)
            current_id = self.configs[current_id].parent_id
        return effective

    @staticmethod
    def _direct_lock_map(
        directives: set[LockDirective] | frozenset[LockDirective],
    ) -> dict[str, LockDirective]:
        return {directive.source_id: directive for directive in directives}

    @staticmethod
    def _contrib_map(
        contributions: set[SourceContribution] | frozenset[SourceContribution],
    ) -> dict[str, datetime | None]:
        return {c.source_id: c.expires_at for c in contributions}

    @staticmethod
    def _suspended_map(
        suspended: set[SuspendedContribution] | frozenset[SuspendedContribution],
    ) -> dict[str, timedelta | None]:
        return {c.source_id: c.remaining for c in suspended}

    @staticmethod
    def _drop_expired(contrib_map: dict[str, datetime | None], now: datetime) -> None:
        expired = [sid for sid, exp in contrib_map.items() if exp is not None and exp <= now]
        for sid in expired:
            contrib_map.pop(sid, None)

    @staticmethod
    def _resume_contributions(
        suspended_map: dict[str, timedelta | None],
        now: datetime,
    ) -> dict[str, datetime | None]:
        resumed: dict[str, datetime | None] = {}
        for source_id, remaining in suspended_map.items():
            if remaining is None:
                resumed[source_id] = None
                continue
            if remaining.total_seconds() <= 0:
                continue
            resumed[source_id] = now + remaining
        return resumed

    @staticmethod
    def _child_source_id(child_id: str) -> str:
        return f"{_CHILD_PREFIX}:{child_id}"

    @staticmethod
    def _follow_source_id(parent_id: str | None) -> str:
        return f"{_FOLLOW_PREFIX}:{parent_id}" if parent_id else _FOLLOW_PREFIX

    @staticmethod
    def _reason_for(
        event: OccupancyEvent | None,
        propagated_from_child: str | None,
        propagated_parent: bool,
    ) -> str:
        if event:
            return f"{REASON_EVENT_PREFIX}{event.event_type.value}"
        if propagated_from_child:
            return f"{REASON_PROPAGATION_CHILD_PREFIX}{propagated_from_child}"
        if propagated_parent:
            return REASON_PROPAGATION_PARENT
        return REASON_TIMEOUT
