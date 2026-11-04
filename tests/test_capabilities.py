"""Per-panel feature table."""
from custom_components.ble_led_pixel.capabilities import resolve_features


def test_unknown_led_type_has_no_features():
    assert resolve_features(None) == frozenset()
    assert resolve_features(999) == frozenset()


def test_large_panels_share_a_set():
    assert resolve_features(25) == resolve_features(33)
    assert resolve_features(25)
