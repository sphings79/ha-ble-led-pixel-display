"""Font locations: /config/fonts comes first and survives HACS updates."""
from __future__ import annotations

from pathlib import Path

import pytest

from custom_components.ble_led_pixel import fonts

BUNDLED = Path(fonts.__file__).parent / "fonts"


@pytest.fixture(autouse=True)
def _reset():
    yield
    fonts.set_config_fonts_dir(None)
    fonts.build_font_index()


def test_config_fonts_dir_is_searched_first(tmp_path):
    fonts.set_config_fonts_dir(tmp_path)
    locations = fonts.get_font_locations()
    assert locations[0] == tmp_path
    assert locations[1] == BUNDLED


def test_missing_config_dir_is_skipped(tmp_path):
    fonts.set_config_fonts_dir(tmp_path / "absent")
    assert fonts.get_font_locations()[0] == BUNDLED


def test_user_font_is_offered_and_overrides_bundled(tmp_path):
    (tmp_path / "Mine.ttf").write_bytes((BUNDLED / "5x5.ttf").read_bytes())
    (tmp_path / "7x5.ttf").write_bytes((BUNDLED / "5x5.ttf").read_bytes())
    fonts.set_config_fonts_dir(tmp_path)
    fonts.build_font_index()
    assert "Mine.ttf" in fonts.get_available_fonts()
    assert fonts.get_font_path("Mine") == tmp_path / "Mine.ttf"
    assert fonts.get_font_path("7x5.ttf") == tmp_path / "7x5.ttf"
