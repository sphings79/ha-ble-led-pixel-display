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
