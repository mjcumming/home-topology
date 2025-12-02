#!/usr/bin/env python3
"""
Demo of the ActionsModule with common automation patterns.

This example demonstrates:
1. Setting up actions with the mock platform adapter
2. Using presets for common patterns (lights, fans, media)
3. Custom rules with conditions (time of day, lux level)
4. Adaptive lighting with different brightness by time
5. Integration with occupancy events

Run with: python -m examples.actions_demo
"""

from datetime import datetime, UTC

from home_topology.core.bus import Event, EventBus
from home_topology.core.manager import LocationManager
from home_topology.modules.actions import (
    ActionsModule,
    MockPlatformAdapter,
    ActionRule,
    EventTriggerConfig,
    TimeOfDayCondition,
    LuxLevelCondition,
    StateCondition,
    ServiceCallAction,
    DelayAction,
    # Presets
    lights_on_when_occupied,
    lights_off_when_vacant,
    fan_off_when_vacant,
    media_off_when_vacant,
    adaptive_lighting,
)


def main():
    print("=" * 60)
    print("ActionsModule Demo")
    print("=" * 60)

    # Set up kernel components
    bus = EventBus()
    loc_manager = LocationManager()
    bus.set_location_manager(loc_manager)

    # Create some locations
    loc_manager.create_location("house", "House", is_explicit_root=True)
    loc_manager.create_location("kitchen", "Kitchen", parent_id="house")
    loc_manager.create_location("bathroom", "Bathroom", parent_id="house")
    loc_manager.create_location("living_room", "Living Room", parent_id="house")

    # Create mock platform adapter
    platform = MockPlatformAdapter()

    # Set up realistic time and sun state (integration provides this)
    platform.set_current_time(datetime(2025, 1, 15, 20, 0, 0, tzinfo=UTC))  # 8 PM
    platform.set_state("sun.sun", "below_horizon")  # It's dark

    # Set some entity states
    platform.set_state("light.kitchen_ceiling", "off")
    platform.set_state("switch.bathroom_exhaust", "on")
    platform.set_state("media_player.living_room_tv", "playing")
    platform.set_state("input_boolean.automation_enabled", "on")
    platform.set_numeric_state("sensor.kitchen_lux", 30.0)  # Dark

    # Create actions module with platform adapter
    actions = ActionsModule(platform=platform)
    actions.attach(bus, loc_manager)

    print("\n1. USING PRESETS (Common Patterns)")
    print("-" * 40)

    # Kitchen: lights on when occupied (with lux sensor)
    kitchen_lights_on = lights_on_when_occupied(
        "kitchen_lights_on",
        "light.kitchen_ceiling",
        brightness_pct=80,
        lux_sensor="sensor.kitchen_lux",
        lux_threshold=50.0,
    )
    actions.add_rule("kitchen", kitchen_lights_on)
    print(f"✓ Added: {kitchen_lights_on.id}")

    # Kitchen: lights off when vacant (30s delay)
    kitchen_lights_off = lights_off_when_vacant(
        "kitchen_lights_off",
        "light.kitchen_ceiling",
        delay_seconds=30,
    )
    actions.add_rule("kitchen", kitchen_lights_off)
    print(f"✓ Added: {kitchen_lights_off.id}")

    # Bathroom: exhaust fan off when vacant (5 min delay)
    bathroom_fan = fan_off_when_vacant(
        "bathroom_fan_off",
        "switch.bathroom_exhaust",
        delay_seconds=300,
    )
    actions.add_rule("bathroom", bathroom_fan)
    print(f"✓ Added: {bathroom_fan.id}")

    # Living room: TV off when vacant (15 min delay)
    tv_off = media_off_when_vacant(
        "living_room_tv_off",
        "media_player.living_room_tv",
        delay_seconds=900,
    )
    actions.add_rule("living_room", tv_off)
    print(f"✓ Added: {tv_off.id}")

    print("\n2. SIMULATING OCCUPANCY EVENTS")
    print("-" * 40)

    # Simulate kitchen becomes occupied
    print("\n→ Kitchen becomes OCCUPIED")
    bus.publish(
        Event(
            type="occupancy.changed",
            source="occupancy",
            location_id="kitchen",
            payload={"occupied": True, "previous_occupied": False, "reason": "trigger:motion"},
            timestamp=datetime.now(UTC),
        )
    )

    # Check what service calls were made
    calls = platform.get_service_calls()
    if calls:
        for domain, service, entity_id, data in calls:
            print(f"   Service called: {domain}.{service} -> {entity_id}")
            if data:
                print(f"   Data: {data}")
    else:
        print("   No service calls (light may already be on)")

    platform.clear_service_calls()

    # Simulate bathroom becomes vacant
    print("\n→ Bathroom becomes VACANT")
    bus.publish(
        Event(
            type="occupancy.changed",
            source="occupancy",
            location_id="bathroom",
            payload={"occupied": False, "previous_occupied": True, "reason": "timeout"},
            timestamp=datetime.now(UTC),
        )
    )

    calls = platform.get_service_calls()
    for domain, service, entity_id, data in calls:
        print(f"   Service called: {domain}.{service} -> {entity_id}")
    platform.clear_service_calls()

    print("\n3. CUSTOM RULE WITH MULTIPLE CONDITIONS")
    print("-" * 40)

    # Create a custom rule: only turn on lights if:
    # - It's after sunset
    # - Automation is enabled
    # - Lux level is low
    custom_rule = ActionRule(
        id="smart_kitchen_lights",
        enabled=True,
        trigger=EventTriggerConfig(
            event_type="occupancy.changed",
            payload_match={"occupied": True},
        ),
        conditions=[
            TimeOfDayCondition(after="sunset", before="sunrise"),
            StateCondition(entity_id="input_boolean.automation_enabled", state="on"),
            LuxLevelCondition(entity_id="sensor.kitchen_lux", below=50.0),
        ],
        actions=[
            ServiceCallAction(
                service="light.turn_on",
                entity_id="light.kitchen_under_cabinet",
                data={"brightness_pct": 50, "color_temp": 300},
            ),
        ],
    )
    actions.add_rule("kitchen", custom_rule)
    print(f"✓ Created custom rule with 3 conditions")
    print(f"   Conditions: time_of_day, state, lux_level")

    print("\n4. ADAPTIVE LIGHTING (Multiple Brightness Levels)")
    print("-" * 40)

    # Create adaptive lighting for living room
    adaptive_rules = adaptive_lighting(
        "living_room",
        "light.living_room_main",
        day_brightness=100,
        evening_brightness=70,
        night_brightness=30,
        evening_start="sunset",
        night_start="22:00:00",
        turn_off_delay=60,
    )

    for rule in adaptive_rules:
        actions.add_rule("living_room", rule)
        print(f"✓ Added: {rule.id}")

    print("\n5. VIEWING EXECUTION HISTORY")
    print("-" * 40)

    history = actions.get_history(limit=5)
    if history:
        for entry in history:
            status = "✓" if entry["success"] else "✗"
            conditions = "conditions met" if entry["conditions_met"] else "conditions not met"
            print(f"   {status} Rule: {entry['rule_id']}")
            print(f"     Location: {entry['location_id']}, {conditions}")
            print(f"     Actions: {entry['actions_executed']}")
    else:
        print("   No history yet")

    print("\n6. VIEWING RULES FOR A LOCATION")
    print("-" * 40)

    kitchen_rules = actions.get_rules("kitchen")
    print(f"Kitchen has {len(kitchen_rules)} rules:")
    for rule in kitchen_rules:
        status = "enabled" if rule.enabled else "disabled"
        print(f"   - {rule.id} ({status})")
        print(f"     Trigger: {rule.trigger.event_type}")
        print(f"     Conditions: {len(rule.conditions)}, Actions: {len(rule.actions)}")

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()

