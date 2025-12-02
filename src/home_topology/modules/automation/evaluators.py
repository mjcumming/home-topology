"""
Condition evaluators for the Automation engine.

Each evaluator checks whether a specific condition type is met.
"""

import logging
from datetime import datetime, time
from typing import TYPE_CHECKING, Optional

from .models import (
    ConditionConfig,
    TimeOfDayCondition,
    StateCondition,
    NumericStateCondition,
    LuxLevelCondition,
    LocationOccupiedCondition,
    DayOfWeekCondition,
)

if TYPE_CHECKING:
    from .adapter import PlatformAdapter
    from home_topology.modules.occupancy import OccupancyModule

logger = logging.getLogger(__name__)


class ConditionEvaluator:
    """
    Evaluates conditions for automation rules.

    Uses platform adapter for entity states and occupancy module for
    location occupancy checks.
    """

    def __init__(
        self,
        platform: "PlatformAdapter",
        occupancy_module: Optional["OccupancyModule"] = None,
    ) -> None:
        self._platform = platform
        self._occupancy = occupancy_module

    def evaluate(self, condition: ConditionConfig) -> bool:
        """
        Evaluate a condition.

        Args:
            condition: The condition to evaluate

        Returns:
            True if condition is met, False otherwise
        """
        if isinstance(condition, TimeOfDayCondition):
            return self._check_time_of_day(condition)
        elif isinstance(condition, StateCondition):
            return self._check_state(condition)
        elif isinstance(condition, NumericStateCondition):
            return self._check_numeric_state(condition)
        elif isinstance(condition, LuxLevelCondition):
            return self._check_lux_level(condition)
        elif isinstance(condition, LocationOccupiedCondition):
            return self._check_location_occupied(condition)
        elif isinstance(condition, DayOfWeekCondition):
            return self._check_day_of_week(condition)
        else:
            logger.warning(f"Unknown condition type: {type(condition)}")
            return False

    def evaluate_all(self, conditions: list[ConditionConfig]) -> bool:
        """
        Evaluate all conditions (AND logic).

        Args:
            conditions: List of conditions to evaluate

        Returns:
            True if ALL conditions are met
        """
        for condition in conditions:
            if not self.evaluate(condition):
                logger.debug(f"Condition not met: {condition}")
                return False
        return True

    # =========================================================================
    # Condition Implementations
    # =========================================================================

    def _check_time_of_day(self, condition: TimeOfDayCondition) -> bool:
        """Check if current time is within the specified window."""
        now = self._platform.get_current_time()
        current_time = now.time()

        after_time: Optional[time] = None
        before_time: Optional[time] = None

        if condition.after:
            after_time = self._platform.parse_time_expression(condition.after)
        if condition.before:
            before_time = self._platform.parse_time_expression(condition.before)

        # Handle various cases
        if after_time and before_time:
            # Window could span midnight (e.g., 22:00 to 06:00)
            if after_time <= before_time:
                # Normal window (e.g., 08:00 to 18:00)
                return after_time <= current_time <= before_time
            else:
                # Spans midnight (e.g., 22:00 to 06:00)
                return current_time >= after_time or current_time <= before_time
        elif after_time:
            return current_time >= after_time
        elif before_time:
            return current_time <= before_time

        return True  # No constraints

    def _check_state(self, condition: StateCondition) -> bool:
        """Check if entity is in the expected state."""
        actual = self._platform.get_state(condition.entity_id)
        if actual is None:
            logger.warning(f"Entity not found: {condition.entity_id}")
            return False
        return actual == condition.state

    def _check_numeric_state(self, condition: NumericStateCondition) -> bool:
        """Check if entity's numeric value is within range."""
        value = self._platform.get_numeric_state(condition.entity_id)
        if value is None:
            logger.warning(f"Numeric state unavailable: {condition.entity_id}")
            return False

        if condition.above is not None and value <= condition.above:
            return False
        if condition.below is not None and value >= condition.below:
            return False
        return True

    def _check_lux_level(self, condition: LuxLevelCondition) -> bool:
        """Check light level condition (wrapper around numeric state)."""
        value = self._platform.get_numeric_state(condition.entity_id)
        if value is None:
            logger.warning(f"Lux sensor unavailable: {condition.entity_id}")
            # When lux sensor unavailable, assume it's dark (safer for lighting)
            # This is configurable behavior - could also return False
            return True

        if condition.below is not None and value >= condition.below:
            return False
        if condition.above is not None and value <= condition.above:
            return False
        return True

    def _check_location_occupied(self, condition: LocationOccupiedCondition) -> bool:
        """Check if a location is occupied or vacant."""
        if not self._occupancy:
            logger.warning("Occupancy module not available for location check")
            return False

        state = self._occupancy.get_location_state(condition.location_id)
        if state is None:
            logger.warning(f"Location not found: {condition.location_id}")
            return False

        actual_occupied = state.get("occupied", False)
        return actual_occupied == condition.occupied

    def _check_day_of_week(self, condition: DayOfWeekCondition) -> bool:
        """Check if current day is in the allowed set."""
        now = self._platform.get_current_time()
        day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        current_day = day_names[now.weekday()]
        return current_day in condition.days


def is_dark(
    platform: "PlatformAdapter",
    lux_entity: Optional[str] = None,
    lux_threshold: float = 50.0,
    dark_entity: str = "sun.sun",
    dark_state: str = "below_horizon",
) -> bool:
    """
    Convenience function to check if it's "dark" (for lighting decisions).

    Uses lux sensor if available, falls back to checking an entity state.

    Args:
        platform: Platform adapter
        lux_entity: Optional lux sensor entity ID
        lux_threshold: Lux level below which it's considered dark
        dark_entity: Entity to check for darkness (default: sun.sun)
        dark_state: State value indicating dark (default: below_horizon)

    Returns:
        True if it's dark (lights should be on)

    Note:
        The integration layer should provide appropriate entities:
        - sun.sun (Home Assistant built-in)
        - binary_sensor.is_dark (integration-provided helper)
    """
    # Try lux sensor first (most accurate)
    if lux_entity:
        lux = platform.get_numeric_state(lux_entity)
        if lux is not None:
            return lux < lux_threshold

    # Fall back to entity state check
    state = platform.get_state(dark_entity)
    if state is None:
        logger.warning(f"Dark entity not found: {dark_entity}, assuming dark")
        return True

    return state == dark_state


def is_nighttime(
    platform: "PlatformAdapter",
    sun_entity: str = "sun.sun",
    night_state: str = "below_horizon",
) -> bool:
    """
    Check if it's nighttime (sun below horizon).

    Args:
        platform: Platform adapter
        sun_entity: Sun entity to check (default: sun.sun)
        night_state: State value indicating night (default: below_horizon)

    Returns:
        True if sun is below horizon

    Note:
        Uses the platform's sun entity. In Home Assistant, sun.sun
        has state "above_horizon" or "below_horizon".
    """
    state = platform.get_state(sun_entity)
    if state is None:
        logger.warning(f"Sun entity not found: {sun_entity}, assuming night")
        return True

    return state == night_state


