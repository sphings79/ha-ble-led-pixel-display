"""The device page's Slot number and its Save, Show and Clear Slot buttons."""
from __future__ import annotations

import asyncio

import pytest

from tests import ha_stubs

ha_stubs.install()

from homeassistant.exceptions import HomeAssistantError  # noqa: E402

from custom_components.ble_led_pixel import button, common, number  # noqa: E402
from custom_components.ble_led_pixel import api as api_module  # noqa: E402
from custom_components.ble_led_pixel.const import MODE_CLOCK  # noqa: E402
from tests.test_text_ordering import make_api  # noqa: E402


class Api:
    def __init__(self, result=True):
        self.selected_slot = 1
        self.result = result
        self.calls = []
        self.identity = None
        self.device_info = None

    async def show_slot(self, slot):
        self.calls.append(("show", slot))
        return self.result

    async def delete_slot(self, slot):
        self.calls.append(("delete", slot))
        return self.result


def make(cls, api):
    entity = cls.__new__(cls)
    entity.hass = None
    entity._api = api
    entity._name = "Panel"
    return entity


def test_buttons_act_on_the_chosen_slot():
    api = Api()
    slot = number.BleLedPixelSlot.__new__(number.BleLedPixelSlot)
    slot._api = api
    slot.async_write_ha_state = lambda: None
    asyncio.run(slot.async_set_native_value(4.0))
    asyncio.run(make(button.BleLedPixelShowSlotButton, api).async_press())
    asyncio.run(make(button.BleLedPixelClearSlotButton, api).async_press())
    assert api.calls == [("show", 4), ("delete", 4)]


def test_save_button_resends_the_current_content_into_the_slot(monkeypatch):
    api = Api()
    api.selected_slot = 7
    seen = {}

    async def update(hass, name, api_, text=None, save_slot=0):
        seen["save_slot"] = save_slot
        return True

    monkeypatch.setattr(button, "update_panel_display", update)
    asyncio.run(make(button.BleLedPixelSaveSlotButton, api).async_press())
    assert seen == {"save_slot": 7}


def test_a_failed_press_is_reported():
    api = Api(result=False)
    with pytest.raises(HomeAssistantError):
        asyncio.run(make(button.BleLedPixelClearSlotButton, api).async_press())


def test_clock_mode_cannot_be_saved(monkeypatch):
    async def setting(*args, **kwargs):
        return MODE_CLOCK

    async def clock(*args, **kwargs):
        raise AssertionError("clock mode must not be sent when saving")

    monkeypatch.setattr(common, "_get_entity_setting", setting)
    monkeypatch.setattr(common, "_update_clock_mode", clock)
    assert asyncio.run(common.update_panel_display(None, "Panel", make_api(), save_slot=2)) is False


def test_rendered_text_reaches_the_slot(monkeypatch):
    seen = {}

    def image_command(**kwargs):
        seen["save_slot"] = kwargs["save_slot"]
        return "plan"

    monkeypatch.setattr(api_module, "render_text_to_png", lambda *a: b"png")
    monkeypatch.setattr(api_module, "make_image_command", image_command)
    api = make_api()
    assert asyncio.run(api.display_text("hi", save_slot=5))
    assert seen == {"save_slot": 5}
    assert api._bluetooth.sent == ["other content"]
