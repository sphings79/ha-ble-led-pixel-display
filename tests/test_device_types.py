"""Panel geometry lookup."""
from custom_components.ble_led_pixel.device_types import (
    DEFAULT_CLOCK_STYLE_COUNT,
    DEFAULT_FRAME_SIZE,
    DEVICE_TYPE_MAP,
    LED_SIZE_MAP,
    clock_style_count,
    resolve_panel,
)


def test_every_device_type_maps_to_a_known_size():
    for device_type, led_type in DEVICE_TYPE_MAP.items():
        assert led_type in LED_SIZE_MAP, device_type


def test_64x20_panel():
    # Type 133 is the 64x20 panel this fork is tested on.
    spec = resolve_panel(133)
    assert (spec.width, spec.height) == (64, 20)
    assert spec.led_type == 5
    assert spec.frame_size == DEFAULT_FRAME_SIZE


def test_pid_overrides_device_type():
    assert resolve_panel(129).led_type == 2
    spec = resolve_panel(129, "55")
    assert spec.led_type == 21
    assert spec.frame_size == 12288


def test_unknown_device_type_is_none_not_a_guess():
    for device_type in (None, 7, 200):
        spec = resolve_panel(device_type)
        assert spec.width is None and spec.height is None
        assert spec.frame_size == DEFAULT_FRAME_SIZE


def test_clock_style_count():
    assert clock_style_count(32, 16) == 10
    assert clock_style_count(64, 20) == DEFAULT_CLOCK_STYLE_COUNT
    assert clock_style_count(None, 16) == DEFAULT_CLOCK_STYLE_COUNT
