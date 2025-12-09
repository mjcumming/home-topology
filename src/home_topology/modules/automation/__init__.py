"""
Automation engine for home-topology.

Provides rule-based automation with triggers, conditions, and actions.
Domain modules (lighting, climate, media) use this engine internally.

Features:
- Rule-based automation (trigger → condition → action)
- Event, state, and time triggers
- Time-of-day, lux-level, entity state, and location conditions
- Service call and delay actions
- Device state checking (avoid redundant commands)
- Execution history for debugging

Architecture:
    This module provides the generic automation engine. Domain-specific
    modules (lighting/, climate/, etc.) build on top of this engine
    to provide simpler, domain-specific APIs.

    ┌─────────────────────────────────────────────┐
    │          Domain Modules (lighting, etc.)    │
    │                     │                       │
    │                     ▼                       │
    │          ┌─────────────────────┐            │
    │          │  Automation Engine  │            │
    │          └─────────────────────┘            │
    └─────────────────────────────────────────────┘
"""

from .module import AutomationModule
from .models import (
    # Enums
    TriggerType,
    ConditionType,
    ActionType,
    ExecutionMode,
    # Triggers
    EventTriggerConfig,
    StateTriggerConfig,
    TimeTriggerConfig,
    TriggerConfig,
    # Conditions
    TimeOfDayCondition,
    StateCondition,
    NumericStateCondition,
    LuxLevelCondition,
    LocationOccupiedCondition,
    DayOfWeekCondition,
    ConditionConfig,
    # Actions
    ServiceCallAction,
    DelayAction,
    ActionConfig,
    # Rule
    AutomationRule,
    RuleExecution,
    LocationAutomationConfig,
)
from .adapter import PlatformAdapter, MockPlatformAdapter
from .engine import AutomationEngine, EngineResult
from .evaluators import ConditionEvaluator, is_dark, is_nighttime

# Generic presets that aren't domain-specific
from .presets import (
    switch_off_when_vacant,
    fan_off_when_vacant,
    media_off_when_vacant,
)

__all__ = [
    # Main module
    "AutomationModule",
    # Engine
    "AutomationEngine",
    "EngineResult",
    # Adapter
    "PlatformAdapter",
    "MockPlatformAdapter",
    # Evaluators
    "ConditionEvaluator",
    "is_dark",
    "is_nighttime",
    # Enums
    "TriggerType",
    "ConditionType",
    "ActionType",
    "ExecutionMode",
    # Triggers
    "EventTriggerConfig",
    "StateTriggerConfig",
    "TimeTriggerConfig",
    "TriggerConfig",
    # Conditions
    "TimeOfDayCondition",
    "StateCondition",
    "NumericStateCondition",
    "LuxLevelCondition",
    "LocationOccupiedCondition",
    "DayOfWeekCondition",
    "ConditionConfig",
    # Actions
    "ServiceCallAction",
    "DelayAction",
    "ActionConfig",
    # Rule
    "AutomationRule",
    "RuleExecution",
    "LocationAutomationConfig",
    # Generic presets
    "switch_off_when_vacant",
    "fan_off_when_vacant",
    "media_off_when_vacant",
]
