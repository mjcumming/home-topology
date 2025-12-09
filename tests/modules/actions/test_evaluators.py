"""Tests for condition evaluators."""

import pytest
from datetime import datetime, UTC

from home_topology.modules.actions import (
    MockPlatformAdapter,
    ConditionEvaluator,
    TimeOfDayCondition,
    StateCondition,
    NumericStateCondition,
    LuxLevelCondition,
    DayOfWeekCondition,
    is_dark,
    is_nighttime,
)


@pytest.fixture
def platform():
    """Create a mock platform adapter."""
    return MockPlatformAdapter()


@pytest.fixture
def evaluator(platform):
    """Create a condition evaluator with mock platform."""
    return ConditionEvaluator(platform)


class TestTimeOfDayCondition:
    """Tests for time-of-day conditions."""

    def test_within_normal_window(self, platform, evaluator):
        """Test time within a normal (non-midnight-spanning) window."""
        # Set current time to 10:00
        platform.set_current_time(datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC))

        condition = TimeOfDayCondition(after="08:00:00", before="18:00:00")
        assert evaluator.evaluate(condition) is True

    def test_outside_normal_window(self, platform, evaluator):
        """Test time outside a normal window."""
        # Set current time to 20:00
        platform.set_current_time(datetime(2025, 1, 15, 20, 0, 0, tzinfo=UTC))

        condition = TimeOfDayCondition(after="08:00:00", before="18:00:00")
        assert evaluator.evaluate(condition) is False

    def test_within_midnight_spanning_window(self, platform, evaluator):
        """Test time within a window that spans midnight."""
        # Set current time to 23:00
        platform.set_current_time(datetime(2025, 1, 15, 23, 0, 0, tzinfo=UTC))

        condition = TimeOfDayCondition(after="22:00:00", before="06:00:00")
        assert evaluator.evaluate(condition) is True

        # Also test early morning
        platform.set_current_time(datetime(2025, 1, 15, 4, 0, 0, tzinfo=UTC))
        assert evaluator.evaluate(condition) is True

    def test_outside_midnight_spanning_window(self, platform, evaluator):
        """Test time outside a window that spans midnight."""
        # Set current time to 12:00
        platform.set_current_time(datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC))

        condition = TimeOfDayCondition(after="22:00:00", before="06:00:00")
        assert evaluator.evaluate(condition) is False

    def test_only_after_constraint(self, platform, evaluator):
        """Test condition with only 'after' constraint."""
        platform.set_current_time(datetime(2025, 1, 15, 20, 0, 0, tzinfo=UTC))

        condition = TimeOfDayCondition(after="18:00:00")
        assert evaluator.evaluate(condition) is True

        platform.set_current_time(datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC))
        assert evaluator.evaluate(condition) is False


class TestStateCondition:
    """Tests for entity state conditions."""

    def test_state_matches(self, platform, evaluator):
        """Test when entity state matches."""
        platform.set_state("input_boolean.auto", "on")

        condition = StateCondition(entity_id="input_boolean.auto", state="on")
        assert evaluator.evaluate(condition) is True

    def test_state_does_not_match(self, platform, evaluator):
        """Test when entity state doesn't match."""
        platform.set_state("input_boolean.auto", "off")

        condition = StateCondition(entity_id="input_boolean.auto", state="on")
        assert evaluator.evaluate(condition) is False

    def test_entity_not_found(self, platform, evaluator):
        """Test when entity doesn't exist."""
        condition = StateCondition(entity_id="nonexistent", state="on")
        assert evaluator.evaluate(condition) is False


class TestNumericStateCondition:
    """Tests for numeric state conditions."""

    def test_above_threshold(self, platform, evaluator):
        """Test value above threshold."""
        platform.set_numeric_state("sensor.temp", 25.0)

        condition = NumericStateCondition(entity_id="sensor.temp", above=20.0)
        assert evaluator.evaluate(condition) is True

    def test_below_threshold(self, platform, evaluator):
        """Test value below threshold."""
        platform.set_numeric_state("sensor.temp", 15.0)

        condition = NumericStateCondition(entity_id="sensor.temp", below=20.0)
        assert evaluator.evaluate(condition) is True

    def test_within_range(self, platform, evaluator):
        """Test value within range."""
        platform.set_numeric_state("sensor.temp", 22.0)

        condition = NumericStateCondition(entity_id="sensor.temp", above=20.0, below=25.0)
        assert evaluator.evaluate(condition) is True

    def test_outside_range(self, platform, evaluator):
        """Test value outside range."""
        platform.set_numeric_state("sensor.temp", 30.0)

        condition = NumericStateCondition(entity_id="sensor.temp", above=20.0, below=25.0)
        assert evaluator.evaluate(condition) is False


class TestLuxLevelCondition:
    """Tests for lux level conditions."""

    def test_dark_enough(self, platform, evaluator):
        """Test when light level is low enough."""
        platform.set_numeric_state("sensor.lux", 30.0)

        condition = LuxLevelCondition(entity_id="sensor.lux", below=50.0)
        assert evaluator.evaluate(condition) is True

    def test_too_bright(self, platform, evaluator):
        """Test when light level is too high."""
        platform.set_numeric_state("sensor.lux", 200.0)

        condition = LuxLevelCondition(entity_id="sensor.lux", below=50.0)
        assert evaluator.evaluate(condition) is False

    def test_sensor_unavailable_defaults_true(self, platform, evaluator):
        """Test that unavailable lux sensor defaults to True (safe for lighting)."""
        # No lux sensor state set
        condition = LuxLevelCondition(entity_id="sensor.lux", below=50.0)
        assert evaluator.evaluate(condition) is True


class TestDayOfWeekCondition:
    """Tests for day of week conditions."""

    def test_weekday(self, platform, evaluator):
        """Test weekday condition."""
        # 2025-01-15 is a Wednesday
        platform.set_current_time(datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC))

        condition = DayOfWeekCondition(days=frozenset(["mon", "tue", "wed", "thu", "fri"]))
        assert evaluator.evaluate(condition) is True

    def test_weekend(self, platform, evaluator):
        """Test weekend condition."""
        # 2025-01-18 is a Saturday
        platform.set_current_time(datetime(2025, 1, 18, 12, 0, 0, tzinfo=UTC))

        condition = DayOfWeekCondition(days=frozenset(["sat", "sun"]))
        assert evaluator.evaluate(condition) is True

    def test_not_matching_day(self, platform, evaluator):
        """Test when day doesn't match."""
        # 2025-01-15 is a Wednesday
        platform.set_current_time(datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC))

        condition = DayOfWeekCondition(days=frozenset(["sat", "sun"]))
        assert evaluator.evaluate(condition) is False


class TestEvaluateAll:
    """Tests for evaluating multiple conditions."""

    def test_all_conditions_met(self, platform, evaluator):
        """Test when all conditions are met."""
        platform.set_current_time(datetime(2025, 1, 15, 20, 0, 0, tzinfo=UTC))
        platform.set_state("input_boolean.auto", "on")
        platform.set_numeric_state("sensor.lux", 30.0)

        conditions = [
            TimeOfDayCondition(after="18:00:00"),
            StateCondition(entity_id="input_boolean.auto", state="on"),
            LuxLevelCondition(entity_id="sensor.lux", below=50.0),
        ]

        assert evaluator.evaluate_all(conditions) is True

    def test_one_condition_not_met(self, platform, evaluator):
        """Test when one condition is not met."""
        platform.set_current_time(datetime(2025, 1, 15, 20, 0, 0, tzinfo=UTC))
        platform.set_state("input_boolean.auto", "off")  # This will fail
        platform.set_numeric_state("sensor.lux", 30.0)

        conditions = [
            TimeOfDayCondition(after="18:00:00"),
            StateCondition(entity_id="input_boolean.auto", state="on"),
            LuxLevelCondition(entity_id="sensor.lux", below=50.0),
        ]

        assert evaluator.evaluate_all(conditions) is False

    def test_empty_conditions(self, evaluator):
        """Test that empty conditions returns True."""
        assert evaluator.evaluate_all([]) is True


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_is_dark_with_lux_sensor(self, platform):
        """Test is_dark with lux sensor."""
        platform.set_numeric_state("sensor.lux", 30.0)
        assert is_dark(platform, lux_entity="sensor.lux", lux_threshold=50.0) is True

        platform.set_numeric_state("sensor.lux", 200.0)
        assert is_dark(platform, lux_entity="sensor.lux", lux_threshold=50.0) is False

    def test_is_dark_with_sun_entity(self, platform):
        """Test is_dark falling back to sun entity state."""
        # Sun below horizon (dark)
        platform.set_state("sun.sun", "below_horizon")
        assert is_dark(platform) is True

        # Sun above horizon (light)
        platform.set_state("sun.sun", "above_horizon")
        assert is_dark(platform) is False

    def test_is_dark_custom_entity(self, platform):
        """Test is_dark with custom dark entity."""
        platform.set_state("binary_sensor.is_dark", "on")
        assert is_dark(platform, dark_entity="binary_sensor.is_dark", dark_state="on") is True

        platform.set_state("binary_sensor.is_dark", "off")
        assert is_dark(platform, dark_entity="binary_sensor.is_dark", dark_state="on") is False

    def test_is_nighttime(self, platform):
        """Test is_nighttime function with sun entity."""
        # Sun below horizon (night)
        platform.set_state("sun.sun", "below_horizon")
        assert is_nighttime(platform) is True

        # Sun above horizon (day)
        platform.set_state("sun.sun", "above_horizon")
        assert is_nighttime(platform) is False

    def test_is_nighttime_missing_entity(self, platform):
        """Test is_nighttime defaults to True when entity missing."""
        # No sun entity set - should default to True (safe for lighting)
        assert is_nighttime(platform) is True
