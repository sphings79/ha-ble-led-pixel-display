"""Device page layout: everyday controls up top, settings under Configuration."""
from __future__ import annotations

import pytest

from tests import ha_stubs

ha_stubs.install()

from homeassistant.const import EntityCategory  # noqa: E402

from custom_components.ble_led_pixel import (  # noqa: E402
    button,
    light,
    number,
    select,
    switch,
    text,
)

CONTROLS = [
    switch.BleLedPixelSwitch,
    select.BleLedPixelModeSelect,
    text.BleLedPixelTextDisplay,
    number.BleLedPixelBrightness,
    button.BleLedPixelUpdateButton,
]
CONFIGURATION = [
    switch.BleLedPixelAntialiasingSwitch,
    switch.BleLedPixelAutoUpdateSwitch,
    switch.BleLedPixelClock24HSwitch,
    switch.BleLedPixelClockShowDateSwitch,
    select.BleLedPixelFontSelect,
    select.BleLedPixelClockStyleSelect,
    select.BleLedPixelTextEffectSelect,
    select.BleLedPixelTextGradientSelect,
    select.BleLedPixelTextSizeSelect,
    number.BleLedPixelFontSize,
    number.BleLedPixelLineSpacing,
    number.BleLedPixelTextSpeed,
    button.BleLedPixelSyncTimeButton,
    button.BleLedPixelSaveSlotButton,
    button.BleLedPixelShowSlotButton,
    button.BleLedPixelClearSlotButton,
    number.BleLedPixelSlot,
    light.BleLedPixelTextColorLight,
    light.BleLedPixelBackgroundColorLight,
]


@pytest.mark.parametrize("cls", CONTROLS + CONFIGURATION)
def test_names_are_prefixed_with_the_device(cls):
    assert cls._attr_has_entity_name is True


@pytest.mark.parametrize("cls", CONFIGURATION)
def test_settings_live_under_configuration(cls):
    assert cls._attr_entity_category is EntityCategory.CONFIG


@pytest.mark.parametrize("cls", CONTROLS)
def test_everyday_controls_stay_in_controls(cls):
    assert "_attr_entity_category" not in vars(cls)


def test_light_names_sort_with_the_text_settings():
    assert light.BleLedPixelTextColorLight._light_name == "Text Color"
    assert light.BleLedPixelBackgroundColorLight._light_name == "Text Background Color"
