"""Custom exceptions for BLE LED Pixel Display integration."""
from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError


class BleLedPixelError(HomeAssistantError):
    """Base LED panel error."""


class BleLedPixelConnectionError(BleLedPixelError):
    """LED panel connection error."""


class BleLedPixelTimeoutError(BleLedPixelError):
    """LED panel timeout error."""

class BleLedPixelFeatureUnsupported(BleLedPixelError):
    """The panel does not implement the requested feature.

    Raised rather than sending the command anyway: these panels acknowledge
    nothing and report nothing, so an unsupported command is indistinguishable
    from a working one until someone looks at the panel.
    """
