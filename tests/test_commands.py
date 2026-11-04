"""Command frames sent to the panel."""
import pytest

from custom_components.ble_led_pixel.device import commands


def test_power():
    assert commands.make_power_command(True) == bytes([5, 0, 7, 1, 1])
    assert commands.make_power_command(False) == bytes([5, 0, 7, 1, 0])


def test_brightness_frame_and_range():
    assert commands.make_brightness_command(50) == bytes([5, 0, 0x04, 0x80, 50])
    for bad in (0, 101):
        with pytest.raises(ValueError):
            commands.make_brightness_command(bad)


def test_command_payload_length_counts_header():
    frame = commands.make_command_payload(0x1234, b"\x01\x02\x03")
    assert frame == bytes([7, 0, 0x34, 0x12, 1, 2, 3])


def test_scoreboard_is_big_endian():
    assert commands.make_scoreboard_command(258, 3) == bytes(
        [8, 0, 0x0A, 0x80, 1, 2, 0, 3]
    )


def test_countdown_and_stopwatch():
    assert commands.make_countdown_command(True, 5, 30) == bytes(
        [7, 0, 0x0D, 0x80, 1, 5, 30]
    )
    assert commands.make_stopwatch_command(False) == bytes([5, 0, 9, 0x80, 0])


def test_password_packs_digit_pairs():
    assert commands.make_verify_password_command("123456") == bytes(
        [7, 0, 5, 2, 12, 34, 56]
    )
    assert commands.make_verify_password_command("1234", digits=4) == bytes(
        [7, 0, 5, 2, 12, 34, 0]
    )
    assert commands.make_set_password_command("123456", enable=False) == bytes(
        [8, 0, 4, 2, 0, 12, 34, 56]
    )


@pytest.mark.parametrize("password", ["12345", "12345a", "1234567"])
def test_malformed_password_rejected(password):
    with pytest.raises(ValueError):
        commands.make_verify_password_command(password)
    with pytest.raises(ValueError):
        commands.make_set_password_command(password)


def test_password_length_by_model():
    assert commands.password_length("0035", "01") == 4
    assert commands.password_length("0035", "02") == 6
    assert commands.password_length(None, None) == 6
