"""
Platform adapter interface for the Automation engine.

The adapter provides an abstraction layer between the automation engine and
the host platform (Home Assistant, etc.). The integration layer provides
a concrete implementation.

Design Principle:
    The adapter is intentionally minimal. Complex logic like sun position
    calculations, "is it dark?" determinations, etc. belong in the integration
    layer. The integration should expose these as entity states that the
    core library can check with simple StateCondition checks.

    For example:
    - Integration exposes `binary_sensor.is_dark` based on sun + lux + time
    - Core library uses StateCondition(entity_id="binary_sensor.is_dark", state="on")

    This keeps the core library platform-agnostic and simple.
"""

from abc import ABC, abstractmethod
from datetime import datetime, time
from typing import Any, Dict, Optional


class PlatformAdapter(ABC):
    """
    Abstract interface for platform operations.

    The host platform (HA integration) provides a concrete implementation
    that translates these calls to platform-specific operations.

    This interface is intentionally minimal:
    - call_service: Execute actions
    - get_state: Check entity states
    - get_numeric_state: Check numeric sensor values
    - get_current_time: Get current time

    Environmental context (sun position, darkness, etc.) should be exposed
    by the integration as entity states, not as adapter methods.
    """

    @abstractmethod
    def call_service(
        self,
        domain: str,
        service: str,
        entity_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Execute a platform service call.

        Args:
            domain: Service domain (e.g., "light", "switch", "media_player")
            service: Service name (e.g., "turn_on", "turn_off")
            entity_id: Target entity (optional, can be in data)
            data: Additional service data

        Returns:
            True if service call succeeded, False otherwise
        """
        pass

    @abstractmethod
    def get_state(self, entity_id: str) -> Optional[str]:
        """
        Get the current state of an entity.

        Args:
            entity_id: Entity to query

        Returns:
            Current state string, or None if entity doesn't exist
        """
        pass

    @abstractmethod
    def get_numeric_state(self, entity_id: str) -> Optional[float]:
        """
        Get the numeric value of an entity's state.

        Args:
            entity_id: Entity to query (e.g., sensor.living_room_lux)

        Returns:
            Numeric value, or None if unavailable/not numeric
        """
        pass

    @abstractmethod
    def get_current_time(self) -> datetime:
        """
        Get current time from platform.

        Returns:
            Current datetime (timezone-aware)
        """
        pass

    def parse_time_expression(self, expr: str) -> time:
        """
        Parse a fixed time expression.

        Args:
            expr: Time string in HH:MM:SS or HH:MM format

        Returns:
            Parsed time value

        Note:
            Solar times (sunset, sunrise) are NOT supported here.
            Use StateCondition with sun.sun or integration-provided
            helpers like binary_sensor.is_dark instead.
        """
        return time.fromisoformat(expr.strip())


class MockPlatformAdapter(PlatformAdapter):
    """
    Mock adapter for testing.

    Tracks service calls and allows setting entity states.

    For testing "is dark" conditions, set up states like:
        adapter.set_state("sun.sun", "below_horizon")
        adapter.set_state("binary_sensor.is_dark", "on")
    """

    def __init__(self) -> None:
        self._states: Dict[str, str] = {}
        self._numeric_states: Dict[str, float] = {}
        self._service_calls: list[tuple[str, str, Optional[str], Optional[Dict]]] = []
        self._current_time: Optional[datetime] = None

    def set_state(self, entity_id: str, state: str) -> None:
        """Set entity state for testing."""
        self._states[entity_id] = state

    def set_numeric_state(self, entity_id: str, value: float) -> None:
        """Set numeric entity state for testing."""
        self._numeric_states[entity_id] = value

    def set_current_time(self, dt: datetime) -> None:
        """Set current time for testing."""
        self._current_time = dt

    def get_service_calls(self) -> list[tuple[str, str, Optional[str], Optional[Dict]]]:
        """Get recorded service calls."""
        return self._service_calls.copy()

    def clear_service_calls(self) -> None:
        """Clear recorded service calls."""
        self._service_calls.clear()

    # PlatformAdapter implementation

    def call_service(
        self,
        domain: str,
        service: str,
        entity_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        self._service_calls.append((domain, service, entity_id, data))
        return True

    def get_state(self, entity_id: str) -> Optional[str]:
        return self._states.get(entity_id)

    def get_numeric_state(self, entity_id: str) -> Optional[float]:
        return self._numeric_states.get(entity_id)

    def get_current_time(self) -> datetime:
        if self._current_time:
            return self._current_time
        from datetime import UTC

        return datetime.now(UTC)


