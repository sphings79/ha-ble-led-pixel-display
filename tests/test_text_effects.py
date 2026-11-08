"""Only effect codes that pypixelcolor accepts are offered."""
from __future__ import annotations

import re
from pathlib import Path

from custom_components.ble_led_pixel.const import ALL_TEXT_EFFECTS, TEXT_EFFECTS

PACKAGE = Path(__file__).resolve().parent.parent / "custom_components" / "ble_led_pixel"

# pypixelcolor 0.5 rejects anything above 7 (Laser is 8 and is not yet accepted).
HIGHEST_ACCEPTED = 7


def test_no_offered_effect_is_above_what_the_library_accepts():
    assert max(ALL_TEXT_EFFECTS.values()) <= HIGHEST_ACCEPTED


def test_laser_is_not_offered():
    assert "Laser" not in TEXT_EFFECTS


def test_action_schema_and_picker_agree_with_the_limit():
    schema = (PACKAGE / "services.py").read_text(encoding="utf-8")
    assert f"vol.Range(min=0, max={HIGHEST_ACCEPTED})" in schema
    yaml = (PACKAGE / "services.yaml").read_text(encoding="utf-8")
    assert "Laser" not in yaml
    assert not re.search(r'value: "8"', yaml)
