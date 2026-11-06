"""Text-mode fonts: sidecar metrics and the built-in fallback."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pypixelcolor.lib.font_config import UNIFONT_PATH, FontConfig

from custom_components.ble_led_pixel.device.text import (
    BUILTIN_FONT,
    make_text_command,
    resolve_text_font,
)

FONTS = Path(__file__).parent.parent / "custom_components" / "ble_led_pixel" / "fonts"


def test_missing_or_unset_font_uses_builtin():
    assert resolve_text_font(None, 16) == BUILTIN_FONT
    assert resolve_text_font("CUSONG", 16) == BUILTIN_FONT
    assert resolve_text_font("/nope/CUSONG.ttf", 16) == BUILTIN_FONT


def test_pypixelcolor_unifont_file_uses_builtin_tuning():
    assert resolve_text_font(UNIFONT_PATH, 16) == BUILTIN_FONT


def test_sidecar_json_metrics_are_applied():
    cfg = resolve_text_font(str(FONTS / "3x5-de.ttf"), 32)
    assert isinstance(cfg, FontConfig)
    assert cfg.font_size == 25
    assert cfg.offset == (0, 2)
    assert cfg.pixel_threshold == 85
    assert cfg.var_width is True


def test_closest_height_metrics_are_used():
    cfg = resolve_text_font(str(FONTS / "3x5-de.ttf"), 20)
    assert cfg.font_size == 12  # the 16 entry is closer to 20 than 24


def test_font_without_json_gets_defaults(tmp_path):
    font = tmp_path / "Plain.ttf"
    font.write_bytes((FONTS / "3x5-de.ttf").read_bytes())
    cfg = resolve_text_font(str(font), 16)
    assert cfg.font_size == 16
    assert cfg.offset == (0, 0)
    assert cfg.var_width is False
    assert cfg.pixel_threshold == 70


@pytest.mark.parametrize(
    "metrics",
    [
        "nope",
        {"16": "invalid"},
        {"16": {"font_size": 16, "offset": {}}},
        {"16": {"font_size": 16, "offset": [1]}},
        {"16": {"font_size": 16, "offset": ["a", 0]}},
        {"16": {"font_size": "big", "offset": [0, 0]}},
        {"16": {"font_size": 16, "offset": [0, 0], "var_width": "false"}},
        {"16": {"font_size": float("inf"), "offset": [0, 0]}},
        {"16": {"font_size": 16, "offset": [float("inf"), 0]}},
        {"16": {"font_size": 0, "offset": [0, 0]}},
        {"16": {"font_size": 16, "offset": [0, 0], "pixel_threshold": -1}},
        {"16": {"font_size": 16, "offset": [0, 0], "pixel_threshold": 256}},
    ],
)
def test_bad_json_falls_back_to_defaults(tmp_path, metrics):
    font = tmp_path / "Odd.ttf"
    font.write_bytes((FONTS / "3x5-de.ttf").read_bytes())
    (tmp_path / "Odd.json").write_text(json.dumps({"metrics": metrics}))
    cfg = resolve_text_font(str(font), 16)
    assert isinstance(cfg, FontConfig)  # the user's font, not the fallback
    assert cfg.pixel_threshold == 70
    assert cfg.font_size == 16
    assert cfg.offset == (0, 0)


@pytest.mark.parametrize(
    "font", [None, str(FONTS / "3x5-de.ttf"), str(FONTS / "OpenSans-Light.ttf")]
)
def test_text_command_builds(font):
    plan = make_text_command(
        "HomeAssistant!", font=font, animation=1, rainbow_mode=1, char_height=16
    )
    assert plan.windows


@pytest.mark.parametrize("font", sorted(FONTS.glob("*.ttf")), ids=lambda p: p.stem)
@pytest.mark.parametrize("height", [16, 24, 32])
def test_every_bundled_font_builds_and_has_a_licence(font, height):
    plan = make_text_command("Hello 12:34", font=str(font), char_height=height)
    assert plan.windows
    if font.stem not in {"3x5-de", "Lepidos", "VCR_OSD_MONO", "WP7xn", "OpenSans-Light"}:
        assert (FONTS / f"OFL-{font.stem}.txt").is_file()
