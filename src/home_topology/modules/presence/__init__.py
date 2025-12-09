"""
Presence module for home-topology.

Tracks WHO is in each location (not just that someone is there).

Features:
- Person registry (separate from Location topology)
- Device tracker management (add/remove dynamically)
- Current location tracking per person
- Presence change events
- Platform-agnostic core (HA integration uses HA Person entities)

Events Emitted:
- presence.changed: When a person enters/leaves a location

Use Cases:
- Person-specific automations ("Mike's scene when he enters office")
- Multi-person scenarios ("Movie mode when both in living room")
- Voice queries ("Where is Mike?")
- Notifications ("Sarah just arrived home")
"""

from .module import PresenceModule
from .models import Person, PresenceChange

__all__ = [
    "PresenceModule",
    "Person",
    "PresenceChange",
]
