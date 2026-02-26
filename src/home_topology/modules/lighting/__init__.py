"""
Lighting module for home-topology.

Provides occupancy-based lighting automation with domain-specific features.

This module builds on top of the automation engine to provide:
- Simple, lighting-focused configuration
- Adaptive lighting (brightness by time of day)
- Light level (lux) awareness
- Scene activation
- Pre-built presets for common patterns

Architecture:
    The lighting module translates high-level lighting configuration
    into automation rules that run on the automation engine.

    ┌─────────────────────────────────────┐
    │         Lighting Module             │
    │   (domain-specific API & presets)   │
    │                │                    │
    │                ▼                    │
    │   ┌─────────────────────────┐       │
    │   │   Automation Engine     │       │
    │   │   (rule execution)      │       │
    │   └─────────────────────────┘       │
    └─────────────────────────────────────┘

Common Use Cases:
- Turn on lights when area becomes occupied (with time/lux conditions)
- Turn off lights when area becomes vacant (with delay)
- Adjust brightness based on time of day
- Activate scenes based on occupancy
"""

# Re-export models commonly used with lighting
from home_topology.modules.automation import (
    AutomationRule,
    DelayAction,
    EventTriggerConfig,
    ExecutionMode,
    LuxLevelCondition,
    ServiceCallAction,
    StateCondition,
    TimeOfDayCondition,
)

from .presets import (
    adaptive_lighting,
    lights_off_when_vacant,
    lights_on_when_occupied,
    scene_when_occupied,
)

__all__ = [
    # Lighting presets
    "lights_on_when_occupied",
    "lights_off_when_vacant",
    "scene_when_occupied",
    "adaptive_lighting",
    # Re-exported for convenience
    "AutomationRule",
    "EventTriggerConfig",
    "TimeOfDayCondition",
    "StateCondition",
    "LuxLevelCondition",
    "ServiceCallAction",
    "DelayAction",
    "ExecutionMode",
]
