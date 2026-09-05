"""Custom exceptions for BLE LED Pixel Display integration."""
from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError


class BleLedPixelError(HomeAssistantError):
    """Base LED panel error."""


class BleLedPixelConnectionError(BleLedPixelError):
    """LED panel connection error."""


class BleLedPixelTimeoutError(BleLedPixelError):
    """LED panel timeout error."""