"""Tests for lighting presets."""

from home_topology.modules.lighting import (
    lights_on_when_occupied,
    lights_off_when_vacant,
    scene_when_occupied,
    adaptive_lighting,
)
from home_topology.modules.automation import (
    EventTriggerConfig,
    ServiceCallAction,
    DelayAction,
    TimeOfDayCondition,
    LuxLevelCondition,
    StateCondition,
)


class TestLightsOnWhenOccupied:
    """Tests for lights_on_when_occupied preset."""

    def test_basic_rule(self):
        """Test basic light-on rule."""
        rule = lights_on_when_occupied(
            "kitchen_lights",
            "light.kitchen_ceiling",
        )

        assert rule.id == "kitchen_lights"
        assert rule.enabled is True
        assert isinstance(rule.trigger, EventTriggerConfig)
        assert rule.trigger.payload_match == {"occupied": True}

        # Should have state condition (sun.sun = below_horizon)
        assert len(rule.conditions) == 1
        assert isinstance(rule.conditions[0], StateCondition)
        assert rule.conditions[0].entity_id == "sun.sun"
        assert rule.conditions[0].state == "below_horizon"

        # Should have light.turn_on action
        assert len(rule.actions) == 1
        assert isinstance(rule.actions[0], ServiceCallAction)
        assert rule.actions[0].service == "light.turn_on"

    def test_with_lux_sensor(self):
        """Test with lux sensor condition."""
        rule = lights_on_when_occupied(
            "kitchen_lights",
            "light.kitchen_ceiling",
            lux_sensor="sensor.kitchen_lux",
            lux_threshold=75.0,
        )

        # Should use lux condition instead of time
        assert len(rule.conditions) == 1
        assert isinstance(rule.conditions[0], LuxLevelCondition)
        assert rule.conditions[0].entity_id == "sensor.kitchen_lux"
        assert rule.conditions[0].below == 75.0

    def test_with_custom_brightness(self):
        """Test with custom brightness."""
        rule = lights_on_when_occupied(
            "kitchen_lights",
            "light.kitchen_ceiling",
            brightness_pct=50,
        )

        action = rule.actions[0]
        assert action.data["brightness_pct"] == 50

    def test_always_on(self):
        """Test without dark condition."""
        rule = lights_on_when_occupied(
            "garage_lights",
            "light.garage",
            only_when_dark=False,
        )

        # Should have no conditions
        assert len(rule.conditions) == 0

    def test_custom_dark_entity(self):
        """Test with custom dark entity."""
        rule = lights_on_when_occupied(
            "bedroom_lights",
            "light.bedroom",
            dark_entity="binary_sensor.is_dark",
            dark_state="on",
        )

        assert len(rule.conditions) == 1
        assert isinstance(rule.conditions[0], StateCondition)
        assert rule.conditions[0].entity_id == "binary_sensor.is_dark"
        assert rule.conditions[0].state == "on"


class TestLightsOffWhenVacant:
    """Tests for lights_off_when_vacant preset."""

    def test_basic_rule(self):
        """Test basic light-off rule."""
        rule = lights_off_when_vacant(
            "kitchen_lights_off",
            "light.kitchen_ceiling",
        )

        assert rule.id == "kitchen_lights_off"
        assert rule.trigger.payload_match == {"occupied": False}

        # Should have delay + turn_off
        assert len(rule.actions) == 2
        assert isinstance(rule.actions[0], DelayAction)
        assert rule.actions[0].seconds == 30  # Default
        assert isinstance(rule.actions[1], ServiceCallAction)
        assert rule.actions[1].service == "light.turn_off"

    def test_custom_delay(self):
        """Test with custom delay."""
        rule = lights_off_when_vacant(
            "kitchen_lights_off",
            "light.kitchen_ceiling",
            delay_seconds=120,
        )

        assert rule.actions[0].seconds == 120

    def test_no_delay(self):
        """Test with no delay."""
        rule = lights_off_when_vacant(
            "kitchen_lights_off",
            "light.kitchen_ceiling",
            delay_seconds=0,
        )

        # Should only have turn_off action (no delay)
        assert len(rule.actions) == 1
        assert isinstance(rule.actions[0], ServiceCallAction)


class TestSceneWhenOccupied:
    """Tests for scene_when_occupied preset."""

    def test_basic_rule(self):
        """Test basic scene rule."""
        rule = scene_when_occupied(
            "evening_scene",
            "scene.living_room_evening",
        )

        assert len(rule.conditions) == 0  # No dark condition by default
        assert rule.actions[0].service == "scene.turn_on"
        assert rule.actions[0].entity_id == "scene.living_room_evening"

    def test_only_when_dark(self):
        """Test with dark condition."""
        rule = scene_when_occupied(
            "evening_scene",
            "scene.living_room_evening",
            only_when_dark=True,
        )

        assert len(rule.conditions) == 1
        assert isinstance(rule.conditions[0], StateCondition)
        assert rule.conditions[0].entity_id == "sun.sun"
        assert rule.conditions[0].state == "below_horizon"


class TestAdaptiveLighting:
    """Tests for adaptive_lighting preset."""

    def test_creates_multiple_rules(self):
        """Test that adaptive lighting creates multiple rules."""
        rules = adaptive_lighting(
            "living_room",
            "light.living_room_main",
        )

        assert len(rules) == 4  # Day, evening, night, off
        rule_ids = [r.id for r in rules]
        assert "living_room_day" in rule_ids
        assert "living_room_evening" in rule_ids
        assert "living_room_night" in rule_ids
        assert "living_room_off" in rule_ids

    def test_brightness_levels(self):
        """Test brightness levels for each time period."""
        rules = adaptive_lighting(
            "living_room",
            "light.living_room_main",
            day_brightness=100,
            evening_brightness=60,
            night_brightness=20,
        )

        # Find each rule and check brightness
        for rule in rules:
            if rule.id == "living_room_day":
                assert rule.actions[0].data["brightness_pct"] == 100
            elif rule.id == "living_room_evening":
                assert rule.actions[0].data["brightness_pct"] == 60
            elif rule.id == "living_room_night":
                assert rule.actions[0].data["brightness_pct"] == 20

    def test_time_conditions(self):
        """Test time conditions for each period."""
        rules = adaptive_lighting(
            "living_room",
            "light.living_room_main",
            day_start="07:00:00",
            evening_start="19:00:00",
            night_start="23:00:00",
        )

        for rule in rules:
            if rule.id == "living_room_day":
                time_cond = rule.conditions[0]
                assert isinstance(time_cond, TimeOfDayCondition)
                assert time_cond.after == "07:00:00"
                assert time_cond.before == "19:00:00"
            elif rule.id == "living_room_evening":
                time_cond = rule.conditions[0]
                assert time_cond.after == "19:00:00"
                assert time_cond.before == "23:00:00"
            elif rule.id == "living_room_night":
                time_cond = rule.conditions[0]
                assert time_cond.after == "23:00:00"
                assert time_cond.before == "07:00:00"

    def test_off_rule_delay(self):
        """Test that off rule has correct delay."""
        rules = adaptive_lighting(
            "living_room",
            "light.living_room_main",
            turn_off_delay=60,
        )

        off_rule = next(r for r in rules if r.id == "living_room_off")
        assert off_rule.actions[0].seconds == 60

    def test_with_lux_sensor(self):
        """Test adaptive lighting with lux sensor."""
        rules = adaptive_lighting(
            "living_room",
            "light.living_room_main",
            lux_sensor="sensor.living_room_lux",
            lux_threshold=75.0,
        )

        # Day rule should have lux condition
        day_rule = next(r for r in rules if r.id == "living_room_day")
        lux_conditions = [c for c in day_rule.conditions if isinstance(c, LuxLevelCondition)]
        assert len(lux_conditions) == 1
        assert lux_conditions[0].entity_id == "sensor.living_room_lux"
        assert lux_conditions[0].below == 75.0
