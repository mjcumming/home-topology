"""
Automation engine - core rule processing logic.

Handles trigger matching, condition evaluation, and action execution.
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import TYPE_CHECKING, Any, Deque, Dict, List, Optional

from home_topology.core.bus import Event

from .models import (
    AutomationRule,
    RuleExecution,
    EventTriggerConfig,
    ServiceCallAction,
    DelayAction,
    ExecutionMode,
)
from .evaluators import ConditionEvaluator

if TYPE_CHECKING:
    from .adapter import PlatformAdapter
    from home_topology.modules.occupancy import OccupancyModule

logger = logging.getLogger(__name__)


@dataclass
class RuleExecutionState:
    """Tracks the execution state of a rule."""

    rule_id: str
    location_id: str
    is_running: bool = False
    started_at: Optional[datetime] = None
    pending_delay: Optional[float] = None  # Remaining delay in seconds


@dataclass
class EngineResult:
    """Result of processing an event or executing actions."""

    rules_evaluated: int = 0
    rules_triggered: int = 0
    actions_executed: int = 0
    errors: List[str] = field(default_factory=list)


# Backwards compatibility alias
ActionEngineResult = EngineResult


class AutomationEngine:
    """
    Core engine for automation rule processing.

    Responsibilities:
    - Match incoming events to rule triggers
    - Evaluate conditions
    - Execute actions via platform adapter
    - Track execution history
    - Handle execution modes (single, restart, parallel)
    """

    HISTORY_SIZE = 100  # Number of executions to keep in history

    def __init__(
        self,
        platform: "PlatformAdapter",
        occupancy_module: Optional["OccupancyModule"] = None,
    ) -> None:
        self._platform = platform
        self._occupancy = occupancy_module
        self._evaluator = ConditionEvaluator(platform, occupancy_module)

        # Rules by location
        self._rules: Dict[str, List[AutomationRule]] = {}

        # Execution state per rule (key: location_id:rule_id)
        self._execution_state: Dict[str, RuleExecutionState] = {}

        # Execution history (ring buffer)
        self._history: Deque[RuleExecution] = deque(maxlen=self.HISTORY_SIZE)

        # Trust device state (per-location setting, default True)
        self._trust_state: Dict[str, bool] = {}

    # =========================================================================
    # Configuration
    # =========================================================================

    def set_location_rules(
        self,
        location_id: str,
        rules: List[AutomationRule],
        trust_device_state: bool = True,
    ) -> None:
        """
        Set rules for a location.

        Args:
            location_id: Location ID
            rules: List of automation rules
            trust_device_state: Whether to check state before commands
        """
        self._rules[location_id] = rules
        self._trust_state[location_id] = trust_device_state
        logger.debug(f"Set {len(rules)} rules for location {location_id}")

    def get_location_rules(self, location_id: str) -> List[AutomationRule]:
        """Get rules for a location."""
        return self._rules.get(location_id, [])

    def clear_location_rules(self, location_id: str) -> None:
        """Clear all rules for a location."""
        self._rules.pop(location_id, None)
        self._trust_state.pop(location_id, None)

    # =========================================================================
    # Event Processing
    # =========================================================================

    def process_event(
        self,
        event: Event,
        now: Optional[datetime] = None,
    ) -> EngineResult:
        """
        Process an incoming event and trigger matching rules.

        Args:
            event: The event to process
            now: Current time (for testing)

        Returns:
            Result with counts of rules evaluated/triggered
        """
        if now is None:
            now = datetime.now(UTC)

        result = EngineResult()

        # Get rules for this location
        location_id = event.location_id
        if not location_id:
            return result

        rules = self._rules.get(location_id, [])
        if not rules:
            return result

        # Evaluate each rule
        for rule in rules:
            result.rules_evaluated += 1

            if not rule.enabled:
                continue

            # Check if trigger matches
            if not self._trigger_matches(rule, event):
                continue

            # Check conditions
            if not self._evaluator.evaluate_all(rule.conditions):
                self._record_execution(
                    rule_id=rule.id,
                    location_id=location_id,
                    trigger_event_type=event.type,
                    conditions_met=False,
                    actions_executed=[],
                    success=True,
                    error=None,
                    timestamp=now,
                    duration_ms=0,
                )
                continue

            # Handle execution mode
            state_key = f"{location_id}:{rule.id}"
            state = self._execution_state.get(state_key)

            if state and state.is_running:
                if rule.mode == ExecutionMode.SINGLE:
                    logger.debug(f"Rule {rule.id} already running, skipping (single mode)")
                    continue
                elif rule.mode == ExecutionMode.RESTART:
                    logger.debug(f"Rule {rule.id} restarting, cancelling previous")
                    self._cancel_execution(state_key)

            # Execute actions
            result.rules_triggered += 1
            exec_result = self._execute_rule(rule, location_id, event.type, now)
            result.actions_executed += exec_result

        return result

    # =========================================================================
    # Trigger Matching
    # =========================================================================

    def _trigger_matches(self, rule: AutomationRule, event: Event) -> bool:
        """Check if an event matches a rule's trigger."""
        trigger = rule.trigger

        if isinstance(trigger, EventTriggerConfig):
            # Check event type
            if event.type != trigger.event_type:
                return False

            # Check payload match
            for key, expected in trigger.payload_match.items():
                actual = event.payload.get(key)

                # Handle threshold matching (e.g., {"min": 0.7})
                if isinstance(expected, dict):
                    if "min" in expected and actual < expected["min"]:
                        return False
                    if "max" in expected and actual > expected["max"]:
                        return False
                elif actual != expected:
                    return False

            return True

        # Other trigger types (state, time) handled elsewhere
        return False

    # =========================================================================
    # Action Execution
    # =========================================================================

    def _execute_rule(
        self,
        rule: AutomationRule,
        location_id: str,
        trigger_event_type: str,
        now: datetime,
    ) -> int:
        """
        Execute a rule's actions.

        Returns:
            Number of actions executed
        """
        start_time = now
        actions_executed = []
        success = True
        error = None

        # Mark as running
        state_key = f"{location_id}:{rule.id}"
        self._execution_state[state_key] = RuleExecutionState(
            rule_id=rule.id,
            location_id=location_id,
            is_running=True,
            started_at=now,
        )

        try:
            for action in rule.actions:
                if isinstance(action, ServiceCallAction):
                    self._execute_service_call(action, location_id)
                    actions_executed.append(
                        {"service": action.service, "entity_id": action.entity_id}
                    )

                elif isinstance(action, DelayAction):
                    # Note: In a real implementation, delays would be handled
                    # asynchronously by the host platform. For now, we just
                    # record them. The HA integration will handle scheduling.
                    actions_executed.append({"delay": action.seconds})
                    logger.debug(f"Delay action: {action.seconds}s (host must schedule)")

        except Exception as e:
            success = False
            error = str(e)
            logger.error(f"Error executing rule {rule.id}: {e}", exc_info=True)

        finally:
            # Mark as not running (unless there's a pending delay)
            state = self._execution_state.get(state_key)
            if state and not state.pending_delay:
                state.is_running = False

        # Calculate duration
        end_time = datetime.now(UTC)
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        # Record execution
        self._record_execution(
            rule_id=rule.id,
            location_id=location_id,
            trigger_event_type=trigger_event_type,
            conditions_met=True,
            actions_executed=actions_executed,
            success=success,
            error=error,
            timestamp=start_time,
            duration_ms=duration_ms,
        )

        return len(actions_executed)

    def _execute_service_call(
        self,
        action: ServiceCallAction,
        location_id: str,
    ) -> bool:
        """
        Execute a service call action.

        Args:
            action: The service call action
            location_id: Location context

        Returns:
            True if successful
        """
        # Parse service (e.g., "light.turn_on" -> domain="light", service="turn_on")
        parts = action.service.split(".", 1)
        if len(parts) != 2:
            logger.error(f"Invalid service format: {action.service}")
            return False

        domain, service = parts

        # Check state before sending (if trust_device_state is True)
        trust_state = self._trust_state.get(location_id, True)
        if trust_state and action.entity_id:
            if self._should_skip_action(action):
                logger.debug(
                    f"Skipping {action.service} for {action.entity_id} (already in desired state)"
                )
                return True

        # Execute service call
        logger.info(f"Executing: {action.service} -> {action.entity_id}")
        return self._platform.call_service(
            domain=domain,
            service=service,
            entity_id=action.entity_id,
            data=dict(action.data) if action.data else None,
        )

    def _should_skip_action(self, action: ServiceCallAction) -> bool:
        """Check if action should be skipped (entity already in desired state)."""
        if not action.entity_id:
            return False

        current_state = self._platform.get_state(action.entity_id)
        if current_state is None:
            return False

        # Common patterns
        if action.service.endswith(".turn_on") and current_state == "on":
            return True
        if action.service.endswith(".turn_off") and current_state == "off":
            return True

        return False

    def _cancel_execution(self, state_key: str) -> None:
        """Cancel a running rule execution."""
        state = self._execution_state.get(state_key)
        if state:
            state.is_running = False
            state.pending_delay = None
            logger.debug(f"Cancelled execution: {state_key}")

    # =========================================================================
    # History
    # =========================================================================

    def _record_execution(
        self,
        rule_id: str,
        location_id: str,
        trigger_event_type: str,
        conditions_met: bool,
        actions_executed: List[Dict[str, Any]],
        success: bool,
        error: Optional[str],
        timestamp: datetime,
        duration_ms: int,
    ) -> None:
        """Record an execution in history."""
        execution = RuleExecution(
            rule_id=rule_id,
            location_id=location_id,
            trigger_event_type=trigger_event_type,
            conditions_met=conditions_met,
            actions_executed=actions_executed,
            success=success,
            error=error,
            timestamp=timestamp,
            duration_ms=duration_ms,
        )
        self._history.append(execution)

    def get_history(
        self,
        location_id: Optional[str] = None,
        rule_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[RuleExecution]:
        """
        Get execution history.

        Args:
            location_id: Filter by location (optional)
            rule_id: Filter by rule (optional)
            limit: Maximum entries to return

        Returns:
            List of RuleExecution records (newest first)
        """
        result = []
        for execution in reversed(self._history):
            if location_id and execution.location_id != location_id:
                continue
            if rule_id and execution.rule_id != rule_id:
                continue
            result.append(execution)
            if len(result) >= limit:
                break
        return result

    # =========================================================================
    # State Export/Import
    # =========================================================================

    def export_state(self) -> Dict[str, Any]:
        """Export engine state for persistence."""
        return {
            "version": 1,
            "execution_states": {
                key: {
                    "rule_id": state.rule_id,
                    "location_id": state.location_id,
                    "is_running": state.is_running,
                    "started_at": state.started_at.isoformat() if state.started_at else None,
                }
                for key, state in self._execution_state.items()
            },
            "history": [
                {
                    "rule_id": e.rule_id,
                    "location_id": e.location_id,
                    "trigger_event_type": e.trigger_event_type,
                    "conditions_met": e.conditions_met,
                    "actions_executed": e.actions_executed,
                    "success": e.success,
                    "error": e.error,
                    "timestamp": e.timestamp.isoformat(),
                    "duration_ms": e.duration_ms,
                }
                for e in self._history
            ],
        }

    def restore_state(self, state: Dict[str, Any]) -> None:
        """Restore engine state from persistence."""
        if state.get("version") != 1:
            logger.warning("Unknown state version, skipping restore")
            return

        # Clear running states on restore (don't continue interrupted executions)
        self._execution_state.clear()

        # Restore history
        self._history.clear()
        for entry in state.get("history", []):
            self._history.append(
                RuleExecution(
                    rule_id=entry["rule_id"],
                    location_id=entry["location_id"],
                    trigger_event_type=entry["trigger_event_type"],
                    conditions_met=entry["conditions_met"],
                    actions_executed=entry["actions_executed"],
                    success=entry["success"],
                    error=entry.get("error"),
                    timestamp=datetime.fromisoformat(entry["timestamp"]),
                    duration_ms=entry["duration_ms"],
                )
            )


# Backwards compatibility alias
ActionsEngine = AutomationEngine
