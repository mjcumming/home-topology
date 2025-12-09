"""Tests for condition evaluators."""

import pytest
from datetime import datetime, UTC

from home_topology.modules.automation import (
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

    def test_within_midnight_spanning_window_early_morning(self, platform, evaluator):
        """Test early morning time within a window that spans midnight."""
        # Set current time to 04:00
        platform.set_current_time(datetime(2025, 1, 15, 4, 0, 0, tzinfo=UTC))

        condition = TimeOfDayCondition(after="22:00:00", before="06:00:00")
        assert evaluator.evaluate(condition) is True

    def test_outside_midnight_spanning_window(self, platform, evaluator):
        """Test time outside a window that spans midnight."""
        # Set current time to 12:00
        platform.set_current_time(datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC))

        condition = TimeOfDayCondition(after="22:00:00", before="06:00:00")
        assert evaluator.evaluate(condition) is False

    def test_after_only(self, platform, evaluator):
        """Test with only 'after' constraint."""
        platform.set_current_time(datetime(2025, 1, 15, 20, 0, 0, tzinfo=UTC))

        condition = TimeOfDayCondition(after="18:00:00")
        assert evaluator.evaluate(condition) is True

    def test_before_only(self, platform, evaluator):
        """Test with only 'before' constraint."""
        platform.set_current_time(datetime(2025, 1, 15, 6, 0, 0, tzinfo=UTC))

        condition = TimeOfDayCondition(before="08:00:00")
        assert evaluator.evaluate(condition) is True


class TestStateCondition:
    """Tests for state conditions."""

    def test_state_matches(self, platform, evaluator):
        """Test when state matches."""
        platform.set_state("sun.sun", "below_horizon")

        condition = StateCondition(entity_id="sun.sun", state="below_horizon")
        assert evaluator.evaluate(condition) is True

    def test_state_does_not_match(self, platform, evaluator):
        """Test when state doesn't match."""
        platform.set_state("sun.sun", "above_horizon")

        condition = StateCondition(entity_id="sun.sun", state="below_horizon")
        assert evaluator.evaluate(condition) is False

    def test_entity_not_found(self, platform, evaluator):
        """Test when entity doesn't exist."""
        condition = StateCondition(entity_id="nonexistent.entity", state="on")
        assert evaluator.evaluate(condition) is False


class TestNumericStateCondition:
    """Tests for numeric state conditions."""

    def test_below_threshold(self, platform, evaluator):
        """Test value below threshold."""
        platform.set_numeric_state("sensor.temp", 18.5)

        condition = NumericStateCondition(entity_id="sensor.temp", below=20.0)
        assert evaluator.evaluate(condition) is True

    def test_above_threshold(self, platform, evaluator):
        """Test value above threshold."""
        platform.set_numeric_state("sensor.temp", 25.0)

        condition = NumericStateCondition(entity_id="sensor.temp", above=20.0)
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
        """Test lux below threshold (dark)."""
        platform.set_numeric_state("sensor.lux", 25.0)

        condition = LuxLevelCondition(entity_id="sensor.lux", below=50.0)
        assert evaluator.evaluate(condition) is True

    def test_too_bright(self, platform, evaluator):
        """Test lux above threshold (bright)."""
        platform.set_numeric_state("sensor.lux", 100.0)

        condition = LuxLevelCondition(entity_id="sensor.lux", below=50.0)
        assert evaluator.evaluate(condition) is False

    def test_sensor_unavailable_assumes_dark(self, platform, evaluator):
        """Test that unavailable lux sensor assumes dark (for safety)."""
        # Don't set any lux value - sensor unavailable

        condition = LuxLevelCondition(entity_id="sensor.lux", below=50.0)
        # Should return True (assume dark) for safety
        assert evaluator.evaluate(condition) is True


class TestDayOfWeekCondition:
    """Tests for day of week conditions."""

    def test_weekday(self, platform, evaluator):
        """Test weekday matching."""
        # Wednesday, Jan 15, 2025
        platform.set_current_time(datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC))

        condition = DayOfWeekCondition(days=frozenset({"mon", "tue", "wed", "thu", "fri"}))
        assert evaluator.evaluate(condition) is True

    def test_weekend(self, platform, evaluator):
        """Test weekend matching."""
        # Saturday, Jan 18, 2025
        platform.set_current_time(datetime(2025, 1, 18, 12, 0, 0, tzinfo=UTC))

        condition = DayOfWeekCondition(days=frozenset({"sat", "sun"}))
        assert evaluator.evaluate(condition) is True

    def test_day_not_in_set(self, platform, evaluator):
        """Test day not in allowed set."""
        # Wednesday, Jan 15, 2025
        platform.set_current_time(datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC))

        condition = DayOfWeekCondition(days=frozenset({"sat", "sun"}))
        assert evaluator.evaluate(condition) is False


class TestEvaluateAll:
    """Tests for evaluating multiple conditions."""

    def test_all_conditions_pass(self, platform, evaluator):
        """Test when all conditions pass."""
        platform.set_current_time(datetime(2025, 1, 15, 20, 0, 0, tzinfo=UTC))  # 8 PM
        platform.set_state("sun.sun", "below_horizon")

        conditions = [
            TimeOfDayCondition(after="18:00:00", before="23:00:00"),
            StateCondition(entity_id="sun.sun", state="below_horizon"),
        ]
        assert evaluator.evaluate_all(conditions) is True

    def test_one_condition_fails(self, platform, evaluator):
        """Test when one condition fails."""
        platform.set_current_time(datetime(2025, 1, 15, 20, 0, 0, tzinfo=UTC))  # 8 PM
        platform.set_state("sun.sun", "above_horizon")  # Sun up

        conditions = [
            TimeOfDayCondition(after="18:00:00", before="23:00:00"),  # Passes
            StateCondition(entity_id="sun.sun", state="below_horizon"),  # Fails
        ]
        assert evaluator.evaluate_all(conditions) is False

    def test_empty_conditions(self, platform, evaluator):
        """Test that empty conditions list passes."""
        assert evaluator.evaluate_all([]) is True


class TestIsDark:
    """Tests for is_dark helper function."""

    def test_dark_by_lux(self, platform):
        """Test dark detection by lux sensor."""
        platform.set_numeric_state("sensor.lux", 25.0)

        result = is_dark(platform, lux_entity="sensor.lux", lux_threshold=50.0)
        assert result is True

    def test_bright_by_lux(self, platform):
        """Test bright detection by lux sensor."""
        platform.set_numeric_state("sensor.lux", 100.0)

        result = is_dark(platform, lux_entity="sensor.lux", lux_threshold=50.0)
        assert result is False

    def test_dark_by_sun(self, platform):
        """Test dark detection by sun entity."""
        platform.set_state("sun.sun", "below_horizon")

        result = is_dark(platform)
        assert result is True

    def test_bright_by_sun(self, platform):
        """Test bright detection by sun entity."""
        platform.set_state("sun.sun", "above_horizon")

        result = is_dark(platform)
        assert result is False


class TestIsNighttime:
    """Tests for is_nighttime helper function."""

    def test_nighttime(self, platform):
        """Test nighttime detection."""
        platform.set_state("sun.sun", "below_horizon")

        result = is_nighttime(platform)
        assert result is True

    def test_daytime(self, platform):
        """Test daytime detection."""
        platform.set_state("sun.sun", "above_horizon")

        result = is_nighttime(platform)
        assert result is False
