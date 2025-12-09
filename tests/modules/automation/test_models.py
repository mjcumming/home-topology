"""Tests for automation models."""

from datetime import time

from home_topology.modules.automation import (
    AutomationRule,
    EventTriggerConfig,
    StateTriggerConfig,
    TimeTriggerConfig,
    TimeOfDayCondition,
    StateCondition,
    LuxLevelCondition,
    DayOfWeekCondition,
    ServiceCallAction,
    DelayAction,
    ExecutionMode,
    LocationAutomationConfig,
)


class TestAutomationRule:
    """Tests for AutomationRule serialization."""

    def test_serialize_simple_rule(self):
        """Test serializing a simple rule."""
        rule = AutomationRule(
            id="test_rule",
            enabled=True,
            trigger=EventTriggerConfig(
                event_type="occupancy.changed",
                payload_match={"occupied": True},
            ),
            conditions=[],
            actions=[
                ServiceCallAction(
                    service="light.turn_on",
                    entity_id="light.kitchen",
                )
            ],
            mode=ExecutionMode.RESTART,
        )

        data = rule.to_dict()

        assert data["id"] == "test_rule"
        assert data["enabled"] is True
        assert data["trigger"]["type"] == "event"
        assert data["trigger"]["event_type"] == "occupancy.changed"
        assert data["trigger"]["payload_match"] == {"occupied": True}
        assert len(data["actions"]) == 1
        assert data["actions"][0]["service"] == "light.turn_on"
        assert data["mode"] == "restart"

    def test_serialize_with_conditions(self):
        """Test serializing a rule with conditions."""
        rule = AutomationRule(
            id="test_rule",
            enabled=True,
            trigger=EventTriggerConfig(event_type="occupancy.changed"),
            conditions=[
                TimeOfDayCondition(after="18:00:00", before="23:00:00"),
                StateCondition(entity_id="sun.sun", state="below_horizon"),
            ],
            actions=[ServiceCallAction(service="light.turn_on", entity_id="light.test")],
        )

        data = rule.to_dict()

        assert len(data["conditions"]) == 2
        assert data["conditions"][0]["type"] == "time_of_day"
        assert data["conditions"][1]["type"] == "state"

    def test_deserialize_simple_rule(self):
        """Test deserializing a simple rule."""
        data = {
            "id": "test_rule",
            "enabled": True,
            "trigger": {
                "type": "event",
                "event_type": "occupancy.changed",
                "payload_match": {"occupied": True},
            },
            "conditions": [],
            "actions": [
                {"type": "service_call", "service": "light.turn_on", "entity_id": "light.kitchen"}
            ],
            "mode": "restart",
        }

        rule = AutomationRule.from_dict(data)

        assert rule.id == "test_rule"
        assert rule.enabled is True
        assert isinstance(rule.trigger, EventTriggerConfig)
        assert rule.trigger.event_type == "occupancy.changed"
        assert len(rule.actions) == 1
        assert rule.mode == ExecutionMode.RESTART

    def test_roundtrip_serialization(self):
        """Test that serialize/deserialize is lossless."""
        original = AutomationRule(
            id="complex_rule",
            enabled=True,
            trigger=EventTriggerConfig(
                event_type="occupancy.changed",
                payload_match={"occupied": True, "confidence": 0.8},
            ),
            conditions=[
                TimeOfDayCondition(after="06:00:00", before="22:00:00"),
                LuxLevelCondition(entity_id="sensor.lux", below=50.0),
            ],
            actions=[
                DelayAction(seconds=5),
                ServiceCallAction(
                    service="light.turn_on",
                    entity_id="light.test",
                    data={"brightness_pct": 80},
                ),
            ],
            mode=ExecutionMode.SINGLE,
        )

        data = original.to_dict()
        restored = AutomationRule.from_dict(data)

        assert restored.id == original.id
        assert restored.enabled == original.enabled
        assert restored.mode == original.mode
        assert len(restored.conditions) == len(original.conditions)
        assert len(restored.actions) == len(original.actions)


class TestTriggerConfigs:
    """Tests for trigger config types."""

    def test_event_trigger(self):
        """Test event trigger config."""
        trigger = EventTriggerConfig(
            event_type="occupancy.changed",
            payload_match={"occupied": True},
        )

        from home_topology.modules.automation import TriggerType

        assert trigger.trigger_type == TriggerType.EVENT

    def test_state_trigger(self):
        """Test state trigger config."""
        trigger = StateTriggerConfig(
            entity_id="binary_sensor.motion",
            to_state="on",
            from_state="off",
            for_seconds=5,
        )

        from home_topology.modules.automation import TriggerType

        assert trigger.trigger_type == TriggerType.STATE

    def test_time_trigger(self):
        """Test time trigger config."""
        trigger = TimeTriggerConfig(at=time(7, 0, 0))

        from home_topology.modules.automation import TriggerType

        assert trigger.trigger_type == TriggerType.TIME


class TestConditionConfigs:
    """Tests for condition config types."""

    def test_time_of_day_condition(self):
        """Test time of day condition."""
        condition = TimeOfDayCondition(after="08:00:00", before="18:00:00")

        from home_topology.modules.automation import ConditionType

        assert condition.condition_type == ConditionType.TIME_OF_DAY

    def test_lux_level_condition(self):
        """Test lux level condition."""
        condition = LuxLevelCondition(entity_id="sensor.lux", below=50.0)

        from home_topology.modules.automation import ConditionType

        assert condition.condition_type == ConditionType.LUX_LEVEL

    def test_day_of_week_condition(self):
        """Test day of week condition."""
        condition = DayOfWeekCondition(days=frozenset({"mon", "tue", "wed", "thu", "fri"}))

        from home_topology.modules.automation import ConditionType

        assert condition.condition_type == ConditionType.DAY_OF_WEEK


class TestLocationAutomationConfig:
    """Tests for location configuration."""

    def test_default_config(self):
        """Test default configuration."""
        config = LocationAutomationConfig()

        assert config.version == 1
        assert config.enabled is True
        assert config.trust_device_state is True
        assert config.rules == []

    def test_serialize_config(self):
        """Test serializing configuration."""
        rule = AutomationRule(
            id="test",
            enabled=True,
            trigger=EventTriggerConfig(event_type="test"),
            conditions=[],
            actions=[ServiceCallAction(service="test.test")],
        )
        config = LocationAutomationConfig(rules=[rule])

        data = config.to_dict()

        assert data["version"] == 1
        assert len(data["rules"]) == 1

    def test_deserialize_config(self):
        """Test deserializing configuration."""
        data = {
            "version": 1,
            "enabled": True,
            "trust_device_state": False,
            "rules": [
                {
                    "id": "test",
                    "enabled": True,
                    "trigger": {"type": "event", "event_type": "test"},
                    "actions": [{"type": "service_call", "service": "test.test"}],
                }
            ],
        }

        config = LocationAutomationConfig.from_dict(data)

        assert config.trust_device_state is False
        assert len(config.rules) == 1
