"""Device-info and firmware replies."""
from custom_components.ble_led_pixel.device import info


def test_firmware_reply():
    reply = bytes([8, 0, 5, 0x80, 4, 6, 1, 2])
    assert info.parse_firmware_response(reply) == {
        "mcu_version": "4.06",
        "mcu_build": "406",
        "wifi_version": "1.02",
    }


def test_firmware_reply_rejects_other_frames():
    assert info.parse_firmware_response(bytes([8, 0, 5, 0x80, 4, 6, 1])) is None
    assert info.parse_firmware_response(bytes([8, 0, 6, 0x80, 4, 6, 1, 2])) is None


def test_firmware_query_frame():
    assert info.build_firmware_command() == bytes([4, 0, 5, 0x80])


def test_device_info_query_comes_from_pypixelcolor():
    command = info.build_device_info_command()
    assert isinstance(command, (bytes, bytearray)) and command


def test_override_only_info_needs_both_dimensions():
    from types import SimpleNamespace

    from tests import ha_stubs

    ha_stubs.install()
    from custom_components.ble_led_pixel import api as api_module
    from custom_components.ble_led_pixel.const import (
        OPT_OVERRIDE_DIMENSIONS,
        OPT_PANEL_HEIGHT,
        OPT_PANEL_WIDTH,
    )

    class FakeApi:
        _override_only_info = api_module.BleLedPixelAPI._override_only_info
        _known_dimensions = api_module.BleLedPixelAPI._known_dimensions
        _resolved_dimensions = api_module.BleLedPixelAPI._resolved_dimensions

        def __init__(self, options):
            self._entry = SimpleNamespace(options=options)
            self._device_info = None

    on = {OPT_OVERRIDE_DIMENSIONS: True, OPT_PANEL_WIDTH: 32, OPT_PANEL_HEIGHT: 32}
    info = FakeApi(on)._override_only_info()
    assert (info["width"], info["height"]) == (32, 32)
    assert FakeApi({})._override_only_info() is None
    assert FakeApi({**on, OPT_OVERRIDE_DIMENSIONS: False})._override_only_info() is None
    assert FakeApi({**on, OPT_PANEL_HEIGHT: 0})._override_only_info() is None
