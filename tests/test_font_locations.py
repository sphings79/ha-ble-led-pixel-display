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
    (tmp_path / "Mine.ttf").write_bytes((BUNDLED / "3x5-de.ttf").read_bytes())
    (tmp_path / "3x5-de.ttf").write_bytes((BUNDLED / "3x5-de.ttf").read_bytes())
    fonts.set_config_fonts_dir(tmp_path)
    fonts.build_font_index()
    assert "Mine.ttf" in fonts.get_available_fonts()
    assert fonts.get_font_path("Mine") == tmp_path / "Mine.ttf"
    assert fonts.get_font_path("3x5-de.ttf") == tmp_path / "3x5-de.ttf"


def test_an_already_resolved_path_resolves_to_itself():
    """Text mode resolves the font, then the API resolves it again.

    The second pass gets an absolute path. It used to miss the index, log
    "not found" and fall back to VCR_OSD_MONO, so text mode ignored the
    chosen font.
    """
    fonts.build_font_index()
    path = fonts.resolve_font_for_library("OpenSans-Light.ttf")
    assert path == str(BUNDLED / "OpenSans-Light.ttf")
    assert fonts.resolve_font_for_library(path) == path


def test_a_path_outside_the_index_is_not_trusted():
    fonts.build_font_index()
    assert fonts.get_font_path("/nowhere/OpenSans-Light.ttf") is None
