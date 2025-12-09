"""
Generic automation presets - non-domain-specific rule templates.

These presets provide templates for automation patterns that don't
belong to a specific domain (lighting, climate, media).

Domain-specific presets live in their respective modules:
- lighting/ - lights_on_when_occupied, adaptive_lighting, etc.
- climate/ - (future) temperature schedules, etc.
- media/ - (future) media control, etc.
"""

from .models import (
    AutomationRule,
    EventTriggerConfig,
    ServiceCallAction,
    DelayAction,
    ExecutionMode,
)


def switch_off_when_vacant(
    rule_id: str,
    switch_entity: str,
    *,
    delay_seconds: int = 60,
    enabled: bool = True,
) -> AutomationRule:
    """
    Create a rule to turn off a switch/plug when area becomes vacant.

    Good for: exhaust fans, space heaters, decorative lights, etc.

    Args:
        rule_id: Unique rule ID
        switch_entity: Switch entity ID (e.g., "switch.bathroom_fan")
        delay_seconds: Delay before turning off
        enabled: Whether rule is active

    Returns:
        Configured AutomationRule

    Example:
        rule = switch_off_when_vacant(
            "bathroom_fan_off",
            "switch.bathroom_exhaust",
            delay_seconds=300,  # 5 minutes
        )
    """
    actions = []

    if delay_seconds > 0:
        actions.append(DelayAction(seconds=delay_seconds))

    actions.append(
        ServiceCallAction(
            service="switch.turn_off",
            entity_id=switch_entity,
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
        mode=ExecutionMode.RESTART,
    )


def fan_off_when_vacant(
    rule_id: str,
    fan_entity: str,
    *,
    delay_seconds: int = 300,
    enabled: bool = True,
) -> AutomationRule:
    """
    Create a rule to turn off exhaust/ceiling fan when area becomes vacant.

    Alias for switch_off_when_vacant with bathroom/kitchen-appropriate defaults.

    Args:
        rule_id: Unique rule ID
        fan_entity: Fan or switch entity ID
        delay_seconds: Delay before turning off (default 5 min for ventilation)
        enabled: Whether rule is active

    Returns:
        Configured AutomationRule
    """
    # Determine domain from entity ID
    domain = "fan" if fan_entity.startswith("fan.") else "switch"

    actions = []
    if delay_seconds > 0:
        actions.append(DelayAction(seconds=delay_seconds))

    actions.append(
        ServiceCallAction(
            service=f"{domain}.turn_off",
            entity_id=fan_entity,
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
        mode=ExecutionMode.RESTART,
    )


def media_off_when_vacant(
    rule_id: str,
    media_entity: str,
    *,
    delay_seconds: int = 600,
    enabled: bool = True,
) -> AutomationRule:
    """
    Create a rule to turn off media player when area becomes vacant.

    Uses a longer default delay (10 min) since users may step away briefly.

    Args:
        rule_id: Unique rule ID
        media_entity: Media player entity ID
        delay_seconds: Delay before turning off (default 10 min)
        enabled: Whether rule is active

    Returns:
        Configured AutomationRule

    Example:
        rule = media_off_when_vacant(
            "living_room_tv_off",
            "media_player.living_room_tv",
            delay_seconds=900,  # 15 minutes
        )
    """
    actions = []

    if delay_seconds > 0:
        actions.append(DelayAction(seconds=delay_seconds))

    actions.append(
        ServiceCallAction(
            service="media_player.turn_off",
            entity_id=media_entity,
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
        mode=ExecutionMode.RESTART,
    )
