"""
Data models for the Ambient Light module.

Defines ambient light readings and related data structures.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class AmbientLightReading:
    """
    Ambient light reading for a location.
    
    Provides both raw lux value and convenience boolean flags
    for common use cases (is_dark, is_bright).
    """
    
    lux: Optional[float]                    # Light level in lux (None if unavailable)
    source_sensor: Optional[str]            # Entity ID of sensor that provided value
    source_location: Optional[str]          # Location that owns the sensor
    is_inherited: bool                      # True if from parent/ancestor
    is_dark: bool                           # Convenience: lux < dark_threshold
    is_bright: bool                         # Convenience: lux > bright_threshold
    dark_threshold: float = 50.0            # Lux below which is "dark"
    bright_threshold: float = 500.0         # Lux above which is "bright"
    fallback_method: Optional[str] = None   # How value was determined if no sensor
    timestamp: datetime = field(default_factory=lambda: datetime.now())
    
    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "lux": self.lux,
            "source_sensor": self.source_sensor,
            "source_location": self.source_location,
            "is_inherited": self.is_inherited,
            "is_dark": self.is_dark,
            "is_bright": self.is_bright,
            "dark_threshold": self.dark_threshold,
            "bright_threshold": self.bright_threshold,
            "fallback_method": self.fallback_method,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AmbientLightConfig:
    """Per-location configuration for ambient light."""
    
    version: int = 1
    lux_sensor: Optional[str] = None         # Explicit sensor entity ID
    auto_discover: bool = True               # Auto-detect lux sensors
    inherit_from_parent: bool = True         # Use parent sensor if no local
    dark_threshold: float = 50.0             # Lux below which is "dark"
    bright_threshold: float = 500.0          # Lux above which is "bright"
    fallback_to_sun: bool = True             # Use sun.sun if no sensors
    assume_dark_on_error: bool = True        # Assume dark if sensor unavailable
    
    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "version": self.version,
            "lux_sensor": self.lux_sensor,
            "auto_discover": self.auto_discover,
            "inherit_from_parent": self.inherit_from_parent,
            "dark_threshold": self.dark_threshold,
            "bright_threshold": self.bright_threshold,
            "fallback_to_sun": self.fallback_to_sun,
            "assume_dark_on_error": self.assume_dark_on_error,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AmbientLightConfig":
        """Deserialize from dict."""
        return cls(
            version=data.get("version", 1),
            lux_sensor=data.get("lux_sensor"),
            auto_discover=data.get("auto_discover", True),
            inherit_from_parent=data.get("inherit_from_parent", True),
            dark_threshold=data.get("dark_threshold", 50.0),
            bright_threshold=data.get("bright_threshold", 500.0),
            fallback_to_sun=data.get("fallback_to_sun", True),
            assume_dark_on_error=data.get("assume_dark_on_error", True),
        )

