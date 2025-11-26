"""The Core Logic Engine for Occupancy (v2.3).

This module contains the pure business logic. It accepts events and time,
and returns state transitions and scheduling instructions.

v2.3 Changes:
- Timer suspension during lock (timer_remaining field)
- Holds and timers coexist (timers preserved during holds)
- RELEASE checks existing timer before starting trailing timer
- Removed active_occupants (identity tracking deferred to PresenceModule)

Licensed under MIT License
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from .models import (
    EngineResult,
    EventType,
    LocationConfig,
    LocationRuntimeState,
    OccupancyEvent,
    OccupancyStrategy,
    StateTransition,
)

_LOGGER = logging.getLogger(__name__)


class OccupancyEngine:
    """The functional core of the occupancy system."""

    def __init__(
        self,
        configs: list[LocationConfig],
        initial_state: dict[str, LocationRuntimeState] | None = None,
    ) -> None:
        """Initialize the engine with static configuration.

        Args:
            configs: List of location configurations.
            initial_state: Optional initial state dictionary for restoration.
        """
        # Store configs as dict for fast lookup
        self.configs: dict[str, LocationConfig] = {c.id: c for c in configs}

        # Initialize or restore state
        if initial_state:
            self.state = initial_state.copy()
            # Ensure all config locations exist in state (initialize missing ones)
            for c in configs:
                if c.id not in self.state:
                    self.state[c.id] = LocationRuntimeState()
        else:
            self.state = {c.id: LocationRuntimeState() for c in configs}

        # Build Parent -> Children map for "FOLLOW_PARENT" logic (Downward)
        self.children_map: dict[str, list[str]] = {}
        for c in configs:
            if c.parent_id:
                if c.parent_id not in self.children_map:
                    self.children_map[c.parent_id] = []
                self.children_map[c.parent_id].append(c.id)

    def handle_event(self, event: OccupancyEvent, now: datetime) -> EngineResult:
        """Process a single external event and return the results.

        Args:
            event: The occupancy event to process.
            now: Current datetime (time-agnostic).

        Returns:
            EngineResult with state transitions and next expiration time.
        """
        if event.location_id not in self.configs:
            _LOGGER.warning(f"Event for unknown location: {event.location_id}")
            return EngineResult(next_expiration=self._calculate_next_expiration(now))

        _LOGGER.info(
            f"Handling event: {event.event_type.value} in {event.location_id} "
            f"(source={event.source_id})"
        )

        transitions: list[StateTransition] = []

        # Process the location update (recursive: handles up and down)
        self._process_location_update(event.location_id, event, now, transitions)

        if transitions:
            for transition in transitions:
                prev_state = "VACANT" if not transition.previous_state.is_occupied else "OCCUPIED"
                new_state = "OCCUPIED" if transition.new_state.is_occupied else "VACANT"
                _LOGGER.info(
                    f"  {transition.location_id}: {prev_state} -> {new_state} "
                    f"({transition.reason})"
                )

        # Return the package (New States + Next Wakeup Time)
        return EngineResult(
            next_expiration=self._calculate_next_expiration(now),
            transitions=transitions,
        )

    def check_timeouts(self, now: datetime) -> EngineResult:
        """Periodic garbage collection. Checks for expired timers.

        Args:
            now: Current datetime.

        Returns:
            EngineResult with state transitions and next expiration time.
        """
        _LOGGER.info(f"Checking timeouts at {now}")
        transitions: list[StateTransition] = []

        for location_id in self.configs:
            state = self.state[location_id]

            # If locked, we don't timeout (state is static)
            if state.is_locked:
                _LOGGER.debug(f"  {location_id}: Skipped (locked by {state.locked_by})")
                continue

            # If not occupied, nothing to timeout
            if not state.is_occupied:
                continue

            # Check if timer expired
            if state.occupied_until and state.occupied_until <= now:
                _LOGGER.info(f"  {location_id}: Timer expired (was {state.occupied_until})")

            # We pass a 'None' event to trigger re-evaluation of the state
            # based purely on time and holds. This will also handle FOLLOW_PARENT
            # children that need to re-evaluate when parent times out.
            self._process_location_update(location_id, None, now, transitions)

        if transitions:
            for transition in transitions:
                prev_state = "VACANT" if not transition.previous_state.is_occupied else "OCCUPIED"
                new_state = "OCCUPIED" if transition.new_state.is_occupied else "VACANT"
                _LOGGER.info(f"  {transition.location_id}: {prev_state} -> {new_state} (timeout)")

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
        is_propagation: bool = False,
    ) -> None:
        """Recursive update handler with upward and downward propagation.

        Args:
            location_id: The location to update.
            event: Optional event triggering this update.
            now: Current datetime.
            transitions: List to append state transitions to.
            is_propagation: True if this is an internal propagation (not external event).
        """
        # 1. Evaluate this location
        state_changed = self._evaluate_state(location_id, event, now, transitions, is_propagation)

        if not state_changed:
            return

        config = self.configs[location_id]
        new_state = self.state[location_id]

        # 2. Upward Propagation (Child -> Parent) - Internal logic
        # If we contribute to parent, bubble up occupancy
        if config.parent_id and config.contributes_to_parent:
            # We propagate if we are occupied
            # Note: We do NOT propagate vacancy.
            should_propagate = new_state.is_occupied

            if should_propagate:
                _LOGGER.debug(
                    f"  Propagating {location_id} -> {config.parent_id} "
                    f"(occupied={new_state.is_occupied})"
                )
                # Internal propagation - no event, just trigger re-evaluation
                self._process_location_update(
                    config.parent_id,
                    event=None,  # Internal propagation doesn't send an event
                    now=now,
                    transitions=transitions,
                    is_propagation=True,
                )
            else:
                _LOGGER.debug(
                    f"  {location_id} -> {config.parent_id}: "
                    f"Not propagating (vacant, contributes_to_parent=True)"
                )

        # 3. Downward Dependency (Parent -> Child with FOLLOW_PARENT)
        # If this location changed, check if any children are watching it
        if location_id in self.children_map:
            for child_id in self.children_map[location_id]:
                child_config = self.configs[child_id]
                if child_config.occupancy_strategy == OccupancyStrategy.FOLLOW_PARENT:
                    _LOGGER.debug(
                        f"  {location_id} -> {child_id}: Triggering re-eval (FOLLOW_PARENT)"
                    )
                    # Trigger re-eval of child (with no event, just context update)
                    self._process_location_update(
                        child_id,
                        event=None,
                        now=now,
                        transitions=transitions,
                        is_propagation=True,
                    )

    def _evaluate_state(
        self,
        location_id: str,
        event: OccupancyEvent | None,
        now: datetime,
        transitions: list[StateTransition],
        is_propagation: bool = False,
    ) -> bool:
        """Core math. Calculates the new state for a location.

        Args:
            location_id: The location to evaluate.
            event: Optional event triggering evaluation.
            now: Current datetime.
            transitions: List to append state transitions to.
            is_propagation: True if this is an internal propagation.

        Returns:
            True if state changed, False otherwise.
        """
        config = self.configs[location_id]
        current_state = self.state[location_id]

        # --- A. Lock Check ---
        if current_state.is_locked:
            # Only process UNLOCK, UNLOCK_ALL, and LOCK when locked
            if event and event.event_type in (EventType.UNLOCK, EventType.UNLOCK_ALL):
                pass  # Allow these through
            elif event and event.event_type == EventType.LOCK:
                pass  # Allow adding more locks
            elif event is None:
                # Timeout check - skip if locked (timer is frozen)
                _LOGGER.debug(f"  {location_id}: Timeout skipped (locked)")
                return False
            else:
                _LOGGER.debug(
                    f"  {location_id}: Event ignored (locked by {current_state.locked_by}, "
                    f"event_type={event.event_type.value if event else 'None'})"
                )
                return False

        # --- B. Calculate Inputs (Next State Candidates) ---
        next_holds = set(current_state.active_holds)
        next_occupied_until = current_state.occupied_until
        next_timer_remaining = current_state.timer_remaining
        next_locked_by = set(current_state.locked_by)

        if event:
            # 1. Handle Lock Events (with timer suspension)
            if event.event_type == EventType.LOCK:
                next_locked_by.add(event.source_id)
                # Suspend timer when locking
                if next_occupied_until is not None and next_timer_remaining is None:
                    next_timer_remaining = next_occupied_until - now
                    next_occupied_until = None
                    _LOGGER.info(
                        f"  {location_id}: LOCKED by {event.source_id} "
                        f"(timer suspended: {next_timer_remaining})"
                    )
                else:
                    _LOGGER.info(f"  {location_id}: LOCKED by {event.source_id}")

            elif event.event_type == EventType.UNLOCK:
                if event.source_id in next_locked_by:
                    next_locked_by.remove(event.source_id)
                    # Resume timer when all locks cleared
                    if not next_locked_by and next_timer_remaining is not None:
                        next_occupied_until = now + next_timer_remaining
                        next_timer_remaining = None
                        _LOGGER.info(
                            f"  {location_id}: UNLOCKED by {event.source_id} "
                            f"(timer resumed: {next_occupied_until})"
                        )
                    else:
                        _LOGGER.info(f"  {location_id}: UNLOCKED by {event.source_id}")
                else:
                    _LOGGER.debug(
                        f"  {location_id}: UNLOCK ignored (not locked by {event.source_id})"
                    )

            elif event.event_type == EventType.UNLOCK_ALL:
                next_locked_by.clear()
                # Resume timer when all locks cleared
                if next_timer_remaining is not None:
                    next_occupied_until = now + next_timer_remaining
                    next_timer_remaining = None
                    _LOGGER.info(
                        f"  {location_id}: ALL LOCKS CLEARED "
                        f"(timer resumed: {next_occupied_until})"
                    )
                else:
                    _LOGGER.info(f"  {location_id}: ALL LOCKS CLEARED")

            # 2. Handle Holds (timers continue during holds)
            if event.event_type == EventType.HOLD:
                next_holds.add(event.source_id)
                # Note: Timer is NOT cleared - it continues in background
            elif event.event_type == EventType.RELEASE:
                if event.source_id in next_holds:
                    next_holds.remove(event.source_id)

            # 3. Handle VACATE (Force Vacant)
            if event.event_type == EventType.VACATE:
                next_holds.clear()
                next_occupied_until = None
                next_timer_remaining = None
                _LOGGER.info(f"  {location_id}: VACATED by {event.source_id}")

            # 4. Timer Logic (TRIGGER and RELEASE)
            elif event.event_type == EventType.TRIGGER:
                timeout_seconds = self._get_timeout(event, config)
                timeout_delta = timedelta(seconds=timeout_seconds)
                calculated_expiry = now + timeout_delta

                # Always extend timer (even during holds - preserved for later)
                if next_occupied_until is None or calculated_expiry > next_occupied_until:
                    next_occupied_until = calculated_expiry

            elif event.event_type == EventType.RELEASE:
                # When LAST hold drops, check existing timer vs trailing timer
                if not next_holds and current_state.active_holds:
                    # Check if existing timer is still valid
                    if next_occupied_until is not None and next_occupied_until > now:
                        # Keep existing timer (from TRIGGERs during hold)
                        _LOGGER.debug(
                            f"  {location_id}: Using existing timer {next_occupied_until}"
                        )
                    else:
                        # No valid timer, start trailing timer
                        timeout_seconds = self._get_release_timeout(event, config)
                        timeout_delta = timedelta(seconds=timeout_seconds)
                        next_occupied_until = now + timeout_delta
                        _LOGGER.debug(
                            f"  {location_id}: Starting trailing timer {next_occupied_until}"
                        )

        # --- C. Handle Internal Propagation ---
        # When a child becomes occupied, extend parent timer
        if is_propagation and not event:
            # Propagation comes FROM children TO parent
            # When propagating up, we should extend the parent's timer
            timeout_seconds = config.default_timeout
            timeout_delta = timedelta(seconds=timeout_seconds)
            calculated_expiry = now + timeout_delta

            if next_occupied_until is None or calculated_expiry > next_occupied_until:
                next_occupied_until = calculated_expiry

        # --- D. Determine Occupancy Status (The Strategy) ---

        # If still locked (after processing event), preserve current occupancy
        if next_locked_by:
            # Locked - preserve current occupancy state
            is_occupied_candidate = current_state.is_occupied
        else:
            # Not locked - calculate normally
            is_occupied_candidate = False

            # 1. Timer Active
            if next_occupied_until and next_occupied_until > now:
                is_occupied_candidate = True

            # 2. Active Hold
            if next_holds:
                is_occupied_candidate = True

            # 3. Strategy: FOLLOW_PARENT
            if config.occupancy_strategy == OccupancyStrategy.FOLLOW_PARENT:
                if config.parent_id:
                    parent_state = self.state.get(config.parent_id)
                    if parent_state and parent_state.is_occupied:
                        is_occupied_candidate = True
                        # If following parent and parent is held, this location is also held
                        if parent_state.active_holds:
                            next_occupied_until = None

        # --- E. Vacancy Cleanup ---
        if not is_occupied_candidate:
            # Reset ephemeral data on vacancy
            next_holds.clear()
            next_occupied_until = None
            next_timer_remaining = None

        # --- F. Commit State ---
        # Convert to frozensets for immutable state
        next_holds_frozen = frozenset(next_holds)
        next_locked_by_frozen = frozenset(next_locked_by)

        # Check if anything actually changed
        if (
            is_occupied_candidate != current_state.is_occupied
            or next_occupied_until != current_state.occupied_until
            or next_timer_remaining != current_state.timer_remaining
            or next_holds_frozen != current_state.active_holds
            or next_locked_by_frozen != current_state.locked_by
        ):
            new_state = LocationRuntimeState(
                is_occupied=is_occupied_candidate,
                occupied_until=next_occupied_until,
                timer_remaining=next_timer_remaining,
                active_holds=next_holds_frozen,
                locked_by=next_locked_by_frozen,
            )

            self.state[location_id] = new_state

            transitions.append(
                StateTransition(
                    location_id=location_id,
                    previous_state=current_state,
                    new_state=new_state,
                    reason="event" if event else ("propagation" if is_propagation else "timeout"),
                )
            )
            return True

        return False

    def _calculate_next_expiration(self, now: datetime) -> datetime | None:
        """Find the earliest future timeout across all locations.

        Args:
            now: Current datetime.

        Returns:
            Earliest expiration datetime, or None if no timers active.
        """
        next_exp: datetime | None = None

        for state in self.state.values():
            # Skip if locked (timer is suspended)
            if state.is_locked:
                continue

            # Skip if held (indefinite occupancy)
            if state.active_holds:
                continue

            if state.occupied_until and state.occupied_until > now:
                if next_exp is None or state.occupied_until < next_exp:
                    next_exp = state.occupied_until

        return next_exp

    def _get_timeout(self, event: OccupancyEvent, config: LocationConfig) -> int:
        """Get timeout in seconds for a TRIGGER event.

        Args:
            event: The occupancy event.
            config: Location configuration.

        Returns:
            Timeout in seconds.
        """
        # Event can override the location default
        if event.timeout is not None:
            return event.timeout
        return config.default_timeout

    def _get_release_timeout(self, event: OccupancyEvent, config: LocationConfig) -> int:
        """Get trailing timeout in seconds for a RELEASE event.

        Args:
            event: The occupancy event.
            config: Location configuration.

        Returns:
            Timeout in seconds.
        """
        # Event can override the location default
        if event.timeout is not None:
            return event.timeout
        return config.hold_release_timeout

    def export_state(self) -> dict[str, dict[str, Any]]:
        """Creates a JSON-serializable dump of the current state.

        Returns:
            dict: { "kitchen": { "is_occupied": true,
                "occupied_until": "iso-string", ... } }
        """
        dump = {}

        for loc_id, state in self.state.items():
            # Only dump non-default states to save space
            # Skip if vacant, unlocked, and no holds
            if (
                not state.is_occupied
                and not state.is_locked
                and not state.active_holds
                and state.occupied_until is None
                and state.timer_remaining is None
            ):
                continue

            dump[loc_id] = {
                "is_occupied": state.is_occupied,
                "occupied_until": (
                    state.occupied_until.isoformat() if state.occupied_until else None
                ),
                "timer_remaining": (
                    state.timer_remaining.total_seconds() if state.timer_remaining else None
                ),
                "active_holds": list(state.active_holds),
                "locked_by": list(state.locked_by),
            }
        return dump

    def restore_state(
        self,
        snapshot: dict[str, dict[str, Any]],
        now: datetime,
        max_age_minutes: int = 15,
    ) -> None:
        """Hydrates state from a snapshot with Stale Data Protection.

        Args:
            snapshot: The data loaded from disk.
            now: Current wall-clock time.
            max_age_minutes: Safety valve. If a timer expired > X mins ago, clean it up.
        """
        for loc_id, data in snapshot.items():
            if loc_id not in self.configs:
                continue

            # 1. Parse Time
            occupied_until = None
            if data.get("occupied_until"):
                try:
                    occupied_until = datetime.fromisoformat(data["occupied_until"])
                except (ValueError, TypeError):
                    pass

            # 2. Parse timer_remaining
            timer_remaining = None
            if data.get("timer_remaining"):
                try:
                    timer_remaining = timedelta(seconds=data["timer_remaining"])
                except (ValueError, TypeError):
                    pass

            # 3. STALE DATA CHECK (The Critical Logic)
            should_restore = True
            is_occupied = data.get("is_occupied", False)
            locked_by = frozenset(data.get("locked_by", []))
            active_holds = frozenset(data.get("active_holds", []))

            # Rule A: Locked states ALWAYS restore (they are timeless)
            if locked_by:
                should_restore = True

            # Rule B: Active holds override expired timers
            elif active_holds:
                should_restore = True
                is_occupied = True

            # Rule C: If it had an expiry time, and that time passed
            elif occupied_until and occupied_until < now:
                should_restore = False
                is_occupied = False
                occupied_until = None

            if should_restore:
                self.state[loc_id] = LocationRuntimeState(
                    is_occupied=is_occupied,
                    occupied_until=occupied_until,
                    timer_remaining=timer_remaining,
                    active_holds=active_holds,
                    locked_by=locked_by,
                )
            else:
                self.state[loc_id] = LocationRuntimeState()

    def get_effective_timeout(self, location_id: str, now: datetime) -> datetime | None:
        """Get when location will TRULY become vacant (considers all descendants).

        This recursively calculates the maximum timeout across a location and
        all its descendants. Useful for knowing when an entire area will be empty.

        Args:
            location_id: The location to check.
            now: Current datetime.

        Returns:
            The latest timeout across location and all descendants, or None if:
            - Location is vacant
            - Location or any descendant has indefinite occupancy (holds)
        """
        if location_id not in self.state:
            return None

        state = self.state[location_id]

        # If not occupied, effective timeout is None
        if not state.is_occupied:
            return None

        # If has active holds, it's indefinite
        if state.active_holds:
            return None

        # Start with this location's own timeout
        effective = state.occupied_until

        # Check all children recursively
        if location_id in self.children_map:
            for child_id in self.children_map[location_id]:
                child_effective = self.get_effective_timeout(child_id, now)

                # If any child is indefinite, parent is effectively indefinite
                if (
                    child_effective is None
                    and self.state.get(child_id, LocationRuntimeState()).is_occupied
                ):
                    return None

                # Take the latest timeout
                if child_effective is not None:
                    if effective is None or child_effective > effective:
                        effective = child_effective

        return effective

    def vacate_area(
        self,
        location_id: str,
        source_id: str,
        now: datetime,
        include_locked: bool = False,
    ) -> EngineResult:
        """Vacate a location and ALL its descendants.

        Args:
            location_id: Root of the subtree to vacate.
            source_id: What initiated the vacate (for logging).
            now: Current datetime.
            include_locked: If True, also unlock and vacate locked locations.

        Returns:
            EngineResult with all state transitions that occurred.
        """
        _LOGGER.info(f"Vacating area: {location_id} (include_locked={include_locked})")

        transitions: list[StateTransition] = []

        # Get all locations to vacate (self + all descendants)
        locations_to_vacate = self._get_descendants(location_id)
        locations_to_vacate.insert(0, location_id)  # Include root

        for loc_id in locations_to_vacate:
            if loc_id not in self.configs:
                continue

            state = self.state[loc_id]

            # Handle locked locations
            if state.is_locked:
                if not include_locked:
                    _LOGGER.debug(f"  {loc_id}: Skipped (locked by {state.locked_by})")
                    continue
                else:
                    # Force unlock first
                    _LOGGER.info(f"  {loc_id}: Force unlocking")
                    unlock_event = OccupancyEvent(
                        location_id=loc_id,
                        event_type=EventType.UNLOCK_ALL,
                        source_id=source_id,
                        timestamp=now,
                    )
                    self._evaluate_state(
                        loc_id, unlock_event, now, transitions, is_propagation=False
                    )

            # Now vacate
            vacate_event = OccupancyEvent(
                location_id=loc_id,
                event_type=EventType.VACATE,
                source_id=source_id,
                timestamp=now,
            )
            self._evaluate_state(loc_id, vacate_event, now, transitions, is_propagation=False)

        _LOGGER.info(f"Vacated {len(transitions)} locations")

        return EngineResult(
            next_expiration=self._calculate_next_expiration(now),
            transitions=transitions,
        )

    def _get_descendants(self, location_id: str) -> list[str]:
        """Get all descendants of a location (children, grandchildren, etc.)."""
        descendants = []

        if location_id in self.children_map:
            for child_id in self.children_map[location_id]:
                descendants.append(child_id)
                descendants.extend(self._get_descendants(child_id))

        return descendants
