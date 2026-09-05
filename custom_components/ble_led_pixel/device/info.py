"""Device information management for BLE LED pixel panels."""
from __future__ import annotations

import logging
from typing import Any

try:
    from pypixelcolor.lib.internal_commands import build_get_device_info_command
    from pypixelcolor.lib.device_info import parse_device_info as pypixelcolor_parse_device_info
except ImportError:
    build_get_device_info_command = None
    pypixelcolor_parse_device_info = None

from ..device_types import resolve_panel

_LOGGER = logging.getLogger(__name__)


def build_device_info_command() -> bytes:
    """Build device info query command using pypixelcolor.

    Returns:
        Command bytes to query device information.

    Raises:
        ImportError: If pypixelcolor is not available.
    """
    if build_get_device_info_command is None:
        raise ImportError("pypixelcolor library is not installed")

    return build_get_device_info_command()


def parse_device_response(response: bytes, pid: str | None = None) -> dict[str, Any]:
    """Parse device info response using pypixelcolor.

    Args:
        response: Raw bytes received from the device.

    Returns:
        Device information as a dict for Home Assistant compatibility.

    Raises:
        ImportError: If pypixelcolor is not available.
        ValueError: If response is invalid.
    """
    if pypixelcolor_parse_device_info is None:
        raise ImportError("pypixelcolor library is not installed")

    _LOGGER.debug("Device response: %s", response.hex())
    _LOGGER.info("Raw device response bytes: %s", [hex(b) for b in response])

    # Use pypixelcolor's parser to get DeviceInfo object
    device_info_obj = pypixelcolor_parse_device_info(response)

    # Convert DeviceInfo object to dict for Home Assistant compatibility
    device_info = {
        "width": device_info_obj.width,
        "height": device_info_obj.height,
        "device_type": device_info_obj.device_type,  # int
        "device_type_str": f"Type {device_info_obj.device_type}",  # String version for display
        "led_type": device_info_obj.led_type,
        "mcu_version": device_info_obj.mcu_version,
        "wifi_version": device_info_obj.wifi_version,
        "has_wifi": device_info_obj.has_wifi,
        "password_flag": device_info_obj.password_flag,
    }

    # Cross-check against the vendor app's own table. pypixelcolor only knows
    # device types 128-147 and assumes a single frame size, so anything newer
    # comes back without dimensions. Where the table knows better, it wins.
    spec = resolve_panel(device_info_obj.device_type, pid)
    if spec.width and spec.height:
        if (device_info["width"], device_info["height"]) != (spec.width, spec.height):
            _LOGGER.info(
                "Panel reports %dx%d but device type %s resolves to %dx%d; "
                "using the resolved size",
                device_info["width"], device_info["height"],
                device_info["device_type"], spec.width, spec.height,
            )
        device_info["width"] = spec.width
        device_info["height"] = spec.height
    if spec.led_type is not None:
        device_info["led_type"] = spec.led_type
    device_info["frame_size"] = spec.frame_size
    device_info["text_size"] = spec.text_size
    if spec.has_wifi is not None:
        device_info["has_wifi"] = spec.has_wifi

    _LOGGER.info("Parsed device info: %dx%d (Type %d, LED Type %s, frame %d)",
                 device_info["width"], device_info["height"],
                 device_info["device_type"], device_info["led_type"],
                 device_info["frame_size"])

    return device_info