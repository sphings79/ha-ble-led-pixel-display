"""Device registration shared by every entity of a panel."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

if TYPE_CHECKING:
    from .api import BleLedPixelAPI


def panel_device_info(api: "BleLedPixelAPI", address: str, name: str) -> DeviceInfo:
    """Build the device registration for a panel.

    The manufacturer is only named when the advertised product id maps to a
    brand we actually know. For everything else a neutral value is used rather
    than a guess - but a value nonetheless: Home Assistant keeps the previous
    registry entry when a field is omitted, so leaving it out would preserve
    whatever was written there before.

    The raw product id stays visible through the cidpid diagnostic sensor, so
    an unrecognised panel can still be identified and reported.
    """
    brand: str | None = None
    try:
        brand = api.identity.brand
    except Exception:  # noqa: BLE001 - registration must never break setup
        pass

    return DeviceInfo(
        identifiers={(DOMAIN, address)},
        name=name,
        manufacturer=brand or "LED_BLE",
        model="LED Pixel Panel",
        sw_version="1.0",
    )
