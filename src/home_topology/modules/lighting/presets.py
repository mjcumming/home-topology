"""
Lighting presets - pre-configured rules for common lighting automation patterns.

These presets provide easy-to-use templates for occupancy-based lighting.
They generate AutomationRules that can be added to the automation engine.

Design Note:
    These presets use entity states for environmental conditions
    (like "is it dark?") rather than calculating sun position.
    The integration layer should provide:
    - sun.sun entity (Home Assistant built-in)
    - Or custom helpers like binary_sensor.is_dark

    This keeps the core library platform-agnostic while allowing
    the integration to provide smart defaults.
"""

from typing import Optional

from home_topology.modules.automation import (
    AutomationRule,
    EventTriggerConfig,
    ServiceCallAction,
    DelayAction,
    TimeOfDayCondition,
    LuxLevelCondition,
    StateCondition,
    ExecutionMode,
)

# Default entity for darkness detection (Home Assistant sun entity)
DEFAULT_DARK_ENTITY = "sun.sun"
DEFAULT_DARK_STATE = "below_horizon"


def lights_on_when_occupied(
    rule_id: str,
    light_entity: str,
    *,
    brightness_pct: int = 100,
    only_when_dark: bool = True,
    lux_sensor: Optional[str] = None,
    lux_threshold: float = 50.0,
    dark_entity: str = DEFAULT_DARK_ENTITY,
    dark_state: str = DEFAULT_DARK_STATE,
    enabled: bool = True,
) -> AutomationRule:
    """
    Create a rule to turn lights on when area becomes occupied.

    Args:
        rule_id: Unique rule ID
        light_entity: Light entity ID (e.g., "light.kitchen_ceiling")
        brightness_pct: Brightness level (0-100)
        only_when_dark: Only turn on when dark (uses dark_entity or lux_sensor)
        lux_sensor: Optional lux sensor for light-level based triggering
        lux_threshold: Lux level below which to turn on lights
        dark_entity: Entity to check for darkness (default: sun.sun)
        dark_state: State indicating dark (default: below_horizon)
        enabled: Whether rule is active

    Returns:
        Configured AutomationRule

    Example:
        # With lux sensor (most accurate)
        rule = lights_on_when_occupied(
            "kitchen_lights_on",
            "light.kitchen_ceiling",
            brightness_pct=80,
            lux_sensor="sensor.kitchen_lux",
        )

        # With sun entity (default)
        rule = lights_on_when_occupied(
            "garage_lights_on",
            "light.garage",
            only_when_dark=True,  # Uses sun.sun state
        )

        # With custom dark helper
        rule = lights_on_when_occupied(
            "bedroom_lights_on",
            "light.bedroom",
            dark_entity="binary_sensor.is_dark",
            dark_state="on",
        )
    """
    conditions = []

    if lux_sensor:
        # Use lux sensor for light level (most accurate)
        conditions.append(LuxLevelCondition(entity_id=lux_sensor, below=lux_threshold))
    elif only_when_dark:
        # Use entity state for darkness check
        conditions.append(StateCondition(entity_id=dark_entity, state=dark_state))

    actions = [
        ServiceCallAction(
            service="light.turn_on",
            entity_id=light_entity,
            data={"brightness_pct": brightness_pct},
        )
    ]

    return AutomationRule(
        id=rule_id,
        enabled=enabled,
        trigger=EventTriggerConfig(
            event_type="occupancy.changed",
            payload_match={"occupied": True},
        ),
        conditions=conditions,
        actions=actions,
        mode=ExecutionMode.RESTART,
    )


def lights_off_when_vacant(
    rule_id: str,
    light_entity: str,
    *,
    delay_seconds: int = 30,
    enabled: bool = True,
) -> AutomationRule:
    """
    Create a rule to turn lights off when area becomes vacant.

    Args:
        rule_id: Unique rule ID
        light_entity: Light entity ID (e.g., "light.kitchen_ceiling")
        delay_seconds: Delay before turning off (gives time to re-trigger)
        enabled: Whether rule is active

    Returns:
        Configured AutomationRule

    Example:
        rule = lights_off_when_vacant(
            "kitchen_lights_off",
            "light.kitchen_ceiling",
            delay_seconds=60,
        )
    """
    actions = []

    if delay_seconds > 0:
        actions.append(DelayAction(seconds=delay_seconds))

    actions.append(
        ServiceCallAction(
            service="light.turn_off",
            entity_id=light_entity,
        )
    )

    return AutomationRule(
        id=rule_id,
        enabled=enabled,
        trigger=EventTriggerConfig(
            event_type="occupancy.changed",
            payload_match={"occupied": False},
        ),
        conditions=[],
        actions=actions,
        mode=ExecutionMode.RESTART,  # Restart cancels pending delay if re-occupied
    )


def scene_when_occupied(
    rule_id: str,
    scene_entity: str,
    *,
    only_when_dark: bool = False,
    dark_entity: str = DEFAULT_DARK_ENTITY,
    dark_state: str = DEFAULT_DARK_STATE,
    enabled: bool = True,
) -> AutomationRule:
    """
    Create a rule to activate a scene when area becomes occupied.

    Args:
        rule_id: Unique rule ID
        scene_entity: Scene entity ID (e.g., "scene.living_room_movie")
        only_when_dark: Only activate when dark
        dark_entity: Entity to check for darkness (default: sun.sun)
        dark_state: State indicating dark (default: below_horizon)
        enabled: Whether rule is active

    Returns:
        Configured AutomationRule

    Example:
        rule = scene_when_occupied(
            "evening_ambiance",
            "scene.living_room_evening",
            only_when_dark=True,
        )
    """
    conditions = []
    if only_when_dark:
        conditions.append(StateCondition(entity_id=dark_entity, state=dark_state))

    return AutomationRule(
        id=rule_id,
        enabled=enabled,
        trigger=EventTriggerConfig(
            event_type="occupancy.changed",
            payload_match={"occupied": True},
        ),
        conditions=conditions,
        actions=[
            ServiceCallAction(
                service="scene.turn_on",
                entity_id=scene_entity,
            )
        ],
        mode=ExecutionMode.RESTART,
    )


def adaptive_lighting(
    rule_id_prefix: str,
    light_entity: str,
    *,
    day_brightness: int = 100,
    evening_brightness: int = 70,
    night_brightness: int = 30,
    day_start: str = "06:00:00",
    evening_start: str = "18:00:00",
    night_start: str = "22:00:00",
    lux_sensor: Optional[str] = None,
    lux_threshold: float = 50.0,
    turn_off_delay: int = 30,
    enabled: bool = True,
) -> list[AutomationRule]:
    """
    Create a set of rules for adaptive lighting based on time of day.

    Creates multiple rules:
    - Daytime: full brightness (day_start to evening_start)
    - Evening: reduced brightness (evening_start to night_start)
    - Night: dim lighting (night_start to day_start)
    - Turn off when vacant

    Args:
        rule_id_prefix: Prefix for rule IDs (e.g., "kitchen")
        light_entity: Light entity ID
        day_brightness: Brightness during day (0-100)
        evening_brightness: Brightness during evening (0-100)
        night_brightness: Brightness during night (0-100)
        day_start: When daytime begins (default: 06:00)
        evening_start: When evening begins (default: 18:00)
        night_start: When night begins (default: 22:00)
        lux_sensor: Optional lux sensor for light-level detection
        lux_threshold: Lux threshold for "needs light"
        turn_off_delay: Delay before turning off when vacant
        enabled: Whether rules are active

    Returns:
        List of configured AutomationRules

    Example:
        rules = adaptive_lighting(
            "living_room",
            "light.living_room_main",
            evening_brightness=60,
            night_brightness=20,
        )

    Note:
        Times are fixed (not solar-relative). For dynamic sunset/sunrise
        times, the integration layer can reconfigure rules when sun
        position changes, or use the simpler lights_on_when_occupied()
        with sun.sun state check.
    """
    rules = []

    # Daytime rule (day_start to evening_start)
    day_conditions = [TimeOfDayCondition(after=day_start, before=evening_start)]
    if lux_sensor:
        day_conditions.append(LuxLevelCondition(entity_id=lux_sensor, below=lux_threshold))

    rules.append(
        AutomationRule(
            id=f"{rule_id_prefix}_day",
            enabled=enabled,
            trigger=EventTriggerConfig(
                event_type="occupancy.changed",
                payload_match={"occupied": True},
            ),
            conditions=day_conditions,
            actions=[
                ServiceCallAction(
                    service="light.turn_on",
                    entity_id=light_entity,
                    data={"brightness_pct": day_brightness},
                )
            ],
            mode=ExecutionMode.RESTART,
        )
    )

    # Evening rule (evening_start to night_start)
    rules.append(
        AutomationRule(
            id=f"{rule_id_prefix}_evening",
            enabled=enabled,
            trigger=EventTriggerConfig(
                event_type="occupancy.changed",
                payload_match={"occupied": True},
            ),
            conditions=[TimeOfDayCondition(after=evening_start, before=night_start)],
            actions=[
                ServiceCallAction(
                    service="light.turn_on",
                    entity_id=light_entity,
                    data={"brightness_pct": evening_brightness},
                )
            ],
            mode=ExecutionMode.RESTART,
        )
    )

    # Night rule (night_start to day_start - spans midnight)
    rules.append(
        AutomationRule(
            id=f"{rule_id_prefix}_night",
            enabled=enabled,
            trigger=EventTriggerConfig(
                event_type="occupancy.changed",
                payload_match={"occupied": True},
            ),
            conditions=[TimeOfDayCondition(after=night_start, before=day_start)],
            actions=[
                ServiceCallAction(
                    service="light.turn_on",
                    entity_id=light_entity,
                    data={"brightness_pct": night_brightness},
                )
            ],
            mode=ExecutionMode.RESTART,
        )
    )

    # Turn off when vacant
    rules.append(lights_off_when_vacant(f"{rule_id_prefix}_off", light_entity, delay_seconds=turn_off_delay, enabled=enabled))

    return rules


