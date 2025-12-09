"""
Ambient Light Module for home-topology.

Provides intelligent ambient light detection with automatic sensor
inheritance through the location hierarchy.
"""

from .models import AmbientLightReading, AmbientLightConfig
from .module import AmbientLightModule

__all__ = [
    "AmbientLightReading",
    "AmbientLightConfig",
    "AmbientLightModule",
]

