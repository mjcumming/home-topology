"""
AutomationModule implementation.

Triggers automations based on location events and state changes.
"""

import logging
from datetime import datetime, UTC
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from home_topology.modules.base import LocationModule
from home_topology.core.bus import Event, EventBus, EventFilter
from home_topology.core.manager import LocationManager

from .engine import AutomationEngine
from .models import AutomationRule, LocationAutomationConfig

if TYPE_CHECKING:
    from .adapter import PlatformAdapter
    from home_topology.modules.occupancy import OccupancyModule

logger = logging.getLogger(__name__)


class AutomationModule(LocationModule):
    """
    Module that handles automation rule execution.

    Responds to semantic events (like occupancy changes) and triggers
    platform-specific actions via a platform adapter.

    Features:
    - Rule-based automation (trigger → condition → action)
    - Time-of-day and lux-level conditions
    - Device state checking (avoid redundant commands)
    - Execution history for debugging
    - Pre-built presets for common patterns
    """

    def __init__(self, platform: Optional["PlatformAdapter"] = None) -> None:
        """
        Initialize the automation module.

        Args:
            platform: Platform adapter for service calls and state queries.
                     Required for action execution. Can be set later via
                     set_platform().
        """
        self._bus: Optional[EventBus] = None
        self._loc_manager: Optional[LocationManager] = None
        self._platform: Optional["PlatformAdapter"] = platform
        self._occupancy: Optional["OccupancyModule"] = None
        self._engine: Optional[AutomationEngine] = None

    @property
    def id(self) -> str:
        return "automation"

    @property
    def CURRENT_CONFIG_VERSION(self) -> int:
        return 1

    def set_platform(self, platform: "PlatformAdapter") -> None:
        """
        Set the platform adapter.

        Must be called before attach() if not provided in constructor.
        """
        self._platform = platform
        if self._engine:
            # Reinitialize engine with new platform
            self._engine = AutomationEngine(platform, self._occupancy)
            self._reload_all_rules()

    def set_occupancy_module(self, occupancy: "OccupancyModule") -> None:
        """
        Set the occupancy module for location state checks.

        Optional, but required for LocationOccupiedCondition to work.
        """
        self._occupancy = occupancy
        if self._engine:
            self._engine = AutomationEngine(self._platform, occupancy)
            self._reload_all_rules()

    def attach(self, bus: EventBus, loc_manager: LocationManager) -> None:
        """
        Attach the automation module to the kernel.

        Subscribes to semantic events and initializes the engine.
        """
        logger.info("Attaching AutomationModule")
        self._bus = bus
        self._loc_manager = loc_manager

        if not self._platform:
            logger.warning(
                "AutomationModule attached without platform adapter. "
                "Actions will not execute until set_platform() is called."
            )
            return

        # Initialize engine
        self._engine = AutomationEngine(self._platform, self._occupancy)

        # Load rules from all locations
        self._reload_all_rules()

        # Subscribe to occupancy events
        bus.subscribe(
            self._on_occupancy_changed,
            EventFilter(event_type="occupancy.changed"),
        )

        logger.info("AutomationModule ready")

    def _reload_all_rules(self) -> None:
        """Reload rules from all locations."""
        if not self._loc_manager or not self._engine:
            return

        for location in self._loc_manager.all_locations():
            self._load_location_rules(location.id)

    def _load_location_rules(self, location_id: str) -> None:
        """Load rules for a specific location."""
        if not self._loc_manager or not self._engine:
            return

        config_dict = self._loc_manager.get_module_config(location_id, self.id)
        if not config_dict:
            return

        # Skip disabled locations
        if not config_dict.get("enabled", True):
            logger.debug(f"Skipping disabled location: {location_id}")
            return

        # Parse configuration
        config = LocationAutomationConfig.from_dict(config_dict)

        # Set rules in engine
        self._engine.set_location_rules(
            location_id,
            config.rules,
            trust_device_state=config.trust_device_state,
        )
        logger.debug(f"Loaded {len(config.rules)} rules for {location_id}")

    def _on_occupancy_changed(self, event: Event) -> None:
        """Handle occupancy change events."""
        if not self._engine:
            logger.debug("No engine, skipping event")
            return

        result = self._engine.process_event(event)

        if result.rules_triggered > 0:
            logger.info(
                f"Processed event for {event.location_id}: "
                f"{result.rules_triggered}/{result.rules_evaluated} rules triggered, "
                f"{result.actions_executed} actions executed"
            )

        # Emit automation.executed events for observability
        if result.actions_executed > 0:
            self._emit_automation_executed(event, result)

    def _emit_automation_executed(self, trigger_event: Event, result: Any) -> None:
        """Emit automation.executed event for observability."""
        if not self._bus:
            return

        self._bus.publish(
            Event(
                type="automation.executed",
                source="automation",
                location_id=trigger_event.location_id,
                payload={
                    "trigger_event": trigger_event.type,
                    "rules_evaluated": result.rules_evaluated,
                    "rules_triggered": result.rules_triggered,
                    "actions_executed": result.actions_executed,
                    "errors": result.errors,
                },
                timestamp=datetime.now(UTC),
            )
        )

    # =========================================================================
    # Public API
    # =========================================================================

    def add_rule(self, location_id: str, rule: AutomationRule) -> None:
        """
        Add a rule to a location.

        Args:
            location_id: Location to add rule to
            rule: The automation rule to add
        """
        if not self._engine:
            raise RuntimeError("Engine not initialized")

        rules = self._engine.get_location_rules(location_id)
        # Remove existing rule with same ID
        rules = [r for r in rules if r.id != rule.id]
        rules.append(rule)
        self._engine.set_location_rules(location_id, rules)
        logger.info(f"Added rule {rule.id} to {location_id}")

    def remove_rule(self, location_id: str, rule_id: str) -> bool:
        """
        Remove a rule from a location.

        Args:
            location_id: Location to remove rule from
            rule_id: ID of rule to remove

        Returns:
            True if rule was removed, False if not found
        """
        if not self._engine:
            raise RuntimeError("Engine not initialized")

        rules = self._engine.get_location_rules(location_id)
        new_rules = [r for r in rules if r.id != rule_id]

        if len(new_rules) == len(rules):
            return False

        self._engine.set_location_rules(location_id, new_rules)
        logger.info(f"Removed rule {rule_id} from {location_id}")
        return True

    def get_rules(self, location_id: str) -> List[AutomationRule]:
        """Get all rules for a location."""
        if not self._engine:
            return []
        return self._engine.get_location_rules(location_id)

    def get_history(
        self,
        location_id: Optional[str] = None,
        rule_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict]:
        """
        Get automation execution history.

        Args:
            location_id: Filter by location (optional)
            rule_id: Filter by rule (optional)
            limit: Maximum entries to return

        Returns:
            List of execution records
        """
        if not self._engine:
            return []

        history = self._engine.get_history(location_id, rule_id, limit)
        return [
            {
                "rule_id": h.rule_id,
                "location_id": h.location_id,
                "trigger_event_type": h.trigger_event_type,
                "conditions_met": h.conditions_met,
                "actions_executed": h.actions_executed,
                "success": h.success,
                "error": h.error,
                "timestamp": h.timestamp.isoformat(),
                "duration_ms": h.duration_ms,
            }
            for h in history
        ]

    # =========================================================================
    # LocationModule Interface
    # =========================================================================

    def default_config(self) -> Dict:
        """Get default automation configuration."""
        return {
            "version": self.CURRENT_CONFIG_VERSION,
            "enabled": True,
            "trust_device_state": True,
            "rules": [],
        }

    def location_config_schema(self) -> Dict:
        """
        Get configuration schema for automation module.

        Returns a JSON-schema-like structure for UI rendering.
        """
        return {
            "type": "object",
            "properties": {
                "version": {
                    "type": "integer",
                    "title": "Config Version",
                    "readOnly": True,
                },
                "enabled": {
                    "type": "boolean",
                    "title": "Enable Automation",
                    "description": "Enable automation rules for this location",
                    "default": True,
                },
                "trust_device_state": {
                    "type": "boolean",
                    "title": "Trust Device State",
                    "description": "Check device state before sending commands (avoids redundant calls)",
                    "default": True,
                },
                "rules": {
                    "type": "array",
                    "title": "Automation Rules",
                    "description": "Automation rules for this location",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "title": "Rule ID",
                            },
                            "enabled": {
                                "type": "boolean",
                                "title": "Enabled",
                                "default": True,
                            },
                            "trigger": {
                                "type": "object",
                                "title": "Trigger",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["event", "state", "time"],
                                    },
                                    "event_type": {"type": "string"},
                                    "payload_match": {"type": "object"},
                                },
                            },
                            "conditions": {
                                "type": "array",
                                "title": "Conditions",
                                "items": {"type": "object"},
                            },
                            "actions": {
                                "type": "array",
                                "title": "Actions",
                                "items": {"type": "object"},
                            },
                            "mode": {
                                "type": "string",
                                "title": "Execution Mode",
                                "enum": ["single", "restart", "parallel"],
                                "default": "restart",
                            },
                        },
                        "required": ["id", "trigger", "actions"],
                    },
                },
            },
            "required": ["version", "enabled"],
        }

    def on_location_config_changed(self, location_id: str, config: Dict) -> None:
        """React to configuration changes for a location."""
        self._load_location_rules(location_id)

    def dump_state(self) -> Dict:
        """Export module state for persistence."""
        if not self._engine:
            return {}
        return self._engine.export_state()

    def restore_state(self, state: Dict) -> None:
        """Restore module state from persistence."""
        if not self._engine:
            logger.warning("Cannot restore state: engine not initialized")
            return
        self._engine.restore_state(state)
        logger.info("Restored automation module state")


# Backwards compatibility alias
ActionsModule = AutomationModule
