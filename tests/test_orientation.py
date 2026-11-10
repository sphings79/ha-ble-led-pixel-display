"""Orientation: the 0x8006 frame, and which rotations a panel shape offers."""
import asyncio
from types import SimpleNamespace

import pytest

from tests import ha_stubs

ha_stubs.install()

from custom_components.ble_led_pixel import api as api_module  # noqa: E402
from custom_components.ble_led_pixel.device.commands import (  # noqa: E402
    make_orientation_command,
)


@pytest.mark.parametrize(
    ("degrees", "frame"),
    [(0, "05 00 06 80 00"), (90, "05 00 06 80 01"), (180, "05 00 06 80 02"), (270, "05 00 06 80 03")],
)
def test_frames_match_the_vendor_app(degrees, frame):
    assert make_orientation_command(degrees).hex(" ") == frame


@pytest.mark.parametrize("bad", [45, 360, -90, 1])
def test_other_angles_are_refused(bad):
    with pytest.raises(ValueError):
        make_orientation_command(bad)


class FakeApi:
    orientations = api_module.BleLedPixelAPI.orientations
    set_orientation = api_module.BleLedPixelAPI.set_orientation
    _known_dimensions = api_module.BleLedPixelAPI._known_dimensions
    _resolved_dimensions = api_module.BleLedPixelAPI._resolved_dimensions

    def __init__(self, info):
        self._entry = SimpleNamespace(options={})
        self._device_info = info
        self.sent = []

    async def _send_with_reconnect(self, command, **_):
        self.sent.append(command.hex(" "))
        return True


def test_square_panels_offer_all_four():
    assert FakeApi({"width": 32, "height": 32}).orientations == [0, 90, 180, 270]


@pytest.mark.parametrize("info", [{"width": 64, "height": 16}, {"width": 64, "height": 20}, None])
def test_other_panels_only_turn_upside_down(info):
    assert FakeApi(info).orientations == [0, 180]


def test_set_orientation_sends_the_frame():
    api = FakeApi({"width": 32, "height": 32})
    assert asyncio.run(api.set_orientation(270))
    assert api.sent == ["05 00 06 80 03"]


def test_set_orientation_refuses_nonsense():
    api = FakeApi({"width": 32, "height": 32})
    assert not asyncio.run(api.set_orientation(45))
    assert api.sent == []
