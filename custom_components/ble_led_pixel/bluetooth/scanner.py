"""Bluetooth device discovery for iPIXEL Color devices."""
from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from homeassistant.components import bluetooth

from ..const import DEVICE_NAME_PREFIX

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def discover_ipixel_devices_ha(hass: HomeAssistant, return_all: bool = False) -> list[dict[str, Any]]:
    """Discover iPIXEL devices using Home Assistant's Bluetooth integration.

    Args:
        hass: Home Assistant instance
        return_all: If True, return all devices with compatibility indication

    Returns:
        List of discovered device information with is_compatible flag
    """
    _LOGGER.debug("Starting iPIXEL device discovery using HA bluetooth API, return_all=%s", return_all)
    devices = []

    try:
        # Use Home Assistant's bluetooth API to get discovered devices
        service_infos = bluetooth.async_discovered_service_info(hass, connectable=True)

        _LOGGER.debug("HA bluetooth API returned %d service infos", len(service_infos))

        for service_info in service_infos:
            device_name = service_info.name or f"Unknown_{service_info.address[-4:]}"
            _LOGGER.debug("Checking device: %s (%s)", device_name, service_info.address)

            # Check if device is compatible (starts with our prefix)
            is_compatible = bool(service_info.name and service_info.name.startswith(DEVICE_NAME_PREFIX))

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
                    _LOGGER.info("Found compatible iPIXEL device: %s", device_info)
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