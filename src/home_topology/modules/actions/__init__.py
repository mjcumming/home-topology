"""
Actions module - DEPRECATED, use automation module instead.

This module provides backwards compatibility for code using the old
"actions" naming. All functionality has been moved to the "automation"
module and the "lighting" module.

Migration:
    # Old imports
    from home_topology.modules.actions import ActionsModule, lights_on_when_occupied

    # New imports
    from home_topology.modules.automation import AutomationModule
    from home_topology.modules.lighting import lights_on_when_occupied

The "actions" name has been replaced with "automation" to better reflect
that this is a general-purpose automation engine, not just "actions".

Lighting-specific presets have moved to the lighting module.
"""

import warnings

from home_topology.modules.automation import (
    ActionConfig,
    ActionType,
    AutomationEngine,
    AutomationEngine as ActionsEngine,
    AutomationModule,
    AutomationModule as ActionsModule,
    AutomationRule,
    AutomationRule as ActionRule,
    ConditionConfig,
    ConditionEvaluator,
    ConditionType,
    DayOfWeekCondition,
    DelayAction,
    EngineResult,
    EngineResult as ActionEngineResult,
    EventTriggerConfig,
    ExecutionMode,
    LocationAutomationConfig,
    LocationAutomationConfig as LocationActionsConfig,
    LocationOccupiedCondition,
    LuxLevelCondition,
    MockPlatformAdapter,
    NumericStateCondition,
    PlatformAdapter,
    RuleExecution,
    RuleExecution as ActionExecution,
    ServiceCallAction,
    StateCondition,
    StateTriggerConfig,
    TimeOfDayCondition,
    TimeTriggerConfig,
    TriggerConfig,
    TriggerType,
    fan_off_when_vacant,
    is_dark,
    is_nighttime,
    media_off_when_vacant,
    switch_off_when_vacant,
)
from home_topology.modules.lighting import (
    adaptive_lighting,
    lights_off_when_vacant,
    lights_on_when_occupied,
    scene_when_occupied,
)

# Show deprecation warning on import
warnings.warn(
    "home_topology.modules.actions is deprecated. "
    "Use home_topology.modules.automation for the engine and "
    "home_topology.modules.lighting for lighting presets.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    # Main module
    "ActionsModule",
    "AutomationModule",
    # Engine
    "ActionsEngine",
    "AutomationEngine",
    "ActionEngineResult",
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
    "ActionRule",
    "AutomationRule",
    "ActionExecution",
    "RuleExecution",
    "LocationActionsConfig",
    "LocationAutomationConfig",
    # All presets (for backwards compatibility)
    "lights_on_when_occupied",
    "lights_off_when_vacant",
    "switch_off_when_vacant",
    "fan_off_when_vacant",
    "media_off_when_vacant",
    "scene_when_occupied",
    "adaptive_lighting",
]
