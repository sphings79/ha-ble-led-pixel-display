"""Bluetooth device discovery for BLE LED pixel panels."""
from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from homeassistant.components import bluetooth

from ..advertisement import parse_identity
from ..const import DEVICE_NAME_MARKER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def discover_panels(hass: HomeAssistant, return_all: bool = False) -> list[dict[str, Any]]:
    """Discover LED panels using Home Assistant's Bluetooth integration.

    Args:
        hass: Home Assistant instance
        return_all: If True, return all devices with compatibility indication

    Returns:
        List of discovered device information with is_compatible flag
    """
    _LOGGER.debug("Starting LED panel discovery using HA bluetooth API, return_all=%s", return_all)
    devices = []

    try:
        # Use Home Assistant's bluetooth API to get discovered devices
        service_infos = bluetooth.async_discovered_service_info(hass, connectable=True)

        _LOGGER.debug("HA bluetooth API returned %d service infos", len(service_infos))

        for service_info in service_infos:
            device_name = service_info.name or f"Unknown_{service_info.address[-4:]}"
            _LOGGER.debug("Checking device: %s (%s)", device_name, service_info.address)

            # Two ways to recognise a panel, both taken from the vendor app.
            # The name check is a substring, not a prefix: the app accepts
            # LED_BLE anywhere in the name. And a panel that does not carry
            # the name at all still counts when its advertisement holds the
            # vendor's manufacturer data -- that is the app's fallback path,
            # and without it a rebranded panel is invisible to us while the
            # app finds it.
            name = service_info.name or ""
            is_compatible = DEVICE_NAME_MARKER in name
            if not is_compatible:
                is_compatible = parse_identity(service_info.manufacturer_data).cid is not None

            device_info = {
                "address": service_info.address,
                "name": device_name,
                "rssi": service_info.rssi,
                "is_compatible": is_compatible,
            }

            # Include device if it's compatible OR if we want all devices
            if is_compatible or return_all:
                devices.append(device_info)
                if is_compatible:
                    _LOGGER.info("Found compatible LED panel: %s", device_info)
                else:
                    _LOGGER.debug("Found other device: %s", device_info)

        _LOGGER.debug("Discovery completed, found %d total devices (%d compatible)",
                     len(devices), sum(1 for d in devices if d.get('is_compatible', False)))
        return devices

    except Exception as err:
        _LOGGER.error("Discovery failed: %s", err)
        import traceback
        _LOGGER.error("Traceback: %s", traceback.format_exc())
        return []