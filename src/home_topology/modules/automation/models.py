"""
Data models for the Automation engine.

Defines rules, triggers, conditions, and actions for automation.
"""

from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Any, Dict, List, Optional, FrozenSet


# =============================================================================
# Enums
# =============================================================================


class TriggerType(Enum):
    """Types of triggers that can activate a rule."""

    EVENT = "event"  # Semantic event (e.g., occupancy.changed)
    STATE = "state"  # Entity state change
    TIME = "time"  # Specific time of day


class ConditionType(Enum):
    """Types of conditions that must be met for actions to execute."""

    TIME_OF_DAY = "time_of_day"  # Time window (supports sunrise/sunset)
    STATE = "state"  # Entity equals specific state
    NUMERIC_STATE = "numeric_state"  # Entity above/below threshold
    LOCATION_OCCUPIED = "location_occupied"  # Check occupancy of a location
    DAY_OF_WEEK = "day_of_week"  # Specific days
    LUX_LEVEL = "lux_level"  # Light level condition (alias for numeric_state)


class ActionType(Enum):
    """Types of actions that can be executed."""

    SERVICE_CALL = "service_call"  # Generic HA service call
    DELAY = "delay"  # Wait before next action
    # Future: CHOOSE, REPEAT, etc.


class ExecutionMode(Enum):
    """How to handle multiple triggers of the same rule."""

    SINGLE = "single"  # Block if already running
    RESTART = "restart"  # Cancel previous, start new
    PARALLEL = "parallel"  # Allow multiple simultaneous


# =============================================================================
# Trigger Configs
# =============================================================================


@dataclass(frozen=True)
class EventTriggerConfig:
    """Trigger on semantic events like occupancy.changed."""

    event_type: str  # e.g., "occupancy.changed"
    payload_match: Dict[str, Any] = field(default_factory=dict)
    # e.g., {"occupied": True} to only trigger when occupied becomes True

    @property
    def trigger_type(self) -> TriggerType:
        return TriggerType.EVENT


@dataclass(frozen=True)
class StateTriggerConfig:
    """Trigger on entity state changes."""

    entity_id: str
    to_state: Optional[str] = None  # State to trigger on
    from_state: Optional[str] = None  # Previous state (optional)
    for_seconds: int = 0  # State must be held for this duration

    @property
    def trigger_type(self) -> TriggerType:
        return TriggerType.STATE


@dataclass(frozen=True)
class TimeTriggerConfig:
    """Trigger at specific time."""

    at: time  # Time to trigger (e.g., time(7, 0, 0) for 7:00 AM)

    @property
    def trigger_type(self) -> TriggerType:
        return TriggerType.TIME


TriggerConfig = EventTriggerConfig | StateTriggerConfig | TimeTriggerConfig


# =============================================================================
# Condition Configs
# =============================================================================


@dataclass(frozen=True)
class TimeOfDayCondition:
    """Check if current time is within a window.

    Supports:
    - Fixed times: "22:00:00", "06:00:00"
    - Solar times: "sunset", "sunrise", "sunset-01:00", "sunrise+00:30"
    """

    after: Optional[str] = None  # e.g., "sunset", "22:00:00"
    before: Optional[str] = None  # e.g., "sunrise", "06:00:00"

    @property
    def condition_type(self) -> ConditionType:
        return ConditionType.TIME_OF_DAY


@dataclass(frozen=True)
class StateCondition:
    """Check if entity is in a specific state."""

    entity_id: str
    state: str  # Expected state value

    @property
    def condition_type(self) -> ConditionType:
        return ConditionType.STATE


@dataclass(frozen=True)
class NumericStateCondition:
    """Check if entity's numeric value is within range."""

    entity_id: str
    above: Optional[float] = None  # Value must be > this
    below: Optional[float] = None  # Value must be < this

    @property
    def condition_type(self) -> ConditionType:
        return ConditionType.NUMERIC_STATE


@dataclass(frozen=True)
class LuxLevelCondition:
    """Check light level from a lux sensor.

    Convenience wrapper around NumericStateCondition.
    Common pattern: only turn on lights if lux < threshold.
    """

    entity_id: str  # Lux sensor entity ID
    below: Optional[float] = None  # Trigger if lux < this (e.g., 50)
    above: Optional[float] = None  # Trigger if lux > this

    @property
    def condition_type(self) -> ConditionType:
        return ConditionType.LUX_LEVEL


@dataclass(frozen=True)
class LocationOccupiedCondition:
    """Check if a location is occupied or vacant."""

    location_id: str
    occupied: bool = True  # True = must be occupied, False = must be vacant

    @property
    def condition_type(self) -> ConditionType:
        return ConditionType.LOCATION_OCCUPIED


@dataclass(frozen=True)
class DayOfWeekCondition:
    """Check if current day is in the allowed set."""

    days: FrozenSet[str]  # e.g., frozenset({"mon", "tue", "wed", "thu", "fri"})

    @property
    def condition_type(self) -> ConditionType:
        return ConditionType.DAY_OF_WEEK


ConditionConfig = (
    TimeOfDayCondition
    | StateCondition
    | NumericStateCondition
    | LuxLevelCondition
    | LocationOccupiedCondition
    | DayOfWeekCondition
)


# =============================================================================
# Action Configs
# =============================================================================


@dataclass(frozen=True)
class ServiceCallAction:
    """Execute a platform service call (e.g., light.turn_on)."""

    service: str  # e.g., "light.turn_on", "switch.turn_off"
    entity_id: Optional[str] = None  # Target entity (can also be in data)
    data: Dict[str, Any] = field(default_factory=dict)  # Service data

    @property
    def action_type(self) -> ActionType:
        return ActionType.SERVICE_CALL


@dataclass(frozen=True)
class DelayAction:
    """Wait before executing next action."""

    seconds: int  # Delay in seconds

    @property
    def action_type(self) -> ActionType:
        return ActionType.DELAY


ActionConfig = ServiceCallAction | DelayAction


# =============================================================================
# Automation Rule
# =============================================================================


@dataclass
class AutomationRule:
    """A complete automation rule.

    Consists of:
    - id: Unique identifier
    - enabled: Whether rule is active
    - trigger: What event/condition activates the rule
    - conditions: All must be true for actions to run
    - actions: What to execute when triggered
    - mode: How to handle concurrent triggers
    """

    id: str
    enabled: bool
    trigger: TriggerConfig
    conditions: List[ConditionConfig]
    actions: List[ActionConfig]
    mode: ExecutionMode = ExecutionMode.RESTART

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for storage/transport."""
        return {
            "id": self.id,
            "enabled": self.enabled,
            "trigger": self._serialize_trigger(),
            "conditions": [self._serialize_condition(c) for c in self.conditions],
            "actions": [self._serialize_action(a) for a in self.actions],
            "mode": self.mode.value,
        }

    def _serialize_trigger(self) -> Dict[str, Any]:
        """Serialize trigger config."""
        if isinstance(self.trigger, EventTriggerConfig):
            return {
                "type": "event",
                "event_type": self.trigger.event_type,
                "payload_match": dict(self.trigger.payload_match),
            }
        elif isinstance(self.trigger, StateTriggerConfig):
            return {
                "type": "state",
                "entity_id": self.trigger.entity_id,
                "to_state": self.trigger.to_state,
                "from_state": self.trigger.from_state,
                "for_seconds": self.trigger.for_seconds,
            }
        elif isinstance(self.trigger, TimeTriggerConfig):
            return {
                "type": "time",
                "at": self.trigger.at.isoformat(),
            }
        return {}

    def _serialize_condition(self, c: ConditionConfig) -> Dict[str, Any]:
        """Serialize condition config."""
        if isinstance(c, TimeOfDayCondition):
            return {"type": "time_of_day", "after": c.after, "before": c.before}
        elif isinstance(c, StateCondition):
            return {"type": "state", "entity_id": c.entity_id, "state": c.state}
        elif isinstance(c, NumericStateCondition):
            return {
                "type": "numeric_state",
                "entity_id": c.entity_id,
                "above": c.above,
                "below": c.below,
            }
        elif isinstance(c, LuxLevelCondition):
            return {
                "type": "lux_level",
                "entity_id": c.entity_id,
                "below": c.below,
                "above": c.above,
            }
        elif isinstance(c, LocationOccupiedCondition):
            return {
                "type": "location_occupied",
                "location_id": c.location_id,
                "occupied": c.occupied,
            }
        elif isinstance(c, DayOfWeekCondition):
            return {"type": "day_of_week", "days": list(c.days)}
        return {}

    def _serialize_action(self, a: ActionConfig) -> Dict[str, Any]:
        """Serialize action config."""
        if isinstance(a, ServiceCallAction):
            result: Dict[str, Any] = {"type": "service_call", "service": a.service}
            if a.entity_id:
                result["entity_id"] = a.entity_id
            if a.data:
                result["data"] = dict(a.data)
            return result
        elif isinstance(a, DelayAction):
            return {"type": "delay", "seconds": a.seconds}
        return {}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AutomationRule":
        """Deserialize from dict."""
        return cls(
            id=data["id"],
            enabled=data.get("enabled", True),
            trigger=cls._parse_trigger(data["trigger"]),
            conditions=[cls._parse_condition(c) for c in data.get("conditions", [])],
            actions=[cls._parse_action(a) for a in data.get("actions", [])],
            mode=ExecutionMode(data.get("mode", "restart")),
        )

    @staticmethod
    def _parse_trigger(data: Dict[str, Any]) -> TriggerConfig:
        """Parse trigger config from dict."""
        trigger_type = data.get("type", "event")

        if trigger_type == "event":
            return EventTriggerConfig(
                event_type=data["event_type"],
                payload_match=data.get("payload_match", {}),
            )
        elif trigger_type == "state":
            return StateTriggerConfig(
                entity_id=data["entity_id"],
                to_state=data.get("to_state"),
                from_state=data.get("from_state"),
                for_seconds=data.get("for_seconds", 0),
            )
        elif trigger_type == "time":
            return TimeTriggerConfig(
                at=time.fromisoformat(data["at"]),
            )
        else:
            raise ValueError(f"Unknown trigger type: {trigger_type}")

    @staticmethod
    def _parse_condition(data: Dict[str, Any]) -> ConditionConfig:
        """Parse condition config from dict."""
        condition_type = data["type"]

        if condition_type == "time_of_day":
            return TimeOfDayCondition(
                after=data.get("after"),
                before=data.get("before"),
            )
        elif condition_type == "state":
            return StateCondition(
                entity_id=data["entity_id"],
                state=data["state"],
            )
        elif condition_type == "numeric_state":
            return NumericStateCondition(
                entity_id=data["entity_id"],
                above=data.get("above"),
                below=data.get("below"),
            )
        elif condition_type == "lux_level":
            return LuxLevelCondition(
                entity_id=data["entity_id"],
                below=data.get("below"),
                above=data.get("above"),
            )
        elif condition_type == "location_occupied":
            return LocationOccupiedCondition(
                location_id=data["location_id"],
                occupied=data.get("occupied", True),
            )
        elif condition_type == "day_of_week":
            return DayOfWeekCondition(
                days=frozenset(data["days"]),
            )
        else:
            raise ValueError(f"Unknown condition type: {condition_type}")

    @staticmethod
    def _parse_action(data: Dict[str, Any]) -> ActionConfig:
        """Parse action config from dict."""
        action_type = data.get("type", "service_call")

        if action_type == "service_call":
            return ServiceCallAction(
                service=data["service"],
                entity_id=data.get("entity_id"),
                data=data.get("data", {}),
            )
        elif action_type == "delay":
            return DelayAction(
                seconds=data["seconds"],
            )
        else:
            raise ValueError(f"Unknown action type: {action_type}")


# =============================================================================
# Execution Records
# =============================================================================


@dataclass
class RuleExecution:
    """Record of a rule execution (for history/debugging)."""

    rule_id: str
    location_id: str
    trigger_event_type: str
    conditions_met: bool
    actions_executed: List[Dict[str, Any]]
    success: bool
    error: Optional[str]
    timestamp: datetime
    duration_ms: int


# =============================================================================
# Location Automation Config
# =============================================================================


@dataclass
class LocationAutomationConfig:
    """Per-location configuration for the automation module."""

    version: int = 1
    enabled: bool = True
    trust_device_state: bool = True  # Check state before sending command
    rules: List[AutomationRule] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "version": self.version,
            "enabled": self.enabled,
            "trust_device_state": self.trust_device_state,
            "rules": [r.to_dict() for r in self.rules],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LocationAutomationConfig":
        """Deserialize from dict."""
        return cls(
            version=data.get("version", 1),
            enabled=data.get("enabled", True),
            trust_device_state=data.get("trust_device_state", True),
            rules=[AutomationRule.from_dict(r) for r in data.get("rules", [])],
        )


# =============================================================================
# Backwards Compatibility Aliases
# =============================================================================

# These aliases allow gradual migration from "actions" naming
ActionRule = AutomationRule
ActionExecution = RuleExecution
LocationActionsConfig = LocationAutomationConfig
