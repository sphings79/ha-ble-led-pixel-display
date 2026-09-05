"""Panel geometry and capabilities per device type.

The panels report a device type byte in their device-info response, but that
byte does not map to a resolution directly. It maps to an internal "LED type",
and for a few device types the mapping additionally depends on the product id
the panel advertises -- the same resolution ships in more than one hardware
generation, with different buffer sizes.

pypixelcolor covers device types 128-147, which its tables inherited from
go-ipxl, which in turn reconstructed them from observed traffic. The vendor
app carries the full set: device types up to 159 and 36 LED types, plus the
per-type frame buffer size and default text size, which no reconstruction from
traffic could have revealed.

Source: com/wifiled/ipixels/ui/ChooseActivity.setLedType() and
AppConfig.ledSizeMap in iPixel Color 3.7.7 (com.wifiled.ipixels).
"""
from __future__ import annotations

import logging
from typing import NamedTuple

_LOGGER = logging.getLogger(__name__)

# LED type -> (width, height). Note that several resolutions appear twice:
# the device type, not the resolution, identifies the hardware.
LED_SIZE_MAP: dict[int, tuple[int, int]] = {
    0: (64, 64),    1: (96, 16),    2: (32, 32),    3: (64, 16),
    4: (32, 16),    5: (64, 20),    6: (128, 32),   7: (144, 16),
    8: (192, 16),   9: (48, 24),   10: (64, 32),   11: (96, 32),
    12: (128, 32), 13: (96, 32),   14: (160, 32),  15: (192, 32),
    16: (256, 32), 17: (320, 32),  18: (384, 32),  19: (448, 32),
    20: (16, 16),  21: (32, 32),   22: (32, 16),   23: (48, 24),
    24: (64, 64),  25: (96, 64),   26: (128, 64),  27: (160, 64),
    28: (192, 64), 29: (256, 64),  30: (320, 64),  31: (384, 64),
    32: (448, 64), 33: (512, 64),  34: (576, 64),  35: (640, 64),
}

# Device type -> LED type. Types 148-159 are absent from pypixelcolor.
DEVICE_TYPE_MAP: dict[int, int] = {
    0: 0, 128: 0, 129: 2, 130: 4, 131: 3, 132: 1, 133: 5, 134: 6,
    135: 7, 136: 8, 137: 9, 138: 10, 139: 11, 140: 12, 141: 13,
    142: 14, 143: 15, 144: 16, 145: 17, 146: 18, 147: 19, 148: 20,
    149: 24, 150: 25, 151: 26, 152: 27, 153: 28, 154: 29, 155: 30,
    156: 31, 157: 32, 158: 33, 159: 34,
}

# (device type, product id) -> LED type, overriding DEVICE_TYPE_MAP. Same
# resolution, different hardware generation and buffer size.
DEVICE_TYPE_PID_MAP: dict[tuple[int, str], int] = {
    (129, "55"): 21,
    (130, "56"): 22,
    (137, "57"): 23,
}

# Bytes the panel accepts per transfer window. go-ipxl assumes 1024
# throughout, the app defaults to 4096 and raises it for these types.
LED_FRAME_SIZE: dict[int, int] = {
    0: 12288, 2: 12288, 21: 12288,
}
DEFAULT_FRAME_SIZE = 4096

# Default text height the app uses per LED type.
LED_TEXT_SIZE: dict[int, int] = {
    6: 32, 9: 24, 23: 24, 10: 32, 11: 32, 12: 32, 13: 32, 14: 32,
    15: 32, 16: 32, 17: 32, 18: 32, 19: 32, 20: 16,
    24: 64, 25: 64, 26: 64, 27: 64, 28: 64, 29: 64, 30: 64, 31: 64,
    32: 64, 33: 64, 34: 64, 35: 64,
}

# Only these are stated outright in the app; anything else is unknown rather
# than absent, so callers get None instead of a guess.
LED_HAS_WIFI: dict[int, bool] = {0: True, 6: False}


class PanelSpec(NamedTuple):
    """What is known about a panel, derived from its device type."""

    led_type: int | None
    width: int | None
    height: int | None
    frame_size: int
    text_size: int | None
    has_wifi: bool | None


def resolve_panel(device_type: int | None, pid: str | None = None) -> PanelSpec:
    """Resolve a reported device type to panel geometry and capabilities.

    Args:
        device_type: The device type byte from the device-info response.
        pid: Product id, where known. Distinguishes hardware generations that
            share a resolution.

    Returns:
        A PanelSpec. Unknown fields are None rather than a guess, so callers
        can fall back to whatever the device itself reported.
    """
    if device_type is None:
        return PanelSpec(None, None, None, DEFAULT_FRAME_SIZE, None, None)

    led_type = None
    if pid is not None:
        led_type = DEVICE_TYPE_PID_MAP.get((device_type, str(pid)))
    if led_type is None:
        led_type = DEVICE_TYPE_MAP.get(device_type)

    if led_type is None:
        _LOGGER.warning(
            "Unknown device type %s. Falling back to the dimensions the panel "
            "reports. Please open an issue with this number and your panel's "
            "model name.", device_type
        )
        return PanelSpec(None, None, None, DEFAULT_FRAME_SIZE, None, None)

    width, height = LED_SIZE_MAP.get(led_type, (None, None))
    return PanelSpec(
        led_type=led_type,
        width=width,
        height=height,
        frame_size=LED_FRAME_SIZE.get(led_type, DEFAULT_FRAME_SIZE),
        text_size=LED_TEXT_SIZE.get(led_type),
        has_wifi=LED_HAS_WIFI.get(led_type),
    )
